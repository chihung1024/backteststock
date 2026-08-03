from __future__ import annotations

import pandas as pd

from apps.api.app.data.history_service import HistoryFailure
from apps.api.app.portfolio.api_models import PortfolioRequest
from apps.api.app.portfolio.api_service import PortfolioAPIService
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