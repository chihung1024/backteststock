from datetime import date

from api import scan_v2
from apps.api.app.data.history_service import PartialTWDHistories
from apps.api.app.scan_service import TWDScanBatch


class FakeTWDScanService:
    def __init__(self):
        self.calls = []

    def run(self, tickers, **kwargs):
        values = list(tickers)
        self.calls.append((values, kwargs))
        return TWDScanBatch(
            requested=tuple([kwargs["benchmark"], *values]),
            results=[{"ticker": ticker, "status": "failed", "retryable": False} for ticker in values],
            benchmark_symbol=kwargs["benchmark"],
            benchmark_available=False,
            benchmark_failure=None,
            histories=PartialTWDHistories(
                requested=tuple([kwargs["benchmark"], *values]),
                histories={},
                failures={},
            ),
        )


def test_scan_v2_accepts_exact_daily_dates(monkeypatch):
    fake_service = FakeTWDScanService()
    monkeypatch.setattr(scan_v2, "twd_scan_service", fake_service)
    response = scan_v2.app.test_client().post(
        "/api/scan",
        json={
            "tickers": ["AAPL"],
            "benchmark": "SPY",
            "startDate": "2024-01-02",
            "endDate": "2024-03-21",
        },
    )

    assert response.status_code == 200
    assert fake_service.calls == [
        (
            ["AAPL"],
            {
                "start": date(2024, 1, 2),
                "end": date(2024, 3, 21),
                "benchmark": "SPY",
                "risk_free_rate": scan_v2.legacy.RISK_FREE_RATE,
            },
        )
    ]
    assert response.get_json()[0]["ticker"] == "AAPL"


def test_scan_v2_keeps_legacy_year_month_contract(monkeypatch):
    fake_service = FakeTWDScanService()
    monkeypatch.setattr(scan_v2, "twd_scan_service", fake_service)
    response = scan_v2.app.test_client().post(
        "/api/scan",
        json={
            "tickers": ["AAPL"],
            "benchmark": "SPY",
            "startYear": 2024,
            "startMonth": 1,
            "endYear": 2024,
            "endMonth": 3,
        },
    )

    assert response.status_code == 200
    assert fake_service.calls[0][1]["start"] == date(2024, 1, 1)
    assert fake_service.calls[0][1]["end"] == date(2024, 3, 31)
