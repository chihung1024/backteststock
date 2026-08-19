from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from apps.api.app.data.history_service import PartialTWDHistories, TWDAssetHistory
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.research.parameter_optimization import (
    InnerValidationSpec,
    ParameterSearchSpace,
)
from apps.api.app.research.walk_forward import WalkForwardPeriod
from apps.api.app.research.walk_forward_job import (
    DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_JOB_CONTRACT_VERSION,
    MAX_PARAMETER_CANDIDATES,
    WALK_FORWARD_DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_SELECTOR_POLICY,
    DualMomentumParameterOptimizationSpec,
    TunedDualMomentumJobPeriodAudit,
    WalkForwardExecutionSpec,
    WalkForwardJobService,
    WalkForwardJobSpec,
    _job_contract_version,
    _parameter_search_plan,
    _selector_policy,
    _spec_payload,
)


def _period() -> WalkForwardPeriod:
    return WalkForwardPeriod(
        period_id="2025-12",
        training_start=date(2023, 1, 31),
        training_end=date(2025, 12, 31),
        decision_date=date(2025, 12, 31),
        evaluation_start=date(2026, 1, 1),
        evaluation_end=date(2026, 1, 30),
    )


def _selector() -> DualMomentumParameterOptimizationSpec:
    return DualMomentumParameterOptimizationSpec(
        risky_symbols=("AAA", "BBB"),
        defensive_symbols=("BND",),
        search_space=ParameterSearchSpace(
            lookback_months=(6, 12),
            top_k=(1,),
            absolute_thresholds=(0.0,),
            allocation_methods=("equal",),
        ),
        inner_validation=InnerValidationSpec(
            fold_count=3,
            evaluation_months=1,
            step_months=1,
        ),
    )


def _asset_history(
    symbol: str,
    levels: pd.Series,
) -> TWDAssetHistory:
    native = levels.rename("native_adjusted_close")
    fx = pd.Series(1.0, index=levels.index, dtype=float, name="fx_to_twd")
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency="TWD",
        valuation=TWDValuation(
            source_currency="TWD",
            native_adjusted_close=native,
            fx_to_twd=fx,
            adjusted_close_twd=levels.rename("adjusted_close_twd"),
            daily_returns=levels.pct_change(fill_method=None)
            .fillna(0.0)
            .rename("daily_return"),
        ),
        corporate_action_audit={"status": "verified_standard_actions"},
        fx_audit={"method": "identity", "tickers": []},
        raw_quote_currency="TWD",
        native_price_scale=1.0,
    )


class RecordingHistoryService:
    def __init__(self) -> None:
        dates = pd.bdate_range("2023-01-31", "2026-01-30")
        phase = np.arange(len(dates), dtype=float)
        daily_by_symbol = {
            "AAA": 0.0008 + 0.0100 * np.sin(phase / 8.0),
            "BBB": 0.0006 + 0.0090 * np.cos(phase / 10.0),
            "BND": 0.00015 + 0.0025 * np.sin(phase / 17.0),
        }
        self._levels = {
            symbol: pd.Series(
                100.0 * np.cumprod(1.0 + daily),
                index=dates,
                dtype=float,
            )
            for symbol, daily in daily_by_symbol.items()
        }
        self.calls: list[tuple[tuple[str, ...], date, date]] = []

    def histories_partial(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> PartialTWDHistories:
        requested = tuple(symbols)
        self.calls.append((requested, start, end))
        histories: dict[str, TWDAssetHistory] = {}
        for symbol in requested:
            source = self._levels[symbol]
            sliced = source.loc[
                (source.index.date >= start) & (source.index.date <= end)
            ].copy()
            histories[symbol] = _asset_history(symbol, sliced)
        return PartialTWDHistories(
            requested=requested,
            histories=histories,
            failures={},
        )


def test_explicit_optimization_has_separate_job_and_selector_identity() -> None:
    selector = _selector()
    spec = WalkForwardJobSpec(periods=(_period(),), selector=selector)

    assert _job_contract_version(selector) == (
        DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_JOB_CONTRACT_VERSION
    )
    assert _selector_policy(selector) == (
        WALK_FORWARD_DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_SELECTOR_POLICY
    )
    payload = _spec_payload(spec)["selector"]
    optimization = payload["parameterOptimization"]
    assert payload["strategy"] == "dual_momentum"
    assert payload["weighting"] == "parameter_optimized"
    assert "lookbackMonths" not in payload
    assert "allocationMethod" not in payload
    assert optimization["searchSpace"]["lookbackMonths"] == [6, 12]
    assert optimization["searchSpace"]["candidateCount"] == 2
    assert optimization["innerValidation"]["foldCount"] == 3


def test_per_period_search_plan_identity_is_independent_of_job_scope() -> None:
    selector = _selector()

    single_period = _parameter_search_plan(selector, outer_period_count=1)
    twelve_periods = _parameter_search_plan(selector, outer_period_count=12)

    assert single_period.plan_hash == twelve_periods.plan_hash
    assert single_period.planned_tuning_evaluations == 6
    assert twelve_periods.planned_tuning_evaluations == 6


def test_budget_preflight_rejects_oversized_search_before_service_execution() -> None:
    search = ParameterSearchSpace(
        lookback_months=tuple(range(1, 17)),
        top_k=(1, 2),
        absolute_thresholds=(-0.05, 0.0),
        allocation_methods=("equal",),
    )
    assert search.candidate_count > MAX_PARAMETER_CANDIDATES
    selector = DualMomentumParameterOptimizationSpec(
        risky_symbols=("AAA", "BBB"),
        defensive_symbols=("BND",),
        search_space=search,
        inner_validation=InnerValidationSpec(fold_count=2),
    )

    with pytest.raises(ValueError, match="candidates, exceeding budget"):
        WalkForwardJobSpec(periods=(_period(),), selector=selector)


def test_service_downloads_outer_training_once_and_outer_evaluation_once() -> None:
    history = RecordingHistoryService()
    service = WalkForwardJobService(history_service=history)  # type: ignore[arg-type]
    spec = WalkForwardJobSpec(
        periods=(_period(),),
        selector=_selector(),
        execution=WalkForwardExecutionSpec(
            initial_amount=100_000.0,
            transition_cost_bps=5.0,
        ),
    )

    result = service.run(spec)
    payload = result.export_payload()

    assert result.contract_version == (
        DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_JOB_CONTRACT_VERSION
    )
    assert result.selector_policy == (
        WALK_FORWARD_DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_SELECTOR_POLICY
    )
    assert len(history.calls) == 2
    assert history.calls[0] == (
        ("AAA", "BBB", "BND"),
        date(2023, 1, 31),
        date(2025, 12, 31),
    )
    assert history.calls[1][1:] == (date(2026, 1, 1), date(2026, 1, 30))
    assert set(history.calls[1][0]).issubset({"AAA", "BBB", "BND"})
    assert len(result.period_audits) == 1
    audit = result.period_audits[0]
    assert isinstance(audit, TunedDualMomentumJobPeriodAudit)
    assert audit.tuning_result_hash
    assert audit.search_plan_hash
    assert audit.winner_parameter_hash
    decision = payload["decisions"][0]
    assert (
        decision["selector"]["parameters"]["tuningResultHash"]
        == audit.tuning_result_hash
    )
    assert (
        decision["selector"]["parameters"]["winnerParameterHash"]
        == audit.winner_parameter_hash
    )
    assert (
        decision["selectionEvidence"]["parameterOptimization"]["resultHash"]
        == audit.tuning_result_hash
    )
    assert payload["request"]["selector"]["parameterOptimization"]
    assert payload["periods"][0]["tuning_result_hash"] == audit.tuning_result_hash


def test_same_optimized_job_is_deterministic_with_same_audited_history() -> None:
    spec = WalkForwardJobSpec(
        periods=(_period(),),
        selector=_selector(),
        execution=WalkForwardExecutionSpec(
            initial_amount=100_000.0,
            transition_cost_bps=5.0,
        ),
    )
    first = WalkForwardJobService(
        history_service=RecordingHistoryService()  # type: ignore[arg-type]
    ).run(spec)
    second = WalkForwardJobService(
        history_service=RecordingHistoryService()  # type: ignore[arg-type]
    ).run(spec)

    assert first.job_hash == second.job_hash
    assert first.export_payload() == second.export_payload()
