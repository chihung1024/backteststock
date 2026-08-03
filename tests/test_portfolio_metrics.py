from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from apps.api.app.portfolio.metrics import (
    historical_tail_risk,
    period_returns,
    solve_xirr,
    top_drawdown_events,
)


def test_xirr_reports_one_unique_root() -> None:
    result = solve_xirr(
        [date(2021, 1, 1), date(2022, 1, 1)],
        [-100.0, 110.0],
    )

    assert result.status == "unique"
    assert result.value == pytest.approx(0.10, abs=0.002)
    assert len(result.roots) == 1


def test_xirr_reports_multiple_roots_instead_of_choosing_one() -> None:
    # -100 + 230/(1+r) - 132/(1+r)^2 has roots near 10% and 20%.
    result = solve_xirr(
        [date(2021, 1, 1), date(2022, 1, 1), date(2023, 1, 1)],
        [-100.0, 230.0, -132.0],
    )

    assert result.status == "multiple"
    assert result.value is None
    assert len(result.roots) == 2
    assert result.roots[0] == pytest.approx(0.10, abs=0.003)
    assert result.roots[1] == pytest.approx(0.20, abs=0.003)


def test_xirr_reports_no_solution_when_cashflows_have_one_sign() -> None:
    result = solve_xirr(
        [date(2021, 1, 1), date(2022, 1, 1)],
        [-100.0, -10.0],
    )

    assert result.status == "no_solution"
    assert result.value is None
    assert result.roots == ()


def test_tail_risk_is_explicitly_historical_and_daily() -> None:
    returns = pd.Series([-0.10, -0.05, -0.01, 0.0, 0.02, 0.03])
    result = historical_tail_risk(returns)

    assert result.method == "historical_simulation"
    assert result.horizon == "daily"
    assert result.confidence == 0.95
    assert result.observations == 6
    assert result.cvar <= result.var


def test_drawdown_events_include_recovery_and_unrecovered_duration() -> None:
    index = pd.to_datetime(
        [
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
            "2024-01-08",
            "2024-01-09",
        ]
    )
    levels = pd.Series([1.0, 0.9, 0.8, 1.01, 0.95, 0.90], index=index)
    events = top_drawdown_events(levels)

    assert len(events) == 2
    assert events[0].depth == pytest.approx(-0.20)
    assert events[0].recovered is True
    assert events[0].recovery == "2024-01-05"
    assert events[1].depth == pytest.approx(0.90 / 1.01 - 1.0)
    assert events[1].recovered is False
    assert events[1].recovery is None


def test_period_returns_mark_incomplete_boundary_periods() -> None:
    index = pd.to_datetime(
        [
            "2024-03-15",
            "2024-12-27",
            "2025-01-03",
            "2025-01-05",
        ]
    )
    levels = pd.Series([1.0, 1.2, 1.25, 1.30], index=index)

    annual = period_returns(levels, "annual")
    monthly = period_returns(levels, "monthly")

    assert annual[0].period == "2024"
    assert annual[0].partial is True
    assert annual[1].period == "2025"
    assert annual[1].partial is True
    assert monthly[0].period == "2024-03"
    assert monthly[0].partial is True
    assert monthly[-1].period == "2025-01"
    assert monthly[-1].partial is True
