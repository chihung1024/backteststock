"""Phase 6 marginal experiment extension for the read-only Refinery API."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd

from apps.api.app.quant import (
    PRIMARY_CLUSTER_LINKAGE,
    PRIMARY_FLAT_CUT_DISTANCE,
    SENSITIVITY_CLUSTER_LINKAGE,
    CorrelationResult,
    effective_dimensions,
    hierarchical_clustering,
    ledoit_wolf_covariance,
    multi_horizon_correlations,
)
from apps.api.app.research import ResearchDataset, build_research_dataset

from .models import (
    DAILY_COVARIANCE_ANNUALIZATION,
    MAX_EXPERIMENT_UNION_SYMBOLS,
    MEDIUM_MIN_OBSERVATIONS,
    MIN_DAILY_ANALYSIS_OBSERVATIONS,
    PHASE6_MARGINAL_CONTRACT_VERSION,
    STRUCTURAL_MIN_OBSERVATIONS,
    TACTICAL_MIN_OBSERVATIONS,
    RefineryExperimentOperation,
    RefineryRequest,
)
from .phase5_service import Phase5RefineryService
from .service import (
    _PreparedResearch,
    _correlation_payload,
    _effective_dimension_payload,
    _failure_payload,
    _finite_complete_case,
    _finite_or_none,
    _subset_histories,
)

PHASE6_SAMPLE_FINGERPRINT_ALGORITHM = "sha256-canonical-json-v1"
PHASE6_GLOBAL_SAMPLE_POLICY = "full-experiment-union-complete-case-frozen-v1"
PHASE6_DIAGNOSTIC_SCOPE = "in_sample_historical_structural_diagnostic_not_oos"
PHASE6_SHARED_PAIR_TOLERANCE = 1e-12
PHASE6_PAIR_IMPACT_HORIZONS = (
    "tactical_daily",
    "medium_daily",
    "structural_weekly",
)
# A Replace-One can remove and add at most one symbol's relationships.  The
# union cap therefore also makes this descriptive evidence bounded.
MAX_EXPERIMENT_PAIR_IMPACTS = 2 * (MAX_EXPERIMENT_UNION_SYMBOLS - 1)


@dataclass(frozen=True, slots=True)
class _PreparedMarginalExperiments:
    """P6-only view derived from the same one authoritative market batch."""

    prepared: _PreparedResearch
    union_dataset: ResearchDataset
    union_symbols: tuple[str, ...]
    status: str
    eligibility_reasons: tuple[str, ...]
    daily_global: pd.DataFrame | None
    weekly_global: pd.DataFrame | None


class Phase6RefineryService(Phase5RefineryService):
    """Add explicit marginal experiments without changing the P3–P5 baseline."""

    def preflight(self, request: RefineryRequest) -> dict[str, Any]:
        prepared = self._prepare(request)
        payload = self._base_payload(prepared, endpoint="preflight")
        if request.experiment_plan is not None:
            marginal = self._prepare_marginal_experiments(prepared)
            payload["marginal_experiments"] = self._marginal_payload(
                marginal,
                include_results=False,
            )
        return payload

    def analyze(self, request: RefineryRequest) -> dict[str, Any]:
        prepared = self._prepare(request)
        payload = self._base_payload(prepared, endpoint="analyze")
        if prepared.status != "ready":
            payload["analysis"] = None
        else:
            payload["status"] = "ok"
            # Dynamic dispatch deliberately preserves the complete Phase 5
            # baseline analysis (including its bootstrap/factor evidence) once.
            payload["analysis"] = self._analysis_payload(prepared)

        if request.experiment_plan is not None:
            marginal = self._prepare_marginal_experiments(prepared)
            payload["marginal_experiments"] = self._marginal_payload(
                marginal,
                include_results=True,
            )
        return payload

    def _base_payload(
        self,
        prepared: _PreparedResearch,
        *,
        endpoint: str,
    ) -> dict[str, Any]:
        payload = super()._base_payload(prepared, endpoint=endpoint)
        request = prepared.request
        if request.experiment_plan is not None:
            payload["request"]["experiment_plan"] = [
                operation.export_payload() for operation in request.experiment_plan
            ]
            payload["methodology"].update(
                {
                    "phase6_marginal_contract_version": (
                        PHASE6_MARGINAL_CONTRACT_VERSION
                    ),
                    "phase6_global_sample_policy": PHASE6_GLOBAL_SAMPLE_POLICY,
                    "phase6_sample_fingerprint_algorithm": (
                        PHASE6_SAMPLE_FINGERPRINT_ALGORITHM
                    ),
                    "phase6_diagnostic_scope": PHASE6_DIAGNOSTIC_SCOPE,
                    "phase6_variant_weighting": (
                        "unweighted_no_implicit_allocation_or_renormalization"
                    ),
                    "phase6_variant_phase5_bootstrap": "not_run_minimal_v1",
                }
            )
        return payload

    def _prepare_marginal_experiments(
        self,
        prepared: _PreparedResearch,
    ) -> _PreparedMarginalExperiments:
        """Build one experiment-union dataset from the already-fetched batch."""

        request = prepared.request
        if request.experiment_plan is None:  # pragma: no cover - internal guard
            raise ValueError("marginal experiment preparation requires an experiment plan")

        union_symbols = request.experiment_union_symbols
        union_dataset = build_research_dataset(
            _subset_histories(prepared.market_histories, union_symbols),
            start=request.start_date,
            end=request.end_date,
        )
        daily_global: pd.DataFrame | None = None
        weekly_global: pd.DataFrame | None = None
        reasons: list[str] = []

        if union_dataset.is_complete:
            canonical_symbols = tuple(sorted(union_symbols))
            daily_global = _finite_complete_case(
                union_dataset.daily_returns_twd,
                canonical_symbols,
            )
            weekly_global = _finite_complete_case(
                union_dataset.weekly_returns_twd,
                canonical_symbols,
            )
        else:
            reasons.append("experiment_membership_incomplete")

        if prepared.status != "ready":
            reasons.append("baseline_analysis_not_ready")
            status = "unavailable_baseline"
        elif not union_dataset.is_complete:
            status = "incomplete"
        elif daily_global is None or len(daily_global) < MIN_DAILY_ANALYSIS_OBSERVATIONS:
            reasons.append(
                "daily_global_observations_below_"
                f"{MIN_DAILY_ANALYSIS_OBSERVATIONS}"
            )
            status = "insufficient_data"
        elif weekly_global is None or len(weekly_global) < STRUCTURAL_MIN_OBSERVATIONS:
            reasons.append(
                "weekly_global_observations_below_"
                f"{STRUCTURAL_MIN_OBSERVATIONS}"
            )
            status = "insufficient_data"
        else:
            status = "ready"

        return _PreparedMarginalExperiments(
            prepared=prepared,
            union_dataset=union_dataset,
            union_symbols=union_symbols,
            status=status,
            eligibility_reasons=tuple(reasons),
            daily_global=daily_global,
            weekly_global=weekly_global,
        )

    def _marginal_payload(
        self,
        prepared: _PreparedMarginalExperiments,
        *,
        include_results: bool,
    ) -> dict[str, Any]:
        common_sample = _common_sample_payload(prepared)
        payload: dict[str, Any] = {
            "status": prepared.status,
            "eligibility": {
                "baseline_analysis_ready": prepared.prepared.status == "ready",
                "experiment_membership_complete": prepared.union_dataset.is_complete,
                "daily_global_observations_sufficient": (
                    prepared.daily_global is not None
                    and len(prepared.daily_global) >= MIN_DAILY_ANALYSIS_OBSERVATIONS
                ),
                "weekly_global_observations_sufficient": (
                    prepared.weekly_global is not None
                    and len(prepared.weekly_global) >= STRUCTURAL_MIN_OBSERVATIONS
                ),
                "reasons": list(prepared.eligibility_reasons),
            },
            "failures": {
                symbol: _failure_payload(failure)
                for symbol, failure in prepared.union_dataset.failures.items()
            },
            "common_sample": common_sample,
            "methodology": {
                "contract_version": PHASE6_MARGINAL_CONTRACT_VERSION,
                "scope": PHASE6_DIAGNOSTIC_SCOPE,
                "global_sample_policy": PHASE6_GLOBAL_SAMPLE_POLICY,
                "sample_fingerprint_algorithm": PHASE6_SAMPLE_FINGERPRINT_ALGORITHM,
                "weighting": "unweighted_no_implicit_allocation_or_renormalization",
                "variant_phase5_bootstrap": "not_run_minimal_v1",
            },
            "experiment_baseline": None,
            "results": [],
        }
        if not include_results or prepared.status != "ready":
            return payload

        if prepared.daily_global is None or prepared.weekly_global is None:
            raise RuntimeError("ready marginal experiments require frozen global samples")

        request = prepared.prepared.request
        baseline_daily = prepared.daily_global.loc[:, list(request.symbols)]
        baseline_weekly = prepared.weekly_global.loc[:, list(request.symbols)]
        baseline = _structural_snapshot(baseline_daily, baseline_weekly)
        payload["experiment_baseline"] = baseline
        sample_reference = _common_sample_reference(common_sample)

        results: list[dict[str, Any]] = []
        for operation in request.experiment_plan or []:
            variant_symbols = _variant_symbols(request.symbols, operation)
            variant_daily = prepared.daily_global.loc[:, list(variant_symbols)]
            variant_weekly = prepared.weekly_global.loc[:, list(variant_symbols)]
            variant = _structural_snapshot(variant_daily, variant_weekly)
            results.append(
                {
                    "id": _experiment_result_id(operation, sample_reference),
                    "operation": operation.export_payload(),
                    "variant_symbols": list(variant_symbols),
                    "common_sample": sample_reference,
                    "variant": variant,
                    "deltas": _snapshot_deltas(baseline, variant),
                }
            )
        payload["results"] = results
        return payload


def _common_sample_payload(
    prepared: _PreparedMarginalExperiments,
) -> dict[str, Any]:
    """Expose dataset provenance separately from frozen effective samples."""

    if prepared.daily_global is None or prepared.weekly_global is None:
        sample_status = "unavailable_experiment_membership_incomplete"
    elif prepared.status == "ready":
        sample_status = "ready"
    else:
        # The frame is still useful evidence, but its cardinality is not
        # eligible for marginal analysis.  Do not label it as ready.
        sample_status = f"frozen_{prepared.status}"

    return {
        "status": sample_status,
        "experiment_union_dataset_hash": prepared.union_dataset.dataset_hash,
        "experiment_union_symbols": list(prepared.union_symbols),
        "daily": (
            frozen_sample_identity(prepared.daily_global)
            if prepared.daily_global is not None
            else None
        ),
        "weekly": (
            frozen_sample_identity(prepared.weekly_global)
            if prepared.weekly_global is not None
            else None
        ),
    }


def frozen_sample_identity(frame: pd.DataFrame) -> dict[str, Any]:
    """Fingerprint exactly the finite canonical matrix consumed by Phase 6.

    Dataset provenance deliberately remains in ``ResearchDataset.dataset_hash``.
    This identity is limited to the rows/columns actually frozen for a frequency.
    """

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frozen sample must be a pandas DataFrame")
    if not frame.columns.is_unique:
        raise ValueError("frozen sample columns must be unique")
    symbols = tuple(sorted(str(column) for column in frame.columns))
    if len(set(symbols)) != len(symbols):
        raise ValueError("frozen sample columns must remain unique after normalization")
    canonical = frame.copy()
    canonical.columns = [str(column) for column in canonical.columns]
    canonical = canonical.loc[:, list(symbols)].sort_index().astype(float)
    values = canonical.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("frozen sample must contain only finite values")

    fingerprint_payload = {
        "symbols": list(symbols),
        "dates": [pd.Timestamp(value).isoformat() for value in canonical.index],
        "values": values.tolist(),
    }
    encoded = json.dumps(
        fingerprint_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return {
        "effective_start": (
            pd.Timestamp(canonical.index[0]).date().isoformat()
            if len(canonical)
            else None
        ),
        "effective_end": (
            pd.Timestamp(canonical.index[-1]).date().isoformat()
            if len(canonical)
            else None
        ),
        "observations": int(len(canonical)),
        "canonical_symbols": list(symbols),
        "fingerprint_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _common_sample_reference(common_sample: dict[str, Any]) -> dict[str, Any]:
    daily = common_sample.get("daily")
    weekly = common_sample.get("weekly")
    if not isinstance(daily, dict) or not isinstance(weekly, dict):
        raise RuntimeError("ready marginal experiments require common sample identities")
    return {
        "daily": dict(daily),
        "weekly": dict(weekly),
    }


def _variant_symbols(
    baseline_symbols: list[str],
    operation: RefineryExperimentOperation,
) -> tuple[str, ...]:
    """Apply one validated operation while preserving baseline display order."""

    if operation.type == "remove_one":
        if operation.remove is None:  # pragma: no cover - model invariant
            raise ValueError("remove_one operation is missing remove")
        return tuple(symbol for symbol in baseline_symbols if symbol != operation.remove)
    if operation.type == "add_one":
        if operation.add is None:  # pragma: no cover - model invariant
            raise ValueError("add_one operation is missing add")
        return tuple([*baseline_symbols, operation.add])
    if operation.remove is None or operation.add is None:  # pragma: no cover
        raise ValueError("replace_one operation is incomplete")
    return tuple(
        operation.add if symbol == operation.remove else symbol
        for symbol in baseline_symbols
    )


def _structural_snapshot(
    daily: pd.DataFrame,
    weekly: pd.DataFrame,
) -> dict[str, Any]:
    """Deterministic unweighted point-estimate evidence on frozen columns only."""

    ledoit_wolf = ledoit_wolf_covariance(
        daily,
        annualization=DAILY_COVARIANCE_ANNUALIZATION,
    )
    covariance_dimension = effective_dimensions(ledoit_wolf.covariance)
    correlations = multi_horizon_correlations(
        daily,
        weekly,
        tactical_min_observations=TACTICAL_MIN_OBSERVATIONS,
        medium_min_observations=MEDIUM_MIN_OBSERVATIONS,
        structural_min_observations=STRUCTURAL_MIN_OBSERVATIONS,
    )
    medium_dimension = None
    if (
        correlations.medium_daily.status == "ok"
        and correlations.medium_daily.matrix is not None
    ):
        medium_dimension = effective_dimensions(
            correlations.medium_daily.matrix.to_numpy(dtype=float)
        )
    return {
        "symbols": [str(column) for column in daily.columns],
        "covariance": {
            "primary_method": ledoit_wolf.method,
            "observations": int(ledoit_wolf.observations),
            "features": int(ledoit_wolf.features),
            "annualization": float(ledoit_wolf.annualization),
            "ledoit_wolf_shrinkage": _finite_or_none(ledoit_wolf.shrinkage),
        },
        "effective_dimensions": {
            "covariance": _effective_dimension_payload(covariance_dimension),
            "medium_correlation": (
                _effective_dimension_payload(medium_dimension)
                if medium_dimension is not None
                else None
            ),
        },
        "correlations": {
            "tactical_daily": _correlation_payload(correlations.tactical_daily),
            "medium_daily": _correlation_payload(correlations.medium_daily),
            "structural_weekly": _correlation_payload(
                correlations.structural_weekly
            ),
        },
        "clustering": _point_estimate_clustering(
            correlations.structural_weekly
        ),
    }


def _point_estimate_clustering(structural: CorrelationResult) -> dict[str, Any]:
    if structural.status != "ok" or structural.matrix is None:
        return {
            "status": "unavailable_structural_correlation",
            "reason": structural.status,
            "primary": None,
            "sensitivity": None,
        }
    primary = hierarchical_clustering(
        structural.matrix,
        method=PRIMARY_CLUSTER_LINKAGE,
        cut_distance=PRIMARY_FLAT_CUT_DISTANCE,
    )
    sensitivity = hierarchical_clustering(
        structural.matrix,
        method=SENSITIVITY_CLUSTER_LINKAGE,
        cut_distance=PRIMARY_FLAT_CUT_DISTANCE,
    )
    return {
        "status": "ok",
        "primary": _hierarchy_payload(primary),
        "sensitivity": _hierarchy_payload(sensitivity),
    }


def _hierarchy_payload(value: Any) -> dict[str, Any]:
    return {
        "method": value.method,
        "cut_distance": _finite_or_none(value.cut_distance),
        "symbols": list(value.symbols),
        "cluster_count": int(len(value.clusters)),
        "clusters": [
            {
                "cluster_id": group.cluster_id,
                "members": list(group.members),
            }
            for group in value.clusters
        ],
        "merges": [
            {
                "node_id": merge.node_id,
                "left": merge.left,
                "right": merge.right,
                "distance": _finite_or_none(merge.distance),
                "count": int(merge.count),
            }
            for merge in value.merges
        ],
    }


def _snapshot_deltas(
    baseline: dict[str, Any],
    variant: dict[str, Any],
) -> dict[str, Any]:
    """Only descriptive variant-minus-baseline deltas; never a ranking score."""

    return {
        "effective_dimensions": {
            "covariance": _dimension_deltas(
                baseline["effective_dimensions"]["covariance"],
                variant["effective_dimensions"]["covariance"],
            ),
            "medium_correlation": _dimension_deltas(
                baseline["effective_dimensions"]["medium_correlation"],
                variant["effective_dimensions"]["medium_correlation"],
            ),
        },
        "clusters": {
            "primary": _cluster_count_delta(
                baseline["clustering"]["primary"],
                variant["clustering"]["primary"],
            ),
            "sensitivity": _cluster_count_delta(
                baseline["clustering"]["sensitivity"],
                variant["clustering"]["sensitivity"],
            ),
        },
        "pair_impacts": _pair_impact_summary(baseline, variant),
    }


def _dimension_deltas(
    baseline: dict[str, Any] | None,
    variant: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if baseline is None or variant is None:
        return None
    return {
        name: _scalar_delta(baseline.get(name), variant.get(name))
        for name in ("entropy_effective_rank", "participation_ratio")
    }


def _cluster_count_delta(
    baseline: dict[str, Any] | None,
    variant: dict[str, Any] | None,
) -> dict[str, float | None]:
    return _scalar_delta(
        baseline.get("cluster_count") if baseline is not None else None,
        variant.get("cluster_count") if variant is not None else None,
    )


def _pair_impact_summary(
    baseline: dict[str, Any],
    variant: dict[str, Any],
) -> dict[str, Any]:
    """Describe only relationships touched by the explicit one-symbol edit.

    The summary deliberately does not sort, score, or label a preferred
    operation.  Shared-pair values are also checked as an executable guard
    against accidentally recomputing a variant on a different date sample.
    """

    baseline_symbols = tuple(str(symbol) for symbol in baseline["symbols"])
    variant_symbols = tuple(str(symbol) for symbol in variant["symbols"])
    baseline_set = set(baseline_symbols)
    variant_set = set(variant_symbols)
    removed_pairs = _pairs_touching(
        baseline_set - variant_set,
        baseline_symbols,
    )
    added_pairs = _pairs_touching(
        variant_set - baseline_set,
        variant_symbols,
    )
    if len(removed_pairs) + len(added_pairs) > MAX_EXPERIMENT_PAIR_IMPACTS:
        raise RuntimeError("marginal pair-impact resource bound was exceeded")

    return {
        "maximum_pairs": MAX_EXPERIMENT_PAIR_IMPACTS,
        "shared_pair_invariant": _shared_pair_invariant(baseline, variant),
        "removed_pairs": _pair_evidence(baseline, removed_pairs),
        "added_pairs": _pair_evidence(variant, added_pairs),
    }


def _pairs_touching(
    changed_symbols: set[str],
    symbols: tuple[str, ...],
) -> list[tuple[str, str]]:
    pairs = {
        tuple(sorted((changed, other)))
        for changed in changed_symbols
        for other in symbols
        if other != changed
    }
    return sorted(pairs)


def _pair_evidence(
    snapshot: dict[str, Any],
    pairs: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    return [
        {
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "correlations": {
                horizon: _pair_correlation(snapshot, horizon, symbol_a, symbol_b)
                for horizon in PHASE6_PAIR_IMPACT_HORIZONS
            },
        }
        for symbol_a, symbol_b in pairs
    ]


def _shared_pair_invariant(
    baseline: dict[str, Any],
    variant: dict[str, Any],
) -> dict[str, Any]:
    shared_symbols = sorted(set(baseline["symbols"]) & set(variant["symbols"]))
    pairs = list(combinations(shared_symbols, 2))
    payload: dict[str, Any] = {}
    for horizon in PHASE6_PAIR_IMPACT_HORIZONS:
        deltas: list[float] = []
        for symbol_a, symbol_b in pairs:
            baseline_value = _pair_correlation(
                baseline,
                horizon,
                symbol_a,
                symbol_b,
            )
            variant_value = _pair_correlation(
                variant,
                horizon,
                symbol_a,
                symbol_b,
            )
            if baseline_value is None and variant_value is None:
                continue
            if baseline_value is None or variant_value is None:
                raise RuntimeError(
                    "shared-pair correlation availability drifted across "
                    "frozen marginal samples"
                )
            deltas.append(abs(variant_value - baseline_value))

        maximum = max(deltas, default=0.0)
        if maximum > PHASE6_SHARED_PAIR_TOLERANCE:
            raise RuntimeError(
                "shared-pair correlation drifted across frozen marginal samples"
            )
        payload[horizon] = {
            "shared_pairs": len(pairs),
            "compared_pairs": len(deltas),
            "maximum_absolute_delta": _finite_or_none(maximum),
            "tolerance": PHASE6_SHARED_PAIR_TOLERANCE,
        }
    return payload


def _pair_correlation(
    snapshot: dict[str, Any],
    horizon: str,
    symbol_a: str,
    symbol_b: str,
) -> float | None:
    correlation = snapshot["correlations"][horizon]
    matrix = correlation.get("matrix")
    if not isinstance(matrix, dict):
        return None
    symbols = matrix.get("symbols")
    values = matrix.get("values")
    if not isinstance(symbols, list) or not isinstance(values, list):
        return None
    try:
        row = symbols.index(symbol_a)
        column = symbols.index(symbol_b)
        value = values[row][column]
    except (IndexError, TypeError, ValueError):
        return None
    return _finite_or_none(value)


def _scalar_delta(
    baseline: Any,
    variant: Any,
) -> dict[str, float | None]:
    baseline_value = _finite_or_none(baseline)
    variant_value = _finite_or_none(variant)
    delta = None
    if baseline_value is not None and variant_value is not None:
        delta = _finite_or_none(variant_value - baseline_value)
    return {
        "baseline": baseline_value,
        "variant": variant_value,
        "delta": delta,
    }


def _experiment_result_id(
    operation: RefineryExperimentOperation,
    common_sample: dict[str, Any],
) -> str:
    """Hash normalized semantics and shared samples, never UI object order."""

    daily = common_sample["daily"]
    weekly = common_sample["weekly"]
    payload = {
        "contract_version": PHASE6_MARGINAL_CONTRACT_VERSION,
        "operation": operation.export_payload(),
        "daily_common_sample_fingerprint_sha256": daily["fingerprint_sha256"],
        "weekly_common_sample_fingerprint_sha256": weekly["fingerprint_sha256"],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
