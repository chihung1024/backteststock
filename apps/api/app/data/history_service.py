"""Partial-success TWD market-data service for scanner and backtest callers."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from api.market_data import download_prices_finitely
from apps.api.app.data.fx_provider import (
    FXLevels,
    QuoteConvention,
    YahooFXProvider,
    normalize_quote_convention,
)
from apps.api.app.data.return_components import (
    TWDReturnComponents,
    native_components_from_adjusted_close,
    total_only_components,
    value_components_in_twd,
)
from apps.api.app.data.twd_valuation import (
    TWDValuation,
    TWDValuationError,
    value_adjusted_close_in_twd,
)

logger = logging.getLogger(__name__)

_MAX_CURRENCY_WORKERS = 4
_COMPONENT_ALIGNMENT_TOLERANCE = 1e-10
_SCALED_COMPONENT_ATTRS = ("raw_close", "dividends", "capital_gains")


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
    raw_quote_currency: str | None = None
    native_price_scale: float = 1.0
    # Appended after all legacy fields to preserve positional construction.
    return_components: TWDReturnComponents | None = None

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

    @property
    def price_returns(self) -> pd.Series:
        return self._components().price_returns

    @property
    def distribution_returns(self) -> pd.Series:
        return self._components().distribution_returns

    @property
    def total_return_index(self) -> pd.Series:
        return self._components().total_return_index

    @property
    def price_return_index(self) -> pd.Series:
        return self._components().price_return_index

    @property
    def return_component_audit(self) -> dict[str, Any]:
        return dict(self._components().audit)

    def _components(self) -> TWDReturnComponents:
        if self.return_components is not None:
            return self.return_components
        return total_only_components(
            self.adjusted_close_twd,
            source_currency=self.quote_currency,
        )


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
    downloader during migration. It adds quote-currency lookup, FX
    normalization, daily TWD valuation, and an exact price/distribution/total
    return decomposition in a framework-neutral layer. Scanner, portfolio
    backtest, and exhaustive-optimizer callers continue to consume the same
    adjusted-close contract while the new ledger can opt into the components.
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

        A download, quote-currency, FX, or valuation failure is reported for
        that symbol only. The method never silently removes a ticker or changes
        input order, so callers can present an explicit preflight result.

        ``end`` is inclusive. The Yahoo equity downloader receives its required
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
                detail=(
                    "Yahoo returned no usable audited adjusted-close history "
                    "after finite retries"
                ),
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

        quote_conventions = self._resolve_quote_conventions(usable_native, failures)
        grouped: dict[str, list[str]] = {}
        for symbol in usable_native:
            convention = quote_conventions.get(symbol)
            if convention is not None:
                grouped.setdefault(convention.currency, []).append(symbol)

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
                raw_native = usable_native[symbol]
                convention = quote_conventions[symbol]
                native = _scale_native_prices(raw_native, convention.native_price_scale)
                try:
                    valuation = value_adjusted_close_in_twd(
                        native,
                        source_currency=currency,
                        fx_to_twd=None if fx_levels is None else fx_levels.levels,
                    )
                    native_components = native_components_from_adjusted_close(native)
                    return_components = value_components_in_twd(
                        native_components,
                        source_currency=currency,
                        fx_to_twd=None if fx_levels is None else fx_levels.levels,
                    )
                    _verify_component_alignment(valuation, return_components)
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
                    corporate_action_audit=_audit_from_native_series(raw_native),
                    fx_audit=_fx_audit(currency, fx_levels, convention),
                    raw_quote_currency=convention.raw_currency,
                    native_price_scale=convention.native_price_scale,
                    return_components=return_components,
                )

        return PartialTWDHistories(
            requested=requested,
            histories=histories,
            failures=failures,
        )

    def _resolve_quote_conventions(
        self,
        native_prices: dict[str, pd.Series],
        failures: dict[str, HistoryFailure],
    ) -> dict[str, QuoteConvention]:
        """Resolve each symbol independently, with bounded metadata concurrency."""

        if not native_prices:
            return {}
        conventions: dict[str, QuoteConvention] = {}
        workers = min(_MAX_CURRENCY_WORKERS, len(native_prices))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._quote_convention, symbol): symbol
                for symbol in native_prices
            }
            for future, symbol in futures.items():
                try:
                    conventions[symbol] = future.result()
                except Exception as exc:  # noqa: BLE001 - external metadata boundary
                    failures[symbol] = HistoryFailure(
                        symbol=symbol,
                        stage="currency",
                        detail=str(exc),
                        retryable=True,
                    )
        return conventions

    def _quote_convention(self, symbol: str) -> QuoteConvention:
        """Use the rich provider contract, with a major-unit compatibility path."""

        resolver = getattr(self._fx_provider, "quote_convention", None)
        if callable(resolver):
            convention = resolver(symbol)
            if not isinstance(convention, QuoteConvention):
                raise TypeError("quote_convention must return QuoteConvention")
            return convention
        currency = self._fx_provider.quote_currency(symbol)
        convention = normalize_quote_convention(currency)
        if convention.native_price_scale != 1.0:
            raise TWDValuationError(
                "a quote provider returning minor units must implement quote_convention"
            )
        return convention


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


def _scale_native_prices(series: pd.Series, scale: float) -> pd.Series:
    if not isinstance(scale, (int, float)) or scale <= 0:
        raise TWDValuationError("native quote-unit scale must be positive")
    scale = float(scale)
    scaled = series.astype(float).copy() * scale
    attrs = dict(series.attrs)
    for key in _SCALED_COMPONENT_ATTRS:
        component = attrs.get(key)
        if isinstance(component, pd.Series):
            attrs[key] = component.astype(float).copy() * scale
    attrs["raw_quote_unit_scale"] = scale
    scaled.attrs = attrs
    return scaled


def _verify_component_alignment(
    valuation: TWDValuation,
    components: TWDReturnComponents,
) -> None:
    if not valuation.daily_returns.index.equals(components.total_returns.index):
        raise TWDValuationError("TWD return components do not use the valuation calendar")
    difference = (
        valuation.daily_returns.astype(float) - components.total_returns.astype(float)
    ).abs()
    if not difference.empty and float(difference.max()) > _COMPONENT_ALIGNMENT_TOLERANCE:
        raise TWDValuationError("TWD return components do not reproduce adjusted-close returns")
    if not np.isfinite(components.price_returns.to_numpy(dtype=float)).all():
        raise TWDValuationError("TWD price return components contain non-finite values")


def _fx_audit(
    currency: str,
    levels: FXLevels | None,
    convention: QuoteConvention,
) -> dict[str, Any]:
    quote_metadata = {
        "raw_quote_currency": convention.raw_currency,
        "normalized_quote_currency": convention.currency,
        "native_price_scale": convention.native_price_scale,
    }
    if currency == "TWD":
        return {
            **quote_metadata,
            "source_currency": "TWD",
            "target_currency": "TWD",
            "method": "identity",
            "tickers": [],
            "correction_count": 0,
            "future_assisted_correction_count": 0,
            "non_causal_repair_present": False,
            "unresolved_count": 0,
            "material_transition_count": 0,
        }
    if levels is None:
        raise AssertionError("non-TWD asset requires FX levels before valuation")
    return {
        **quote_metadata,
        "source_currency": levels.source_currency,
        "target_currency": levels.target_currency,
        "method": levels.method,
        "tickers": list(levels.tickers),
        "correction_count": levels.correction_count,
        "future_assisted_correction_count": levels.future_assisted_correction_count,
        "non_causal_repair_present": levels.future_assisted_correction_count > 0,
        "unresolved_count": levels.unresolved_count,
        "material_transition_count": levels.material_transition_count,
    }
