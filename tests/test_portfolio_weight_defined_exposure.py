from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from apps.api.app.data.history_service import TWDAssetHistory
from apps.api.app.data.return_components import TWDReturnComponents
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.portfolio.ledger import simulate_portfolio_ledger
from apps.api.app.portfolio.models import (
    AssetWeight,
    LeverageConfig,
    LeverageType,
    PortfolioSpec,
    RebalanceConfig,
    SimulationConfig,
)

def _history(
    symbol: str,
    dates: list[str | date],
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



def test_portfolio_validation_accepts_cash_and_leverage_targets_but_rejects_excess() -> None:
    with pytest.raises(ValueError, match="unique"):
        PortfolioSpec(
            name="Duplicate",
            assets=(AssetWeight("AAA", 0.5), AssetWeight("AAA", 0.5)),
        )

    cash_target = PortfolioSpec.from_weights("Cash", {"AAA": 0.8})
    leveraged_target = PortfolioSpec.from_weights(
        "Leveraged",
        {"AAA": 0.75, "BBB": 0.75},
    )
    assert cash_target.target_gross_exposure == pytest.approx(0.8)
    assert cash_target.target_cash_allocation == pytest.approx(0.2)
    assert leveraged_target.target_gross_exposure == pytest.approx(1.5)
    assert leveraged_target.target_cash_allocation == 0.0
    assert leveraged_target.target_asset_mix == pytest.approx(
        {"AAA": 0.5, "BBB": 0.5}
    )

    with pytest.raises(ValueError, match="gross exposure"):
        PortfolioSpec.from_weights("Too much", {"AAA": 5.0, "BBB": 0.01})


def test_weight_below_100_percent_resets_total_exposure_each_close() -> None:
    history = _history(
        "AAA",
        ["2024-01-02", "2024-01-03", "2024-01-04"],
        [0.0, 0.10, 0.0],
    )
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("80/20", {"AAA": 0.8}),
        {"AAA": history},
        SimulationConfig(initial_amount=100.0),
    )

    assert ledger.target_gross_exposure_ratio == pytest.approx(0.8)
    assert ledger.target_cash_allocation == pytest.approx(0.2)
    assert ledger.gross_exposure.iloc[0] == pytest.approx(80.0)
    assert ledger.cash.iloc[0] == pytest.approx(20.0)
    assert ledger.debt.iloc[0] == 0.0
    assert ledger.equity.iloc[1] == pytest.approx(108.0)
    assert ledger.gross_exposure.iloc[1] == pytest.approx(86.4)
    assert ledger.cash.iloc[1] == pytest.approx(21.6)
    assert ledger.debt.iloc[1] == pytest.approx(0.0)
    assert ledger.gross_exposure_ratio.iloc[1] == pytest.approx(0.8)
    assert ledger.gross_exposure_ratio.iloc[2] == pytest.approx(0.8)
    assert ledger.leverage_reset_count == 1
    assert any(event.type == "leverage_reset" for event in ledger.events)

def test_weight_defined_leverage_resets_gross_exposure_at_each_close() -> None:
    history = _history(
        "AAA",
        ["2024-01-02", "2024-01-03", "2024-01-04"],
        [0.0, 0.10, -0.10],
    )
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("1.5x", {"AAA": 1.5}),
        {"AAA": history},
        SimulationConfig(
            initial_amount=100.0,
            leverage=LeverageConfig(maintenance_margin_percent=0.0),
        ),
    )

    assert ledger.gross_exposure.iloc[0] == pytest.approx(150.0)
    assert ledger.debt.iloc[0] == pytest.approx(50.0)
    assert ledger.equity.iloc[1] == pytest.approx(115.0)
    assert ledger.gross_exposure.iloc[1] == pytest.approx(172.5)
    assert ledger.debt.iloc[1] == pytest.approx(57.5)
    assert ledger.gross_exposure_ratio.iloc[1] == pytest.approx(1.5)
    assert ledger.equity.iloc[2] == pytest.approx(97.75)
    assert ledger.gross_exposure.iloc[2] == pytest.approx(146.625)
    assert ledger.debt.iloc[2] == pytest.approx(48.875)
    assert ledger.gross_exposure_ratio.iloc[2] == pytest.approx(1.5)
    assert ledger.return_index.iloc[-1] == pytest.approx(0.9775)
    assert ledger.leverage_reset_count == 2
    assert all(
        event.details["asset_allocation_preserved"] is True
        for event in ledger.events
        if event.type == "leverage_reset"
    )


def test_daily_leverage_reset_preserves_asset_mix_until_allocation_rebalance() -> None:
    dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
    histories = {
        "AAA": _history("AAA", dates, [0.0, 0.20, 0.0]),
        "BBB": _history("BBB", dates, [0.0, 0.0, 0.0]),
    }
    portfolio = PortfolioSpec.from_weights(
        "1.5x balanced",
        {"AAA": 0.75, "BBB": 0.75},
    )

    reset_only = simulate_portfolio_ledger(
        portfolio,
        histories,
        SimulationConfig(
            initial_amount=100.0,
            leverage=LeverageConfig(maintenance_margin_percent=0.0),
        ),
    )
    assert reset_only.rebalance_count == 0
    assert reset_only.leverage_reset_count >= 1
    assert reset_only.allocation_history.iloc[1]["AAA"] == pytest.approx(90.0 / 165.0)
    assert reset_only.allocation_history.iloc[1]["BBB"] == pytest.approx(75.0 / 165.0)
    assert reset_only.gross_exposure_ratio.iloc[1] == pytest.approx(1.5)

    threshold_rebalanced = simulate_portfolio_ledger(
        portfolio,
        histories,
        SimulationConfig(
            initial_amount=100.0,
            rebalancing=RebalanceConfig(threshold_percent=4.0),
            leverage=LeverageConfig(maintenance_margin_percent=0.0),
        ),
    )
    assert threshold_rebalanced.rebalance_count >= 1
    assert threshold_rebalanced.allocation_history.iloc[1]["AAA"] == pytest.approx(0.5)
    assert threshold_rebalanced.allocation_history.iloc[1]["BBB"] == pytest.approx(0.5)
    assert threshold_rebalanced.gross_exposure_ratio.iloc[1] == pytest.approx(1.5)
    assert any(
        event.type == "rebalance" and event.details["trigger"] == "threshold"
        for event in threshold_rebalanced.events
    )


def test_gross_only_drift_does_not_trigger_asset_allocation_threshold() -> None:
    history = _history(
        "AAA",
        ["2024-01-02", "2024-01-03", "2024-01-04"],
        [0.0, 0.10, 0.0],
    )
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("One asset 1.5x", {"AAA": 1.5}),
        {"AAA": history},
        SimulationConfig(
            initial_amount=100.0,
            rebalancing=RebalanceConfig(threshold_percent=1.0),
            leverage=LeverageConfig(maintenance_margin_percent=0.0),
        ),
    )

    assert ledger.rebalance_count == 0
    assert ledger.leverage_reset_count >= 1
    assert any(event.type == "leverage_reset" for event in ledger.events)


def test_underinvested_gross_drift_does_not_trigger_asset_mix_threshold() -> None:
    history = _history(
        "AAA",
        ["2024-01-02", "2024-01-03", "2024-01-04"],
        [0.0, 0.25, 0.0],
    )
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("80/20 threshold", {"AAA": 0.8}),
        {"AAA": history},
        SimulationConfig(
            initial_amount=100.0,
            rebalancing=RebalanceConfig(threshold_percent=3.0),
        ),
    )

    assert ledger.rebalance_count == 0
    assert ledger.leverage_reset_count == 1
    assert ledger.equity.iloc[1] == pytest.approx(120.0)
    assert ledger.gross_exposure.iloc[1] == pytest.approx(96.0)
    assert ledger.cash.iloc[1] == pytest.approx(24.0)
    assert ledger.gross_exposure_ratio.iloc[1] == pytest.approx(0.8)
    assert any(event.type == "leverage_reset" for event in ledger.events)


def test_underinvested_daily_reset_preserves_asset_mix_until_rebalance() -> None:
    dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
    histories = {
        "AAA": _history("AAA", dates, [0.0, 0.20, 0.0]),
        "BBB": _history("BBB", dates, [0.0, 0.0, 0.0]),
    }
    portfolio = PortfolioSpec.from_weights(
        "50 percent balanced",
        {"AAA": 0.3, "BBB": 0.2},
    )

    reset_only = simulate_portfolio_ledger(
        portfolio,
        histories,
        SimulationConfig(initial_amount=100.0),
    )
    assert reset_only.rebalance_count == 0
    assert reset_only.leverage_reset_count >= 1
    assert reset_only.gross_exposure_ratio.iloc[1] == pytest.approx(0.5)
    assert reset_only.cash.iloc[1] == pytest.approx(53.0)
    assert reset_only.allocation_history.iloc[1]["AAA"] == pytest.approx(36.0 / 56.0)
    assert reset_only.allocation_history.iloc[1]["BBB"] == pytest.approx(20.0 / 56.0)

    threshold_rebalanced = simulate_portfolio_ledger(
        portfolio,
        histories,
        SimulationConfig(
            initial_amount=100.0,
            rebalancing=RebalanceConfig(threshold_percent=4.0),
        ),
    )
    assert threshold_rebalanced.rebalance_count >= 1
    assert threshold_rebalanced.allocation_history.iloc[1]["AAA"] == pytest.approx(0.6)
    assert threshold_rebalanced.allocation_history.iloc[1]["BBB"] == pytest.approx(0.4)
    assert threshold_rebalanced.gross_exposure_ratio.iloc[1] == pytest.approx(0.5)
    assert any(
        event.type == "rebalance" and event.details["trigger"] == "threshold"
        for event in threshold_rebalanced.events
    )

def test_leverage_reset_transaction_cost_is_charged_inside_ledger() -> None:
    history = _history(
        "AAA",
        ["2024-01-02", "2024-01-03"],
        [0.0, 0.10],
    )
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("Costed 1.5x", {"AAA": 1.5}),
        {"AAA": history},
        SimulationConfig(
            initial_amount=100.0,
            transaction_cost_bps=100.0,
            leverage=LeverageConfig(maintenance_margin_percent=0.0),
        ),
    )

    assert 0.0 < ledger.transaction_costs < 0.1
    assert ledger.equity.iloc[1] < 115.0
    assert ledger.gross_exposure_ratio.iloc[1] == pytest.approx(1.5)
    event = next(event for event in ledger.events if event.type == "leverage_reset")
    assert event.details["traded_notional"] > 0.0
    assert event.details["transaction_cost"] == pytest.approx(
        ledger.transaction_costs
    )


def test_weight_defined_exposure_rejects_ambiguous_legacy_leverage_overlay() -> None:
    history = _history(
        "AAA",
        ["2024-01-02", "2024-01-03"],
        [0.0, 0.0],
    )
    with pytest.raises(ValueError, match="cannot be combined"):
        simulate_portfolio_ledger(
            PortfolioSpec.from_weights("Ambiguous", {"AAA": 1.5}),
            {"AAA": history},
            SimulationConfig(
                initial_amount=100.0,
                leverage=LeverageConfig(type=LeverageType.FIXED_RATIO, ratio=2.0),
            ),
        )


def test_legacy_fixed_ratio_now_uses_the_same_daily_reset_authority() -> None:
    history = _history(
        "AAA",
        ["2024-01-02", "2024-01-03"],
        [0.0, 0.10],
    )
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("Legacy 2x", {"AAA": 1.0}),
        {"AAA": history},
        SimulationConfig(
            initial_amount=100.0,
            leverage=LeverageConfig(
                type=LeverageType.FIXED_RATIO,
                ratio=2.0,
                maintenance_margin_percent=0.0,
            ),
        ),
    )

    assert ledger.equity.iloc[1] == pytest.approx(120.0)
    assert ledger.gross_exposure.iloc[1] == pytest.approx(240.0)
    assert ledger.debt.iloc[1] == pytest.approx(120.0)
    assert ledger.gross_exposure_ratio.iloc[1] == pytest.approx(2.0)
    assert ledger.leverage_reset_count == 1


def test_initial_target_exposure_must_satisfy_maintenance_margin() -> None:
    history = _history(
        "AAA",
        ["2024-01-02", "2024-01-03"],
        [0.0, 0.0],
    )

    valid = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("Valid 3x", {"AAA": 3.0}),
        {"AAA": history},
        SimulationConfig(
            initial_amount=100.0,
            leverage=LeverageConfig(maintenance_margin_percent=25.0),
        ),
    )
    assert valid.gross_exposure_ratio.iloc[0] == pytest.approx(3.0)

    with pytest.raises(ValueError, match="initial portfolio exposure"):
        simulate_portfolio_ledger(
            PortfolioSpec.from_weights("Invalid 5x", {"AAA": 5.0}),
            {"AAA": history},
            SimulationConfig(
                initial_amount=100.0,
                leverage=LeverageConfig(maintenance_margin_percent=25.0),
            ),
        )


def test_initial_fixed_debt_also_uses_the_same_margin_guard() -> None:
    history = _history(
        "AAA",
        ["2024-01-02", "2024-01-03"],
        [0.0, 0.0],
    )

    with pytest.raises(ValueError, match="initial portfolio exposure"):
        simulate_portfolio_ledger(
            PortfolioSpec.from_weights("Invalid fixed debt", {"AAA": 1.0}),
            {"AAA": history},
            SimulationConfig(
                initial_amount=100.0,
                leverage=LeverageConfig(
                    type=LeverageType.FIXED_DEBT,
                    debt_amount=400.0,
                    maintenance_margin_percent=25.0,
                ),
            ),
        )
