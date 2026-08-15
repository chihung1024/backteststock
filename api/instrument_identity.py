"""Current-instrument lifecycle guard for Yahoo market histories.

Yahoo chart data is keyed by ticker text. A ticker can be reused, or Yahoo can
stitch history across an instrument change. Price rows alone therefore do not
prove that a historical observation belongs to the instrument represented by
the ticker today.

This module resolves Yahoo's current ``firstTradeDate`` metadata and clips every
history/component series before that boundary. The guard is intentionally
separate from return math and corporate-action math: it establishes instrument
identity before either calculation is allowed to consume the data.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import pandas as pd
import yfinance as yf
from cachetools import TTLCache

logger = logging.getLogger(__name__)

INSTRUMENT_IDENTITY_CONTRACT_VERSION = "yahoo-first-trade-date-2026-08-15.1"
INSTRUMENT_IDENTITY_SOURCE = "yahoo_history_metadata.firstTradeDate"
_MAX_IDENTITY_WORKERS = 8
_MAX_IDENTITY_ATTEMPTS = 2

_identity_cache = TTLCache(maxsize=2048, ttl=6 * 60 * 60)
_identity_failure_cache = TTLCache(maxsize=2048, ttl=30)
_identity_cache_lock = threading.RLock()


@dataclass(frozen=True, slots=True)
class InstrumentIdentity:
    """Current Yahoo instrument identity evidence for one symbol."""

    symbol: str
    status: str
    first_trade_date: date | None
    detail: str | None = None
    source: str = INSTRUMENT_IDENTITY_SOURCE
    exchange_timezone: str | None = None

    def audit(self) -> dict[str, Any]:
        return {
            "contract_version": INSTRUMENT_IDENTITY_CONTRACT_VERSION,
            "status": self.status,
            "source": self.source,
            "symbol": self.symbol,
            "first_trade_date": (
                self.first_trade_date.isoformat() if self.first_trade_date else None
            ),
            "exchange_timezone": self.exchange_timezone,
            "detail": self.detail,
        }


def resolve_instrument_identity(symbol: str) -> InstrumentIdentity:
    """Resolve current-instrument first-trade evidence with a bounded Yahoo call."""

    normalized = str(symbol or "").strip().upper()
    if not normalized:
        return InstrumentIdentity(
            symbol="",
            status="unverified_metadata",
            first_trade_date=None,
            detail="empty symbol",
        )

    with _identity_cache_lock:
        cached = _identity_cache.get(normalized)
        failed = _identity_failure_cache.get(normalized)
    if cached is not None:
        return cached
    if failed is not None:
        return failed

    errors: list[str] = []
    for _attempt in range(_MAX_IDENTITY_ATTEMPTS):
        try:
            metadata = yf.Ticker(normalized).get_history_metadata()
            if not isinstance(metadata, dict):
                raise TypeError("Yahoo history metadata was not an object")
            exchange_timezone = str(metadata.get("exchangeTimezoneName") or "").strip()
            if not exchange_timezone:
                raise ValueError(
                    "Yahoo history metadata did not include exchangeTimezoneName"
                )
            first_trade_date = parse_first_trade_date(
                metadata.get("firstTradeDate"), exchange_timezone
            )
            if first_trade_date is None:
                raise ValueError("Yahoo history metadata did not include valid firstTradeDate")
            identity = InstrumentIdentity(
                symbol=normalized,
                status="verified",
                first_trade_date=first_trade_date,
                exchange_timezone=exchange_timezone,
            )
            with _identity_cache_lock:
                _identity_cache[normalized] = identity
                _identity_failure_cache.pop(normalized, None)
            return identity
        except Exception as exc:  # noqa: BLE001 - untrusted upstream metadata boundary
            errors.append(str(exc))

    detail = errors[-1] if errors else "Yahoo instrument metadata unavailable"
    identity = InstrumentIdentity(
        symbol=normalized,
        status="unverified_metadata",
        first_trade_date=None,
        detail=detail,
    )
    # Keep failures only briefly. That suppresses duplicate lookups inside the
    # same finite retry cycle without turning a transient metadata outage into a
    # multi-hour correctness outage.
    with _identity_cache_lock:
        _identity_failure_cache[normalized] = identity
    logger.warning(
        "Instrument identity metadata unavailable for %s: %s", normalized, detail
    )
    return identity


def resolve_instrument_identities(
    symbols: Iterable[str],
) -> dict[str, InstrumentIdentity]:
    """Resolve unique symbols concurrently without changing requested identity."""

    requested = list(
        dict.fromkeys(str(symbol or "").strip().upper() for symbol in symbols)
    )
    requested = [symbol for symbol in requested if symbol]
    if not requested:
        return {}
    workers = min(_MAX_IDENTITY_WORKERS, len(requested))
    resolved: dict[str, InstrumentIdentity] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(resolve_instrument_identity, symbol): symbol
            for symbol in requested
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                resolved[symbol] = future.result()
            except Exception as exc:  # pragma: no cover - resolver returns explicit failures
                resolved[symbol] = InstrumentIdentity(
                    symbol=symbol,
                    status="unverified_metadata",
                    first_trade_date=None,
                    detail=str(exc),
                )
    return resolved


def apply_instrument_lifecycle_guard(
    series: pd.Series,
    identity: InstrumentIdentity,
) -> pd.Series:
    """Clip a price series and every time-indexed component to current lifetime."""

    guarded = series.copy()
    attrs = dict(getattr(series, "attrs", {}) or {})
    original_first = _date_string(guarded.index[0]) if not guarded.empty else None
    original_last = _date_string(guarded.index[-1]) if not guarded.empty else None
    removed_rows = 0

    if identity.first_trade_date is not None and not guarded.empty:
        boundary = pd.Timestamp(identity.first_trade_date)
        keep = pd.DatetimeIndex(guarded.index) >= boundary
        removed_rows = int((~keep).sum())
        guarded = guarded.loc[keep].copy()
        attrs = _clip_time_series_attrs(attrs, boundary)

    effective_first = _date_string(guarded.index[0]) if not guarded.empty else None
    lifecycle_status = identity.status
    if identity.first_trade_date is not None:
        lifecycle_status = "verified_clipped" if removed_rows else "verified"
        if guarded.empty:
            lifecycle_status = "verified_no_overlap"

    attrs["instrument_identity_audit"] = {
        **identity.audit(),
        "status": lifecycle_status,
        "original_first_date": original_first,
        "original_last_date": original_last,
        "effective_first_date": effective_first,
        "removed_pre_inception_rows": removed_rows,
        "clipping_applied": bool(removed_rows),
    }
    guarded.attrs = attrs
    return guarded


def parse_first_trade_date(
    value: object,
    exchange_timezone: str | None = None,
) -> date | None:
    """Parse Yahoo first-trade metadata into the exchange-local trading date."""

    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            if stripped.replace(".", "", 1).isdigit():
                value = float(stripped)
            else:
                return _timestamp_to_local_date(
                    pd.Timestamp(stripped), exchange_timezone
                )
        if isinstance(value, (int, float)):
            number = float(value)
            if not pd.notna(number):
                return None
            unit = "ms" if abs(number) >= 100_000_000_000 else "s"
            parsed = pd.to_datetime(number, unit=unit, utc=True)
            return _timestamp_to_local_date(parsed, exchange_timezone)
        return _timestamp_to_local_date(pd.Timestamp(value), exchange_timezone)
    except (TypeError, ValueError, OverflowError, KeyError):
        return None


def clear_instrument_identity_cache() -> None:
    with _identity_cache_lock:
        _identity_cache.clear()
        _identity_failure_cache.clear()


def _timestamp_to_local_date(
    timestamp: pd.Timestamp,
    exchange_timezone: str | None,
) -> date | None:
    if timestamp.tzinfo is None:
        return timestamp.date()
    target_timezone = str(exchange_timezone or "UTC").strip() or "UTC"
    try:
        return timestamp.tz_convert(target_timezone).date()
    except (TypeError, ValueError, KeyError):
        return None


def _clip_time_series_attrs(attrs: dict[str, Any], boundary: pd.Timestamp) -> dict[str, Any]:
    clipped = dict(attrs)
    for key, value in list(clipped.items()):
        if not isinstance(value, pd.Series) or value.empty:
            continue
        try:
            index = pd.DatetimeIndex(pd.to_datetime(value.index))
        except (TypeError, ValueError):
            continue
        if index.tz is not None:
            index = index.tz_convert(None)
        normalized = value.copy()
        normalized.index = index.normalize()
        clipped[key] = normalized.loc[normalized.index >= boundary].copy()
    return clipped


def _date_string(value: object) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp.date().isoformat()
