import numpy as np
import pandas as pd
import pytest

from api import index as api


@pytest.fixture()
def client():
    # `api.index_v2` intentionally replaces this shared Flask app's production
    # view at import time.  These are historical legacy-module tests, so keep
    # their target explicit instead of letting test collection order decide
    # whether they accidentally invoke the new TWD service.
    previous_handler = api.app.view_functions["backtest_handler"]
    api.app.view_functions["backtest_handler"] = api.backtest_handler
    api.app.config.update(TESTING=True)
    try:
        yield api.app.test_client()
    finally:
        api.app.view_functions["backtest_handler"] = previous_handler


def business_prices(columns=("AAA", "SPY"), periods=260):
    dates = pd.bdate_range("2023-01-02", periods=periods)
    data = {}
    base_returns = 0.0005 + 0.0002 * np.sin(np.arange(periods) / 7)
    for position, ticker in enumerate(columns):
        returns = base_returns + position * 0.0001
        data[ticker] = 100 * np.cumprod(1 + returns)
    return pd.DataFrame(data, index=dates)


def test_health_does_not_expose_environment(client, monkeypatch):
    monkeypatch.setenv("SUPER_SECRET", "do-not-leak")
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"service": "backteststock-api", "status": "ok"}
    assert b"SUPER_SECRET" not in response.data
    assert client.get("/api/debug").status_code == 404


def test_calculate_metrics_does_not_mutate_input_and_self_beta_is_one():
    history = business_prices(("AAA",), 260).rename(columns={"AAA": "value"})
    original_columns = history.columns.tolist()
    metrics = api.calculate_metrics(history, history)
    assert history.columns.tolist() == original_columns
    assert metrics["total_return"] > 0
    assert metrics["cagr"] > 0
    assert metrics["mdd"] <= 0
    assert metrics["beta"] == pytest.approx(1.0, abs=1e-10)
    assert metrics["alpha"] == pytest.approx(0.0, abs=1e-10)


def test_rebalancing_keeps_value_and_hits_target_weights():
    dates = pd.bdate_range("2023-01-02", periods=45)
    prices = pd.DataFrame(
        {
            "AAA": np.linspace(100, 140, len(dates)),
            "BBB": np.linspace(100, 80, len(dates)),
        },
        index=dates,
    )
    result = api.run_simulation(
        {
            "name": "balanced",
            "tickers": ["AAA", "BBB"],
            "weights": [50, 50],
            "rebalancingPeriod": "monthly",
        },
        prices,
        10_000,
    )
    assert result is not None
    assert result["portfolioHistory"][0]["value"] == pytest.approx(10_000)
    assert all(point["value"] > 0 for point in result["portfolioHistory"])


def test_backtest_rejects_invalid_weights_without_downloading(client, monkeypatch):
    def should_not_run(*args, **kwargs):
        raise AssertionError("market data should not be requested")

    monkeypatch.setattr(api, "download_data_silently", should_not_run)
    response = client.post(
        "/api/backtest",
        json={
            "initialAmount": 10000,
            "startYear": 2023,
            "startMonth": 1,
            "endYear": 2023,
            "endMonth": 12,
            "rebalancingPeriod": "annually",
            "benchmark": "SPY",
            "portfolios": [
                {
                    "name": "Invalid",
                    "tickers": ["AAA", "BBB"],
                    "weights": [60, 30],
                    "rebalancingPeriod": "annually",
                }
            ],
        },
    )
    assert response.status_code == 400
    assert "100%" in response.get_json()["error"]


def test_backtest_returns_explicit_benchmark_beta_and_alpha(client, monkeypatch):
    prices = business_prices(("AAA", "SPY"), 260)
    monkeypatch.setattr(api, "download_data_silently", lambda *args, **kwargs: prices)
    response = client.post(
        "/api/backtest",
        json={
            "initialAmount": 10000,
            "startYear": 2023,
            "startMonth": 1,
            "endYear": 2023,
            "endMonth": 12,
            "rebalancingPeriod": "never",
            "benchmark": "SPY",
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
    assert response.status_code == 200
    benchmark = response.get_json()["benchmark"]
    assert benchmark["beta"] == 1.0
    assert benchmark["alpha"] == 0.0


def test_screener_supports_multi_field_filters(client, monkeypatch):
    stocks = [
        {
            "ticker": "AAA",
            "in_sp500": True,
            "sector": "Technology",
            "marketCap": 500e9,
            "trailingPE": 20,
        },
        {
            "ticker": "BBB",
            "in_sp500": True,
            "sector": "Technology",
            "marketCap": 50e9,
            "trailingPE": 60,
        },
    ]
    monkeypatch.setattr(api, "get_preprocessed_data", lambda: stocks)
    response = client.post(
        "/api/screener",
        json={
            "index": "sp500",
            "sector": "Technology",
            "filters": {"marketCap": {"min": 100e9}, "trailingPE": {"max": 30}},
        },
    )
    assert response.status_code == 200
    assert response.get_json() == ["AAA"]


def test_all_tickers_is_available_for_autocomplete(client, monkeypatch):
    monkeypatch.setattr(
        api,
        "get_preprocessed_data",
        lambda: [{"ticker": "MSFT"}, {"ticker": "AAPL"}, {"ticker": "MSFT"}],
    )
    response = client.get("/api/all-tickers")
    assert response.status_code == 200
    assert response.get_json() == ["AAPL", "MSFT"]


def test_scan_reports_total_return_and_data_coverage(client, monkeypatch):
    prices = business_prices(("AAA", "SPY"), 260)
    monkeypatch.setattr(
        api, "download_data_reliably", lambda *args, **kwargs: (prices, {})
    )
    response = client.post(
        "/api/scan",
        json={
            "tickers": ["AAA"],
            "benchmark": "SPY",
            "startYear": 2023,
            "startMonth": 1,
            "endYear": 2023,
            "endMonth": 12,
        },
    )
    assert response.status_code == 200
    result = response.get_json()[0]
    assert result["status"] == "ok"
    assert result["retryable"] is False
    assert result["total_return"] > 0
    assert 0 < result["data_coverage"] <= 1
    assert result["trading_days"] == 260
    assert result["data_start"] == "2023-01-02"


def bulk_prices(tickers, periods=5):
    dates = pd.bdate_range("2023-01-02", periods=periods)
    columns = pd.MultiIndex.from_product([["Close"], tickers])
    values = np.column_stack(
        [np.linspace(100 + index, 104 + index, periods) for index in range(len(tickers))]
    )
    return pd.DataFrame(values, index=dates, columns=columns)


def test_bulk_download_uses_one_large_call_and_individual_success_cache(monkeypatch):
    api.price_cache.clear()
    calls = []

    def fake_download(tickers, **kwargs):
        calls.append((tickers, kwargs))
        return bulk_prices(tickers)

    monkeypatch.setattr(api.yf, "download", fake_download)

    prices, failures = api.download_data_reliably(
        ["AAA", "BBB", "SPY"], "2023-01-01", "2023-02-01"
    )
    cached_prices, cached_failures = api.download_data_reliably(
        ["AAA", "BBB", "SPY"], "2023-01-01", "2023-02-01"
    )

    assert failures == {}
    assert cached_failures == {}
    assert list(prices.columns) == ["AAA", "BBB", "SPY"]
    assert prices.equals(cached_prices)
    assert len(calls) == 1
    assert calls[0][0] == ["AAA", "BBB", "SPY"]
    assert calls[0][1]["threads"] == 3
    assert calls[0][1]["repair"] is True


def test_bulk_download_retries_only_symbols_missing_from_http_200(
    monkeypatch,
):
    api.price_cache.clear()
    calls = []

    def fake_download(tickers, **_kwargs):
        calls.append(tickers)
        if len(calls) == 1:
            return bulk_prices(["AAA", "SPY"])
        return bulk_prices(["BBB"])

    monkeypatch.setattr(api.yf, "download", fake_download)
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)

    prices, failures = api.download_data_reliably(
        ["AAA", "BBB", "SPY"], "2023-01-01", "2023-02-01"
    )

    assert failures == {}
    assert list(prices.columns) == ["AAA", "BBB", "SPY"]
    assert calls == [["AAA", "BBB", "SPY"], ["BBB"]]


def test_bulk_download_never_caches_an_unresolved_symbol(monkeypatch):
    api.price_cache.clear()
    calls = []

    def fake_download(tickers, **_kwargs):
        calls.append(tickers)
        available = [ticker for ticker in tickers if ticker == "AAA"]
        return bulk_prices(available) if available else pd.DataFrame()

    monkeypatch.setattr(api.yf, "download", fake_download)
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)

    prices, failures = api.download_data_reliably(
        ["AAA", "BBB"], "2023-01-01", "2023-02-01"
    )

    assert list(prices.columns) == ["AAA"]
    assert set(failures) == {"BBB"}
    assert ("AAA", "2023-01-01", "2023-02-01") in api.price_cache
    assert ("BBB", "2023-01-01", "2023-02-01") not in api.price_cache
    assert calls == [["AAA", "BBB"], ["BBB"], ["BBB"]]


def test_scan_keeps_partial_success_and_marks_missing_ticker_for_retry(
    client, monkeypatch
):
    prices = business_prices(("AAA", "SPY"), 260)
    monkeypatch.setattr(
        api,
        "download_data_reliably",
        lambda *args, **kwargs: (prices, {"BBB": RuntimeError("temporary")}),
    )
    response = client.post(
        "/api/scan",
        json={
            "tickers": ["AAA", "BBB"],
            "benchmark": "SPY",
            "startYear": 2023,
            "startMonth": 1,
            "endYear": 2023,
            "endMonth": 12,
        },
    )

    assert response.status_code == 200
    results = {item["ticker"]: item for item in response.get_json()}
    assert results["AAA"]["status"] == "ok"
    assert results["AAA"]["beta"] is not None
    assert results["AAA"]["alpha"] is not None
    assert results["BBB"] == {
        "ticker": "BBB",
        "status": "pending",
        "retryable": True,
        "error_code": "market_data_temporarily_unavailable",
    }


def test_scan_retries_whole_chunk_when_benchmark_is_missing(client, monkeypatch):
    prices = business_prices(("AAA",), 260)
    monkeypatch.setattr(
        api,
        "download_data_reliably",
        lambda *args, **kwargs: (prices, {"SPY": RuntimeError("temporary")}),
    )
    response = client.post(
        "/api/scan",
        json={
            "tickers": ["AAA"],
            "benchmark": "SPY",
            "startYear": 2023,
            "startMonth": 1,
            "endYear": 2023,
            "endMonth": 12,
        },
    )

    assert response.status_code == 503
    assert "自動重試" in response.get_json()["error"]


def test_v2_screener_returns_versioned_funnel_and_explicit_truncation(
    client, monkeypatch
):
    stocks = [
        {
            "ticker": "AAA",
            "sector": "Technology",
            "marketCap": 300e9,
            "trailingPE": 25,
        },
        {
            "ticker": "BBB",
            "sector": "Technology",
            "marketCap": 200e9,
            "trailingPE": 20,
        },
        {
            "ticker": "CCC",
            "sector": "Financial Services",
            "marketCap": 100e9,
            "trailingPE": 15,
        },
    ]
    monkeypatch.setattr(
        api,
        "get_preprocessed_dataset",
        lambda: {"data": stocks, "asOf": "2026-07-28", "warning": None},
    )
    response = client.post(
        "/api/v2/screener",
        json={
            "_universe": {
                "id": "sp500",
                "name": "S&P 500（IVV holdings）",
                "version": "2026-07-28-abc",
                "sourceAsOf": "2026-07-28",
                "proxyNote": "proxy disclosure",
                "members": ["AAA", "BBB", "CCC", "MISSING"],
            },
            "universe": "sp500",
            "sector": "Technology",
            "filters": {"marketCap": {"min": 100e9}},
            "sort": "marketCap-desc",
            "limit": 1,
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["universe"]["version"] == "2026-07-28-abc"
    assert payload["funnel"] == {
        "universeCount": 4,
        "fundamentalsAvailable": 3,
        "sectorMatches": 2,
        "passedFilters": 2,
        "selectedForScan": 1,
    }
    assert payload["candidates"][0]["ticker"] == "AAA"
    assert payload["truncated"] is True
    assert any("proxy disclosure" in warning for warning in payload["warnings"])
    assert any("缺少基本面" in warning for warning in payload["warnings"])


def test_v2_screener_defaults_to_every_candidate(client, monkeypatch):
    stocks = [
        {"ticker": "AAA", "sector": "Technology", "marketCap": 300e9},
        {"ticker": "BBB", "sector": "Technology", "marketCap": 200e9},
        {"ticker": "CCC", "sector": "Technology", "marketCap": 100e9},
    ]
    monkeypatch.setattr(
        api,
        "get_preprocessed_dataset",
        lambda: {"data": stocks, "asOf": "2026-07-30", "warning": None},
    )

    response = client.post(
        "/api/v2/screener",
        json={
            "_universe": {
                "id": "sp500",
                "name": "S&P 500（IVV holdings）",
                "version": "2026-07-30-abc",
                "sourceAsOf": "2026-07-30",
                "members": ["AAA", "BBB", "CCC"],
            },
            "universe": "sp500",
            "sort": "marketCap-desc",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["limit"] is None
    assert payload["truncated"] is False
    assert payload["funnel"]["passedFilters"] == 3
    assert payload["funnel"]["selectedForScan"] == 3
    assert [item["ticker"] for item in payload["candidates"]] == [
        "AAA",
        "BBB",
        "CCC",
    ]


def test_v2_screener_rejects_missing_worker_snapshot(client):
    response = client.post(
        "/api/v2/screener",
        json={"universe": "sp500", "limit": 25},
    )
    assert response.status_code == 400
    assert "Universe" in response.get_json()["error"]
