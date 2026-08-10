from __future__ import annotations

from apps.api.app.refinery.redundancy import (
    RedundancyEvidence,
    redundancy_confidence,
    redundancy_verdict,
)


def _evidence(**overrides: object) -> RedundancyEvidence:
    values: dict[str, object] = {
        "structural_correlation": 0.50,
        "medium_correlation": 0.50,
        "downside_correlation": None,
        "stress_correlation": None,
        "factor_implied_correlation": None,
        "factor_corroboration_eligible": False,
        "shared_traceable_theme": None,
        "same_average_cluster": False,
        "same_complete_cluster": False,
        "bootstrap_probability": 0.50,
        "window_agreement": 0.50,
    }
    values.update(overrides)
    return RedundancyEvidence(**values)  # type: ignore[arg-type]


def test_high_requires_all_primary_and_stability_evidence() -> None:
    evidence = _evidence(
        structural_correlation=0.85,
        medium_correlation=0.75,
        same_average_cluster=True,
        same_complete_cluster=True,
        bootstrap_probability=0.82,
        window_agreement=2.0 / 3.0,
    )
    assert redundancy_verdict(evidence) == "HIGH"

    assert redundancy_verdict(
        _evidence(
            structural_correlation=0.85,
            medium_correlation=None,
            same_average_cluster=True,
            same_complete_cluster=True,
            bootstrap_probability=0.82,
            window_agreement=1.0,
        )
    ) != "HIGH"


def test_medium_requires_core_evidence_plus_one_available_corroborator() -> None:
    no_corroborator = _evidence(
        structural_correlation=0.70,
        medium_correlation=None,
        downside_correlation=None,
        stress_correlation=None,
        factor_implied_correlation=None,
        shared_traceable_theme=None,
        same_average_cluster=True,
        bootstrap_probability=0.70,
    )
    assert redundancy_verdict(no_corroborator) == "UNCERTAIN"

    ineligible_factor = _evidence(
        structural_correlation=0.70,
        medium_correlation=None,
        factor_implied_correlation=0.70,
        factor_corroboration_eligible=False,
        same_average_cluster=True,
        bootstrap_probability=0.70,
    )
    assert redundancy_verdict(ineligible_factor) == "UNCERTAIN"

    eligible_factor = _evidence(
        structural_correlation=0.70,
        medium_correlation=None,
        factor_implied_correlation=0.70,
        factor_corroboration_eligible=True,
        same_average_cluster=True,
        bootstrap_probability=0.70,
    )
    assert redundancy_verdict(eligible_factor) == "MEDIUM"


def test_missing_optional_evidence_is_not_interpreted_as_zero_or_low() -> None:
    evidence = _evidence(
        structural_correlation=0.30,
        medium_correlation=None,
        same_average_cluster=None,
        bootstrap_probability=None,
        window_agreement=None,
    )
    assert redundancy_verdict(evidence) == "UNCERTAIN"


def test_low_requires_low_structural_low_bootstrap_and_separate_clusters() -> None:
    assert redundancy_verdict(
        _evidence(
            structural_correlation=0.20,
            same_average_cluster=False,
            bootstrap_probability=0.20,
        )
    ) == "LOW"
    assert redundancy_verdict(
        _evidence(
            structural_correlation=0.20,
            same_average_cluster=True,
            bootstrap_probability=0.20,
        )
    ) == "UNCERTAIN"


def test_confidence_is_separate_evidence_completeness_policy() -> None:
    assert redundancy_confidence(
        available_windows=3,
        usable_bootstrap_replicates=200,
        structural_valid=True,
        medium_valid=True,
    ) == "HIGH"
    assert redundancy_confidence(
        available_windows=2,
        usable_bootstrap_replicates=170,
        structural_valid=True,
        medium_valid=True,
    ) == "MEDIUM"
    assert redundancy_confidence(
        available_windows=3,
        usable_bootstrap_replicates=200,
        structural_valid=True,
        medium_valid=False,
    ) == "LOW"
