"""Deterministic nested parameter-search primitives for Optimizer Hub 4B-3.

This module owns only canonical parameter/search identity, inner temporal fold
construction and explicit resource-budget preflight. Candidate execution and
outer OOS evaluation remain in the existing research/Portfolio authorities.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Iterable

import pandas as pd

from apps.api.app.quant.allocation import AllocationMethod
from apps.api.app.research.walk_forward import WalkForwardPeriod, validate_period_schedule

PARAMETER_OPTIMIZATION_CONTRACT_VERSION = (
    "optimizer-hub-parameter-optimization-2026-08-18.1"
)
PARAMETER_OPTIMIZATION_HASH_ALGORITHM = "sha256-canonical-json-v1"
PARAMETER_OPTIMIZATION_OBJECTIVE_POLICY = "inner-oos-sortino-lexicographic-v1"
PARAMETER_OPTIMIZATION_SELECTOR_POLICY = "dual-momentum-nested-parameter-optimization-v1"

ALLOCATION_METHOD_ORDER: tuple[AllocationMethod, ...] = (
    "equal",
    "inverse_volatility",
    "risk_parity_erc",
)
_ALLOCATION_ORDER = {method: index for index, method in enumerate(ALLOCATION_METHOD_ORDER)}


@dataclass(frozen=True, slots=True)
class ParameterCandidate:
    """One canonical Dual Momentum + allocation parameter tuple."""

    lookback_months: int
    top_k: int
    absolute_threshold: float
    allocation_method: AllocationMethod
    parameter_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.lookback_months, int)
            or isinstance(self.lookback_months, bool)
            or not 1 <= self.lookback_months <= 60
        ):
            raise ValueError("lookback_months must be an integer between 1 and 60")
        if (
            not isinstance(self.top_k, int)
            or isinstance(self.top_k, bool)
            or self.top_k < 1
        ):
            raise ValueError("top_k must be a positive integer")
        threshold = float(self.absolute_threshold)
        if not math.isfinite(threshold):
            raise ValueError("absolute_threshold must be finite")
        if self.allocation_method not in _ALLOCATION_ORDER:
            raise ValueError("unsupported allocation_method")
        object.__setattr__(self, "absolute_threshold", 0.0 if threshold == 0.0 else threshold)
        object.__setattr__(self, "parameter_hash", _canonical_hash(self.identity_payload()))

    def identity_payload(self) -> dict[str, Any]:
        return {
            "contractVersion": PARAMETER_OPTIMIZATION_CONTRACT_VERSION,
            "lookbackMonths": self.lookback_months,
            "topK": self.top_k,
            "absoluteThreshold": self.absolute_threshold,
            "allocationMethod": self.allocation_method,
        }

    def export_payload(self) -> dict[str, Any]:
        payload = self.identity_payload()
        current = _canonical_hash(payload)
        if current != self.parameter_hash:
            raise ValueError("parameter candidate identity mismatch")
        return {**payload, "parameterHash": self.parameter_hash}


@dataclass(frozen=True, slots=True)
class ParameterSearchSpace:
    """Normalized bounded Cartesian search space with deterministic identity."""

    lookback_months: tuple[int, ...]
    top_k: tuple[int, ...]
    absolute_thresholds: tuple[float, ...]
    allocation_methods: tuple[AllocationMethod, ...]
    search_space_hash: str = field(init=False)

    def __post_init__(self) -> None:
        lookbacks = _canonical_ints(
            self.lookback_months,
            label="lookback_months",
            minimum=1,
            maximum=60,
        )
        top_k = _canonical_ints(self.top_k, label="top_k", minimum=1, maximum=None)
        thresholds = _canonical_thresholds(self.absolute_thresholds)
        methods = _canonical_allocation_methods(self.allocation_methods)
        object.__setattr__(self, "lookback_months", lookbacks)
        object.__setattr__(self, "top_k", top_k)
        object.__setattr__(self, "absolute_thresholds", thresholds)
        object.__setattr__(self, "allocation_methods", methods)
        object.__setattr__(self, "search_space_hash", _canonical_hash(self.identity_payload()))

    @property
    def candidate_count(self) -> int:
        return (
            len(self.lookback_months)
            * len(self.top_k)
            * len(self.absolute_thresholds)
            * len(self.allocation_methods)
        )

    @property
    def maximum_lookback_months(self) -> int:
        return max(self.lookback_months)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "contractVersion": PARAMETER_OPTIMIZATION_CONTRACT_VERSION,
            "lookbackMonths": list(self.lookback_months),
            "topK": list(self.top_k),
            "absoluteThreshold": list(self.absolute_thresholds),
            "allocationMethod": list(self.allocation_methods),
        }

    def export_payload(self) -> dict[str, Any]:
        payload = self.identity_payload()
        current = _canonical_hash(payload)
        if current != self.search_space_hash:
            raise ValueError("parameter search-space identity mismatch")
        return {
            **payload,
            "candidateCount": self.candidate_count,
            "searchSpaceHash": self.search_space_hash,
        }


@dataclass(frozen=True, slots=True)
class InnerValidationSpec:
    """Bounded rolling-month inner validation policy."""

    fold_count: int
    evaluation_months: int = 1
    step_months: int = 1

    def __post_init__(self) -> None:
        for label, value in (
            ("fold_count", self.fold_count),
            ("evaluation_months", self.evaluation_months),
            ("step_months", self.step_months),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{label} must be a positive integer")
        if self.step_months < self.evaluation_months:
            raise ValueError(
                "step_months must be >= evaluation_months so inner OOS folds do not overlap"
            )

    def export_payload(self) -> dict[str, int]:
        return {
            "foldCount": self.fold_count,
            "evaluationMonths": self.evaluation_months,
            "stepMonths": self.step_months,
        }


@dataclass(frozen=True, slots=True)
class InnerFoldSchedule:
    """Chronologically ordered inner folds fully contained in outer Training."""

    periods: tuple[WalkForwardPeriod, ...]
    schedule_hash: str = field(init=False)

    def __post_init__(self) -> None:
        ordered = validate_period_schedule(self.periods)
        object.__setattr__(self, "periods", ordered)
        object.__setattr__(self, "schedule_hash", _canonical_hash(self.identity_payload()))

    def identity_payload(self) -> dict[str, Any]:
        return {
            "contractVersion": PARAMETER_OPTIMIZATION_CONTRACT_VERSION,
            "periods": [
                {
                    "periodId": period.period_id,
                    "trainingStart": period.training_start.isoformat(),
                    "trainingEnd": period.training_end.isoformat(),
                    "decisionDate": period.decision_date.isoformat(),
                    "evaluationStart": period.evaluation_start.isoformat(),
                    "evaluationEnd": period.evaluation_end.isoformat(),
                    "decisionTiming": period.decision_timing,
                }
                for period in self.periods
            ],
        }

    def export_payload(self) -> dict[str, Any]:
        payload = self.identity_payload()
        current = _canonical_hash(payload)
        if current != self.schedule_hash:
            raise ValueError("inner fold schedule identity mismatch")
        return {**payload, "innerFoldScheduleHash": self.schedule_hash}


@dataclass(frozen=True, slots=True)
class TuningBudget:
    """Caller-supplied hard ceilings; production values require benchmark evidence."""

    max_parameter_candidates: int
    max_inner_folds: int
    max_tuning_evaluations: int

    def __post_init__(self) -> None:
        for label, value in (
            ("max_parameter_candidates", self.max_parameter_candidates),
            ("max_inner_folds", self.max_inner_folds),
            ("max_tuning_evaluations", self.max_tuning_evaluations),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{label} must be a positive integer")

    def validate(
        self,
        *,
        candidate_count: int,
        inner_fold_count: int,
        outer_period_count: int = 1,
    ) -> int:
        for label, value in (
            ("candidate_count", candidate_count),
            ("inner_fold_count", inner_fold_count),
            ("outer_period_count", outer_period_count),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{label} must be a positive integer")
        if candidate_count > self.max_parameter_candidates:
            raise ValueError(
                f"parameter search contains {candidate_count} candidates, exceeding budget "
                f"{self.max_parameter_candidates}"
            )
        if inner_fold_count > self.max_inner_folds:
            raise ValueError(
                f"inner validation requests {inner_fold_count} folds, exceeding budget "
                f"{self.max_inner_folds}"
            )
        planned = candidate_count * inner_fold_count * outer_period_count
        if planned > self.max_tuning_evaluations:
            raise ValueError(
                f"parameter search plans {planned} candidate-fold evaluations, exceeding budget "
                f"{self.max_tuning_evaluations}"
            )
        return planned


@dataclass(frozen=True, slots=True)
class ParameterSearchPlan:
    search_space: ParameterSearchSpace
    candidates: tuple[ParameterCandidate, ...]
    inner_validation: InnerValidationSpec
    planned_tuning_evaluations: int
    plan_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if len(self.candidates) != self.search_space.candidate_count:
            raise ValueError("candidate materialization does not match normalized search space")
        object.__setattr__(self, "plan_hash", _canonical_hash(self.identity_payload()))

    def identity_payload(self) -> dict[str, Any]:
        return {
            "contractVersion": PARAMETER_OPTIMIZATION_CONTRACT_VERSION,
            "objectivePolicyVersion": PARAMETER_OPTIMIZATION_OBJECTIVE_POLICY,
            "searchSpaceHash": self.search_space.search_space_hash,
            "candidateParameterHashes": [candidate.parameter_hash for candidate in self.candidates],
            "innerValidation": self.inner_validation.export_payload(),
            "plannedTuningEvaluations": self.planned_tuning_evaluations,
        }

    def export_payload(self) -> dict[str, Any]:
        payload = self.identity_payload()
        current = _canonical_hash(payload)
        if current != self.plan_hash:
            raise ValueError("parameter search plan identity mismatch")
        return {**payload, "planHash": self.plan_hash}


def enumerate_parameter_candidates(
    search_space: ParameterSearchSpace,
    *,
    risky_symbol_count: int,
) -> tuple[ParameterCandidate, ...]:
    """Materialize candidates in canonical order after fixed-universe validation."""

    if (
        not isinstance(risky_symbol_count, int)
        or isinstance(risky_symbol_count, bool)
        or risky_symbol_count < 1
    ):
        raise ValueError("risky_symbol_count must be a positive integer")
    invalid_top_k = [value for value in search_space.top_k if value > risky_symbol_count]
    if invalid_top_k:
        raise ValueError(
            "top_k search values exceed the fixed risky universe size: "
            + ", ".join(str(value) for value in invalid_top_k)
        )
    return tuple(
        ParameterCandidate(
            lookback_months=lookback,
            top_k=top_k,
            absolute_threshold=threshold,
            allocation_method=method,
        )
        for lookback, top_k, threshold, method in itertools.product(
            search_space.lookback_months,
            search_space.top_k,
            search_space.absolute_thresholds,
            search_space.allocation_methods,
        )
    )


def build_parameter_search_plan(
    *,
    search_space: ParameterSearchSpace,
    inner_validation: InnerValidationSpec,
    risky_symbol_count: int,
    outer_period_count: int,
    budget: TuningBudget,
) -> ParameterSearchPlan:
    """Fail closed on resource bounds before candidate execution or market-data work."""

    planned = budget.validate(
        candidate_count=search_space.candidate_count,
        inner_fold_count=inner_validation.fold_count,
        outer_period_count=outer_period_count,
    )
    candidates = enumerate_parameter_candidates(
        search_space,
        risky_symbol_count=risky_symbol_count,
    )
    return ParameterSearchPlan(
        search_space=search_space,
        candidates=candidates,
        inner_validation=inner_validation,
        planned_tuning_evaluations=planned,
    )


def build_inner_fold_schedule(
    *,
    outer_period: WalkForwardPeriod,
    validation: InnerValidationSpec,
    maximum_lookback_months: int,
) -> InnerFoldSchedule:
    """Build newest rolling-month folds using only the outer Training interval."""

    if outer_period.training_end != outer_period.decision_date:
        raise ValueError(
            "parameter optimization v1 requires outer training_end == outer decision_date"
        )
    if (
        not isinstance(maximum_lookback_months, int)
        or isinstance(maximum_lookback_months, bool)
        or not 1 <= maximum_lookback_months <= 60
    ):
        raise ValueError("maximum_lookback_months must be an integer between 1 and 60")

    newest_end = pd.Timestamp(outer_period.training_end)
    generated: list[WalkForwardPeriod] = []
    for reverse_index in range(validation.fold_count):
        evaluation_end_ts = newest_end - pd.DateOffset(
            months=reverse_index * validation.step_months
        )
        evaluation_start_ts = (
            evaluation_end_ts
            - pd.DateOffset(months=validation.evaluation_months)
            + pd.Timedelta(days=1)
        )
        decision_ts = evaluation_start_ts - pd.Timedelta(days=1)
        required_lookback_start = decision_ts - pd.DateOffset(
            months=maximum_lookback_months
        )
        if required_lookback_start.date() < outer_period.training_start:
            raise ValueError(
                "outer Training interval cannot support the requested maximum lookback "
                "and inner fold schedule"
            )
        if evaluation_start_ts.date() <= outer_period.training_start:
            raise ValueError("inner evaluation must leave a non-empty causal training interval")
        if evaluation_end_ts.date() > outer_period.training_end:
            raise ValueError("inner evaluation escaped outer Training end")
        generated.append(
            WalkForwardPeriod(
                period_id=f"{outer_period.period_id}:inner:{validation.fold_count - reverse_index:02d}",
                training_start=outer_period.training_start,
                training_end=decision_ts.date(),
                decision_date=decision_ts.date(),
                evaluation_start=evaluation_start_ts.date(),
                evaluation_end=evaluation_end_ts.date(),
            )
        )

    chronological = tuple(reversed(generated))
    schedule = InnerFoldSchedule(chronological)
    for period in schedule.periods:
        if period.training_start < outer_period.training_start:
            raise ValueError("inner Training started before outer Training")
        if period.evaluation_end > outer_period.training_end:
            raise ValueError("inner Evaluation ended after outer Training")
        if period.evaluation_end >= outer_period.evaluation_start:
            raise ValueError("inner Evaluation touched outer OOS")
    return schedule


def _canonical_ints(
    values: Iterable[int],
    *,
    label: str,
    minimum: int,
    maximum: int | None,
) -> tuple[int, ...]:
    normalized: set[int] = set()
    for value in values:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{label} must contain integers")
        if value < minimum or (maximum is not None and value > maximum):
            bound = f"[{minimum}, {maximum}]" if maximum is not None else f">= {minimum}"
            raise ValueError(f"{label} values must be {bound}")
        normalized.add(value)
    if not normalized:
        raise ValueError(f"{label} requires at least one value")
    return tuple(sorted(normalized))


def _canonical_thresholds(values: Iterable[float]) -> tuple[float, ...]:
    normalized: set[float] = set()
    for value in values:
        threshold = float(value)
        if not math.isfinite(threshold):
            raise ValueError("absolute_thresholds must be finite")
        normalized.add(0.0 if threshold == 0.0 else threshold)
    if not normalized:
        raise ValueError("absolute_thresholds requires at least one value")
    return tuple(sorted(normalized))


def _canonical_allocation_methods(
    values: Iterable[AllocationMethod],
) -> tuple[AllocationMethod, ...]:
    unique = set(values)
    unsupported = [value for value in unique if value not in _ALLOCATION_ORDER]
    if unsupported:
        raise ValueError("unsupported allocation methods: " + ", ".join(sorted(unsupported)))
    if not unique:
        raise ValueError("allocation_methods requires at least one value")
    return tuple(sorted(unique, key=_ALLOCATION_ORDER.__getitem__))


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
