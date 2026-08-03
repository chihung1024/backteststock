"""Unified portfolio metrics for path-dependent TWD ledgers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Iterable

import numpy as np
import pandas as pd

from apps.api.app.portfolio.ledger import PortfolioLedger
from apps.api.app.portfolio.models import SimulationConfig

PORTFOLIO_METRIC_CONTEXT_VERSION = "portfolio-metrics-twd-2026-08-04.1"
TRADING_DAYS_PER_YEAR = 252.0
DAYS_PER_YEAR = 365.2425
_EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class XirrResult:
    status: str
    value: float | None
    roots: tuple[float, ...]
    method: str = "log-rate-grid-plus-bisection"


@dataclass(frozen=True, slots=True)
class TailRiskResult:
    method: str
    horizon: str
    confidence: float
    var: float | None
    cvar: float | None
    observations: int


@dataclass(frozen=True, slots=True)
class DrawdownEvent:
    peak: str
    trough: str
    recovery: str | None
    depth: float
    duration_days: int
    recovered: bool


@dataclass(frozen=True, slots=True)
class PeriodReturn:
    period: str
    start: str
    end: str
    return_value: float
    partial: bool


@dataclass(frozen=True, slots=True)
class PortfolioMetricReport:
    metrics: dict[str, float | int | str | None]
    xirr: XirrResult
    tail_risk: TailRiskResult
    drawdown_events: tuple[DrawdownEvent, ...]
    annual_returns: tuple[PeriodReturn, ...]
    monthly_returns: tuple[PeriodReturn, ...]
    metadata: dict[str, object]


def compute_metric_report(
    ledger: PortfolioLedger,
    config: SimulationConfig,
    benchmark_returns: pd.Series | None = None,
) -> PortfolioMetricReport:
    """Compute all core metrics from one ledger and one explicit context."""

    equity = _clean_series(ledger.equity, "equity")
    return_index = _clean_series(ledger.return_index, "return_index")
    daily_returns = pd.to_numeric(ledger.daily_returns, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )
    clean_returns = daily_returns.iloc[1:].dropna().astype(float)

    elapsed_days = int((return_index.index[-1] - return_index.index[0]).days)
    elapsed_years = max(elapsed_days / DAYS_PER_YEAR, 1.0 / DAYS_PER_YEAR)
    total_return = float(return_index.iloc[-1] - 1.0)
    cagr = (
        float(return_index.iloc[-1] ** (1.0 / elapsed_years) - 1.0)
        if return_index.iloc[-1] > 0.0
        else -1.0
    )

    annual_rf = config.risk_free_rate
    daily_rf = (1.0 + annual_rf) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1.0
    excess = clean_returns - daily_rf
    volatility = (
        float(clean_returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
        if len(clean_returns) > 1
        else 0.0
    )
    annualized_excess = float(excess.mean() * TRADING_DAYS_PER_YEAR) if len(excess) else 0.0
    sharpe = _safe_ratio(annualized_excess, volatility)
    downside = np.minimum(excess.to_numpy(dtype=float), 0.0)
    downside_deviation = (
        float(np.sqrt(np.mean(np.square(downside))) * math.sqrt(TRADING_DAYS_PER_YEAR))
        if len(downside)
        else 0.0
    )
    sortino = _safe_ratio(annualized_excess, downside_deviation)

    drawdowns = return_index / return_index.cummax() - 1.0
    max_drawdown = float(drawdowns.min())
    annual = period_returns(return_index, "annual")
    monthly = period_returns(return_index, "monthly")
    positive_month_ratio = (
        float(np.mean([item.return_value > 0.0 for item in monthly])) if monthly else None
    )

    xirr_result = ledger_xirr(ledger, config.initial_amount)
    tail = historical_tail_risk(clean_returns)
    events = tuple(top_drawdown_events(return_index, limit=5))

    contributions = float(ledger.external_flows.clip(lower=0.0).sum())
    withdrawals = float(-ledger.external_flows.clip(upper=0.0).sum())
    net_flows = contributions - withdrawals
    metrics: dict[str, float | int | str | None] = {
        "initial_balance": float(config.initial_amount),
        "final_balance": float(equity.iloc[-1]),
        "contributions": contributions,
        "withdrawals": withdrawals,
        "net_contributions": net_flows,
        "net_profit": float(equity.iloc[-1] - config.initial_amount - net_flows),
        "total_return": total_return,
        "cagr": cagr,
        "money_weighted_return": xirr_result.value,
        "xirr_status": xirr_result.status,
        "volatility": volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_drawdown,
        "calmar_ratio": _safe_ratio(cagr, abs(max_drawdown)),
        "var_95_daily": tail.var,
        "cvar_95_daily": tail.cvar,
        "best_year": max((item.return_value for item in annual), default=None),
        "worst_year": min((item.return_value for item in annual), default=None),
        "positive_month_ratio": positive_month_ratio,
        "transaction_costs": float(ledger.transaction_costs),
        "borrowing_costs": float(ledger.borrowing_costs),
        "total_income": float(ledger.income.sum()),
        "rebalance_count": int(ledger.rebalance_count),
        "liquidated": int(ledger.liquidated),
        "observations": int(len(return_index)),
        "start": return_index.index[0].date().isoformat(),
        "end": return_index.index[-1].date().isoformat(),
    }
    metrics.update(_benchmark_metrics(clean_returns, benchmark_returns, daily_rf))

    return PortfolioMetricReport(
        metrics=metrics,
        xirr=xirr_result,
        tail_risk=tail,
        drawdown_events=events,
        annual_returns=tuple(annual),
        monthly_returns=tuple(monthly),
        metadata={
            "metric_context_version": PORTFOLIO_METRIC_CONTEXT_VERSION,
            "ledger_contract_version": ledger.contract_version,
            "valuation_currency": "TWD",
            "risk_free_rate": annual_rf,
            "trading_days_per_year": int(TRADING_DAYS_PER_YEAR),
            "twr_flow_timing": "beginning-flow-in-denominator_end-flow-removed-from-numerator",
            "var_cvar_method": "historical_simulation_daily",
            "xirr_method": xirr_result.method,
        },
    )


def ledger_xirr(ledger: PortfolioLedger, initial_amount: float) -> XirrResult:
    dates: list[date] = [ledger.equity.index[0].date()]
    amounts: list[float] = [-float(initial_amount)]
    for timestamp, flow in ledger.external_flows.items():
        value = float(flow)
        if abs(value) <= _EPSILON:
            continue
        dates.append(timestamp.date())
        amounts.append(-value)
    dates.append(ledger.equity.index[-1].date())
    amounts.append(float(ledger.equity.iloc[-1]))
    return solve_xirr(dates, amounts)


def solve_xirr(dates: Iterable[date], amounts: Iterable[float]) -> XirrResult:
    """Return every sign-changing XIRR root instead of choosing ambiguously."""

    date_values = tuple(dates)
    cash_values = np.asarray(tuple(amounts), dtype=float)
    if len(date_values) != len(cash_values) or len(date_values) < 2:
        raise ValueError("XIRR requires matching dates and at least two cashflows")
    if not np.isfinite(cash_values).all():
        raise ValueError("XIRR cashflows must be finite")
    if not (np.any(cash_values > 0.0) and np.any(cash_values < 0.0)):
        return XirrResult(status="no_solution", value=None, roots=())

    origin = min(date_values)
    years = np.asarray([(value - origin).days / DAYS_PER_YEAR for value in date_values])

    def npv_log_rate(log_rate: float) -> float:
        values = cash_values * np.exp(-log_rate * years)
        return float(np.sum(values))

    # log(1+r) keeps the full valid domain r>-1 numerically stable.
    grid = np.linspace(math.log(1e-6), math.log(1_000_001.0), 2_401)
    values = np.asarray([npv_log_rate(point) for point in grid], dtype=float)
    scale = max(float(np.sum(np.abs(cash_values))), 1.0)
    roots: list[float] = []
    for index in range(len(grid) - 1):
        left_x, right_x = float(grid[index]), float(grid[index + 1])
        left_value, right_value = float(values[index]), float(values[index + 1])
        if not np.isfinite(left_value) or not np.isfinite(right_value):
            continue
        if abs(left_value) <= scale * 1e-12:
            roots.append(math.expm1(left_x))
            continue
        if left_value * right_value > 0.0:
            continue
        for _ in range(100):
            middle = (left_x + right_x) / 2.0
            middle_value = npv_log_rate(middle)
            if abs(middle_value) <= scale * 1e-12:
                left_x = right_x = middle
                break
            if left_value * middle_value <= 0.0:
                right_x = middle
                right_value = middle_value
            else:
                left_x = middle
                left_value = middle_value
        roots.append(math.expm1((left_x + right_x) / 2.0))

    unique = _deduplicate_roots(roots)
    if not unique:
        return XirrResult(status="no_solution", value=None, roots=())
    if len(unique) > 1:
        return XirrResult(status="multiple", value=None, roots=tuple(unique))
    return XirrResult(status="unique", value=unique[0], roots=tuple(unique))


def historical_tail_risk(returns: pd.Series, confidence: float = 0.95) -> TailRiskResult:
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return TailRiskResult(
            method="historical_simulation",
            horizon="daily",
            confidence=confidence,
            var=None,
            cvar=None,
            observations=0,
        )
    quantile = 1.0 - confidence
    var = float(clean.quantile(quantile))
    tail = clean[clean <= var]
    cvar = float(tail.mean()) if not tail.empty else var
    return TailRiskResult(
        method="historical_simulation",
        horizon="daily",
        confidence=confidence,
        var=var,
        cvar=cvar,
        observations=int(len(clean)),
    )


def period_returns(return_index: pd.Series, frequency: str) -> list[PeriodReturn]:
    levels = _clean_series(return_index, "return_index")
    if frequency == "annual":
        keys = levels.index.to_period("Y")
        start_grace = pd.Timedelta(days=7)
        end_grace = pd.Timedelta(days=7)
    elif frequency == "monthly":
        keys = levels.index.to_period("M")
        start_grace = pd.Timedelta(days=3)
        end_grace = pd.Timedelta(days=3)
    else:
        raise ValueError("period-return frequency must be annual or monthly")

    result: list[PeriodReturn] = []
    previous_level = float(levels.iloc[0])
    grouped = list(levels.groupby(keys))
    for position, (period, group) in enumerate(grouped):
        first = group.index[0]
        last = group.index[-1]
        last_level = float(group.iloc[-1])
        value = last_level / previous_level - 1.0 if previous_level > _EPSILON else 0.0
        partial_start = position == 0 and first > period.start_time + start_grace
        partial_end = position == len(grouped) - 1 and last < period.end_time - end_grace
        result.append(
            PeriodReturn(
                period=str(period),
                start=first.date().isoformat(),
                end=last.date().isoformat(),
                return_value=float(value),
                partial=bool(partial_start or partial_end),
            )
        )
        previous_level = last_level
    return result


def top_drawdown_events(
    return_index: pd.Series,
    *,
    limit: int = 5,
) -> list[DrawdownEvent]:
    levels = _clean_series(return_index, "return_index")
    peak_date = levels.index[0]
    peak_value = float(levels.iloc[0])
    event_peak: pd.Timestamp | None = None
    trough_date: pd.Timestamp | None = None
    trough_value = peak_value
    events: list[DrawdownEvent] = []

    for timestamp, raw_value in levels.iloc[1:].items():
        value = float(raw_value)
        if value >= peak_value - _EPSILON:
            if event_peak is not None and trough_date is not None:
                events.append(
                    _drawdown_event(
                        event_peak,
                        peak_value,
                        trough_date,
                        trough_value,
                        timestamp,
                    )
                )
            peak_date = timestamp
            peak_value = value
            event_peak = None
            trough_date = None
            trough_value = value
            continue
        if event_peak is None:
            event_peak = peak_date
            trough_date = timestamp
            trough_value = value
        elif value < trough_value:
            trough_date = timestamp
            trough_value = value

    if event_peak is not None and trough_date is not None:
        events.append(
            _drawdown_event(
                event_peak,
                peak_value,
                trough_date,
                trough_value,
                None,
                end=levels.index[-1],
            )
        )
    events.sort(key=lambda item: (item.depth, -item.duration_days))
    return events[: max(limit, 0)]


def _benchmark_metrics(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series | None,
    daily_risk_free: float,
) -> dict[str, float | None]:
    empty = {"beta": None, "alpha": None, "benchmark_correlation": None}
    if benchmark_returns is None:
        return empty
    benchmark = pd.to_numeric(benchmark_returns, errors="coerce").rename("benchmark")
    joined = pd.concat(
        [portfolio_returns.rename("portfolio"), benchmark],
        axis=1,
        join="inner",
    ).replace([np.inf, -np.inf], np.nan).dropna()
    if len(joined) < 3:
        return empty
    variance = float(joined["benchmark"].var(ddof=1))
    if variance <= _EPSILON:
        return empty
    covariance = float(joined["portfolio"].cov(joined["benchmark"]))
    beta = covariance / variance
    alpha_daily = joined["portfolio"].mean() - (
        daily_risk_free + beta * (joined["benchmark"].mean() - daily_risk_free)
    )
    return {
        "beta": float(beta),
        "alpha": float(alpha_daily * TRADING_DAYS_PER_YEAR),
        "benchmark_correlation": float(joined.corr().loc["portfolio", "benchmark"]),
    }


def _drawdown_event(
    peak: pd.Timestamp,
    peak_value: float,
    trough: pd.Timestamp,
    trough_value: float,
    recovery: pd.Timestamp | None,
    *,
    end: pd.Timestamp | None = None,
) -> DrawdownEvent:
    final_date = recovery or end or trough
    return DrawdownEvent(
        peak=peak.date().isoformat(),
        trough=trough.date().isoformat(),
        recovery=recovery.date().isoformat() if recovery is not None else None,
        depth=float(trough_value / peak_value - 1.0),
        duration_days=int((final_date - peak).days),
        recovered=recovery is not None,
    )


def _deduplicate_roots(values: list[float]) -> list[float]:
    result: list[float] = []
    for value in sorted(item for item in values if math.isfinite(item)):
        if not result or abs(value - result[-1]) > 1e-7 * (1.0 + abs(value)):
            result.append(float(value))
    return result


def _clean_series(values: pd.Series, name: str) -> pd.Series:
    result = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    result.index = pd.DatetimeIndex(pd.to_datetime(result.index)).tz_localize(None)
    result = result[~result.index.duplicated(keep="last")].sort_index().astype(float)
    if len(result) < 2:
        raise ValueError(f"{name} requires at least two finite observations")
    return result.rename(name)


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if not math.isfinite(numerator) or not math.isfinite(denominator):
        return None
    if abs(denominator) <= _EPSILON:
        return None
    return numerator / denominator
