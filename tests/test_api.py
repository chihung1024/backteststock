import numpy as np
import pandas as pd
import pytest

from api import index as api


@pytest.fixture()
def client():
    api.app.config.update(TESTING=True)
    return api.app.test_client()


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
    monkeypatch.setattr(api, "download_data_silently", lambda *args, **kwargs: prices)
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
    assert result["total_return"] > 0
    assert 0 < result["data_coverage"] <= 1
    assert result["trading_days"] == 260
    assert result["data_start"] == "2023-01-02"


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


def test_v2_screener_rejects_missing_worker_snapshot(client):
    response = client.post(
        "/api/v2/screener",
        json={"universe": "sp500", "limit": 25},
    )
    assert response.status_code == 400
    assert "Universe" in response.get_json()["error"]
