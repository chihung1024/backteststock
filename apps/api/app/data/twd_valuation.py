"""Daily TWD valuation from a native-currency adjusted-close series.

The unified product has one valuation currency: TWD.  For a non-TWD asset the
daily total-return price level is therefore the source's adjusted close times
the number of TWD per unit of its quote currency on that date.  The valuation
calendar is the union of the native market and FX calendars.  A closed local
market carries its last adjusted close forward, so an FX-only day still affects
the TWD value.  Conversely, neither a price nor FX rate is ever filled backward
from a later observation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

VALUATION_CURRENCY = "TWD"
TWD_VALUATION_CONTRACT_VERSION = "twd-adjusted-close-union-calendar-2026-08-03.2"


class TWDValuationError(ValueError):
    """Raised when a series cannot be valued in TWD without inventing data."""


@dataclass(frozen=True, slots=True)
class TWDValuation:
    """A fully auditable daily TWD adjusted-close valuation.

    ``native_adjusted_close`` and ``fx_to_twd`` are exposed on the same
    valuation calendar as ``adjusted_close_twd``.  They are forward-filled only
    after their own first valid observation.  This gives callers the exact
    factors behind every displayed TWD value.

    ``native_observation_mask`` records which valuation-calendar rows came from
    a real native-market price observation before any FX-calendar forward fill.
    Valuation returns remain on the union calendar; portfolio execution can use
    this provenance to avoid trading a constituent on a carried-forward quote.
    """

    source_currency: str
    native_adjusted_close: pd.Series
    fx_to_twd: pd.Series
    adjusted_close_twd: pd.Series
    daily_returns: pd.Series
    native_observation_mask: pd.Series | None = None

    @property
    def first_date(self) -> pd.Timestamp:
        return self.adjusted_close_twd.index[0]

    @property
    def last_date(self) -> pd.Timestamp:
        return self.adjusted_close_twd.index[-1]


def value_adjusted_close_in_twd(
    native_adjusted_close: pd.Series,
    *,
    source_currency: str,
    fx_to_twd: pd.Series | None = None,
) -> TWDValuation:
    """Return daily adjusted-close levels and returns expressed in TWD.

    ``fx_to_twd`` must contain *TWD per one unit of ``source_currency``*.  Its
    source can be a direct or inverted Yahoo cross; cross selection and quality
    checks belong to the downloader.  This function intentionally receives the
    already-normalized rate so the mathematical valuation contract is identical
    in the scanner, backtest, benchmark, and exhaustive optimizer.

    No backward fill is allowed.  If the first usable FX quote comes after the
    first native price, the returned valuation starts on that later date rather
    than borrowing the future FX quote.  Callers that need a shared portfolio
    calendar must align the resulting TWD levels afterwards.
    """

    currency = _normalize_currency(source_currency)
    native = _clean_positive_series(native_adjusted_close, label="native adjusted close")
    native_observation_index = native.index

    if currency == VALUATION_CURRENCY:
        fx = pd.Series(1.0, index=native.index, dtype=float, name="fx_to_twd")
        twd = native.rename("adjusted_close_twd")
        native_observation_mask = pd.Series(
            True,
            index=native.index,
            dtype=bool,
            name="native_market_observation",
        )
    else:
        if fx_to_twd is None:
            raise TWDValuationError(
                f"{currency} assets require a verified {currency}/TWD FX series"
            )
        source_fx = _clean_positive_series(fx_to_twd, label="FX to TWD")
        valuation_index = native.index.union(source_fx.index).sort_values().unique()
        native_observation_mask = pd.Series(
            valuation_index.isin(native_observation_index),
            index=valuation_index,
            dtype=bool,
            name="native_market_observation",
        )
        native = native.reindex(valuation_index).ffill()
        fx = source_fx.reindex(valuation_index).ffill()

        # Do not fabricate an opening price or rate.  This intentionally differs
        # from a backward fill: data begins only once both observed histories have
        # a contemporaneous or prior value.
        usable = native.notna() & fx.notna()
        native = native.loc[usable]
        fx = fx.loc[usable]
        native_observation_mask = native_observation_mask.loc[usable]
        if native.empty:
            raise TWDValuationError(
                f"{currency} adjusted close and {currency}/TWD FX have no usable overlap"
            )
        twd = (native * fx).rename("adjusted_close_twd")

    daily_returns = twd.pct_change(fill_method=None).fillna(0.0).rename("daily_return")
    return TWDValuation(
        source_currency=currency,
        native_adjusted_close=native.rename("native_adjusted_close"),
        fx_to_twd=fx.rename("fx_to_twd"),
        adjusted_close_twd=twd,
        daily_returns=daily_returns,
        native_observation_mask=native_observation_mask,
    )


def _clean_positive_series(values: pd.Series, *, label: str) -> pd.Series:
    if not isinstance(values, pd.Series):
        raise TWDValuationError(f"{label} must be a pandas Series")
    try:
        index = pd.DatetimeIndex(pd.to_datetime(values.index))
    except (TypeError, ValueError) as exc:
        raise TWDValuationError(f"{label} index is not datetime-like") from exc
    if index.tz is not None:
        index = index.tz_localize(None)

    result = pd.Series(values.to_numpy(copy=True), index=index, dtype="float64")
    result = result.replace([np.inf, -np.inf], np.nan).dropna().sort_index()
    result = result.loc[~result.index.duplicated(keep="last")]
    if result.empty:
        raise TWDValuationError(f"{label} has no finite observations")
    if (result <= 0.0).any():
        raise TWDValuationError(f"{label} must contain only positive observations")
    return result.astype(float)


def _normalize_currency(value: str) -> str:
    currency = str(value or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise TWDValuationError(f"invalid quote currency: {value!r}")
    return currency
