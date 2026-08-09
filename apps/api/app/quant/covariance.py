"""Covariance estimators and diagnostics for Portfolio Refinery research.

This module is intentionally framework-neutral and has no API/UI/optimizer side
effects.  Ledoit-Wolf follows the same centered MLE covariance + shrinkage
semantics as scikit-learn's reference implementation, while scikit-learn itself
remains a dev/test-only dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Mapping

import numpy as np
import pandas as pd

RISK_MATH_CONTRACT_VERSION = "risk-math-twd-2026-08-09.1"
_NUMERICAL_EPSILON = 1e-15


@dataclass(frozen=True, slots=True)
class CovarianceEstimate:
    method: str
    covariance: np.ndarray
    observations: int
    features: int
    annualization: float
    shrinkage: float | None = None


@dataclass(frozen=True, slots=True)
class CovarianceDiagnostics:
    observations: int
    features: int
    symmetry_error: float
    tolerance: float
    min_eigenvalue: float
    max_eigenvalue: float
    is_psd: bool
    numerical_rank: int
    condition_number: float


@dataclass(frozen=True, slots=True)
class EstimatorDispersion:
    pairwise_relative_frobenius: dict[str, float]
    maximum_relative_frobenius: float


def sample_covariance(
    returns: pd.DataFrame | np.ndarray,
    *,
    annualization: float = 1.0,
) -> CovarianceEstimate:
    """Return the conventional unbiased sample covariance (`ddof=1`)."""

    matrix = _return_matrix(returns)
    scale = _positive_scale(annualization)
    observations, features = matrix.shape
    if features == 1:
        covariance = np.array([[np.var(matrix[:, 0], ddof=1)]], dtype=float)
    else:
        covariance = np.asarray(np.cov(matrix, rowvar=False, ddof=1), dtype=float)
    covariance *= scale
    return CovarianceEstimate(
        method="sample-unbiased-ddof1",
        covariance=covariance,
        observations=observations,
        features=features,
        annualization=scale,
    )


def ledoit_wolf_covariance(
    returns: pd.DataFrame | np.ndarray,
    *,
    assume_centered: bool = False,
    annualization: float = 1.0,
) -> CovarianceEstimate:
    """Return Ledoit-Wolf shrinkage covariance without a runtime sklearn dependency.

    The implementation matches the reference estimator's empirical covariance
    convention: centered MLE covariance (`1/n`) and shrinkage toward
    `mu * I`, where `mu = trace(empirical_covariance) / p`.
    """

    matrix = _return_matrix(returns)
    scale = _positive_scale(annualization)
    observations, features = matrix.shape
    centered = matrix.copy()
    if not assume_centered:
        centered -= centered.mean(axis=0)

    empirical = (centered.T @ centered) / observations
    empirical = np.atleast_2d(np.asarray(empirical, dtype=float))
    if features == 1:
        shrinkage = 0.0
        covariance = empirical
    else:
        squared = centered**2
        empirical_trace = squared.sum(axis=0) / observations
        mu = float(empirical_trace.sum() / features)

        beta_sum = float(np.sum(squared.T @ squared))
        delta_sum = float(np.sum((centered.T @ centered) ** 2)) / observations**2
        beta = (beta_sum / observations - delta_sum) / (features * observations)
        delta = (
            delta_sum
            - 2.0 * mu * float(empirical_trace.sum())
            + features * mu**2
        ) / features
        beta = min(beta, delta)
        shrinkage = 0.0 if beta == 0.0 else float(beta / delta)

        covariance = (1.0 - shrinkage) * empirical
        covariance = covariance.copy()
        covariance.flat[:: features + 1] += shrinkage * mu

    covariance = np.asarray(covariance, dtype=float) * scale
    return CovarianceEstimate(
        method="ledoit-wolf-mle-spherical-target",
        covariance=covariance,
        observations=observations,
        features=features,
        annualization=scale,
        shrinkage=float(shrinkage),
    )


def ewma_covariance(
    returns: pd.DataFrame | np.ndarray,
    *,
    decay: float,
    assume_centered: bool = False,
    annualization: float = 1.0,
) -> CovarianceEstimate:
    """Return an explicit-decay exponentially weighted population covariance.

    No universal decay constant is embedded in the risk core.  Callers must
    choose and record the decay.  When `assume_centered=False`, observations are
    centered around their exponentially weighted mean.
    """

    matrix = _return_matrix(returns)
    scale = _positive_scale(annualization)
    if not math.isfinite(decay) or not 0.0 < decay < 1.0:
        raise ValueError("EWMA decay must be finite and strictly between 0 and 1")

    observations, features = matrix.shape
    exponents = np.arange(observations - 1, -1, -1, dtype=float)
    weights = decay**exponents
    weights /= weights.sum()

    centered = matrix.copy()
    if not assume_centered:
        weighted_mean = np.sum(centered * weights[:, None], axis=0)
        centered -= weighted_mean
    weighted = centered * np.sqrt(weights)[:, None]
    covariance = weighted.T @ weighted
    covariance = np.atleast_2d(np.asarray(covariance, dtype=float)) * scale
    return CovarianceEstimate(
        method=f"ewma-weighted-population-decay-{decay:.12g}",
        covariance=covariance,
        observations=observations,
        features=features,
        annualization=scale,
    )


def covariance_diagnostics(
    covariance: np.ndarray,
    *,
    observations: int,
    relative_tolerance: float = 1e-12,
) -> CovarianceDiagnostics:
    """Return numerical reliability diagnostics without repairing the matrix."""

    matrix = _square_finite_matrix(covariance)
    if observations < 0:
        raise ValueError("observations must be non-negative")
    if not math.isfinite(relative_tolerance) or relative_tolerance <= 0.0:
        raise ValueError("relative_tolerance must be positive and finite")

    symmetry_error = float(np.max(np.abs(matrix - matrix.T)))
    scale = max(float(np.max(np.abs(matrix))), _NUMERICAL_EPSILON)
    tolerance = relative_tolerance * scale
    symmetric = (matrix + matrix.T) / 2.0
    eigenvalues = np.linalg.eigvalsh(symmetric)
    min_eigenvalue = float(eigenvalues[0])
    max_eigenvalue = float(eigenvalues[-1])
    is_psd = min_eigenvalue >= -tolerance
    numerical_rank = int(np.sum(eigenvalues > tolerance))
    if min_eigenvalue <= tolerance or max_eigenvalue <= tolerance:
        condition_number = math.inf
    else:
        condition_number = float(max_eigenvalue / min_eigenvalue)

    return CovarianceDiagnostics(
        observations=int(observations),
        features=int(matrix.shape[0]),
        symmetry_error=symmetry_error,
        tolerance=tolerance,
        min_eigenvalue=min_eigenvalue,
        max_eigenvalue=max_eigenvalue,
        is_psd=bool(is_psd and symmetry_error <= tolerance),
        numerical_rank=numerical_rank,
        condition_number=condition_number,
    )


def estimator_dispersion(
    estimates: Mapping[str, CovarianceEstimate | np.ndarray],
) -> EstimatorDispersion:
    """Compare estimators using scale-normalized pairwise Frobenius distance."""

    if len(estimates) < 2:
        raise ValueError("at least two covariance estimates are required")
    matrices = {
        str(name): _square_finite_matrix(
            estimate.covariance if isinstance(estimate, CovarianceEstimate) else estimate
        )
        for name, estimate in estimates.items()
    }
    shapes = {matrix.shape for matrix in matrices.values()}
    if len(shapes) != 1:
        raise ValueError("all covariance estimates must have the same shape")

    pairwise: dict[str, float] = {}
    for left, right in combinations(sorted(matrices), 2):
        left_matrix = matrices[left]
        right_matrix = matrices[right]
        denominator = max(
            float(np.linalg.norm(left_matrix, ord="fro")),
            float(np.linalg.norm(right_matrix, ord="fro")),
            _NUMERICAL_EPSILON,
        )
        distance = float(np.linalg.norm(left_matrix - right_matrix, ord="fro"))
        pairwise[f"{left}::{right}"] = distance / denominator

    return EstimatorDispersion(
        pairwise_relative_frobenius=pairwise,
        maximum_relative_frobenius=max(pairwise.values(), default=0.0),
    )


def _return_matrix(returns: pd.DataFrame | np.ndarray) -> np.ndarray:
    matrix = (
        returns.to_numpy(dtype=float, copy=True)
        if isinstance(returns, pd.DataFrame)
        else np.asarray(returns, dtype=float)
    )
    if matrix.ndim == 1:
        matrix = matrix.reshape(-1, 1)
    if matrix.ndim != 2:
        raise ValueError("returns must be a 2D samples-by-assets matrix")
    if matrix.shape[0] < 2:
        raise ValueError("at least two return observations are required")
    if matrix.shape[1] < 1:
        raise ValueError("at least one asset is required")
    if not np.isfinite(matrix).all():
        raise ValueError("returns must contain only finite observations")
    return matrix


def _square_finite_matrix(matrix: np.ndarray) -> np.ndarray:
    value = np.asarray(matrix, dtype=float)
    if value.ndim != 2 or value.shape[0] != value.shape[1] or value.shape[0] < 1:
        raise ValueError("covariance must be a non-empty square matrix")
    if not np.isfinite(value).all():
        raise ValueError("covariance must contain only finite values")
    return value


def _positive_scale(value: float) -> float:
    scale = float(value)
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("annualization must be positive and finite")
    return scale
