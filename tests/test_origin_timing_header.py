from api import scan_v2
from apps.api.app.data.history_service import PartialTWDHistories
from apps.api.app.scan_service import TWDScanBatch


def test_scan_origin_emits_stable_timing_alias(monkeypatch):
    class FakeTWDScanService:
        def run(self, tickers, **kwargs):
            symbols = tuple(tickers)
            benchmark = kwargs["benchmark"]
            return TWDScanBatch(
                requested=(benchmark, *symbols),
                results=[
                    {
                        "ticker": ticker,
                        "status": "ok",
                        "valuation_currency": "TWD",
                    }
                    for ticker in symbols
                ],
                benchmark_symbol=benchmark,
                benchmark_available=True,
                benchmark_failure=None,
                histories=PartialTWDHistories(
                    requested=(benchmark, *symbols), histories={}, failures={}
                ),
            )

    monkeypatch.setattr(scan_v2, "twd_scan_service", FakeTWDScanService())
    scan_v2.app.config.update(TESTING=True)
    response = scan_v2.app.test_client().post(
        "/api/scan",
        json={
            "tickers": ["AAPL"],
            "benchmark": "SPY",
            "startYear": 2025,
            "startMonth": 1,
            "endYear": 2025,
            "endMonth": 3,
        },
    )

    assert response.status_code == 200
    standard = response.headers["Server-Timing"]
    stable = response.headers["X-Backend-Server-Timing"]
    assert stable == standard
    assert "market;dur=" in stable
    assert "compute;dur=" in stable
    assert "serialize;dur=" in stable
    assert "total;dur=" in stable
    assert response.headers["X-Scan-Requested"] == "1"
    assert response.headers["X-Scan-Resolved"] == "1"
    assert response.headers["X-Valuation-Currency"] == "TWD"
