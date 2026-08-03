"""Self-owned Portfolio v3 preflight and backtest orchestration."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
import yfinance as yf

from api.metrics import METRIC_DEFINITION_VERSION, series_fingerprint
from apps.api.app.data.history_service import (
    PartialTWDHistories,
    TWDHistoryService,
    normalize_symbol,
)
from apps.api.app.data.return_components import RETURN_COMPONENTS_CONTRACT_VERSION
from apps.api.app.data.twd_valuation import TWD_VALUATION_CONTRACT_VERSION
from apps.api.app.portfolio.analytics import (
    PORTFOLIO_ANALYTICS_CONTRACT_VERSION,
    STYLE_PROXIES,
    constrained_style_analysis,
    factor_fx_regression,
    inflation_adjusted_metrics,
    regime_analysis,
)
from apps.api.app.portfolio.analytics_data import FrenchFactorProvider, FredProvider
from apps.api.app.portfolio.api_models import (
    PORTFOLIO_API_CONTRACT_VERSION,
    PORTFOLIO_API_SCHEMA_VERSION,
    AssetPreflightResult,
    AssetSearchResult,
    BacktestResponse,
    PortfolioPreflightResult,
    PortfolioRequest,
    PreflightResponse,
    RegimeType,
)
from apps.api.app.portfolio.ledger import (
    PORTFOLIO_LEDGER_CONTRACT_VERSION,
    align_portfolio_components,
    simulate_portfolio_ledger,
)
from apps.api.app.portfolio.metrics import (
    PORTFOLIO_METRIC_CONTEXT_VERSION,
    compute_metric_report,
)
from apps.api.app.portfolio.models import PortfolioSpec, SimulationConfig
from apps.api.app.portfolio.service import (
    PORTFOLIO_SERVICE_CONTRACT_VERSION,
    PortfolioLedgerService,
)

logger = logging.getLogger(__name__)


class PortfolioAPIService:
    def __init__(
        self,
        *,
        history_service: TWDHistoryService | None = None,
        factor_provider: FrenchFactorProvider | None = None,
        fred_provider: FredProvider | None = None,
    ) -> None:
        self.history_service = history_service or TWDHistoryService()
        self.factor_provider = factor_provider or FrenchFactorProvider()
        self.fred_provider = fred_provider or FredProvider()
        self.ledger_service = PortfolioLedgerService()

    def search_assets(self, query: str, limit: int = 8) -> list[AssetSearchResult]:
        value = str(query or "").strip()
        if not value:
            return []
        limit = min(max(int(limit), 1), 12)
        results: list[AssetSearchResult] = []
        seen: set[str] = set()
        if value.isdigit() and 4 <= len(value) <= 6:
            for suffix, exchange in ((".TW", "Taiwan"), (".TWO", "Taipei Exchange")):
                symbol = f"{value}{suffix}"
                results.append(
                    AssetSearchResult(
                        symbol=symbol,
                        name=f"{value} ({exchange})",
                        exchange=exchange,
                        quote_type="EQUITY",
                        currency="TWD",
                    )
                )
                seen.add(symbol)
        try:
            quotes = yf.Search(value, max_results=max(limit, 8), news_count=0).quotes or []
        except Exception as exc:  # noqa: BLE001 - search is best effort
            logger.warning("Portfolio v3 ticker search failed for %s: %s", value, exc)
            quotes = []
        for quote in quotes:
            symbol = str(quote.get("symbol") or "").strip().upper()
            if not symbol or symbol in seen:
                continue
            quote_type = str(quote.get("quoteType") or "").strip().upper()
            if quote_type and quote_type not in {"EQUITY", "ETF", "MUTUALFUND", "INDEX"}:
                continue
            results.append(
                AssetSearchResult(
                    symbol=symbol,
                    name=str(quote.get("longname") or quote.get("shortname") or symbol),
                    exchange=quote.get("exchDisp") or quote.get("exchange"),
                    quote_type=quote_type or None,
                    currency=quote.get("currency"),
                )
            )
            seen.add(symbol)
            if len(results) >= limit:
                break
        return results[:limit]

    def preflight(self, request: PortfolioRequest) -> PreflightResponse:
        request_id = str(uuid4())
        effective_end = request.effective_end_date()
        portfolio_symbols = _portfolio_symbols(request)
        requested = list(request.requested_symbols)
        analysis_symbols = (
            list(STYLE_PROXIES.values()) if request.analytics.style_analysis else []
        )
        all_symbols = _deduplicate([*requested, *analysis_symbols])
        batch = self.history_service.histories_partial(
            all_symbols,
            request.start_date,
            effective_end,
        )
        portfolios = [
            self._portfolio_preflight(portfolio.to_spec(), batch)
            for portfolio in request.portfolios
        ]
        warnings = self._request_warnings(request, effective_end)
        if request.analytics.factor_analysis:
            warnings.append(
                "Factor data are fetched from the Kenneth French Data Library only during the backtest."
            )
        if self._needs_fred(request) and not self.fred_provider.available:
            warnings.append(
                "FRED-dependent analytics are unavailable until BACKTEST_FRED_API_KEY or FRED_API_KEY is configured."
            )
        return PreflightResponse(
            request_id=request_id,
            generated_at=datetime.now(UTC).isoformat(),
            contract_version=PORTFOLIO_API_CONTRACT_VERSION,
            schema_version=PORTFOLIO_API_SCHEMA_VERSION,
            base_currency="TWD",
            requested_start=request.start_date.isoformat(),
            requested_end=request.end_date.isoformat(),
            effective_end=effective_end.isoformat(),
            assets=[self._asset_preflight(symbol, batch) for symbol in portfolio_symbols],
            portfolios=portfolios,
            benchmark=(
                self._asset_preflight(request.benchmark, batch)
                if request.benchmark
                else None
            ),
            analysis_dependencies=[
                self._asset_preflight(symbol, batch) for symbol in analysis_symbols
            ],
            warnings=list(dict.fromkeys(warnings)),
        )

    def backtest(self, request: PortfolioRequest) -> BacktestResponse:
        started = time.perf_counter()
        request_id = str(uuid4())
        effective_end = request.effective_end_date()
        portfolio_symbols = _portfolio_symbols(request)
        requested = list(request.requested_symbols)
        analysis_symbols = (
            list(STYLE_PROXIES.values()) if request.analytics.style_analysis else []
        )
        all_symbols = _deduplicate([*requested, *analysis_symbols])

        market_started = time.perf_counter()
        histories = self.history_service.histories_partial(
            all_symbols,
            request.start_date,
            effective_end,
        )
        market_ms = (time.perf_counter() - market_started) * 1_000.0

        compute_started = time.perf_counter()
        config = request.to_simulation_config()
        batch = self.ledger_service.run(
            request.to_specs(),
            histories.histories,
            config,
            benchmark=request.benchmark,
            history_failures=histories.failures,
        )
        factors, cpi, real_gdp, global_warnings = self._load_analysis_data(
            request,
            effective_end,
        )
        benchmark_returns = (
            histories.histories[request.benchmark].daily_returns
            if request.benchmark and request.benchmark in histories.histories
            else None
        )

        results: list[dict[str, Any]] = []
        for run in batch.results:
            analytics, analytics_warnings = self._analytics_for_result(
                request,
                run.ledger,
                histories,
                benchmark_returns,
                factors=factors,
                cpi=cpi,
                real_gdp=real_gdp,
            )
            results.append(
                self._serialize_run(
                    run.ledger,
                    run.metrics,
                    request,
                    analytics=analytics,
                    warnings=[
                        *run.warnings,
                        *global_warnings,
                        *analytics_warnings,
                    ],
                )
            )

        benchmark_payload = self._benchmark_payload(request, histories, config)
        compute_ms = (time.perf_counter() - compute_started) * 1_000.0
        warnings = [
            *self._request_warnings(request, effective_end),
            *batch.warnings,
            *global_warnings,
        ]
        if not results:
            warnings.append("No requested portfolio completed successfully.")
        total_ms = (time.perf_counter() - started) * 1_000.0
        return BacktestResponse(
            request_id=request_id,
            generated_at=datetime.now(UTC).isoformat(),
            contract_version=PORTFOLIO_API_CONTRACT_VERSION,
            schema_version=PORTFOLIO_API_SCHEMA_VERSION,
            base_currency="TWD",
            requested_start=request.start_date.isoformat(),
            requested_end=request.end_date.isoformat(),
            effective_end=effective_end.isoformat(),
            results=results,
            failures=[asdict(failure) for failure in batch.failures],
            assets=[
                self._asset_preflight(symbol, histories) for symbol in portfolio_symbols
            ],
            benchmark=benchmark_payload,
            warnings=list(dict.fromkeys(warnings)),
            timing={
                "market_ms": market_ms,
                "compute_ms": compute_ms,
                "total_ms": total_ms,
            },
            reproducibility={
                "api_schema_version": PORTFOLIO_API_SCHEMA_VERSION,
                "ledger_contract_version": PORTFOLIO_LEDGER_CONTRACT_VERSION,
                "metric_context_version": PORTFOLIO_METRIC_CONTEXT_VERSION,
                "service_contract_version": PORTFOLIO_SERVICE_CONTRACT_VERSION,
                "analytics_contract_version": PORTFOLIO_ANALYTICS_CONTRACT_VERSION,
                "metric_definition_version": METRIC_DEFINITION_VERSION,
                "twd_valuation_contract_version": TWD_VALUATION_CONTRACT_VERSION,
                "return_components_contract_version": RETURN_COMPONENTS_CONTRACT_VERSION,
                "requested_symbols": requested,
                "resolved_symbols": list(histories.histories),
                "failed_symbols": list(histories.failures),
            },
        )

    def _load_analysis_data(
        self,
        request: PortfolioRequest,
        effective_end: date,
    ) -> tuple[pd.DataFrame | None, pd.Series | None, pd.Series | None, list[str]]:
        factors: pd.DataFrame | None = None
        cpi: pd.Series | None = None
        real_gdp: pd.Series | None = None
        warnings: list[str] = []
        if request.analytics.factor_analysis:
            try:
                factors = self.factor_provider.monthly_factors()
            except Exception as exc:  # noqa: BLE001 - optional external analysis
                warnings.append(f"factor analysis unavailable: {exc}")
        if not self._needs_fred(request):
            return factors, cpi, real_gdp, warnings
        if not self.fred_provider.available:
            warnings.append(
                "FRED-dependent analytics unavailable: FRED API key is not configured"
            )
            return factors, cpi, real_gdp, warnings

        macro_start = request.start_date - timedelta(days=500)
        try:
            cpi = self.fred_provider.series("CPIAUCSL", macro_start, effective_end)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"CPI analysis unavailable: {exc}")
        if request.analytics.regime == RegimeType.BUSINESS_CYCLE:
            try:
                real_gdp = self.fred_provider.series("GDPC1", macro_start, effective_end)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"business-cycle analysis unavailable: {exc}")
        return factors, cpi, real_gdp, warnings

    def _analytics_for_result(
        self,
        request: PortfolioRequest,
        ledger: Any,
        histories: PartialTWDHistories,
        benchmark_returns: pd.Series | None,
        *,
        factors: pd.DataFrame | None,
        cpi: pd.Series | None,
        real_gdp: pd.Series | None,
    ) -> tuple[dict[str, Any], list[str]]:
        output: dict[str, Any] = {}
        warnings: list[str] = []
        if request.analytics.factor_analysis and factors is not None:
            try:
                output["factor"] = factor_fx_regression(
                    ledger,
                    histories.histories,
                    factors,
                )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{ledger.name}: factor analysis unavailable: {exc}")
        if request.analytics.style_analysis:
            try:
                output["style"] = constrained_style_analysis(
                    ledger,
                    histories.histories,
                )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{ledger.name}: style analysis unavailable: {exc}")
        if request.analytics.regime != RegimeType.NONE:
            if benchmark_returns is None:
                warnings.append(
                    f"{ledger.name}: regime analysis requires an available benchmark"
                )
            else:
                try:
                    output["regime"] = regime_analysis(
                        ledger,
                        benchmark_returns,
                        request.analytics.regime,
                        cpi=cpi,
                        real_gdp=real_gdp,
                    )
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"{ledger.name}: regime analysis unavailable: {exc}")
        if request.analytics.inflation_adjusted:
            if cpi is None:
                warnings.append(f"{ledger.name}: inflation adjustment unavailable")
            else:
                try:
                    output["inflation_adjusted"] = inflation_adjusted_metrics(ledger, cpi)
                except Exception as exc:  # noqa: BLE001
                    warnings.append(
                        f"{ledger.name}: inflation adjustment unavailable: {exc}"
                    )
        return output, warnings

    def _benchmark_payload(
        self,
        request: PortfolioRequest,
        histories: PartialTWDHistories,
        config: SimulationConfig,
    ) -> dict[str, Any] | None:
        if not request.benchmark or request.benchmark not in histories.histories:
            return None
        spec = PortfolioSpec.from_weights(
            f"Benchmark · {request.benchmark}",
            {request.benchmark: 1.0},
        )
        benchmark_config = SimulationConfig(
            initial_amount=config.initial_amount,
            reinvest_distributions=True,
            risk_free_rate=config.risk_free_rate,
        )
        ledger = simulate_portfolio_ledger(spec, histories.histories, benchmark_config)
        report = compute_metric_report(ledger, benchmark_config)
        return self._serialize_run(
            ledger,
            report,
            request,
            analytics={},
            warnings=ledger.warnings,
            is_benchmark=True,
        )

    def _serialize_run(
        self,
        ledger: Any,
        report: Any,
        request: PortfolioRequest,
        *,
        analytics: dict[str, Any],
        warnings: list[str] | tuple[str, ...],
        is_benchmark: bool = False,
    ) -> dict[str, Any]:
        frame = pd.DataFrame(
            {
                "value": ledger.equity,
                "return_index": ledger.return_index,
                "daily_return": ledger.daily_returns,
                "external_flow": ledger.external_flows,
                "income": ledger.income,
                "cumulative_income": ledger.cumulative_income,
                "cash": ledger.cash,
                "debt": ledger.debt,
                "gross_exposure": ledger.gross_exposure,
            }
        )
        sampled = _sample_frame(frame, request.output_frequency.value)
        payload: dict[str, Any] = {
            "name": ledger.name,
            "display_name": (
                ledger.name
                if is_benchmark
                else _display_name(ledger.name, ledger.target_allocation)
            ),
            "metrics": report.metrics,
            "xirr": asdict(report.xirr),
            "tail_risk": asdict(report.tail_risk),
            "drawdown_events": [asdict(event) for event in report.drawdown_events],
            "annual_returns": [asdict(item) for item in report.annual_returns],
            "monthly_returns": [asdict(item) for item in report.monthly_returns],
            "target_allocation": ledger.target_allocation,
            "final_allocation": ledger.final_allocation,
            "series": [
                {
                    "date": timestamp.date().isoformat(),
                    **{
                        column: _finite_or_none(value)
                        for column, value in row.items()
                    },
                }
                for timestamp, row in sampled.iterrows()
            ],
            "analytics": analytics,
            "warnings": list(dict.fromkeys(warnings)),
            "metadata": report.metadata,
        }
        if request.include_events:
            payload["events"] = [asdict(event) for event in ledger.events]
        if request.include_allocation_history:
            payload["allocation_history"] = [
                {
                    "date": timestamp.date().isoformat(),
                    "allocations": {
                        symbol: float(value) for symbol, value in row.items()
                    },
                }
                for timestamp, row in ledger.allocation_history.iterrows()
            ]
        return payload

    def _asset_preflight(
        self,
        symbol: str,
        batch: PartialTWDHistories,
    ) -> AssetPreflightResult:
        normalized = normalize_symbol(symbol)
        history = batch.histories.get(normalized)
        if history is None:
            failure = batch.failures.get(normalized)
            return AssetPreflightResult(
                symbol=normalized,
                status="failed",
                stage=failure.stage if failure else "history",
                detail=failure.detail if failure else "no usable audited TWD history",
                retryable=failure.retryable if failure else False,
            )
        components = history.return_components
        return AssetPreflightResult(
            symbol=normalized,
            status="ready",
            quote_currency=history.quote_currency,
            effective_start=history.adjusted_close_twd.index[0].date().isoformat(),
            effective_end=history.adjusted_close_twd.index[-1].date().isoformat(),
            observations=int(len(history.adjusted_close_twd)),
            corporate_action_audit=history.corporate_action_audit,
            fx_audit=history.fx_audit,
            return_component_audit=(components.audit if components is not None else None),
            fingerprints={
                "native_adjusted_close": series_fingerprint(
                    history.native_adjusted_close
                ),
                "fx_to_twd": series_fingerprint(history.fx_to_twd),
                "adjusted_close_twd": series_fingerprint(history.adjusted_close_twd),
            },
        )

    def _portfolio_preflight(
        self,
        portfolio: PortfolioSpec,
        batch: PartialTWDHistories,
    ) -> PortfolioPreflightResult:
        missing = [symbol for symbol in portfolio.symbols if symbol not in batch.histories]
        if missing:
            return PortfolioPreflightResult(
                name=portfolio.name,
                status="failed",
                symbols=list(portfolio.symbols),
                missing_symbols=missing,
                detail="missing audited TWD history",
            )
        try:
            aligned = align_portfolio_components(batch.histories, portfolio.symbols)
        except ValueError as exc:
            return PortfolioPreflightResult(
                name=portfolio.name,
                status="failed",
                symbols=list(portfolio.symbols),
                detail=str(exc),
            )
        return PortfolioPreflightResult(
            name=portfolio.name,
            status="ready",
            symbols=list(portfolio.symbols),
            effective_start=aligned.start.date().isoformat(),
            effective_end=aligned.end.date().isoformat(),
            observations=int(len(aligned.total_returns)),
        )

    @staticmethod
    def _request_warnings(
        request: PortfolioRequest,
        effective_end: date,
    ) -> list[str]:
        if effective_end == request.end_date:
            return []
        return [
            f"Excluded incomplete year-to-date data; effective end moved to {effective_end.isoformat()}."
        ]

    @staticmethod
    def _needs_fred(request: PortfolioRequest) -> bool:
        return request.analytics.inflation_adjusted or request.analytics.regime in {
            RegimeType.INFLATION,
            RegimeType.BUSINESS_CYCLE,
        }


def _portfolio_symbols(request: PortfolioRequest) -> list[str]:
    return _deduplicate(
        [asset.symbol for portfolio in request.portfolios for asset in portfolio.assets]
    )


def _deduplicate(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = normalize_symbol(raw)
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _sample_frame(frame: pd.DataFrame, frequency: str) -> pd.DataFrame:
    if frequency == "daily":
        return frame
    sampled = frame.resample("W-FRI" if frequency == "weekly" else "ME").last()
    sampled = sampled.dropna(how="all")
    combined = pd.concat([frame.iloc[[0, -1]], sampled]).sort_index()
    return combined.loc[~combined.index.duplicated(keep="last")]


def _finite_or_none(value: Any) -> float | None:
    number = float(value)
    return number if np.isfinite(number) else None


def _display_name(name: str, allocation: dict[str, float]) -> str:
    largest = sorted(allocation.items(), key=lambda item: item[1], reverse=True)[:3]
    suffix = " · ".join(
        f"{symbol} {weight * 100.0:.2f}%" for symbol, weight in largest
    )
    return f"{name} · {suffix}" if suffix else name
