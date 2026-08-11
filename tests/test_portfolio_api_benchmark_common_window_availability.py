from __future__ import annotations

import pandas as pd

from apps.api.app.portfolio.api_models import PortfolioRequest
from apps.api.app.portfolio.api_service import PortfolioAPIService
from tests.portfolio_v3_fixtures import FakeHistoryService, make_history


class UnavailableFredProvider:
    available = False

    def series(self, *_args, **_kwargs):
        raise AssertionError("FRED must not be called")


class EmptyFactorProvider:
    def monthly_factors(self) -> pd.DataFrame:
        return pd.DataFrame()


def test_late_benchmark_fails_closed_without_erasing_valid_common_window_results() -> None:
    common_index = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    )
    benchmark_index = pd.to_datetime(["2024-01-04", "2024-01-05"])
    histories = {
        "A": make_history("A", common_index, [0.0, 0.01, 0.01, 0.01]),
        "B": make_history("B", common_index, [0.0, 0.02, 0.02, 0.02]),
        "BMK": make_history("BMK", benchmark_index, [0.0, 0.03]),
    }
    service = PortfolioAPIService(
        history_service=FakeHistoryService(histories),
        factor_provider=EmptyFactorProvider(),
        fred_provider=UnavailableFredProvider(),
    )
    request = PortfolioRequest.model_validate(
        {
            "portfolios": [
                {"name": "A", "assets": [{"symbol": "A", "weight": 100}]},
                {"name": "B", "assets": [{"symbol": "B", "weight": 100}]},
            ],
            "benchmark": "BMK",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
            "initial_amount": 100,
            "analytics": {
                "factor_analysis": False,
                "style_analysis": False,
                "regime": "market",
                "inflation_adjusted": False,
                "risk_free_rate_percent": 0,
            },
        }
    )

    result = service.backtest(request)

    assert [item["name"] for item in result.results] == ["A", "B"]
    assert [item["metrics"]["start"] for item in result.results] == [
        "2024-01-02",
        "2024-01-02",
    ]
    assert [item["metrics"]["end"] for item in result.results] == [
        "2024-01-05",
        "2024-01-05",
    ]
    assert result.benchmark is None
    assert any(
        "benchmark BMK unavailable on common comparison window" in warning
        for warning in result.warnings
    )
    assert all(item["metrics"]["beta"] is None for item in result.results)
    assert all(item["metrics"]["alpha"] is None for item in result.results)
    assert all(
        any("regime analysis requires an available benchmark" in warning for warning in item["warnings"])
        for item in result.results
    )
