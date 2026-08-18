"""Full-Outer-Training refit seam for Optimizer Hub 4B-3.

Nested tuning chooses parameters only. This module reruns the winning parameter
set on the complete outer Training ResearchDataset and binds compact tuning
identity plus full tuning evidence into the existing configured DecisionSnapshot
before any outer Evaluation dataset can be consumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Mapping

from apps.api.app.research.dataset import ResearchDataset
from apps.api.app.research.momentum import DualMomentumAllocatedSelectionEngine
from apps.api.app.research.parameter_optimization import (
    PARAMETER_OPTIMIZATION_CONTRACT_VERSION,
    PARAMETER_OPTIMIZATION_OBJECTIVE_POLICY,
    ParameterCandidate,
)
from apps.api.app.research.parameter_tuning import ParameterTuningResult
from apps.api.app.research.selection import (
    SelectionContext,
    SelectionResult,
    run_configured_selection,
)
from apps.api.app.research.walk_forward import (
    ConfiguredResearchUniverse,
    DecisionSnapshot,
    WalkForwardPeriod,
)

TUNED_DUAL_MOMENTUM_ENGINE_VERSION = (
    "dual-momentum-parameter-optimized-selection-2026-08-18.1"
)
TUNED_DUAL_MOMENTUM_RULE = "dual-momentum-nested-parameter-optimization-refit-v1"


@dataclass(frozen=True, slots=True)
class TunedDualMomentumSelectionEngine:
    """Refit one already-selected parameter winner on full outer Training."""

    risky_symbols: tuple[str, ...]
    defensive_symbols: tuple[str, ...]
    tuning_result: ParameterTuningResult

    contract_version: ClassVar[str] = TUNED_DUAL_MOMENTUM_ENGINE_VERSION
    rule: ClassVar[str] = TUNED_DUAL_MOMENTUM_RULE

    def __post_init__(self) -> None:
        self.tuning_result.export_payload()
        winner = _winner_candidate(self.tuning_result)
        base = self._base_engine(winner)
        object.__setattr__(self, "risky_symbols", base.risky_symbols)
        object.__setattr__(self, "defensive_symbols", base.defensive_symbols)

    @property
    def parameters(self) -> Mapping[str, Any]:
        winner = _winner_candidate(self.tuning_result)
        return {
            "optimizationContractVersion": PARAMETER_OPTIMIZATION_CONTRACT_VERSION,
            "objectivePolicyVersion": PARAMETER_OPTIMIZATION_OBJECTIVE_POLICY,
            "tuningResultContractVersion": self.tuning_result.contract_version,
            "tuningResultHash": self.tuning_result.result_hash,
            "searchPlanHash": self.tuning_result.search_plan_hash,
            "innerFoldScheduleHash": self.tuning_result.inner_fold_schedule.schedule_hash,
            "winnerParameterHash": winner.parameter_hash,
            "winnerParameters": winner.identity_payload(),
            "refitPolicy": "winner-on-full-outer-training-v1",
            "refitDatasetAuthority": "ResearchDataset",
        }

    def select(self, context: SelectionContext) -> SelectionResult:
        if context.training_dataset.dataset_hash != self.tuning_result.outer_training_dataset_hash:
            raise ValueError(
                "parameter winner must be refit on the exact outer Training dataset used for tuning"
            )
        winner = _winner_candidate(self.tuning_result)
        base_result = self._base_engine(winner).select(context)
        evidence = dict(base_result.evidence)
        evidence["parameterOptimization"] = self.tuning_result.export_payload()
        evidence["parameterOptimizationRefit"] = {
            "policy": "winner-on-full-outer-training-v1",
            "outerTrainingDatasetHash": context.training_dataset.dataset_hash,
            "winnerParameterHash": winner.parameter_hash,
        }
        return SelectionResult(
            selected_constituents=base_result.selected_constituents,
            weights=base_result.weights,
            evidence=evidence,
        )

    def _base_engine(
        self,
        winner: ParameterCandidate,
    ) -> DualMomentumAllocatedSelectionEngine:
        return DualMomentumAllocatedSelectionEngine(
            risky_symbols=self.risky_symbols,
            defensive_symbols=self.defensive_symbols,
            allocation_method=winner.allocation_method,
            lookback_months=winner.lookback_months,
            top_k=winner.top_k,
            absolute_threshold=winner.absolute_threshold,
        )


def refit_parameter_tuning_winner(
    *,
    outer_period: WalkForwardPeriod,
    outer_training_dataset: ResearchDataset,
    configured_universe: ConfiguredResearchUniverse,
    risky_symbols: tuple[str, ...],
    defensive_symbols: tuple[str, ...],
    tuning_result: ParameterTuningResult,
) -> DecisionSnapshot:
    """Create the final outer DecisionSnapshot before outer Evaluation is available."""

    tuning_result.export_payload()
    if tuning_result.outer_training_dataset_hash != outer_training_dataset.dataset_hash:
        raise ValueError("tuning result does not belong to this outer Training dataset")
    engine = TunedDualMomentumSelectionEngine(
        risky_symbols=risky_symbols,
        defensive_symbols=defensive_symbols,
        tuning_result=tuning_result,
    )
    return run_configured_selection(
        period=outer_period,
        configured_universe=configured_universe,
        training_dataset=outer_training_dataset,
        engine=engine,
    )


def _winner_candidate(tuning_result: ParameterTuningResult) -> ParameterCandidate:
    raw = tuning_result.winner_parameters
    try:
        candidate = ParameterCandidate(
            lookback_months=int(raw["lookbackMonths"]),
            top_k=int(raw["topK"]),
            absolute_threshold=float(raw["absoluteThreshold"]),
            allocation_method=raw["allocationMethod"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("tuning result winner parameters are invalid") from exc
    if candidate.parameter_hash != tuning_result.winner_parameter_hash:
        raise ValueError("tuning result winner parameter identity mismatch")
    return candidate
