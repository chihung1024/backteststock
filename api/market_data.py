"""Shared finite Yahoo market-data downloader with a versioned data contract."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterable

import numpy as np
import pandas as pd
import yfinance as yf
from cachetools import TTLCache

from api.corporate_actions import (
    CORPORATE_ACTION_POLICY_VERSION,
    audit_from_series,
    build_corporate_action_audit,
    extract_adjusted_close_prices,
)
from api.instrument_identity import (
    INSTRUMENT_IDENTITY_CONTRACT_VERSION,
    apply_instrument_lifecycle_guard,
    clear_instrument_identity_cache,
    resolve_instrument_identities,
)
from api.metrics import DATA_SOURCE_SETTINGS

logger = logging.getLogger(__name__)

RETURN_COMPONENT_SOURCE_VERSION = "yahoo-close-events-2026-08-04.1"
MARKET_DATA_CONTRACT_VERSION = (
    f"adjusted-close-actions-components-{CORPORATE_ACTION_POLICY_VERSION}-"
    f"{RETURN_COMPONENT_SOURCE_VERSION}-{INSTRUMENT_IDENTITY_CONTRACT_VERSION}"
)
DEFAULT_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = (0.0, 1.5, 5.0)
DEFAULT_TIMEOUT_SECONDS = 12
DEFAULT_DOWNLOAD_THREADS = 16
DEFAULT_BATCH_SIZE = 100

_price_cache = TTLCache(maxsize=1024, ttl=3600)
_price_cache_lock = threading.RLock()


def deduplicate(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def bulk_download_prices(
    tickers,
    start_date,
    end_date,
    *,
    use_threads: bool = True,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    download_threads: int = DEFAULT_DOWNLOAD_THREADS,
):
    """Fetch raw Close, explicit Adj Close, events, and repair diagnostics."""
    requested = list(tickers)
    thread_count = min(download_threads, max(len(requested), 1))
    return yf.download(
        requested,
        start=start_date,
        end=end_date,
        interval=DATA_SOURCE_SETTINGS["interval"],
        auto_adjust=DATA_SOURCE_SETTINGS["auto_adjust"],
        actions=DATA_SOURCE_SETTINGS["actions"],
        repair=DATA_SOURCE_SETTINGS["repair"],
        keepna=DATA_SOURCE_SETTINGS["keepna"],
        progress=False,
        threads=thread_count if use_threads else False,
        timeout=timeout_seconds,
        group_by="column",
        multi_level_index=True,
    )


def _cache_key(ticker: str, start_date, end_date):
    return MARKET_DATA_CONTRACT_VERSION, ticker, str(start_date), str(end_date)


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


def _normalise_component(raw, *, name: str, event: bool = False) -> pd.Series:
    if raw is None:
        return pd.Series(dtype=float, name=name)
    values = pd.to_numeric(raw, errors="coerce").astype(float)
    values = values.replace([np.inf, -np.inf], np.nan)
    values = values.fillna(0.0) if event else values.dropna()
    if event:
        values = values.clip(lower=0.0)
    else:
        values = values[values > 0.0]
    if values.empty:
        return pd.Series(dtype=float, name=name)
    index = pd.DatetimeIndex(pd.to_datetime(values.index))
    if index.tz is not None:
        index = index.tz_convert(None)
    values = values.copy()
    values.index = index.normalize()
    values = values.loc[~values.index.duplicated(keep="last")].sort_index()
    values.name = name
    return values.astype(float)


def _normalise_repaired(raw) -> pd.Series:
    if raw is None:
        return pd.Series(dtype=bool, name="Repaired?")
    values = pd.Series(raw).fillna(False).astype(bool)
    if values.empty:
        return pd.Series(dtype=bool, name="Repaired?")
    index = pd.DatetimeIndex(pd.to_datetime(values.index))
    if index.tz is not None:
        index = index.tz_convert(None)
    values.index = index.normalize()
    values = values.loc[~values.index.duplicated(keep="last")].sort_index()
    values.name = "Repaired?"
    return values


def _attach_return_component_attrs(
    downloaded: pd.DataFrame,
    requested: list[str],
    extracted: dict[str, pd.Series],
) -> None:
    """Attach cleaned component inputs without changing the public return type."""

    tables = {
        "raw_close": _field_table(downloaded, "Close"),
        "dividends": _field_table(downloaded, "Dividends"),
        "capital_gains": _field_table(downloaded, "Capital Gains"),
        "stock_splits": _field_table(downloaded, "Stock Splits"),
        "repaired": _field_table(downloaded, "Repaired?"),
    }
    ticker_count = len(requested)
    for ticker, adjusted in extracted.items():
        attrs = dict(getattr(adjusted, "attrs", {}) or {})
        attrs.update(
            {
                "return_component_source_version": RETURN_COMPONENT_SOURCE_VERSION,
                "raw_close": _normalise_component(
                    _ticker_series(tables["raw_close"], ticker, ticker_count),
                    name="raw_close",
                ),
                "dividends": _normalise_component(
                    _ticker_series(tables["dividends"], ticker, ticker_count),
                    name="dividends",
                    event=True,
                ),
                "capital_gains": _normalise_component(
                    _ticker_series(tables["capital_gains"], ticker, ticker_count),
                    name="capital_gains",
                    event=True,
                ),
                "stock_splits": _normalise_component(
                    _ticker_series(tables["stock_splits"], ticker, ticker_count),
                    name="stock_splits",
                    event=True,
                ),
                "repaired": _normalise_repaired(
                    _ticker_series(tables["repaired"], ticker, ticker_count)
                ),
            }
        )
        adjusted.attrs = attrs


def _apply_instrument_identity_guards(
    extracted: dict[str, pd.Series],
) -> dict[str, pd.Series]:
    """Keep only rows belonging to each ticker's current Yahoo instrument."""

    identities = resolve_instrument_identities(extracted)
    guarded: dict[str, pd.Series] = {}
    for ticker, adjusted in extracted.items():
        identity = identities.get(ticker)
        if identity is None:
            continue
        current = apply_instrument_lifecycle_guard(adjusted, identity)
        if current.empty:
            continue
        attrs = dict(current.attrs)
        corporate_audit = build_corporate_action_audit(
            ticker=ticker,
            adjusted_close=current,
            raw_close=attrs.get("raw_close"),
            dividends=attrs.get("dividends"),
            stock_splits=attrs.get("stock_splits"),
            capital_gains=attrs.get("capital_gains"),
            repaired=attrs.get("repaired"),
        )
        corporate_audit["instrument_identity"] = dict(
            attrs.get("instrument_identity_audit") or {}
        )
        attrs["corporate_action_audit"] = corporate_audit
        current.attrs = attrs
        guarded[ticker] = current
    return guarded


def download_prices_finitely(
    tickers,
    start_date,
    end_date,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    backoff_seconds=DEFAULT_BACKOFF_SECONDS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    download_threads: int = DEFAULT_DOWNLOAD_THREADS,
    batch_size: int = DEFAULT_BATCH_SIZE,
):
    """Resolve symbols in large finite requests and preserve per-symbol audits."""
    requested = deduplicate(tickers)
    resolved: dict[str, pd.Series] = {}
    pending: list[str] = []

    with _price_cache_lock:
        for ticker in requested:
            cached = _price_cache.get(_cache_key(ticker, start_date, end_date))
            if cached is None:
                pending.append(ticker)
            else:
                resolved[ticker] = cached.copy()

    errors = []
    delays = tuple(backoff_seconds)[:attempts]
    for attempt_index, delay in enumerate(delays, start=1):
        if not pending:
            break
        if delay:
            time.sleep(delay)

        unresolved: list[str] = []
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset : offset + batch_size]
            try:
                downloaded = bulk_download_prices(
                    batch,
                    start_date,
                    end_date,
                    use_threads=attempt_index < attempts,
                    timeout_seconds=timeout_seconds,
                    download_threads=download_threads,
                )
                extracted = extract_adjusted_close_prices(downloaded, batch)
                _attach_return_component_attrs(downloaded, batch, extracted)
                extracted = _apply_instrument_identity_guards(extracted)
            except Exception as exc:  # noqa: BLE001 - upstream boundary
                logger.warning(
                    "Corporate-action market-data request failed",
                    extra={"attempt": attempt_index, "ticker_count": len(batch)},
                    exc_info=exc,
                )
                errors.append(exc)
                extracted = {}

            for ticker in batch:
                prices = extracted.get(ticker)
                if prices is None or prices.empty:
                    unresolved.append(ticker)
                    continue
                resolved[ticker] = prices
                with _price_cache_lock:
                    _price_cache[_cache_key(ticker, start_date, end_date)] = prices.copy()
        pending = unresolved

    if pending:
        logger.warning(
            "Adjusted-close data remained incomplete after finite retries",
            extra={
                "requested_count": len(requested),
                "resolved_count": len(resolved),
                "unresolved_count": len(pending),
                "error_count": len(errors),
                "contract_version": MARKET_DATA_CONTRACT_VERSION,
            },
        )
    return resolved, pending


def download_data_reliably(
    tickers,
    start_date,
    end_date,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    backoff_seconds=DEFAULT_BACKOFF_SECONDS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    download_threads: int = DEFAULT_DOWNLOAD_THREADS,
    batch_size: int = DEFAULT_BATCH_SIZE,
):
    """Return a price DataFrame plus failures, retaining action audits in attrs."""
    requested = deduplicate(tickers)
    resolved, unresolved = download_prices_finitely(
        requested,
        start_date,
        end_date,
        attempts=attempts,
        backoff_seconds=backoff_seconds,
        timeout_seconds=timeout_seconds,
        download_threads=download_threads,
        batch_size=batch_size,
    )
    failures = {
        ticker: RuntimeError("upstream returned no usable explicit Adj Close prices")
        for ticker in unresolved
    }
    if not resolved:
        frame = pd.DataFrame(columns=requested)
    else:
        columns = [ticker for ticker in requested if ticker in resolved]
        frame = pd.DataFrame({ticker: resolved[ticker] for ticker in columns})
        frame = frame.reindex(columns=columns)
    frame.attrs["market_data_contract_version"] = MARKET_DATA_CONTRACT_VERSION
    frame.attrs["corporate_action_audits"] = {
        ticker: audit_from_series(series) for ticker, series in resolved.items()
    }
    frame.attrs["instrument_identity_contract_version"] = (
        INSTRUMENT_IDENTITY_CONTRACT_VERSION
    )
    frame.attrs["instrument_identity_audits"] = {
        ticker: dict(series.attrs.get("instrument_identity_audit") or {})
        for ticker, series in resolved.items()
    }
    frame.attrs["return_component_source_version"] = RETURN_COMPONENT_SOURCE_VERSION
    frame.attrs["return_component_inputs"] = {
        ticker: {
            "raw_close": resolved[ticker].attrs.get("raw_close"),
            "dividends": resolved[ticker].attrs.get("dividends"),
            "capital_gains": resolved[ticker].attrs.get("capital_gains"),
            "stock_splits": resolved[ticker].attrs.get("stock_splits"),
            "repaired": resolved[ticker].attrs.get("repaired"),
        }
        for ticker in resolved
    }
    return frame, failures


def download_data_silently(tickers, start_date, end_date, **kwargs):
    prices, _failures = download_data_reliably(
        tickers, start_date, end_date, **kwargs
    )
    return prices


def clear_price_cache():
    with _price_cache_lock:
        _price_cache.clear()
    clear_instrument_identity_cache()
