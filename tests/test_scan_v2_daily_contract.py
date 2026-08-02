from api import scan_v2


def test_scan_v2_accepts_exact_daily_dates(monkeypatch):
    captured = {}

    def fake_download(tickers, start_date, end_date):
        captured["tickers"] = list(tickers)
        captured["start"] = start_date
        captured["end"] = end_date
        return {}, list(tickers)

    monkeypatch.setattr(scan_v2, "download_prices_finitely", fake_download)
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
    assert captured == {
        "tickers": ["SPY", "AAPL"],
        "start": "2024-01-02",
        "end": "2024-03-22",
    }
    assert response.get_json()[0]["ticker"] == "AAPL"


def test_scan_v2_keeps_legacy_year_month_contract(monkeypatch):
    captured = {}

    def fake_download(tickers, start_date, end_date):
        captured["start"] = start_date
        captured["end"] = end_date
        return {}, list(tickers)

    monkeypatch.setattr(scan_v2, "download_prices_finitely", fake_download)
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
    assert captured == {"start": "2024-01-01", "end": "2024-04-01"}
