"""Causal selection orchestration for walk-forward research.

Batch 4A-2 keeps selection physically separated from Evaluation/OOS data. A
selector receives one exact-window training ResearchDataset plus immutable PIT
membership/accounting, and the result is frozen through the Batch 4A-1
DecisionSnapshot contract before any evaluation dataset may be consumed.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, ClassVar, Mapping, Protocol

from apps.api.app.research.dataset import ResearchDataset
from apps.api.app.research.walk_forward import (
    DecisionSnapshot,
    ResolvedPITUniverse,
    WalkForwardPeriod,
    create_decision_snapshot,
)

WALK_FORWARD_SELECTION_CONTRACT_VERSION = "walk-forward-selection-2026-08-15.1"
CONFIGURED_EQUAL_WEIGHT_ENGINE_VERSION = "configured-equal-weight-reference-2026-08-15.1"


@dataclass(frozen=True, slots=True)
class UnavailableCandidate:
    """One PIT member with an explicit training-history failure."""

    symbol: str
    stage: str
    detail: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class SelectionContext:
    """Exact inputs visible to a SelectionEngine.

    Deliberately absent: Evaluation/OOS market data. The period contains future
    date boundaries, but no future observations or evaluation dataset.
    """

    period: WalkForwardPeriod
    pit_universe: ResolvedPITUniverse
    training_dataset: ResearchDataset
    eligible_candidates: tuple[str, ...]
    unavailable_candidates: tuple[UnavailableCandidate, ...]
    contract_version: ClassVar[str] = WALK_FORWARD_SELECTION_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """Pure portfolio choice returned by a selector before OOS evaluation."""

    selected_constituents: tuple[str, ...]
    weights: tuple[float, ...]


class SelectionEngine(Protocol):
    """Framework-neutral selector boundary for later adapters."""

    contract_version: str
    rule: str

    @property
    def parameters(self) -> Mapping[str, Any]:
        ...

    def select(self, context: SelectionContext) -> SelectionResult:
        ...


@dataclass(frozen=True, slots=True)
class ConfiguredEqualWeightSelectionEngine:
    """Reference engine used to verify orchestration, not an investment strategy.

    It makes no ranking claim and intentionally reads no price series. Batch
    4A-3 will adapt the existing Exhaustive authority behind SelectionEngine.
    """

    selected_symbols: tuple[str, ...]
    contract_version: ClassVar[str] = CONFIGURED_EQUAL_WEIGHT_ENGINE_VERSION
    rule: ClassVar[str] = "configured-equal-weight-reference"

    def __post_init__(self) -> None:
        selected = tuple(str(symbol) for symbol in self.selected_symbols)
        if not selected:
            raise ValueError("configured reference selection requires at least one symbol")
        if any(symbol != symbol.strip().upper() for symbol in selected):
            raise ValueError("configured symbols must already be canonical symbols")
        if len(set(selected)) != len(selected):
            raise ValueError("configured symbols must be unique")
        object.__setattr__(self, "selected_symbols", selected)

    @property
    def parameters(self) -> Mapping[str, Any]:
        return {
            "configuredSymbols": list(self.selected_symbols),
            "weighting": "equal",
        }

    def select(self, context: SelectionContext) -> SelectionResult:
        eligible = set(context.eligible_candidates)
        missing = [symbol for symbol in self.selected_symbols if symbol not in eligible]
        if missing:
            raise ValueError(
                "configured symbols are not eligible in the training dataset: "
                + ", ".join(missing)
            )
        weight = 1.0 / len(self.selected_symbols)
        return SelectionResult(
            selected_constituents=self.selected_symbols,
            weights=tuple(weight for _ in self.selected_symbols),
        )


def build_selection_context(
    *,
    period: WalkForwardPeriod,
    pit_universe: ResolvedPITUniverse,
    training_dataset: ResearchDataset,
) -> SelectionContext:
    """Validate the exact training/PIT accounting visible to a selector."""

    if pit_universe.requested_as_of != period.decision_date:
        raise ValueError("PIT requested_as_of must equal the walk-forward decision_date")
    if training_dataset.requested_start != period.training_start:
        raise ValueError("training dataset requested_start must equal training_start")
    if training_dataset.requested_end != period.training_end:
        raise ValueError("training dataset requested_end must equal training_end")
    if tuple(training_dataset.requested_symbols) != tuple(pit_universe.members):
        raise ValueError(
            "training dataset requested symbols must exactly match PIT membership order"
        )

    _assert_dataset_identity(training_dataset, label="training")

    effective_start = training_dataset.effective_start
    effective_end = training_dataset.effective_end
    if effective_start is None or effective_end is None:
        raise ValueError("training dataset has no effective TWD observations")
    if effective_start < period.training_start or effective_end > period.training_end:
        raise ValueError("training dataset effective observations escape training window")
    if effective_end > period.decision_date:
        raise ValueError("training dataset effective observations extend beyond decision")

    requested = tuple(training_dataset.requested_symbols)
    resolved = tuple(training_dataset.resolved_symbols)
    failure_symbols = tuple(training_dataset.failures)
    if len(set(requested)) != len(requested):
        raise ValueError("training dataset requested symbols must be unique")
    if any(symbol != symbol.strip().upper() for symbol in requested):
        raise ValueError("training dataset symbols must already be canonical")
    if not set(resolved).issubset(set(requested)):
        raise ValueError("training resolved symbols must be a subset of requested symbols")
    if not set(failure_symbols).issubset(set(requested)):
        raise ValueError("training failure symbols must be a subset of requested symbols")
    if set(resolved).intersection(failure_symbols):
        raise ValueError("training candidate cannot be both resolved and failed")
    if set(resolved).union(failure_symbols) != set(requested):
        raise ValueError("every PIT member must have an explicit training outcome")

    resolved_set = set(resolved)
    eligible = tuple(symbol for symbol in requested if symbol in resolved_set)
    unavailable = tuple(
        UnavailableCandidate(
            symbol=symbol,
            stage=training_dataset.failures[symbol].stage,
            detail=training_dataset.failures[symbol].detail,
            retryable=bool(training_dataset.failures[symbol].retryable),
        )
        for symbol in requested
        if symbol in training_dataset.failures
    )
    if not eligible:
        raise ValueError("selection requires at least one eligible training candidate")

    return SelectionContext(
        period=period,
        pit_universe=pit_universe,
        training_dataset=training_dataset,
        eligible_candidates=eligible,
        unavailable_candidates=unavailable,
    )


def run_selection(
    *,
    period: WalkForwardPeriod,
    pit_universe: ResolvedPITUniverse,
    training_dataset: ResearchDataset,
    engine: SelectionEngine,
) -> DecisionSnapshot:
    """Run one selector with no Evaluation/OOS dataset in scope and freeze it."""

    context = build_selection_context(
        period=period,
        pit_universe=pit_universe,
        training_dataset=training_dataset,
    )
    training_hash = training_dataset.dataset_hash

    engine_contract_version = _required_text(
        getattr(engine, "contract_version", None),
        label="selector contract_version",
    )
    selector_contract_version = (
        f"{WALK_FORWARD_SELECTION_CONTRACT_VERSION}+{engine_contract_version}"
    )
    selector_rule = _required_text(
        getattr(engine, "rule", None),
        label="selector rule",
    )
    raw_parameters = getattr(engine, "parameters", None)
    if not isinstance(raw_parameters, Mapping):
        raise TypeError("selector parameters must be a mapping")
    selector_parameters = copy.deepcopy(dict(raw_parameters))

    result = engine.select(context)
    if not isinstance(result, SelectionResult):
        raise TypeError("selector must return SelectionResult")

    _assert_same_dataset_identity(
        training_dataset,
        expected_hash=training_hash,
        label="training",
    )
    if training_dataset.effective_start is None or training_dataset.effective_end is None:
        raise ValueError("training dataset lost its effective observations")

    return create_decision_snapshot(
        period=period,
        pit_universe=pit_universe,
        training_dataset_hash=training_hash,
        training_effective_start=training_dataset.effective_start,
        training_effective_end=training_dataset.effective_end,
        selector_contract_version=selector_contract_version,
        selector_rule=selector_rule,
        selector_parameters=selector_parameters,
        eligible_candidates=context.eligible_candidates,
        selected_constituents=result.selected_constituents,
        weights=result.weights,
    )


def validate_evaluation_dataset(
    *,
    decision: DecisionSnapshot,
    evaluation_dataset: ResearchDataset,
) -> ResearchDataset:
    """Validate OOS data only after the decision is already immutable."""

    decision.export_payload()
    period = decision.period
    if evaluation_dataset.requested_start != period.evaluation_start:
        raise ValueError("evaluation dataset requested_start must equal evaluation_start")
    if evaluation_dataset.requested_end != period.evaluation_end:
        raise ValueError("evaluation dataset requested_end must equal evaluation_end")

    _assert_dataset_identity(evaluation_dataset, label="evaluation")
    effective_start = evaluation_dataset.effective_start
    effective_end = evaluation_dataset.effective_end
    if effective_start is None or effective_end is None:
        raise ValueError("evaluation dataset has no effective TWD observations")
    if effective_start < period.evaluation_start or effective_end > period.evaluation_end:
        raise ValueError("evaluation dataset effective observations escape evaluation window")

    requested = set(evaluation_dataset.requested_symbols)
    resolved = set(evaluation_dataset.resolved_symbols)
    selected = set(decision.selected_constituents)
    if not selected.issubset(requested):
        raise ValueError("evaluation dataset must request every selected constituent")
    if not selected.issubset(resolved):
        missing = sorted(selected - resolved)
        raise ValueError(
            "evaluation dataset is missing selected constituent history: "
            + ", ".join(missing)
        )
    return evaluation_dataset


def _assert_dataset_identity(dataset: ResearchDataset, *, label: str) -> str:
    payload = dataset.export_payload()
    dataset_hash = str(dataset.dataset_hash).strip().lower()
    if not dataset_hash or payload.get("datasetHash") != dataset_hash:
        raise ValueError(f"{label} dataset identity is missing or inconsistent")
    return dataset_hash


def _assert_same_dataset_identity(
    dataset: ResearchDataset,
    *,
    expected_hash: str,
    label: str,
) -> None:
    current_hash = _assert_dataset_identity(dataset, label=label)
    if current_hash != expected_hash:
        raise ValueError(f"{label} dataset identity changed during selection")


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()
