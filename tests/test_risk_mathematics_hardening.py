from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.covariance import ledoit_wolf as sklearn_ledoit_wolf

from apps.api.app.quant.correlation import downside_correlation
from apps.api.app.quant.covariance import covariance_diagnostics
from apps.api.app.quant.risk import effective_dimensions, portfolio_variance

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "risk_math_v1.json"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_golden_fixture_is_anchored_to_numpy_and_sklearn_references() -> None:
    fixture = _fixture()
    returns = np.asarray(fixture["returns"], dtype=float)

    expected_sample = np.cov(returns, rowvar=False, ddof=1)
    expected_lw, expected_shrinkage = sklearn_ledoit_wolf(
        returns,
        assume_centered=False,
    )

    np.testing.assert_allclose(
        np.asarray(fixture["sampleCovariance"], dtype=float),
        expected_sample,
        rtol=1e-13,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        np.asarray(fixture["ledoitWolfCovariance"], dtype=float),
        expected_lw,
        rtol=1e-13,
        atol=1e-15,
    )
    assert fixture["ledoitWolfShrinkage"] == pytest.approx(
        expected_shrinkage,
        rel=1e-13,
        abs=1e-15,
    )


def test_covariance_diagnostics_keep_relative_scale_for_small_matrices() -> None:
    base = np.array([[4.0, 1.0], [1.0, 2.0]], dtype=float)
    tiny = base * 1e-14

    base_report = covariance_diagnostics(base, observations=100)
    tiny_report = covariance_diagnostics(tiny, observations=100)

    assert base_report.is_psd
    assert tiny_report.is_psd
    assert base_report.numerical_rank == 2
    assert tiny_report.numerical_rank == 2
    assert tiny_report.condition_number == pytest.approx(
        base_report.condition_number,
        rel=1e-12,
    )


def test_effective_dimensions_are_invariant_to_positive_matrix_scale() -> None:
    base = np.array([[1.0, 0.3], [0.3, 0.5]], dtype=float)
    tiny = base * 1e-14

    base_result = effective_dimensions(base)
    tiny_result = effective_dimensions(tiny)

    assert tiny_result.entropy_effective_rank == pytest.approx(
        base_result.entropy_effective_rank,
        rel=1e-12,
    )
    assert tiny_result.participation_ratio == pytest.approx(
        base_result.participation_ratio,
        rel=1e-12,
    )


def test_materially_negative_tiny_portfolio_variance_is_not_clipped_to_zero() -> None:
    covariance = np.array([[-1e-14, 0.0], [0.0, 1e-14]], dtype=float)
    weights = np.array([0.9, 0.1], dtype=float)

    with pytest.raises(ValueError, match="materially negative"):
        portfolio_variance(weights, covariance)


def test_conditional_correlation_counts_only_condition_eligible_rows_as_input() -> None:
    index = pd.date_range("2026-01-01", periods=6, freq="D")
    returns = pd.DataFrame(
        {
            "__risk_benchmark__": [-0.02, 0.01, np.nan, -0.01, 0.02, -0.03],
            "BBB": [-0.01, 0.02, -0.005, 0.004, 0.01, -0.02],
        },
        index=index,
    )
    benchmark = pd.Series(
        [-0.03, 0.01, -0.02, -0.01, 0.02, -0.04],
        index=index,
        name="benchmark",
    )

    result = downside_correlation(returns, benchmark, min_observations=2)

    assert result.status == "ok"
    assert result.input_observations == 4
    assert result.observations == 3
    assert result.dropped_observations == 1
    assert result.matrix is not None
    assert list(result.matrix.columns) == ["__risk_benchmark__", "BBB"]
