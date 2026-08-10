from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from apps.api.app.data.history_service import (
    HistoryFailure,
    PartialTWDHistories,
    TWDAssetHistory,
)
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.refinery import RefineryRequest, RefineryService
from apps.api.app.refinery.service import RefineryService as Phase4BaseService


class FakeHistoryService:
    def __init__(
        self,
        histories: dict[str, TWDAssetHistory],
        failures: dict[str, HistoryFailure] | None = None,
    ) -> None:
        self.histories = histories
        self.failures = failures or {}
        self.calls: list[tuple[str, ...]] = []

    def histories_partial(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> PartialTWDHistories:
        requested = tuple(symbols)
        self.calls.append(requested)
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


class FakeFactorProvider:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.calls = 0

    def monthly_factors(self) -> pd.DataFrame:
        self.calls += 1
        return self.frame.copy()


def _history(
    symbol: str,
    dates: pd.DatetimeIndex,
    *,
    phase: float,
    quote_currency: str = "TWD",
) -> TWDAssetHistory:
    t = np.arange(len(dates), dtype=float)
    returns = (
        0.00035
        + 0.0055 * np.sin(t / (8.0 + phase))
        + 0.0025 * np.cos(t / (17.0 + phase))
        + phase * 0.00004
    )
    native_levels = 100.0 * np.cumprod(1.0 + returns)
    native = pd.Series(
        native_levels,
        index=dates,
        dtype=float,
        name="native_adjusted_close",
    )
    fx_level = 30.0 if quote_currency == "USD" else 1.0
    fx = pd.Series(fx_level, index=dates, dtype=float, name="fx_to_twd")
    twd = (native * fx).rename("adjusted_close_twd")
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency=quote_currency,
        valuation=TWDValuation(
            source_currency=quote_currency,
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
        fx_audit={
            "method": "constant_test_fx" if quote_currency == "USD" else "identity",
            "tickers": [],
        },
        raw_quote_currency=quote_currency,
        native_price_scale=1.0,
    )


def _twd_fixture() -> tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]]:
    dates = pd.bdate_range("2023-01-03", periods=780)
    return dates, {
        "AAA": _history("AAA", dates, phase=0.0),
        "BBB": _history("BBB", dates, phase=0.8),
        "CCC": _history("CCC", dates, phase=2.3),
        "SPY": _history("SPY", dates, phase=4.0),
    }


def _request(
    dates: pd.DatetimeIndex,
    *,
    symbols: list[str] | None = None,
    benchmark: str | None = "SPY",
) -> RefineryRequest:
    return RefineryRequest(
        symbols=symbols or ["AAA", "BBB", "CCC"],
        benchmark=benchmark,
        start_date=dates[0].date(),
        end_date=dates[-1].date(),
    )


def _factor_fixture(start: str = "2021-01-31", months: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(101)
    index = pd.date_range(start, periods=months, freq="ME")
    return pd.DataFrame(
        {
            "MKT_RF": rng.normal(0.006, 0.035, months),
            "SMB": rng.normal(0.001, 0.018, months),
            "HML": rng.normal(0.001, 0.017, months),
            "RMW": rng.normal(0.001, 0.012, months),
            "CMA": rng.normal(0.001, 0.011, months),
            "MOM": rng.normal(0.002, 0.025, months),
            "RF": np.full(months, 0.001),
        },
        index=index,
    )


def test_phase5_preserves_all_phase4_analysis_fields_exactly() -> None:
    dates, histories = _twd_fixture()
    request = _request(dates)
    base = Phase4BaseService(
        history_service=FakeHistoryService(histories)
    ).analyze(request)
    phase5 = RefineryService(
        history_service=FakeHistoryService(histories)
    ).analyze(request)

    for key in ("symbols", "covariance", "effective_dimensions", "portfolio", "correlations"):
        assert phase5["analysis"][key] == base["analysis"][key]
    assert phase5["dataset"] == base["dataset"]
    assert phase5["request"] == base["request"]


def test_phase5_adds_read_only_clustering_redundancy_and_unavailable_theme() -> None:
    dates, histories = _twd_fixture()
    result = RefineryService(
        history_service=FakeHistoryService(histories)
    ).analyze(_request(dates))
    analysis = result["analysis"]

    assert result["status"] == "ok"
    assert analysis["clustering"]["status"] == "ok"
    assert analysis["clustering"]["primary"]["method"] == "average"
    assert analysis["clustering"]["sensitivity"]["method"] == "complete"
    assert analysis["clustering"]["bootstrap"]["requested_replicates"] == 200
    assert len(analysis["redundancy"]["pairs"]) == 3
    assert sum(analysis["redundancy"]["counts"].values()) == 3
    assert set(analysis["redundancy"]["counts"]) == {
        "HIGH",
        "MEDIUM",
        "LOW",
        "UNCERTAIN",
    }
    assert analysis["redundancy"]["magic_numeric_score"] is False
    assert analysis["theme_relationships"]["status"] == (
        "unavailable_no_traceable_theme_source"
    )
    assert analysis["factor_relationships"]["status"] == (
        "unavailable_no_eligible_assets"
    )


def test_phase5_candidate_permutation_keeps_labelled_relationship_evidence_equivalent() -> None:
    dates, histories = _twd_fixture()
    service = RefineryService(history_service=FakeHistoryService(histories))

    original = service.analyze(
        _request(dates, symbols=["AAA", "BBB", "CCC"], benchmark=None)
    )["analysis"]
    permuted = service.analyze(
        _request(dates, symbols=["CCC", "AAA", "BBB"], benchmark=None)
    )["analysis"]

    assert original["clustering"] == permuted["clustering"]
    assert original["redundancy"]["status"] == permuted["redundancy"]["status"]
    assert original["redundancy"]["counts"] == permuted["redundancy"]["counts"]
    assert original["redundancy"]["verdict_semantics"] == (
        permuted["redundancy"]["verdict_semantics"]
    )
    assert original["redundancy"]["magic_numeric_score"] is False

    original_pairs = {
        (item["symbol_a"], item["symbol_b"]): item
        for item in original["redundancy"]["pairs"]
    }
    permuted_pairs = {
        (item["symbol_a"], item["symbol_b"]): item
        for item in permuted["redundancy"]["pairs"]
    }
    assert original_pairs.keys() == permuted_pairs.keys()
    numeric_fields = {
        "structural_correlation",
        "medium_correlation",
        "downside_correlation",
        "stress_correlation",
        "factor_implied_correlation",
        "window_cocluster_agreement",
        "bootstrap_cocluster_probability",
    }
    for pair_key in original_pairs:
        left = original_pairs[pair_key]
        right = permuted_pairs[pair_key]
        assert {
            key: value for key, value in left.items() if key not in numeric_fields
        } == {
            key: value for key, value in right.items() if key not in numeric_fields
        }
        for field in numeric_fields:
            left_value = left[field]
            right_value = right[field]
            if left_value is None or right_value is None:
                assert left_value is right_value
            else:
                assert np.isclose(
                    left_value,
                    right_value,
                    rtol=1e-12,
                    atol=1e-15,
                )

    assert original["clustering"]["bootstrap_input_fingerprint_sha256"] == (
        permuted["clustering"]["bootstrap_input_fingerprint_sha256"]
    )


def test_failed_benchmark_removes_only_conditional_redundancy_corroborators() -> None:
    dates, histories = _twd_fixture()
    histories = {key: value for key, value in histories.items() if key != "SPY"}
    failure = HistoryFailure(
        symbol="SPY",
        stage="download",
        detail="synthetic benchmark failure",
        retryable=True,
    )
    result = RefineryService(
        history_service=FakeHistoryService(histories, {"SPY": failure})
    ).analyze(_request(dates))

    assert result["status"] == "ok"
    assert result["analysis"]["clustering"]["status"] == "ok"
    assert result["analysis"]["redundancy"]["status"] == "ok"
    for pair in result["analysis"]["redundancy"]["pairs"]:
        assert pair["downside_correlation"] is None
        assert pair["stress_correlation"] is None
        assert pair["correlation_status"]["downside"] == (
            "unavailable_benchmark_failed"
        )
        assert pair["correlation_status"]["stress"] == (
            "unavailable_benchmark_failed"
        )


def test_usd_assets_use_injected_french_factors_without_second_market_fetch() -> None:
    dates = pd.bdate_range("2021-01-04", periods=1300)
    histories = {
        "AAA": _history("AAA", dates, phase=0.0, quote_currency="USD"),
        "BBB": _history("BBB", dates, phase=1.1, quote_currency="USD"),
    }
    history_service = FakeHistoryService(histories)
    factor_provider = FakeFactorProvider(_factor_fixture())
    service = RefineryService(
        history_service=history_service,
        factor_provider=factor_provider,  # type: ignore[arg-type]
    )
    request = RefineryRequest(
        symbols=["AAA", "BBB"],
        start_date=dates[0].date(),
        end_date=dates[-1].date(),
    )

    result = service.analyze(request)
    factors = result["analysis"]["factor_relationships"]

    assert history_service.calls == [("AAA", "BBB")]
    assert factor_provider.calls == 1
    assert factors["source"] == "Kenneth French Data Library"
    assert factors["scope"] == "U.S.-factor co-movement diagnostic"
    assert factors["factor_model_scope"] == "U.S.-factor co-movement diagnostic"
    assert factors["assets"]["AAA"]["status"] == "ok"
    assert factors["assets"]["BBB"]["status"] == "ok"
    assert factors["assets"]["AAA"]["factor_computable"] is True
    assert factors["assets"]["BBB"]["factor_computable"] is True
    assert factors["assets"]["AAA"]["factor_corroboration_eligible"] is False
    assert factors["assets"]["BBB"]["factor_corroboration_eligible"] is False
    assert factors["assets"]["AAA"]["factor_corroboration_reason"] == (
        "unavailable_no_traceable_instrument_scope"
    )
    assert factors["systematic_relationship"]["status"] == "ok"
    assert factors["systematic_relationship"]["matrix"]["symbols"] == ["AAA", "BBB"]
    pair = result["analysis"]["redundancy"]["pairs"][0]
    assert pair["factor_implied_correlation"] is not None
    assert pair["factor_corroboration_eligible"] is False
    assert pair["factor_corroboration_reason"] == (
        "unavailable_no_traceable_instrument_scope"
    )


def test_incomplete_membership_still_blocks_all_formal_phase5_analysis() -> None:
    dates, histories = _twd_fixture()
    histories = {key: value for key, value in histories.items() if key != "BBB"}
    failure = HistoryFailure(
        symbol="BBB",
        stage="download",
        detail="synthetic missing candidate",
        retryable=True,
    )
    result = RefineryService(
        history_service=FakeHistoryService(histories, {"BBB": failure})
    ).analyze(_request(dates))

    assert result["status"] == "incomplete"
    assert result["analysis"] is None
