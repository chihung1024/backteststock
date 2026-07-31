import pandas as pd

from api import scan_v2


def test_scan_origin_emits_stable_timing_alias(monkeypatch):
    dates = pd.bdate_range("2025-01-02", periods=40)
    source = {
        "SPY": pd.Series(range(100, 140), index=dates, name="SPY", dtype=float),
        "AAPL": pd.Series(range(200, 240), index=dates, name="AAPL", dtype=float),
    }

    def fake_download(requested, *_args, **_kwargs):
        return ({ticker: source[ticker] for ticker in requested}, [])

    monkeypatch.setattr(scan_v2.legacy, "download_prices_finitely", fake_download)
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
