from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apps.api.app.portfolio.ledger import PortfolioLedger, _rebalance
from apps.api.app.portfolio.models import LeverageConfig


def test_legacy_portfolio_ledger_constructor_derives_new_exposure_diagnostics() -> None:
    index = pd.to_datetime(["2024-01-02", "2024-01-03"])
    equity = pd.Series([100.0, 110.0], index=index, name="equity")
    zeros = pd.Series(0.0, index=index, dtype=float)
    gross = equity.rename("gross_exposure")
    ledger = PortfolioLedger(
        name="legacy fixture",
        symbols=("AAA",),
        target_allocation={"AAA": 1.0},
        equity=equity,
        return_index=pd.Series([1.0, 1.1], index=index, name="return_index"),
        daily_returns=pd.Series([0.0, 0.1], index=index, name="daily_return"),
        external_flows=zeros.rename("external_flow"),
        income=zeros.rename("income"),
        cumulative_income=zeros.rename("cumulative_income"),
        cash=zeros.rename("cash"),
        debt=zeros.rename("debt"),
        gross_exposure=gross,
        allocation_history=pd.DataFrame({"AAA": [1.0, 1.0]}, index=index),
        transaction_costs=0.0,
        borrowing_costs=0.0,
        rebalance_count=0,
        events=[],
        warnings=[],
        liquidated=False,
    )

    assert ledger.target_asset_mix == {"AAA": 1.0}
    assert ledger.target_gross_exposure_ratio == pytest.approx(1.0)
    assert ledger.target_cash_allocation == pytest.approx(0.0)
    assert ledger.leverage_reset_count == 0
    assert ledger.net_exposure.tolist() == pytest.approx([100.0, 110.0])
    assert ledger.gross_exposure_ratio.tolist() == pytest.approx([1.0, 1.0])
    assert ledger.net_exposure_ratio.tolist() == pytest.approx([1.0, 1.0])


def test_existing_weight_vector_rebalance_adapter_uses_same_policy_authority() -> None:
    assets = np.asarray([110.0, 0.0], dtype=float)
    target_weights = np.asarray([0.0, 1.0], dtype=float)

    target, debt, cash, cost, traded = _rebalance(
        assets,
        0.0,
        0.0,
        target_weights,
        LeverageConfig(),
        100.0,
    )

    assert traded == pytest.approx(220.0)
    assert cost == pytest.approx(2.2)
    assert target.tolist() == pytest.approx([0.0, 107.8])
    assert debt == pytest.approx(0.0)
    assert cash == pytest.approx(0.0)
