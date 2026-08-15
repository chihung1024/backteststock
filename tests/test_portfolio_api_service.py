from __future__ import annotations

import pandas as pd
import pytest

from apps.api.app.data.history_service import HistoryFailure
from apps.api.app.portfolio.api_models import PortfolioRequest
from apps.api.app.portfolio.api_service import PortfolioAPIService
from apps.api.app.portfolio.metrics import DAYS_PER_YEAR
from tests.portfolio_v3_fixtures import FakeHistoryService, make_history


class UnavailableFredProvider:
    available = False

    def series(self, *_args, **_kwargs):
        raise AssertionError("FRED must not be called when unavailable")


class StaticFactorProvider:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame

    def monthly_factors(self) -> pd.DataFrame:
        return self.frame.copy()


def _request(**overrides) -> PortfolioRequest:
    payload = {
        "contract_version": "portfolio-v3",
        "portfolios": [
            {
                "name": "Balanced",
                "assets": [
                    {"symbol": "SPY", "weight": 50},
                    {"symbol": "2330.TW", "weight": 50},
                ],
            }
        ],
        "benchmark": "SPY",
        "start_date": "2020-01-01",
        "end_date": "2022-12-31",
        "initial_amount": 100000,
        "output_frequency": "monthly",
    }
    payload.update(overrides)
    return PortfolioRequest.model_validate(payload)


def _service() -> tuple[PortfolioAPIService, FakeHistoryService]:
    index = pd.date_range("2020-01-31", periods=36, freq="ME")
    spy_returns = [0.0, *[0.006 + (position % 5) * 0.002 for position in range(35)]]
    tw_returns = [0.0, *[0.008 + (position % 4) * 0.0025 for position in range(35)]]
    histories = {
        "SPY": make_history(
            "SPY",
            index,
            spy_returns,
            quote_currency="USD",
            fx_returns=[0.0, *([0.001] * 35)],
        ),
        "2330.TW": make_history(
            "2330.TW",
            index,
            tw_returns,
            quote_currency="TWD",
        ),
    }
    history_service = FakeHistoryService(histories)
    service = PortfolioAPIService(
        history_service=history_service,
        factor_provider=StaticFactorProvider(pd.DataFrame()),
        fred_provider=UnavailableFredProvider(),
    )
    return service, history_service


def test_preflight_reports_asset_audits_portfolio_overlap_and_benchmark() -> None:
    service, history_service = _service()

    result = service.preflight(_request())

    assert result.contract_version == "portfolio-v3"
    assert {asset.symbol for asset in result.assets} == {"SPY", "2330.TW"}
    assert all(asset.status == "ready" for asset in result.assets)
    assert result.benchmark is not None
    assert result.benchmark.symbol == "SPY"
    assert result.benchmark.fingerprints["adjusted_close_twd"]
    assert result.portfolios[0].status == "ready"
    assert result.portfolios[0].observations == 36
    assert history_service.calls[0][0] == ("SPY", "2330.TW")


def test_backtest_serializes_self_owned_ledger_metrics_and_benchmark() -> None:
    service, _ = _service()

    result = service.backtest(_request())

    assert len(result.results) == 1
    portfolio = result.results[0]
    assert portfolio["name"] == "Balanced"
    assert portfolio["metrics"]["cagr"] > 0
    assert portfolio["metrics"]["beta"] is not None
    assert portfolio["series"][0]["date"] == "2020-01-31"
    assert portfolio["target_allocation"] == {"SPY": 0.5, "2330.TW": 0.5}
    assert portfolio["xirr"]["status"] in {"unique", "no_solution"}
    assert result.benchmark is not None
    assert result.benchmark["name"] == "Benchmark · SPY"
    assert result.reproducibility["api_schema_version"].startswith("portfolio-v3-")
    assert result.reproducibility["ledger_contract_version"].startswith(
        "portfolio-ledger-twd-"
    )
    assert result.failures == []
    assert result.timing["total_ms"] >= result.timing["market_ms"]


def test_partial_history_failure_preserves_unrelated_portfolio() -> None:
    index = pd.date_range("2020-01-31", periods=30, freq="ME")
    histories = {
        "GOOD": make_history("GOOD", index, [0.0, *([0.01] * 29)]),
    }
    failures = {
        "BAD": HistoryFailure(
            symbol="BAD",
            stage="download",
            detail="upstream unavailable",
            retryable=True,
        )
    }
    service = PortfolioAPIService(
        history_service=FakeHistoryService(histories, failures),
        factor_provider=StaticFactorProvider(pd.DataFrame()),
        fred_provider=UnavailableFredProvider(),
    )
    request = PortfolioRequest.model_validate(
        {
            "portfolios": [
                {
                    "name": "Good",
                    "assets": [{"symbol": "GOOD", "weight": 100}],
                },
                {
                    "name": "Bad",
                    "assets": [{"symbol": "BAD", "weight": 100}],
                },
            ],
            "start_date": "2020-01-01",
            "end_date": "2022-06-30",
        }
    )

    result = service.backtest(request)

    assert [item["name"] for item in result.results] == ["Good"]
    assert [item["name"] for item in result.failures] == ["Bad"]
    assert result.failures[0]["retryable"] is True
    asset_status = {asset.symbol: asset.status for asset in result.assets}
    assert asset_status == {"GOOD": "ready", "BAD": "failed"}


def test_fred_dependent_analytics_degrade_to_warnings_without_erasing_result() -> None:
    service, _ = _service()
    request = _request(
        analytics={
            "factor_analysis": False,
            "style_analysis": False,
            "regime": "inflation",
            "inflation_adjusted": True,
            "risk_free_rate_percent": 0,
        }
    )

    preflight = service.preflight(request)
    result = service.backtest(request)

    assert any("FRED-dependent analytics" in warning for warning in preflight.warnings)
    assert len(result.results) == 1
    assert any("FRED API key" in warning for warning in result.warnings)
    assert any(
        "inflation adjustment unavailable" in warning
        for warning in result.results[0]["warnings"]
    )


def test_style_preflight_lists_proxy_dependencies_without_making_them_user_assets() -> None:
    service, history_service = _service()
    request = _request(
        analytics={
            "factor_analysis": False,
            "style_analysis": True,
            "regime": "none",
            "inflation_adjusted": False,
            "risk_free_rate_percent": 0,
        }
    )

    result = service.preflight(request)

    assert {asset.symbol for asset in result.assets} == {"SPY", "2330.TW"}
    assert len(result.analysis_dependencies) == 6
    assert all(item.status == "failed" for item in result.analysis_dependencies)
    requested = set(history_service.calls[0][0])
    assert requested.issuperset({"IWD", "IWF", "IWS", "IWP", "IWN", "IWO"})


def test_multi_portfolio_benchmark_uses_the_common_comparison_window() -> None:
    early_index = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    )
    late_index = pd.to_datetime(["2024-01-04", "2024-01-05"])
    histories = {
        "EARLY": make_history("EARLY", early_index, [0.0, 0.50, 0.10, 0.10]),
        "LATE": make_history("LATE", late_index, [0.0, 0.02]),
        "BMK": make_history(
            "BMK",
            early_index,
            [0.0, 0.50, 0.10, 0.10],
            price_returns=[0.0, 0.30, 0.10, 0.10],
            distribution_returns=[0.0, 0.20, 0.0, 0.0],
        ),
    }
    service = PortfolioAPIService(
        history_service=FakeHistoryService(histories),
        factor_provider=StaticFactorProvider(pd.DataFrame()),
        fred_provider=UnavailableFredProvider(),
    )
    request = PortfolioRequest.model_validate(
        {
            "portfolios": [
                {
                    "name": "Early history",
                    "assets": [{"symbol": "EARLY", "weight": 100}],
                },
                {
                    "name": "Late history",
                    "assets": [{"symbol": "LATE", "weight": 100}],
                },
            ],
            "benchmark": "BMK",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
            "initial_amount": 100,
            "output_frequency": "daily",
            "analytics": {
                "factor_analysis": False,
                "style_analysis": False,
                "regime": "none",
                "inflation_adjusted": False,
                "risk_free_rate_percent": 0,
            },
        }
    )

    result = service.backtest(request)

    assert [item["metrics"]["start"] for item in result.results] == [
        "2024-01-04",
        "2024-01-04",
    ]
    assert [item["metrics"]["end"] for item in result.results] == [
        "2024-01-05",
        "2024-01-05",
    ]
    assert [item["series"][0]["date"] for item in result.results] == [
        "2024-01-04",
        "2024-01-04",
    ]
    assert [item["series"][-1]["date"] for item in result.results] == [
        "2024-01-05",
        "2024-01-05",
    ]
    assert any("common-runnable-portfolios-v1" in warning for warning in result.warnings)
    assert result.benchmark is not None
    benchmark = result.benchmark
    assert benchmark["metrics"]["start"] == "2024-01-04"
    assert benchmark["metrics"]["end"] == "2024-01-05"
    assert benchmark["metrics"]["observations"] == 2
    assert benchmark["tail_risk"]["observations"] == 1
    assert benchmark["tail_risk"]["observations"] == (
        benchmark["metrics"]["observations"] - 1
    )
    assert benchmark["metrics"]["initial_balance"] == pytest.approx(100.0)
    assert benchmark["metrics"]["final_balance"] == pytest.approx(110.0)
    assert benchmark["metrics"]["total_return"] == pytest.approx(
        benchmark["metrics"]["final_balance"]
        / benchmark["metrics"]["initial_balance"]
        - 1.0
    )
    expected_cagr = (110.0 / 100.0) ** DAYS_PER_YEAR - 1.0
    assert benchmark["metrics"]["cagr"] == pytest.approx(expected_cagr)
    assert benchmark["metrics"]["total_income"] == pytest.approx(0.0)
    assert benchmark["series"][0]["date"] == "2024-01-04"
    assert benchmark["series"][-1]["date"] == "2024-01-05"
    assert benchmark["series"][-1]["cumulative_income"] == pytest.approx(0.0)


def test_single_portfolio_keeps_full_benchmark_history_without_common_policy() -> None:
    benchmark_index = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    )
    portfolio_index = pd.to_datetime(["2024-01-04", "2024-01-05"])
    histories = {
        "ONLY": make_history("ONLY", portfolio_index, [0.0, 0.02]),
        "BMK": make_history("BMK", benchmark_index, [0.0, 0.01, 0.01, 0.01]),
    }
    service = PortfolioAPIService(
        history_service=FakeHistoryService(histories),
        factor_provider=StaticFactorProvider(pd.DataFrame()),
        fred_provider=UnavailableFredProvider(),
    )
    request = PortfolioRequest.model_validate(
        {
            "portfolios": [
                {
                    "name": "Only",
                    "assets": [{"symbol": "ONLY", "weight": 100}],
                }
            ],
            "benchmark": "BMK",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
            "initial_amount": 100,
            "output_frequency": "daily",
            "analytics": {
                "factor_analysis": False,
                "style_analysis": False,
                "regime": "none",
                "inflation_adjusted": False,
                "risk_free_rate_percent": 0,
            },
        }
    )

    result = service.backtest(request)

    assert result.results[0]["metrics"]["start"] == "2024-01-04"
    assert result.results[0]["metrics"]["end"] == "2024-01-05"
    assert result.benchmark is not None
    assert result.benchmark["metrics"]["start"] == "2024-01-02"
    assert result.benchmark["metrics"]["end"] == "2024-01-05"
    assert not any("common-runnable-portfolios-v1" in warning for warning in result.warnings)



def test_backtest_serializes_weight_defined_cash_exposure_truth() -> None:
    service, _ = _service()
    request = _request(
        portfolios=[
            {
                "name": "Cash sleeve",
                "assets": [{"symbol": "SPY", "weight": 80}],
            }
        ],
        benchmark=None,
        output_frequency="daily",
    )

    result = service.backtest(request)

    portfolio = result.results[0]
    assert portfolio["target_allocation"] == {"SPY": 0.8}
    assert portfolio["target_asset_mix"] == {"SPY": 1.0}
    assert portfolio["target_gross_exposure_ratio"] == pytest.approx(0.8)
    assert portfolio["target_cash_allocation"] == pytest.approx(0.2)
    assert portfolio["leverage_reset_count"] > 0
    for point in portfolio["series"][1:]:
        if point["value"] and point["value"] > 0:
            assert point["gross_exposure_ratio"] == pytest.approx(0.8, rel=1e-9)
    first = portfolio["series"][0]
    assert first["cash"] == pytest.approx(20000.0)
    assert first["debt"] == pytest.approx(0.0)
    assert first["gross_exposure"] == pytest.approx(80000.0)
    assert first["net_exposure"] == pytest.approx(80000.0)
    assert first["gross_exposure_ratio"] == pytest.approx(0.8)
    assert first["net_exposure_ratio"] == pytest.approx(0.8)


def test_backtest_serializes_daily_weight_defined_leverage_truth() -> None:
    service, _ = _service()
    request = _request(
        portfolios=[
            {
                "name": "Leveraged",
                "assets": [{"symbol": "SPY", "weight": 150}],
            }
        ],
        benchmark=None,
        output_frequency="daily",
        leverage={
            "type": "none",
            "annual_interest_rate_percent": 4,
            "maintenance_margin_percent": 25,
        },
    )

    result = service.backtest(request)

    portfolio = result.results[0]
    assert portfolio["target_allocation"] == {"SPY": 1.5}
    assert portfolio["target_asset_mix"] == {"SPY": 1.0}
    assert portfolio["target_gross_exposure_ratio"] == pytest.approx(1.5)
    assert portfolio["target_cash_allocation"] == pytest.approx(0.0)
    assert portfolio["leverage_reset_count"] > 0
    first = portfolio["series"][0]
    assert first["cash"] == pytest.approx(0.0)
    assert first["debt"] == pytest.approx(50000.0)
    assert first["gross_exposure"] == pytest.approx(150000.0)
    assert first["net_exposure"] == pytest.approx(150000.0)
    assert first["gross_exposure_ratio"] == pytest.approx(1.5)
    assert first["net_exposure_ratio"] == pytest.approx(1.5)
    for point in portfolio["series"][1:]:
        if point["value"] and point["value"] > 0:
            assert point["gross_exposure_ratio"] == pytest.approx(1.5, rel=1e-9)
