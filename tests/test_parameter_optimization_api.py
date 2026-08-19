from __future__ import annotations

from pydantic import ValidationError
import pytest

import api.walk_forward_v1 as api_module
from apps.api.app.research.walk_forward_job import (
    DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_JOB_CONTRACT_VERSION,
    DualMomentumParameterOptimizationSpec,
    DualMomentumSelectorSpec,
    _spec_payload,
)


def _period() -> dict[str, str]:
    return {
        "periodId": "2025-12",
        "trainingStart": "2023-01-31",
        "trainingEnd": "2025-12-31",
        "decisionDate": "2025-12-31",
        "evaluationStart": "2026-01-01",
        "evaluationEnd": "2026-01-30",
    }


def _optimized_selector() -> dict[str, object]:
    return {
        "strategy": "dual_momentum",
        "riskySymbols": ["aaa", "BBB"],
        "defensiveSymbols": ["bnd"],
        "parameterOptimization": {
            "searchSpace": {
                "lookbackMonths": [12, 6, 12],
                "topK": [1, 1],
                "absoluteThresholds": [0.0, -0.0, 0.05],
                "allocationMethods": [
                    "risk_parity_erc",
                    "equal",
                    "inverse_volatility",
                ],
            },
            "innerValidation": {
                "foldCount": 3,
                "evaluationMonths": 1,
                "stepMonths": 1,
            },
        },
    }


def test_api_exposes_4b3_health_contract_and_candidate_safety_bounds() -> None:
    health = api_module.health()

    assert api_module.WALK_FORWARD_API_CONTRACT_VERSION == (
        "walk-forward-api-2026-08-18.4"
    )
    assert health["api_contract_version"] == api_module.WALK_FORWARD_API_CONTRACT_VERSION
    assert health["dual_momentum_parameter_optimization_job_contract_version"] == (
        DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_JOB_CONTRACT_VERSION
    )
    assert health["max_parameter_candidates"] == api_module.MAX_PARAMETER_CANDIDATES
    assert health["max_inner_folds"] == api_module.MAX_INNER_FOLDS
    assert health["max_tuning_evaluations_per_job"] == (
        api_module.MAX_TUNING_EVALUATIONS_PER_JOB
    )


def test_api_normalizes_explicit_optimization_into_separate_domain_spec() -> None:
    request = api_module.WalkForwardRequest.model_validate(
        {
            "periods": [_period()],
            "selector": _optimized_selector(),
            "execution": {
                "initialAmountTwd": 100_000,
                "transitionCostBps": 5,
            },
        }
    )
    spec = api_module._domain_spec(request)

    assert isinstance(spec.selector, DualMomentumParameterOptimizationSpec)
    assert spec.selector.risky_symbols == ("AAA", "BBB")
    assert spec.selector.defensive_symbols == ("BND",)
    assert spec.selector.search_space.lookback_months == (6, 12)
    assert spec.selector.search_space.top_k == (1,)
    assert spec.selector.search_space.absolute_thresholds == (0.0, 0.05)
    assert spec.selector.search_space.allocation_methods == (
        "equal",
        "inverse_volatility",
        "risk_parity_erc",
    )
    assert spec.selector.search_space.candidate_count == 12
    assert spec.selector.inner_validation.fold_count == 3

    selector_payload = _spec_payload(spec)["selector"]
    assert selector_payload["weighting"] == "parameter_optimized"
    assert "lookbackMonths" not in selector_payload
    assert "topK" not in selector_payload
    assert "absoluteThreshold" not in selector_payload
    assert "allocationMethod" not in selector_payload
    assert selector_payload["parameterOptimization"]["searchSpace"][
        "candidateCount"
    ] == 12


def test_api_rejects_ambiguous_manual_and_auto_parameter_authority() -> None:
    selector = _optimized_selector()
    selector["lookbackMonths"] = 12

    with pytest.raises(ValidationError, match="parameterOptimization cannot be combined"):
        api_module.WalkForwardRequest.model_validate(
            {"periods": [_period()], "selector": selector}
        )

    selector = _optimized_selector()
    selector["allocationMethod"] = "equal"
    with pytest.raises(ValidationError, match="allocationMethod"):
        api_module.WalkForwardRequest.model_validate(
            {"periods": [_period()], "selector": selector}
        )


def test_api_rejects_parameter_optimization_for_exhaustive() -> None:
    with pytest.raises(ValidationError, match="parameterOptimization requires"):
        api_module.WalkForwardRequest.model_validate(
            {
                "periods": [_period()],
                "selector": {
                    "universe": "soxx",
                    "benchmark": "SPY",
                    "holdingCount": 5,
                    "parameterOptimization": _optimized_selector()[
                        "parameterOptimization"
                    ],
                },
            }
        )


def test_manual_dual_request_omitting_parameter_optimization_keeps_old_shape() -> None:
    request = api_module.WalkForwardRequest.model_validate(
        {
            "periods": [_period()],
            "selector": {
                "strategy": "dual_momentum",
                "riskySymbols": ["AAA", "BBB"],
                "defensiveSymbols": ["BND"],
                "lookbackMonths": 12,
                "topK": 2,
                "absoluteThreshold": 0.0,
                "allocationMethod": "risk_parity_erc",
            },
        }
    )
    spec = api_module._domain_spec(request)

    assert isinstance(spec.selector, DualMomentumSelectorSpec)
    assert _spec_payload(spec)["selector"] == {
        "strategy": "dual_momentum",
        "riskySymbols": ["AAA", "BBB"],
        "defensiveSymbols": ["BND"],
        "lookbackMonths": 12,
        "topK": 2,
        "absoluteThreshold": 0.0,
        "rebalanceFrequency": "monthly",
        "weighting": "risk_parity_erc",
        "signalAuthority": "ResearchDataset.daily_levels_twd",
        "allocationMethod": "risk_parity_erc",
        "allocationReturnAuthority": "ResearchDataset.daily_returns_twd",
        "allocationCovarianceAuthority": (
            "risk-math-twd-2026-08-09.1/ledoit-wolf"
        ),
    }
