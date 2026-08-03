from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apps.api.app.data.history_service import TWDAssetHistory
from apps.api.app.data.return_components import TWDReturnComponents
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.portfolio.ledger import simulate_portfolio_ledger
from apps.api.app.portfolio.models import (
    CashflowConfig,
    CashflowFrequency,
    CashflowTiming,
    CashflowType,
    LeverageConfig,
    LeverageType,
    PortfolioSpec,
    SimulationConfig,
    validate_portfolio_batch,
)


def _flat_history(symbol: str, dates: list[str]) -> TWDAssetHistory:
    index = pd.to_datetime(dates)
    returns = pd.Series(0.0, index=index, name="total_return")
    levels = pd.Series(100.0, index=index, name="adjusted_close_twd")
    fx = pd.Series(1.0, index=index, name="fx_to_twd")
    valuation = TWDValuation(
        source_currency="TWD",
        native_adjusted_close=levels.rename("native_adjusted_close"),
        fx_to_twd=fx,
        adjusted_close_twd=levels,
        daily_returns=returns.rename("daily_return"),
    )
    components = TWDReturnComponents(
        source_currency="TWD",
        fx_to_twd=fx,
        total_returns=returns,
        price_returns=returns.rename("price_return"),
        distribution_returns=returns.rename("distribution_return"),
        total_return_index=pd.Series(1.0, index=index),
        price_return_index=pd.Series(1.0, index=index),
        audit={"status": "synthetic"},
    )
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency="TWD",
        valuation=valuation,
        corporate_action_audit={"status": "verified_standard_actions"},
        return_components=components,
    )


def test_beginning_annual_contribution_applies_growth_and_preserves_twr() -> None:
    history = _flat_history(
        "AAA",
        ["2024-01-02", "2024-12-31", "2025-01-02"],
    )
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("Growth flow", {"AAA": 1.0}),
        {"AAA": history},
        SimulationConfig(
            initial_amount=1_000.0,
            cashflow=CashflowConfig(
                type=CashflowType.FIXED,
                amount=100.0,
                frequency=CashflowFrequency.ANNUAL,
                timing=CashflowTiming.BEGINNING,
                annual_growth_rate_percent=10.0,
            ),
        ),
    )

    assert ledger.external_flows.loc[pd.Timestamp("2025-01-02")] == pytest.approx(110.0)
    assert ledger.equity.iloc[-1] == pytest.approx(1_110.0)
    np.testing.assert_allclose(ledger.return_index, 1.0)
    event = next(event for event in ledger.events if event.type == "external_cashflow")
    assert event.details["timing"] == "beginning"


def test_fixed_ratio_contribution_updates_assets_and_debt_consistently() -> None:
    history = _flat_history(
        "AAA",
        ["2024-01-30", "2024-01-31", "2024-02-01"],
    )
    ledger = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("Leveraged flow", {"AAA": 1.0}),
        {"AAA": history},
        SimulationConfig(
            initial_amount=100.0,
            cashflow=CashflowConfig(
                type=CashflowType.FIXED,
                amount=100.0,
                frequency=CashflowFrequency.MONTHLY,
                timing=CashflowTiming.END,
            ),
            leverage=LeverageConfig(
                type=LeverageType.FIXED_RATIO,
                ratio=2.0,
                maintenance_margin_percent=0.0,
            ),
        ),
    )

    assert ledger.equity.iloc[-1] == pytest.approx(200.0)
    assert ledger.gross_exposure.iloc[-1] == pytest.approx(400.0)
    assert ledger.debt.iloc[-1] == pytest.approx(200.0)
    np.testing.assert_allclose(ledger.return_index, 1.0)


def test_batch_validation_enforces_five_portfolios_and_unique_names() -> None:
    portfolios = tuple(
        PortfolioSpec.from_weights(f"Portfolio {index}", {"AAA": 1.0})
        for index in range(6)
    )
    with pytest.raises(ValueError, match="1 to 5"):
        validate_portfolio_batch(portfolios)

    duplicate_names = (
        PortfolioSpec.from_weights("Same", {"AAA": 1.0}),
        PortfolioSpec.from_weights("Same", {"BBB": 1.0}),
    )
    with pytest.raises(ValueError, match="names must be unique"):
        validate_portfolio_batch(duplicate_names)
