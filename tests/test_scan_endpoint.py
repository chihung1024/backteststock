import importlib

import pandas as pd


def price_frame(tickers):
    dates = pd.date_range("2025-01-02", periods=4, freq="B")
    columns = pd.MultiIndex.from_product([["Close"], tickers])
    values = []
    for offset, _date in enumerate(dates):
        values.append([100 + offset + index for index, _ticker in enumerate(tickers)])
    return pd.DataFrame(values, index=dates, columns=columns)


def payload(tickers):
    return {
        "tickers": tickers,
        "benchmark": "SPY",
        "startYear": 2025,
        "startMonth": 1,
        "endYear": 2025,
        "endMonth": 1,
    }


def test_scan_recovers_partial_bulk_response(monkeypatch):
    scan = importlib.import_module("api.scan")
    scan._price_cache.clear()
    calls = []

    def fake_download(tickers, _start, _end, *, use_threads=True):
        calls.append((list(tickers), use_threads))
        if len(calls) == 1:
            return price_frame(["AAPL", "SPY"])
        return price_frame(["MSFT"])

    monkeypatch.setattr(scan, "bulk_download_prices", fake_download)
    monkeypatch.setattr(scan.time, "sleep", lambda _delay: None)

    response = scan.app.test_client().post("/api/scan", json=payload(["AAPL", "MSFT"]))
    assert response.status_code == 200
    body = response.get_json()
    assert [item["ticker"] for item in body] == ["AAPL", "MSFT"]
    assert all(item["status"] == "ok" for item in body)
    assert calls[0][0] == ["AAPL", "MSFT", "SPY"]
    assert calls[1][0] == ["MSFT"]


def test_scan_finishes_with_terminal_failures_instead_of_pending(monkeypatch):
    scan = importlib.import_module("api.scan")
    scan._price_cache.clear()
    calls = []

    def empty_download(tickers, _start, _end, *, use_threads=True):
        calls.append((list(tickers), use_threads))
        return pd.DataFrame()

    monkeypatch.setattr(scan, "bulk_download_prices", empty_download)
    monkeypatch.setattr(scan.time, "sleep", lambda _delay: None)

    response = scan.app.test_client().post("/api/scan", json=payload(["AAPL", "MSFT"]))
    assert response.status_code == 200
    body = response.get_json()
    assert len(calls) == scan.MARKET_DATA_ATTEMPTS
    assert {item["status"] for item in body} == {"failed"}
    assert all(item["retryable"] is False for item in body)
    assert all(item["error_code"] == "market_data_unavailable" for item in body)
    assert not any(item.get("status") == "pending" for item in body)


def test_scan_keeps_stock_results_when_benchmark_is_missing(monkeypatch):
    scan = importlib.import_module("api.scan")
    scan._price_cache.clear()

    def stock_only_download(tickers, _start, _end, *, use_threads=True):
        available = [ticker for ticker in tickers if ticker != "SPY"]
        return price_frame(available) if available else pd.DataFrame()

    monkeypatch.setattr(scan, "bulk_download_prices", stock_only_download)
    monkeypatch.setattr(scan.time, "sleep", lambda _delay: None)

    response = scan.app.test_client().post("/api/scan", json=payload(["AAPL"]))
    assert response.status_code == 200
    body = response.get_json()
    assert body[0]["status"] == "ok"
    assert body[0]["beta"] is None
    assert body[0]["alpha"] is None
    assert "Beta／Alpha 暫不計算" in body[0]["note"]
