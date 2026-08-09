"""Read-only Portfolio Refinery service over ResearchDataset + Risk Mathematics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from apps.api.app.data.history_service import (
    HistoryFailure,
    PartialTWDHistories,
    TWDHistoryService,
)
from apps.api.app.quant import (
    MEDIUM_DAILY_WINDOW,
    RISK_MATH_CONTRACT_VERSION,
    STRUCTURAL_WEEKLY_WINDOW,
    TACTICAL_DAILY_WINDOW,
    CorrelationResult,
    covariance_diagnostics,
    diversification_ratio,
    downside_correlation,
    effective_dimensions,
    estimator_dispersion,
    ewma_covariance,
    gross_risk_contribution_equivalent_holdings,
    ledoit_wolf_covariance,
    multi_horizon_correlations,
    portfolio_variance,
    risk_contributions,
    sample_covariance,
    stress_correlation,
    weight_effective_holdings,
)
from apps.api.app.research import (
    RESEARCH_DAILY_RETURN_POLICY,
    RESEARCH_DATASET_CONTRACT_VERSION,
    RESEARCH_DATASET_HASH_ALGORITHM,
    RESEARCH_WEEKLY_POLICY,
    ResearchDataset,
    build_research_dataset,
)

from .models import (
    CONDITIONAL_MIN_OBSERVATIONS,
    DAILY_COVARIANCE_ANNUALIZATION,
    MEDIUM_MIN_OBSERVATIONS,
    MIN_DAILY_ANALYSIS_OBSERVATIONS,
    REFINERY_API_CONTRACT_VERSION,
    REFINERY_API_SCHEMA_VERSION,
    STRUCTURAL_MIN_OBSERVATIONS,
    TACTICAL_MIN_OBSERVATIONS,
    RefineryRequest,
)


@dataclass(frozen=True, slots=True)
class _PreparedResearch:
    request: RefineryRequest
    candidate_dataset: ResearchDataset
    benchmark_dataset: ResearchDataset | None
    status: str
    eligibility_reasons: tuple[str, ...]
    daily_returns: pd.DataFrame
    weekly_returns: pd.DataFrame


class RefineryService:
    """Build deterministic read-only risk diagnostics without recommendation logic."""

    def __init__(self, *, history_service: TWDHistoryService | None = None) -> None:
        self._history_service = history_service or TWDHistoryService()

    def preflight(self, request: RefineryRequest) -> dict[str, Any]:
        prepared = self._prepare(request)
        return self._base_payload(prepared, endpoint="preflight")

    def analyze(self, request: RefineryRequest) -> dict[str, Any]:
        prepared = self._prepare(request)
        payload = self._base_payload(prepared, endpoint="analyze")
        if prepared.status != "ready":
            payload["analysis"] = None
            return payload
        payload["status"] = "ok"
        payload["analysis"] = self._analysis_payload(prepared)
        return payload

    def _prepare(self, request: RefineryRequest) -> _PreparedResearch:
        batch = self._history_service.histories_partial(
            list(request.requested_market_symbols),
            request.start_date,
            request.end_date,
        )
        candidate_dataset = build_research_dataset(
            _subset_histories(batch, request.symbols),
            start=request.start_date,
            end=request.end_date,
        )
        benchmark_dataset = None
        if request.benchmark is not None:
            benchmark_dataset = build_research_dataset(
                _subset_histories(batch, (request.benchmark,)),
                start=request.start_date,
                end=request.end_date,
            )

        resolved_symbols = candidate_dataset.resolved_symbols
        daily = _finite_complete_case(
            candidate_dataset.daily_returns_twd,
            resolved_symbols,
        )
        weekly = _finite_complete_case(
            candidate_dataset.weekly_returns_twd,
            resolved_symbols,
        )
        reasons: list[str] = []
        if not candidate_dataset.is_complete:
            reasons.append("candidate_membership_incomplete")
            status = "incomplete"
        elif len(daily) < MIN_DAILY_ANALYSIS_OBSERVATIONS:
            reasons.append(
                "daily_complete_case_observations_below_"
                f"{MIN_DAILY_ANALYSIS_OBSERVATIONS}"
            )
            status = "insufficient_data"
        else:
            status = "ready"
        return _PreparedResearch(
            request=request,
            candidate_dataset=candidate_dataset,
            benchmark_dataset=benchmark_dataset,
            status=status,
            eligibility_reasons=tuple(reasons),
            daily_returns=daily,
            weekly_returns=weekly,
        )

    def _base_payload(
        self,
        prepared: _PreparedResearch,
        *,
        endpoint: str,
    ) -> dict[str, Any]:
        request = prepared.request
        candidate = prepared.candidate_dataset
        benchmark = prepared.benchmark_dataset
        benchmark_failure = None
        benchmark_status = "not_requested"
        benchmark_hash = None
        if request.benchmark is not None and benchmark is not None:
            benchmark_hash = benchmark.dataset_hash
            if request.benchmark in benchmark.failures:
                benchmark_status = "failed"
                benchmark_failure = _failure_payload(
                    benchmark.failures[request.benchmark]
                )
            else:
                benchmark_status = "ready"

        return {
            "contract_version": REFINERY_API_CONTRACT_VERSION,
            "schema_version": REFINERY_API_SCHEMA_VERSION,
            "endpoint": endpoint,
            "status": prepared.status,
            "request": {
                "symbols": list(request.symbols),
                "benchmark": request.benchmark,
                "start_date": request.start_date.isoformat(),
                "end_date": request.end_date.isoformat(),
                "weights_supplied": request.weights is not None,
                "weights": (
                    [
                        {
                            "symbol": item.symbol,
                            "weight_percent": float(item.weight_percent),
                        }
                        for item in request.weights
                    ]
                    if request.weights is not None
                    else None
                ),
                "weight_input_total_percent": request.weight_input_total_percent,
                "weight_normalization": (
                    "proportional_to_unit_sum"
                    if request.weights is not None
                    else None
                ),
                "ewma_decay": float(request.ewma_decay),
                "stress_quantile": float(request.stress_quantile),
            },
            "methodology": {
                "research_dataset_contract_version": RESEARCH_DATASET_CONTRACT_VERSION,
                "research_dataset_hash_algorithm": RESEARCH_DATASET_HASH_ALGORITHM,
                "daily_return_policy": RESEARCH_DAILY_RETURN_POLICY,
                "weekly_policy": RESEARCH_WEEKLY_POLICY,
                "risk_math_contract_version": RISK_MATH_CONTRACT_VERSION,
                "daily_covariance_annualization": DAILY_COVARIANCE_ANNUALIZATION,
                "minimum_daily_analysis_observations": MIN_DAILY_ANALYSIS_OBSERVATIONS,
                "tactical_daily_window": TACTICAL_DAILY_WINDOW,
                "tactical_minimum_observations": TACTICAL_MIN_OBSERVATIONS,
                "medium_daily_window": MEDIUM_DAILY_WINDOW,
                "medium_minimum_observations": MEDIUM_MIN_OBSERVATIONS,
                "structural_weekly_window": STRUCTURAL_WEEKLY_WINDOW,
                "structural_minimum_observations": STRUCTURAL_MIN_OBSERVATIONS,
                "conditional_minimum_observations": CONDITIONAL_MIN_OBSERVATIONS,
                "ewma_decay": float(request.ewma_decay),
                "stress_quantile": float(request.stress_quantile),
            },
            "dataset": {
                "candidate_dataset_hash": candidate.dataset_hash,
                "benchmark_dataset_hash": benchmark_hash,
                "requested_symbols": list(candidate.requested_symbols),
                "resolved_symbols": list(candidate.resolved_symbols),
                "failures": {
                    symbol: _failure_payload(failure)
                    for symbol, failure in candidate.failures.items()
                },
                "effective_start": (
                    candidate.effective_start.isoformat()
                    if candidate.effective_start
                    else None
                ),
                "effective_end": (
                    candidate.effective_end.isoformat()
                    if candidate.effective_end
                    else None
                ),
                "reference_observations": len(candidate.reference_calendar),
                "daily_return_observations": len(candidate.daily_returns_twd),
                "daily_complete_case_observations": len(prepared.daily_returns),
                "weekly_return_observations": len(candidate.weekly_returns_twd),
                "weekly_complete_case_observations": len(prepared.weekly_returns),
                "coverage": _json_safe(candidate.coverage),
                "assets": _json_safe(candidate.asset_metadata),
                "benchmark": {
                    "symbol": request.benchmark,
                    "status": benchmark_status,
                    "failure": benchmark_failure,
                    "effective_start": (
                        benchmark.effective_start.isoformat()
                        if benchmark is not None and benchmark.effective_start
                        else None
                    ),
                    "effective_end": (
                        benchmark.effective_end.isoformat()
                        if benchmark is not None and benchmark.effective_end
                        else None
                    ),
                },
            },
            "eligibility": {
                "analysis_ready": prepared.status == "ready",
                "candidate_membership_complete": candidate.is_complete,
                "reasons": list(prepared.eligibility_reasons),
            },
        }

    def _analysis_payload(self, prepared: _PreparedResearch) -> dict[str, Any]:
        request = prepared.request
        daily = prepared.daily_returns
        weekly = prepared.weekly_returns

        sample = sample_covariance(
            daily,
            annualization=DAILY_COVARIANCE_ANNUALIZATION,
        )
        ledoit_wolf = ledoit_wolf_covariance(
            daily,
            annualization=DAILY_COVARIANCE_ANNUALIZATION,
        )
        ewma = ewma_covariance(
            daily,
            decay=request.ewma_decay,
            annualization=DAILY_COVARIANCE_ANNUALIZATION,
        )
        estimates = {
            "sample": sample,
            "ledoit_wolf": ledoit_wolf,
            "ewma": ewma,
        }
        diagnostics = {
            name: covariance_diagnostics(
                estimate.covariance,
                observations=estimate.observations,
            )
            for name, estimate in estimates.items()
        }
        dispersion = estimator_dispersion(estimates)

        correlations = multi_horizon_correlations(
            daily,
            weekly,
            tactical_min_observations=TACTICAL_MIN_OBSERVATIONS,
            medium_min_observations=MEDIUM_MIN_OBSERVATIONS,
            structural_min_observations=STRUCTURAL_MIN_OBSERVATIONS,
        )
        correlation_payloads = {
            "tactical_daily": _correlation_payload(correlations.tactical_daily),
            "medium_daily": _correlation_payload(correlations.medium_daily),
            "structural_weekly": _correlation_payload(
                correlations.structural_weekly
            ),
        }
        correlation_payloads.update(self._conditional_correlations(prepared))

        covariance_dimension = effective_dimensions(ledoit_wolf.covariance)
        medium_dimension = None
        if (
            correlations.medium_daily.status == "ok"
            and correlations.medium_daily.matrix is not None
        ):
            medium_dimension = effective_dimensions(
                correlations.medium_daily.matrix.to_numpy(dtype=float)
            )

        portfolio = self._portfolio_payload(request, ledoit_wolf.covariance)
        return {
            "symbols": list(request.symbols),
            "covariance": {
                "primary_method": ledoit_wolf.method,
                "annualization": DAILY_COVARIANCE_ANNUALIZATION,
                "ledoit_wolf_shrinkage": ledoit_wolf.shrinkage,
                "estimators": {
                    name: {
                        "method": estimate.method,
                        "observations": estimate.observations,
                        "features": estimate.features,
                        "annualization": estimate.annualization,
                        "shrinkage": estimate.shrinkage,
                        "diagnostics": _covariance_diagnostics_payload(
                            diagnostics[name]
                        ),
                    }
                    for name, estimate in estimates.items()
                },
                "estimator_dispersion": {
                    "pairwise_relative_frobenius": _json_safe(
                        dispersion.pairwise_relative_frobenius
                    ),
                    "maximum_relative_frobenius": _finite_or_none(
                        dispersion.maximum_relative_frobenius
                    ),
                },
            },
            "effective_dimensions": {
                "covariance": _effective_dimension_payload(covariance_dimension),
                "medium_correlation": (
                    _effective_dimension_payload(medium_dimension)
                    if medium_dimension is not None
                    else None
                ),
            },
            "portfolio": portfolio,
            "correlations": correlation_payloads,
        }

    def _portfolio_payload(
        self,
        request: RefineryRequest,
        covariance: np.ndarray,
    ) -> dict[str, Any]:
        weights = request.weight_vector
        if weights is None:
            return {
                "status": "unavailable_weights_not_supplied",
                "weights": None,
            }
        vector = np.asarray(weights, dtype=float)
        contribution = risk_contributions(vector, covariance)
        variance = portfolio_variance(vector, covariance)
        return {
            "status": contribution.status,
            "weights": [float(value) for value in vector],
            "variance": _finite_or_none(variance),
            "volatility": _finite_or_none(contribution.volatility),
            "marginal_risk_contribution": (
                [_finite_or_none(value) for value in contribution.marginal]
                if contribution.marginal is not None
                else None
            ),
            "signed_component_risk_contribution": (
                [_finite_or_none(value) for value in contribution.component]
                if contribution.component is not None
                else None
            ),
            "diversification_ratio": _finite_or_none(
                diversification_ratio(vector, covariance)
            ),
            "weight_effective_holdings": _finite_or_none(
                weight_effective_holdings(vector)
            ),
            "gross_risk_contribution_equivalent_holdings": _finite_or_none(
                gross_risk_contribution_equivalent_holdings(contribution.component)
            ),
        }

    def _conditional_correlations(
        self,
        prepared: _PreparedResearch,
    ) -> dict[str, dict[str, Any]]:
        benchmark_symbol = prepared.request.benchmark
        benchmark_dataset = prepared.benchmark_dataset
        if benchmark_symbol is None:
            unavailable = _unavailable_correlation(
                "unavailable_benchmark_not_supplied",
                "benchmark_not_supplied",
            )
            return {"downside": unavailable, "stress": dict(unavailable)}
        if (
            benchmark_dataset is None
            or benchmark_symbol in benchmark_dataset.failures
        ):
            unavailable = _unavailable_correlation(
                "unavailable_benchmark_failed",
                "benchmark_unavailable",
            )
            return {"downside": unavailable, "stress": dict(unavailable)}

        benchmark_returns = benchmark_dataset.daily_returns_twd[benchmark_symbol]
        downside = downside_correlation(
            prepared.daily_returns,
            benchmark_returns,
            min_observations=CONDITIONAL_MIN_OBSERVATIONS,
        )
        stress = stress_correlation(
            prepared.daily_returns,
            benchmark_returns,
            quantile=prepared.request.stress_quantile,
            min_observations=CONDITIONAL_MIN_OBSERVATIONS,
        )
        return {
            "downside": _correlation_payload(downside),
            "stress": _correlation_payload(stress),
        }


def _subset_histories(
    batch: PartialTWDHistories,
    requested: Iterable[str],
) -> PartialTWDHistories:
    symbols = tuple(requested)
    return PartialTWDHistories(
        requested=symbols,
        histories={
            symbol: batch.histories[symbol]
            for symbol in symbols
            if symbol in batch.histories
        },
        failures={
            symbol: batch.failures[symbol]
            for symbol in symbols
            if symbol in batch.failures
        },
    )


def _finite_complete_case(
    frame: pd.DataFrame,
    symbols: Iterable[str],
) -> pd.DataFrame:
    ordered = list(symbols)
    if not ordered:
        return pd.DataFrame(dtype=float)
    if frame.empty:
        return pd.DataFrame(columns=ordered, dtype=float)
    selected = frame.loc[:, ordered].replace([np.inf, -np.inf], np.nan)
    return selected.dropna(how="any").astype(float)


def _failure_payload(failure: HistoryFailure) -> dict[str, Any]:
    return {
        "symbol": failure.symbol,
        "stage": failure.stage,
        "detail": failure.detail,
        "retryable": bool(failure.retryable),
    }


def _covariance_diagnostics_payload(value: Any) -> dict[str, Any]:
    return {
        "observations": int(value.observations),
        "features": int(value.features),
        "symmetry_error": _finite_or_none(value.symmetry_error),
        "tolerance": _finite_or_none(value.tolerance),
        "min_eigenvalue": _finite_or_none(value.min_eigenvalue),
        "max_eigenvalue": _finite_or_none(value.max_eigenvalue),
        "is_psd": bool(value.is_psd),
        "numerical_rank": int(value.numerical_rank),
        "condition_number": _finite_or_none(value.condition_number),
    }


def _effective_dimension_payload(value: Any) -> dict[str, Any]:
    return {
        "entropy_effective_rank": _finite_or_none(value.entropy_effective_rank),
        "participation_ratio": _finite_or_none(value.participation_ratio),
        "positive_eigenvalues": [
            _finite_or_none(item) for item in value.positive_eigenvalues
        ],
    }


def _correlation_payload(result: CorrelationResult) -> dict[str, Any]:
    matrix = None
    if result.matrix is not None:
        matrix = {
            "symbols": [str(column) for column in result.matrix.columns],
            "values": [
                [_finite_or_none(value) for value in row]
                for row in result.matrix.to_numpy(dtype=float)
            ],
        }
    return {
        "status": result.status,
        "input_observations": int(result.input_observations),
        "observations": int(result.observations),
        "dropped_observations": int(result.dropped_observations),
        "window": result.window,
        "condition": result.condition,
        "threshold": _finite_or_none(result.threshold),
        "matrix": matrix,
    }


def _unavailable_correlation(status: str, condition: str) -> dict[str, Any]:
    return {
        "status": status,
        "input_observations": 0,
        "observations": 0,
        "dropped_observations": 0,
        "window": None,
        "condition": condition,
        "threshold": None,
        "matrix": None,
    }


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, int):
        return value
    if isinstance(value, (float, np.floating)):
        return _finite_or_none(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    return str(value)
