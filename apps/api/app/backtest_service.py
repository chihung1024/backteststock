"""Framework-neutral, full-period portfolio backtests valued in TWD.

This is the shared calculation boundary for the unified product.  It consumes
only the audited TWD price histories made by :mod:`apps.api.app.data` and
therefore prevents a caller from accidentally computing a portfolio, benchmark,
or risk metric in its native quote currency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from api.metrics import calculate_metrics, reproducibility_metadata, series_fingerprint
from apps.api.app.data.history_service import (
    HistoryFailure,
    PartialTWDHistories,
    TWDAssetHistory,
    TWDHistoryService,
    normalize_symbol,
)
from apps.api.app.data.twd_valuation import (
    TWD_VALUATION_CONTRACT_VERSION,
    VALUATION_CURRENCY,
)

TRADING_DAYS_PER_YEAR = 252
EPSILON = 1e-12
ALLOWED_REBALANCING_PERIODS = frozenset(
    {"never", "annually", "quarterly", "monthly"}
)
TWD_PORTFOLIO_CALENDAR_POLICY = (
    "union_twd_valuation_calendar_forward_fill_after_observation_complete_case-v1"
)


@dataclass(frozen=True, slots=True)
class PortfolioSpec:
    """One already-validated portfolio request.

    ``weights`` are decimal fractions and must sum to one.  Keeping validation
    here as well as at the HTTP boundary makes the service safe to reuse by a
    FastAPI route, a worker, and future batch jobs.
    """

    name: str
    tickers: tuple[str, ...]
    weights: tuple[float, ...]
    rebalancing_period: str = "never"


@dataclass(frozen=True, slots=True)
class PortfolioFailure:
    """An explicit portfolio-level result when its required data is unavailable."""

    name: str
    stage: str
    detail: str
    symbols: tuple[str, ...]
    retryable: bool


@dataclass(slots=True)
class TWDBacktestBatch:
    """Successful portfolios are retained even when sibling portfolios fail."""

    requested: tuple[str, ...]
    results: list[dict[str, Any]]
    failures: list[PortfolioFailure]
    benchmark: dict[str, Any] | None
    benchmark_failure: HistoryFailure | None
    histories: PartialTWDHistories


class TWDPortfolioBacktestService:
    """Run only full-period portfolio backtests on daily TWD adjusted levels.

    The calendar intentionally takes the union of every selected asset's TWD
    valuation calendar.  Each asset carries its *previous observed* TWD value
    forward on another market's trading or FX-only day.  Initial observations
    are never filled backward, and the shared calendar begins only after every
    selected asset has a real history.  Thus currency movement remains visible
    on days a local equity market is closed without introducing look-ahead.
    """

    def __init__(self, *, history_service: TWDHistoryService | None = None) -> None:
        self._history_service = history_service or TWDHistoryService()

    def run(
        self,
        portfolios: Iterable[PortfolioSpec],
        *,
        start: date,
        end: date,
        initial_amount: float,
        benchmark: str | None = None,
        risk_free_rate: float = 0.0,
    ) -> TWDBacktestBatch:
        """Fetch and calculate a batch without silently discarding failures."""

        specs = tuple(_normalize_spec(spec) for spec in portfolios)
        _validate_initial_amount(initial_amount)
        _validate_risk_free_rate(risk_free_rate)
        if not specs:
            raise ValueError("at least one portfolio is required")

        benchmark_symbol = normalize_symbol(benchmark) if benchmark else None
        requested = _deduplicate_symbols(
            ticker for spec in specs for ticker in spec.tickers
        )
        if benchmark_symbol:
            requested = _deduplicate_symbols([*requested, benchmark_symbol])

        histories = self._history_service.histories_partial(
            list(requested), start, end
        )
        benchmark_history = (
            histories.histories.get(benchmark_symbol) if benchmark_symbol else None
        )
        benchmark_failure = (
            histories.failures.get(benchmark_symbol) if benchmark_symbol else None
        )
        benchmark_result = (
            _serialize_benchmark(benchmark_history, initial_amount, risk_free_rate)
            if benchmark_history is not None
            else None
        )

        results: list[dict[str, Any]] = []
        failures: list[PortfolioFailure] = []
        for spec in specs:
            missing = tuple(
                ticker for ticker in spec.tickers if ticker not in histories.histories
            )
            if missing:
                failures.append(_missing_data_failure(spec, missing, histories.failures))
                continue

            required = [*spec.tickers]
            if benchmark_history is not None and benchmark_symbol is not None:
                required.append(benchmark_symbol)
            prices = align_twd_price_frame(histories.histories, required)
            if len(prices) < 2:
                failures.append(
                    PortfolioFailure(
                        name=spec.name,
                        stage="calendar",
                        detail=(
                            "selected TWD histories have fewer than two shared "
                            "valuation dates without backward fill"
                        ),
                        symbols=tuple(required),
                        retryable=False,
                    )
                )
                continue

            portfolio_values = simulate_twd_portfolio(
                prices.loc[:, list(spec.tickers)],
                weights=spec.weights,
                initial_amount=initial_amount,
                rebalancing_period=spec.rebalancing_period,
            )
            benchmark_values = (
                _normalized_value_history(prices[benchmark_symbol], initial_amount)
                if benchmark_history is not None and benchmark_symbol is not None
                else None
            )
            results.append(
                _serialize_portfolio(
                    spec,
                    portfolio_values,
                    benchmark_values,
                    histories.histories,
                    risk_free_rate,
                    benchmark_available=benchmark_history is not None,
                )
            )

        return TWDBacktestBatch(
            requested=requested,
            results=results,
            failures=failures,
            benchmark=benchmark_result,
            benchmark_failure=benchmark_failure,
            histories=histories,
        )


def align_twd_price_frame(
    histories: Mapping[str, TWDAssetHistory], symbols: Iterable[str]
) -> pd.DataFrame:
    """Return an auditable, common TWD valuation calendar for ``symbols``.

    The input individual valuations already include each non-TWD asset's own
    FX-only dates.  This second union is needed for mixed exchanges: for
    example, a Taiwan equity carries forward over a U.S. FX trading day while a
    U.S. equity's TWD value changes.  The final complete case trims only the
    opening period where a symbol has not yet observed any real price.
    """

    ordered_symbols = _deduplicate_symbols(symbols)
    if not ordered_symbols:
        return pd.DataFrame()
    missing = [symbol for symbol in ordered_symbols if symbol not in histories]
    if missing:
        raise ValueError("cannot align missing TWD histories: " + ", ".join(missing))

    calendar = pd.DatetimeIndex([])
    for symbol in ordered_symbols:
        calendar = calendar.union(histories[symbol].adjusted_close_twd.index)
    calendar = calendar.sort_values().unique()
    frame = pd.DataFrame(index=calendar)
    for symbol in ordered_symbols:
        # Forward fill only.  A pre-listing/pre-data opening remains unavailable.
        frame[symbol] = histories[symbol].adjusted_close_twd.reindex(calendar).ffill()
    return frame.loc[:, ordered_symbols].dropna(how="any").astype(float)


def simulate_twd_portfolio(
    prices: pd.DataFrame,
    *,
    weights: Iterable[float],
    initial_amount: float,
    rebalancing_period: str,
) -> pd.Series:
    """Simulate holdings directly from common-calendar TWD price levels."""

    if rebalancing_period not in ALLOWED_REBALANCING_PERIODS:
        raise ValueError("unsupported rebalancing period")
    values = prices.dropna(how="any").astype(float)
    if values.empty or (values <= 0.0).any().any():
        raise ValueError("portfolio requires finite positive TWD price levels")
    normalized_weights = np.asarray(tuple(weights), dtype=float)
    if len(normalized_weights) != len(values.columns):
        raise ValueError("weight count must equal asset count")
    if (
        not np.isfinite(normalized_weights).all()
        or (normalized_weights <= 0.0).any()
        or not math.isclose(float(normalized_weights.sum()), 1.0, abs_tol=1e-8)
    ):
        raise ValueError("weights must be finite positive fractions summing to one")

    values_index = values.index
    history = pd.Series(index=values_index, dtype=float, name="value")
    shares = (initial_amount * normalized_weights) / values.iloc[0].to_numpy()
    history.iloc[0] = initial_amount
    rebalance_dates = _rebalancing_dates(values_index, rebalancing_period)
    for position in range(1, len(values)):
        if values_index[position] in rebalance_dates:
            previous_prices = values.iloc[position - 1].to_numpy()
            previous_value = float(np.dot(shares, previous_prices))
            shares = (previous_value * normalized_weights) / previous_prices
        current_prices = values.iloc[position].to_numpy()
        current_value = float(np.dot(shares, current_prices))
        history.iloc[position] = current_value
    return history


def _normalize_spec(spec: PortfolioSpec) -> PortfolioSpec:
    if not isinstance(spec, PortfolioSpec):
        raise TypeError("portfolios must contain PortfolioSpec values")
    name = str(spec.name or "").strip()
    tickers = tuple(normalize_symbol(ticker) for ticker in spec.tickers)
    weights = tuple(float(weight) for weight in spec.weights)
    if not name:
        raise ValueError("portfolio name is required")
    if not tickers or len(tickers) != len(weights):
        raise ValueError("portfolio tickers and weights must have the same non-zero length")
    if len(set(tickers)) != len(tickers):
        raise ValueError("portfolio tickers must be unique")
    if spec.rebalancing_period not in ALLOWED_REBALANCING_PERIODS:
        raise ValueError("unsupported rebalancing period")
    if (
        not np.isfinite(weights).all()
        or any(weight <= 0.0 for weight in weights)
        or not math.isclose(sum(weights), 1.0, abs_tol=1e-8)
    ):
        raise ValueError("portfolio weights must be positive fractions summing to one")
    return PortfolioSpec(
        name=name,
        tickers=tickers,
        weights=weights,
        rebalancing_period=spec.rebalancing_period,
    )


def _validate_initial_amount(value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("initial amount must be finite and positive")


def _validate_risk_free_rate(value: float) -> None:
    if not math.isfinite(value) or value <= -1.0:
        raise ValueError("risk-free rate must be finite and greater than -1")


def _deduplicate_symbols(symbols: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in symbols:
        symbol = normalize_symbol(raw)
        if symbol and symbol not in seen:
            seen.add(symbol)
            result.append(symbol)
    return tuple(result)


def _rebalancing_dates(index: pd.DatetimeIndex, period: str) -> set[pd.Timestamp]:
    if period == "never":
        return set()
    frequency = {"annually": "Y", "quarterly": "Q", "monthly": "M"}[period]
    first_dates = pd.Series(index=index, data=index).groupby(
        index.to_period(frequency)
    ).head(1)
    return set(first_dates.iloc[1:].tolist())


def _normalized_value_history(prices: pd.Series, initial_amount: float) -> pd.Series:
    if prices.empty or prices.iloc[0] <= EPSILON:
        raise ValueError("benchmark requires a positive opening TWD price")
    return (prices / float(prices.iloc[0]) * initial_amount).rename("value")


def _serialize_portfolio(
    spec: PortfolioSpec,
    values: pd.Series,
    benchmark_values: pd.Series | None,
    histories: Mapping[str, TWDAssetHistory],
    risk_free_rate: float,
    *,
    benchmark_available: bool,
) -> dict[str, Any]:
    asset_quote_currencies = {
        ticker: histories[ticker].quote_currency for ticker in spec.tickers
    }
    asset_fx_audits = {
        ticker: histories[ticker].fx_audit for ticker in spec.tickers
    }
    asset_corporate_action_audits = {
        ticker: histories[ticker].corporate_action_audit for ticker in spec.tickers
    }
    asset_native_price_fingerprints = {
        ticker: series_fingerprint(histories[ticker].native_adjusted_close)
        for ticker in spec.tickers
    }
    asset_fx_price_fingerprints = {
        ticker: series_fingerprint(histories[ticker].fx_to_twd)
        for ticker in spec.tickers
    }
    metrics = calculate_metrics(values, benchmark_values, risk_free_rate=risk_free_rate)
    metadata = reproducibility_metadata(
        risk_free_rate=risk_free_rate,
        extra={
            "valuation_currency": VALUATION_CURRENCY,
            "twd_valuation_contract_version": TWD_VALUATION_CONTRACT_VERSION,
            "twd_portfolio_calendar_policy": TWD_PORTFOLIO_CALENDAR_POLICY,
            "rebalancing_execution": "previous_close_before_period_start",
            "asset_quote_currencies": asset_quote_currencies,
            "asset_fx_audits": asset_fx_audits,
            "asset_corporate_action_audits": asset_corporate_action_audits,
            "asset_native_price_fingerprints": asset_native_price_fingerprints,
            "asset_fx_price_fingerprints": asset_fx_price_fingerprints,
        },
    )
    return {
        "name": spec.name,
        **metrics,
        "return_basis": metadata["return_basis"],
        "corporate_action_policy_version": metadata[
            "corporate_action_policy_version"
        ],
        "corporate_action_status": _portfolio_action_status(
            [histories[ticker].corporate_action_audit for ticker in spec.tickers]
        ),
        "portfolio_value_fingerprint": series_fingerprint(values),
        "valuationCurrency": VALUATION_CURRENCY,
        "twdValuationContractVersion": TWD_VALUATION_CONTRACT_VERSION,
        "calendarPolicy": TWD_PORTFOLIO_CALENDAR_POLICY,
        "assetQuoteCurrencies": asset_quote_currencies,
        "assetFxAudits": asset_fx_audits,
        "assetCorporateActionAudits": asset_corporate_action_audits,
        "assetNativePriceFingerprints": asset_native_price_fingerprints,
        "assetFxPriceFingerprints": asset_fx_price_fingerprints,
        "benchmarkAvailable": benchmark_available,
        "rebalancingPeriod": spec.rebalancing_period,
        "rebalancing_execution": "previous_close_before_period_start",
        "metadata": metadata,
        "portfolioHistory": [
            {"date": timestamp.strftime("%Y-%m-%d"), "value": float(value)}
            for timestamp, value in values.items()
        ],
    }


def _serialize_benchmark(
    history: TWDAssetHistory,
    initial_amount: float,
    risk_free_rate: float,
) -> dict[str, Any]:
    values = _normalized_value_history(history.adjusted_close_twd, initial_amount)
    metrics = calculate_metrics(values, risk_free_rate=risk_free_rate)
    metadata = reproducibility_metadata(risk_free_rate=risk_free_rate)
    return {
        "name": history.symbol,
        **metrics,
        "beta": 1.0,
        "alpha": 0.0,
        "return_basis": metadata["return_basis"],
        "corporate_action_policy_version": metadata["corporate_action_policy_version"],
        "corporate_action_status": _portfolio_action_status(
            [history.corporate_action_audit]
        ),
        "portfolio_value_fingerprint": series_fingerprint(values),
        "valuationCurrency": VALUATION_CURRENCY,
        "twdValuationContractVersion": TWD_VALUATION_CONTRACT_VERSION,
        "quoteCurrency": history.quote_currency,
        "fxAudit": history.fx_audit,
        "corporateActionAudit": history.corporate_action_audit,
        "nativePriceFingerprint": series_fingerprint(history.native_adjusted_close),
        "fxPriceFingerprint": series_fingerprint(history.fx_to_twd),
        "portfolioHistory": [
            {"date": timestamp.strftime("%Y-%m-%d"), "value": float(value)}
            for timestamp, value in values.items()
        ],
    }


def _missing_data_failure(
    spec: PortfolioSpec,
    missing: tuple[str, ...],
    failures: Mapping[str, HistoryFailure],
) -> PortfolioFailure:
    failed = [failures[symbol] for symbol in missing if symbol in failures]
    detail = "; ".join(
        f"{failure.symbol}: {failure.stage} - {failure.detail}" for failure in failed
    ) or "one or more required TWD histories were not returned"
    return PortfolioFailure(
        name=spec.name,
        stage="market_data",
        detail=detail,
        symbols=missing,
        retryable=any(failure.retryable for failure in failed),
    )


def _portfolio_action_status(audits: Iterable[dict[str, Any] | None]) -> str:
    statuses = {
        audit.get("status", "audit_not_recorded")
        for audit in audits
        if isinstance(audit, dict)
    }
    if "review_required" in statuses:
        return "review_required"
    if statuses & {"adjusted_close_unverifiable", "insufficient_audit_history"}:
        return "audit_incomplete"
    if statuses == {"verified_standard_actions"}:
        return "verified_standard_actions"
    return "audit_not_recorded"
