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

PORTFOLIO_SERVICE_CONTRACT_VERSION = "portfolio-service-twd-2026-08-27.1"
COMPARISON_WINDOW_POLICY = "common-comparison-universe-v2"
EXECUTION_CLOCK_AUDIT_POLICY = "valuation-calendar-native-observation-audit-v1"


@dataclass(frozen=True, slots=True)
class PortfolioRunResult:
    name: str
    ledger: PortfolioLedger
    metrics: PortfolioMetricReport
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioComparisonContext:
    """Authoritative effective sample for one comparable portfolio batch."""

    policy: str
    start: pd.Timestamp
    end: pd.Timestamp

    def bound_history(self, history: TWDAssetHistory) -> TWDAssetHistory:
        """Rebuild audited history/components on this comparison window."""

        _require_history_coverage(history, self.start, self.end)
        return _history_on_common_window(history, self.start, self.end)


@dataclass(frozen=True, slots=True)
class PortfolioBatchResult:
    results: tuple[PortfolioRunResult, ...]
    failures: tuple[PortfolioFailure, ...]
    benchmark: str | None
    warnings: tuple[str, ...]
    comparison_context: PortfolioComparisonContext | None = None
    effective_benchmark_history: TWDAssetHistory | None = None
    contract_version: str = PORTFOLIO_SERVICE_CONTRACT_VERSION


class PortfolioLedgerService:
    """Run every comparable series on one authoritative effective window.

    A single runnable portfolio without a benchmark retains its full internally
    aligned history. Whenever an available benchmark is requested, or when two
    or more sibling portfolios are runnable, the service uses the intersection
    across every runnable portfolio's aligned constituent window and the
    benchmark's audited window when present. Every portfolio ledger and the
    benchmark are freshly initialized at that common start; results are never
    post-hoc clipped to create the appearance of comparability.
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
        benchmark_history: TWDAssetHistory | None = None
        benchmark_returns: pd.Series | None = None
        benchmark_window: tuple[pd.Timestamp, pd.Timestamp] | None = None
        batch_warnings: list[str] = []
        if normalized_benchmark:
            benchmark_history = histories.get(normalized_benchmark)
            if benchmark_history is None:
                detail = _history_failure_detail(normalized_benchmark, history_failures)
                batch_warnings.append(
                    f"benchmark {normalized_benchmark} unavailable; beta and alpha omitted: {detail}"
                )
            else:
                try:
                    benchmark_window = _history_effective_window(benchmark_history)
                except ValueError as exc:
                    batch_warnings.append(
                        f"benchmark {normalized_benchmark} unavailable; beta and alpha omitted: {exc}"
                    )
                    benchmark_history = None
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

        comparison_context: PortfolioComparisonContext | None = None
        simulation_histories: Mapping[str, TWDAssetHistory] = histories
        needs_common_window = len(runnable) >= 2 or (
            bool(runnable) and benchmark_window is not None
        )
        if needs_common_window:
            comparison_starts = [item[1] for item in runnable]
            comparison_ends = [item[2] for item in runnable]
            if benchmark_window is not None:
                comparison_starts.append(benchmark_window[0])
                comparison_ends.append(benchmark_window[1])
            comparison_start = max(comparison_starts)
            comparison_end = min(comparison_ends)
            if comparison_start >= comparison_end:
                participants = (
                    "runnable portfolios and benchmark"
                    if benchmark_window is not None
                    else "runnable portfolios"
                )
                detail = (
                    f"{participants} do not share two overlapping valuation dates; "
                    "comparison requires one common effective window"
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
                comparison_context = PortfolioComparisonContext(
                    policy=COMPARISON_WINDOW_POLICY,
                    start=comparison_start,
                    end=comparison_end,
                )
                compared_symbols = {
                    symbol
                    for portfolio, _, _ in runnable
                    for symbol in portfolio.symbols
                }
                simulation_histories = {
                    symbol: (
                        comparison_context.bound_history(history)
                        if symbol in compared_symbols
                        else history
                    )
                    for symbol, history in histories.items()
                }
                if benchmark_history is not None:
                    try:
                        benchmark_history = comparison_context.bound_history(
                            benchmark_history
                        )
                    except ValueError as exc:
                        batch_warnings.append(
                            f"benchmark {normalized_benchmark} unavailable on common comparison window "
                            f"{comparison_context.start.date().isoformat()} -> "
                            f"{comparison_context.end.date().isoformat()}; "
                            f"beta and alpha omitted: {exc}"
                        )
                        benchmark_history = None
                        benchmark_returns = None
                    else:
                        benchmark_returns = benchmark_history.daily_returns
                comparison_scope = (
                    "all runnable portfolio constituents plus benchmark"
                    if benchmark_window is not None
                    else "all runnable portfolio constituents"
                )
                batch_warnings.append(
                    "comparison recomputed from one common window "
                    f"{comparison_context.start.date().isoformat()} -> "
                    f"{comparison_context.end.date().isoformat()} across "
                    f"{comparison_scope} ({comparison_context.policy})"
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
            execution_clock_warning = _execution_clock_audit_warning(
                ledger,
                simulation_histories,
            )
            warnings = tuple(
                dict.fromkeys(
                    [
                        *batch_warnings,
                        *ledger.warnings,
                        *([execution_clock_warning] if execution_clock_warning else []),
                    ]
                )
            )
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
            comparison_context=comparison_context,
            effective_benchmark_history=benchmark_history,
        )


def _execution_clock_audit_warning(
    ledger: PortfolioLedger,
    histories: Mapping[str, TWDAssetHistory],
) -> str | None:
    """Flag real trade events that use carry-forward native prices.

    The current ledger deliberately remains valuation-calendar-driven.  This
    audit only observes whether a rebalance with non-zero traded notional occurs
    on a date when every constituent has a fresh native-market observation.
    Unknown provenance is ignored so synthetic/legacy fixtures keep their
    established warning surface.
    """

    audited_events = 0
    mismatches: list[tuple[str, str, tuple[str, ...]]] = []
    for event in ledger.events:
        if event.type != "rebalance":
            continue
        traded_notional = float(event.details.get("traded_notional") or 0.0)
        if traded_notional <= 1e-12:
            continue
        timestamp = pd.Timestamp(event.date).normalize()
        missing_observations: list[str] = []
        complete_provenance = True
        for symbol in ledger.symbols:
            history = histories.get(symbol)
            mask = (
                getattr(history.valuation, "native_observation_mask", None)
                if history is not None
                else None
            )
            if not isinstance(mask, pd.Series):
                complete_provenance = False
                break
            observed = bool(mask.get(timestamp, False))
            if not observed:
                missing_observations.append(symbol)
        if not complete_provenance:
            continue
        audited_events += 1
        if missing_observations:
            trigger = str(event.details.get("trigger") or "unknown")
            mismatches.append(
                (event.date, trigger, tuple(missing_observations))
            )

    if not mismatches:
        return None

    examples = "; ".join(
        f"{event_date} ({trigger}): {','.join(symbols)}"
        for event_date, trigger, symbols in mismatches[:3]
    )
    return (
        f"execution-clock audit ({EXECUTION_CLOCK_AUDIT_POLICY}): "
        f"{len(mismatches)}/{audited_events} non-zero rebalance events occurred "
        "without a fresh native-market observation for every constituent; "
        f"examples {examples}. Metrics are unchanged; the current ledger still "
        "executes on the union TWD valuation calendar."
    )


def _history_effective_window(
    history: TWDAssetHistory,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    levels = pd.to_numeric(history.adjusted_close_twd, errors="coerce").dropna().sort_index()
    if len(levels) < 2:
        raise ValueError("audited history has fewer than two usable valuation dates")
    return pd.Timestamp(levels.index[0]), pd.Timestamp(levels.index[-1])


def _require_history_coverage(
    history: TWDAssetHistory,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> None:
    first, last = _history_effective_window(history)
    if first > start or last < end:
        raise ValueError(
            "audited history does not cover exact common comparison interval "
            f"{start.date().isoformat()} -> {end.date().isoformat()} "
            f"(available {first.date().isoformat()} -> {last.date().isoformat()})"
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
