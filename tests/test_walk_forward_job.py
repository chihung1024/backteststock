from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from apps.api.app.data.history_service import PartialTWDHistories, TWDAssetHistory
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.research.walk_forward import ResolvedPITUniverse, WalkForwardPeriod
from apps.api.app.research.walk_forward_job import (
    WalkForwardExecutionSpec,
    WalkForwardJobService,
    WalkForwardJobSpec,
    WalkForwardSelectorSpec,
)


def _pit(members: tuple[str, ...], *, authoritative: bool = True) -> ResolvedPITUniverse:
    return ResolvedPITUniverse(
        universe_id="soxx",
        requested_as_of=date(2024, 4, 30),
        source_as_of=date(2024, 4, 30),
        evidence_available_as_of=date(2024, 4, 30),
        fetched_at="2024-04-30T12:00:00Z",
        version="2024-04-30-pit",
        checksum="abc123",
        members=members,
        membership_policy="latest-causally-available-observation-on-or-before-max-10d-v2",
        membership_authoritative=authoritative,
        source_label="Fixture source",
        source_url="https://example.com/source",
        source_is_proxy=not authoritative,
    )


class FakePITResolver:
    def __init__(self, resolved: ResolvedPITUniverse, events: list[str]) -> None:
        self.resolved = resolved
        self.events = events

    def resolve(self, universe_id: str, requested_as_of: date) -> ResolvedPITUniverse:
        self.events.append("pit")
        assert universe_id == "soxx"
        assert requested_as_of == date(2024, 4, 30)
        return self.resolved


class FakeHistoryService:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls: list[tuple[tuple[str, ...], date, date]] = []

    def histories_partial(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> PartialTWDHistories:
        requested = tuple(symbols)
        self.calls.append((requested, start, end))
        self.events.append("training_history" if start < date(2024, 4, 30) else "evaluation_history")
        dates = pd.bdate_range(start.isoformat(), end.isoformat())
        histories = {
            symbol: _history(symbol, dates, offset=index * 10.0)
            for index, symbol in enumerate(requested)
        }
        return PartialTWDHistories(
            requested=requested,
            histories=histories,
            failures={},
        )


class FakeAuthorityRunner:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def identity(self) -> dict[str, str]:
        self.events.append("authority_identity")
        return {
            "authorityVersion": "fixture-authority-v1",
            "bridgeVersion": "fixture-bridge-v1",
        }

    def select_best(self, payload: dict) -> dict:
        self.events.append("authority_select")
        candidates = list(payload["candidateTickers"])
        holding_count = int(payload["settings"]["holdingCount"])
        selected = candidates[:holding_count]
        return {
            "authorityVersion": "fixture-authority-v1",
            "bridgeVersion": "fixture-bridge-v1",
            "datasetHash": payload["datasetHash"],
            "combinationCount": math.comb(len(candidates), holding_count),
            "bestRank": 0,
            "selectedConstituents": selected,
            "weights": [1.0 / holding_count for _ in selected],
            "ranking": {
                "field": "optimized_score",
                "direction": "desc",
                "nonFinite": "negative-infinity",
                "tieBreak": "smaller-combination-rank",
            },
        }


def _history(symbol: str, dates: pd.DatetimeIndex, *, offset: float) -> TWDAssetHistory:
    levels = pd.Series(
        100.0 + offset + np.arange(len(dates), dtype=float),
        index=dates,
        dtype=float,
    )
    fx = pd.Series(1.0, index=dates, dtype=float)
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency="TWD",
        valuation=TWDValuation(
            source_currency="TWD",
            native_adjusted_close=levels.rename("native_adjusted_close"),
            fx_to_twd=fx.rename("fx_to_twd"),
            adjusted_close_twd=levels.rename("adjusted_close_twd"),
            daily_returns=levels.pct_change(fill_method=None).fillna(0.0).rename("daily_return"),
        ),
        corporate_action_audit={
            "status": "verified_standard_actions",
            "warning_dates": [],
        },
        fx_audit={"method": "identity", "tickers": []},
        raw_quote_currency="TWD",
        native_price_scale=1.0,
    )


def _spec() -> WalkForwardJobSpec:
    return WalkForwardJobSpec(
        periods=(
            WalkForwardPeriod(
                period_id="p1",
                training_start=date(2024, 1, 2),
                training_end=date(2024, 4, 30),
                decision_date=date(2024, 4, 30),
                evaluation_start=date(2024, 5, 1),
                evaluation_end=date(2024, 5, 10),
            ),
        ),
        selector=WalkForwardSelectorSpec(
            universe_id="soxx",
            benchmark_symbol="SPY",
            holding_count=1,
        ),
        execution=WalkForwardExecutionSpec(
            initial_amount=100_000.0,
            transition_cost_bps=5.0,
        ),
    )


def test_job_freezes_decision_before_oos_and_reuses_one_training_fetch():
    events: list[str] = []
    history_service = FakeHistoryService(events)
    runner = FakeAuthorityRunner(events)
    service = WalkForwardJobService(
        pit_resolver=FakePITResolver(_pit(("AAA", "BBB")), events),
        history_service=history_service,
        authority_runner_factory=lambda: runner,
    )

    result = service.run(_spec())

    assert events == [
        "pit",
        "training_history",
        "authority_identity",
        "authority_select",
        "evaluation_history",
    ]
    assert history_service.calls[0][0] == ("AAA", "BBB", "SPY")
    assert history_service.calls[1][0] == ("AAA",)
    assert len(history_service.calls) == 2
    assert result.decisions[0].selected_constituents == ("AAA",)
    assert result.period_audits[0].training_dataset_hash == result.decisions[0].training_dataset_hash
    assert result.period_audits[0].authority_dataset_hash != result.period_audits[0].training_dataset_hash
    assert result.oos.periods[0].decision_hash == result.decisions[0].decision_hash
    assert result.oos.metrics.metrics["initial_balance"] == 100_000.0
    assert len(result.job_hash) == 64
    exported = result.export_payload()
    assert exported["status"] == "completed"
    assert exported["selectorPolicy"] == "exhaustive-gross-buy-and-hold-v1"
    assert exported["request"]["selector"]["rebalanceMode"] == "never"
    assert exported["request"]["selector"]["trainingTransactionCostBps"] == 0.0


def test_job_rejects_proxy_membership_before_market_data():
    events: list[str] = []
    history_service = FakeHistoryService(events)
    service = WalkForwardJobService(
        pit_resolver=FakePITResolver(
            _pit(("AAA", "BBB"), authoritative=False),
            events,
        ),
        history_service=history_service,
        authority_runner_factory=lambda: FakeAuthorityRunner(events),
    )

    with pytest.raises(ValueError, match="authoritative PIT membership"):
        service.run(_spec())

    assert events == ["pit"]
    assert history_service.calls == []


def test_job_rejects_large_pit_universe_without_silent_truncation():
    events: list[str] = []
    members = tuple(f"S{index:03d}" for index in range(101))
    history_service = FakeHistoryService(events)
    service = WalkForwardJobService(
        pit_resolver=FakePITResolver(_pit(members), events),
        history_service=history_service,
        authority_runner_factory=lambda: FakeAuthorityRunner(events),
    )

    with pytest.raises(ValueError, match="will not silently truncate"):
        service.run(_spec())

    assert events == ["pit"]
    assert history_service.calls == []
