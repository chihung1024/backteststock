"""Nested inner-OOS candidate evaluation for Optimizer Hub 4B-3.

The tuner receives only one outer Training ResearchDataset. It derives inner
Training/Evaluation views from that object, freezes each inner Decision before
its Evaluation view is validated, and delegates continuous OOS accounting and
metrics to the existing Walk-Forward + Portfolio v3 authority.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

from apps.api.app.portfolio.models import SimulationConfig
from apps.api.app.research.dataset import ResearchDataset
from apps.api.app.research.dataset_views import slice_research_dataset
from apps.api.app.research.momentum import DualMomentumAllocatedSelectionEngine
from apps.api.app.research.oos_ledger import (
    WalkForwardEvaluation,
    run_continuous_oos_ledger,
)
from apps.api.app.research.parameter_optimization import (
    PARAMETER_OPTIMIZATION_CONTRACT_VERSION,
    PARAMETER_OPTIMIZATION_OBJECTIVE_POLICY,
    InnerFoldSchedule,
    ParameterCandidate,
    ParameterSearchPlan,
    build_inner_fold_schedule,
)
from apps.api.app.research.selection import run_configured_selection
from apps.api.app.research.walk_forward import ConfiguredResearchUniverse, WalkForwardPeriod

PARAMETER_TUNING_RESULT_CONTRACT_VERSION = (
    "optimizer-hub-parameter-tuning-result-2026-08-18.1"
)


@dataclass(frozen=True, slots=True)
class CandidateTuningSummary:
    parameter_hash: str
    parameters: dict[str, Any]
    status: str
    completed_fold_count: int
    failed_fold: str | None
    failure_reason: str | None
    sortino: float | None
    max_drawdown: float | None
    cagr: float | None
    transaction_costs: float | None
    inner_oos_identity: str | None
    decision_hashes: tuple[str, ...]
    evaluation_dataset_hashes: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return self.status == "eligible"

    def export_payload(self) -> dict[str, Any]:
        return {
            "parameterHash": self.parameter_hash,
            "parameters": dict(self.parameters),
            "status": self.status,
            "completedFoldCount": self.completed_fold_count,
            "failedFold": self.failed_fold,
            "failureReason": self.failure_reason,
            "innerOosMetricSummary": {
                "sortino": self.sortino,
                "maxDrawdown": self.max_drawdown,
                "cagr": self.cagr,
                "transactionCosts": self.transaction_costs,
            },
            "innerOosIdentity": self.inner_oos_identity,
            "decisionHashes": list(self.decision_hashes),
            "evaluationDatasetHashes": list(self.evaluation_dataset_hashes),
        }


@dataclass(frozen=True, slots=True)
class ParameterTuningResult:
    outer_training_dataset_hash: str
    inner_fold_schedule: InnerFoldSchedule
    search_plan_hash: str
    candidates: tuple[CandidateTuningSummary, ...]
    winner_parameter_hash: str
    winner_parameters: dict[str, Any]
    winner_rank: int
    result_hash: str
    contract_version: str = PARAMETER_TUNING_RESULT_CONTRACT_VERSION

    def export_payload(self) -> dict[str, Any]:
        payload = _result_identity_payload(
            outer_training_dataset_hash=self.outer_training_dataset_hash,
            inner_fold_schedule_hash=self.inner_fold_schedule.schedule_hash,
            search_plan_hash=self.search_plan_hash,
            candidates=self.candidates,
            winner_parameter_hash=self.winner_parameter_hash,
            winner_parameters=self.winner_parameters,
            winner_rank=self.winner_rank,
        )
        current = _canonical_hash(payload)
        if current != self.result_hash:
            raise ValueError("parameter tuning result identity mismatch")
        return {
            "contractVersion": self.contract_version,
            "tuningContractVersion": PARAMETER_OPTIMIZATION_CONTRACT_VERSION,
            "objectivePolicyVersion": PARAMETER_OPTIMIZATION_OBJECTIVE_POLICY,
            "outerTrainingDatasetHash": self.outer_training_dataset_hash,
            "innerFoldSchedule": self.inner_fold_schedule.export_payload(),
            "searchPlanHash": self.search_plan_hash,
            "candidateCount": len(self.candidates),
            "candidates": [item.export_payload() for item in self.candidates],
            "winnerParameterHash": self.winner_parameter_hash,
            "winnerParameters": dict(self.winner_parameters),
            "winnerRank": self.winner_rank,
            "resultHash": self.result_hash,
        }


def run_inner_parameter_tuning(
    *,
    outer_period: WalkForwardPeriod,
    outer_training_dataset: ResearchDataset,
    configured_universe: ConfiguredResearchUniverse,
    risky_symbols: tuple[str, ...],
    defensive_symbols: tuple[str, ...],
    search_plan: ParameterSearchPlan,
    simulation_config: SimulationConfig,
) -> ParameterTuningResult:
    """Evaluate every canonical candidate without any outer Evaluation dataset."""

    outer_training_dataset.export_payload()
    configured_universe.export_payload()
    if outer_training_dataset.requested_start != outer_period.training_start:
        raise ValueError("outer Training dataset requested_start mismatch")
    if outer_training_dataset.requested_end != outer_period.training_end:
        raise ValueError("outer Training dataset requested_end mismatch")
    if tuple(outer_training_dataset.requested_symbols) != configured_universe.members:
        raise ValueError("outer Training dataset membership differs from configured universe")
    expected_members = (*risky_symbols, *defensive_symbols)
    if configured_universe.members != expected_members:
        raise ValueError("configured universe must equal risky symbols followed by defensive symbols")

    schedule = build_inner_fold_schedule(
        outer_period=outer_period,
        validation=search_plan.inner_validation,
        maximum_lookback_months=search_plan.search_space.maximum_lookback_months,
    )
    summaries = tuple(
        _evaluate_candidate(
            candidate=candidate,
            schedule=schedule,
            outer_training_dataset=outer_training_dataset,
            configured_universe=configured_universe,
            risky_symbols=risky_symbols,
            defensive_symbols=defensive_symbols,
            simulation_config=simulation_config,
        )
        for candidate in search_plan.candidates
    )
    ranked = rank_candidate_summaries(summaries)
    winner = ranked[0]
    payload = _result_identity_payload(
        outer_training_dataset_hash=outer_training_dataset.dataset_hash,
        inner_fold_schedule_hash=schedule.schedule_hash,
        search_plan_hash=search_plan.plan_hash,
        candidates=summaries,
        winner_parameter_hash=winner.parameter_hash,
        winner_parameters=winner.parameters,
        winner_rank=1,
    )
    return ParameterTuningResult(
        outer_training_dataset_hash=outer_training_dataset.dataset_hash,
        inner_fold_schedule=schedule,
        search_plan_hash=search_plan.plan_hash,
        candidates=summaries,
        winner_parameter_hash=winner.parameter_hash,
        winner_parameters=dict(winner.parameters),
        winner_rank=1,
        result_hash=_canonical_hash(payload),
    )


def rank_candidate_summaries(
    summaries: tuple[CandidateTuningSummary, ...],
) -> tuple[CandidateTuningSummary, ...]:
    """Apply the transparent V1 Sortino-first lexicographic ranking."""

    eligible = tuple(item for item in summaries if item.eligible)
    if not eligible:
        raise ValueError("parameter optimization produced no eligible candidate")
    for item in eligible:
        for label, value in (
            ("sortino", item.sortino),
            ("max_drawdown", item.max_drawdown),
            ("cagr", item.cagr),
            ("transaction_costs", item.transaction_costs),
        ):
            if value is None or not math.isfinite(float(value)):
                raise ValueError(f"eligible candidate has unavailable {label}")
    return tuple(
        sorted(
            eligible,
            key=lambda item: (
                -float(item.sortino),
                abs(float(item.max_drawdown)),
                -float(item.cagr),
                float(item.transaction_costs),
                item.parameter_hash,
            ),
        )
    )


def _evaluate_candidate(
    *,
    candidate: ParameterCandidate,
    schedule: InnerFoldSchedule,
    outer_training_dataset: ResearchDataset,
    configured_universe: ConfiguredResearchUniverse,
    risky_symbols: tuple[str, ...],
    defensive_symbols: tuple[str, ...],
    simulation_config: SimulationConfig,
) -> CandidateTuningSummary:
    evaluations: list[WalkForwardEvaluation] = []
    decisions: list[str] = []
    evaluation_hashes: list[str] = []

    for fold in schedule.periods:
        try:
            training_dataset = slice_research_dataset(
                outer_training_dataset,
                start=fold.training_start,
                end=fold.training_end,
            )
            engine = DualMomentumAllocatedSelectionEngine(
                risky_symbols=risky_symbols,
                defensive_symbols=defensive_symbols,
                allocation_method=candidate.allocation_method,
                lookback_months=candidate.lookback_months,
                top_k=candidate.top_k,
                absolute_threshold=candidate.absolute_threshold,
            )
            decision = run_configured_selection(
                period=fold,
                configured_universe=configured_universe,
                training_dataset=training_dataset,
                engine=engine,
            )
            evaluation_dataset = slice_research_dataset(
                outer_training_dataset,
                start=fold.evaluation_start,
                end=fold.evaluation_end,
            )
            evaluations.append(
                WalkForwardEvaluation(
                    decision=decision,
                    evaluation_dataset=evaluation_dataset,
                )
            )
            decisions.append(decision.decision_hash)
            evaluation_hashes.append(evaluation_dataset.dataset_hash)
        except (TypeError, ValueError) as exc:
            return CandidateTuningSummary(
                parameter_hash=candidate.parameter_hash,
                parameters=candidate.identity_payload(),
                status="failed",
                completed_fold_count=len(evaluations),
                failed_fold=fold.period_id,
                failure_reason=f"{type(exc).__name__}: {exc}",
                sortino=None,
                max_drawdown=None,
                cagr=None,
                transaction_costs=None,
                inner_oos_identity=None,
                decision_hashes=tuple(decisions),
                evaluation_dataset_hashes=tuple(evaluation_hashes),
            )

    try:
        oos = run_continuous_oos_ledger(
            evaluations,
            simulation_config,
            name=f"Inner Parameter Tuning:{candidate.parameter_hash[:12]}",
        )
    except (TypeError, ValueError) as exc:
        return CandidateTuningSummary(
            parameter_hash=candidate.parameter_hash,
            parameters=candidate.identity_payload(),
            status="failed",
            completed_fold_count=len(evaluations),
            failed_fold=None,
            failure_reason=f"{type(exc).__name__}: {exc}",
            sortino=None,
            max_drawdown=None,
            cagr=None,
            transaction_costs=None,
            inner_oos_identity=None,
            decision_hashes=tuple(decisions),
            evaluation_dataset_hashes=tuple(evaluation_hashes),
        )

    metrics = oos.metrics.metrics
    sortino = _finite_metric(metrics.get("sortino_ratio"))
    max_drawdown = _finite_metric(metrics.get("max_drawdown"))
    cagr = _finite_metric(metrics.get("cagr"))
    transaction_costs = _finite_metric(metrics.get("transaction_costs"))
    if None in {sortino, max_drawdown, cagr, transaction_costs}:
        return CandidateTuningSummary(
            parameter_hash=candidate.parameter_hash,
            parameters=candidate.identity_payload(),
            status="failed",
            completed_fold_count=len(evaluations),
            failed_fold=None,
            failure_reason="authoritative inner OOS objective metrics are unavailable",
            sortino=sortino,
            max_drawdown=max_drawdown,
            cagr=cagr,
            transaction_costs=transaction_costs,
            inner_oos_identity=None,
            decision_hashes=tuple(decisions),
            evaluation_dataset_hashes=tuple(evaluation_hashes),
        )

    identity_payload = {
        "contractVersion": PARAMETER_TUNING_RESULT_CONTRACT_VERSION,
        "parameterHash": candidate.parameter_hash,
        "decisionHashes": decisions,
        "evaluationDatasetHashes": evaluation_hashes,
        "oosContractVersion": oos.contract_version,
        "metricContextVersion": oos.metrics.metadata.get("metric_context_version"),
        "sortino": sortino,
        "maxDrawdown": max_drawdown,
        "cagr": cagr,
        "transactionCosts": transaction_costs,
    }
    return CandidateTuningSummary(
        parameter_hash=candidate.parameter_hash,
        parameters=candidate.identity_payload(),
        status="eligible",
        completed_fold_count=len(evaluations),
        failed_fold=None,
        failure_reason=None,
        sortino=sortino,
        max_drawdown=max_drawdown,
        cagr=cagr,
        transaction_costs=transaction_costs,
        inner_oos_identity=_canonical_hash(identity_payload),
        decision_hashes=tuple(decisions),
        evaluation_dataset_hashes=tuple(evaluation_hashes),
    )


def _finite_metric(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _result_identity_payload(
    *,
    outer_training_dataset_hash: str,
    inner_fold_schedule_hash: str,
    search_plan_hash: str,
    candidates: tuple[CandidateTuningSummary, ...],
    winner_parameter_hash: str,
    winner_parameters: dict[str, Any],
    winner_rank: int,
) -> dict[str, Any]:
    return {
        "contractVersion": PARAMETER_TUNING_RESULT_CONTRACT_VERSION,
        "tuningContractVersion": PARAMETER_OPTIMIZATION_CONTRACT_VERSION,
        "objectivePolicyVersion": PARAMETER_OPTIMIZATION_OBJECTIVE_POLICY,
        "outerTrainingDatasetHash": outer_training_dataset_hash,
        "innerFoldScheduleHash": inner_fold_schedule_hash,
        "searchPlanHash": search_plan_hash,
        "candidateSummaries": [item.export_payload() for item in candidates],
        "winnerParameterHash": winner_parameter_hash,
        "winnerParameters": dict(winner_parameters),
        "winnerRank": winner_rank,
    }


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
