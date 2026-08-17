"""Training-return allocation primitives for Optimizer Hub.

This module consumes the existing ResearchDataset TWD return semantics and the
existing Risk Mathematics covariance/risk authorities. It does not fetch market
data, perform selection, or execute an OOS portfolio.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from apps.api.app.quant.covariance import (
    RISK_MATH_CONTRACT_VERSION,
    covariance_diagnostics,
    ledoit_wolf_covariance,
)
from apps.api.app.quant.risk import risk_contributions

ALLOCATION_CONTRACT_VERSION = "optimizer-hub-allocation-twd-2026-08-17.1"
ALLOCATION_MIN_COMPLETE_CASE_OBSERVATIONS = 60
ALLOCATION_COVARIANCE_ANNUALIZATION = 252.0
ERC_DEFAULT_TOLERANCE = 1e-8
ERC_DEFAULT_MAX_ITERATIONS = 10_000

AllocationMethod = Literal["equal", "inverse_volatility", "risk_parity_erc"]


@dataclass(frozen=True, slots=True)
class AllocationResult:
    """One deterministic allocation and its Training-only risk evidence."""

    method: AllocationMethod
    symbols: tuple[str, ...]
    weights: tuple[float, ...]
    input_observations: int
    complete_case_observations: int
    minimum_complete_case_observations: int
    status: str
    covariance_method: str | None = None
    covariance_annualization: float | None = None
    covariance_shrinkage: float | None = None
    covariance_is_psd: bool | None = None
    covariance_numerical_rank: int | None = None
    covariance_condition_number: float | None = None
    portfolio_volatility: float | None = None
    component_risk: tuple[float, ...] | None = None
    risk_budget_shares: tuple[float, ...] | None = None
    iterations: int | None = None
    max_abs_risk_budget_error: float | None = None
    contract_version: str = ALLOCATION_CONTRACT_VERSION

    def export_payload(self) -> dict[str, Any]:
        return {
            "contractVersion": self.contract_version,
            "riskMathContractVersion": RISK_MATH_CONTRACT_VERSION,
            "method": self.method,
            "symbols": list(self.symbols),
            "weights": list(self.weights),
            "status": self.status,
            "inputObservations": self.input_observations,
            "completeCaseObservations": self.complete_case_observations,
            "minimumCompleteCaseObservations": self.minimum_complete_case_observations,
            "returnFrequency": "daily",
            "valuationCurrency": "TWD",
            "covariance": (
                {
                    "method": self.covariance_method,
                    "annualization": self.covariance_annualization,
                    "shrinkage": self.covariance_shrinkage,
                    "isPsd": self.covariance_is_psd,
                    "numericalRank": self.covariance_numerical_rank,
                    "conditionNumber": self.covariance_condition_number,
                }
                if self.covariance_method is not None
                else None
            ),
            "portfolioVolatility": self.portfolio_volatility,
            "componentRisk": (
                list(self.component_risk) if self.component_risk is not None else None
            ),
            "riskBudgetShares": (
                list(self.risk_budget_shares)
                if self.risk_budget_shares is not None
                else None
            ),
            "solver": (
                {
                    "algorithm": "canonical-cyclic-coordinate-risk-budgeting-v1",
                    "iterations": self.iterations,
                    "maxAbsRiskBudgetError": self.max_abs_risk_budget_error,
                    "tolerance": ERC_DEFAULT_TOLERANCE,
                    "maxIterations": ERC_DEFAULT_MAX_ITERATIONS,
                }
                if self.method == "risk_parity_erc" and self.iterations is not None
                else None
            ),
        }


def allocate_weights_from_returns(
    returns: pd.DataFrame,
    *,
    method: AllocationMethod,
    minimum_observations: int = ALLOCATION_MIN_COMPLETE_CASE_OBSERVATIONS,
    annualization: float = ALLOCATION_COVARIANCE_ANNUALIZATION,
) -> AllocationResult:
    """Allocate long-only fully-invested weights from Training-only TWD returns.

    Equal weighting is data-independent. Risk-based methods use finite
    complete-case daily returns and the existing Ledoit-Wolf covariance
    authority. Missing observations are never imputed inside the optimizer.
    Risk-based numerical work is performed in canonical symbol order so request
    column ordering cannot change a converged allocation.
    """

    if method not in {"equal", "inverse_volatility", "risk_parity_erc"}:
        raise ValueError("unsupported allocation method")
    if not isinstance(returns, pd.DataFrame):
        raise TypeError("allocation returns must be a pandas DataFrame")
    symbols = tuple(str(column) for column in returns.columns)
    if not symbols:
        raise ValueError("allocation requires at least one selected symbol")
    if len(set(symbols)) != len(symbols):
        raise ValueError("allocation symbols must be unique")
    if any(not symbol or symbol != symbol.strip().upper() for symbol in symbols):
        raise ValueError("allocation symbols must be canonical")
    if (
        not isinstance(minimum_observations, int)
        or isinstance(minimum_observations, bool)
        or minimum_observations < 2
    ):
        raise ValueError("minimum_observations must be an integer >= 2")
    scale = float(annualization)
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("allocation annualization must be positive and finite")

    numeric = returns.apply(pd.to_numeric, errors="coerce").astype(float)
    numeric = numeric.replace([np.inf, -np.inf], np.nan)
    complete = numeric.dropna(axis=0, how="any")
    input_observations = len(numeric)
    complete_case_observations = len(complete)

    if method == "equal":
        weight = 1.0 / len(symbols)
        return AllocationResult(
            method=method,
            symbols=symbols,
            weights=tuple(weight for _ in symbols),
            input_observations=input_observations,
            complete_case_observations=complete_case_observations,
            minimum_complete_case_observations=minimum_observations,
            status="ok",
        )

    if len(symbols) == 1:
        return AllocationResult(
            method=method,
            symbols=symbols,
            weights=(1.0,),
            input_observations=input_observations,
            complete_case_observations=complete_case_observations,
            minimum_complete_case_observations=minimum_observations,
            status="single_asset",
        )

    if complete_case_observations < minimum_observations:
        raise ValueError(
            "risk-based allocation requires at least "
            f"{minimum_observations} finite complete-case daily observations; "
            f"received {complete_case_observations}"
        )

    canonical_symbols = tuple(sorted(symbols))
    canonical_complete = complete.loc[:, list(canonical_symbols)]
    estimate = ledoit_wolf_covariance(canonical_complete, annualization=scale)
    diagnostics = covariance_diagnostics(
        estimate.covariance,
        observations=estimate.observations,
    )
    if not diagnostics.is_psd:
        raise ValueError("formal allocation covariance is not PSD within tolerance")

    if method == "inverse_volatility":
        canonical_weights = _inverse_volatility_weights(estimate.covariance)
        iterations = None
        max_error = None
    else:
        canonical_weights, iterations, max_error = _equal_risk_contribution_weights(
            estimate.covariance,
            tolerance=ERC_DEFAULT_TOLERANCE,
            max_iterations=ERC_DEFAULT_MAX_ITERATIONS,
        )

    risk = risk_contributions(canonical_weights, estimate.covariance)
    if risk.status != "ok" or risk.component is None or risk.volatility <= 0.0:
        raise ValueError("risk-based allocation produced unavailable portfolio risk")
    canonical_component = np.asarray(risk.component, dtype=float)
    canonical_risk_budget_shares = canonical_component / risk.volatility
    if not np.isfinite(canonical_risk_budget_shares).all():
        raise ValueError("risk-based allocation produced non-finite risk budget shares")

    weight_by_symbol = dict(zip(canonical_symbols, canonical_weights, strict=True))
    component_by_symbol = dict(zip(canonical_symbols, canonical_component, strict=True))
    share_by_symbol = dict(
        zip(canonical_symbols, canonical_risk_budget_shares, strict=True)
    )
    ordered_weights = tuple(float(weight_by_symbol[symbol]) for symbol in symbols)
    ordered_component = tuple(float(component_by_symbol[symbol]) for symbol in symbols)
    ordered_shares = tuple(float(share_by_symbol[symbol]) for symbol in symbols)

    return AllocationResult(
        method=method,
        symbols=symbols,
        weights=ordered_weights,
        input_observations=input_observations,
        complete_case_observations=complete_case_observations,
        minimum_complete_case_observations=minimum_observations,
        status="ok",
        covariance_method=estimate.method,
        covariance_annualization=estimate.annualization,
        covariance_shrinkage=estimate.shrinkage,
        covariance_is_psd=diagnostics.is_psd,
        covariance_numerical_rank=diagnostics.numerical_rank,
        covariance_condition_number=diagnostics.condition_number,
        portfolio_volatility=risk.volatility,
        component_risk=ordered_component,
        risk_budget_shares=ordered_shares,
        iterations=iterations,
        max_abs_risk_budget_error=max_error,
    )


def _inverse_volatility_weights(covariance: np.ndarray) -> np.ndarray:
    diagonal = np.diag(np.asarray(covariance, dtype=float))
    if not np.isfinite(diagonal).all() or bool((diagonal <= 0.0).any()):
        raise ValueError("inverse-volatility allocation requires positive finite variances")
    inverse = 1.0 / np.sqrt(diagonal)
    total = float(inverse.sum())
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("inverse-volatility allocation normalization failed")
    return inverse / total


def _equal_risk_contribution_weights(
    covariance: np.ndarray,
    *,
    tolerance: float,
    max_iterations: int,
) -> tuple[np.ndarray, int, float]:
    """Solve long-only equal risk budgets with cyclic coordinate descent.

    The solver minimizes the standard convex risk-budgeting objective
    ``0.5 * x'Σx - sum(b_i log(x_i))`` with equal budgets ``b_i=1/n``.
    The positive solution is normalized to unit-sum portfolio weights and then
    independently checked using the existing signed risk-contribution authority.
    """

    cov = np.asarray(covariance, dtype=float)
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1] or cov.shape[0] < 2:
        raise ValueError("ERC covariance must be a square matrix with at least two assets")
    if not np.isfinite(cov).all():
        raise ValueError("ERC covariance must contain only finite values")
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("ERC tolerance must be positive and finite")
    if not isinstance(max_iterations, int) or max_iterations < 1:
        raise ValueError("ERC max_iterations must be a positive integer")

    diagonal = np.diag(cov)
    if bool((diagonal <= 0.0).any()):
        raise ValueError("ERC requires strictly positive asset variances")

    asset_count = cov.shape[0]
    budgets = np.full(asset_count, 1.0 / asset_count, dtype=float)
    x = 1.0 / np.sqrt(diagonal)
    starting_variance = float(x @ cov @ x)
    if not math.isfinite(starting_variance) or starting_variance <= 0.0:
        raise ValueError("ERC initial portfolio variance must be positive and finite")
    x /= math.sqrt(starting_variance)

    max_error = math.inf
    for iteration in range(1, max_iterations + 1):
        for index in range(asset_count):
            diagonal_value = float(cov[index, index])
            cross = float(cov[index] @ x - diagonal_value * x[index])
            discriminant = cross * cross + 4.0 * diagonal_value * budgets[index]
            if discriminant < 0.0 or not math.isfinite(discriminant):
                raise ValueError("ERC coordinate update produced invalid discriminant")
            updated = (-cross + math.sqrt(discriminant)) / (2.0 * diagonal_value)
            if not math.isfinite(updated) or updated <= 0.0:
                raise ValueError("ERC coordinate update produced non-positive weight")
            x[index] = updated

        total = float(x.sum())
        if not math.isfinite(total) or total <= 0.0:
            raise ValueError("ERC normalization failed")
        weights = x / total
        risk = risk_contributions(weights, cov)
        if risk.status != "ok" or risk.component is None or risk.volatility <= 0.0:
            raise ValueError("ERC risk contribution check is unavailable")
        shares = np.asarray(risk.component, dtype=float) / risk.volatility
        max_error = float(np.max(np.abs(shares - budgets)))
        if max_error <= tolerance:
            return weights, iteration, max_error

    raise ValueError(
        "ERC solver did not converge within "
        f"{max_iterations} iterations; max risk-budget error={max_error:.12g}"
    )
