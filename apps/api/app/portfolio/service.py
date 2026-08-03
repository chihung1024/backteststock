"""Partial-success service boundary for the self-owned portfolio ledger."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from apps.api.app.data.history_service import HistoryFailure, TWDAssetHistory
from apps.api.app.portfolio.ledger import PortfolioLedger, simulate_portfolio_ledger
from apps.api.app.portfolio.metrics import PortfolioMetricReport, compute_metric_report
from apps.api.app.portfolio.models import (
    PortfolioFailure,
    PortfolioSpec,
    SimulationConfig,
    validate_portfolio_batch,
)

PORTFOLIO_SERVICE_CONTRACT_VERSION = "portfolio-service-twd-2026-08-04.1"


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
    """Run valid sibling portfolios even when one portfolio or benchmark fails."""

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

        results: list[PortfolioRunResult] = []
        failures: list[PortfolioFailure] = []
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
                ledger = simulate_portfolio_ledger(portfolio, histories, config)
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
