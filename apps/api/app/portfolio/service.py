"""Partial-success service boundary for the self-owned portfolio ledger."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

import pandas as pd

from apps.api.app.data.history_service import HistoryFailure, TWDAssetHistory
from apps.api.app.data.return_components import total_only_components
from apps.api.app.portfolio.ledger import (
    PortfolioLedger,
    align_portfolio_components,
    simulate_portfolio_ledger,
)
from apps.api.app.portfolio.metrics import PortfolioMetricReport, compute_metric_report
from apps.api.app.portfolio.models import (
    PortfolioFailure,
    PortfolioSpec,
    SimulationConfig,
    validate_portfolio_batch,
)

PORTFOLIO_SERVICE_CONTRACT_VERSION = "portfolio-service-twd-2026-08-11.1"
COMPARISON_WINDOW_POLICY = "common-runnable-portfolios-v1"


@dataclass(frozen=True, slots=True)
class PortfolioRunResult:
    name: str
    ledger: PortfolioLedger
    metrics: PortfolioMetricReport
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioBatchResult:
    results: tuple[PortfolioRunResult, ...]
    failures: tuple[PortfolioFailure, ...]
    benchmark: str | None
    warnings: tuple[str, ...]
    contract_version: str = PORTFOLIO_SERVICE_CONTRACT_VERSION


class PortfolioLedgerService:
    """Run valid sibling portfolios on one comparable window when applicable.

    A single runnable portfolio retains its full internally aligned history. When
    two or more sibling portfolios are runnable, the service first determines
    each portfolio's own valid window, then uses the intersection across every
    runnable sibling. Each ledger is freshly initialized at that common start;
    results are never post-hoc clipped to create the appearance of comparability.
    """

    def run(
        self,
        portfolios: tuple[PortfolioSpec, ...],
        histories: Mapping[str, TWDAssetHistory],
        config: SimulationConfig,
        *,
        benchmark: str | None = None,
        history_failures: Mapping[str, HistoryFailure] | None = None,
    ) -> PortfolioBatchResult:
        validate_portfolio_batch(portfolios)
        normalized_benchmark = _normalize_symbol(benchmark) if benchmark else None
        benchmark_returns: pd.Series | None = None
        batch_warnings: list[str] = []
        if normalized_benchmark:
            benchmark_history = histories.get(normalized_benchmark)
            if benchmark_history is None:
                detail = _history_failure_detail(normalized_benchmark, history_failures)
                batch_warnings.append(
                    f"benchmark {normalized_benchmark} unavailable; beta and alpha omitted: {detail}"
                )
            else:
                benchmark_returns = benchmark_history.daily_returns

        failures: list[PortfolioFailure] = []
        runnable: list[tuple[PortfolioSpec, pd.Timestamp, pd.Timestamp]] = []
        for portfolio in portfolios:
            missing = tuple(symbol for symbol in portfolio.symbols if symbol not in histories)
            if missing:
                detail = "; ".join(
                    f"{symbol}: {_history_failure_detail(symbol, history_failures)}"
                    for symbol in missing
                )
                failures.append(
                    PortfolioFailure(
                        name=portfolio.name,
                        stage="history",
                        detail=detail,
                        symbols=missing,
                        retryable=any(
                            _history_failure_retryable(symbol, history_failures)
                            for symbol in missing
                        ),
                    )
                )
                continue
            try:
                aligned = align_portfolio_components(histories, portfolio.symbols)
            except ValueError as exc:
                failures.append(
                    PortfolioFailure(
                        name=portfolio.name,
                        stage="simulation",
                        detail=str(exc),
                        symbols=portfolio.symbols,
                        retryable=False,
                    )
                )
                continue
            runnable.append((portfolio, aligned.start, aligned.end))

        comparison_start: pd.Timestamp | None = None
        comparison_end: pd.Timestamp | None = None
        simulation_histories: Mapping[str, TWDAssetHistory] = histories
        if len(runnable) >= 2:
            comparison_start = max(item[1] for item in runnable)
            comparison_end = min(item[2] for item in runnable)
            if comparison_start >= comparison_end:
                detail = (
                    "runnable portfolios do not share two overlapping valuation dates; "
                    "multi-portfolio comparison requires one common effective window"
                )
                failures.extend(
                    PortfolioFailure(
                        name=portfolio.name,
                        stage="comparison_window",
                        detail=detail,
                        symbols=portfolio.symbols,
                        retryable=False,
                    )
                    for portfolio, _, _ in runnable
                )
                runnable = []
                batch_warnings.append(detail)
            else:
                compared_symbols = {
                    symbol
                    for portfolio, _, _ in runnable
                    for symbol in portfolio.symbols
                }
                simulation_histories = {
                    symbol: (
                        _history_on_common_window(history, comparison_start, comparison_end)
                        if symbol in compared_symbols
                        else history
                    )
                    for symbol, history in histories.items()
                }
                if benchmark_returns is not None:
                    benchmark_returns = benchmark_returns.loc[
                        comparison_start:comparison_end
                    ]
                batch_warnings.append(
                    "multi-portfolio comparison recomputed from common window "
                    f"{comparison_start.date().isoformat()} -> "
                    f"{comparison_end.date().isoformat()} "
                    f"({COMPARISON_WINDOW_POLICY})"
                )

        results: list[PortfolioRunResult] = []
        for portfolio, _, _ in runnable:
            try:
                ledger = simulate_portfolio_ledger(
                    portfolio,
                    simulation_histories,
                    config,
                )
                report = compute_metric_report(
                    ledger,
                    config,
                    benchmark_returns=benchmark_returns,
                )
            except ValueError as exc:
                failures.append(
                    PortfolioFailure(
                        name=portfolio.name,
                        stage="simulation",
                        detail=str(exc),
                        symbols=portfolio.symbols,
                        retryable=False,
                    )
                )
                continue
            warnings = tuple(dict.fromkeys([*batch_warnings, *ledger.warnings]))
            results.append(
                PortfolioRunResult(
                    name=portfolio.name,
                    ledger=ledger,
                    metrics=report,
                    warnings=warnings,
                )
            )

        return PortfolioBatchResult(
            results=tuple(results),
            failures=tuple(failures),
            benchmark=normalized_benchmark,
            warnings=tuple(dict.fromkeys(batch_warnings)),
        )


def _history_on_common_window(
    history: TWDAssetHistory,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> TWDAssetHistory:
    """Return an ephemeral history bounded to an audited common window.

    Boundary dates can originate from another portfolio's valuation calendar.
    When this asset has no observation on a boundary, carrying its last known
    level forward and assigning a zero return is equivalent to the repository's
    existing union-calendar closed-market treatment. No value is backfilled from
    after the boundary.
    """

    valuation = history.valuation
    components = history.return_components or total_only_components(
        history.adjusted_close_twd,
        source_currency=history.quote_currency,
    )

    total_returns = _bounded_returns(components.total_returns, start, end)
    price_returns = _bounded_returns(components.price_returns, start, end)
    distribution_returns = _bounded_returns(
        components.distribution_returns,
        start,
        end,
    )
    total_index = (1.0 + total_returns).cumprod().rename("total_return_index")
    price_index = (1.0 + price_returns).cumprod().rename("price_return_index")

    bounded_valuation = replace(
        valuation,
        native_adjusted_close=_bounded_level(
            valuation.native_adjusted_close,
            start,
            end,
        ),
        fx_to_twd=_bounded_level(valuation.fx_to_twd, start, end),
        adjusted_close_twd=_bounded_level(
            valuation.adjusted_close_twd,
            start,
            end,
        ),
        daily_returns=total_returns.rename("daily_return"),
    )
    bounded_components = replace(
        components,
        fx_to_twd=_bounded_level(components.fx_to_twd, start, end),
        total_returns=total_returns,
        price_returns=price_returns,
        distribution_returns=distribution_returns,
        total_return_index=total_index,
        price_return_index=price_index,
    )
    return replace(
        history,
        valuation=bounded_valuation,
        return_components=bounded_components,
    )


def _bounded_returns(
    values: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    result = pd.to_numeric(values.loc[start:end], errors="coerce").astype(float).copy()
    if start not in result.index:
        result.loc[start] = 0.0
    if end not in result.index:
        result.loc[end] = 0.0
    result = result.sort_index()
    result.iloc[0] = 0.0
    return result.rename(values.name)


def _bounded_level(
    values: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    source = pd.to_numeric(values, errors="coerce").astype(float).sort_index()
    result = source.loc[start:end].copy()
    if start not in result.index:
        prior = source.loc[:start]
        if prior.empty:
            raise ValueError("common comparison window precedes audited history")
        result.loc[start] = float(prior.iloc[-1])
    if end not in result.index:
        prior = source.loc[:end]
        if prior.empty:
            raise ValueError("common comparison window precedes audited history")
        result.loc[end] = float(prior.iloc[-1])
    return result.sort_index().rename(values.name)


def _history_failure_detail(
    symbol: str,
    failures: Mapping[str, HistoryFailure] | None,
) -> str:
    if failures and symbol in failures:
        return failures[symbol].detail
    return "no usable audited TWD history"


def _history_failure_retryable(
    symbol: str,
    failures: Mapping[str, HistoryFailure] | None,
) -> bool:
    return bool(failures and symbol in failures and failures[symbol].retryable)


def _normalize_symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()
    if symbol.isdigit() and 4 <= len(symbol) <= 6:
        return f"{symbol}.TW"
    return symbol
