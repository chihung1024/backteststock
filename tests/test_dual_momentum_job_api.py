from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import api.walk_forward_v1 as api_module
from apps.api.app.data.history_service import PartialTWDHistories, TWDAssetHistory
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.research.walk_forward import WalkForwardPeriod
from apps.api.app.research.walk_forward_job import (
    DUAL_MOMENTUM_JOB_CONTRACT_VERSION,
    WALK_FORWARD_DUAL_MOMENTUM_SELECTOR_POLICY,
    DualMomentumSelectorSpec,
    WalkForwardExecutionSpec,
    WalkForwardJobService,
    WalkForwardJobSpec,
)


class ForbiddenPITResolver:
    def resolve(self, _universe_id: str, _requested_as_of: date):  # noqa: ANN201
        raise AssertionError("Dual Momentum must not resolve PIT membership")


class DualHistoryService:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], date, date]] = []

    def histories_partial(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> PartialTWDHistories:
        requested = tuple(symbols)
        self.calls.append((requested, start, end))
        dates = pd.bdate_range(start.isoformat(), end.isoformat())
        if start < date(2024, 4, 30):
            endings = {"AAA": 150.0, "BBB": 120.0, "BND": 105.0}
        else:
            endings = {symbol: 105.0 for symbol in requested}
        histories = {
            symbol: _history(symbol, dates, ending=endings[symbol])
            for symbol in requested
        }
        return PartialTWDHistories(
            requested=requested,
            histories=histories,
            failures={},
        )


def _history(symbol: str, dates: pd.DatetimeIndex, *, ending: float) -> TWDAssetHistory:
    levels = pd.Series(
        np.linspace(100.0, ending, len(dates)),
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
            daily_returns=levels.pct_change(fill_method=None)
            .fillna(0.0)
            .rename("daily_return"),
        ),
        corporate_action_audit={"status": "verified_standard_actions"},
        fx_audit={"method": "identity", "tickers": []},
        raw_quote_currency="TWD",
        native_price_scale=1.0,
    )


def _dual_spec() -> WalkForwardJobSpec:
    return WalkForwardJobSpec(
        periods=(
            WalkForwardPeriod(
                period_id="2024-04",
                training_start=date(2024, 1, 2),
                training_end=date(2024, 4, 30),
                decision_date=date(2024, 4, 30),
                evaluation_start=date(2024, 5, 1),
                evaluation_end=date(2024, 5, 31),
            ),
        ),
        selector=DualMomentumSelectorSpec(
            risky_symbols=("AAA", "BBB"),
            defensive_symbols=("BND",),
            lookback_months=3,
            top_k=1,
            absolute_threshold=0.0,
        ),
        execution=WalkForwardExecutionSpec(
            initial_amount=100_000.0,
            transition_cost_bps=5.0,
        ),
    )


def test_dual_momentum_job_skips_pit_and_exhaustive_but_reuses_oos_authority():
    history = DualHistoryService()

    def forbidden_authority():  # noqa: ANN202
        raise AssertionError("Dual Momentum must not initialize Exhaustive authority")

    service = WalkForwardJobService(
        pit_resolver=ForbiddenPITResolver(),
        history_service=history,
        authority_runner_factory=forbidden_authority,
    )
    result = service.run(_dual_spec())

    assert [call[0] for call in history.calls] == [("AAA", "BBB", "BND"), ("AAA",)]
    assert result.contract_version == DUAL_MOMENTUM_JOB_CONTRACT_VERSION
    assert result.selector_policy == WALK_FORWARD_DUAL_MOMENTUM_SELECTOR_POLICY
    assert result.decisions[0].pit_universe is None
    assert result.decisions[0].selected_constituents == ("AAA",)
    assert result.oos.periods[0].decision_hash == result.decisions[0].decision_hash
    assert result.oos.metrics.metrics["initial_balance"] == 100_000.0
    exported = result.export_payload()
    assert exported["request"]["selector"]["strategy"] == "dual_momentum"
    assert exported["request"]["selector"]["rebalanceFrequency"] == "monthly"
    assert exported["decisions"][0]["selectionEvidence"]["regime"] == "risk_on"
    assert len(result.job_hash) == 64


def test_dual_momentum_schedule_is_server_authoritative_and_monthly():
    selector = DualMomentumSelectorSpec(
        risky_symbols=("AAA", "BBB"),
        defensive_symbols=("BND",),
        lookback_months=3,
        top_k=1,
    )
    too_long = WalkForwardPeriod(
        period_id="too-long",
        training_start=date(2024, 1, 2),
        training_end=date(2024, 4, 30),
        decision_date=date(2024, 4, 30),
        evaluation_start=date(2024, 5, 1),
        evaluation_end=date(2024, 6, 30),
    )
    with pytest.raises(ValueError, match="at most 35"):
        WalkForwardJobSpec(periods=(too_long,), selector=selector)

    short_training = WalkForwardPeriod(
        period_id="short-training",
        training_start=date(2024, 3, 1),
        training_end=date(2024, 4, 30),
        decision_date=date(2024, 4, 30),
        evaluation_start=date(2024, 5, 1),
        evaluation_end=date(2024, 5, 31),
    )
    with pytest.raises(ValueError, match="full configured momentum lookback"):
        WalkForwardJobSpec(periods=(short_training,), selector=selector)


def _api_payload() -> dict:
    return {
        "periods": [
            {
                "periodId": "2024-04",
                "trainingStart": "2024-01-02",
                "trainingEnd": "2024-04-30",
                "decisionDate": "2024-04-30",
                "evaluationStart": "2024-05-01",
                "evaluationEnd": "2024-05-31",
            }
        ],
        "selector": {
            "strategy": "dual_momentum",
            "riskySymbols": ["aaa", "BBB"],
            "defensiveSymbols": ["bnd"],
            "lookbackMonths": 3,
            "topK": 1,
            "absoluteThreshold": 0,
        },
        "execution": {
            "initialAmountTwd": 100000,
            "transitionCostBps": 5,
        },
    }


def test_api_normalizes_explicit_dual_momentum_selector(monkeypatch):
    api_module._limiter._requests.clear()
    captured = {}

    class Service:
        def run(self, spec):  # noqa: ANN001
            captured["spec"] = spec
            return type(
                "Result",
                (),
                {
                    "job_hash": "b" * 64,
                    "as_of_date": date(2024, 5, 31),
                    "contract_version": DUAL_MOMENTUM_JOB_CONTRACT_VERSION,
                    "export_payload": lambda self: {
                        "status": "completed",
                        "jobHash": "b" * 64,
                    },
                },
            )()

    monkeypatch.setattr(api_module, "get_service", lambda: Service())
    client = TestClient(api_module.app)
    response = client.post("/api/v1/research/walk-forward", json=_api_payload())

    assert response.status_code == 200
    spec = captured["spec"]
    assert isinstance(spec.selector, DualMomentumSelectorSpec)
    assert spec.selector.risky_symbols == ("AAA", "BBB")
    assert spec.selector.defensive_symbols == ("BND",)
    assert response.headers["x-walk-forward-job-contract-version"] == (
        DUAL_MOMENTUM_JOB_CONTRACT_VERSION
    )


def test_api_rejects_hidden_pit_universe_on_dual_momentum_request():
    api_module._limiter._requests.clear()
    payload = _api_payload()
    payload["selector"]["universe"] = "soxx"
    client = TestClient(api_module.app)

    response = client.post("/api/v1/research/walk-forward", json=payload)

    assert response.status_code == 422
    assert "not a PIT universe id" in str(response.json())
