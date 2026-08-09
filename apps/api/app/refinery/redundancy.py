"""Versioned descriptive redundancy verdict and confidence policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RedundancyEvidence:
    structural_correlation: float | None
    medium_correlation: float | None
    downside_correlation: float | None
    stress_correlation: float | None
    factor_implied_correlation: float | None
    shared_traceable_theme: bool | None
    same_average_cluster: bool | None
    same_complete_cluster: bool | None
    bootstrap_probability: float | None
    window_agreement: float | None


def redundancy_verdict(evidence: RedundancyEvidence) -> str:
    """Classify historical overlap evidence without turning missing values into zero."""

    structural = evidence.structural_correlation
    bootstrap = evidence.bootstrap_probability
    same_average = evidence.same_average_cluster
    if structural is None or bootstrap is None or same_average is None:
        return "UNCERTAIN"

    if (
        structural >= 0.80
        and same_average
        and evidence.same_complete_cluster is True
        and bootstrap >= 0.75
        and evidence.window_agreement is not None
        and evidence.window_agreement >= (2.0 / 3.0)
        and evidence.medium_correlation is not None
        and evidence.medium_correlation >= 0.70
    ):
        return "HIGH"

    corroborators = (
        evidence.medium_correlation is not None
        and evidence.medium_correlation >= 0.60,
        evidence.downside_correlation is not None
        and evidence.downside_correlation >= 0.65,
        evidence.stress_correlation is not None
        and evidence.stress_correlation >= 0.65,
        evidence.factor_implied_correlation is not None
        and evidence.factor_implied_correlation >= 0.65,
        evidence.shared_traceable_theme is True,
    )
    if (
        structural >= 0.65
        and same_average
        and bootstrap >= 0.60
        and any(corroborators)
    ):
        return "MEDIUM"

    if structural <= 0.35 and not same_average and bootstrap <= 0.35:
        return "LOW"

    return "UNCERTAIN"


def redundancy_confidence(
    *,
    available_windows: int,
    usable_bootstrap_replicates: int,
    structural_valid: bool,
    medium_valid: bool,
) -> str:
    """Summarize evidence completeness separately from the redundancy verdict."""

    if (
        available_windows >= 3
        and usable_bootstrap_replicates >= 190
        and structural_valid
        and medium_valid
    ):
        return "HIGH"
    if (
        available_windows >= 2
        and usable_bootstrap_replicates >= 160
        and structural_valid
        and medium_valid
    ):
        return "MEDIUM"
    return "LOW"
