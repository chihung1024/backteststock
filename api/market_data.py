"""Shared finite Yahoo market-data downloader with a versioned data contract."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterable

import pandas as pd
import yfinance as yf
from cachetools import TTLCache

from api.corporate_actions import (
    CORPORATE_ACTION_POLICY_VERSION,
    audit_from_series,
    extract_adjusted_close_prices,
)
from api.metrics import DATA_SOURCE_SETTINGS

logger = logging.getLogger(__name__)

MARKET_DATA_CONTRACT_VERSION = f"adjusted-close-actions-{CORPORATE_ACTION_POLICY_VERSION}"
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
    return frame, failures


def download_data_silently(tickers, start_date, end_date, **kwargs):
    prices, _failures = download_data_reliably(
        tickers, start_date, end_date, **kwargs
    )
    return prices


def clear_price_cache():
    with _price_cache_lock:
        _price_cache.clear()
