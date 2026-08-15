from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from apps.api.app.data.history_service import PartialTWDHistories, TWDAssetHistory
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.research.dataset import build_research_dataset
from apps.api.app.research.selection import (
    CONFIGURED_EQUAL_WEIGHT_ENGINE_VERSION,
    WALK_FORWARD_SELECTION_CONTRACT_VERSION,
    ConfiguredEqualWeightSelectionEngine,
    run_selection,
)
from apps.api.app.research.walk_forward import ResolvedPITUniverse, WalkForwardPeriod


def _dataset():
    dates = pd.bdate_range("2024-01-02", "2024-01-31")
    values = pd.Series(
        np.linspace(100.0, 120.0, len(dates)),
        index=dates,
        dtype=float,
        name="native_adjusted_close",
    )
    fx = pd.Series(1.0, index=dates, dtype=float, name="fx_to_twd")
    history = TWDAssetHistory(
        symbol="AAA",
        quote_currency="TWD",
        valuation=TWDValuation(
            source_currency="TWD",
            native_adjusted_close=values,
            fx_to_twd=fx,
            adjusted_close_twd=values.rename("adjusted_close_twd"),
            daily_returns=values.pct_change(fill_method=None)
            .fillna(0.0)
            .rename("daily_return"),
        ),
        corporate_action_audit={"status": "verified_standard_actions"},
        fx_audit={"method": "identity", "tickers": []},
        raw_quote_currency="TWD",
        native_price_scale=1.0,
    )
    return build_research_dataset(
        PartialTWDHistories(
            requested=("AAA",),
            histories={"AAA": history},
            failures={},
        ),
        start=date(2024, 1, 2),
        end=date(2024, 1, 31),
    )


def _period():
    return WalkForwardPeriod(
        period_id="identity",
        training_start=date(2024, 1, 2),
        training_end=date(2024, 1, 31),
        decision_date=date(2024, 1, 31),
        evaluation_start=date(2024, 2, 1),
        evaluation_end=date(2024, 2, 29),
    )


def _universe():
    return ResolvedPITUniverse(
        universe_id="synthetic",
        requested_as_of=date(2024, 1, 31),
        source_as_of=date(2024, 1, 30),
        evidence_available_as_of=date(2024, 1, 30),
        fetched_at="2024-01-30T12:00:00Z",
        version="synthetic-2024-01-30",
        checksum="abc123",
        members=("AAA",),
        membership_policy="latest-causal-v1",
        membership_authoritative=True,
        source_label="synthetic-official",
        source_url="https://example.test/universe",
        source_is_proxy=False,
    )


def test_decision_selector_identity_binds_core_and_engine_versions():
    decision = run_selection(
        period=_period(),
        pit_universe=_universe(),
        training_dataset=_dataset(),
        engine=ConfiguredEqualWeightSelectionEngine(("AAA",)),
    )
    assert decision.selector_contract_version == (
        f"{WALK_FORWARD_SELECTION_CONTRACT_VERSION}+"
        f"{CONFIGURED_EQUAL_WEIGHT_ENGINE_VERSION}"
    )


def test_reference_engine_identity_cannot_be_spoofed_via_constructor():
    with pytest.raises(TypeError):
        ConfiguredEqualWeightSelectionEngine(
            ("AAA",),
            contract_version="spoofed",
        )
