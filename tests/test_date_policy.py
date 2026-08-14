from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd

from api import date_policy, index_v2, scan_v2


def test_complete_period_excludes_current_utc_calendar_day() -> None:
    now = datetime(2026, 8, 14, 7, 30, tzinfo=timezone.utc)

    accepted = date_policy.require_complete_period(
        pd.Timestamp("2026-08-01"),
        pd.Timestamp("2026-08-14"),
        now=now,
    )
    assert accepted.as_of_date == date(2026, 8, 13)
    assert accepted.as_of_policy == "last_complete_utc_calendar_day-v1"
    assert accepted.incomplete_current_bar_excluded is True

    try:
        date_policy.require_complete_period(
            pd.Timestamp("2026-08-01"),
            pd.Timestamp("2026-08-15"),
            now=now,
        )
    except date_policy.DatePolicyError as exc:
        assert "最後一個完整日 2026-08-13" in str(exc)
        assert "未收盤或不完整日線" in str(exc)
    else:
        raise AssertionError("current UTC day must be excluded")


def test_backtest_rejects_future_month_before_market_data(monkeypatch) -> None:
    called = False

    class ShouldNotRun:
        def run(self, *_args, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError("market data must not run for an incomplete period")

    monkeypatch.setattr(index_v2, "twd_backtest_service", ShouldNotRun())
    monkeypatch.setattr(
        date_policy,
        "latest_complete_utc_date",
        lambda _now=None: date(2024, 6, 14),
    )
    index_v2.app.config.update(TESTING=True)
    response = index_v2.app.test_client().post(
        "/api/backtest",
        json={
            "initialAmount": 10000,
            "startYear": 2024,
            "startMonth": 1,
            "endYear": 2024,
            "endMonth": 7,
            "rebalancingPeriod": "never",
            "portfolios": [
                {
                    "name": "Portfolio",
                    "tickers": ["AAA"],
                    "weights": [100],
                    "rebalancingPeriod": "never",
                }
            ],
        },
    )

    assert response.status_code == 400
    assert called is False
    assert "最後一個完整日 2024-06-14" in response.get_json()["error"]


def test_scan_rejects_incomplete_current_day_before_market_data(monkeypatch) -> None:
    called = False

    class ShouldNotRun:
        def run(self, *_args, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError("market data must not run for an incomplete period")

    monkeypatch.setattr(scan_v2, "twd_scan_service", ShouldNotRun())
    monkeypatch.setattr(
        date_policy,
        "latest_complete_utc_date",
        lambda _now=None: date(2024, 6, 14),
    )
    scan_v2.app.config.update(TESTING=True)
    response = scan_v2.app.test_client().post(
        "/api/scan",
        json={
            "tickers": ["AAA"],
            "benchmark": "SPY",
            "startDate": "2024-06-01",
            "endDate": "2024-06-15",
        },
    )

    assert response.status_code == 400
    assert called is False
    payload = response.get_json()
    assert payload["retryable"] is False
    assert "最後一個完整日 2024-06-14" in payload["error"]
