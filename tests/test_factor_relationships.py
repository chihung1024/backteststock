from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apps.api.app.portfolio.analytics_data import (
    FRENCH_FACTOR_SOURCE as PORTFOLIO_FRENCH_SOURCE,
)
from apps.api.app.portfolio.analytics_data import (
    FrenchFactorProvider as PortfolioFrenchFactorProvider,
)
from apps.api.app.portfolio.analytics_data import (
    parse_monthly_factor_text as portfolio_parse_monthly_factor_text,
)
from apps.api.app.quant.factors import (
    US_FACTOR_COLUMNS,
    boundary_safe_monthly_returns,
    factor_implied_relationship,
    fit_us_factor_exposure,
)
from apps.api.app.research.factor_data import (
    FRENCH_FACTOR_SOURCE,
    FrenchFactorProvider,
    parse_monthly_factor_text,
)


def _factor_fixture(months: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(20260810)
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


def test_portfolio_factor_adapter_is_shared_reexport_not_second_authority() -> None:
    assert PortfolioFrenchFactorProvider is FrenchFactorProvider
    assert PORTFOLIO_FRENCH_SOURCE == FRENCH_FACTOR_SOURCE
    assert portfolio_parse_monthly_factor_text is parse_monthly_factor_text


def test_shared_factor_parser_preserves_official_monthly_percent_rows() -> None:
    text = """Description\n,Mkt-RF,SMB,HML,RMW,CMA,RF\n202601,1.00,2.00,-1.00,0.50,0.25,0.10\n202602,2.00,1.00,-0.50,0.25,0.10,0.10\nAnnual Factors: January-December\n"""
    parsed = parse_monthly_factor_text(text)

    assert list(parsed.index) == [pd.Timestamp("2026-01-31"), pd.Timestamp("2026-02-28")]
    assert parsed.loc[pd.Timestamp("2026-01-31"), "Mkt-RF"] == pytest.approx(1.0)
    assert parsed.loc[pd.Timestamp("2026-02-28"), "RF"] == pytest.approx(0.10)


def test_factor_exposure_recovers_known_native_return_betas() -> None:
    factors = _factor_fixture()
    beta = np.array([1.10, 0.30, -0.20, 0.15, -0.10, 0.40])
    intercept = 0.002
    asset_return = (
        factors["RF"].to_numpy()
        + intercept
        + factors[list(US_FACTOR_COLUMNS)].to_numpy() @ beta
    )
    native_returns = pd.Series(asset_return, index=factors.index, name="native")

    result = fit_us_factor_exposure(native_returns, factors, min_observations=36)

    assert result.status == "ok"
    assert result.observations == len(factors) - 2
    assert result.start == factors.index[1].date().isoformat()
    assert result.end == factors.index[-2].date().isoformat()
    assert result.intercept_monthly == pytest.approx(intercept, abs=1e-12)
    assert result.r_squared == pytest.approx(1.0, abs=1e-12)
    assert result.betas is not None
    np.testing.assert_allclose(
        np.array([result.betas[name] for name in US_FACTOR_COLUMNS]),
        beta,
        rtol=0.0,
        atol=1e-12,
    )


def test_factor_exposure_fails_closed_on_insufficient_months() -> None:
    factors = _factor_fixture(months=24)
    native_returns = pd.Series(
        factors["RF"].to_numpy() + 0.5 * factors["MKT_RF"].to_numpy(),
        index=factors.index,
    )

    result = fit_us_factor_exposure(native_returns, factors, min_observations=36)

    assert result.status == "insufficient_observations"
    assert result.observations == 22
    assert result.betas is None
    assert result.r_squared is None


def test_factor_implied_covariance_and_correlation_match_matrix_formula() -> None:
    factors = _factor_fixture()
    beta_a = np.array([1.0, 0.2, -0.1, 0.0, 0.1, 0.3])
    beta_b = np.array([0.7, -0.1, 0.4, 0.2, -0.2, 0.1])
    asset_a = pd.Series(
        factors["RF"].to_numpy()
        + factors[list(US_FACTOR_COLUMNS)].to_numpy() @ beta_a,
        index=factors.index,
    )
    asset_b = pd.Series(
        factors["RF"].to_numpy()
        + factors[list(US_FACTOR_COLUMNS)].to_numpy() @ beta_b,
        index=factors.index,
    )

    result = factor_implied_relationship(
        {"BBB": asset_b, "AAA": asset_a},
        factors,
        min_observations=36,
    )

    assert result.status == "ok"
    assert result.symbols == ("AAA", "BBB")
    assert result.observations == len(factors) - 2
    assert result.start == factors.index[1].date().isoformat()
    assert result.end == factors.index[-2].date().isoformat()
    assert result.sample_fingerprint_sha256 is not None
    assert result.covariance is not None
    assert result.correlation is not None
    common_factors = factors.iloc[1:-1]
    sigma_f = np.cov(
        common_factors[list(US_FACTOR_COLUMNS)].to_numpy(),
        rowvar=False,
        ddof=1,
    )
    beta_matrix = np.vstack([beta_a, beta_b])
    expected_covariance = beta_matrix @ sigma_f @ beta_matrix.T
    expected_scale = np.sqrt(np.diag(expected_covariance))
    expected_correlation = expected_covariance / np.outer(expected_scale, expected_scale)

    np.testing.assert_allclose(
        result.covariance.to_numpy(), expected_covariance, rtol=1e-13, atol=1e-15
    )
    np.testing.assert_allclose(
        result.correlation.to_numpy(), expected_correlation, rtol=1e-13, atol=1e-15
    )


def test_factor_implied_relationship_excludes_non_ok_exposures_explicitly() -> None:
    factors = _factor_fixture()
    valid = pd.Series(
        factors["RF"].to_numpy() + 0.5 * factors["MKT_RF"].to_numpy(),
        index=factors.index,
    )
    short_factors = factors.iloc[:20]
    unavailable = pd.Series(
        short_factors["RF"].to_numpy()
        + 0.5 * short_factors["MKT_RF"].to_numpy(),
        index=short_factors.index,
    )

    result = factor_implied_relationship(
        {"AAA": valid, "NON_US_OR_SHORT": unavailable},
        factors,
        min_observations=36,
    )

    assert result.status == "insufficient_assets"
    assert result.symbols == ("AAA",)
    assert result.observations == 0
    assert result.sample_fingerprint_sha256 is None
    assert result.covariance is None
    assert result.correlation is None
