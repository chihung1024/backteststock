"""Yahoo quote-currency and FX-level adapter for the unified TWD contract."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from apps.api.app.data.fx_price_quality import reconcile_ohlc_levels
from apps.api.app.data.twd_valuation import VALUATION_CURRENCY, TWDValuationError

logger = logging.getLogger(__name__)

_MINOR_QUOTE_UNITS = {
    # Yahoo uses mixed-case ``GBp`` for London prices in pence. ``GBX`` is the
    # ISO-style code for the same unit.  Detect ``GBp`` before upper-casing so
    # it cannot be confused with a true GBP quote.
    "GBp": ("GBP", 0.01),
    "GBX": ("GBP", 0.01),
    "GBx": ("GBP", 0.01),
    # South African cents and Israeli agorot are likewise 1/100 major unit.
    "ZAc": ("ZAR", 0.01),
    "ZAC": ("ZAR", 0.01),
    "ILA": ("ILS", 0.01),
}
_FX_LOOKBACK_DAYS = 10
_FX_LOOKAHEAD_DAYS = 1
_MAX_CURRENCY_ATTEMPTS = 2
_MATERIAL_FX_TRANSITION = 1.8


class FXDownloadError(RuntimeError):
    """Raised when a verified FX series cannot be obtained from finite sources."""


@dataclass(frozen=True, slots=True)
class QuoteConvention:
    """Yahoo quote metadata normalized to a major currency and price scale."""

    raw_currency: str
    currency: str
    native_price_scale: float


@dataclass(frozen=True, slots=True)
class FXLevels:
    """A normalized quote-currency-to-target-currency daily FX series."""

    source_currency: str
    target_currency: str
    levels: pd.Series
    method: str
    tickers: tuple[str, ...]
    correction_count: int
    unresolved_count: int
    material_transition_count: int
    candidate_priority: int = 0

    @property
    def quality_score(self) -> tuple[int, int, int, int, int]:
        """Lower is better; use a direct clean path when quality is otherwise equal."""

        method_penalty = 1 if self.method == "usd_triangulation" else 0
        return (
            self.unresolved_count,
            self.material_transition_count,
            self.correction_count,
            method_penalty,
            self.candidate_priority,
        )


class YahooFXProvider:
    """Resolve actual Yahoo quote currencies and trend-correct daily FX levels.

    FX symbols are tried a finite number of times: the normal direct quote, an
    inverse quote, Yahoo's legacy USD aliases, then (for a non-USD currency) a
    source→USD→TWD triangulation.  All candidates are normalized before their
    quality is compared.  The provider never turns a later rate into an earlier
    one; calendar alignment is intentionally left to ``value_adjusted_close_in_twd``.
    """

    def __init__(self) -> None:
        self._quote_cache: dict[str, QuoteConvention] = {}
        self._fx_cache: dict[tuple[str, str, str, str], FXLevels] = {}
        self._lock = threading.RLock()

    def quote_currency(self, symbol: str) -> str:
        """Return the normalized major quote currency for compatibility callers."""

        return self.quote_convention(symbol).currency

    def quote_convention(self, symbol: str) -> QuoteConvention:
        """Return Yahoo's quote currency and any minor-unit price scale."""

        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            raise TWDValuationError("cannot resolve an empty ticker currency")
        with self._lock:
            cached = self._quote_cache.get(normalized_symbol)
        if cached is not None:
            return cached

        errors: list[str] = []
        for _ in range(_MAX_CURRENCY_ATTEMPTS):
            try:
                raw_currency = yf.Ticker(normalized_symbol).fast_info.currency
                convention = normalize_quote_convention(raw_currency)
                with self._lock:
                    self._quote_cache[normalized_symbol] = convention
                return convention
            except Exception as exc:  # noqa: BLE001 - external provider boundary
                errors.append(str(exc))
        detail = errors[-1] if errors else "currency metadata was empty"
        raise FXDownloadError(
            f"unable to verify Yahoo quote currency for {normalized_symbol}: {detail}"
        )

    def fx_to_twd(self, source_currency: str, start: date, end: date) -> FXLevels:
        """Download a source-currency→TWD rate for an inclusive calendar range."""

        return self.levels(source_currency, VALUATION_CURRENCY, start, end)

    def levels(
        self,
        source_currency: str,
        target_currency: str,
        start: date,
        end: date,
    ) -> FXLevels:
        """Return a quality-ranked finite FX source for an inclusive date range."""

        source = normalize_quote_currency(source_currency)
        target = normalize_quote_currency(target_currency)
        if source == target:
            raise TWDValuationError("a same-currency FX series is not required")
        if start > end:
            raise TWDValuationError("FX start date must not be after end date")

        cache_key = (source, target, start.isoformat(), end.isoformat())
        with self._lock:
            cached = self._fx_cache.get(cache_key)
        if cached is not None:
            return _copy_fx_levels(cached)

        candidates: list[FXLevels] = []
        direct = self._best_direct_levels(source, target, start, end)
        if direct is not None:
            candidates.append(direct)

        if source != "USD" and target == VALUATION_CURRENCY:
            source_to_usd = self._best_direct_levels(source, "USD", start, end)
            usd_to_twd = self._best_direct_levels("USD", VALUATION_CURRENCY, start, end)
            if source_to_usd is not None and usd_to_twd is not None:
                candidates.append(
                    _triangulate_via_usd(
                        source_to_usd,
                        usd_to_twd,
                        source_currency=source,
                        target_currency=target,
                    )
                )

        if not candidates:
            raise FXDownloadError(
                f"unable to obtain a verified {source}/{target} Yahoo FX history"
            )
        selected = min(candidates, key=lambda item: item.quality_score)
        with self._lock:
            self._fx_cache[cache_key] = selected
        return _copy_fx_levels(selected)

    def _best_direct_levels(
        self,
        source: str,
        target: str,
        start: date,
        end: date,
    ) -> FXLevels | None:
        candidates: list[FXLevels] = []
        for priority, (ticker, invert) in enumerate(_direct_fx_candidates(source, target)):
            result = self._download_candidate(
                ticker,
                invert=invert,
                source_currency=source,
                target_currency=target,
                start=start,
                end=end,
                priority=priority,
            )
            if result is not None:
                candidates.append(result)
        return min(candidates, key=lambda item: item.quality_score) if candidates else None

    def _download_candidate(
        self,
        ticker: str,
        *,
        invert: bool,
        source_currency: str,
        target_currency: str,
        start: date,
        end: date,
        priority: int,
    ) -> FXLevels | None:
        try:
            raw = yf.download(
                ticker,
                start=(start - timedelta(days=_FX_LOOKBACK_DAYS)).isoformat(),
                end=(end + timedelta(days=_FX_LOOKAHEAD_DAYS)).isoformat(),
                auto_adjust=True,
                actions=False,
                repair=False,
                keepna=True,
                progress=False,
                threads=False,
                timeout=20,
            )
        except Exception as exc:  # noqa: BLE001 - external provider boundary
            logger.info("FX download failed for %s: %s", ticker, exc)
            return None
        if not isinstance(raw, pd.DataFrame) or raw.empty:
            return None

        frame = _ticker_frame(raw, ticker)
        if frame.empty:
            frame = raw
        reconciliation = reconcile_ohlc_levels(frame, invert=invert)
        levels = _levels_for_requested_window(reconciliation.levels, start, end)
        if len(levels) <= 1:
            return None
        return FXLevels(
            source_currency=source_currency,
            target_currency=target_currency,
            levels=levels,
            method="inverse" if invert else "direct",
            tickers=(ticker,),
            correction_count=reconciliation.correction_count,
            unresolved_count=reconciliation.unresolved_count,
            material_transition_count=_material_transition_count(levels),
            candidate_priority=priority,
        )


def normalize_quote_currency(value: object) -> str:
    """Normalize Yahoo currency aliases and reject unknown quote-currency data."""

    return normalize_quote_convention(value).currency


def normalize_quote_convention(value: object) -> QuoteConvention:
    """Preserve Yahoo minor quote units while resolving their major currency."""

    raw_currency = str(value or "").strip()
    minor = _MINOR_QUOTE_UNITS.get(raw_currency)
    if minor is not None:
        currency, native_price_scale = minor
        return QuoteConvention(
            raw_currency=raw_currency,
            currency=currency,
            native_price_scale=native_price_scale,
        )
    currency = raw_currency.upper()
    if len(currency) != 3 or not currency.isalpha():
        raise TWDValuationError(f"Yahoo returned invalid quote currency: {value!r}")
    return QuoteConvention(
        raw_currency=raw_currency,
        currency=currency,
        native_price_scale=1.0,
    )


def _direct_fx_candidates(source: str, target: str) -> tuple[tuple[str, bool], ...]:
    candidates: list[tuple[str, bool]] = [
        (f"{source}{target}=X", False),
        (f"{target}{source}=X", True),
    ]
    # Yahoo's legacy one-currency aliases are sometimes longer lived than the
    # explicit crosses.  These orientations follow Yahoo's historical symbols.
    if source == "USD":
        candidates.insert(0, (f"{target}=X", False))
    elif target == "USD":
        candidates.insert(0, (f"{source}=X", True))
    return tuple(dict.fromkeys(candidates))


def _ticker_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw
    for level in range(raw.columns.nlevels):
        if ticker in set(raw.columns.get_level_values(level)):
            frame = raw.xs(ticker, axis=1, level=level, drop_level=True)
            return frame if isinstance(frame, pd.DataFrame) else frame.to_frame()
    return pd.DataFrame()


def _triangulate_via_usd(
    source_to_usd: FXLevels,
    usd_to_twd: FXLevels,
    *,
    source_currency: str,
    target_currency: str,
) -> FXLevels:
    index = source_to_usd.levels.index.union(usd_to_twd.levels.index).sort_values()
    first = source_to_usd.levels.reindex(index).ffill()
    second = usd_to_twd.levels.reindex(index).ffill()
    usable = first.notna() & second.notna()
    levels = (first.loc[usable] * second.loc[usable]).rename("fx_to_twd")
    if len(levels) <= 1:
        raise FXDownloadError(
            f"{source_currency}/USD and USD/{target_currency} have no usable overlap"
        )
    return FXLevels(
        source_currency=source_currency,
        target_currency=target_currency,
        levels=levels,
        method="usd_triangulation",
        tickers=source_to_usd.tickers + usd_to_twd.tickers,
        correction_count=source_to_usd.correction_count + usd_to_twd.correction_count,
        unresolved_count=source_to_usd.unresolved_count + usd_to_twd.unresolved_count,
        material_transition_count=_material_transition_count(levels),
        candidate_priority=max(
            source_to_usd.candidate_priority,
            usd_to_twd.candidate_priority,
        ),
    )


def _material_transition_count(levels: pd.Series) -> int:
    gross = levels / levels.shift(1)
    material = (gross < 1.0 / _MATERIAL_FX_TRANSITION) | (
        gross > _MATERIAL_FX_TRANSITION
    )
    return int(material.fillna(False).sum())


def _levels_for_requested_window(
    levels: pd.Series, start: date, end: date
) -> pd.Series:
    """Clip downloaded FX output without losing the prior known opening rate.

    Yahoo is deliberately asked for a short lookback so a market holiday at the
    beginning of the requested interval can use the last *past* FX observation.
    Its lookahead, however, is only a download aid and must never appear in the
    returned valuation calendar; otherwise a carried equity price could create a
    post-request TWD return.
    """

    start_timestamp = pd.Timestamp(start)
    end_timestamp = pd.Timestamp(end)
    prior = levels.loc[levels.index < start_timestamp].tail(1)
    requested = levels.loc[
        (levels.index >= start_timestamp) & (levels.index <= end_timestamp)
    ]
    return pd.concat([prior, requested]).loc[lambda item: ~item.index.duplicated(keep="last")]


def _copy_fx_levels(value: FXLevels) -> FXLevels:
    return FXLevels(
        source_currency=value.source_currency,
        target_currency=value.target_currency,
        levels=value.levels.copy(),
        method=value.method,
        tickers=value.tickers,
        correction_count=value.correction_count,
        unresolved_count=value.unresolved_count,
        material_transition_count=value.material_transition_count,
        candidate_priority=value.candidate_priority,
    )
