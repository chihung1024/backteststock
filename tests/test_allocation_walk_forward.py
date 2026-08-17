from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

import api.walk_forward_v1 as api_module
from apps.api.app.data.history_service import PartialTWDHistories, TWDAssetHistory
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.research.dataset import build_research_dataset
from apps.api.app.research.momentum import (
    DualMomentumAllocatedSelectionEngine,
    DualMomentumSelectionEngine,
)
from apps.api.app.research.selection import run_configured_selection
from apps.api.app.research.walk_forward import ConfiguredResearchUniverse, WalkForwardPeriod
from apps.api.app.research.walk_forward_job import (
    DUAL_MOMENTUM_ALLOCATION_JOB_CONTRACT_VERSION,
    DUAL_MOMENTUM_JOB_CONTRACT_VERSION,
    WALK_FORWARD_DUAL_MOMENTUM_ALLOCATION_SELECTOR_POLICY,
    WALK_FORWARD_DUAL_MOMENTUM_SELECTOR_POLICY,
    DualMomentumSelectorSpec,
    WalkForwardJobSpec,
    _job_contract_version,
    _selector_policy,
    _spec_payload,
)


def _period() -> WalkForwardPeriod:
    return WalkForwardPeriod(
        period_id="2025-01",
        training_start=date(2024, 1, 31),
        training_end=date(2025, 1, 31),
        decision_date=date(2025, 1, 31),
        evaluation_start=date(2025, 2, 1),
        evaluation_end=date(2025, 2, 28),
    )


def _history(symbol: str, dates: pd.DatetimeIndex, daily: np.ndarray) -> TWDAssetHistory:
    levels = pd.Series(100.0 * np.cumprod(1.0 + daily), index=dates, dtype=float)
    fx = pd.Series(1.0, index=dates, dtype=float)
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency="TWD",
        valuation=TWDValuation(
            source_currency="TWD",
            native_adjusted_close=levels.rename("native_adjusted_close"),
            fx_to_twd=fx.rename("fx_to_twd"),
            adjusted_close_twd=levels.rename("adjusted_close_twd"),
            daily_returns=levels.pct_change(fill_method=None)
            .fillna(0.0)
            .rename("daily_return"),
        ),
        corporate_action_audit={"status": "verified_standard_actions"},
        fx_audit={"method": "identity", "tickers": []},
        raw_quote_currency="TWD",
        native_price_scale=1.0,
    )


def _dataset():
    dates = pd.bdate_range("2024-01-31", "2025-01-31")
    phase = np.arange(len(dates), dtype=float)
    daily_by_symbol = {
        "AAA": 0.0010 + 0.0070 * np.sin(phase / 5.0),
        "BBB": 0.0006 + 0.0030 * np.cos(phase / 7.0),
        "BND": 0.0001 + 0.0015 * np.sin(phase / 11.0),
    }
    histories = {
        symbol: _history(symbol, dates, daily)
        for symbol, daily in daily_by_symbol.items()
    }
    return build_research_dataset(
        PartialTWDHistories(
            requested=("AAA", "BBB", "BND"),
            histories=histories,
            failures={},
        ),
        start=date(2024, 1, 31),
        end=date(2025, 1, 31),
    )


def _selector(*, allocation_method: str | None) -> DualMomentumSelectorSpec:
    return DualMomentumSelectorSpec(
        risky_symbols=("AAA", "BBB"),
        defensive_symbols=("BND",),
        lookback_months=12,
        top_k=2,
        absolute_threshold=0.0,
        allocation_method=allocation_method,
    )


def test_legacy_dual_request_keeps_4b1_contract_and_normalized_request_shape() -> None:
    spec = WalkForwardJobSpec(periods=(_period(),), selector=_selector(allocation_method=None))

    assert _job_contract_version(spec.selector) == DUAL_MOMENTUM_JOB_CONTRACT_VERSION
    assert _selector_policy(spec.selector) == WALK_FORWARD_DUAL_MOMENTUM_SELECTOR_POLICY
    selector_payload = _spec_payload(spec)["selector"]
    assert selector_payload == {
        "strategy": "dual_momentum",
        "riskySymbols": ["AAA", "BBB"],
        "defensiveSymbols": ["BND"],
        "lookbackMonths": 12,
        "topK": 2,
        "absoluteThreshold": 0.0,
        "rebalanceFrequency": "monthly",
        "weighting": "equal",
        "signalAuthority": "ResearchDataset.daily_levels_twd",
    }


def test_explicit_allocation_gets_new_job_contract_and_request_identity() -> None:
    spec = WalkForwardJobSpec(
        periods=(_period(),),
        selector=_selector(allocation_method="risk_parity_erc"),
    )

    assert _job_contract_version(spec.selector) == (
        DUAL_MOMENTUM_ALLOCATION_JOB_CONTRACT_VERSION
    )
    assert _selector_policy(spec.selector) == (
        WALK_FORWARD_DUAL_MOMENTUM_ALLOCATION_SELECTOR_POLICY
    )
    selector_payload = _spec_payload(spec)["selector"]
    assert selector_payload["allocationMethod"] == "risk_parity_erc"
    assert selector_payload["weighting"] == "risk_parity_erc"
    assert selector_payload["allocationReturnAuthority"] == (
        "ResearchDataset.daily_returns_twd"
    )


def test_allocated_dual_momentum_freezes_training_only_weights_and_evidence() -> None:
    dataset = _dataset()
    universe = ConfiguredResearchUniverse(("AAA", "BBB", "BND"))

    legacy = run_configured_selection(
        period=_period(),
        configured_universe=universe,
        training_dataset=dataset,
        engine=DualMomentumSelectionEngine(
            risky_symbols=("AAA", "BBB"),
            defensive_symbols=("BND",),
            lookback_months=12,
            top_k=2,
        ),
    )
    explicit_equal = run_configured_selection(
        period=_period(),
        configured_universe=universe,
        training_dataset=dataset,
        engine=DualMomentumAllocatedSelectionEngine(
            risky_symbols=("AAA", "BBB"),
            defensive_symbols=("BND",),
            allocation_method="equal",
            lookback_months=12,
            top_k=2,
        ),
    )
    erc = run_configured_selection(
        period=_period(),
        configured_universe=universe,
        training_dataset=dataset,
        engine=DualMomentumAllocatedSelectionEngine(
            risky_symbols=("AAA", "BBB"),
            defensive_symbols=("BND",),
            allocation_method="risk_parity_erc",
            lookback_months=12,
            top_k=2,
        ),
    )

    assert legacy.selected_constituents == ("AAA", "BBB")
    assert explicit_equal.selected_constituents == legacy.selected_constituents
    assert explicit_equal.weights == legacy.weights == (0.5, 0.5)
    assert explicit_equal.decision_hash != legacy.decision_hash

    assert erc.selected_constituents == ("AAA", "BBB")
    assert sum(erc.weights) == pytest.approx(1.0)
    assert all(weight > 0.0 for weight in erc.weights)
    evidence = erc.export_payload()["selectionEvidence"]["allocation"]
    assert evidence["method"] == "risk_parity_erc"
    assert evidence["completeCaseObservations"] >= 60
    assert evidence["covariance"]["method"] == "ledoit-wolf-mle-spherical-target"
    assert evidence["riskBudgetShares"] == pytest.approx([0.5, 0.5], abs=1e-8)
    assert evidence["solver"]["maxAbsRiskBudgetError"] <= 1e-8


def test_api_normalizes_explicit_allocation_but_rejects_it_for_exhaustive() -> None:
    payload = {
        "periods": [
            {
                "periodId": "2025-01",
                "trainingStart": "2024-01-31",
                "trainingEnd": "2025-01-31",
                "decisionDate": "2025-01-31",
                "evaluationStart": "2025-02-01",
                "evaluationEnd": "2025-02-28",
            }
        ],
        "selector": {
            "strategy": "dual_momentum",
            "riskySymbols": ["aaa", "BBB"],
            "defensiveSymbols": ["bnd"],
            "lookbackMonths": 12,
            "topK": 2,
            "absoluteThreshold": 0,
            "allocationMethod": "inverse_volatility",
        },
    }
    request = api_module.WalkForwardRequest.model_validate(payload)
    spec = api_module._domain_spec(request)
    assert isinstance(spec.selector, DualMomentumSelectorSpec)
    assert spec.selector.allocation_method == "inverse_volatility"
    assert spec.selector.risky_symbols == ("AAA", "BBB")

    exhaustive = {
        **payload,
        "selector": {
            "universe": "soxx",
            "benchmark": "SPY",
            "holdingCount": 5,
            "allocationMethod": "risk_parity_erc",
        },
    }
    with pytest.raises(ValidationError, match="allocationMethod requires"):
        api_module.WalkForwardRequest.model_validate(exhaustive)
