from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apps.api.app.quant.factors import (
    US_FACTOR_COLUMNS,
    boundary_safe_monthly_returns,
    factor_implied_relationship,
    fit_us_factor_exposure,
)


def _factor_fixture(months: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(20260811)
    index = pd.date_range("2020-01-31", periods=months, freq="ME")
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


def _asset_returns(
    factors: pd.DataFrame,
    beta: np.ndarray,
) -> pd.Series:
    values = (
        factors["RF"].to_numpy(dtype=float)
        + factors[list(US_FACTOR_COLUMNS)].to_numpy(dtype=float) @ beta
    )
    return pd.Series(values, index=factors.index, dtype=float)


def test_boundary_month_policy_excludes_first_and_last_represented_periods() -> None:
    daily = pd.Series(
        [0.50, 0.10, 0.10, 0.20, 0.30],
        index=pd.to_datetime(
            [
                "2024-01-17",
                "2024-02-01",
                "2024-02-02",
                "2024-03-15",
                "2024-04-08",
            ]
        ),
    )

    monthly = boundary_safe_monthly_returns(daily)

    assert list(monthly.index) == [
        pd.Timestamp("2024-02-29"),
        pd.Timestamp("2024-03-31"),
    ]
    assert monthly.loc[pd.Timestamp("2024-02-29")] == pytest.approx(0.21)
    assert monthly.loc[pd.Timestamp("2024-03-31")] == pytest.approx(0.20)
    # January and April factor rows could exist, but the asset boundary periods
    # are deliberately excluded rather than being treated as complete months.
    assert pd.Timestamp("2024-01-31") not in monthly.index
    assert pd.Timestamp("2024-04-30") not in monthly.index


def test_mid_month_start_and_partial_terminal_month_never_become_factor_observations() -> None:
    factors = _factor_fixture(months=40)
    represented_dates = factors.index.to_period("M").to_timestamp(how="start") + pd.Timedelta(days=14)
    native_returns = pd.Series(
        factors["RF"].to_numpy(dtype=float)
        + 0.5 * factors["MKT_RF"].to_numpy(dtype=float),
        index=represented_dates,
    )

    exposure = fit_us_factor_exposure(native_returns, factors, min_observations=36)

    assert exposure.status == "ok"
    assert exposure.observations == 38
    assert exposure.start == factors.index[1].date().isoformat()
    assert exposure.end == factors.index[-2].date().isoformat()
    assert exposure.start != factors.index[0].date().isoformat()
    assert exposure.end != factors.index[-1].date().isoformat()


def test_boundary_exclusion_can_make_factor_evidence_explicitly_insufficient() -> None:
    factors = _factor_fixture(months=37)
    native_returns = pd.Series(
        factors["RF"].to_numpy(dtype=float)
        + 0.5 * factors["MKT_RF"].to_numpy(dtype=float),
        index=factors.index,
    )

    exposure = fit_us_factor_exposure(native_returns, factors, min_observations=36)

    assert exposure.status == "insufficient_observations"
    assert exposure.observations == 35
    assert exposure.betas is None
    assert exposure.r_squared is None


def test_boundary_policy_does_not_fabricate_a_prior_return() -> None:
    daily = pd.Series(
        [0.07, 0.02, 0.03],
        index=pd.to_datetime(["2024-01-20", "2024-02-20", "2024-03-20"]),
    )

    monthly = boundary_safe_monthly_returns(daily)

    # There is no synthetic pre-January observation and therefore January is
    # excluded. Only the real interior February return remains.
    assert list(monthly.index) == [pd.Timestamp("2024-02-29")]
    assert monthly.iloc[0] == pytest.approx(0.02)


def test_systematic_relationship_refits_betas_and_sigma_f_on_one_global_common_sample() -> None:
    factors = _factor_fixture(months=60)
    beta_a = np.array([1.0, 0.2, -0.1, 0.0, 0.1, 0.3])
    beta_b = np.array([0.7, -0.1, 0.4, 0.2, -0.2, 0.1])
    asset_a = _asset_returns(factors, beta_a)
    asset_b = _asset_returns(factors.iloc[5:55], beta_b)

    relationship = factor_implied_relationship(
        {"BBB": asset_b, "AAA": asset_a},
        factors,
        min_observations=36,
    )

    expected_common = factors.iloc[6:54]
    assert relationship.status == "ok"
    assert relationship.symbols == ("AAA", "BBB")
    assert relationship.observations == 48
    assert relationship.start == expected_common.index[0].date().isoformat()
    assert relationship.end == expected_common.index[-1].date().isoformat()
    assert relationship.sample_fingerprint_sha256 is not None
    assert relationship.covariance is not None
    assert relationship.correlation is not None

    sigma_f = np.cov(
        expected_common[list(US_FACTOR_COLUMNS)].to_numpy(dtype=float),
        rowvar=False,
        ddof=1,
    )
    beta_matrix = np.vstack([beta_a, beta_b])
    expected_covariance = beta_matrix @ sigma_f @ beta_matrix.T
    expected_scale = np.sqrt(np.diag(expected_covariance))
    expected_correlation = expected_covariance / np.outer(
        expected_scale,
        expected_scale,
    )
    np.testing.assert_allclose(
        relationship.covariance.to_numpy(),
        expected_covariance,
        rtol=1e-12,
        atol=1e-14,
    )
    np.testing.assert_allclose(
        relationship.correlation.to_numpy(),
        expected_correlation,
        rtol=1e-12,
        atol=1e-14,
    )


def test_individually_valid_assets_fail_closed_when_global_common_sample_is_too_short() -> None:
    factors = _factor_fixture(months=60)
    beta_a = np.array([1.0, 0.2, -0.1, 0.0, 0.1, 0.3])
    beta_b = np.array([0.7, -0.1, 0.4, 0.2, -0.2, 0.1])
    asset_a = _asset_returns(factors.iloc[:40], beta_a)
    asset_b = _asset_returns(factors.iloc[20:], beta_b)

    # Each asset retains 38 boundary-safe months and is individually valid, but
    # the global intersection is only factors[21:39] => 18 observations.
    assert fit_us_factor_exposure(asset_a, factors, min_observations=36).status == "ok"
    assert fit_us_factor_exposure(asset_b, factors, min_observations=36).status == "ok"

    relationship = factor_implied_relationship(
        {"AAA": asset_a, "BBB": asset_b},
        factors,
        min_observations=36,
    )

    assert relationship.status == "insufficient_common_observations"
    assert relationship.observations == 18
    assert relationship.start == factors.index[21].date().isoformat()
    assert relationship.end == factors.index[38].date().isoformat()
    assert relationship.sample_fingerprint_sha256 is not None
    assert relationship.covariance is None
    assert relationship.correlation is None


def test_relationship_sample_and_matrix_are_invariant_to_symbol_request_order() -> None:
    factors = _factor_fixture(months=60)
    beta_a = np.array([1.0, 0.2, -0.1, 0.0, 0.1, 0.3])
    beta_b = np.array([0.7, -0.1, 0.4, 0.2, -0.2, 0.1])
    asset_a = _asset_returns(factors, beta_a)
    asset_b = _asset_returns(factors.iloc[5:55], beta_b)

    first = factor_implied_relationship(
        {"AAA": asset_a, "BBB": asset_b},
        factors,
        min_observations=36,
    )
    second = factor_implied_relationship(
        {"BBB": asset_b, "AAA": asset_a},
        factors,
        min_observations=36,
    )

    assert first.status == second.status == "ok"
    assert first.symbols == second.symbols == ("AAA", "BBB")
    assert first.observations == second.observations
    assert first.start == second.start
    assert first.end == second.end
    assert first.sample_fingerprint_sha256 == second.sample_fingerprint_sha256
    assert first.covariance is not None and second.covariance is not None
    assert first.correlation is not None and second.correlation is not None
    pd.testing.assert_frame_equal(first.covariance, second.covariance)
    pd.testing.assert_frame_equal(first.correlation, second.correlation)
