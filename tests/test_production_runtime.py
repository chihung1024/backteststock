import math

import numpy as np
import pandas as pd
import pytest

from api import index_v2, scan_v2
from api.metrics import calculate_metrics


@pytest.fixture()
def scan_client():
    scan_v2.app.config.update(TESTING=True)
    return scan_v2.app.test_client()


@pytest.fixture()
def backtest_client():
    index_v2.app.config.update(TESTING=True)
    return index_v2.app.test_client()


def test_scan_uses_aligned_standard_metrics_and_benchmark_calendar(
    scan_client, monkeypatch
):
    benchmark_dates = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
    )
    asset_dates = benchmark_dates[[0, 2, 3, 4]]
    benchmark = pd.Series([100, 101, 104, 103, 106], index=benchmark_dates, name="SPY")
    asset = pd.Series([50, 55, 52, 58], index=asset_dates, name="AAA")

    monkeypatch.setattr(
        scan_v2.legacy,
        "download_prices_finitely",
        lambda *_args, **_kwargs: ({"AAA": asset, "SPY": benchmark}, []),
    )
    response = scan_client.post(
        "/api/scan",
        json={
            "tickers": ["AAA"],
            "benchmark": "SPY",
            "startYear": 2024,
            "startMonth": 1,
            "endYear": 2024,
            "endMonth": 1,
        },
    )
    assert response.status_code == 200
    result = response.get_json()[0]
    expected = calculate_metrics(asset, benchmark, risk_free_rate=scan_v2.legacy.RISK_FREE_RATE)

    for key in (
        "total_return",
        "cagr",
        "mdd",
        "volatility",
        "sharpe_ratio",
        "sortino_ratio",
        "beta",
        "alpha",
    ):
        assert result[key] == pytest.approx(expected[key])
    assert result["data_coverage"] == pytest.approx(0.8)
    assert result["metric_price_observations"] == 4
    assert result["metric_return_observations"] == 2
    assert result["metric_start"] == "2024-01-02"
    assert result["metric_end"] == "2024-01-08"
    assert len(result["price_fingerprint"]) == 64
    assert len(result["aligned_price_fingerprint"]) == 64
    assert "repair=true" in result["reproducibility"]
    assert "aligned_sha256=" in result["note"]
    assert response.headers["X-Metric-Definition-Version"] == result[
        "metric_definition_version"
    ]


def test_scan_refuses_results_when_benchmark_is_unavailable(scan_client, monkeypatch):
    asset = pd.Series(
        [100, 101, 102], index=pd.bdate_range("2024-01-02", periods=3), name="AAA"
    )
    monkeypatch.setattr(
        scan_v2.legacy,
        "download_prices_finitely",
        lambda *_args, **_kwargs: ({"AAA": asset}, ["SPY"]),
    )
    response = scan_client.post(
        "/api/scan",
        json={
            "tickers": ["AAA"],
            "benchmark": "SPY",
            "startYear": 2024,
            "startMonth": 1,
            "endYear": 2024,
            "endMonth": 1,
        },
    )
    assert response.status_code == 503
    assert response.get_json()["retryable"] is True


def test_scan_download_contract_is_adjusted_repaired_daily(monkeypatch):
    captured = {}

    def fake_download(tickers, **kwargs):
        captured["tickers"] = tickers
        captured.update(kwargs)
        return pd.DataFrame()

    monkeypatch.setattr(scan_v2.yf, "download", fake_download)
    scan_v2.bulk_download_prices(["AAA", "SPY"], "2024-01-01", "2024-02-01")

    assert captured["tickers"] == ["AAA", "SPY"]
    assert captured["interval"] == "1d"
    assert captured["auto_adjust"] is True
    assert captured["repair"] is True
    assert captured["actions"] is False
    assert captured["keepna"] is False


def test_backtest_uses_one_global_common_period(backtest_client, monkeypatch):
    dates = pd.bdate_range("2024-01-02", periods=8)
    prices = pd.DataFrame(
        {
            "AAA": [np.nan, np.nan, 50, 52, 51, 54, 55, 58],
            "SPY": [100, 101, 102, 103, 104, 105, 106, 107],
        },
        index=dates,
    )
    monkeypatch.setattr(index_v2.legacy, "download_data_silently", lambda *_a, **_k: prices)

    response = backtest_client.post(
        "/api/backtest",
        json={
            "initialAmount": 10000,
            "startYear": 2024,
            "startMonth": 1,
            "endYear": 2024,
            "endMonth": 1,
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
    payload = response.get_json()
    effective_start = dates[2].strftime("%Y-%m-%d")
    assert payload["metadata"]["effective_start"] == effective_start
    assert payload["metadata"]["calendar_policy"] == (
        "global_complete_case_across_all_assets_and_benchmark"
    )
    assert payload["data"][0]["metric_start"] == effective_start
    assert payload["benchmark"]["metric_start"] == effective_start
    assert payload["benchmark"]["beta"] == 1.0
    assert payload["benchmark"]["alpha"] == 0.0


def test_period_rebalance_is_effective_before_first_return_of_new_period():
    dates = pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02"])
    prices = pd.DataFrame(
        {
            "AAA": [100.0, 200.0, 400.0, 400.0],
            "BBB": [100.0, 100.0, 100.0, 100.0],
        },
        index=dates,
    )
    result = index_v2.run_simulation(
        {
            "name": "Balanced",
            "tickers": ["AAA", "BBB"],
            "weights": [50, 50],
            "rebalancingPeriod": "monthly",
        },
        prices,
        100.0,
    )
    values = {point["date"]: point["value"] for point in result["portfolioHistory"]}
    assert values["2024-01-31"] == pytest.approx(150.0)
    assert values["2024-02-01"] == pytest.approx(225.0)
    assert result["rebalancing_execution"] == "previous_close_before_period_start"


def test_runtime_metric_formula_matches_manual_sharpe_and_sortino():
    values = pd.Series(
        [100.0, 103.0, 101.0, 106.0, 104.0],
        index=pd.bdate_range("2024-01-02", periods=5),
    )
    metrics = index_v2.calculate_metrics(values)
    returns = values.pct_change(fill_method=None).dropna()
    annual_std = returns.std(ddof=1) * math.sqrt(252)
    expected_sharpe = returns.mean() * 252 / annual_std
    downside = np.minimum(returns.to_numpy(), 0.0)
    downside_dev = np.sqrt(np.mean(downside**2)) * math.sqrt(252)
    expected_sortino = returns.mean() * 252 / downside_dev
    assert metrics["sharpe_ratio"] == pytest.approx(expected_sharpe)
    assert metrics["sortino_ratio"] == pytest.approx(expected_sortino)
