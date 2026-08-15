from __future__ import annotations

import math
import shutil
from datetime import date

import numpy as np
import pandas as pd
import pytest

from apps.api.app.data.history_service import (
    HistoryFailure,
    PartialTWDHistories,
    TWDAssetHistory,
)
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.research.dataset import build_research_dataset
from apps.api.app.research.exhaustive_selection import (
    EXHAUSTIVE_RANKING_DIRECTION,
    EXHAUSTIVE_RANKING_FIELD,
    EXHAUSTIVE_RANKING_TIE_BREAK,
    ExhaustiveSelectionEngine,
    NodeExhaustiveAuthorityRunner,
)
from apps.api.app.research.selection import run_selection
from apps.api.app.research.walk_forward import ResolvedPITUniverse, WalkForwardPeriod

CANDIDATES = ("AAA", "BBB", "CCC", "DDD")
BENCHMARK = "SPY"
TRAINING_START = date(2024, 1, 2)
TRAINING_END = date(2024, 4, 1)


def _period() -> WalkForwardPeriod:
    return WalkForwardPeriod(
        period_id="2024-04-A",
        training_start=TRAINING_START,
        training_end=TRAINING_END,
        decision_date=TRAINING_END,
        evaluation_start=date(2024, 4, 2),
        evaluation_end=date(2024, 4, 30),
    )


def _universe() -> ResolvedPITUniverse:
    return ResolvedPITUniverse(
        universe_id="synthetic-exhaustive",
        requested_as_of=TRAINING_END,
        source_as_of=date(2024, 3, 29),
        evidence_available_as_of=date(2024, 3, 29),
        fetched_at="2024-03-29T12:00:00Z",
        version="synthetic-2024-03-29",
        checksum="exhaustive123",
        members=CANDIDATES,
        membership_policy="latest-causal-v1",
        membership_authoritative=True,
        source_label="synthetic-official",
        source_url="https://example.test/exhaustive-universe",
        source_is_proxy=False,
    )


def _history(
    symbol: str,
    dates: pd.DatetimeIndex,
    values: np.ndarray,
) -> TWDAssetHistory:
    native = pd.Series(
        np.asarray(values, dtype=float),
        index=dates,
        dtype=float,
        name="native_adjusted_close",
    )
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
        corporate_action_audit={
            "status": "verified_standard_actions",
            "warning_dates": [],
        },
        fx_audit={"method": "identity", "tickers": []},
        raw_quote_currency="TWD",
        native_price_scale=1.0,
    )


def _histories(*, changed_aaa: bool = False, late_ddd: bool = False):
    dates = pd.bdate_range(TRAINING_START, TRAINING_END)
    positions = np.arange(len(dates), dtype=float)
    aaa = 100.0 * np.power(1.0025, positions)
    if changed_aaa:
        aaa = 100.0 * np.power(1.0035, positions)
    result = {
        "AAA": _history("AAA", dates, aaa),
        "BBB": _history(
            "BBB",
            dates,
            100.0 * np.power(1.0012, positions) * (1.0 + 0.015 * np.sin(positions / 3.0)),
        ),
        "CCC": _history(
            "CCC",
            dates,
            100.0 * np.power(1.0018, positions) * (1.0 + 0.020 * np.cos(positions / 5.0)),
        ),
        "DDD": _history(
            "DDD",
            dates,
            100.0 * np.power(1.0005, positions) * (1.0 + 0.010 * np.sin(positions / 2.0)),
        ),
        "SPY": _history(
            "SPY",
            dates,
            100.0 * np.power(1.0010, positions) * (1.0 + 0.008 * np.sin(positions / 4.0)),
        ),
    }
    if late_ddd:
        late_dates = dates[10:]
        late_positions = np.arange(len(late_dates), dtype=float)
        result["DDD"] = _history(
            "DDD",
            late_dates,
            100.0 * np.power(1.0005, late_positions),
        )
    return result


def _dataset(
    requested: tuple[str, ...],
    histories: dict[str, TWDAssetHistory],
    *,
    failures: dict[str, HistoryFailure] | None = None,
):
    return build_research_dataset(
        PartialTWDHistories(
            requested=requested,
            histories={symbol: histories[symbol] for symbol in requested if symbol in histories},
            failures=failures or {},
        ),
        start=TRAINING_START,
        end=TRAINING_END,
    )


def _candidate_and_authority(*, changed_authority_aaa: bool = False, late_ddd: bool = False):
    candidate_histories = _histories(late_ddd=late_ddd)
    authority_histories = (
        _histories(changed_aaa=True, late_ddd=late_ddd)
        if changed_authority_aaa
        else candidate_histories
    )
    candidates = _dataset(CANDIDATES, candidate_histories)
    authority = _dataset((*CANDIDATES, BENCHMARK), authority_histories)
    return candidates, authority


class FakeAuthorityRunner:
    def __init__(self, *, authority_version="exhaustive-band-test-v1", bridge_version="bridge-test-v1"):
        self.authority_version = authority_version
        self.bridge_version = bridge_version
        self.payloads = []

    def identity(self):
        return {
            "authorityVersion": self.authority_version,
            "bridgeVersion": self.bridge_version,
        }

    def select_best(self, payload):
        self.payloads.append(payload)
        holding_count = payload["settings"]["holdingCount"]
        return {
            "authorityVersion": self.authority_version,
            "bridgeVersion": self.bridge_version,
            "datasetHash": payload["datasetHash"],
            "ranking": {
                "field": EXHAUSTIVE_RANKING_FIELD,
                "direction": EXHAUSTIVE_RANKING_DIRECTION,
                "nonFinite": "negative-infinity",
                "tieBreak": EXHAUSTIVE_RANKING_TIE_BREAK,
            },
            "combinationCount": math.comb(len(payload["candidateTickers"]), holding_count),
            "bestRank": 0,
            "selectedConstituents": payload["candidateTickers"][:holding_count],
            "weights": [1.0 / holding_count] * holding_count,
        }


def _engine(authority_dataset, *, runner=None):
    return ExhaustiveSelectionEngine(
        authority_dataset=authority_dataset,
        benchmark_symbol=BENCHMARK,
        holding_count=2,
        rebalance_mode="never",
        band_ratio=0.20,
        transaction_cost_bps=0.0,
        execution_delay_trading_days=1,
        risk_free_rate=0.03,
        runner=runner or FakeAuthorityRunner(),
    )


def test_exhaustive_adapter_freezes_authority_identity_and_training_evidence():
    training, authority = _candidate_and_authority()
    runner = FakeAuthorityRunner()
    decision = run_selection(
        period=_period(),
        pit_universe=_universe(),
        training_dataset=training,
        engine=_engine(authority, runner=runner),
    )

    assert decision.selected_constituents == ("AAA", "BBB")
    assert decision.weights == (0.5, 0.5)
    params = decision.selector_parameters
    assert params["quantAuthority"] == "public/exhaustive-optimizer-core.js"
    assert params["authorityVersion"] == runner.authority_version
    assert params["bridgeVersion"] == runner.bridge_version
    assert params["authorityDatasetHash"] == authority.dataset_hash
    assert params["benchmarkSymbol"] == BENCHMARK
    assert params["ranking"]["field"] == EXHAUSTIVE_RANKING_FIELD
    assert params["ranking"]["tieBreak"] == EXHAUSTIVE_RANKING_TIE_BREAK
    assert runner.payloads[0]["candidateTickers"] == list(CANDIDATES)
    assert runner.payloads[0]["benchmark"] == BENCHMARK
    assert runner.payloads[0]["datasetHash"] == authority.dataset_hash


def test_exhaustive_adapter_rejects_candidate_history_drift_between_training_artifacts():
    training, authority = _candidate_and_authority(changed_authority_aaa=True)
    with pytest.raises(ValueError, match="history differs.*AAA"):
        run_selection(
            period=_period(),
            pit_universe=_universe(),
            training_dataset=training,
            engine=_engine(authority),
        )


def test_exhaustive_adapter_reuses_existing_strict_full_period_coverage_policy():
    training, authority = _candidate_and_authority(late_ddd=True)
    with pytest.raises(ValueError, match="不會靜默|覆蓋不足|DDD"):
        run_selection(
            period=_period(),
            pit_universe=_universe(),
            training_dataset=training,
            engine=_engine(authority),
        )


def test_exhaustive_adapter_does_not_silently_drop_unavailable_pit_members():
    histories = _histories()
    training = _dataset(
        CANDIDATES,
        histories,
        failures={
            "DDD": HistoryFailure(
                symbol="DDD",
                stage="download",
                detail="synthetic missing history",
                retryable=True,
            )
        },
    )
    authority = _dataset(("AAA", "BBB", "CCC", BENCHMARK), histories)
    with pytest.raises(ValueError, match="does not silently drop.*DDD"):
        run_selection(
            period=_period(),
            pit_universe=_universe(),
            training_dataset=training,
            engine=_engine(authority),
        )


def test_exhaustive_adapter_rejects_authority_result_with_wrong_dataset_identity():
    training, authority = _candidate_and_authority()

    class WrongDatasetRunner(FakeAuthorityRunner):
        def select_best(self, payload):
            result = dict(super().select_best(payload))
            result["datasetHash"] = "wrong-dataset"
            return result

    with pytest.raises(ValueError, match="different dataset"):
        run_selection(
            period=_period(),
            pit_universe=_universe(),
            training_dataset=training,
            engine=_engine(authority, runner=WrongDatasetRunner()),
        )


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for JS authority parity")
def test_node_exhaustive_authority_runs_end_to_end_behind_selection_engine():
    training, authority = _candidate_and_authority()
    engine = ExhaustiveSelectionEngine(
        authority_dataset=authority,
        benchmark_symbol=BENCHMARK,
        holding_count=2,
        rebalance_mode="never",
        band_ratio=0.20,
        transaction_cost_bps=0.0,
        execution_delay_trading_days=1,
        risk_free_rate=0.03,
        runner=NodeExhaustiveAuthorityRunner(timeout_seconds=60.0),
    )
    decision = run_selection(
        period=_period(),
        pit_universe=_universe(),
        training_dataset=training,
        engine=engine,
    )

    assert len(decision.selected_constituents) == 2
    assert set(decision.selected_constituents).issubset(set(CANDIDATES))
    assert decision.weights == pytest.approx((0.5, 0.5), abs=1e-12)
    assert decision.selector_parameters["authorityVersion"].startswith("exhaustive-band-")
    assert decision.selector_parameters["authorityDatasetHash"] == authority.dataset_hash
