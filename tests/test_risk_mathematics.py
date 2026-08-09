from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.covariance import ledoit_wolf as sklearn_ledoit_wolf

from apps.api.app.quant.correlation import (
    MEDIUM_DAILY_WINDOW,
    STRUCTURAL_WEEKLY_WINDOW,
    TACTICAL_DAILY_WINDOW,
    correlation_matrix,
    downside_correlation,
    multi_horizon_correlations,
    stress_correlation,
)
from apps.api.app.quant.covariance import (
    covariance_diagnostics,
    estimator_dispersion,
    ewma_covariance,
    ledoit_wolf_covariance,
    sample_covariance,
)
from apps.api.app.quant.risk import (
    diversification_ratio,
    effective_dimensions,
    gross_risk_contribution_equivalent_holdings,
    portfolio_variance,
    portfolio_volatility,
    risk_contributions,
    weight_effective_holdings,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "risk_math_v1.json"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _returns() -> np.ndarray:
    return np.asarray(_fixture()["returns"], dtype=float)


def test_covariance_estimators_match_golden_fixture() -> None:
    fixture = _fixture()
    returns = _returns()

    sample = sample_covariance(returns)
    lw = ledoit_wolf_covariance(returns)
    ewma = ewma_covariance(returns, decay=fixture["ewmaDecay"])

    np.testing.assert_allclose(
        sample.covariance,
        np.asarray(fixture["sampleCovariance"]),
        rtol=1e-13,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        lw.covariance,
        np.asarray(fixture["ledoitWolfCovariance"]),
        rtol=1e-13,
        atol=1e-15,
    )
    assert lw.shrinkage == pytest.approx(
        fixture["ledoitWolfShrinkage"], rel=1e-13, abs=1e-15
    )
    np.testing.assert_allclose(
        ewma.covariance,
        np.asarray(fixture["ewmaCovariance"]),
        rtol=1e-13,
        atol=1e-15,
    )


def test_ledoit_wolf_matches_sklearn_reference_on_multiple_shapes() -> None:
    rng = np.random.default_rng(20260809)
    for observations, features in ((40, 3), (100, 12), (35, 50), (20, 1)):
        returns = rng.normal(size=(observations, features))
        expected_covariance, expected_shrinkage = sklearn_ledoit_wolf(
            returns,
            assume_centered=False,
        )
        actual = ledoit_wolf_covariance(returns)
        np.testing.assert_allclose(
            actual.covariance,
            expected_covariance,
            rtol=1e-12,
            atol=1e-14,
        )
        assert actual.shrinkage == pytest.approx(
            expected_shrinkage,
            rel=1e-12,
            abs=1e-14,
        )


def test_ledoit_wolf_assume_centered_matches_sklearn_reference() -> None:
    rng = np.random.default_rng(7)
    returns = rng.normal(loc=0.002, scale=0.01, size=(80, 7))
    expected_covariance, expected_shrinkage = sklearn_ledoit_wolf(
        returns,
        assume_centered=True,
    )
    actual = ledoit_wolf_covariance(returns, assume_centered=True)

    np.testing.assert_allclose(
        actual.covariance,
        expected_covariance,
        rtol=1e-12,
        atol=1e-14,
    )
    assert actual.shrinkage == pytest.approx(
        expected_shrinkage,
        rel=1e-12,
        abs=1e-14,
    )


def test_annualization_scales_covariance_not_shrinkage() -> None:
    returns = _returns()
    daily = ledoit_wolf_covariance(returns)
    annual = ledoit_wolf_covariance(returns, annualization=252.0)

    np.testing.assert_allclose(annual.covariance, daily.covariance * 252.0)
    assert annual.shrinkage == pytest.approx(daily.shrinkage)


def test_covariance_diagnostics_identify_singular_psd_matrix() -> None:
    covariance = np.array([[0.04, 0.04], [0.04, 0.04]], dtype=float)
    report = covariance_diagnostics(covariance, observations=100)

    assert report.is_psd
    assert report.symmetry_error == 0.0
    assert report.numerical_rank == 1
    assert report.min_eigenvalue == pytest.approx(0.0, abs=1e-15)
    assert math.isinf(report.condition_number)


def test_covariance_diagnostics_reject_material_asymmetry_from_psd_status() -> None:
    covariance = np.array([[1.0, 0.2], [0.25, 1.0]], dtype=float)
    report = covariance_diagnostics(covariance, observations=20)

    assert report.symmetry_error > report.tolerance
    assert not report.is_psd


def test_estimator_dispersion_is_zero_for_identical_and_positive_otherwise() -> None:
    sample = sample_covariance(_returns())
    lw = ledoit_wolf_covariance(_returns())
    report = estimator_dispersion(
        {
            "sample": sample,
            "sample_copy": sample.covariance.copy(),
            "lw": lw,
        }
    )

    assert report.pairwise_relative_frobenius["sample::sample_copy"] == 0.0
    assert report.maximum_relative_frobenius > 0.0


def test_risk_contribution_and_diversification_match_golden_fixture() -> None:
    fixture = _fixture()
    expected = fixture["annualizedLedoitWolf"]
    covariance = ledoit_wolf_covariance(
        _returns(),
        annualization=fixture["annualization"],
    ).covariance
    weights = np.asarray(fixture["weights"], dtype=float)

    variance = portfolio_variance(weights, covariance)
    volatility = portfolio_volatility(weights, covariance)
    contributions = risk_contributions(weights, covariance)

    assert variance == pytest.approx(expected["portfolioVariance"], rel=1e-13)
    assert volatility == pytest.approx(
        expected["portfolioVolatility"], rel=1e-13
    )
    assert contributions.status == "ok"
    assert contributions.marginal is not None
    assert contributions.component is not None
    np.testing.assert_allclose(
        contributions.marginal,
        np.asarray(expected["marginalRiskContribution"]),
        rtol=1e-13,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        contributions.component,
        np.asarray(expected["componentRiskContribution"]),
        rtol=1e-13,
        atol=1e-15,
    )
    assert float(np.sum(contributions.component)) == pytest.approx(
        volatility,
        rel=1e-13,
    )
    assert diversification_ratio(weights, covariance) == pytest.approx(
        expected["diversificationRatio"],
        rel=1e-13,
    )
    assert weight_effective_holdings(weights) == pytest.approx(
        expected["weightEffectiveHoldings"],
        rel=1e-13,
    )
    assert gross_risk_contribution_equivalent_holdings(
        contributions.component
    ) == pytest.approx(
        expected["grossRiskContributionEquivalentHoldings"],
        rel=1e-13,
    )


def test_negative_hedge_risk_contribution_remains_signed() -> None:
    covariance = np.array([[0.04, -0.019], [-0.019, 0.01]], dtype=float)
    weights = np.array([0.2, 0.8], dtype=float)
    result = risk_contributions(weights, covariance)

    assert result.status == "ok"
    assert result.component is not None
    assert result.component[0] < 0.0
    assert result.component[1] > 0.0
    assert float(result.component.sum()) == pytest.approx(result.volatility)
    gross_count = gross_risk_contribution_equivalent_holdings(result.component)
    assert gross_count is not None
    assert 1.0 <= gross_count <= 2.0


def test_zero_volatility_returns_unavailable_contribution_decomposition() -> None:
    covariance = np.zeros((2, 2), dtype=float)
    weights = np.array([0.5, 0.5], dtype=float)
    result = risk_contributions(weights, covariance)

    assert result.status == "zero_volatility"
    assert result.volatility == 0.0
    assert result.marginal is None
    assert result.component is None
    assert diversification_ratio(weights, covariance) is None


def test_duplicate_assets_do_not_create_effective_risk_dimensions() -> None:
    perfect_duplicate_correlation = np.ones((3, 3), dtype=float)
    result = effective_dimensions(perfect_duplicate_correlation)

    assert result.entropy_effective_rank == pytest.approx(1.0)
    assert result.participation_ratio == pytest.approx(1.0)


def test_identity_matrix_has_full_effective_dimensions() -> None:
    result = effective_dimensions(np.eye(4, dtype=float))

    assert result.entropy_effective_rank == pytest.approx(4.0)
    assert result.participation_ratio == pytest.approx(4.0)


def test_effective_dimension_golden_values() -> None:
    fixture = _fixture()
    expected = fixture["annualizedLedoitWolf"]
    returns = _returns()
    correlation = np.corrcoef(returns, rowvar=False)
    covariance = ledoit_wolf_covariance(
        returns,
        annualization=fixture["annualization"],
    ).covariance

    correlation_rank = effective_dimensions(correlation)
    covariance_rank = effective_dimensions(covariance)

    assert correlation_rank.entropy_effective_rank == pytest.approx(
        expected["correlationEntropyEffectiveRank"], rel=1e-13
    )
    assert correlation_rank.participation_ratio == pytest.approx(
        expected["correlationParticipationRatio"], rel=1e-13
    )
    assert covariance_rank.entropy_effective_rank == pytest.approx(
        expected["covarianceEntropyEffectiveRank"], rel=1e-13
    )
    assert covariance_rank.participation_ratio == pytest.approx(
        expected["covarianceParticipationRatio"], rel=1e-13
    )


def test_asset_permutation_does_not_change_portfolio_risk() -> None:
    fixture = _fixture()
    covariance = ledoit_wolf_covariance(
        _returns(), annualization=fixture["annualization"]
    ).covariance
    weights = np.asarray(fixture["weights"], dtype=float)
    permutation = np.array([2, 0, 1])

    original = risk_contributions(weights, covariance)
    permuted = risk_contributions(
        weights[permutation],
        covariance[np.ix_(permutation, permutation)],
    )

    assert permuted.volatility == pytest.approx(original.volatility)
    assert original.component is not None
    assert permuted.component is not None
    np.testing.assert_allclose(
        permuted.component,
        original.component[permutation],
        rtol=1e-13,
        atol=1e-15,
    )


def _correlation_fixture(rows: int = 300) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(20260809)
    market = rng.normal(0.0003, 0.01, size=rows)
    returns = pd.DataFrame(
        {
            "AAA": market + rng.normal(0.0, 0.004, size=rows),
            "BBB": 0.8 * market + rng.normal(0.0, 0.005, size=rows),
            "CCC": -0.25 * market + rng.normal(0.0, 0.009, size=rows),
        },
        index=pd.bdate_range("2024-01-02", periods=rows),
    )
    benchmark = pd.Series(market, index=returns.index, name="benchmark")
    return returns, benchmark


def test_multi_horizon_correlation_uses_explicit_windows() -> None:
    daily, _benchmark = _correlation_fixture()
    weekly = daily.iloc[4::5].copy()
    result = multi_horizon_correlations(
        daily,
        weekly,
        tactical_min_observations=20,
        medium_min_observations=60,
        structural_min_observations=30,
    )

    assert result.tactical_daily.status == "ok"
    assert result.tactical_daily.observations == TACTICAL_DAILY_WINDOW
    assert result.medium_daily.status == "ok"
    assert result.medium_daily.observations == MEDIUM_DAILY_WINDOW
    assert result.structural_weekly.status == "ok"
    assert result.structural_weekly.window == STRUCTURAL_WEEKLY_WINDOW
    assert result.structural_weekly.observations == len(weekly)


def test_correlation_reports_complete_case_drops_and_degenerate_variance() -> None:
    daily, _benchmark = _correlation_fixture(rows=30)
    daily.loc[daily.index[-1], "AAA"] = np.nan
    result = correlation_matrix(daily, min_observations=20)

    assert result.status == "ok"
    assert result.input_observations == 30
    assert result.observations == 29
    assert result.dropped_observations == 1

    degenerate = pd.DataFrame(
        {
            "AAA": np.ones(20),
            "BBB": np.linspace(-0.01, 0.01, 20),
        }
    )
    rejected = correlation_matrix(degenerate, min_observations=10)
    assert rejected.status == "degenerate_variance"
    assert rejected.matrix is None


def test_downside_and_stress_correlations_fail_closed_on_small_samples() -> None:
    daily, benchmark = _correlation_fixture(rows=40)
    downside = downside_correlation(daily, benchmark, min_observations=10)
    assert downside.status == "ok"
    assert downside.threshold == 0.0
    assert downside.observations >= 10

    stress = stress_correlation(
        daily,
        benchmark,
        quantile=0.10,
        min_observations=8,
    )
    assert stress.status == "insufficient_observations"
    assert stress.matrix is None
    assert stress.observations < 8


def test_correlation_minimum_is_caller_policy_not_hidden_default() -> None:
    daily, _benchmark = _correlation_fixture(rows=15)
    insufficient = correlation_matrix(daily, min_observations=20)
    accepted = correlation_matrix(daily, min_observations=10)

    assert insufficient.status == "insufficient_observations"
    assert accepted.status == "ok"
