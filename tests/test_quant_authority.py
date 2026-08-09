from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from api.metrics import DAYS_PER_YEAR as SIMPLE_DAYS_PER_YEAR
from api.metrics import calculate_metrics
from apps.api.app.portfolio.ledger import PortfolioLedger
from apps.api.app.portfolio.metrics import (
    DAYS_PER_YEAR as LEDGER_DAYS_PER_YEAR,
)
from apps.api.app.portfolio.metrics import compute_metric_report
from apps.api.app.portfolio.models import SimulationConfig

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "quant_authority_v1.json"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _series(values: list[float], dates: list[str], name: str) -> pd.Series:
    return pd.Series(
        values,
        index=pd.DatetimeIndex(pd.to_datetime(dates)),
        dtype=float,
        name=name,
    )


def _no_flow_ledger(levels: pd.Series) -> PortfolioLedger:
    return_index = (levels / float(levels.iloc[0])).rename("return_index")
    daily_returns = return_index.pct_change(fill_method=None).fillna(0.0).rename(
        "daily_return"
    )
    zeros = pd.Series(0.0, index=levels.index, dtype=float)
    allocations = pd.DataFrame({"SYN": 1.0}, index=levels.index, dtype=float)
    return PortfolioLedger(
        name="synthetic",
        symbols=("SYN",),
        target_allocation={"SYN": 1.0},
        equity=levels.rename("equity"),
        return_index=return_index,
        daily_returns=daily_returns,
        external_flows=zeros.rename("external_flow"),
        income=zeros.rename("income"),
        cumulative_income=zeros.rename("cumulative_income"),
        cash=zeros.rename("cash"),
        debt=zeros.rename("debt"),
        gross_exposure=levels.rename("gross_exposure"),
        allocation_history=allocations,
        transaction_costs=0.0,
        borrowing_costs=0.0,
        rebalance_count=0,
        events=[],
        warnings=[],
        liquidated=False,
    )


def test_simple_metric_authority_matches_golden_fixture() -> None:
    fixture = _fixture()
    levels = _series(fixture["portfolioLevels"], fixture["dates"], "value")
    benchmark = _series(fixture["benchmarkLevels"], fixture["dates"], "value")
    expected = fixture["canonical"]

    metrics = calculate_metrics(
        levels,
        benchmark,
        risk_free_rate=fixture["riskFreeRate"],
    )

    assert SIMPLE_DAYS_PER_YEAR == expected["daysPerYear"]
    assert metrics["total_return"] == pytest.approx(expected["totalReturn"], rel=1e-12)
    assert metrics["cagr"] == pytest.approx(expected["cagr"], rel=1e-12)
    assert metrics["mdd"] == pytest.approx(expected["maxDrawdown"], rel=1e-12)
    assert metrics["volatility"] == pytest.approx(expected["volatility"], rel=1e-12)
    assert metrics["sharpe_ratio"] == pytest.approx(expected["sharpeRatio"], rel=1e-12)
    assert metrics["sortino_ratio"] == pytest.approx(expected["sortinoRatio"], rel=1e-12)
    assert metrics["beta"] == pytest.approx(expected["beta"], rel=1e-12)
    assert metrics["alpha"] == pytest.approx(expected["alpha"], rel=1e-12)


def test_portfolio_ledger_shared_metrics_match_when_context_is_equivalent() -> None:
    fixture = _fixture()
    levels = _series(fixture["portfolioLevels"], fixture["dates"], "equity")
    benchmark_levels = _series(
        fixture["benchmarkLevels"], fixture["dates"], "benchmark"
    )
    benchmark_returns = benchmark_levels.pct_change(fill_method=None).dropna()
    expected = fixture["canonical"]

    report = compute_metric_report(
        _no_flow_ledger(levels),
        SimulationConfig(
            initial_amount=float(levels.iloc[0]),
            risk_free_rate=fixture["riskFreeRate"],
        ),
        benchmark_returns=benchmark_returns,
    )
    metrics = report.metrics

    # These quantities have equivalent inputs/semantics in the simple-value and
    # no-flow ledger contexts and therefore must remain in parity.
    assert metrics["total_return"] == pytest.approx(expected["totalReturn"], rel=1e-12)
    assert metrics["max_drawdown"] == pytest.approx(
        expected["maxDrawdown"], rel=1e-12
    )
    assert metrics["volatility"] == pytest.approx(expected["volatility"], rel=1e-12)
    assert metrics["sharpe_ratio"] == pytest.approx(expected["sharpeRatio"], rel=1e-12)
    assert metrics["sortino_ratio"] == pytest.approx(expected["sortinoRatio"], rel=1e-12)
    assert metrics["beta"] == pytest.approx(expected["beta"], rel=1e-12)
    assert metrics["alpha"] == pytest.approx(expected["alpha"], rel=1e-12)
    assert metrics["benchmark_correlation"] == pytest.approx(
        expected["benchmarkCorrelation"], rel=1e-12
    )
    assert report.tail_risk.var == pytest.approx(expected["var95Daily"], rel=1e-12)
    assert report.tail_risk.cvar == pytest.approx(expected["cvar95Daily"], rel=1e-12)


def test_cagr_day_count_difference_is_explicit_not_silently_normalized() -> None:
    fixture = _fixture()
    levels = _series(fixture["portfolioLevels"], fixture["dates"], "equity")
    context = fixture["portfolioContext"]

    report = compute_metric_report(
        _no_flow_ledger(levels),
        SimulationConfig(initial_amount=float(levels.iloc[0])),
    )

    assert SIMPLE_DAYS_PER_YEAR == 365.25
    assert LEDGER_DAYS_PER_YEAR == context["daysPerYear"] == 365.2425
    assert report.metrics["cagr"] == pytest.approx(context["cagr"], rel=1e-12)
    # Phase 0 freezes this existing versioned difference instead of changing a
    # production result under the guise of a parity refactor.
    canonical_cagr = fixture["canonical"]["cagr"]
    assert abs(report.metrics["cagr"] - canonical_cagr) > 1e-6
    assert abs(report.metrics["cagr"] - canonical_cagr) < 0.01
