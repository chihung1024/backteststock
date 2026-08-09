"""Portfolio risk-decomposition and effective-dimension primitives."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

_NUMERICAL_EPSILON = 1e-15
_WEIGHT_SUM_TOLERANCE = 1e-8
_SYMMETRY_TOLERANCE = 1e-10


@dataclass(frozen=True, slots=True)
class RiskContributionResult:
    status: str
    volatility: float
    marginal: np.ndarray | None
    component: np.ndarray | None


@dataclass(frozen=True, slots=True)
class EffectiveDimensionResult:
    entropy_effective_rank: float | None
    participation_ratio: float | None
    positive_eigenvalues: tuple[float, ...]


def portfolio_variance(weights: np.ndarray, covariance: np.ndarray) -> float:
    w, cov = _validated_weights_and_covariance(weights, covariance)
    variance = float(w @ cov @ w)
    tolerance = _matrix_scale(cov) * 1e-12
    if variance < -tolerance:
        raise ValueError("portfolio variance is materially negative")
    return max(variance, 0.0)


def portfolio_volatility(weights: np.ndarray, covariance: np.ndarray) -> float:
    return math.sqrt(portfolio_variance(weights, covariance))


def risk_contributions(
    weights: np.ndarray,
    covariance: np.ndarray,
) -> RiskContributionResult:
    """Return signed marginal/component risk contributions.

    For non-zero portfolio volatility, the Euler decomposition satisfies
    `sum(component) == volatility` within numerical tolerance.  Negative
    component contributions remain negative and are not hidden.
    """

    w, cov = _validated_weights_and_covariance(weights, covariance)
    variance = portfolio_variance(w, cov)
    volatility = math.sqrt(variance)
    if volatility <= _NUMERICAL_EPSILON:
        return RiskContributionResult(
            status="zero_volatility",
            volatility=0.0,
            marginal=None,
            component=None,
        )
    marginal = (cov @ w) / volatility
    component = w * marginal
    return RiskContributionResult(
        status="ok",
        volatility=volatility,
        marginal=np.asarray(marginal, dtype=float),
        component=np.asarray(component, dtype=float),
    )


def diversification_ratio(
    weights: np.ndarray,
    covariance: np.ndarray,
) -> float | None:
    """Return Choueifaty-style diversification ratio for the supplied covariance."""

    w, cov = _validated_weights_and_covariance(weights, covariance)
    volatility = portfolio_volatility(w, cov)
    if volatility <= _NUMERICAL_EPSILON:
        return None
    diagonal = np.diag(cov)
    tolerance = _matrix_scale(cov) * 1e-12
    if np.any(diagonal < -tolerance):
        raise ValueError("covariance diagonal contains materially negative variance")
    asset_volatility = np.sqrt(np.clip(diagonal, 0.0, None))
    numerator = float(w @ asset_volatility)
    return numerator / volatility


def weight_effective_holdings(weights: np.ndarray) -> float:
    w = _validated_weights(weights)
    concentration = float(np.sum(w**2))
    if concentration <= _NUMERICAL_EPSILON:
        raise ValueError("weight concentration is numerically zero")
    return 1.0 / concentration


def gross_risk_contribution_equivalent_holdings(
    component_risk: np.ndarray | None,
) -> float | None:
    """Return inverse-HHI count from absolute RC shares.

    This deliberately does not erase signed RC from the main risk report; it is
    a separate *gross* concentration diagnostic only.
    """

    if component_risk is None:
        return None
    component = np.asarray(component_risk, dtype=float)
    if component.ndim != 1 or component.size < 1 or not np.isfinite(component).all():
        raise ValueError("component_risk must be a finite non-empty vector")
    gross = float(np.sum(np.abs(component)))
    if gross <= _NUMERICAL_EPSILON:
        return None
    shares = np.abs(component) / gross
    return 1.0 / float(np.sum(shares**2))


def effective_dimensions(
    matrix: np.ndarray,
    *,
    relative_tolerance: float = 1e-12,
) -> EffectiveDimensionResult:
    """Return entropy effective rank and participation ratio of a PSD matrix."""

    value = np.asarray(matrix, dtype=float)
    if value.ndim != 2 or value.shape[0] != value.shape[1] or value.shape[0] < 1:
        raise ValueError("matrix must be a non-empty square matrix")
    if not np.isfinite(value).all():
        raise ValueError("matrix must contain only finite values")
    if not math.isfinite(relative_tolerance) or relative_tolerance <= 0.0:
        raise ValueError("relative_tolerance must be positive and finite")
    symmetry_error = float(np.max(np.abs(value - value.T)))
    tolerance = max(float(np.max(np.abs(value))), 1.0) * relative_tolerance
    if symmetry_error > tolerance:
        raise ValueError("matrix is not symmetric within tolerance")

    eigenvalues = np.linalg.eigvalsh((value + value.T) / 2.0)
    if float(eigenvalues[0]) < -tolerance:
        raise ValueError("matrix is not positive semidefinite within tolerance")
    positive = np.clip(eigenvalues, 0.0, None)
    total = float(positive.sum())
    if total <= _NUMERICAL_EPSILON:
        return EffectiveDimensionResult(
            entropy_effective_rank=None,
            participation_ratio=None,
            positive_eigenvalues=tuple(float(item) for item in positive),
        )

    probabilities = positive / total
    nonzero = probabilities > 0.0
    entropy = -float(np.sum(probabilities[nonzero] * np.log(probabilities[nonzero])))
    entropy_rank = math.exp(entropy)
    participation = total**2 / float(np.sum(positive**2))
    return EffectiveDimensionResult(
        entropy_effective_rank=entropy_rank,
        participation_ratio=participation,
        positive_eigenvalues=tuple(float(item) for item in positive),
    )


def _validated_weights_and_covariance(
    weights: np.ndarray,
    covariance: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    w = _validated_weights(weights)
    cov = np.asarray(covariance, dtype=float)
    if cov.ndim != 2 or cov.shape != (w.size, w.size):
        raise ValueError("covariance dimensions must match the weight vector")
    if not np.isfinite(cov).all():
        raise ValueError("covariance must contain only finite values")
    symmetry_error = float(np.max(np.abs(cov - cov.T)))
    if symmetry_error > _matrix_scale(cov) * _SYMMETRY_TOLERANCE:
        raise ValueError("covariance must be symmetric within tolerance")
    return w, (cov + cov.T) / 2.0


def _validated_weights(weights: np.ndarray) -> np.ndarray:
    value = np.asarray(weights, dtype=float)
    if value.ndim != 1 or value.size < 1:
        raise ValueError("weights must be a non-empty vector")
    if not np.isfinite(value).all():
        raise ValueError("weights must contain only finite values")
    if abs(float(value.sum()) - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError("weights must sum to 1 within tolerance")
    return value


def _matrix_scale(matrix: np.ndarray) -> float:
    return max(float(np.max(np.abs(matrix))), 1.0)
