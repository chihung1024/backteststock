from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from apps.api.app.data.history_service import (
    HistoryFailure,
    PartialTWDHistories,
    TWDAssetHistory,
)
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.quant import (
    ledoit_wolf_covariance,
    risk_contributions,
)
from apps.api.app.refinery import RefineryRequest, RefineryService


def _history(
    symbol: str,
    dates: pd.DatetimeIndex,
    *,
    phase: float,
) -> TWDAssetHistory:
    t = np.arange(len(dates), dtype=float)
    returns = (
        0.0004
        + 0.006 * np.sin(t / (7.0 + phase))
        + 0.003 * np.cos(t / (13.0 + phase))
        + phase * 0.00005
    )
    levels = 100.0 * np.cumprod(1.0 + returns)
    native = pd.Series(levels, index=dates, dtype=float, name="native_adjusted_close")
    fx = pd.Series(1.0, index=dates, dtype=float, name="fx_to_twd")
    twd = native.rename("adjusted_close_twd")
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency="TWD",
        valuation=TWDValuation(
            source_currency="TWD",
            native_adjusted_close=native,
            fx_to_twd=fx,
            adjusted_close_twd=twd,
            daily_returns=twd.pct_change(fill_method=None)
            .fillna(0.0)
            .rename("daily_return"),
        ),
        corporate_action_audit={
            "status": "verified_standard_actions",
            "warning_dates": [],
        },
        fx_audit={"method": "identity", "tickers": []},
        raw_quote_currency="TWD",
        native_price_scale=1.0,
    )


class FakeHistoryService:
    def __init__(
        self,
        histories: dict[str, TWDAssetHistory],
        failures: dict[str, HistoryFailure] | None = None,
    ) -> None:
        self.histories = histories
        self.failures = failures or {}
        self.calls: list[tuple[tuple[str, ...], date, date]] = []

    def histories_partial(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> PartialTWDHistories:
        requested = tuple(symbols)
        self.calls.append((requested, start, end))
        return PartialTWDHistories(
            requested=requested,
            histories={
                symbol: self.histories[symbol]
                for symbol in requested
                if symbol in self.histories
            },
            failures={
                symbol: self.failures[symbol]
                for symbol in requested
                if symbol in self.failures
            },
        )


@pytest.fixture
def research_fixture() -> tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]]:
    dates = pd.bdate_range("2024-01-02", periods=340)
    histories = {
        "AAA": _history("AAA", dates, phase=0.0),
        "BBB": _history("BBB", dates, phase=1.0),
        "CCC": _history("CCC", dates, phase=2.0),
        "SPY": _history("SPY", dates, phase=4.0),
    }
    return dates, histories


def _request(
    dates: pd.DatetimeIndex,
    *,
    benchmark: str | None = "SPY",
    weights: list[dict[str, object]] | None = None,
) -> RefineryRequest:
    return RefineryRequest(
        symbols=["AAA", "BBB", "CCC"],
        benchmark=benchmark,
        start_date=dates[0].date(),
        end_date=dates[-1].date(),
        weights=weights,
    )


def test_request_normalizes_symbols_and_requires_exact_explicit_weights() -> None:
    request = RefineryRequest(
        symbols=["2330", "spy"],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    assert request.symbols == ["2330.TW", "SPY"]
    assert request.weight_vector is None

    with pytest.raises(ValidationError, match="unique after normalization"):
        RefineryRequest(
            symbols=["2330", "2330.TW"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

    with pytest.raises(ValidationError, match="every candidate exactly once"):
        RefineryRequest(
            symbols=["AAA", "BBB"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            weights=[
                {"symbol": "AAA", "weight_percent": 100.0},
                {"symbol": "CCC", "weight_percent": 1.0},
            ],
        )


def test_service_fetches_union_once_and_benchmark_does_not_change_candidate_view(
    research_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = research_fixture
    history_service = FakeHistoryService(histories)
    service = RefineryService(history_service=history_service)

    with_benchmark = service.analyze(_request(dates, benchmark="SPY"))
    without_benchmark = service.analyze(_request(dates, benchmark=None))

    assert history_service.calls[0][0] == ("AAA", "BBB", "CCC", "SPY")
    assert history_service.calls[1][0] == ("AAA", "BBB", "CCC")
    assert len(history_service.calls) == 2
    assert with_benchmark["dataset"]["candidate_dataset_hash"] == (
        without_benchmark["dataset"]["candidate_dataset_hash"]
    )
    assert with_benchmark["analysis"]["covariance"] == without_benchmark["analysis"][
        "covariance"
    ]
    assert with_benchmark["analysis"]["effective_dimensions"] == (
        without_benchmark["analysis"]["effective_dimensions"]
    )
    for key in ("tactical_daily", "medium_daily", "structural_weekly"):
        assert with_benchmark["analysis"]["correlations"][key] == (
            without_benchmark["analysis"]["correlations"][key]
        )


def test_incomplete_candidate_blocks_formal_analysis_without_silent_deletion(
    research_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = research_fixture
    histories = {key: value for key, value in histories.items() if key != "BBB"}
    failure = HistoryFailure(
        symbol="BBB",
        stage="download",
        detail="synthetic missing candidate",
        retryable=True,
    )
    service = RefineryService(
        history_service=FakeHistoryService(histories, {"BBB": failure})
    )

    result = service.analyze(_request(dates))

    assert result["status"] == "incomplete"
    assert result["analysis"] is None
    assert result["dataset"]["requested_symbols"] == ["AAA", "BBB", "CCC"]
    assert result["dataset"]["resolved_symbols"] == ["AAA", "CCC"]
    assert result["dataset"]["failures"]["BBB"]["stage"] == "download"
    assert result["eligibility"]["candidate_membership_complete"] is False


def test_failed_benchmark_keeps_candidate_analysis_but_disables_conditionals(
    research_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = research_fixture
    histories = {key: value for key, value in histories.items() if key != "SPY"}
    failure = HistoryFailure(
        symbol="SPY",
        stage="download",
        detail="synthetic missing benchmark",
        retryable=True,
    )
    service = RefineryService(
        history_service=FakeHistoryService(histories, {"SPY": failure})
    )

    result = service.analyze(_request(dates))

    assert result["status"] == "ok"
    assert result["analysis"] is not None
    assert result["dataset"]["benchmark"]["status"] == "failed"
    assert result["analysis"]["correlations"]["downside"]["status"] == (
        "unavailable_benchmark_failed"
    )
    assert result["analysis"]["correlations"]["stress"]["status"] == (
        "unavailable_benchmark_failed"
    )


def test_no_weights_never_fabricates_equal_weight_portfolio(
    research_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = research_fixture
    result = RefineryService(history_service=FakeHistoryService(histories)).analyze(
        _request(dates)
    )

    assert result["status"] == "ok"
    assert result["request"]["weights_supplied"] is False
    assert result["analysis"]["portfolio"] == {
        "status": "unavailable_weights_not_supplied",
        "weights": None,
    }


def test_explicit_portfolio_risk_matches_phase2_primitives(
    research_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = research_fixture
    weights = [
        {"symbol": "AAA", "weight_percent": 50.0},
        {"symbol": "BBB", "weight_percent": 30.0},
        {"symbol": "CCC", "weight_percent": 20.0},
    ]
    fake = FakeHistoryService(histories)
    service = RefineryService(history_service=fake)
    request = _request(dates, weights=weights)

    result = service.analyze(request)
    candidate_dataset = service._prepare(request).candidate_dataset
    returns = candidate_dataset.daily_returns_twd.loc[:, request.symbols].dropna(how="any")
    covariance = ledoit_wolf_covariance(returns, annualization=252.0)
    direct = risk_contributions(
        np.asarray([0.5, 0.3, 0.2], dtype=float),
        covariance.covariance,
    )

    assert result["analysis"]["covariance"]["ledoit_wolf_shrinkage"] == pytest.approx(
        covariance.shrinkage
    )
    assert result["analysis"]["portfolio"]["volatility"] == pytest.approx(
        direct.volatility
    )
    np.testing.assert_allclose(
        result["analysis"]["portfolio"]["signed_component_risk_contribution"],
        direct.component,
    )


def test_repeated_injected_data_produces_identical_payloads(
    research_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = research_fixture
    service = RefineryService(history_service=FakeHistoryService(histories))
    request = _request(dates)

    assert service.analyze(request) == service.analyze(request)
