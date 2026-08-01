"""Corporate-action-aware adjusted-price extraction and audit helpers.

Yahoo Finance exposes raw split-adjusted Close, total-return Adj Close, and a
limited event taxonomy (dividends, stock splits, and capital-gains
distributions).  This module makes that contract explicit instead of relying on
``auto_adjust=True`` silently renaming Adj Close to Close.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

CORPORATE_ACTION_POLICY_VERSION = "2026-08-01.2"
RETURN_BASIS = "yahoo_adjusted_close_total_return_gross_reinvestment"
RETURN_PRICE_COLUMN = "Adj Close"
RAW_PRICE_COLUMN = "Close"
STANDARD_ACTION_COVERAGE = (
    "cash_dividends_reported_by_yahoo",
    "special_dividends_reported_by_yahoo",
    "stock_splits_and_reverse_splits_reported_by_yahoo",
    "capital_gains_distributions_reported_by_yahoo",
    "stock_dividends_when_encoded_as_splits",
)
NONSTANDARD_ACTION_LIMITATIONS = (
    "spin_off_distribution_not_reported_as_yahoo_adjustment",
    "rights_or_warrant_distribution",
    "cash_or_stock_merger_consideration",
    "ticker_or_exchange_change_history_stitching",
    "adr_ratio_change_not_reported_as_split",
    "delisting_or_liquidation_cash_proceeds",
    "tax_withholding_fees_and_transaction_costs",
)
EVENT_COLUMNS = ("Dividends", "Stock Splits", "Capital Gains")
FACTOR_CHANGE_TOLERANCE = 5e-4
DISTRIBUTION_RELATIVE_TOLERANCE = 0.25
DISTRIBUTION_ABSOLUTE_TOLERANCE = 2.5e-3
LARGE_UNEXPLAINED_RETURN_THRESHOLD = 0.75
SPLIT_LIKE_RATIOS = np.asarray(
    [0.1, 0.2, 0.25, 1 / 3, 0.5, 2.0, 3.0, 4.0, 5.0, 10.0],
    dtype=float,
)


def _normalise_index(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    index = pd.DatetimeIndex(pd.to_datetime(series.index))
    if index.tz is not None:
        index = index.tz_convert(None)
    series = series.copy()
    series.index = index.normalize()
    return series[~series.index.duplicated(keep="last")].sort_index()


def _normalise_price(raw, name: str) -> pd.Series:
    if raw is None:
        return pd.Series(dtype=float, name=name)
    series = pd.to_numeric(raw, errors="coerce").astype(float)
    series = series.replace([np.inf, -np.inf], np.nan).dropna()
    series = series[series > 0]
    series = _normalise_index(series)
    series.name = name
    return series


def _normalise_event(raw, name: str) -> pd.Series:
    if raw is None:
        return pd.Series(dtype=float, name=name)
    series = pd.to_numeric(raw, errors="coerce").astype(float)
    series = series.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    series = _normalise_index(series)
    series.name = name
    return series


def _normalise_repaired(raw) -> pd.Series:
    if raw is None:
        return pd.Series(dtype=bool, name="Repaired?")
    series = pd.Series(raw).fillna(False).astype(bool)
    series = _normalise_index(series)
    series.name = "Repaired?"
    return series


def _field_table(downloaded: pd.DataFrame, field: str):
    if not isinstance(downloaded, pd.DataFrame) or downloaded.empty:
        return None
    if isinstance(downloaded.columns, pd.MultiIndex):
        for level in range(downloaded.columns.nlevels):
            if field in set(downloaded.columns.get_level_values(level)):
                return downloaded.xs(field, axis=1, level=level, drop_level=True)
        return None
    if field in downloaded.columns:
        return downloaded[field]
    return None


def _ticker_series(table, ticker: str, ticker_count: int):
    if table is None:
        return None
    if isinstance(table, pd.Series):
        return table if ticker_count == 1 else None
    if not isinstance(table, pd.DataFrame):
        return None
    if ticker in table.columns:
        return table[ticker]
    if isinstance(table.columns, pd.MultiIndex):
        matches = [column for column in table.columns if ticker in column]
        if len(matches) == 1:
            return table[matches[0]]
    if ticker_count == 1 and len(table.columns) == 1:
        return table.iloc[:, 0]
    return None


def _event_neighbour_mask(events: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    mask = events.reindex(index, fill_value=0.0).abs() > 0
    return mask | mask.shift(1, fill_value=False) | mask.shift(-1, fill_value=False)


def _split_like_unreported_returns(
    adjusted: pd.Series,
    declared_actions: pd.Series,
) -> pd.Series:
    ratios = adjusted / adjusted.shift(1)
    nearest = pd.Series(np.inf, index=ratios.index, dtype=float)
    valid = ratios.notna()
    if valid.any():
        distances = np.abs(
            ratios.loc[valid].to_numpy(dtype=float)[:, None] / SPLIT_LIKE_RATIOS - 1.0
        )
        nearest.loc[valid] = np.min(distances, axis=1)
    return nearest.le(0.03) & ~declared_actions & valid


def build_corporate_action_audit(
    *,
    ticker: str,
    adjusted_close: pd.Series,
    raw_close: pd.Series,
    dividends: pd.Series | None = None,
    stock_splits: pd.Series | None = None,
    capital_gains: pd.Series | None = None,
    repaired: pd.Series | None = None,
) -> dict:
    adjusted = _normalise_price(adjusted_close, ticker)
    raw = _normalise_price(raw_close, ticker)
    dividends = _normalise_event(dividends, "Dividends")
    stock_splits = _normalise_event(stock_splits, "Stock Splits")
    capital_gains = _normalise_event(capital_gains, "Capital Gains")
    repaired = _normalise_repaired(repaired)

    base = {
        "policy_version": CORPORATE_ACTION_POLICY_VERSION,
        "return_basis": RETURN_BASIS,
        "price_column": RETURN_PRICE_COLUMN,
        "raw_close_available": not raw.empty,
        "adjusted_close_available": not adjusted.empty,
        "dividend_events": int((dividends.abs() > 0).sum()),
        "stock_split_events": int((stock_splits.abs() > 0).sum()),
        "capital_gain_events": int((capital_gains.abs() > 0).sum()),
        "repaired_rows": int(repaired.sum()),
        "unexplained_adjustment_factor_changes": 0,
        "distribution_adjustment_mismatches": 0,
        "split_like_unreported_changes": 0,
        "large_unexplained_returns": 0,
        "warning_dates": [],
    }
    if adjusted.empty:
        return {**base, "status": "missing_adjusted_close"}
    if raw.empty:
        return {**base, "status": "adjusted_close_unverifiable"}

    paired = pd.concat(
        [adjusted.rename("adjusted"), raw.rename("raw")], axis=1, join="inner"
    ).dropna()
    if len(paired) < 2:
        return {**base, "status": "insufficient_audit_history"}

    index = paired.index
    distributions = (
        dividends.reindex(index, fill_value=0.0)
        + capital_gains.reindex(index, fill_value=0.0)
    )
    splits = stock_splits.reindex(index, fill_value=0.0)
    factor = paired["adjusted"] / paired["raw"]
    factor_change = factor / factor.shift(1) - 1.0
    event_neighbours = _event_neighbour_mask(distributions, index)
    unexplained_factor = (
        factor_change.abs() > FACTOR_CHANGE_TOLERANCE
    ) & ~event_neighbours

    previous_close = paired["raw"].shift(1)
    valid_distribution = (
        distributions.abs() > 0
    ) & previous_close.gt(0) & (distributions.abs() < previous_close * 0.95)
    expected_factor_change = 1.0 / (1.0 - distributions / previous_close) - 1.0
    tolerance = np.maximum(
        DISTRIBUTION_ABSOLUTE_TOLERANCE,
        expected_factor_change.abs() * DISTRIBUTION_RELATIVE_TOLERANCE,
    )
    distribution_mismatch = valid_distribution & (
        (factor_change - expected_factor_change).abs() > tolerance
    )

    declared_actions = _event_neighbour_mask(distributions.abs() + splits.abs(), index)
    adjusted_returns = paired["adjusted"].pct_change(fill_method=None)
    split_like = _split_like_unreported_returns(paired["adjusted"], declared_actions)
    large_unexplained = (
        adjusted_returns.abs() > LARGE_UNEXPLAINED_RETURN_THRESHOLD
    ) & ~declared_actions

    warning_mask = (
        unexplained_factor
        | distribution_mismatch
        | split_like
        | large_unexplained
    )
    warning_dates = [date.strftime("%Y-%m-%d") for date in index[warning_mask]][:20]
    review_required = bool(warning_mask.any())

    return {
        **base,
        "status": "review_required" if review_required else "verified_standard_actions",
        "unexplained_adjustment_factor_changes": int(unexplained_factor.sum()),
        "distribution_adjustment_mismatches": int(distribution_mismatch.sum()),
        "split_like_unreported_changes": int(split_like.sum()),
        "large_unexplained_returns": int(large_unexplained.sum()),
        "warning_dates": warning_dates,
    }


def extract_adjusted_close_prices(
    downloaded: pd.DataFrame,
    tickers: Iterable[str],
) -> dict[str, pd.Series]:
    """Return explicit Adj Close total-return series with per-symbol audit attrs."""
    requested = list(dict.fromkeys(str(ticker) for ticker in tickers))
    adjusted_table = _field_table(downloaded, RETURN_PRICE_COLUMN)
    raw_table = _field_table(downloaded, RAW_PRICE_COLUMN)
    dividend_table = _field_table(downloaded, "Dividends")
    split_table = _field_table(downloaded, "Stock Splits")
    capital_gain_table = _field_table(downloaded, "Capital Gains")
    repaired_table = _field_table(downloaded, "Repaired?")

    extracted: dict[str, pd.Series] = {}
    for ticker in requested:
        adjusted = _normalise_price(
            _ticker_series(adjusted_table, ticker, len(requested)), ticker
        )
        if adjusted.empty:
            continue
        raw = _normalise_price(
            _ticker_series(raw_table, ticker, len(requested)), ticker
        )
        audit = build_corporate_action_audit(
            ticker=ticker,
            adjusted_close=adjusted,
            raw_close=raw,
            dividends=_ticker_series(dividend_table, ticker, len(requested)),
            stock_splits=_ticker_series(split_table, ticker, len(requested)),
            capital_gains=_ticker_series(capital_gain_table, ticker, len(requested)),
            repaired=_ticker_series(repaired_table, ticker, len(requested)),
        )
        adjusted.attrs["corporate_action_audit"] = audit
        extracted[ticker] = adjusted
    return extracted


def audit_from_series(series: pd.Series | None) -> dict:
    audit = getattr(series, "attrs", {}).get("corporate_action_audit") if series is not None else None
    if isinstance(audit, dict):
        return dict(audit)
    return {
        "policy_version": CORPORATE_ACTION_POLICY_VERSION,
        "return_basis": RETURN_BASIS,
        "price_column": RETURN_PRICE_COLUMN,
        "status": "audit_not_recorded",
        "raw_close_available": False,
        "adjusted_close_available": bool(series is not None and not series.empty),
        "dividend_events": 0,
        "stock_split_events": 0,
        "capital_gain_events": 0,
        "repaired_rows": 0,
        "unexplained_adjustment_factor_changes": 0,
        "distribution_adjustment_mismatches": 0,
        "split_like_unreported_changes": 0,
        "large_unexplained_returns": 0,
        "warning_dates": [],
    }


def flattened_audit_fields(audit: dict) -> dict:
    return {
        "return_basis": audit.get("return_basis", RETURN_BASIS),
        "corporate_action_policy_version": audit.get(
            "policy_version", CORPORATE_ACTION_POLICY_VERSION
        ),
        "corporate_action_status": audit.get("status", "audit_not_recorded"),
        "dividend_events": int(audit.get("dividend_events", 0) or 0),
        "stock_split_events": int(audit.get("stock_split_events", 0) or 0),
        "capital_gain_events": int(audit.get("capital_gain_events", 0) or 0),
        "price_repaired_rows": int(audit.get("repaired_rows", 0) or 0),
        "unexplained_adjustment_changes": int(
            audit.get("unexplained_adjustment_factor_changes", 0) or 0
        ),
        "distribution_adjustment_mismatches": int(
            audit.get("distribution_adjustment_mismatches", 0) or 0
        ),
        "split_like_unreported_changes": int(
            audit.get("split_like_unreported_changes", 0) or 0
        ),
        "large_unexplained_returns": int(
            audit.get("large_unexplained_returns", 0) or 0
        ),
        "corporate_action_warning_dates": ";".join(audit.get("warning_dates", [])),
    }
