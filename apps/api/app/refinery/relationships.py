"""Phase 5 read-only relationship evidence over an existing ResearchDataset."""

from __future__ import annotations

import hashlib
import json
from itertools import combinations
from typing import Any, Mapping

import numpy as np
import pandas as pd

from apps.api.app.quant import (
    BOOTSTRAP_BLOCK_WEEKS,
    BOOTSTRAP_REPLICATES,
    DEFAULT_FACTOR_MIN_MONTHS,
    FACTOR_MONTHLY_RETURN_POLICY,
    PRIMARY_CLUSTER_LINKAGE,
    PRIMARY_FLAT_CUT_DISTANCE,
    PRIMARY_STRUCTURAL_WINDOW_WEEKS,
    REFINERY_CLUSTERING_CONTRACT_VERSION,
    SENSITIVITY_CLUSTER_LINKAGE,
    STABILITY_WINDOWS_WEEKS,
    CorrelationResult,
    FactorExposure,
    bootstrap_cluster_stability,
    factor_implied_relationship,
    fit_us_factor_exposure,
    hierarchical_clustering,
    multi_window_cluster_stability,
)
from apps.api.app.research import FRENCH_FACTOR_SOURCE, FrenchFactorProvider, ResearchDataset

from .redundancy import RedundancyEvidence, redundancy_confidence, redundancy_verdict

THEME_UNAVAILABLE_STATUS = "unavailable_no_traceable_theme_source"
FACTOR_MODEL_SCOPE = "U.S.-factor co-movement diagnostic"
FACTOR_CORROBORATION_UNAVAILABLE_REASON = (
    "unavailable_no_traceable_instrument_scope"
)


def build_phase5_relationships(
    *,
    candidate_dataset: ResearchDataset,
    weekly_returns: pd.DataFrame,
    structural_correlation: CorrelationResult,
    correlation_payloads: Mapping[str, Mapping[str, Any]],
    bootstrap_input_fingerprint: str,
    factor_provider: FrenchFactorProvider,
) -> dict[str, Any]:
    """Compose clustering, redundancy, factor and theme evidence without re-fetching prices."""

    clustering = _clustering_payload(
        weekly_returns=weekly_returns,
        structural_correlation=structural_correlation,
        input_fingerprint=bootstrap_input_fingerprint,
    )
    factors = _factor_payload(candidate_dataset, factor_provider)
    theme = {
        "status": THEME_UNAVAILABLE_STATUS,
        "source": None,
        "taxonomy_version": None,
        "relationships": None,
    }
    redundancy = _redundancy_payload(
        symbols=tuple(candidate_dataset.requested_symbols),
        clustering=clustering,
        correlation_payloads=correlation_payloads,
        factor_payload=factors,
    )
    return {
        "clustering": clustering,
        "redundancy": redundancy,
        "factor_relationships": factors,
        "theme_relationships": theme,
    }


def _clustering_payload(
    *,
    weekly_returns: pd.DataFrame,
    structural_correlation: CorrelationResult,
    input_fingerprint: str,
) -> dict[str, Any]:
    base = {
        "contract_version": REFINERY_CLUSTERING_CONTRACT_VERSION,
        "primary_linkage": PRIMARY_CLUSTER_LINKAGE,
        "sensitivity_linkage": SENSITIVITY_CLUSTER_LINKAGE,
        "flat_cut_distance": PRIMARY_FLAT_CUT_DISTANCE,
        "stability_windows_weeks": list(STABILITY_WINDOWS_WEEKS),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_block_weeks": BOOTSTRAP_BLOCK_WEEKS,
        "bootstrap_window_weeks": PRIMARY_STRUCTURAL_WINDOW_WEEKS,
        "bootstrap_input_fingerprint_sha256": input_fingerprint,
    }
    if structural_correlation.status != "ok" or structural_correlation.matrix is None:
        return {
            **base,
            "status": "unavailable_structural_correlation",
            "reason": structural_correlation.status,
            "primary": None,
            "sensitivity": None,
            "multi_window": None,
            "bootstrap": None,
            "clusters": [],
        }

    try:
        primary = hierarchical_clustering(
            structural_correlation.matrix,
            method=PRIMARY_CLUSTER_LINKAGE,
            cut_distance=PRIMARY_FLAT_CUT_DISTANCE,
        )
        sensitivity = hierarchical_clustering(
            structural_correlation.matrix,
            method=SENSITIVITY_CLUSTER_LINKAGE,
            cut_distance=PRIMARY_FLAT_CUT_DISTANCE,
        )
        windows = multi_window_cluster_stability(
            weekly_returns,
            windows=STABILITY_WINDOWS_WEEKS,
            min_observations=52,
            cut_distance=PRIMARY_FLAT_CUT_DISTANCE,
        )
        bootstrap = bootstrap_cluster_stability(
            weekly_returns,
            input_fingerprint=input_fingerprint,
            replicates=BOOTSTRAP_REPLICATES,
            block_weeks=BOOTSTRAP_BLOCK_WEEKS,
            min_observations=52,
            window=PRIMARY_STRUCTURAL_WINDOW_WEEKS,
            cut_distance=PRIMARY_FLAT_CUT_DISTANCE,
        )
    except (TypeError, ValueError) as exc:
        return {
            **base,
            "status": "unavailable_clustering_input",
            "reason": str(exc),
            "primary": None,
            "sensitivity": None,
            "multi_window": None,
            "bootstrap": None,
            "clusters": [],
        }

    bootstrap_lookup = {
        (item.symbol_a, item.symbol_b): item.probability
        for item in bootstrap.pair_probabilities
    }
    cluster_summaries: list[dict[str, Any]] = []
    for group in primary.clusters:
        pairs = list(combinations(group.members, 2))
        correlations = [
            float(structural_correlation.matrix.loc[a, b]) for a, b in pairs
        ]
        boot_values = [
            bootstrap_lookup.get(tuple(sorted((a, b)))) for a, b in pairs
        ]
        finite_boot = [value for value in boot_values if value is not None]
        complete_ids = {sensitivity.cluster_by_symbol[symbol] for symbol in group.members}
        cluster_summaries.append(
            {
                "cluster_id": group.cluster_id,
                "members": list(group.members),
                "member_count": len(group.members),
                "structural_correlation": (
                    {
                        "minimum": min(correlations),
                        "mean": float(np.mean(correlations)),
                        "maximum": max(correlations),
                    }
                    if correlations
                    else None
                ),
                "bootstrap_stability": (
                    float(np.mean(finite_boot)) if finite_boot else None
                ),
                "bootstrap_stability_status": (
                    "ok" if finite_boot else "not_applicable"
                ),
                "complete_linkage_agreement": (
                    len(complete_ids) == 1 if len(group.members) > 1 else None
                ),
            }
        )

    return {
        **base,
        "status": "ok",
        "reason": None,
        "primary": _hierarchy_payload(primary),
        "sensitivity": _hierarchy_payload(sensitivity),
        "multi_window": {
            "windows": [
                {
                    "window_weeks": item.window_weeks,
                    "status": item.status,
                    "input_observations": item.input_observations,
                    "observations": item.observations,
                }
                for item in windows.windows
            ],
            "pair_agreements": [
                {
                    "symbol_a": item.symbol_a,
                    "symbol_b": item.symbol_b,
                    "available_windows": item.available_windows,
                    "same_cluster_windows": item.same_cluster_windows,
                    "agreement": item.agreement,
                }
                for item in windows.pair_agreements
            ],
        },
        "bootstrap": {
            "status": bootstrap.status,
            "requested_replicates": bootstrap.requested_replicates,
            "usable_replicates": bootstrap.usable_replicates,
            "unusable_replicates": bootstrap.unusable_replicates,
            "block_weeks": bootstrap.block_weeks,
            "observations": bootstrap.observations,
            "seed": bootstrap.seed,
            "pair_probabilities": [
                {
                    "symbol_a": item.symbol_a,
                    "symbol_b": item.symbol_b,
                    "probability": item.probability,
                }
                for item in bootstrap.pair_probabilities
            ],
        },
        "clusters": cluster_summaries,
    }


def _factor_payload(
    dataset: ResearchDataset,
    provider: FrenchFactorProvider,
) -> dict[str, Any]:
    asset_results: dict[str, dict[str, Any]] = {}
    eligible: list[str] = []
    for symbol in dataset.requested_symbols:
        metadata = dataset.asset_metadata.get(symbol, {})
        quote_currency = str(metadata.get("quote_currency") or "").upper()
        if quote_currency != "USD":
            asset_results[symbol] = {
                "status": "unavailable_non_usd_quote_currency",
                "quote_currency": quote_currency or None,
                "factor_computable": False,
                "factor_model_scope": FACTOR_MODEL_SCOPE,
                "factor_corroboration_eligible": False,
                "factor_corroboration_reason": FACTOR_CORROBORATION_UNAVAILABLE_REASON,
                "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,
                "observations": 0,
                "r_squared": None,
                "betas": None,
            }
            continue
        if symbol not in dataset.native_returns:
            asset_results[symbol] = {
                "status": "unavailable_native_returns",
                "quote_currency": quote_currency,
                "factor_computable": False,
                "factor_model_scope": FACTOR_MODEL_SCOPE,
                "factor_corroboration_eligible": False,
                "factor_corroboration_reason": FACTOR_CORROBORATION_UNAVAILABLE_REASON,
                "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,
                "observations": 0,
                "r_squared": None,
                "betas": None,
            }
            continue
        eligible.append(symbol)

    base = {
        "source": FRENCH_FACTOR_SOURCE,
        "scope": FACTOR_MODEL_SCOPE,
        "factor_model_scope": FACTOR_MODEL_SCOPE,
        "factor_corroboration_policy": "fail_closed_without_traceable_instrument_scope_v1",
        "return_currency": "native_quote_currency",
        "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,
        "minimum_monthly_observations": DEFAULT_FACTOR_MIN_MONTHS,
    }
    if not eligible:
        return {
            **base,
            "status": "unavailable_no_eligible_assets",
            "factor_sample": None,
            "assets": asset_results,
            "systematic_relationship": None,
        }

    try:
        factors = provider.monthly_factors()
    except Exception:  # noqa: BLE001 - external factor source is best-effort evidence
        for symbol in eligible:
            asset_results[symbol] = {
                "status": "unavailable_factor_source",
                "quote_currency": "USD",
                "factor_computable": False,
                "factor_model_scope": FACTOR_MODEL_SCOPE,
                "factor_corroboration_eligible": False,
                "factor_corroboration_reason": FACTOR_CORROBORATION_UNAVAILABLE_REASON,
                "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,
                "observations": 0,
                "r_squared": None,
                "betas": None,
            }
        return {
            **base,
            "status": "unavailable_factor_source",
            "factor_sample": None,
            "assets": asset_results,
            "systematic_relationship": None,
        }

    factors = factors.loc[
        (factors.index >= pd.Timestamp(dataset.requested_start))
        & (factors.index <= pd.Timestamp(dataset.requested_end))
    ].copy()
    exposures: dict[str, FactorExposure] = {}
    for symbol in eligible:
        exposure = fit_us_factor_exposure(
            dataset.native_returns[symbol],
            factors,
            min_observations=DEFAULT_FACTOR_MIN_MONTHS,
        )
        exposures[symbol] = exposure
        asset_results[symbol] = {
            "status": exposure.status,
            "quote_currency": "USD",
            "factor_computable": exposure.status == "ok" and exposure.betas is not None,
            "factor_model_scope": FACTOR_MODEL_SCOPE,
            "factor_corroboration_eligible": False,
            "factor_corroboration_reason": FACTOR_CORROBORATION_UNAVAILABLE_REASON,
            "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,
            "observations": exposure.observations,
            "start": exposure.start,
            "end": exposure.end,
            "intercept_monthly": exposure.intercept_monthly,
            "r_squared": exposure.r_squared,
            "betas": exposure.betas,
        }

    relation = factor_implied_relationship(
        {symbol: dataset.native_returns[symbol] for symbol in eligible},
        factors,
        min_observations=DEFAULT_FACTOR_MIN_MONTHS,
    )
    relationship_payload = None
    if relation.status == "ok" and relation.correlation is not None:
        relationship_payload = {
            "status": relation.status,
            "observations": relation.observations,
            "start": relation.start,
            "end": relation.end,
            "sample_fingerprint_sha256": relation.sample_fingerprint_sha256,
            "matrix": _matrix_payload(relation.correlation),
        }
    elif relation.symbols:
        relationship_payload = {
            "status": relation.status,
            "observations": relation.observations,
            "start": relation.start,
            "end": relation.end,
            "sample_fingerprint_sha256": relation.sample_fingerprint_sha256,
            "matrix": None,
        }

    return {
        **base,
        "status": "ok" if any(value.status == "ok" for value in exposures.values()) else "unavailable_insufficient_factor_history",
        "factor_sample": {
            "observations": len(factors),
            "start": factors.index[0].date().isoformat() if len(factors) else None,
            "end": factors.index[-1].date().isoformat() if len(factors) else None,
            "fingerprint_sha256": _frame_fingerprint(factors),
        },
        "assets": asset_results,
        "systematic_relationship": relationship_payload,
    }


def _redundancy_payload(
    *,
    symbols: tuple[str, ...],
    clustering: Mapping[str, Any],
    correlation_payloads: Mapping[str, Mapping[str, Any]],
    factor_payload: Mapping[str, Any],
) -> dict[str, Any]:
    if clustering.get("status") != "ok":
        return {
            "status": "unavailable_clustering",
            "pairs": [],
            "counts": {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNCERTAIN": 0},
        }

    primary = clustering["primary"]
    sensitivity = clustering["sensitivity"]
    primary_by_symbol = dict(primary["cluster_by_symbol"])
    sensitivity_by_symbol = dict(sensitivity["cluster_by_symbol"])
    window_lookup = {
        (item["symbol_a"], item["symbol_b"]): item
        for item in clustering["multi_window"]["pair_agreements"]
    }
    bootstrap_lookup = {
        (item["symbol_a"], item["symbol_b"]): item["probability"]
        for item in clustering["bootstrap"]["pair_probabilities"]
    }
    factor_matrix = _factor_matrix_lookup(factor_payload)
    usable_bootstrap = int(clustering["bootstrap"]["usable_replicates"])

    rows: list[dict[str, Any]] = []
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNCERTAIN": 0}
    for symbol_a, symbol_b in combinations(sorted(symbols), 2):
        pair = (symbol_a, symbol_b)
        structural = _correlation_value(
            correlation_payloads.get("structural_weekly"), symbol_a, symbol_b
        )
        medium = _correlation_value(
            correlation_payloads.get("medium_daily"), symbol_a, symbol_b
        )
        downside = _correlation_value(
            correlation_payloads.get("downside"), symbol_a, symbol_b
        )
        stress = _correlation_value(
            correlation_payloads.get("stress"), symbol_a, symbol_b
        )
        factor = factor_matrix.get(pair)
        factor_corroboration_eligible, factor_corroboration_reason = (
            _factor_corroboration_pair_evidence(
                factor_payload,
                symbol_a,
                symbol_b,
                factor,
            )
        )
        window = window_lookup.get(pair, {})
        bootstrap = bootstrap_lookup.get(pair)
        evidence = RedundancyEvidence(
            structural_correlation=structural,
            medium_correlation=medium,
            downside_correlation=downside,
            stress_correlation=stress,
            factor_implied_correlation=factor,
            factor_corroboration_eligible=factor_corroboration_eligible,
            shared_traceable_theme=None,
            same_average_cluster=(
                primary_by_symbol.get(symbol_a) == primary_by_symbol.get(symbol_b)
            ),
            same_complete_cluster=(
                sensitivity_by_symbol.get(symbol_a)
                == sensitivity_by_symbol.get(symbol_b)
            ),
            bootstrap_probability=bootstrap,
            window_agreement=window.get("agreement"),
        )
        verdict = redundancy_verdict(evidence)
        counts[verdict] += 1
        rows.append(
            {
                "symbol_a": symbol_a,
                "symbol_b": symbol_b,
                "verdict": verdict,
                "confidence": redundancy_confidence(
                    available_windows=int(window.get("available_windows") or 0),
                    usable_bootstrap_replicates=usable_bootstrap,
                    structural_valid=structural is not None,
                    medium_valid=medium is not None,
                ),
                "structural_correlation": structural,
                "medium_correlation": medium,
                "downside_correlation": downside,
                "stress_correlation": stress,
                "factor_implied_correlation": factor,
                "factor_corroboration_eligible": factor_corroboration_eligible,
                "factor_corroboration_reason": factor_corroboration_reason,
                "same_average_cluster": evidence.same_average_cluster,
                "same_complete_cluster": evidence.same_complete_cluster,
                "available_stability_windows": int(window.get("available_windows") or 0),
                "window_cocluster_agreement": evidence.window_agreement,
                "bootstrap_cocluster_probability": bootstrap,
                "correlation_status": {
                    key: str(correlation_payloads.get(key, {}).get("status") or "unavailable")
                    for key in ("structural_weekly", "medium_daily", "downside", "stress")
                },
            }
        )

    return {
        "status": "ok",
        "verdict_semantics": "historical_exposure_redundancy_evidence_only",
        "magic_numeric_score": False,
        "counts": counts,
        "pairs": rows,
    }


def _hierarchy_payload(value: Any) -> dict[str, Any]:
    return {
        "method": value.method,
        "cut_distance": value.cut_distance,
        "symbols": list(value.symbols),
        "merges": [
            {
                "node_id": merge.node_id,
                "left": merge.left,
                "right": merge.right,
                "distance": merge.distance,
                "count": merge.count,
            }
            for merge in value.merges
        ],
        "clusters": [
            {"cluster_id": group.cluster_id, "members": list(group.members)}
            for group in value.clusters
        ],
        "cluster_by_symbol": dict(sorted(value.cluster_by_symbol.items())),
    }


def _correlation_value(
    payload: Mapping[str, Any] | None,
    symbol_a: str,
    symbol_b: str,
) -> float | None:
    if not payload or payload.get("status") != "ok":
        return None
    matrix = payload.get("matrix")
    if not isinstance(matrix, Mapping):
        return None
    symbols = list(matrix.get("symbols") or [])
    values = list(matrix.get("values") or [])
    try:
        row = symbols.index(symbol_a)
        column = symbols.index(symbol_b)
        value = values[row][column]
    except (ValueError, IndexError, TypeError):
        return None
    return float(value) if value is not None else None


def _factor_corroboration_pair_evidence(
    payload: Mapping[str, Any],
    symbol_a: str,
    symbol_b: str,
    factor_correlation: float | None,
) -> tuple[bool, str | None]:
    if factor_correlation is None:
        return False, "unavailable_factor_relationship"
    assets = payload.get("assets")
    if not isinstance(assets, Mapping):
        return False, FACTOR_CORROBORATION_UNAVAILABLE_REASON
    asset_a = assets.get(symbol_a)
    asset_b = assets.get(symbol_b)
    eligible = (
        isinstance(asset_a, Mapping)
        and isinstance(asset_b, Mapping)
        and asset_a.get("factor_corroboration_eligible") is True
        and asset_b.get("factor_corroboration_eligible") is True
    )
    if eligible:
        return True, None
    for asset in (asset_a, asset_b):
        if isinstance(asset, Mapping):
            reason = asset.get("factor_corroboration_reason")
            if isinstance(reason, str) and reason:
                return False, reason
    return False, FACTOR_CORROBORATION_UNAVAILABLE_REASON


def _factor_matrix_lookup(payload: Mapping[str, Any]) -> dict[tuple[str, str], float]:
    relationship = payload.get("systematic_relationship")
    if not isinstance(relationship, Mapping) or relationship.get("status") != "ok":
        return {}
    matrix = relationship.get("matrix")
    if not isinstance(matrix, Mapping):
        return {}
    symbols = list(matrix.get("symbols") or [])
    values = list(matrix.get("values") or [])
    result: dict[tuple[str, str], float] = {}
    for row, symbol_a in enumerate(symbols):
        for column in range(row + 1, len(symbols)):
            value = values[row][column]
            if value is not None:
                result[(str(symbol_a), str(symbols[column]))] = float(value)
    return result


def _matrix_payload(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "symbols": [str(column) for column in frame.columns],
        "values": [
            [float(value) if np.isfinite(value) else None for value in row]
            for row in frame.to_numpy(dtype=float)
        ],
    }


def _frame_fingerprint(frame: pd.DataFrame) -> str:
    payload = {
        "columns": [str(column) for column in frame.columns],
        "dates": [pd.Timestamp(value).date().isoformat() for value in frame.index],
        "values": [
            [float(value) if np.isfinite(value) else None for value in row]
            for row in frame.to_numpy(dtype=float)
        ],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
