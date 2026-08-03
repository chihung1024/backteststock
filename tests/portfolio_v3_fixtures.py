from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from apps.api.app.data.history_service import (
    HistoryFailure,
    PartialTWDHistories,
    TWDAssetHistory,
)
from apps.api.app.data.return_components import TWDReturnComponents
from apps.api.app.data.twd_valuation import TWDValuation


def make_history(
    symbol: str,
    index: pd.DatetimeIndex,
    total_returns: list[float] | np.ndarray | pd.Series,
    *,
    price_returns: list[float] | np.ndarray | pd.Series | None = None,
    distribution_returns: list[float] | np.ndarray | pd.Series | None = None,
    quote_currency: str = "TWD",
    fx_returns: list[float] | np.ndarray | pd.Series | None = None,
) -> TWDAssetHistory:
    total = pd.Series(total_returns, index=index, dtype=float, name="total_return")
    price = pd.Series(
        total_returns if price_returns is None else price_returns,
        index=index,
        dtype=float,
        name="price_return",
    )
    distribution = pd.Series(
        np.zeros(len(index)) if distribution_returns is None else distribution_returns,
        index=index,
        dtype=float,
        name="distribution_return",
    )
    np.testing.assert_allclose(total, price + distribution, atol=1e-12)
    fx_return_series = pd.Series(
        np.zeros(len(index)) if fx_returns is None else fx_returns,
        index=index,
        dtype=float,
    )
    fx_levels = (1.0 + fx_return_series).cumprod().rename("fx_to_twd")
    total_index = (1.0 + total).cumprod().rename("total_return_index")
    price_index = (1.0 + price).cumprod().rename("price_return_index")
    adjusted = (100.0 * total_index).rename("adjusted_close_twd")
    valuation = TWDValuation(
        source_currency=quote_currency,
        native_adjusted_close=adjusted.rename("native_adjusted_close"),
        fx_to_twd=fx_levels,
        adjusted_close_twd=adjusted,
        daily_returns=total.rename("daily_return"),
    )
    components = TWDReturnComponents(
        source_currency=quote_currency,
        fx_to_twd=fx_levels,
        total_returns=total,
        price_returns=price,
        distribution_returns=distribution,
        total_return_index=total_index,
        price_return_index=price_index,
        audit={
            "status": "synthetic",
            "contract_version": "test-return-components",
            "observations": len(index),
        },
    )
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency=quote_currency,
        valuation=valuation,
        corporate_action_audit={"status": "verified_standard_actions"},
        fx_audit={
            "source_currency": quote_currency,
            "target_currency": "TWD",
            "method": "synthetic",
        },
        return_components=components,
    )


class FakeHistoryService:
    def __init__(
        self,
        histories: dict[str, TWDAssetHistory],
        failures: dict[str, HistoryFailure] | None = None,
    ) -> None:
        self.histories = histories
        self.failures = failures or {}
        self.calls: list[tuple[tuple[str, ...], date, date]] = []

    def histories_partial(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> PartialTWDHistories:
        requested = tuple(dict.fromkeys(symbols))
        self.calls.append((requested, start, end))
        available = {
            symbol: self.histories[symbol]
            for symbol in requested
            if symbol in self.histories
        }
        failures = {
            symbol: self.failures.get(
                symbol,
                HistoryFailure(
                    symbol=symbol,
                    stage="download",
                    detail="synthetic missing history",
                    retryable=True,
                ),
            )
            for symbol in requested
            if symbol not in available
        }
        return PartialTWDHistories(
            requested=requested,
            histories=available,
            failures=failures,
        )
