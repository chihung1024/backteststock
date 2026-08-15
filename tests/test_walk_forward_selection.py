from __future__ import annotations

import inspect
from datetime import date

import numpy as np
import pandas as pd
import pytest

from apps.api.app.data.history_service import (
    HistoryFailure,
    PartialTWDHistories,
    TWDAssetHistory,
)
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.research.dataset import build_research_dataset
from apps.api.app.research.selection import (
    ConfiguredEqualWeightSelectionEngine,
    SelectionContext,
    SelectionResult,
    build_selection_context,
    run_selection,
    validate_evaluation_dataset,
)
from apps.api.app.research.walk_forward import ResolvedPITUniverse, WalkForwardPeriod


def _period() -> WalkForwardPeriod:
    return WalkForwardPeriod(
        period_id="2024-02-A",
        training_start=date(2024, 1, 2),
        training_end=date(2024, 1, 31),
        decision_date=date(2024, 1, 31),
        evaluation_start=date(2024, 2, 1),
        evaluation_end=date(2024, 2, 15),
    )


def _universe() -> ResolvedPITUniverse:
    return ResolvedPITUniverse(
        universe_id="synthetic",
        requested_as_of=date(2024, 1, 31),
        source_as_of=date(2024, 1, 30),
        evidence_available_as_of=date(2024, 1, 30),
        fetched_at="2024-01-30T12:00:00Z",
        version="synthetic-2024-01-30",
        checksum="abc123",
        members=("AAA", "BBB", "CCC"),
        membership_policy="latest-causal-v1",
        membership_authoritative=True,
        source_label="synthetic-official",
        source_url="https://example.test/universe",
        source_is_proxy=False,
    )


def _history(symbol: str, dates: pd.DatetimeIndex, values: list[float]) -> TWDAssetHistory:
    native = pd.Series(values, index=dates, dtype=float, name="native_adjusted_close")
    fx = pd.Series(1.0, index=dates, dtype=float, name="fx_to_twd")
    twd = native.rename("adjusted_close_twd")
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency="TWD",
        valuation=TWDValuation(
            source_currency="TWD",
            native_adjusted_close=native,
            fx_to_twd=fx,
            adjusted_close_twd=twd,
            daily_returns=twd.pct_change(fill_method=None)
            .fillna(0.0)
            .rename("daily_return"),
        ),
        corporate_action_audit={
            "status": "verified_standard_actions",
            "warning_dates": [],
        },
        fx_audit={"method": "identity", "tickers": []},
        raw_quote_currency="TWD",
        native_price_scale=1.0,
    )


def _dataset(
    *,
    start: date,
    end: date,
    paths: dict[str, tuple[pd.DatetimeIndex, list[float]]],
    requested: tuple[str, ...] = ("AAA", "BBB", "CCC"),
    failures: dict[str, HistoryFailure] | None = None,
):
    histories = {
        symbol: _history(symbol, dates, values)
        for symbol, (dates, values) in paths.items()
    }
    return build_research_dataset(
        PartialTWDHistories(
            requested=requested,
            histories=histories,
            failures=failures or {},
        ),
        start=start,
        end=end,
    )


def _training_dataset(*, include_failure: bool = False):
    dates = pd.bdate_range("2024-01-02", "2024-01-31")
    paths = {
        "AAA": (dates, list(np.linspace(100.0, 135.0, len(dates)))),
        "BBB": (dates, list(np.linspace(100.0, 120.0, len(dates)))),
    }
    failures = {}
    if include_failure:
        failures["CCC"] = HistoryFailure(
            symbol="CCC",
            stage="download",
            detail="synthetic training history unavailable",
            retryable=True,
        )
    else:
        paths["CCC"] = (dates, list(np.linspace(100.0, 105.0, len(dates))))
    return _dataset(
        start=date(2024, 1, 2),
        end=date(2024, 1, 31),
        paths=paths,
        failures=failures,
    )


def _evaluation_dataset(*, extreme: bool):
    dates = pd.bdate_range("2024-02-01", "2024-02-15")
    if extreme:
        aaa = list(np.geomspace(100.0, 5100.0, len(dates)))
        bbb = list(np.geomspace(100.0, 1.0, len(dates)))
        ccc = list(np.linspace(100.0, 101.0, len(dates)))
    else:
        aaa = list(np.linspace(100.0, 101.0, len(dates)))
        bbb = list(np.linspace(100.0, 102.0, len(dates)))
        ccc = list(np.linspace(100.0, 103.0, len(dates)))
    return _dataset(
        start=date(2024, 2, 1),
        end=date(2024, 2, 15),
        paths={
            "AAA": (dates, aaa),
            "BBB": (dates, bbb),
            "CCC": (dates, ccc),
        },
    )


class TrainingReturnEngine:
    contract_version = "test-training-return-v1"
    rule = "top-two-training-total-return"

    @property
    def parameters(self):
        return {"holdingCount": 2, "weighting": "equal"}

    def select(self, context: SelectionContext) -> SelectionResult:
        levels = context.training_dataset.daily_levels_twd
        ranked = sorted(
            context.eligible_candidates,
            key=lambda symbol: (
                -(float(levels[symbol].iloc[-1]) / float(levels[symbol].iloc[0]) - 1.0),
                symbol,
            ),
        )
        selected = tuple(ranked[:2])
        return SelectionResult(
            selected_constituents=selected,
            weights=(0.5, 0.5),
        )


def test_selection_context_has_no_oos_dataset_and_requires_exact_training_window():
    assert "evaluation_dataset" not in inspect.signature(run_selection).parameters
    assert "evaluation_dataset" not in SelectionContext.__dataclass_fields__

    context = build_selection_context(
        period=_period(),
        pit_universe=_universe(),
        training_dataset=_training_dataset(),
    )
    assert context.eligible_candidates == ("AAA", "BBB", "CCC")
    assert context.unavailable_candidates == ()

    dates = pd.bdate_range("2024-01-02", "2024-01-30")
    short = _dataset(
        start=date(2024, 1, 2),
        end=date(2024, 1, 30),
        paths={
            "AAA": (dates, list(np.linspace(100.0, 110.0, len(dates)))),
            "BBB": (dates, list(np.linspace(100.0, 109.0, len(dates)))),
            "CCC": (dates, list(np.linspace(100.0, 108.0, len(dates)))),
        },
    )
    with pytest.raises(ValueError, match="requested_end"):
        build_selection_context(
            period=_period(),
            pit_universe=_universe(),
            training_dataset=short,
        )


def test_partial_history_is_explicit_and_failed_candidate_cannot_be_selected():
    context = build_selection_context(
        period=_period(),
        pit_universe=_universe(),
        training_dataset=_training_dataset(include_failure=True),
    )
    assert context.eligible_candidates == ("AAA", "BBB")
    assert [item.symbol for item in context.unavailable_candidates] == ["CCC"]
    assert context.unavailable_candidates[0].stage == "download"
    assert context.unavailable_candidates[0].retryable is True

    engine = ConfiguredEqualWeightSelectionEngine(("AAA", "CCC"))
    with pytest.raises(ValueError, match="not eligible"):
        run_selection(
            period=_period(),
            pit_universe=_universe(),
            training_dataset=_training_dataset(include_failure=True),
            engine=engine,
        )


def test_future_oos_mutation_cannot_change_selection_or_decision_hash():
    training = _training_dataset()
    engine = TrainingReturnEngine()

    first = run_selection(
        period=_period(),
        pit_universe=_universe(),
        training_dataset=training,
        engine=engine,
    )
    second = run_selection(
        period=_period(),
        pit_universe=_universe(),
        training_dataset=training,
        engine=engine,
    )

    ordinary_oos = _evaluation_dataset(extreme=False)
    extreme_oos = _evaluation_dataset(extreme=True)
    validate_evaluation_dataset(decision=first, evaluation_dataset=ordinary_oos)
    validate_evaluation_dataset(decision=second, evaluation_dataset=extreme_oos)

    assert first.selected_constituents == ("AAA", "BBB")
    assert second.selected_constituents == first.selected_constituents
    assert second.weights == first.weights
    assert second.decision_hash == first.decision_hash
    assert ordinary_oos.dataset_hash != extreme_oos.dataset_hash


def test_selector_mutating_training_dataset_fails_closed():
    class MutatingEngine:
        contract_version = "mutating-test-v1"
        rule = "invalid-mutation"

        @property
        def parameters(self):
            return {}

        def select(self, context):
            context.training_dataset.daily_levels_twd.iloc[-1, 0] *= 2.0
            return SelectionResult(("AAA",), (1.0,))

    with pytest.raises(ValueError, match="content changed after hash creation"):
        run_selection(
            period=_period(),
            pit_universe=_universe(),
            training_dataset=_training_dataset(),
            engine=MutatingEngine(),
        )


def test_selector_identity_is_snapshotted_before_engine_execution():
    class ParameterMutatingEngine:
        contract_version = "parameter-mutation-test-v1"
        rule = "configured"

        def __init__(self):
            self.values = {"nested": {"lookback": 20}}

        @property
        def parameters(self):
            return self.values

        def select(self, context):
            self.values["nested"]["lookback"] = 1
            return SelectionResult(("AAA",), (1.0,))

    engine = ParameterMutatingEngine()
    decision = run_selection(
        period=_period(),
        pit_universe=_universe(),
        training_dataset=_training_dataset(),
        engine=engine,
    )
    assert engine.values["nested"]["lookback"] == 1
    assert decision.export_payload()["selector"]["parameters"]["nested"]["lookback"] == 20


def test_invalid_selector_output_fails_closed_at_decision_boundary():
    class BadSymbolEngine:
        contract_version = "bad-symbol-v1"
        rule = "bad-symbol"

        @property
        def parameters(self):
            return {}

        def select(self, context):
            return SelectionResult(("aaa",), (1.0,))

    with pytest.raises(ValueError, match="canonical symbols"):
        run_selection(
            period=_period(),
            pit_universe=_universe(),
            training_dataset=_training_dataset(),
            engine=BadSymbolEngine(),
        )

    class BadWeightEngine(BadSymbolEngine):
        contract_version = "bad-weight-v1"
        rule = "bad-weight"

        def select(self, context):
            return SelectionResult(("AAA", "BBB"), (0.8, 0.1))

    with pytest.raises(ValueError, match="summing to one"):
        run_selection(
            period=_period(),
            pit_universe=_universe(),
            training_dataset=_training_dataset(),
            engine=BadWeightEngine(),
        )


def test_evaluation_dataset_is_post_decision_and_requires_selected_history():
    decision = run_selection(
        period=_period(),
        pit_universe=_universe(),
        training_dataset=_training_dataset(),
        engine=TrainingReturnEngine(),
    )
    assert validate_evaluation_dataset(
        decision=decision,
        evaluation_dataset=_evaluation_dataset(extreme=False),
    ).requested_start == date(2024, 2, 1)

    wrong_dates = pd.bdate_range("2024-02-02", "2024-02-15")
    wrong_window = _dataset(
        start=date(2024, 2, 2),
        end=date(2024, 2, 15),
        requested=("AAA", "BBB"),
        paths={
            "AAA": (wrong_dates, list(np.linspace(100.0, 101.0, len(wrong_dates)))),
            "BBB": (wrong_dates, list(np.linspace(100.0, 102.0, len(wrong_dates)))),
        },
    )
    with pytest.raises(ValueError, match="requested_start"):
        validate_evaluation_dataset(decision=decision, evaluation_dataset=wrong_window)

    dates = pd.bdate_range("2024-02-01", "2024-02-15")
    missing_selected = _dataset(
        start=date(2024, 2, 1),
        end=date(2024, 2, 15),
        requested=("AAA",),
        paths={
            "AAA": (dates, list(np.linspace(100.0, 101.0, len(dates)))),
        },
    )
    with pytest.raises(ValueError, match="request every selected constituent"):
        validate_evaluation_dataset(
            decision=decision,
            evaluation_dataset=missing_selected,
        )
