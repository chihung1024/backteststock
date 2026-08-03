import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from api import index_v2, market_data, scan_v2
from api.corporate_actions import RETURN_BASIS
from api.metrics import METRIC_DEFINITION_VERSION
from apps.api.app.backtest_service import PortfolioFailure, TWDBacktestBatch
from apps.api.app.data.history_service import PartialTWDHistories
from apps.api.app.scan_service import TWDScanBatch


@pytest.fixture()
def scan_client():
    scan_v2.app.config.update(TESTING=True)
    return scan_v2.app.test_client()


@pytest.fixture()
def backtest_client():
    index_v2.app.config.update(TESTING=True)
    return index_v2.app.test_client()


class FakeTWDScanService:
    def __init__(self, *, benchmark_available=True):
        self.calls = []
        self.benchmark_available = benchmark_available

    def run(self, tickers, **kwargs):
        normalized = list(tickers)
        self.calls.append((normalized, kwargs))
        rows = [
            {
                "ticker": ticker,
                "status": "ok",
                "retryable": False,
                "total_return": 0.1,
                "cagr": 0.1,
                "mdd": -0.05,
                "volatility": 0.2,
                "sharpe_ratio": 0.5,
                "sortino_ratio": 0.6,
                "beta": 1.0 if self.benchmark_available else None,
                "alpha": 0.0 if self.benchmark_available else None,
                "metric_start": "2024-01-02",
                "metric_end": "2024-01-31",
                "metric_definition_version": METRIC_DEFINITION_VERSION,
                "valuation_currency": "TWD",
                "benchmark_available": self.benchmark_available,
                "note": None if self.benchmark_available else "（Beta／Alpha 暫不計算）",
            }
            for ticker in normalized
        ]
        return TWDScanBatch(
            requested=tuple([kwargs["benchmark"], *normalized]),
            results=rows,
            benchmark_symbol=kwargs["benchmark"],
            benchmark_available=self.benchmark_available,
            benchmark_failure=None,
            histories=PartialTWDHistories(
                requested=tuple([kwargs["benchmark"], *normalized]),
                histories={},
                failures={},
            ),
        )


def test_scan_routes_twd_results_and_preserves_timing_headers(scan_client, monkeypatch):
    fake_service = FakeTWDScanService()
    monkeypatch.setattr(scan_v2, "twd_scan_service", fake_service)
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
    tickers, call = fake_service.calls[0]
    assert tickers == ["AAA"]
    assert call["start"] == date(2024, 1, 1)
    assert call["end"] == date(2024, 1, 31)
    assert call["benchmark"] == "SPY"
    assert result["valuation_currency"] == "TWD"
    assert result["metric_definition_version"] == METRIC_DEFINITION_VERSION
    assert "market;dur=" in response.headers["Server-Timing"]
    assert response.headers["X-Scan-Requested"] == "1"
    assert response.headers["X-Scan-Resolved"] == "1"
    assert response.headers["X-Metric-Definition-Version"] == METRIC_DEFINITION_VERSION
    assert response.headers["X-Valuation-Currency"] == "TWD"
    assert response.headers["X-TWD-Valuation-Contract-Version"]


def test_scan_keeps_asset_results_without_an_available_benchmark(scan_client, monkeypatch):
    fake_service = FakeTWDScanService(benchmark_available=False)
    monkeypatch.setattr(scan_v2, "twd_scan_service", fake_service)
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
    assert result["status"] == "ok"
    assert result["beta"] is None
    assert result["alpha"] is None
    assert result["benchmark_available"] is False
    assert "Beta／Alpha 暫不計算" in result["note"]


def test_scan_accepts_more_than_the_internal_hundred_ticker_batch(scan_client, monkeypatch):
    fake_service = FakeTWDScanService()
    monkeypatch.setattr(scan_v2, "twd_scan_service", fake_service)
    tickers = [f"T{index:03d}" for index in range(101)]
    response = scan_client.post(
        "/api/scan",
        json={
            "tickers": tickers,
            "benchmark": "SPY",
            "startDate": "2024-01-02",
            "endDate": "2024-01-31",
        },
    )

    assert response.status_code == 200
    assert len(fake_service.calls[0][0]) == 101
    assert len(response.get_json()) == 101


def test_scan_download_contract_preserves_raw_adjusted_and_actions(monkeypatch):
    captured = {}

    def fake_download(tickers, **kwargs):
        captured["tickers"] = tickers
        captured.update(kwargs)
        return pd.DataFrame()

    monkeypatch.setattr(market_data.yf, "download", fake_download)
    scan_v2.bulk_download_prices(["AAA", "SPY"], "2024-01-01", "2024-02-01")

    assert captured["tickers"] == ["AAA", "SPY"]
    assert captured["interval"] == "1d"
    assert captured["auto_adjust"] is False
    assert captured["repair"] is True
    assert captured["actions"] is True
    assert captured["keepna"] is False


def test_backtest_routes_through_the_twd_service_and_preserves_partial_results(
    backtest_client, monkeypatch
):
    class FakeTWDService:
        def __init__(self):
            self.calls = []

        def run(self, specs, **kwargs):
            self.calls.append((specs, kwargs))
            return TWDBacktestBatch(
                requested=("AAA", "BAD", "SPY"),
                results=[
                    {
                        "name": "Portfolio",
                        "metric_start": "2024-01-03",
                        "metric_end": "2024-01-31",
                        "metric_price_observations": 21,
                        "valuationCurrency": "TWD",
                        "portfolioHistory": [],
                    }
                ],
                failures=[
                    PortfolioFailure(
                        name="Unavailable",
                        stage="market_data",
                        detail="BAD: fx unavailable",
                        symbols=("BAD",),
                        retryable=True,
                    )
                ],
                benchmark={
                    "name": "SPY",
                    "metric_start": "2024-01-03",
                    "metric_end": "2024-01-31",
                    "beta": 1.0,
                    "alpha": 0.0,
                    "valuationCurrency": "TWD",
                    "portfolioHistory": [],
                },
                benchmark_failure=None,
                histories=PartialTWDHistories(
                    requested=("AAA", "BAD", "SPY"), histories={}, failures={}
                ),
            )

    fake_service = FakeTWDService()
    monkeypatch.setattr(index_v2, "twd_backtest_service", fake_service)

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
    specs, call = fake_service.calls[0]
    assert specs[0].weights == (1.0,)
    assert call["start"] == date(2024, 1, 1)
    assert call["end"] == date(2024, 1, 31)
    assert call["benchmark"] == "SPY"
    assert payload["metadata"]["valuation_currency"] == "TWD"
    assert payload["metadata"]["calendar_policy"] == (
        "union_twd_valuation_calendar_forward_fill_after_observation_complete_case-v1"
    )
    assert payload["metadata"]["return_basis"] == RETURN_BASIS
    assert response.headers["X-Valuation-Currency"] == "TWD"
    assert response.headers["X-TWD-Valuation-Contract-Version"]
    assert payload["data"][0]["metric_start"] == "2024-01-03"
    assert payload["data"][0]["valuationCurrency"] == "TWD"
    assert payload["benchmark"]["metric_start"] == "2024-01-03"
    assert payload["benchmark"]["beta"] == 1.0
    assert payload["benchmark"]["alpha"] == 0.0
    assert payload["failures"] == [
        {
            "name": "Unavailable",
            "stage": "market_data",
            "detail": "BAD: fx unavailable",
            "symbols": ["BAD"],
            "retryable": True,
        }
    ]
    assert "其他投組已保留" in payload["warning"]


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
