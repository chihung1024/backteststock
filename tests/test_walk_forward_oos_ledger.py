from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from apps.api.app.data.history_service import PartialTWDHistories, TWDAssetHistory
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.portfolio.models import (
    CashflowConfig,
    CashflowFrequency,
    CashflowType,
    LeverageConfig,
    LeverageType,
    SimulationConfig,
)
from apps.api.app.research.dataset import build_research_dataset
from apps.api.app.research.oos_ledger import (
    WALK_FORWARD_OOS_EXECUTION_POLICY,
    WALK_FORWARD_OOS_GAP_POLICY,
    WALK_FORWARD_OOS_LEDGER_CONTRACT_VERSION,
    WalkForwardEvaluation,
    run_continuous_oos_ledger,
)
from apps.api.app.research.walk_forward import (
    ResolvedPITUniverse,
    WalkForwardPeriod,
    create_decision_snapshot,
)


def _history(symbol: str, dates: list[str], values: list[float]) -> TWDAssetHistory:
    index = pd.to_datetime(dates)
    native = pd.Series(values, index=index, dtype=float, name="native_adjusted_close")
    fx = pd.Series(1.0, index=index, dtype=float, name="fx_to_twd")
    twd = native.rename("adjusted_close_twd")
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency="TWD",
        valuation=TWDValuation(
            source_currency="TWD",
            native_adjusted_close=native,
            fx_to_twd=fx,
            adjusted_close_twd=twd,
            daily_returns=(
                twd.pct_change(fill_method=None).fillna(0.0).rename("daily_return")
            ),
        ),
        corporate_action_audit={
            "status": "verified_standard_actions",
            "warning_dates": [],
        },
        fx_audit={"method": "identity", "tickers": []},
        raw_quote_currency="TWD",
        native_price_scale=1.0,
    )


def _evaluation_dataset(
    *,
    start: date,
    end: date,
    dates: list[str],
    aaa: list[float],
    bbb: list[float],
):
    return build_research_dataset(
        PartialTWDHistories(
            requested=("AAA", "BBB"),
            histories={
                "AAA": _history("AAA", dates, aaa),
                "BBB": _history("BBB", dates, bbb),
            },
            failures={},
        ),
        start=start,
        end=end,
    )


def _period_one() -> WalkForwardPeriod:
    return WalkForwardPeriod(
        period_id="2024-02-01",
        training_start=date(2024, 1, 2),
        training_end=date(2024, 1, 31),
        decision_date=date(2024, 1, 31),
        evaluation_start=date(2024, 2, 1),
        evaluation_end=date(2024, 2, 2),
    )


def _period_two() -> WalkForwardPeriod:
    return WalkForwardPeriod(
        period_id="2024-02-05",
        training_start=date(2024, 1, 2),
        training_end=date(2024, 2, 2),
        decision_date=date(2024, 2, 2),
        evaluation_start=date(2024, 2, 5),
        evaluation_end=date(2024, 2, 6),
    )


def _universe(period: WalkForwardPeriod) -> ResolvedPITUniverse:
    evidence_date = (
        date(2024, 1, 30)
        if period.decision_date == date(2024, 1, 31)
        else date(2024, 2, 1)
    )
    return ResolvedPITUniverse(
        universe_id="synthetic",
        requested_as_of=period.decision_date,
        source_as_of=evidence_date,
        evidence_available_as_of=evidence_date,
        fetched_at=f"{evidence_date.isoformat()}T12:00:00Z",
        version=f"synthetic-{evidence_date.isoformat()}",
        checksum=f"checksum-{period.period_id}",
        members=("AAA", "BBB"),
        membership_policy="latest-causal-v1",
        membership_authoritative=True,
        source_label="synthetic-official",
        source_url="https://example.test/universe",
        source_is_proxy=False,
    )


def _decision(
    period: WalkForwardPeriod,
    *,
    selected: tuple[str, ...],
    weights: tuple[float, ...],
):
    return create_decision_snapshot(
        period=period,
        pit_universe=_universe(period),
        training_dataset_hash=f"training-{period.period_id}",
        training_effective_start=period.training_start,
        training_effective_end=period.training_end,
        selector_contract_version="synthetic-selection-v1",
        selector_rule="configured-test-selection",
        selector_parameters={"fixture": period.period_id},
        eligible_candidates=("AAA", "BBB"),
        selected_constituents=selected,
        weights=weights,
    )


def _two_period_evaluations(*, second_selected: str = "BBB"):
    first_period = _period_one()
    second_period = _period_two()
    first = WalkForwardEvaluation(
        decision=_decision(first_period, selected=("AAA",), weights=(1.0,)),
        evaluation_dataset=_evaluation_dataset(
            start=first_period.evaluation_start,
            end=first_period.evaluation_end,
            dates=["2024-02-01", "2024-02-02"],
            aaa=[100.0, 110.0],
            bbb=[100.0, 100.0],
        ),
    )
    second = WalkForwardEvaluation(
        decision=_decision(
            second_period,
            selected=(second_selected,),
            weights=(1.0,),
        ),
        evaluation_dataset=_evaluation_dataset(
            start=second_period.evaluation_start,
            end=second_period.evaluation_end,
            dates=["2024-02-05", "2024-02-06"],
            aaa=[110.0, 121.0],
            bbb=[100.0, 120.0],
        ),
    )
    return first, second


def test_continuous_oos_ledger_carries_equity_and_charges_full_transition_turnover():
    result = run_continuous_oos_ledger(
        _two_period_evaluations(),
        SimulationConfig(initial_amount=100.0, transaction_cost_bps=100.0),
    )
    ledger = result.ledger

    # Period 1: 100 -> 110.  At the next Decision boundary a disjoint AAA -> BBB
    # transition sells 110 and buys 110, so traded notional is 220 and 100 bps
    # costs 2.2.  Period 2 then compounds 107.8 by +20% to 129.36.
    assert ledger.equity.loc[pd.Timestamp("2024-02-02")] == pytest.approx(110.0)
    assert ledger.equity.loc[pd.Timestamp("2024-02-05")] == pytest.approx(107.8)
    assert ledger.equity.iloc[-1] == pytest.approx(129.36)
    assert ledger.transaction_costs == pytest.approx(2.2)
    assert ledger.daily_returns.loc[pd.Timestamp("2024-02-05")] == pytest.approx(-0.02)
    assert ledger.return_index.iloc[-1] == pytest.approx(1.2936)
    assert result.metrics.metrics["final_balance"] == pytest.approx(129.36)
    assert result.metrics.metrics["total_return"] == pytest.approx(0.2936)

    transition = next(event for event in ledger.events if event.type == "walk_forward_transition")
    assert transition.date == "2024-02-05"
    assert transition.details["traded_notional"] == pytest.approx(220.0)
    assert transition.details["transaction_cost"] == pytest.approx(2.2)
    assert transition.details["from_decision_hash"] == result.periods[0].decision_hash
    assert transition.details["to_decision_hash"] == result.periods[1].decision_hash
    assert transition.details["execution_policy"] == WALK_FORWARD_OOS_EXECUTION_POLICY
    assert transition.details["gap_policy"] == WALK_FORWARD_OOS_GAP_POLICY

    assert ledger.allocation_history.loc[pd.Timestamp("2024-02-02"), "AAA"] == pytest.approx(1.0)
    assert ledger.allocation_history.loc[pd.Timestamp("2024-02-05"), "BBB"] == pytest.approx(1.0)
    assert ledger.rebalance_count == 1
    assert result.contract_version == WALK_FORWARD_OOS_LEDGER_CONTRACT_VERSION


def test_same_target_carries_state_without_fabricating_gap_return_or_turnover():
    result = run_continuous_oos_ledger(
        _two_period_evaluations(second_selected="AAA"),
        SimulationConfig(initial_amount=100.0, transaction_cost_bps=100.0),
    )

    # No OOS observation is invented for the weekend gap.  The audited 110 state
    # is carried flat into Monday's target application; unchanged 100% AAA has
    # zero traded notional/cost, then Tuesday's observed +10% is applied.
    assert list(result.ledger.equity.index.strftime("%Y-%m-%d")) == [
        "2024-02-01",
        "2024-02-02",
        "2024-02-05",
        "2024-02-06",
    ]
    assert result.ledger.equity.loc[pd.Timestamp("2024-02-05")] == pytest.approx(110.0)
    assert result.ledger.equity.iloc[-1] == pytest.approx(121.0)
    assert result.ledger.transaction_costs == pytest.approx(0.0)
    assert result.periods[1].transition_traded_notional == pytest.approx(0.0)
    assert result.periods[1].transition_cost == pytest.approx(0.0)


def test_period_local_nav_is_not_reset_inside_global_return_index():
    result = run_continuous_oos_ledger(
        _two_period_evaluations(),
        SimulationConfig(initial_amount=100.0, transaction_cost_bps=0.0),
    )

    np.testing.assert_allclose(
        result.ledger.return_index.to_numpy(),
        np.asarray([1.0, 1.1, 1.1, 1.32]),
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        result.ledger.equity.to_numpy(),
        100.0 * result.ledger.return_index.to_numpy(),
        rtol=1e-12,
        atol=1e-12,
    )


def test_oos_period_audit_binds_decision_and_evaluation_dataset_identity():
    evaluations = _two_period_evaluations()
    result = run_continuous_oos_ledger(evaluations, SimulationConfig(initial_amount=100.0))

    assert [item.period_id for item in result.periods] == ["2024-02-01", "2024-02-05"]
    assert result.periods[0].decision_hash == evaluations[0].decision.decision_hash
    assert (
        result.periods[0].evaluation_dataset_hash
        == evaluations[0].evaluation_dataset.dataset_hash
    )
    assert result.periods[0].effective_start == "2024-02-01"
    assert result.periods[1].effective_end == "2024-02-06"
    assert result.periods[1].selected_constituents == ("BBB",)
    assert result.periods[1].weights == (1.0,)


def test_oos_v1_fails_closed_for_state_not_proven_by_research_dataset():
    evaluations = _two_period_evaluations()

    with pytest.raises(ValueError, match="reinvest_distributions=True"):
        run_continuous_oos_ledger(
            evaluations,
            SimulationConfig(initial_amount=100.0, reinvest_distributions=False),
        )

    with pytest.raises(ValueError, match="external cashflows"):
        run_continuous_oos_ledger(
            evaluations,
            SimulationConfig(
                initial_amount=100.0,
                cashflow=CashflowConfig(
                    type=CashflowType.FIXED,
                    amount=10.0,
                    frequency=CashflowFrequency.MONTHLY,
                ),
            ),
        )

    with pytest.raises(ValueError, match="leverage/debt"):
        run_continuous_oos_ledger(
            evaluations,
            SimulationConfig(
                initial_amount=100.0,
                leverage=LeverageConfig(type=LeverageType.FIXED_RATIO, ratio=2.0),
            ),
        )


def test_oos_requires_at_least_two_effective_valuation_dates_per_segment():
    period = WalkForwardPeriod(
        period_id="single-date",
        training_start=date(2024, 1, 2),
        training_end=date(2024, 1, 31),
        decision_date=date(2024, 1, 31),
        evaluation_start=date(2024, 2, 1),
        evaluation_end=date(2024, 2, 1),
    )
    decision = _decision(period, selected=("AAA",), weights=(1.0,))
    dataset = _evaluation_dataset(
        start=period.evaluation_start,
        end=period.evaluation_end,
        dates=["2024-02-01"],
        aaa=[100.0],
        bbb=[100.0],
    )

    with pytest.raises(ValueError, match="at least two effective valuation dates"):
        run_continuous_oos_ledger(
            (WalkForwardEvaluation(decision, dataset),),
            SimulationConfig(initial_amount=100.0),
        )
