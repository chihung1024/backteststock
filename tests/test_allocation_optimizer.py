from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apps.api.app.quant.allocation import (
    ALLOCATION_COVARIANCE_ANNUALIZATION,
    ALLOCATION_MIN_COMPLETE_CASE_OBSERVATIONS,
    allocate_weights_from_returns,
)
from apps.api.app.quant.covariance import ledoit_wolf_covariance
from apps.api.app.quant.risk import risk_contributions


def _training_returns(observations: int = 180) -> pd.DataFrame:
    rng = np.random.default_rng(42017)
    factor_a = rng.normal(0.0004, 0.010, observations)
    factor_b = rng.normal(0.0001, 0.007, observations)
    idio = rng.normal(0.0, 1.0, (observations, 3))
    return pd.DataFrame(
        {
            "AAA": 0.75 * factor_a + 0.20 * factor_b + 0.004 * idio[:, 0],
            "BBB": 0.20 * factor_a + 0.80 * factor_b + 0.009 * idio[:, 1],
            "CCC": -0.15 * factor_a + 0.35 * factor_b + 0.013 * idio[:, 2],
        }
    )


def test_equal_allocation_is_data_independent_and_fully_invested() -> None:
    returns = pd.DataFrame(
        {
            "AAA": [0.01, np.nan],
            "BBB": [np.nan, 0.02],
            "CCC": [0.00, 0.01],
        }
    )

    result = allocate_weights_from_returns(returns, method="equal")

    assert result.weights == pytest.approx((1 / 3, 1 / 3, 1 / 3))
    assert result.complete_case_observations == 0
    assert result.covariance_method is None
    assert result.status == "ok"


def test_inverse_volatility_uses_formal_ledoit_wolf_covariance() -> None:
    returns = _training_returns()
    result = allocate_weights_from_returns(returns, method="inverse_volatility")
    estimate = ledoit_wolf_covariance(
        returns,
        annualization=ALLOCATION_COVARIANCE_ANNUALIZATION,
    )
    inverse = 1.0 / np.sqrt(np.diag(estimate.covariance))
    expected = inverse / inverse.sum()

    assert result.weights == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert result.covariance_method == estimate.method
    assert result.covariance_shrinkage == pytest.approx(estimate.shrinkage)
    assert result.covariance_is_psd is True
    assert sum(result.weights) == pytest.approx(1.0)
    assert all(weight > 0.0 for weight in result.weights)


def test_erc_equalizes_signed_component_risk_and_is_permutation_invariant() -> None:
    returns = _training_returns()
    result = allocate_weights_from_returns(returns, method="risk_parity_erc")

    estimate = ledoit_wolf_covariance(
        returns,
        annualization=ALLOCATION_COVARIANCE_ANNUALIZATION,
    )
    risk = risk_contributions(np.asarray(result.weights), estimate.covariance)
    assert risk.component is not None
    shares = risk.component / risk.volatility

    assert shares == pytest.approx(np.full(3, 1 / 3), abs=1e-8)
    assert result.max_abs_risk_budget_error is not None
    assert result.max_abs_risk_budget_error <= 1e-8
    assert result.iterations is not None and result.iterations > 0

    permuted = returns[["CCC", "AAA", "BBB"]]
    permuted_result = allocate_weights_from_returns(
        permuted,
        method="risk_parity_erc",
    )
    permuted_by_symbol = dict(zip(permuted.columns, permuted_result.weights, strict=True))
    original_by_symbol = dict(zip(returns.columns, result.weights, strict=True))
    assert permuted_by_symbol == pytest.approx(original_by_symbol, abs=1e-10)


def test_risk_allocations_ignore_incomplete_rows_but_fail_closed_below_minimum() -> None:
    returns = _training_returns(ALLOCATION_MIN_COMPLETE_CASE_OBSERVATIONS + 5)
    returns.loc[0:4, "BBB"] = np.nan
    result = allocate_weights_from_returns(returns, method="inverse_volatility")
    assert result.complete_case_observations == ALLOCATION_MIN_COMPLETE_CASE_OBSERVATIONS

    returns.loc[5, "BBB"] = np.nan
    with pytest.raises(ValueError, match="at least 60 finite complete-case"):
        allocate_weights_from_returns(returns, method="inverse_volatility")


def test_single_asset_risk_methods_resolve_to_full_weight_without_covariance() -> None:
    returns = pd.DataFrame({"AAA": [0.01]})

    for method in ("inverse_volatility", "risk_parity_erc"):
        result = allocate_weights_from_returns(returns, method=method)
        assert result.weights == (1.0,)
        assert result.status == "single_asset"
        assert result.covariance_method is None


def test_risk_allocation_weights_are_invariant_to_common_return_unit_scaling() -> None:
    returns = _training_returns()

    for method in ("inverse_volatility", "risk_parity_erc"):
        baseline = allocate_weights_from_returns(returns, method=method)
        scaled = allocate_weights_from_returns(returns * 100.0, method=method)
        assert scaled.weights == pytest.approx(baseline.weights, abs=1e-10)
