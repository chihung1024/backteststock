from __future__ import annotations

import pandas as pd
import pytest

from apps.api.app.portfolio.api_models import PortfolioRequest
from apps.api.app.portfolio.api_service import PortfolioAPIService
from tests.portfolio_v3_fixtures import FakeHistoryService, make_history


class UnavailableFredProvider:
    available = False

    def series(self, *_args, **_kwargs):
        raise AssertionError("FRED must not be called for market-regime analysis")


class EmptyFactorProvider:
    def monthly_factors(self) -> pd.DataFrame:
        return pd.DataFrame()


def test_multi_portfolio_regime_analytics_receives_common_window_benchmark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    early_index = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    )
    late_index = pd.to_datetime(["2024-01-04", "2024-01-05"])
    histories = {
        "EARLY": make_history("EARLY", early_index, [0.0, 0.50, 0.10, 0.10]),
        "LATE": make_history("LATE", late_index, [0.0, 0.02]),
        "BMK": make_history("BMK", early_index, [0.0, 0.50, 0.10, 0.10]),
    }
    service = PortfolioAPIService(
        history_service=FakeHistoryService(histories),
        factor_provider=EmptyFactorProvider(),
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
            "analytics": {
                "factor_analysis": False,
                "style_analysis": False,
                "regime": "market",
                "inflation_adjusted": False,
                "risk_free_rate_percent": 0,
            },
        }
    )
    observed: list[tuple[str, str, str]] = []

    def capture_regime(ledger, benchmark_returns, *_args, **_kwargs):
        observed.append(
            (
                ledger.name,
                benchmark_returns.index[0].date().isoformat(),
                benchmark_returns.index[-1].date().isoformat(),
            )
        )
        return {"status": "captured"}

    monkeypatch.setattr(
        "apps.api.app.portfolio.api_service.regime_analysis",
        capture_regime,
    )

    result = service.backtest(request)

    assert [item["analytics"]["regime"] for item in result.results] == [
        {"status": "captured"},
        {"status": "captured"},
    ]
    assert observed == [
        ("Early history", "2024-01-04", "2024-01-05"),
        ("Late history", "2024-01-04", "2024-01-05"),
    ]
