"""Auditable price, distribution, and total-return components in TWD.

The unified product values every asset in TWD.  A portfolio ledger needs more
than a total-return adjusted-close series because users may retain cash
distributions instead of reinvesting them.  This module decomposes the exact
adjusted-close total return into a price component and a non-negative cash
component, then converts both through the same no-look-ahead TWD valuation
calendar used by the scanner, backtest, and exhaustive optimizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from apps.api.app.data.twd_valuation import TWDValuationError, VALUATION_CURRENCY

RETURN_COMPONENTS_CONTRACT_VERSION = "twd-return-components-2026-08-04.1"
_COMPONENT_TOLERANCE = 5e-4
_EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class NativeReturnComponents:
    """Native-quote-currency return components on the asset calendar."""

    adjusted_close: pd.Series
    raw_close: pd.Series
    distributions: pd.Series
    total_returns: pd.Series
    price_returns: pd.Series
    distribution_returns: pd.Series
    audit: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TWDReturnComponents:
    """Return components on the union asset/FX TWD valuation calendar."""

    source_currency: str
    fx_to_twd: pd.Series
    total_returns: pd.Series
    price_returns: pd.Series
    distribution_returns: pd.Series
    total_return_index: pd.Series
    price_return_index: pd.Series
    audit: dict[str, Any]

    @property
    def first_date(self) -> pd.Timestamp:
        return self.total_returns.index[0]

    @property
    def last_date(self) -> pd.Timestamp:
        return self.total_returns.index[-1]


def native_components_from_adjusted_close(
    adjusted_close: pd.Series,
) -> NativeReturnComponents:
    """Build an exact additive decomposition from an audited adjusted series.

    ``api.market_data`` records cleaned raw Close, dividends, and capital-gain
    distributions in the adjusted series attrs.  Reported cash distributions
    are converted to returns using the previous raw close.  The price component
    is then defined as ``total - distribution`` so the additive identity is
    exact even when Yahoo rounds its adjustment factor or a split changes the
    raw-price scale.  If that price component would imply a loss of 100% or
    worse, the function falls back to the raw price return and derives the cash
    residual conservatively.
    """

    adjusted = _clean_positive_series(adjusted_close, label="adjusted close")
    attrs = dict(getattr(adjusted_close, "attrs", {}) or {})
    raw = _clean_optional_positive_series(attrs.get("raw_close"), adjusted.index)
    dividends = _clean_optional_nonnegative_series(attrs.get("dividends"), adjusted.index)
    capital_gains = _clean_optional_nonnegative_series(
        attrs.get("capital_gains"), adjusted.index
    )
    distributions = (dividends + capital_gains).rename("distributions")

    total = adjusted.pct_change(fill_method=None).fillna(0.0).rename("total_return")
    if raw.empty:
        price = total.copy().rename("price_return")
        cash = pd.Series(0.0, index=adjusted.index, name="distribution_return")
        return NativeReturnComponents(
            adjusted_close=adjusted,
            raw_close=raw,
            distributions=distributions,
            total_returns=total,
            price_returns=price,
            distribution_returns=cash,
            audit={
                "contract_version": RETURN_COMPONENTS_CONTRACT_VERSION,
                "status": "total_return_only",
                "component_source": "adjusted_close_without_raw_components",
                "reported_distribution_events": int((distributions > 0).sum()),
                "fallback_rows": 0,
                "raw_total_mismatch_rows": 0,
                "max_raw_total_residual": None,
            },
        )

    raw = raw.reindex(adjusted.index).ffill()
    previous_raw = raw.shift(1)
    reported_cash = pd.Series(0.0, index=adjusted.index, dtype=float)
    valid_cash = previous_raw.gt(_EPSILON) & distributions.gt(0.0)
    reported_cash.loc[valid_cash] = (
        distributions.loc[valid_cash] / previous_raw.loc[valid_cash]
    )
    reported_cash = reported_cash.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    reported_cash = reported_cash.clip(lower=0.0).rename("reported_distribution_return")

    raw_price = raw.pct_change(fill_method=None).fillna(0.0).rename("raw_price_return")
    cash = reported_cash.copy()
    price = (total - cash).rename("price_return")

    invalid_price = (~np.isfinite(price)) | price.le(-1.0 + _EPSILON)
    fallback_cash = (total - raw_price).clip(lower=0.0)
    cash.loc[invalid_price] = fallback_cash.loc[invalid_price]
    price.loc[invalid_price] = total.loc[invalid_price] - cash.loc[invalid_price]

    # A final safety fallback preserves a valid price path and the exact identity.
    still_invalid = (~np.isfinite(price)) | price.le(-1.0 + _EPSILON)
    cash.loc[still_invalid] = 0.0
    price.loc[still_invalid] = total.loc[still_invalid]

    cash = cash.rename("distribution_return")
    price = price.rename("price_return")
    additive_residual = (total - price - cash).abs()
    if float(additive_residual.max()) > 1e-12:
        raise TWDValuationError("return-component additive identity was not preserved")

    raw_total_residual = (total - (raw_price + reported_cash)).abs()
    material_mismatch = raw_total_residual.gt(_COMPONENT_TOLERANCE)
    fallback_rows = int(invalid_price.sum())
    status = "verified_components"
    if fallback_rows:
        status = "verified_with_price_fallback"
    elif bool(material_mismatch.any()):
        status = "verified_with_adjustment_residual"

    return NativeReturnComponents(
        adjusted_close=adjusted,
        raw_close=raw.rename("raw_close"),
        distributions=distributions,
        total_returns=total,
        price_returns=price,
        distribution_returns=cash,
        audit={
            "contract_version": RETURN_COMPONENTS_CONTRACT_VERSION,
            "status": status,
            "component_source": "reported_distributions_plus_exact_adjusted_total",
            "reported_distribution_events": int((distributions > 0).sum()),
            "fallback_rows": fallback_rows,
            "raw_total_mismatch_rows": int(material_mismatch.sum()),
            "max_raw_total_residual": float(raw_total_residual.max()),
        },
    )


def value_components_in_twd(
    native: NativeReturnComponents,
    *,
    source_currency: str,
    fx_to_twd: pd.Series | None = None,
) -> TWDReturnComponents:
    """Convert native components to TWD without backward-filling future data.

    The valuation calendar is the union of the native adjusted-close calendar
    and the FX calendar.  Native and FX levels are forward-filled only after
    their own first observations.  Missing asset-market returns on FX-only days
    are zero; the FX return still changes both the price and total TWD value.
    Cash distributions are converted at the contemporaneous FX movement using
    ``native_distribution * (1 + fx_return)``.
    """

    currency = _normalize_currency(source_currency)
    adjusted = native.adjusted_close
    if currency == VALUATION_CURRENCY:
        calendar = adjusted.index
        fx = pd.Series(1.0, index=calendar, dtype=float, name="fx_to_twd")
        usable = pd.Series(True, index=calendar)
    else:
        if fx_to_twd is None:
            raise TWDValuationError(
                f"{currency} return components require a verified {currency}/TWD FX series"
            )
        source_fx = _clean_positive_series(fx_to_twd, label="FX to TWD")
        calendar = adjusted.index.union(source_fx.index).sort_values().unique()
        native_level = adjusted.reindex(calendar).ffill()
        fx = source_fx.reindex(calendar).ffill().rename("fx_to_twd")
        usable = native_level.notna() & fx.notna()
        calendar = calendar[usable]
        fx = fx.loc[calendar]
        if len(calendar) < 1:
            raise TWDValuationError(
                f"{currency} adjusted close and {currency}/TWD FX have no usable overlap"
            )

    native_total = native.total_returns.reindex(calendar).fillna(0.0)
    native_distribution = native.distribution_returns.reindex(calendar).fillna(0.0)
    native_total.iloc[0] = 0.0
    native_distribution.iloc[0] = 0.0
    fx_return = fx.pct_change(fill_method=None).fillna(0.0)
    fx_return.iloc[0] = 0.0

    total = ((1.0 + native_total) * (1.0 + fx_return) - 1.0).rename("total_return")
    cash = (native_distribution * (1.0 + fx_return)).rename("distribution_return")
    price = (total - cash).rename("price_return")

    invalid_price = (~np.isfinite(price)) | price.le(-1.0 + _EPSILON)
    if bool(invalid_price.any()):
        raise TWDValuationError("TWD price component contains an invalid return")
    if bool(cash.lt(-_EPSILON).any()):
        raise TWDValuationError("TWD distribution component must be non-negative")
    residual = (total - price - cash).abs()
    if float(residual.max()) > 1e-12:
        raise TWDValuationError("TWD return-component additive identity was not preserved")

    total_index = (1.0 + total).cumprod().rename("total_return_index")
    price_index = (1.0 + price).cumprod().rename("price_return_index")
    return TWDReturnComponents(
        source_currency=currency,
        fx_to_twd=fx,
        total_returns=total,
        price_returns=price,
        distribution_returns=cash,
        total_return_index=total_index,
        price_return_index=price_index,
        audit={
            **native.audit,
            "contract_version": RETURN_COMPONENTS_CONTRACT_VERSION,
            "valuation_currency": VALUATION_CURRENCY,
            "source_currency": currency,
            "calendar_policy": "union_native_fx_forward_fill_after_observation_no_backward_fill",
            "observations": int(len(calendar)),
            "distribution_events": int(cash.gt(0.0).sum()),
        },
    )


def total_only_components(
    adjusted_close_twd: pd.Series,
    *,
    source_currency: str,
) -> TWDReturnComponents:
    """Compatibility fallback for synthetic or legacy histories without attrs."""

    adjusted = _clean_positive_series(adjusted_close_twd, label="TWD adjusted close")
    total = adjusted.pct_change(fill_method=None).fillna(0.0).rename("total_return")
    cash = pd.Series(0.0, index=adjusted.index, name="distribution_return")
    price = total.copy().rename("price_return")
    return TWDReturnComponents(
        source_currency=_normalize_currency(source_currency),
        fx_to_twd=pd.Series(1.0, index=adjusted.index, name="fx_to_twd"),
        total_returns=total,
        price_returns=price,
        distribution_returns=cash,
        total_return_index=(1.0 + total).cumprod().rename("total_return_index"),
        price_return_index=(1.0 + price).cumprod().rename("price_return_index"),
        audit={
            "contract_version": RETURN_COMPONENTS_CONTRACT_VERSION,
            "status": "total_return_only",
            "valuation_currency": VALUATION_CURRENCY,
            "source_currency": _normalize_currency(source_currency),
            "calendar_policy": "existing_twd_history",
            "observations": int(len(adjusted)),
            "distribution_events": 0,
        },
    )


def _clean_positive_series(values: pd.Series, *, label: str) -> pd.Series:
    if not isinstance(values, pd.Series):
        raise TWDValuationError(f"{label} must be a pandas Series")
    index = _datetime_index(values.index, label=label)
    result = pd.Series(values.to_numpy(copy=True), index=index, dtype="float64")
    result = result.replace([np.inf, -np.inf], np.nan).dropna().sort_index()
    result = result.loc[~result.index.duplicated(keep="last")]
    if result.empty:
        raise TWDValuationError(f"{label} has no finite observations")
    if bool(result.le(0.0).any()):
        raise TWDValuationError(f"{label} must contain only positive observations")
    return result.astype(float)


def _clean_optional_positive_series(values: Any, index: pd.DatetimeIndex) -> pd.Series:
    if not isinstance(values, pd.Series):
        return pd.Series(dtype=float, name="raw_close")
    try:
        cleaned = _clean_positive_series(values, label="raw close")
    except TWDValuationError:
        return pd.Series(dtype=float, name="raw_close")
    return cleaned.reindex(index).rename("raw_close")


def _clean_optional_nonnegative_series(values: Any, index: pd.DatetimeIndex) -> pd.Series:
    if not isinstance(values, pd.Series):
        return pd.Series(0.0, index=index, dtype=float)
    source_index = _datetime_index(values.index, label="distribution")
    cleaned = pd.Series(values.to_numpy(copy=True), index=source_index, dtype="float64")
    cleaned = cleaned.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    cleaned = cleaned.clip(lower=0.0)
    cleaned = cleaned.loc[~cleaned.index.duplicated(keep="last")].sort_index()
    return cleaned.reindex(index, fill_value=0.0).astype(float)


def _datetime_index(values: Any, *, label: str) -> pd.DatetimeIndex:
    try:
        index = pd.DatetimeIndex(pd.to_datetime(values))
    except (TypeError, ValueError) as exc:
        raise TWDValuationError(f"{label} index is not datetime-like") from exc
    if index.tz is not None:
        index = index.tz_localize(None)
    return index.normalize()


def _normalize_currency(value: str) -> str:
    currency = str(value or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise TWDValuationError(f"invalid quote currency: {value!r}")
    return currency
