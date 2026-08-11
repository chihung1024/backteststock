from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apps.api.app.portfolio.analytics import STYLE_PROXIES
from apps.api.app.portfolio.api_models import PortfolioRequest
from apps.api.app.portfolio.api_service import PortfolioAPIService
from tests.portfolio_v3_fixtures import FakeHistoryService, make_history


class UnavailableFredProvider:
    available = False

    def series(self, *_args, **_kwargs):
        raise AssertionError("FRED must not be called")


class StaticFactorProvider:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame

    def monthly_factors(self) -> pd.DataFrame:
        return self.frame.copy()


def _factor_frame() -> pd.DataFrame:
    index = pd.date_range("2020-01-31", "2022-12-31", freq="ME")
    position = np.arange(len(index), dtype=float)
    return pd.DataFrame(
        {
            "MKT_RF": 0.004 + 0.002 * np.sin(position / 3.0),
            "SMB": 0.001 + 0.0015 * np.cos(position / 4.0),
            "RF": np.full(len(index), 0.0005),
        },
        index=index,
    )


def _history_set(*, mutate_pre_window: bool = False, short_style: bool = False):
    full_index = pd.bdate_range("2020-01-02", "2022-12-30")
    common_start = pd.Timestamp("2020-01-15")
    common_end = pd.Timestamp("2022-12-20")
    late_index = full_index[(full_index >= common_start) & (full_index <= common_end)]

    position = np.arange(len(full_index), dtype=float)
    usd_returns = 0.0004 + 0.0002 * np.sin(position / 11.0)
    usd_returns[0] = 0.0
    fx_returns = 0.0001 + 0.00015 * np.cos(position / 13.0)
    fx_returns[0] = 0.0
    benchmark_returns = 0.0003 + 0.00025 * np.sin(position / 7.0)
    benchmark_returns[0] = 0.0

    if mutate_pre_window:
        pre = full_index < common_start
        fx_returns = fx_returns.copy()
        benchmark_returns = benchmark_returns.copy()
        fx_returns[pre] = 0.08
        benchmark_returns[pre] = 0.15
        fx_returns[0] = 0.0
        benchmark_returns[0] = 0.0

    late_position = np.arange(len(late_index), dtype=float)
    late_returns = 0.0005 + 0.0002 * np.cos(late_position / 9.0)
    late_returns[0] = 0.0

    histories = {
        "USDASSET": make_history(
            "USDASSET",
            full_index,
            usd_returns.tolist(),
            quote_currency="USD",
            fx_returns=fx_returns.tolist(),
        ),
        "LATE": make_history("LATE", late_index, late_returns.tolist()),
        "BMK": make_history("BMK", full_index, benchmark_returns.tolist()),
    }

    for style_position, (style, symbol) in enumerate(STYLE_PROXIES.items(), start=1):
        style_returns = (
            0.00025 * style_position
            + 0.00015 * np.sin(position / (5.0 + style_position))
            + 0.00005 * np.cos(position / (3.0 + style_position))
        )
        style_returns[0] = 0.0
        if mutate_pre_window and style == "large_value":
            pre = full_index < common_start
            style_returns = style_returns.copy()
            style_returns[pre] = 0.20
            style_returns[0] = 0.0
        style_index = full_index
        if short_style and style == "large_value":
            covered = full_index >= pd.Timestamp("2020-02-03")
            style_index = full_index[covered]
            style_returns = style_returns[covered]
        histories[symbol] = make_history(symbol, style_index, style_returns.tolist())

    return histories


def _request() -> PortfolioRequest:
    return PortfolioRequest.model_validate(
        {
            "portfolios": [
                {
                    "name": "USD early",
                    "assets": [{"symbol": "USDASSET", "weight": 100}],
                },
                {
                    "name": "TWD late",
                    "assets": [{"symbol": "LATE", "weight": 100}],
                },
            ],
            "benchmark": "BMK",
            "start_date": "2020-01-01",
            "end_date": "2022-12-20",
            "initial_amount": 100,
            "analytics": {
                "factor_analysis": True,
                "style_analysis": True,
                "regime": "market",
                "inflation_adjusted": False,
                "risk_free_rate_percent": 0,
            },
        }
    )


def _run(histories):
    service = PortfolioAPIService(
        history_service=FakeHistoryService(histories),
        factor_provider=StaticFactorProvider(_factor_frame()),
        fred_provider=UnavailableFredProvider(),
    )
    return service.backtest(_request())


def test_pre_common_window_benchmark_style_and_fx_movements_do_not_leak() -> None:
    baseline = _run(_history_set())
    mutated = _run(_history_set(mutate_pre_window=True))

    baseline_result = baseline.results[0]
    mutated_result = mutated.results[0]

    assert baseline_result["metrics"]["start"] == "2020-01-15"
    assert baseline_result["metrics"]["end"] == "2022-12-20"
    assert mutated_result["metrics"]["start"] == "2020-01-15"
    assert mutated_result["metrics"]["end"] == "2022-12-20"

    baseline_factor = baseline_result["analytics"]["factor"]
    mutated_factor = mutated_result["analytics"]["factor"]
    assert baseline_factor["sample_policy"] == "exclude-common-window-boundary-months"
    assert baseline_factor["excluded_boundary_months"] == ["2020-01", "2022-12"]
    assert baseline_factor["start"] == "2020-02-29"
    assert baseline_factor["end"] == "2022-11-30"
    assert mutated_factor["sample_policy"] == baseline_factor["sample_policy"]
    assert mutated_factor["excluded_boundary_months"] == baseline_factor["excluded_boundary_months"]
    assert mutated_factor["observations"] == baseline_factor["observations"]
    assert mutated_factor["start"] == baseline_factor["start"]
    assert mutated_factor["end"] == baseline_factor["end"]
    assert mutated_factor["factor_betas"] == pytest.approx(baseline_factor["factor_betas"])
    assert mutated_factor["fx_betas"] == pytest.approx(baseline_factor["fx_betas"])
    assert mutated_factor["annualized_intercept"] == pytest.approx(
        baseline_factor["annualized_intercept"]
    )
    assert mutated_factor["r_squared"] == pytest.approx(baseline_factor["r_squared"])

    baseline_style = baseline_result["analytics"]["style"]
    mutated_style = mutated_result["analytics"]["style"]
    assert mutated_style["observations"] == baseline_style["observations"]
    assert mutated_style["start"] == baseline_style["start"]
    assert mutated_style["end"] == baseline_style["end"]
    assert mutated_style["exposures"] == pytest.approx(baseline_style["exposures"])
    assert mutated_style["r_squared"] == pytest.approx(baseline_style["r_squared"])

    assert mutated_result["analytics"]["regime"] == baseline_result["analytics"]["regime"]


def test_style_proxy_without_exact_common_window_coverage_fails_optional_analysis_only() -> None:
    response = _run(_history_set(short_style=True))

    assert [item["name"] for item in response.results] == ["USD early", "TWD late"]
    assert all("style" not in item["analytics"] for item in response.results)
    assert all(
        any(
            "style analysis unavailable" in warning
            and "does not cover exact common comparison interval" in warning
            for warning in item["warnings"]
        )
        for item in response.results
    )
    assert all("factor" in item["analytics"] for item in response.results)
    assert all("regime" in item["analytics"] for item in response.results)
