from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from apps.api.app.data.history_service import HistoryFailure, TWDAssetHistory
from apps.api.app.data.return_components import TWDReturnComponents
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.portfolio.ledger import simulate_portfolio_ledger
from apps.api.app.portfolio.models import (
    AssetWeight,
    CashflowConfig,
    CashflowFrequency,
    CashflowTiming,
    CashflowType,
    LeverageConfig,
    LeverageType,
    PortfolioSpec,
    RebalanceConfig,
    RebalanceFrequency,
    SimulationConfig,
)
from apps.api.app.portfolio.service import PortfolioLedgerService


def _history(
    symbol: str,
    dates: list[str],
    total: list[float],
    *,
    price: list[float] | None = None,
    distribution: list[float] | None = None,
) -> TWDAssetHistory:
    index = pd.to_datetime(dates)
    total_series = pd.Series(total, index=index, dtype=float, name="total_return")
    price_values = price if price is not None else total
    price_series = pd.Series(price_values, index=index, dtype=float, name="price_return")
    distribution_values = distribution or [0.0] * len(index)
    distribution_series = pd.Series(
        distribution_values,
        index=index,
        dtype=float,
        name="distribution_return",
    )
    np.testing.assert_allclose(total_series, price_series + distribution_series)
    total_index = (1.0 + total_series).cumprod()
    price_index = (1.0 + price_series).cumprod()
    adjusted = (100.0 * total_index).rename("adjusted_close_twd")
    fx = pd.Series(1.0, index=index, name="fx_to_twd")
    valuation = TWDValuation(
        source_currency="TWD",
        native_adjusted_close=adjusted.rename("native_adjusted_close"),
        fx_to_twd=fx,
        adjusted_close_twd=adjusted,
        daily_returns=total_series.rename("daily_return"),
    )
    components = TWDReturnComponents(
        source_currency="TWD",
        fx_to_twd=fx,
        total_returns=total_series,
        price_returns=price_series,
        distribution_returns=distribution_series,
        total_return_index=total_index,
        price_return_index=price_index,
        audit={"status": "synthetic", "contract_version": "test"},
    )
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency="TWD",
        valuation=valuation,
        corporate_action_audit={"status": "verified_standard_actions"},
        return_components=components,
    )


def test_portfolio_validation_rejects_duplicate_or_incomplete_weights() -> None:
    with pytest.raises(ValueError, match="unique"):
        PortfolioSpec(
            name="Duplicate",
            assets=(AssetWeight("AAA", 0.5), AssetWeight("AAA", 0.5)),
        )
    with pytest.raises(ValueError, match="sum"):
        PortfolioSpec.from_weights("Incomplete", {"AAA": 0.8})


def test_distribution_can_be_retained_as_cash_without_double_counting() -> None:
    history = _history(
        "AAA",
        ["2024-01-02", "2024-01-03", "2024-01-04"],
        [0.0, 0.10, 0.10],
        price=[0.0, 0.05, 0.10],
        distribution=[0.0, 0.05, 0.0],
    )
    portfolio = PortfolioSpec.from_weights("AAA", {"AAA": 1.0})
    reinvested = simulate_portfolio_ledger(
        portfolio,
        {"AAA": history},
        SimulationConfig(initial_amount=100.0, reinvest_distributions=True),
    )
    retained = simulate_portfolio_ledger(
        portfolio,
        {"AAA": history},
        SimulationConfig(initial_amount=100.0, reinvest_distributions=False),
    )

    assert reinvested.equity.iloc[1] == pytest.approx(retained.equity.iloc[1])
    assert retained.cash.iloc[1] == pytest.approx(5.0)
    assert retained.income.iloc[1] == pytest.approx(5.0)
    assert retained.equity.iloc[-1] == pytest.approx(120.5)
    assert reinvested.equity.iloc[-1] == pytest.approx(121.0)
    assert any(event.type == "distribution_cash" for event in retained.events)


def test_end_of_month_contribution_is_excluded_from_time_weighted_return() -> None:
    history = _history(
        "AAA",
        ["2024-01-30", "2024-01-31", "2024-02-01"],
        [0.0, 0.0, 0.0],
    )
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("Flow", {"AAA": 1.0}),
        {"AAA": history},
        SimulationConfig(
            initial_amount=1_000.0,
            cashflow=CashflowConfig(
                type=CashflowType.FIXED,
                amount=100.0,
                frequency=CashflowFrequency.MONTHLY,
                timing=CashflowTiming.END,
            ),
        ),
    )

    assert ledger.external_flows.loc[pd.Timestamp("2024-01-31")] == pytest.approx(100.0)
    assert ledger.equity.iloc[-1] == pytest.approx(1_100.0)
    np.testing.assert_allclose(ledger.return_index, 1.0)


def test_monthly_rebalance_charges_cost_and_records_trades() -> None:
    dates = ["2024-01-30", "2024-01-31", "2024-02-01"]
    histories = {
        "AAA": _history("AAA", dates, [0.0, 0.20, 0.0]),
        "BBB": _history("BBB", dates, [0.0, 0.0, 0.0]),
    }
    portfolio = PortfolioSpec.from_weights("Balanced", {"AAA": 0.5, "BBB": 0.5})
    no_cost = simulate_portfolio_ledger(
        portfolio,
        histories,
        SimulationConfig(
            initial_amount=1_000.0,
            rebalancing=RebalanceConfig(frequency=RebalanceFrequency.MONTHLY),
        ),
    )
    with_cost = simulate_portfolio_ledger(
        portfolio,
        histories,
        SimulationConfig(
            initial_amount=1_000.0,
            transaction_cost_bps=100.0,
            rebalancing=RebalanceConfig(frequency=RebalanceFrequency.MONTHLY),
        ),
    )

    assert with_cost.rebalance_count == 1
    assert with_cost.transaction_costs > 0.0
    assert with_cost.equity.iloc[-1] < no_cost.equity.iloc[-1]
    event = next(event for event in with_cost.events if event.type == "rebalance")
    assert event.details["traded_notional"] > 0.0
    assert event.details["trigger"] == "periodic"


def test_weight_drift_threshold_independently_triggers_rebalance() -> None:
    dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
    histories = {
        "AAA": _history("AAA", dates, [0.0, 0.50, 0.0]),
        "BBB": _history("BBB", dates, [0.0, 0.0, 0.0]),
    }
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("Threshold", {"AAA": 0.5, "BBB": 0.5}),
        histories,
        SimulationConfig(
            initial_amount=1_000.0,
            rebalancing=RebalanceConfig(threshold_percent=5.0),
        ),
    )

    assert ledger.rebalance_count >= 1
    assert any(
        event.type == "rebalance" and event.details["trigger"] == "threshold"
        for event in ledger.events
    )


def test_fixed_ratio_margin_breach_is_a_liquidation_event() -> None:
    history = _history(
        "AAA",
        ["2024-01-02", "2024-01-03", "2024-01-04"],
        [0.0, -0.40, 0.10],
    )
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("Leveraged", {"AAA": 1.0}),
        {"AAA": history},
        SimulationConfig(
            initial_amount=100.0,
            leverage=LeverageConfig(
                type=LeverageType.FIXED_RATIO,
                ratio=2.0,
                maintenance_margin_percent=25.0,
            ),
        ),
    )

    assert ledger.liquidated is True
    assert ledger.equity.iloc[1] == pytest.approx(20.0)
    assert ledger.equity.iloc[-1] == pytest.approx(20.0)
    assert ledger.debt.iloc[-1] == 0.0
    assert any(event.type == "margin_liquidation" for event in ledger.events)


def test_fixed_debt_interest_reduces_equity_without_changing_principal() -> None:
    history = _history(
        "AAA",
        ["2024-01-02", "2024-01-03", "2024-01-04"],
        [0.0, 0.0, 0.0],
    )
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("Debt", {"AAA": 1.0}),
        {"AAA": history},
        SimulationConfig(
            initial_amount=100.0,
            leverage=LeverageConfig(
                type=LeverageType.FIXED_DEBT,
                debt_amount=50.0,
                annual_interest_rate_percent=36.52425,
                maintenance_margin_percent=0.0,
            ),
        ),
    )

    assert ledger.borrowing_costs == pytest.approx(0.1, rel=1e-6)
    assert ledger.debt.iloc[-1] == pytest.approx(50.0)
    assert ledger.equity.iloc[-1] == pytest.approx(99.9, rel=1e-6)


def test_percentage_withdrawal_is_capped_at_available_equity() -> None:
    history = _history(
        "AAA",
        ["2024-01-30", "2024-01-31", "2024-02-01"],
        [0.0, 0.0, 0.0],
    )
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("Withdrawal", {"AAA": 1.0}),
        {"AAA": history},
        SimulationConfig(
            initial_amount=100.0,
            cashflow=CashflowConfig(
                type=CashflowType.PERCENT,
                amount=-200.0,
                frequency=CashflowFrequency.MONTHLY,
                timing=CashflowTiming.END,
            ),
        ),
    )

    assert ledger.external_flows.loc[pd.Timestamp("2024-01-31")] == pytest.approx(-100.0)
    assert ledger.equity.iloc[-1] == pytest.approx(0.0)
    assert any("capped" in warning for warning in ledger.warnings)


def test_service_preserves_success_when_sibling_and_benchmark_fail() -> None:
    dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
    histories = {"GOOD": _history("GOOD", dates, [0.0, 0.01, 0.01])}
    failures = {
        "BAD": HistoryFailure(
            symbol="BAD",
            stage="download",
            detail="upstream unavailable",
            retryable=True,
        )
    }
    batch = PortfolioLedgerService().run(
        (
            PortfolioSpec.from_weights("Good", {"GOOD": 1.0}),
            PortfolioSpec.from_weights("Bad", {"BAD": 1.0}),
        ),
        histories,
        SimulationConfig(initial_amount=100.0),
        benchmark="MISSING",
        history_failures=failures,
    )

    assert [result.name for result in batch.results] == ["Good"]
    assert [failure.name for failure in batch.failures] == ["Bad"]
    assert batch.failures[0].retryable is True
    assert batch.results[0].metrics.metrics["beta"] is None
    assert any("benchmark MISSING unavailable" in warning for warning in batch.warnings)
