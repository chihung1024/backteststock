"""Phase 5 extension of the read-only Refinery service boundary."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from apps.api.app.quant import (
    BOOTSTRAP_BLOCK_WEEKS,
    BOOTSTRAP_REPLICATES,
    DEFAULT_FACTOR_MIN_MONTHS,
    PRIMARY_CLUSTER_LINKAGE,
    PRIMARY_FLAT_CUT_DISTANCE,
    REFINERY_CLUSTERING_CONTRACT_VERSION,
    SENSITIVITY_CLUSTER_LINKAGE,
    STABILITY_WINDOWS_WEEKS,
    CorrelationResult,
)
from apps.api.app.research import FRENCH_FACTOR_SOURCE, FrenchFactorProvider

from .relationships import THEME_UNAVAILABLE_STATUS, build_phase5_relationships
from .service import RefineryService as _BaseRefineryService


class Phase5RefineryService(_BaseRefineryService):
    """Add Phase 5 relationship evidence without changing Phase 3/4 semantics."""

    def __init__(
        self,
        *,
        history_service: Any | None = None,
        factor_provider: FrenchFactorProvider | None = None,
    ) -> None:
        super().__init__(history_service=history_service)
        self._factor_provider = factor_provider or FrenchFactorProvider()

    def _base_payload(self, prepared: Any, *, endpoint: str) -> dict[str, Any]:
        payload = super()._base_payload(prepared, endpoint=endpoint)
        payload["methodology"].update(
            {
                "clustering_contract_version": REFINERY_CLUSTERING_CONTRACT_VERSION,
                "clustering_primary_input": "structural_synchronized_weekly_twd_returns",
                "clustering_primary_linkage": PRIMARY_CLUSTER_LINKAGE,
                "clustering_sensitivity_linkage": SENSITIVITY_CLUSTER_LINKAGE,
                "clustering_flat_cut_distance": PRIMARY_FLAT_CUT_DISTANCE,
                "clustering_stability_windows_weeks": list(STABILITY_WINDOWS_WEEKS),
                "clustering_bootstrap_replicates": BOOTSTRAP_REPLICATES,
                "clustering_bootstrap_block_weeks": BOOTSTRAP_BLOCK_WEEKS,
                "factor_source": FRENCH_FACTOR_SOURCE,
                "factor_scope": "U.S.-factor co-movement diagnostic",
                "factor_minimum_monthly_observations": DEFAULT_FACTOR_MIN_MONTHS,
                "theme_relationship_policy": THEME_UNAVAILABLE_STATUS,
            }
        )
        return payload

    def _analysis_payload(self, prepared: Any) -> dict[str, Any]:
        payload = super()._analysis_payload(prepared)
        structural = _correlation_result_from_payload(
            payload["correlations"]["structural_weekly"]
        )
        payload.update(
            build_phase5_relationships(
                candidate_dataset=prepared.candidate_dataset,
                weekly_returns=prepared.weekly_returns,
                structural_correlation=structural,
                correlation_payloads=payload["correlations"],
                factor_provider=self._factor_provider,
            )
        )
        return payload


def _correlation_result_from_payload(payload: Mapping[str, Any]) -> CorrelationResult:
    matrix_payload = payload.get("matrix")
    matrix = None
    if isinstance(matrix_payload, Mapping):
        symbols = [str(item) for item in matrix_payload.get("symbols") or []]
        values = matrix_payload.get("values") or []
        if symbols and values:
            matrix = pd.DataFrame(values, index=symbols, columns=symbols, dtype=float)
    return CorrelationResult(
        status=str(payload.get("status") or "unavailable"),
        matrix=matrix,
        input_observations=int(payload.get("input_observations") or 0),
        observations=int(payload.get("observations") or 0),
        dropped_observations=int(payload.get("dropped_observations") or 0),
        window=(int(payload["window"]) if payload.get("window") is not None else None),
        condition=str(payload.get("condition") or "unknown"),
        threshold=(
            float(payload["threshold"])
            if payload.get("threshold") is not None
            else None
        ),
    )
