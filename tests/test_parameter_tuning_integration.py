from __future__ import annotations

from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from apps.api.app.data.history_service import PartialTWDHistories, TWDAssetHistory
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.portfolio.models import SimulationConfig
from apps.api.app.research.dataset import build_research_dataset
from apps.api.app.research.dataset_views import slice_research_dataset
from apps.api.app.research.parameter_optimization import (
    InnerValidationSpec,
    ParameterSearchSpace,
    TuningBudget,
    build_parameter_search_plan,
)
from apps.api.app.research.parameter_refit import refit_parameter_tuning_winner
from apps.api.app.research.parameter_tuning import run_inner_parameter_tuning
from apps.api.app.research.walk_forward import ConfiguredResearchUniverse, WalkForwardPeriod


def _history(symbol: str, dates: pd.DatetimeIndex, daily: np.ndarray) -> TWDAssetHistory:
    levels = pd.Series(100.0 * np.cumprod(1.0 + daily), index=dates, dtype=float)
    fx = pd.Series(1.0, index=dates, dtype=float)
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency="TWD",
        valuation=TWDValuation(
            source_currency="TWD",
            native_adjusted_close=levels.rename("native_adjusted_close"),
            fx_to_twd=fx.rename("fx_to_twd"),
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


def _outer_period() -> WalkForwardPeriod:
    return WalkForwardPeriod(
        period_id="outer-2025-12",
        training_start=date(2023, 1, 31),
        training_end=date(2025, 12, 31),
        decision_date=date(2025, 12, 31),
        evaluation_start=date(2026, 1, 1),
        evaluation_end=date(2026, 1, 30),
    )


def _outer_training_dataset():
    dates = pd.bdate_range("2023-01-31", "2025-12-31")
    phase = np.arange(len(dates), dtype=float)
    daily_by_symbol = {
        "AAA": 0.0008 + 0.0100 * np.sin(phase / 8.0),
        "BBB": 0.0006 + 0.0090 * np.cos(phase / 10.0),
        "BND": 0.00015 + 0.0025 * np.sin(phase / 17.0),
    }
    histories = {
        symbol: _history(symbol, dates, daily)
        for symbol, daily in daily_by_symbol.items()
    }
    return build_research_dataset(
        PartialTWDHistories(
            requested=("AAA", "BBB", "BND"),
            histories=histories,
            failures={},
        ),
        start=date(2023, 1, 31),
        end=date(2025, 12, 31),
    )


def _search_plan():
    return build_parameter_search_plan(
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
        risky_symbol_count=2,
        outer_period_count=1,
        budget=TuningBudget(
            max_parameter_candidates=4,
            max_inner_folds=4,
            max_tuning_evaluations=12,
        ),
    )


def test_nested_tuning_is_deterministic_and_never_uses_outer_oos() -> None:
    outer_period = _outer_period()
    dataset = _outer_training_dataset()
    universe = ConfiguredResearchUniverse(("AAA", "BBB", "BND"))
    plan = _search_plan()
    config = SimulationConfig(initial_amount=100_000.0, transaction_cost_bps=5.0)

    first = run_inner_parameter_tuning(
        outer_period=outer_period,
        outer_training_dataset=dataset,
        configured_universe=universe,
        risky_symbols=("AAA", "BBB"),
        defensive_symbols=("BND",),
        search_plan=plan,
        simulation_config=config,
    )
    second = run_inner_parameter_tuning(
        outer_period=outer_period,
        outer_training_dataset=dataset,
        configured_universe=universe,
        risky_symbols=("AAA", "BBB"),
        defensive_symbols=("BND",),
        search_plan=plan,
        simulation_config=config,
    )

    assert first.result_hash == second.result_hash
    assert first.winner_parameter_hash == second.winner_parameter_hash
    assert len(first.candidates) == 2
    assert all(item.status == "eligible" for item in first.candidates)
    assert all(item.completed_fold_count == 3 for item in first.candidates)
    assert all(
        period.evaluation_end <= outer_period.training_end
        for period in first.inner_fold_schedule.periods
    )
    assert all(
        period.evaluation_end < outer_period.evaluation_start
        for period in first.inner_fold_schedule.periods
    )
    assert first.export_payload() == second.export_payload()


def test_winner_is_refit_on_full_outer_training_and_hash_bound_into_decision() -> None:
    outer_period = _outer_period()
    dataset = _outer_training_dataset()
    universe = ConfiguredResearchUniverse(("AAA", "BBB", "BND"))
    tuning = run_inner_parameter_tuning(
        outer_period=outer_period,
        outer_training_dataset=dataset,
        configured_universe=universe,
        risky_symbols=("AAA", "BBB"),
        defensive_symbols=("BND",),
        search_plan=_search_plan(),
        simulation_config=SimulationConfig(
            initial_amount=100_000.0,
            transaction_cost_bps=5.0,
        ),
    )

    decision = refit_parameter_tuning_winner(
        outer_period=outer_period,
        outer_training_dataset=dataset,
        configured_universe=universe,
        risky_symbols=("AAA", "BBB"),
        defensive_symbols=("BND",),
        tuning_result=tuning,
    )
    payload = decision.export_payload()
    selector_parameters = payload["selector"]["parameters"]

    assert decision.training_dataset_hash == dataset.dataset_hash
    assert decision.training_effective_end <= outer_period.decision_date
    assert sum(decision.weights) == pytest.approx(1.0)
    assert selector_parameters["tuningResultHash"] == tuning.result_hash
    assert selector_parameters["winnerParameterHash"] == tuning.winner_parameter_hash
    assert (
        payload["selectionEvidence"]["parameterOptimization"]["resultHash"]
        == tuning.result_hash
    )
    assert payload["selectionEvidence"]["parameterOptimizationRefit"] == {
        "policy": "winner-on-full-outer-training-v1",
        "outerTrainingDatasetHash": dataset.dataset_hash,
        "winnerParameterHash": tuning.winner_parameter_hash,
    }


def test_refit_rejects_a_different_outer_training_dataset_identity() -> None:
    outer_period = _outer_period()
    dataset = _outer_training_dataset()
    universe = ConfiguredResearchUniverse(("AAA", "BBB", "BND"))
    tuning = run_inner_parameter_tuning(
        outer_period=outer_period,
        outer_training_dataset=dataset,
        configured_universe=universe,
        risky_symbols=("AAA", "BBB"),
        defensive_symbols=("BND",),
        search_plan=_search_plan(),
        simulation_config=SimulationConfig(initial_amount=100_000.0),
    )
    different = slice_research_dataset(
        dataset,
        start=date(2023, 2, 1),
        end=date(2025, 12, 31),
    )

    with pytest.raises(ValueError, match="does not belong"):
        refit_parameter_tuning_winner(
            outer_period=outer_period,
            outer_training_dataset=different,
            configured_universe=universe,
            risky_symbols=("AAA", "BBB"),
            defensive_symbols=("BND",),
            tuning_result=tuning,
        )


def test_tampered_winner_identity_fails_closed_before_refit() -> None:
    outer_period = _outer_period()
    dataset = _outer_training_dataset()
    universe = ConfiguredResearchUniverse(("AAA", "BBB", "BND"))
    tuning = run_inner_parameter_tuning(
        outer_period=outer_period,
        outer_training_dataset=dataset,
        configured_universe=universe,
        risky_symbols=("AAA", "BBB"),
        defensive_symbols=("BND",),
        search_plan=_search_plan(),
        simulation_config=SimulationConfig(initial_amount=100_000.0),
    )
    tampered = replace(tuning, winner_parameter_hash="0" * 64)

    with pytest.raises(ValueError, match="tuning result identity mismatch"):
        refit_parameter_tuning_winner(
            outer_period=outer_period,
            outer_training_dataset=dataset,
            configured_universe=universe,
            risky_symbols=("AAA", "BBB"),
            defensive_symbols=("BND",),
            tuning_result=tampered,
        )
