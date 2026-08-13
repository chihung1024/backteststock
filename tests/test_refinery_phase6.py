from __future__ import annotations

import json
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
    PRIMARY_CLUSTER_LINKAGE,
    PRIMARY_FLAT_CUT_DISTANCE,
    SENSITIVITY_CLUSTER_LINKAGE,
    effective_dimensions,
    hierarchical_clustering,
    ledoit_wolf_covariance,
    multi_horizon_correlations,
)
from apps.api.app.refinery import RefineryRequest, RefineryService
from apps.api.app.refinery.models import (
    DAILY_COVARIANCE_ANNUALIZATION,
    MAX_EXPERIMENT_OPERATIONS,
    MAX_EXPERIMENT_UNION_SYMBOLS,
    MAX_RESPONSE_BYTES,
    MEDIUM_MIN_OBSERVATIONS,
    STRUCTURAL_MIN_OBSERVATIONS,
    TACTICAL_MIN_OBSERVATIONS,
)
from apps.api.app.refinery.phase5_service import Phase5RefineryService
from apps.api.app.refinery.phase6_service import (
    MAX_EXPERIMENT_PAIR_IMPACTS,
    PHASE6_MARGINAL_CONTRACT_VERSION,
    Phase6RefineryService,
    frozen_sample_identity,
)
from apps.api.app.research import build_research_dataset


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
        del start, end
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
) -> TWDAssetHistory:
    timeline = np.arange(len(dates), dtype=float)
    returns = (
        0.00035
        + 0.0055 * np.sin(timeline / (8.0 + phase))
        + 0.0025 * np.cos(timeline / (17.0 + phase))
        + phase * 0.00004
    )
    levels = 100.0 * np.cumprod(1.0 + returns)
    native = pd.Series(
        levels,
        index=dates,
        dtype=float,
        name="native_adjusted_close",
    )
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


def _factor_fixture() -> pd.DataFrame:
    rng = np.random.default_rng(101)
    months = 72
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
        index=pd.date_range("2021-01-31", periods=months, freq="ME"),
    )


@pytest.fixture
def market_fixture() -> tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]]:
    dates = pd.bdate_range("2023-01-03", periods=780)
    return dates, {
        "AAA": _history("AAA", dates, phase=0.0),
        "BBB": _history("BBB", dates, phase=0.8),
        "CCC": _history("CCC", dates, phase=2.3),
        "DDD": _history("DDD", dates[150:], phase=3.1),
        "SPY": _history("SPY", dates, phase=4.0),
    }


def _request(
    dates: pd.DatetimeIndex,
    *,
    experiment_plan: list[dict[str, str]] | None = None,
    symbols: list[str] | None = None,
    benchmark: str | None = "SPY",
) -> RefineryRequest:
    return RefineryRequest(
        symbols=symbols or ["AAA", "BBB", "CCC"],
        benchmark=benchmark,
        start_date=dates[0].date(),
        end_date=dates[-1].date(),
        experiment_plan=experiment_plan,
    )


def _history_with_changed_level(
    history: TWDAssetHistory,
    timestamp: pd.Timestamp,
    *,
    multiplier: float,
) -> TWDAssetHistory:
    """Change one audited level without changing the fixture object in place."""

    native = history.native_adjusted_close.copy()
    native.loc[timestamp] *= multiplier
    fx = history.fx_to_twd.copy()
    twd = (native * fx).rename("adjusted_close_twd")
    return TWDAssetHistory(
        symbol=history.symbol,
        quote_currency=history.quote_currency,
        valuation=TWDValuation(
            source_currency="TWD",
            native_adjusted_close=native.rename("native_adjusted_close"),
            fx_to_twd=fx.rename("fx_to_twd"),
            adjusted_close_twd=twd,
            daily_returns=twd.pct_change(fill_method=None)
            .fillna(0.0)
            .rename("daily_return"),
        ),
        corporate_action_audit=history.corporate_action_audit,
        fx_audit=history.fx_audit,
        raw_quote_currency=history.raw_quote_currency,
        native_price_scale=history.native_price_scale,
    )


def _direct_frozen_global_samples(
    histories: dict[str, TWDAssetHistory],
    request: RefineryRequest,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Construct the P6 source matrices without service-private helpers."""

    union_symbols = request.experiment_union_symbols
    dataset = build_research_dataset(
        PartialTWDHistories(
            requested=union_symbols,
            histories={symbol: histories[symbol] for symbol in union_symbols},
            failures={},
        ),
        start=request.start_date,
        end=request.end_date,
    )
    canonical_symbols = sorted(union_symbols)
    daily = (
        dataset.daily_returns_twd.loc[:, canonical_symbols]
        .replace([np.inf, -np.inf], np.nan)
        .dropna(how="any")
        .astype(float)
    )
    weekly = (
        dataset.weekly_returns_twd.loc[:, canonical_symbols]
        .replace([np.inf, -np.inf], np.nan)
        .dropna(how="any")
        .astype(float)
    )
    return daily, weekly


def _assert_direct_structural_parity(
    actual: dict[str, object],
    daily: pd.DataFrame,
    weekly: pd.DataFrame,
) -> None:
    """Independently recompose the allowed quant primitives for one variant."""

    covariance = ledoit_wolf_covariance(
        daily,
        annualization=DAILY_COVARIANCE_ANNUALIZATION,
    )
    covariance_dimension = effective_dimensions(covariance.covariance)
    correlations = multi_horizon_correlations(
        daily,
        weekly,
        tactical_min_observations=TACTICAL_MIN_OBSERVATIONS,
        medium_min_observations=MEDIUM_MIN_OBSERVATIONS,
        structural_min_observations=STRUCTURAL_MIN_OBSERVATIONS,
    )
    actual_covariance = actual["covariance"]
    assert isinstance(actual_covariance, dict)
    assert actual_covariance["observations"] == covariance.observations
    assert actual_covariance["features"] == covariance.features
    assert actual_covariance["annualization"] == pytest.approx(
        covariance.annualization
    )
    assert actual_covariance["ledoit_wolf_shrinkage"] == pytest.approx(
        covariance.shrinkage
    )

    actual_dimensions = actual["effective_dimensions"]
    assert isinstance(actual_dimensions, dict)
    actual_covariance_dimension = actual_dimensions["covariance"]
    assert isinstance(actual_covariance_dimension, dict)
    assert actual_covariance_dimension["entropy_effective_rank"] == pytest.approx(
        covariance_dimension.entropy_effective_rank
    )
    assert actual_covariance_dimension["participation_ratio"] == pytest.approx(
        covariance_dimension.participation_ratio
    )

    actual_correlations = actual["correlations"]
    assert isinstance(actual_correlations, dict)
    for name, expected in {
        "tactical_daily": correlations.tactical_daily,
        "medium_daily": correlations.medium_daily,
        "structural_weekly": correlations.structural_weekly,
    }.items():
        observed = actual_correlations[name]
        assert isinstance(observed, dict)
        assert observed["status"] == expected.status
        assert observed["observations"] == expected.observations
        assert observed["input_observations"] == expected.input_observations
        if expected.matrix is None:
            assert observed["matrix"] is None
            continue
        observed_matrix = observed["matrix"]
        assert isinstance(observed_matrix, dict)
        assert observed_matrix["symbols"] == list(expected.matrix.columns)
        np.testing.assert_allclose(
            np.asarray(observed_matrix["values"], dtype=float),
            expected.matrix.to_numpy(dtype=float),
            rtol=0.0,
            atol=1e-12,
        )

    actual_clustering = actual["clustering"]
    assert isinstance(actual_clustering, dict)
    if correlations.structural_weekly.matrix is None:
        assert actual_clustering["primary"] is None
        assert actual_clustering["sensitivity"] is None
        return

    for key, method in {
        "primary": PRIMARY_CLUSTER_LINKAGE,
        "sensitivity": SENSITIVITY_CLUSTER_LINKAGE,
    }.items():
        expected = hierarchical_clustering(
            correlations.structural_weekly.matrix,
            method=method,
            cut_distance=PRIMARY_FLAT_CUT_DISTANCE,
        )
        observed = actual_clustering[key]
        assert isinstance(observed, dict)
        assert observed["method"] == method
        assert observed["cluster_count"] == len(expected.clusters)
        assert {
            tuple(group["members"])
            for group in observed["clusters"]
        } == {tuple(group.members) for group in expected.clusters}


def test_phase6_plan_normalization_and_resource_policy() -> None:
    assert RefineryService is Phase6RefineryService

    request = RefineryRequest(
        symbols=["2330", "AAA", "BBB"],
        start_date=date(2024, 1, 2),
        end_date=date(2024, 12, 31),
        experiment_plan=[
            {"type": "remove_one", "remove": "2330.tw"},
            {"type": "add_one", "add": "spy"},
            {"type": "replace_one", "remove": "AAA", "add": "0050"},
        ],
    )

    assert request.symbols == ["2330.TW", "AAA", "BBB"]
    assert request.experiment_external_symbols == ("SPY", "0050.TW")
    assert request.experiment_union_symbols == (
        "2330.TW",
        "AAA",
        "BBB",
        "SPY",
        "0050.TW",
    )
    assert request.requested_market_symbols == request.experiment_union_symbols

    with pytest.raises(ValidationError, match="unique after normalization"):
        _request(
            pd.bdate_range("2024-01-02", periods=260),
            experiment_plan=[
                {"type": "add_one", "add": "2330"},
                {"type": "add_one", "add": "2330.tw"},
            ],
        )

    with pytest.raises(ValidationError, match="must exist in candidate symbols"):
        _request(
            pd.bdate_range("2024-01-02", periods=260),
            experiment_plan=[{"type": "remove_one", "remove": "ZZZ"}],
        )

    with pytest.raises(ValidationError, match="must not already exist"):
        _request(
            pd.bdate_range("2024-01-02", periods=260),
            experiment_plan=[{"type": "add_one", "add": "AAA"}],
        )

    with pytest.raises(ValidationError):
        _request(
            pd.bdate_range("2024-01-02", periods=260),
            experiment_plan=[
                {"type": "add_one", "add": f"EXTRA{index:02d}"}
                for index in range(MAX_EXPERIMENT_OPERATIONS + 1)
            ],
        )

    baseline = [f"BASE{index:02d}" for index in range(13)]
    additions = [
        {"type": "add_one", "add": f"EXTRA{index:02d}"}
        for index in range(MAX_EXPERIMENT_OPERATIONS)
    ]
    assert len(baseline) + len(additions) == MAX_EXPERIMENT_UNION_SYMBOLS + 1
    with pytest.raises(ValidationError, match="union symbols exceed"):
        _request(
            pd.bdate_range("2024-01-02", periods=260),
            symbols=baseline,
            experiment_plan=additions,
        )


def test_phase6_without_a_plan_is_exact_phase5_parity(
    market_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = market_fixture
    request = _request(dates)
    phase5_history = FakeHistoryService(histories)
    phase6_history = FakeHistoryService(histories)
    phase5_factors = FakeFactorProvider(_factor_fixture())
    phase6_factors = FakeFactorProvider(_factor_fixture())
    phase5 = Phase5RefineryService(
        history_service=phase5_history,
        factor_provider=phase5_factors,
    )
    phase6 = Phase6RefineryService(
        history_service=phase6_history,
        factor_provider=phase6_factors,
    )

    assert phase6.preflight(request) == phase5.preflight(request)
    assert phase6_history.calls == [("AAA", "BBB", "CCC", "SPY")]
    assert phase6_factors.calls == 0
    assert phase6.analyze(request) == phase5.analyze(request)
    assert phase6_history.calls == [
        ("AAA", "BBB", "CCC", "SPY"),
        ("AAA", "BBB", "CCC", "SPY"),
    ]
    assert phase6_factors.calls == phase5_factors.calls


def test_phase6_uses_one_union_fetch_and_one_frozen_sample(
    market_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = market_fixture
    history_service = FakeHistoryService(histories)
    result = Phase6RefineryService(
        history_service=history_service,
        factor_provider=FakeFactorProvider(_factor_fixture()),
    ).analyze(
        _request(
            dates,
            experiment_plan=[
                {"type": "remove_one", "remove": "AAA"},
                {"type": "add_one", "add": "DDD"},
                {"type": "replace_one", "remove": "BBB", "add": "DDD"},
            ],
        )
    )

    marginal = result["marginal_experiments"]
    assert history_service.calls == [("AAA", "BBB", "CCC", "DDD", "SPY")]
    assert result["status"] == "ok"
    assert marginal["status"] == "ready"
    assert marginal["methodology"]["contract_version"] == (
        PHASE6_MARGINAL_CONTRACT_VERSION
    )
    assert len(marginal["results"]) == 3
    assert marginal["common_sample"]["status"] == "ready"
    assert marginal["common_sample"]["daily"]["observations"] < result["analysis"][
        "covariance"
    ]["estimators"]["ledoit_wolf"]["observations"]
    assert [item["operation"] for item in marginal["results"]] == [
        {"type": "remove_one", "remove": "AAA"},
        {"type": "add_one", "add": "DDD"},
        {"type": "replace_one", "remove": "BBB", "add": "DDD"},
    ]
    assert {
        item["common_sample"]["daily"]["fingerprint_sha256"]
        for item in marginal["results"]
    } == {marginal["common_sample"]["daily"]["fingerprint_sha256"]}
    assert {
        item["common_sample"]["weekly"]["fingerprint_sha256"]
        for item in marginal["results"]
    } == {marginal["common_sample"]["weekly"]["fingerprint_sha256"]}
    experiment_baseline = marginal["experiment_baseline"]
    assert experiment_baseline is not None
    for item in marginal["results"]:
        assert item["variant"]["covariance"]["observations"] == (
            experiment_baseline["covariance"]["observations"]
        )
        pair_impacts = item["deltas"]["pair_impacts"]
        assert len(pair_impacts["removed_pairs"]) + len(pair_impacts["added_pairs"]) <= (
            MAX_EXPERIMENT_PAIR_IMPACTS
        )
        for evidence in pair_impacts["shared_pair_invariant"].values():
            assert evidence["maximum_absolute_delta"] <= evidence["tolerance"]
    assert all("portfolio" not in item["variant"] for item in marginal["results"])


def test_phase6_variants_match_direct_frozen_sample_primitives_and_ids(
    market_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    """Falsify per-variant recomputation by independently rebuilding inputs."""

    dates, histories = market_fixture
    request = _request(
        dates,
        experiment_plan=[
            {"type": "remove_one", "remove": "AAA"},
            {"type": "add_one", "add": "DDD"},
            {"type": "replace_one", "remove": "BBB", "add": "DDD"},
        ],
    )
    result = Phase6RefineryService(
        history_service=FakeHistoryService(histories),
        factor_provider=FakeFactorProvider(_factor_fixture()),
    ).analyze(request)
    marginal = result["marginal_experiments"]
    daily_global, weekly_global = _direct_frozen_global_samples(histories, request)

    assert marginal["common_sample"]["daily"] == frozen_sample_identity(daily_global)
    assert marginal["common_sample"]["weekly"] == frozen_sample_identity(weekly_global)
    experiment_baseline = marginal["experiment_baseline"]
    assert isinstance(experiment_baseline, dict)
    _assert_direct_structural_parity(
        experiment_baseline,
        daily_global.loc[:, request.symbols],
        weekly_global.loc[:, request.symbols],
    )

    expected_variants = [
        [symbol for symbol in request.symbols if symbol != "AAA"],
        [*request.symbols, "DDD"],
        ["DDD" if symbol == "BBB" else symbol for symbol in request.symbols],
    ]
    for item, symbols in zip(marginal["results"], expected_variants, strict=True):
        assert item["variant_symbols"] == symbols
        _assert_direct_structural_parity(
            item["variant"],
            daily_global.loc[:, symbols],
            weekly_global.loc[:, symbols],
        )

    repeated = Phase6RefineryService(
        history_service=FakeHistoryService(histories),
        factor_provider=FakeFactorProvider(_factor_fixture()),
    ).analyze(
        _request(
            dates,
            experiment_plan=[
                {"remove": "aaa", "type": "remove_one"},
                {"add": "ddd", "type": "add_one"},
                {"add": "ddd", "remove": "bbb", "type": "replace_one"},
            ],
        )
    )
    assert [item["id"] for item in marginal["results"]] == [
        item["id"] for item in repeated["marginal_experiments"]["results"]
    ]
    assert all(
        item["id"]
        not in {
            marginal["common_sample"]["daily"]["fingerprint_sha256"],
            marginal["common_sample"]["weekly"]["fingerprint_sha256"],
            marginal["common_sample"]["experiment_union_dataset_hash"],
        }
        for item in marginal["results"]
    )


def test_phase6_experiment_membership_failure_preserves_baseline(
    market_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = market_fixture
    histories.pop("DDD")
    failure = HistoryFailure(
        symbol="DDD",
        stage="download",
        detail="synthetic external symbol failure",
        retryable=True,
    )
    history_service = FakeHistoryService(histories, {"DDD": failure})
    result = Phase6RefineryService(
        history_service=history_service,
        factor_provider=FakeFactorProvider(_factor_fixture()),
    ).analyze(
        _request(
            dates,
            experiment_plan=[{"type": "add_one", "add": "DDD"}],
        )
    )

    marginal = result["marginal_experiments"]
    assert history_service.calls == [("AAA", "BBB", "CCC", "DDD", "SPY")]
    assert result["status"] == "ok"
    assert result["analysis"] is not None
    assert marginal["status"] == "incomplete"
    assert marginal["experiment_baseline"] is None
    assert marginal["results"] == []
    assert marginal["failures"]["DDD"]["stage"] == "download"
    assert marginal["eligibility"]["baseline_analysis_ready"] is True
    assert marginal["eligibility"]["experiment_membership_complete"] is False


def test_phase6_preflight_exposes_eligibility_without_variant_analysis(
    market_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = market_fixture
    history_service = FakeHistoryService(histories)
    result = Phase6RefineryService(
        history_service=history_service,
        factor_provider=FakeFactorProvider(_factor_fixture()),
    ).preflight(
        _request(
            dates,
            experiment_plan=[{"type": "add_one", "add": "DDD"}],
        )
    )

    marginal = result["marginal_experiments"]
    assert history_service.calls == [("AAA", "BBB", "CCC", "DDD", "SPY")]
    assert marginal["status"] == "ready"
    assert marginal["experiment_baseline"] is None
    assert marginal["results"] == []


def test_phase6_insufficient_global_sample_fails_only_the_marginal_layer(
    market_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = market_fixture
    histories["DDD"] = _history("DDD", dates[-40:], phase=3.1)
    result = Phase6RefineryService(
        history_service=FakeHistoryService(histories),
        factor_provider=FakeFactorProvider(_factor_fixture()),
    ).analyze(
        _request(
            dates,
            experiment_plan=[{"type": "add_one", "add": "DDD"}],
        )
    )

    marginal = result["marginal_experiments"]
    assert result["status"] == "ok"
    assert result["analysis"] is not None
    assert marginal["status"] == "insufficient_data"
    assert marginal["common_sample"]["status"] == "frozen_insufficient_data"
    assert marginal["experiment_baseline"] is None
    assert marginal["results"] == []


def test_phase6_benchmark_failure_does_not_constrain_common_sample(
    market_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = market_fixture
    no_benchmark = Phase6RefineryService(
        history_service=FakeHistoryService(histories),
        factor_provider=FakeFactorProvider(_factor_fixture()),
    ).analyze(
        _request(
            dates,
            benchmark=None,
            experiment_plan=[{"type": "add_one", "add": "DDD"}],
        )
    )
    histories.pop("SPY")
    failed_benchmark = Phase6RefineryService(
        history_service=FakeHistoryService(
            histories,
            {
                "SPY": HistoryFailure(
                    symbol="SPY",
                    stage="download",
                    detail="synthetic benchmark failure",
                    retryable=True,
                )
            },
        ),
        factor_provider=FakeFactorProvider(_factor_fixture()),
    ).analyze(
        _request(
            dates,
            experiment_plan=[{"type": "add_one", "add": "DDD"}],
        )
    )

    assert failed_benchmark["status"] == "ok"
    assert failed_benchmark["dataset"]["benchmark"]["status"] == "failed"
    assert failed_benchmark["marginal_experiments"]["common_sample"] == (
        no_benchmark["marginal_experiments"]["common_sample"]
    )


def test_frozen_sample_identity_is_canonical_and_value_sensitive() -> None:
    frame = pd.DataFrame(
        {"BBB": [0.01, 0.02], "AAA": [0.03, 0.04]},
        index=pd.to_datetime(["2024-01-03", "2024-01-02"]),
    )
    equivalent = frame.iloc[::-1].loc[:, ["AAA", "BBB"]]
    changed = equivalent.copy()
    changed.loc[pd.Timestamp("2024-01-02"), "AAA"] = 0.031

    assert frozen_sample_identity(frame) == frozen_sample_identity(equivalent)
    assert frozen_sample_identity(frame)["fingerprint_sha256"] != frozen_sample_identity(
        changed
    )["fingerprint_sha256"]

    source = pd.DataFrame(
        {"AAA": [0.01, 0.02, 0.03], "BBB": [0.04, np.nan, 0.06]},
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
    )
    effective = source.dropna(how="any")
    excluded_change = source.copy()
    excluded_change.loc[pd.Timestamp("2024-01-03"), "AAA"] = 0.99
    assert frozen_sample_identity(effective) == frozen_sample_identity(
        excluded_change.dropna(how="any")
    )


def test_phase6_union_dataset_hash_remains_independent_of_frozen_sample_hashes(
    market_fixture: tuple[pd.DatetimeIndex, dict[str, TWDAssetHistory]],
) -> None:
    dates, histories = market_fixture
    request = _request(
        dates,
        benchmark=None,
        experiment_plan=[{"type": "add_one", "add": "DDD"}],
    )
    baseline = Phase6RefineryService(
        history_service=FakeHistoryService(histories),
        factor_provider=FakeFactorProvider(_factor_fixture()),
    ).analyze(request)["marginal_experiments"]["common_sample"]

    changed_histories = dict(histories)
    changed_histories["AAA"] = _history_with_changed_level(
        histories["AAA"],
        dates[0],
        multiplier=1.01,
    )
    changed = Phase6RefineryService(
        history_service=FakeHistoryService(changed_histories),
        factor_provider=FakeFactorProvider(_factor_fixture()),
    ).analyze(request)["marginal_experiments"]["common_sample"]

    # DDD begins later, so the altered opening level is outside both frozen
    # full-union samples. It still belongs to ResearchDataset provenance.
    assert baseline["experiment_union_dataset_hash"] != changed[
        "experiment_union_dataset_hash"
    ]
    assert baseline["daily"] == changed["daily"]
    assert baseline["weekly"] == changed["weekly"]
    assert baseline["experiment_union_dataset_hash"] not in {
        baseline["daily"]["fingerprint_sha256"],
        baseline["weekly"]["fingerprint_sha256"],
    }


def test_phase6_bounded_plan_stays_under_response_limit() -> None:
    dates = pd.bdate_range("2023-01-03", periods=340)
    baseline = [f"BASE{index:02d}" for index in range(MAX_EXPERIMENT_UNION_SYMBOLS)]
    histories = {
        symbol: _history(symbol, dates, phase=float(index) / 3.0)
        for index, symbol in enumerate(baseline)
    }
    result = Phase6RefineryService(
        history_service=FakeHistoryService(histories),
        factor_provider=FakeFactorProvider(_factor_fixture()),
    ).analyze(
        _request(
            dates,
            symbols=baseline,
            benchmark=None,
            experiment_plan=[
                {"type": "remove_one", "remove": symbol}
                for symbol in baseline[:MAX_EXPERIMENT_OPERATIONS]
            ],
        )
    )

    assert result["marginal_experiments"]["status"] == "ready"
    assert len(result["marginal_experiments"]["results"]) == MAX_EXPERIMENT_OPERATIONS
    assert {
        item["variant"]["covariance"]["features"]
        for item in result["marginal_experiments"]["results"]
    } == {MAX_EXPERIMENT_UNION_SYMBOLS - 1}
    payload_bytes = json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert len(payload_bytes) < MAX_RESPONSE_BYTES
