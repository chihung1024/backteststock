from __future__ import annotations

import pandas as pd
import pytest

from apps.api.app.data.twd_valuation import (
    VALUATION_CURRENCY,
    TWDValuationError,
    value_adjusted_close_in_twd,
)


def _series(values, dates) -> pd.Series:
    return pd.Series(values, index=pd.to_datetime(dates), dtype=float)


def test_usd_adjusted_close_is_valued_daily_in_twd() -> None:
    native = _series([100.0, 102.0, 101.0], ["2025-01-02", "2025-01-03", "2025-01-06"])
    fx = _series([30.0, 30.4, 30.3], ["2025-01-02", "2025-01-03", "2025-01-06"])

    valued = value_adjusted_close_in_twd(
        native,
        source_currency="USD",
        fx_to_twd=fx,
    )

    assert valued.source_currency == "USD"
    assert valued.adjusted_close_twd.tolist() == pytest.approx([3000.0, 3100.8, 3060.3])
    assert valued.daily_returns.tolist() == pytest.approx(
        [0.0, 3100.8 / 3000.0 - 1.0, 3060.3 / 3100.8 - 1.0]
    )


def test_fx_only_day_changes_twd_value_while_native_market_is_closed() -> None:
    native = _series([100.0, 100.0], ["2025-01-02", "2025-01-06"])
    fx = _series([30.0, 30.2, 30.3], ["2025-01-02", "2025-01-03", "2025-01-06"])

    valued = value_adjusted_close_in_twd(
        native,
        source_currency="USD",
        fx_to_twd=fx,
    )

    assert valued.adjusted_close_twd.index.tolist() == list(pd.to_datetime(fx.index))
    assert valued.native_adjusted_close.tolist() == pytest.approx([100.0, 100.0, 100.0])
    assert valued.adjusted_close_twd.tolist() == pytest.approx([3000.0, 3020.0, 3030.0])
    assert valued.daily_returns.tolist() == pytest.approx([0.0, 30.2 / 30.0 - 1.0, 30.3 / 30.2 - 1.0])


def test_future_fx_quote_is_not_backfilled_into_first_native_day() -> None:
    native = _series([100.0, 101.0], ["2025-01-02", "2025-01-03"])
    fx = _series([30.0], ["2025-01-03"])

    valued = value_adjusted_close_in_twd(
        native,
        source_currency="USD",
        fx_to_twd=fx,
    )

    assert valued.adjusted_close_twd.index.tolist() == [pd.Timestamp("2025-01-03")]
    assert valued.adjusted_close_twd.tolist() == pytest.approx([3030.0])


def test_twd_asset_requires_no_fx_series_and_preserves_adjusted_close() -> None:
    native = _series([100.0, 102.0], ["2025-01-02", "2025-01-03"])

    valued = value_adjusted_close_in_twd(native, source_currency=VALUATION_CURRENCY)

    assert valued.fx_to_twd.tolist() == pytest.approx([1.0, 1.0])
    assert valued.adjusted_close_twd.equals(native.rename("adjusted_close_twd"))


def test_non_twd_asset_requires_positive_verified_fx() -> None:
    native = _series([100.0, 102.0], ["2025-01-02", "2025-01-03"])

    with pytest.raises(TWDValuationError, match="require a verified USD/TWD FX"):
        value_adjusted_close_in_twd(native, source_currency="USD")

    with pytest.raises(TWDValuationError, match="only positive"):
        value_adjusted_close_in_twd(
            native,
            source_currency="USD",
            fx_to_twd=_series([30.0, 0.0], ["2025-01-02", "2025-01-03"]),
        )
