"""Partial-success TWD market-data service for scanner and backtest callers."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd

from api.market_data import download_prices_finitely
from apps.api.app.data.fx_provider import FXLevels, YahooFXProvider
from apps.api.app.data.twd_valuation import (
    TWDValuation,
    TWDValuationError,
    value_adjusted_close_in_twd,
)

logger = logging.getLogger(__name__)

_MAX_CURRENCY_WORKERS = 4


@dataclass(frozen=True, slots=True)
class HistoryFailure:
    """An explicit per-symbol outcome which callers can show in their precheck."""

    symbol: str
    stage: str
    detail: str
    retryable: bool


@dataclass(slots=True)
class TWDAssetHistory:
    """One symbol's audited native and TWD-adjusted daily price levels."""

    symbol: str
    quote_currency: str
    valuation: TWDValuation
    corporate_action_audit: dict[str, Any] | None
    fx_audit: dict[str, Any] | None = None

    @property
    def native_adjusted_close(self) -> pd.Series:
        return self.valuation.native_adjusted_close

    @property
    def fx_to_twd(self) -> pd.Series:
        return self.valuation.fx_to_twd

    @property
    def adjusted_close_twd(self) -> pd.Series:
        return self.valuation.adjusted_close_twd

    @property
    def daily_returns(self) -> pd.Series:
        return self.valuation.daily_returns


@dataclass(slots=True)
class PartialTWDHistories:
    """Successful histories plus non-destructive failures from one batch request."""

    requested: tuple[str, ...]
    histories: dict[str, TWDAssetHistory]
    failures: dict[str, HistoryFailure]

    @property
    def is_complete(self) -> bool:
        return not self.failures


class TWDHistoryService:
    """Build individual TWD histories without allowing one symbol to erase a batch.

    The service reuses the existing, corporate-action-audited finite Yahoo
    downloader during migration.  It adds the missing quote-currency lookup,
    FX normalization, and daily TWD valuation in a framework-neutral layer.
    The Flask compatibility routes for portfolio backtest, scanner, and
    exhaustive-optimizer snapshot construction all use this service today;
    the same layer remains reusable for a future FastAPI migration.
    """

    def __init__(self, *, fx_provider: YahooFXProvider | None = None) -> None:
        self._fx_provider = fx_provider or YahooFXProvider()

    def histories_partial(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> PartialTWDHistories:
        """Fetch all possible symbols, retaining each successful TWD history.

        A download, quote-currency, or FX failure is reported for that symbol
        only.  The method never silently removes a ticker or changes the input
        order, so the UI can ask the user how to proceed with the precheck.

        ``end`` is inclusive.  The Yahoo equity downloader receives its required
        exclusive upper boundary internally, while the FX adapter returns no
        observations after this final requested valuation date.
        """

        requested = _normalized_symbols(symbols)
        if not requested:
            return PartialTWDHistories(requested=(), histories={}, failures={})

        try:
            native_prices, unresolved = download_prices_finitely(
                requested,
                start.isoformat(),
                (end + timedelta(days=1)).isoformat(),
            )
        except Exception as exc:  # noqa: BLE001 - keep an upstream batch failure explicit
            return PartialTWDHistories(
                requested=requested,
                histories={},
                failures={
                    symbol: HistoryFailure(
                        symbol=symbol,
                        stage="download",
                        detail=str(exc),
                        retryable=True,
                    )
                    for symbol in requested
                },
            )
        failures: dict[str, HistoryFailure] = {
            symbol: HistoryFailure(
                symbol=symbol,
                stage="download",
                detail="Yahoo returned no usable audited adjusted-close history after finite retries",
                retryable=True,
            )
            for symbol in unresolved
        }
        usable_native = {
            symbol: prices.copy()
            for symbol, prices in native_prices.items()
            if symbol in requested and symbol not in failures and not prices.empty
        }
        for symbol in requested:
            if symbol not in failures and symbol not in usable_native:
                failures[symbol] = HistoryFailure(
                    symbol=symbol,
                    stage="download",
                    detail="Yahoo downloader did not return this requested symbol",
                    retryable=True,
                )

        currencies = self._resolve_currencies(usable_native, failures)
        grouped: dict[str, list[str]] = {}
        for symbol in usable_native:
            currency = currencies.get(symbol)
            if currency is not None:
                grouped.setdefault(currency, []).append(symbol)

        histories: dict[str, TWDAssetHistory] = {}
        for currency, group in grouped.items():
            fx_levels: FXLevels | None = None
            if currency != "TWD":
                try:
                    fx_levels = self._fx_provider.fx_to_twd(currency, start, end)
                except Exception as exc:  # noqa: BLE001 - external FX boundary
                    logger.warning("TWD FX conversion unavailable for %s: %s", currency, exc)
                    for symbol in group:
                        failures[symbol] = HistoryFailure(
                            symbol=symbol,
                            stage="fx",
                            detail=str(exc),
                            retryable=True,
                        )
                    continue

            for symbol in group:
                native = usable_native[symbol]
                try:
                    valuation = value_adjusted_close_in_twd(
                        native,
                        source_currency=currency,
                        fx_to_twd=None if fx_levels is None else fx_levels.levels,
                    )
                except TWDValuationError as exc:
                    failures[symbol] = HistoryFailure(
                        symbol=symbol,
                        stage="valuation",
                        detail=str(exc),
                        retryable=False,
                    )
                    continue
                histories[symbol] = TWDAssetHistory(
                    symbol=symbol,
                    quote_currency=currency,
                    valuation=valuation,
                    corporate_action_audit=_audit_from_native_series(native),
                    fx_audit=_fx_audit(currency, fx_levels),
                )

        return PartialTWDHistories(
            requested=requested,
            histories=histories,
            failures=failures,
        )

    def _resolve_currencies(
        self,
        native_prices: dict[str, pd.Series],
        failures: dict[str, HistoryFailure],
    ) -> dict[str, str]:
        """Resolve each symbol independently, with bounded metadata concurrency."""

        if not native_prices:
            return {}
        currencies: dict[str, str] = {}
        workers = min(_MAX_CURRENCY_WORKERS, len(native_prices))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._fx_provider.quote_currency, symbol): symbol
                for symbol in native_prices
            }
            for future, symbol in futures.items():
                try:
                    currencies[symbol] = future.result()
                except Exception as exc:  # noqa: BLE001 - external metadata boundary
                    failures[symbol] = HistoryFailure(
                        symbol=symbol,
                        stage="currency",
                        detail=str(exc),
                        retryable=True,
                    )
        return currencies


def normalize_symbol(symbol: str) -> str:
    """Normalize Taiwan shorthand without changing an explicit Yahoo ticker."""

    value = str(symbol or "").strip().upper()
    if value.isdigit() and 4 <= len(value) <= 6:
        return f"{value}.TW"
    return value


def _normalized_symbols(symbols: list[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in symbols:
        symbol = normalize_symbol(raw)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        result.append(symbol)
    return tuple(result)


def _audit_from_native_series(series: pd.Series) -> dict[str, Any] | None:
    audit = series.attrs.get("corporate_action_audit")
    return dict(audit) if isinstance(audit, dict) else None


def _fx_audit(currency: str, levels: FXLevels | None) -> dict[str, Any]:
    if currency == "TWD":
        return {
            "source_currency": "TWD",
            "target_currency": "TWD",
            "method": "identity",
            "tickers": [],
            "correction_count": 0,
            "unresolved_count": 0,
            "material_transition_count": 0,
        }
    if levels is None:
        raise AssertionError("non-TWD asset requires FX levels before valuation")
    return {
        "source_currency": levels.source_currency,
        "target_currency": levels.target_currency,
        "method": levels.method,
        "tickers": list(levels.tickers),
        "correction_count": levels.correction_count,
        "unresolved_count": levels.unresolved_count,
        "material_transition_count": levels.material_transition_count,
    }
