from __future__ import annotations

import inspect
from datetime import date

import numpy as np
import pandas as pd
import pytest

from apps.api.app.data.history_service import PartialTWDHistories, TWDAssetHistory
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.research.dataset import build_research_dataset
from apps.api.app.research.momentum import (
    DualMomentumSelectionEngine,
    passes_absolute_momentum,
    rank_relative_momentum,
    trailing_total_return,
)
from apps.api.app.research.selection import (
    SelectionContext,
    run_configured_selection,
)
from apps.api.app.research.walk_forward import (
    ConfiguredResearchUniverse,
    ResolvedPITUniverse,
    WalkForwardPeriod,
    create_decision_snapshot,
)


SYMBOLS = ("AAA", "BBB", "CCC", "BND", "IEF")


def _period() -> WalkForwardPeriod:
    return WalkForwardPeriod(
        period_id="2025-01",
        training_start=date(2024, 1, 2),
        training_end=date(2025, 1, 31),
        decision_date=date(2025, 1, 31),
        evaluation_start=date(2025, 2, 3),
        evaluation_end=date(2025, 2, 28),
    )


def _history(symbol: str, dates: pd.DatetimeIndex, values: np.ndarray) -> TWDAssetHistory:
    native = pd.Series(values, index=dates, dtype=float, name="native_adjusted_close")
    fx = pd.Series(1.0, index=dates, dtype=float, name="fx_to_twd")
    twd = native.rename("adjusted_close_twd")
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency="TWD",
        valuation=TWDValuation(
            source_currency="TWD",
            native_adjusted_close=native,
            fx_to_twd=fx,
            adjusted_close_twd=twd,
            daily_returns=twd.pct_change(fill_method=None)
            .fillna(0.0)
            .rename("daily_return"),
        ),
        corporate_action_audit={"status": "verified_standard_actions"},
        fx_audit={"method": "identity", "tickers": []},
        raw_quote_currency="TWD",
        native_price_scale=1.0,
    )


def _dataset(*, risk_on: bool = True):
    dates = pd.bdate_range("2024-01-02", "2025-01-31")
    endings = {
        "AAA": 155.0 if risk_on else 72.0,
        "BBB": 132.0 if risk_on else 82.0,
        "CCC": 94.0 if risk_on else 92.0,
        "BND": 106.0,
        "IEF": 114.0,
    }
    histories = {
        symbol: _history(symbol, dates, np.linspace(100.0, ending, len(dates)))
        for symbol, ending in endings.items()
    }
    return build_research_dataset(
        PartialTWDHistories(
            requested=SYMBOLS,
            histories=histories,
            failures={},
        ),
        start=date(2024, 1, 2),
        end=date(2025, 1, 31),
    )


def _engine() -> DualMomentumSelectionEngine:
    return DualMomentumSelectionEngine(
        risky_symbols=("AAA", "BBB", "CCC"),
        defensive_symbols=("BND", "IEF"),
        lookback_months=12,
        top_k=2,
        absolute_threshold=0.0,
    )


def test_configured_universe_is_distinct_hash_bound_request_provenance():
    first = ConfiguredResearchUniverse(SYMBOLS)
    second = ConfiguredResearchUniverse(SYMBOLS)
    reordered = ConfiguredResearchUniverse(("BBB", "AAA", "CCC", "BND", "IEF"))

    assert first.universe_hash == second.universe_hash
    assert first.universe_hash != reordered.universe_hash
    assert first.export_payload()["provenanceType"] == "configured-request"
    assert "sourceAsOf" not in first.export_payload()
    assert "requestedAsOf" not in first.export_payload()

    with pytest.raises(ValueError, match="canonical symbols"):
        ConfiguredResearchUniverse(("aaa", "BBB"))


def test_dual_momentum_uses_training_only_absolute_then_relative_top_k():
    assert "evaluation_dataset" not in inspect.signature(run_configured_selection).parameters
    assert "evaluation_dataset" not in SelectionContext.__dataclass_fields__

    decision = run_configured_selection(
        period=_period(),
        configured_universe=ConfiguredResearchUniverse(SYMBOLS),
        training_dataset=_dataset(risk_on=True),
        engine=_engine(),
    )
    payload = decision.export_payload()

    assert decision.pit_universe is None
    assert decision.selected_constituents == ("AAA", "BBB")
    assert decision.weights == (0.5, 0.5)
    assert payload["configuredUniverse"]["members"] == list(SYMBOLS)
    assert "pitUniverse" not in payload
    assert payload["selectionEvidence"]["regime"] == "risk_on"
    assert payload["selectionEvidence"]["selected"] == ["AAA", "BBB"]
    assert [item["symbol"] for item in payload["selectionEvidence"]["riskyRanking"]] == [
        "AAA",
        "BBB",
        "CCC",
    ]
    assert all(
        item["endDate"] <= _period().training_end.isoformat()
        for item in payload["selectionEvidence"]["riskyRanking"]
    )


def test_dual_momentum_defensive_fallback_is_deterministic():
    first = run_configured_selection(
        period=_period(),
        configured_universe=ConfiguredResearchUniverse(SYMBOLS),
        training_dataset=_dataset(risk_on=False),
        engine=_engine(),
    )
    second = run_configured_selection(
        period=_period(),
        configured_universe=ConfiguredResearchUniverse(SYMBOLS),
        training_dataset=_dataset(risk_on=False),
        engine=_engine(),
    )

    assert first.selected_constituents == ("IEF", "BND")
    assert first.weights == (0.5, 0.5)
    assert first.decision_hash == second.decision_hash
    evidence = first.export_payload()["selectionEvidence"]
    assert evidence["regime"] == "defensive"
    assert evidence["fallbackReason"] == "no-risky-asset-cleared-absolute-threshold"
    assert evidence["selected"] == ["IEF", "BND"]


def test_momentum_primitives_have_deterministic_ties_and_absolute_threshold():
    dates = pd.bdate_range("2024-01-31", "2025-01-31")
    same = pd.Series(np.linspace(100.0, 120.0, len(dates)), index=dates)
    aaa = trailing_total_return(
        same,
        symbol="AAA",
        as_of=date(2025, 1, 31),
        lookback_months=12,
    )
    bbb = trailing_total_return(
        same,
        symbol="BBB",
        as_of=date(2025, 1, 31),
        lookback_months=12,
    )

    assert rank_relative_momentum((bbb, aaa)) == (aaa, bbb)
    assert passes_absolute_momentum(aaa, threshold=aaa.total_return)
    assert not passes_absolute_momentum(aaa, threshold=aaa.total_return + 0.01)


def test_momentum_fails_closed_on_materially_short_lookback_history():
    dates = pd.bdate_range("2024-07-01", "2025-01-31")
    levels = pd.Series(np.linspace(100.0, 120.0, len(dates)), index=dates)
    with pytest.raises(ValueError, match="causal baseline"):
        trailing_total_return(
            levels,
            symbol="AAA",
            as_of=date(2025, 1, 31),
            lookback_months=12,
        )


def test_existing_pit_decision_golden_hash_is_unchanged():
    period = WalkForwardPeriod(
        period_id="2025-Q1",
        training_start=date(2022, 1, 1),
        training_end=date(2024, 12, 31),
        decision_date=date(2024, 12, 31),
        evaluation_start=date(2025, 1, 1),
        evaluation_end=date(2025, 3, 31),
    )
    pit = ResolvedPITUniverse(
        universe_id="sp500",
        requested_as_of=date(2024, 12, 31),
        source_as_of=date(2024, 12, 30),
        evidence_available_as_of=date(2024, 12, 30),
        fetched_at="2024-12-30T12:34:56Z",
        version="sp500-2024-12-30",
        checksum="abc123",
        members=("AAPL", "MSFT", "NVDA"),
        membership_policy="latest-causal-v1",
        membership_authoritative=True,
        source_label="official",
        source_url="https://example.test/universe",
        source_is_proxy=False,
    )
    decision = create_decision_snapshot(
        period=period,
        pit_universe=pit,
        training_dataset_hash="dataset-123",
        training_effective_start=date(2022, 1, 3),
        training_effective_end=date(2024, 12, 31),
        selector_contract_version="selector-test-v1",
        selector_rule="top-two",
        selector_parameters={"lookback": 252, "nested": {"enabled": True}},
        eligible_candidates=("AAPL", "MSFT", "NVDA"),
        selected_constituents=("AAPL", "MSFT"),
        weights=(0.5, 0.5),
    )

    assert decision.decision_hash == (
        "2c354e721d345430f4d71d1a71fb79d046d1d583233dd7fda5f1017fb14f17db"
    )
    payload = decision.export_payload()
    assert "pitUniverse" in payload
    assert "configuredUniverse" not in payload
    assert "selectionEvidence" not in payload
