"""Request-scoped Walk-Forward orchestration over the existing research authorities.

The original PIT + Exhaustive route remains unchanged. Optimizer Hub strategy
selectors are additive dispatch paths that reuse the same ResearchDataset,
DecisionSnapshot, Evaluation and Portfolio v3 OOS authorities.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any, Callable

import pandas as pd

from api import date_policy, exhaustive_optimizer
from apps.api.app.data.history_service import PartialTWDHistories, TWDHistoryService
from apps.api.app.portfolio.models import SimulationConfig
from apps.api.app.quant.covariance import RISK_MATH_CONTRACT_VERSION
from apps.api.app.research.dataset import ResearchDatasetService, build_research_dataset
from apps.api.app.research.exhaustive_authority_http import HttpExhaustiveAuthorityRunner
from apps.api.app.research.exhaustive_selection import (
    ExhaustiveAuthorityRunner,
    ExhaustiveSelectionEngine,
)
from apps.api.app.research.momentum import (
    DualMomentumAllocatedSelectionEngine,
    DualMomentumSelectionEngine,
)
from apps.api.app.research.oos_ledger import (
    WALK_FORWARD_OOS_LEDGER_CONTRACT_VERSION,
    WalkForwardEvaluation,
    WalkForwardOOSResult,
    run_continuous_oos_ledger,
)
from apps.api.app.research.parameter_optimization import (
    PARAMETER_OPTIMIZATION_CONTRACT_VERSION,
    PARAMETER_OPTIMIZATION_OBJECTIVE_POLICY,
    PARAMETER_OPTIMIZATION_SELECTOR_POLICY,
    InnerValidationSpec,
    ParameterSearchPlan,
    ParameterSearchSpace,
    TuningBudget,
    build_parameter_search_plan,
)
from apps.api.app.research.parameter_refit import refit_parameter_tuning_winner
from apps.api.app.research.parameter_tuning import run_inner_parameter_tuning
from apps.api.app.research.pit_client import PITUniverseClient, PITUniverseResolver
from apps.api.app.research.selection import (
    run_configured_selection,
    run_selection,
    validate_evaluation_dataset,
)
from apps.api.app.research.walk_forward import (
    ConfiguredResearchUniverse,
    DecisionSnapshot,
    WalkForwardPeriod,
    validate_period_schedule,
)

WALK_FORWARD_JOB_CONTRACT_VERSION = "walk-forward-job-2026-08-15.1"
DUAL_MOMENTUM_JOB_CONTRACT_VERSION = "walk-forward-dual-momentum-job-2026-08-17.1"
DUAL_MOMENTUM_ALLOCATION_JOB_CONTRACT_VERSION = (
    "walk-forward-dual-momentum-allocation-job-2026-08-17.1"
)
DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_JOB_CONTRACT_VERSION = (
    "walk-forward-dual-momentum-parameter-optimization-job-2026-08-18.1"
)
WALK_FORWARD_JOB_HASH_ALGORITHM = "sha256-canonical-json-v1"
WALK_FORWARD_PUBLIC_SELECTOR_POLICY = "exhaustive-gross-buy-and-hold-v1"
WALK_FORWARD_DUAL_MOMENTUM_SELECTOR_POLICY = "dual-momentum-configured-monthly-v1"
WALK_FORWARD_DUAL_MOMENTUM_ALLOCATION_SELECTOR_POLICY = (
    "dual-momentum-configured-monthly-allocation-v1"
)
WALK_FORWARD_DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_SELECTOR_POLICY = (
    PARAMETER_OPTIMIZATION_SELECTOR_POLICY
)
WALK_FORWARD_PUBLIC_OOS_POLICY = "decision-transition-cost-only-v1"
MAX_WALK_FORWARD_PERIODS = 24
MAX_SERVER_EXHAUSTIVE_CANDIDATES = 100
MAX_SERVER_EXHAUSTIVE_COMBINATIONS_PER_PERIOD = 500_000
MAX_SERVER_EXHAUSTIVE_COMBINATIONS_PER_JOB = 2_000_000
MAX_PUBLIC_HOLDING_COUNT = 20
MAX_CONFIGURED_STRATEGY_SYMBOLS = 50
# Candidate-stage synchronous safety bounds. Capacity benchmarking is mandatory
# before PR #175 can become Ready and may tighten/raise these values explicitly.
MAX_PARAMETER_CANDIDATES = 48
MAX_INNER_FOLDS = 6
MAX_TUNING_EVALUATIONS_PER_JOB = 216


@dataclass(frozen=True, slots=True)
class WalkForwardSelectorSpec:
    """Existing PIT + Exhaustive public selector specification."""

    universe_id: str
    benchmark_symbol: str
    holding_count: int

    def __post_init__(self) -> None:
        universe = str(self.universe_id or "").strip().lower()
        benchmark = str(self.benchmark_symbol or "").strip().upper()
        if not universe or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789-"
            for character in universe
        ):
            raise ValueError(
                "universe_id must contain only lowercase letters, digits or hyphens"
            )
        if not benchmark or benchmark != benchmark.strip().upper():
            raise ValueError("benchmark_symbol must be canonical")
        if not isinstance(self.holding_count, int) or isinstance(self.holding_count, bool):
            raise TypeError("holding_count must be an integer")
        if not 1 <= self.holding_count <= MAX_PUBLIC_HOLDING_COUNT:
            raise ValueError(
                f"holding_count must be between 1 and {MAX_PUBLIC_HOLDING_COUNT}"
            )
        object.__setattr__(self, "universe_id", universe)
        object.__setattr__(self, "benchmark_symbol", benchmark)


@dataclass(frozen=True, slots=True)
class DualMomentumSelectorSpec:
    """Configured-universe Dual Momentum methodology for Optimizer Hub 4B-1."""

    risky_symbols: tuple[str, ...]
    defensive_symbols: tuple[str, ...]
    lookback_months: int = 12
    top_k: int = 1
    absolute_threshold: float = 0.0
    allocation_method: str | None = None

    def __post_init__(self) -> None:
        risky = _canonical_symbols(self.risky_symbols, label="risky_symbols")
        defensive = _canonical_symbols(
            self.defensive_symbols, label="defensive_symbols"
        )
        if set(risky).intersection(defensive):
            raise ValueError("risky and defensive symbols must not overlap")
        if len(risky) + len(defensive) > MAX_CONFIGURED_STRATEGY_SYMBOLS:
            raise ValueError(
                f"configured strategy supports at most {MAX_CONFIGURED_STRATEGY_SYMBOLS} total symbols"
            )
        if (
            not isinstance(self.lookback_months, int)
            or isinstance(self.lookback_months, bool)
            or not 1 <= self.lookback_months <= 60
        ):
            raise ValueError("lookback_months must be an integer between 1 and 60")
        if (
            not isinstance(self.top_k, int)
            or isinstance(self.top_k, bool)
            or not 1 <= self.top_k <= len(risky)
        ):
            raise ValueError("top_k must be between 1 and the risky universe size")
        threshold = float(self.absolute_threshold)
        if not math.isfinite(threshold):
            raise ValueError("absolute_threshold must be finite")
        if self.allocation_method not in {
            None,
            "equal",
            "inverse_volatility",
            "risk_parity_erc",
        }:
            raise ValueError("unsupported Dual Momentum allocation_method")
        object.__setattr__(self, "risky_symbols", risky)
        object.__setattr__(self, "defensive_symbols", defensive)
        object.__setattr__(
            self, "absolute_threshold", 0.0 if threshold == 0.0 else threshold
        )

    @property
    def configured_members(self) -> tuple[str, ...]:
        return (*self.risky_symbols, *self.defensive_symbols)


@dataclass(frozen=True, slots=True)
class DualMomentumParameterOptimizationSpec:
    """Explicit 4B-3 configured search request; never mutates manual 4B-1/4B-2."""

    risky_symbols: tuple[str, ...]
    defensive_symbols: tuple[str, ...]
    search_space: ParameterSearchSpace
    inner_validation: InnerValidationSpec

    def __post_init__(self) -> None:
        risky = _canonical_symbols(self.risky_symbols, label="risky_symbols")
        defensive = _canonical_symbols(
            self.defensive_symbols, label="defensive_symbols"
        )
        if set(risky).intersection(defensive):
            raise ValueError("risky and defensive symbols must not overlap")
        if len(risky) + len(defensive) > MAX_CONFIGURED_STRATEGY_SYMBOLS:
            raise ValueError(
                f"configured strategy supports at most {MAX_CONFIGURED_STRATEGY_SYMBOLS} total symbols"
            )
        if not isinstance(self.search_space, ParameterSearchSpace):
            raise TypeError("search_space must be ParameterSearchSpace")
        if not isinstance(self.inner_validation, InnerValidationSpec):
            raise TypeError("inner_validation must be InnerValidationSpec")
        if max(self.search_space.top_k) > len(risky):
            raise ValueError(
                "parameter optimization top_k search values cannot exceed risky universe size"
            )
        object.__setattr__(self, "risky_symbols", risky)
        object.__setattr__(self, "defensive_symbols", defensive)

    @property
    def configured_members(self) -> tuple[str, ...]:
        return (*self.risky_symbols, *self.defensive_symbols)


SelectorSpec = (
    WalkForwardSelectorSpec
    | DualMomentumSelectorSpec
    | DualMomentumParameterOptimizationSpec
)


@dataclass(frozen=True, slots=True)
class WalkForwardExecutionSpec:
    initial_amount: float = 10_000.0
    transition_cost_bps: float = 0.0

    def __post_init__(self) -> None:
        initial = float(self.initial_amount)
        cost = float(self.transition_cost_bps)
        if not math.isfinite(initial) or initial <= 0.0 or initial > 1e12:
            raise ValueError("initial_amount must be finite, positive and <= 1e12 TWD")
        if not math.isfinite(cost) or not 0.0 <= cost <= 1000.0:
            raise ValueError("transition_cost_bps must be in [0, 1000]")
        object.__setattr__(self, "initial_amount", initial)
        object.__setattr__(self, "transition_cost_bps", cost)


@dataclass(frozen=True, slots=True)
class WalkForwardJobSpec:
    periods: tuple[WalkForwardPeriod, ...]
    selector: SelectorSpec
    execution: WalkForwardExecutionSpec = WalkForwardExecutionSpec()

    def __post_init__(self) -> None:
        periods = validate_period_schedule(self.periods)
        if len(periods) > MAX_WALK_FORWARD_PERIODS:
            raise ValueError(
                f"walk-forward request supports at most {MAX_WALK_FORWARD_PERIODS} periods"
            )
        if isinstance(self.selector, DualMomentumSelectorSpec):
            _validate_dual_momentum_schedule(periods, self.selector)
        elif isinstance(self.selector, DualMomentumParameterOptimizationSpec):
            _validate_parameter_optimization_schedule(periods, self.selector)
            _parameter_search_plan(self.selector, outer_period_count=len(periods))
        object.__setattr__(self, "periods", periods)


@dataclass(frozen=True, slots=True)
class WalkForwardJobPeriodAudit:
    period_id: str
    pit_member_count: int
    exhaustive_combination_count: int
    training_dataset_hash: str
    authority_dataset_hash: str
    decision_hash: str
    evaluation_dataset_hash: str


@dataclass(frozen=True, slots=True)
class DualMomentumJobPeriodAudit:
    period_id: str
    configured_member_count: int
    training_dataset_hash: str
    decision_hash: str
    evaluation_dataset_hash: str


@dataclass(frozen=True, slots=True)
class TunedDualMomentumJobPeriodAudit:
    period_id: str
    configured_member_count: int
    training_dataset_hash: str
    tuning_result_hash: str
    search_plan_hash: str
    winner_parameter_hash: str
    decision_hash: str
    evaluation_dataset_hash: str


PeriodAudit = (
    WalkForwardJobPeriodAudit
    | DualMomentumJobPeriodAudit
    | TunedDualMomentumJobPeriodAudit
)


@dataclass(frozen=True, slots=True)
class WalkForwardJobResult:
    job_hash: str
    spec: WalkForwardJobSpec
    as_of_date: date
    decisions: tuple[DecisionSnapshot, ...]
    period_audits: tuple[PeriodAudit, ...]
    oos: WalkForwardOOSResult
    contract_version: str = WALK_FORWARD_JOB_CONTRACT_VERSION
    selector_policy: str = WALK_FORWARD_PUBLIC_SELECTOR_POLICY

    def export_payload(self) -> dict[str, Any]:
        return {
            "contractVersion": self.contract_version,
            "jobHash": self.job_hash,
            "hashAlgorithm": WALK_FORWARD_JOB_HASH_ALGORITHM,
            "status": "completed",
            "asOfDate": self.as_of_date.isoformat(),
            "asOfPolicy": date_policy.AS_OF_POLICY,
            "selectorPolicy": self.selector_policy,
            "oosPolicy": WALK_FORWARD_PUBLIC_OOS_POLICY,
            "request": _spec_payload(self.spec),
            "periods": [asdict(item) for item in self.period_audits],
            "decisions": [decision.export_payload() for decision in self.decisions],
            "oos": _oos_payload(self.oos),
        }


class WalkForwardJobService:
    """Execute one synchronous, reproducible Walk-Forward research request."""

    def __init__(
        self,
        *,
        pit_resolver: PITUniverseResolver | None = None,
        history_service: TWDHistoryService | None = None,
        authority_runner_factory: Callable[[], ExhaustiveAuthorityRunner] | None = None,
    ) -> None:
        self._pit_resolver = pit_resolver or PITUniverseClient()
        self._history_service = history_service or TWDHistoryService()
        self._dataset_service = ResearchDatasetService(history_service=self._history_service)
        self._authority_runner_factory = (
            authority_runner_factory or HttpExhaustiveAuthorityRunner
        )

    def run(self, spec: WalkForwardJobSpec) -> WalkForwardJobResult:
        periods = validate_period_schedule(spec.periods)
        complete = date_policy.require_complete_period(
            pd.Timestamp(min(period.training_start for period in periods)),
            pd.Timestamp(max(period.evaluation_end for period in periods) + timedelta(days=1)),
        )
        evaluations: list[WalkForwardEvaluation] = []
        decisions: list[DecisionSnapshot] = []
        audits: list[PeriodAudit] = []
        total_combinations = 0

        exhaustive_selector = (
            spec.selector if isinstance(spec.selector, WalkForwardSelectorSpec) else None
        )
        optimized_selector = (
            spec.selector
            if isinstance(spec.selector, DualMomentumParameterOptimizationSpec)
            else None
        )
        dual_selector = (
            spec.selector if isinstance(spec.selector, DualMomentumSelectorSpec) else None
        )
        runner = self._authority_runner_factory() if exhaustive_selector is not None else None
        configured_selector = dual_selector or optimized_selector
        configured_universe = (
            ConfiguredResearchUniverse(configured_selector.configured_members)
            if configured_selector is not None
            else None
        )
        search_plan = (
            _parameter_search_plan(optimized_selector, outer_period_count=len(periods))
            if optimized_selector is not None
            else None
        )
        risk_free_rate = float(exhaustive_optimizer.legacy.RISK_FREE_RATE)
        oos_config = SimulationConfig(
            initial_amount=spec.execution.initial_amount,
            reinvest_distributions=True,
            transaction_cost_bps=spec.execution.transition_cost_bps,
            risk_free_rate=risk_free_rate,
        )

        for period in periods:
            if exhaustive_selector is not None:
                pit = self._pit_resolver.resolve(
                    exhaustive_selector.universe_id, period.decision_date
                )
                if not pit.membership_authoritative or pit.source_is_proxy:
                    raise ValueError(
                        "public Walk-Forward v1 requires authoritative PIT membership; "
                        f"{pit.universe_id} at {period.decision_date.isoformat()} is proxy/non-authoritative"
                    )
                candidate_count = len(pit.members)
                if candidate_count < exhaustive_optimizer.MIN_SOURCE_TICKERS:
                    raise ValueError(
                        f"PIT universe contains only {candidate_count} candidates; Exhaustive requires at least "
                        f"{exhaustive_optimizer.MIN_SOURCE_TICKERS}"
                    )
                if candidate_count > MAX_SERVER_EXHAUSTIVE_CANDIDATES:
                    raise ValueError(
                        f"PIT universe contains {candidate_count} members, but causal Walk-Forward v1 supports "
                        f"at most {MAX_SERVER_EXHAUSTIVE_CANDIDATES} Exhaustive candidates. The service will not "
                        "silently truncate membership or use current fundamentals as a historical prefilter."
                    )
                if exhaustive_selector.holding_count > candidate_count:
                    raise ValueError("holding_count cannot exceed PIT candidate count")
                if exhaustive_selector.benchmark_symbol in pit.members:
                    raise ValueError("benchmark_symbol cannot also be a PIT candidate")

                combinations = math.comb(candidate_count, exhaustive_selector.holding_count)
                if combinations > MAX_SERVER_EXHAUSTIVE_COMBINATIONS_PER_PERIOD:
                    raise ValueError(
                        f"period {period.period_id} requires {combinations} Exhaustive combinations, exceeding "
                        f"the synchronous server budget {MAX_SERVER_EXHAUSTIVE_COMBINATIONS_PER_PERIOD}"
                    )
                total_combinations += combinations
                if total_combinations > MAX_SERVER_EXHAUSTIVE_COMBINATIONS_PER_JOB:
                    raise ValueError(
                        "walk-forward job exceeds the total synchronous Exhaustive budget "
                        f"{MAX_SERVER_EXHAUSTIVE_COMBINATIONS_PER_JOB} combinations"
                    )

                training_requested = (*pit.members, exhaustive_selector.benchmark_symbol)
                training_batch = self._history_service.histories_partial(
                    list(training_requested),
                    period.training_start,
                    period.training_end,
                )
                training_dataset = build_research_dataset(
                    _subset_histories(training_batch, pit.members),
                    start=period.training_start,
                    end=period.training_end,
                )
                authority_dataset = build_research_dataset(
                    _subset_histories(training_batch, training_requested),
                    start=period.training_start,
                    end=period.training_end,
                )
                if runner is None:
                    raise RuntimeError("Exhaustive authority runner was not initialized")
                engine = ExhaustiveSelectionEngine(
                    authority_dataset=authority_dataset,
                    benchmark_symbol=exhaustive_selector.benchmark_symbol,
                    holding_count=exhaustive_selector.holding_count,
                    rebalance_mode="never",
                    band_ratio=0.20,
                    transaction_cost_bps=0.0,
                    execution_delay_trading_days=1,
                    runner=runner,
                )
                decision = run_selection(
                    period=period,
                    pit_universe=pit,
                    training_dataset=training_dataset,
                    engine=engine,
                )
                audit_factory: PeriodAudit = WalkForwardJobPeriodAudit(
                    period_id=period.period_id,
                    pit_member_count=candidate_count,
                    exhaustive_combination_count=combinations,
                    training_dataset_hash=training_dataset.dataset_hash,
                    authority_dataset_hash=authority_dataset.dataset_hash,
                    decision_hash=decision.decision_hash,
                    evaluation_dataset_hash="",
                )
            elif (
                optimized_selector is not None
                and configured_universe is not None
                and search_plan is not None
            ):
                training_batch = self._history_service.histories_partial(
                    list(configured_universe.members),
                    period.training_start,
                    period.training_end,
                )
                training_dataset = build_research_dataset(
                    training_batch,
                    start=period.training_start,
                    end=period.training_end,
                )
                tuning_result = run_inner_parameter_tuning(
                    outer_period=period,
                    outer_training_dataset=training_dataset,
                    configured_universe=configured_universe,
                    risky_symbols=optimized_selector.risky_symbols,
                    defensive_symbols=optimized_selector.defensive_symbols,
                    search_plan=search_plan,
                    simulation_config=oos_config,
                )
                decision = refit_parameter_tuning_winner(
                    outer_period=period,
                    outer_training_dataset=training_dataset,
                    configured_universe=configured_universe,
                    risky_symbols=optimized_selector.risky_symbols,
                    defensive_symbols=optimized_selector.defensive_symbols,
                    tuning_result=tuning_result,
                )
                audit_factory = TunedDualMomentumJobPeriodAudit(
                    period_id=period.period_id,
                    configured_member_count=len(configured_universe.members),
                    training_dataset_hash=training_dataset.dataset_hash,
                    tuning_result_hash=tuning_result.result_hash,
                    search_plan_hash=search_plan.plan_hash,
                    winner_parameter_hash=tuning_result.winner_parameter_hash,
                    decision_hash=decision.decision_hash,
                    evaluation_dataset_hash="",
                )
            elif dual_selector is not None and configured_universe is not None:
                training_batch = self._history_service.histories_partial(
                    list(configured_universe.members),
                    period.training_start,
                    period.training_end,
                )
                training_dataset = build_research_dataset(
                    training_batch,
                    start=period.training_start,
                    end=period.training_end,
                )
                if dual_selector.allocation_method is None:
                    engine = DualMomentumSelectionEngine(
                        risky_symbols=dual_selector.risky_symbols,
                        defensive_symbols=dual_selector.defensive_symbols,
                        lookback_months=dual_selector.lookback_months,
                        top_k=dual_selector.top_k,
                        absolute_threshold=dual_selector.absolute_threshold,
                    )
                else:
                    engine = DualMomentumAllocatedSelectionEngine(
                        risky_symbols=dual_selector.risky_symbols,
                        defensive_symbols=dual_selector.defensive_symbols,
                        allocation_method=dual_selector.allocation_method,
                        lookback_months=dual_selector.lookback_months,
                        top_k=dual_selector.top_k,
                        absolute_threshold=dual_selector.absolute_threshold,
                    )
                decision = run_configured_selection(
                    period=period,
                    configured_universe=configured_universe,
                    training_dataset=training_dataset,
                    engine=engine,
                )
                audit_factory = DualMomentumJobPeriodAudit(
                    period_id=period.period_id,
                    configured_member_count=len(configured_universe.members),
                    training_dataset_hash=training_dataset.dataset_hash,
                    decision_hash=decision.decision_hash,
                    evaluation_dataset_hash="",
                )
            else:
                raise TypeError("unsupported Walk-Forward selector specification")

            # Causal firewall: for optimized jobs this outer Evaluation fetch remains
            # after inner tuning + full-Outer-Training winner refit + Decision freeze.
            evaluation_batch = self._history_service.histories_partial(
                list(decision.selected_constituents),
                period.evaluation_start,
                period.evaluation_end,
            )
            evaluation_dataset = build_research_dataset(
                evaluation_batch,
                start=period.evaluation_start,
                end=period.evaluation_end,
            )
            validate_evaluation_dataset(
                decision=decision,
                evaluation_dataset=evaluation_dataset,
            )
            evaluations.append(
                WalkForwardEvaluation(
                    decision=decision,
                    evaluation_dataset=evaluation_dataset,
                )
            )
            decisions.append(decision)
            if isinstance(audit_factory, WalkForwardJobPeriodAudit):
                audits.append(
                    WalkForwardJobPeriodAudit(
                        period_id=audit_factory.period_id,
                        pit_member_count=audit_factory.pit_member_count,
                        exhaustive_combination_count=audit_factory.exhaustive_combination_count,
                        training_dataset_hash=audit_factory.training_dataset_hash,
                        authority_dataset_hash=audit_factory.authority_dataset_hash,
                        decision_hash=audit_factory.decision_hash,
                        evaluation_dataset_hash=evaluation_dataset.dataset_hash,
                    )
                )
            elif isinstance(audit_factory, TunedDualMomentumJobPeriodAudit):
                audits.append(
                    TunedDualMomentumJobPeriodAudit(
                        period_id=audit_factory.period_id,
                        configured_member_count=audit_factory.configured_member_count,
                        training_dataset_hash=audit_factory.training_dataset_hash,
                        tuning_result_hash=audit_factory.tuning_result_hash,
                        search_plan_hash=audit_factory.search_plan_hash,
                        winner_parameter_hash=audit_factory.winner_parameter_hash,
                        decision_hash=audit_factory.decision_hash,
                        evaluation_dataset_hash=evaluation_dataset.dataset_hash,
                    )
                )
            else:
                audits.append(
                    DualMomentumJobPeriodAudit(
                        period_id=audit_factory.period_id,
                        configured_member_count=audit_factory.configured_member_count,
                        training_dataset_hash=audit_factory.training_dataset_hash,
                        decision_hash=audit_factory.decision_hash,
                        evaluation_dataset_hash=evaluation_dataset.dataset_hash,
                    )
                )

        oos = run_continuous_oos_ledger(evaluations, oos_config)
        contract_version = _job_contract_version(spec.selector)
        selector_policy = _selector_policy(spec.selector)
        job_hash = _job_hash(
            spec,
            complete.as_of_date,
            audits,
            oos,
            contract_version=contract_version,
        )
        return WalkForwardJobResult(
            job_hash=job_hash,
            spec=spec,
            as_of_date=complete.as_of_date,
            decisions=tuple(decisions),
            period_audits=tuple(audits),
            oos=oos,
            contract_version=contract_version,
            selector_policy=selector_policy,
        )


def _canonical_symbols(values: tuple[str, ...], *, label: str) -> tuple[str, ...]:
    symbols = tuple(str(value) for value in values)
    if not symbols:
        raise ValueError(f"{label} requires at least one symbol")
    if any(not symbol or symbol != symbol.strip().upper() for symbol in symbols):
        raise ValueError(f"{label} must contain canonical symbols")
    if len(set(symbols)) != len(symbols):
        raise ValueError(f"{label} must contain unique symbols")
    return symbols


def _validate_dual_momentum_schedule(
    periods: tuple[WalkForwardPeriod, ...],
    selector: DualMomentumSelectorSpec,
) -> None:
    for period in periods:
        if period.training_end != period.decision_date:
            raise ValueError(
                "Dual Momentum monthly decisions require training_end == decision_date"
            )
        if period.evaluation_start != period.decision_date + timedelta(days=1):
            raise ValueError(
                "Dual Momentum monthly Evaluation must start the calendar day after Decision"
            )
        if (period.evaluation_end - period.decision_date).days > 35:
            raise ValueError(
                "Dual Momentum v1 Evaluation windows may span at most 35 calendar days"
            )
        requested_signal_start = (
            pd.Timestamp(period.decision_date)
            - pd.DateOffset(months=selector.lookback_months)
        ).date()
        if period.training_start > requested_signal_start:
            raise ValueError(
                "Dual Momentum training_start must cover the full configured momentum lookback"
            )

    for previous, current in zip(periods, periods[1:]):
        previous_month = previous.decision_date.year * 12 + previous.decision_date.month
        current_month = current.decision_date.year * 12 + current.decision_date.month
        if current_month != previous_month + 1:
            raise ValueError(
                "Dual Momentum v1 requires one Decision in each consecutive calendar month"
            )
        if previous.evaluation_end != current.decision_date:
            raise ValueError(
                "Dual Momentum monthly periods must hand off at the next Decision date without an OOS gap"
            )


def _validate_parameter_optimization_schedule(
    periods: tuple[WalkForwardPeriod, ...],
    selector: DualMomentumParameterOptimizationSpec,
) -> None:
    maximum_lookback = selector.search_space.maximum_lookback_months
    for period in periods:
        if period.training_end != period.decision_date:
            raise ValueError(
                "Dual Momentum parameter optimization requires training_end == decision_date"
            )
        if period.evaluation_start != period.decision_date + timedelta(days=1):
            raise ValueError(
                "Dual Momentum parameter optimization Evaluation must start the calendar day after Decision"
            )
        if (period.evaluation_end - period.decision_date).days > 35:
            raise ValueError(
                "Dual Momentum parameter optimization Evaluation windows may span at most 35 calendar days"
            )
        requested_signal_start = (
            pd.Timestamp(period.decision_date) - pd.DateOffset(months=maximum_lookback)
        ).date()
        if period.training_start > requested_signal_start:
            raise ValueError(
                "parameter optimization training_start must cover the maximum momentum lookback"
            )

    for previous, current in zip(periods, periods[1:]):
        previous_month = previous.decision_date.year * 12 + previous.decision_date.month
        current_month = current.decision_date.year * 12 + current.decision_date.month
        if current_month != previous_month + 1:
            raise ValueError(
                "Dual Momentum parameter optimization requires one Decision in each consecutive calendar month"
            )
        if previous.evaluation_end != current.decision_date:
            raise ValueError(
                "parameter-optimized monthly periods must hand off at the next Decision date without an OOS gap"
            )


def _parameter_search_plan(
    selector: DualMomentumParameterOptimizationSpec,
    *,
    outer_period_count: int,
) -> ParameterSearchPlan:
    budget = TuningBudget(
        max_parameter_candidates=MAX_PARAMETER_CANDIDATES,
        max_inner_folds=MAX_INNER_FOLDS,
        max_tuning_evaluations=MAX_TUNING_EVALUATIONS_PER_JOB,
    )
    # Job-level resource accounting depends on how many outer periods are in the
    # request, but that operational count must not contaminate the methodology
    # identity of any one outer Decision.
    budget.validate(
        candidate_count=selector.search_space.candidate_count,
        inner_fold_count=selector.inner_validation.fold_count,
        outer_period_count=outer_period_count,
    )
    return build_parameter_search_plan(
        search_space=selector.search_space,
        inner_validation=selector.inner_validation,
        risky_symbol_count=len(selector.risky_symbols),
        outer_period_count=1,
        budget=budget,
    )


def _subset_histories(
    batch: PartialTWDHistories,
    requested: tuple[str, ...],
) -> PartialTWDHistories:
    requested_tuple = tuple(requested)
    histories = {
        symbol: batch.histories[symbol]
        for symbol in requested_tuple
        if symbol in batch.histories
    }
    failures = {
        symbol: batch.failures[symbol]
        for symbol in requested_tuple
        if symbol in batch.failures
    }
    missing = [
        symbol
        for symbol in requested_tuple
        if symbol not in histories and symbol not in failures
    ]
    if missing:
        raise ValueError(
            "shared Training history batch did not account for requested symbols: "
            + ", ".join(missing)
        )
    return PartialTWDHistories(
        requested=requested_tuple,
        histories=histories,
        failures=failures,
    )


def _selector_policy(selector: SelectorSpec) -> str:
    if isinstance(selector, WalkForwardSelectorSpec):
        return WALK_FORWARD_PUBLIC_SELECTOR_POLICY
    if isinstance(selector, DualMomentumParameterOptimizationSpec):
        return WALK_FORWARD_DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_SELECTOR_POLICY
    if isinstance(selector, DualMomentumSelectorSpec):
        if selector.allocation_method is None:
            return WALK_FORWARD_DUAL_MOMENTUM_SELECTOR_POLICY
        return WALK_FORWARD_DUAL_MOMENTUM_ALLOCATION_SELECTOR_POLICY
    raise TypeError("unsupported Walk-Forward selector specification")


def _job_contract_version(selector: SelectorSpec) -> str:
    if isinstance(selector, WalkForwardSelectorSpec):
        return WALK_FORWARD_JOB_CONTRACT_VERSION
    if isinstance(selector, DualMomentumParameterOptimizationSpec):
        return DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_JOB_CONTRACT_VERSION
    if isinstance(selector, DualMomentumSelectorSpec):
        if selector.allocation_method is None:
            return DUAL_MOMENTUM_JOB_CONTRACT_VERSION
        return DUAL_MOMENTUM_ALLOCATION_JOB_CONTRACT_VERSION
    raise TypeError("unsupported Walk-Forward selector specification")


def _spec_payload(spec: WalkForwardJobSpec) -> dict[str, Any]:
    selector = spec.selector
    if isinstance(selector, WalkForwardSelectorSpec):
        selector_payload: dict[str, Any] = {
            "universe": selector.universe_id,
            "benchmark": selector.benchmark_symbol,
            "holdingCount": selector.holding_count,
            "rebalanceMode": "never",
            "trainingTransactionCostBps": 0.0,
            "executionDelayTradingDays": 1,
        }
    elif isinstance(selector, DualMomentumParameterOptimizationSpec):
        selector_payload = {
            "strategy": "dual_momentum",
            "riskySymbols": list(selector.risky_symbols),
            "defensiveSymbols": list(selector.defensive_symbols),
            "parameterOptimization": {
                "contractVersion": PARAMETER_OPTIMIZATION_CONTRACT_VERSION,
                "objectivePolicyVersion": PARAMETER_OPTIMIZATION_OBJECTIVE_POLICY,
                "searchSpace": selector.search_space.export_payload(),
                "innerValidation": selector.inner_validation.export_payload(),
            },
            "rebalanceFrequency": "monthly",
            "weighting": "parameter_optimized",
            "signalAuthority": "ResearchDataset.daily_levels_twd",
            "allocationReturnAuthority": "ResearchDataset.daily_returns_twd",
            "allocationCovarianceAuthority": (
                f"{RISK_MATH_CONTRACT_VERSION}/ledoit-wolf"
            ),
        }
    elif isinstance(selector, DualMomentumSelectorSpec):
        selector_payload = {
            "strategy": "dual_momentum",
            "riskySymbols": list(selector.risky_symbols),
            "defensiveSymbols": list(selector.defensive_symbols),
            "lookbackMonths": selector.lookback_months,
            "topK": selector.top_k,
            "absoluteThreshold": selector.absolute_threshold,
            "rebalanceFrequency": "monthly",
            "weighting": "equal",
            "signalAuthority": "ResearchDataset.daily_levels_twd",
        }
        if selector.allocation_method is not None:
            selector_payload["allocationMethod"] = selector.allocation_method
            selector_payload["weighting"] = selector.allocation_method
            selector_payload["allocationReturnAuthority"] = (
                "ResearchDataset.daily_returns_twd"
            )
            selector_payload["allocationCovarianceAuthority"] = (
                f"{RISK_MATH_CONTRACT_VERSION}/ledoit-wolf"
            )
    else:
        raise TypeError("unsupported Walk-Forward selector specification")

    return {
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
            for period in spec.periods
        ],
        "selector": selector_payload,
        "execution": {
            "initialAmountTwd": spec.execution.initial_amount,
            "transitionCostBps": spec.execution.transition_cost_bps,
            "inSegmentRebalance": "none",
            "reinvestDistributions": True,
            "cashflows": "none",
            "leverage": "none",
            "riskFreeRate": float(exhaustive_optimizer.legacy.RISK_FREE_RATE),
        },
    }


def _oos_payload(result: WalkForwardOOSResult) -> dict[str, Any]:
    ledger = result.ledger
    return {
        "contractVersion": result.contract_version,
        "executionPolicy": result.execution_policy,
        "gapPolicy": result.gap_policy,
        "returnComponentPolicy": result.return_component_policy,
        "periods": [asdict(item) for item in result.periods],
        "ledger": {
            "contractVersion": ledger.contract_version,
            "valuationCurrency": "TWD",
            "equity": [
                {"date": timestamp.date().isoformat(), "value": float(value)}
                for timestamp, value in ledger.equity.items()
            ],
            "returnIndex": [
                {"date": timestamp.date().isoformat(), "value": float(value)}
                for timestamp, value in ledger.return_index.items()
            ],
            "transactionCosts": float(ledger.transaction_costs),
            "borrowingCosts": float(ledger.borrowing_costs),
            "rebalanceCount": int(ledger.rebalance_count),
            "liquidated": bool(ledger.liquidated),
            "warnings": list(ledger.warnings),
            "events": [
                {
                    "date": event.date,
                    "type": event.type,
                    "details": dict(event.details),
                }
                for event in ledger.events
            ],
        },
        "metrics": asdict(result.metrics),
    }


def _job_hash(
    spec: WalkForwardJobSpec,
    as_of_date: date,
    audits: list[PeriodAudit],
    oos: WalkForwardOOSResult,
    *,
    contract_version: str,
) -> str:
    payload = {
        "contractVersion": contract_version,
        "asOfDate": as_of_date.isoformat(),
        "asOfPolicy": date_policy.AS_OF_POLICY,
        "request": _spec_payload(spec),
        "periods": [asdict(item) for item in audits],
        "oosContractVersion": WALK_FORWARD_OOS_LEDGER_CONTRACT_VERSION,
        "oosPeriodDecisionHashes": [item.decision_hash for item in oos.periods],
        "oosPeriodDatasetHashes": [item.evaluation_dataset_hash for item in oos.periods],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
