from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

import api.walk_forward_v1 as module


def _payload() -> dict:
    return {
        "periods": [
            {
                "periodId": "p1",
                "trainingStart": "2024-01-02",
                "trainingEnd": "2024-04-30",
                "decisionDate": "2024-04-30",
                "evaluationStart": "2024-05-01",
                "evaluationEnd": "2024-05-10",
            }
        ],
        "selector": {
            "universe": "SOXX",
            "benchmark": "spy",
            "holdingCount": 1,
        },
        "execution": {
            "initialAmountTwd": 100000,
            "transitionCostBps": 5,
        },
    }


def test_walk_forward_api_normalizes_boundary_input_and_returns_job_headers(monkeypatch):
    module._limiter._requests.clear()
    captured = {}

    class Service:
        def run(self, spec):  # noqa: ANN001
            captured["spec"] = spec
            return SimpleNamespace(
                job_hash="a" * 64,
                as_of_date=date(2024, 5, 10),
                export_payload=lambda: {"status": "completed", "jobHash": "a" * 64},
            )

    monkeypatch.setattr(module, "get_service", lambda: Service())
    client = TestClient(module.app)
    response = client.post("/api/v1/research/walk-forward", json=_payload())

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.headers["x-walk-forward-job-hash"] == "a" * 64
    spec = captured["spec"]
    assert spec.selector.universe_id == "soxx"
    assert spec.selector.benchmark_symbol == "SPY"
    assert spec.selector.holding_count == 1
    assert spec.execution.transition_cost_bps == 5.0


def test_walk_forward_api_forbids_unversioned_selector_strategy_knobs():
    module._limiter._requests.clear()
    payload = _payload()
    payload["selector"]["rebalanceMode"] = "monthly"
    client = TestClient(module.app)

    response = client.post("/api/v1/research/walk-forward", json=payload)

    assert response.status_code == 422


def test_walk_forward_api_rejects_temporally_invalid_schedule_before_service(monkeypatch):
    module._limiter._requests.clear()
    payload = _payload()
    payload["periods"][0]["evaluationStart"] = "2024-04-30"

    class Service:
        def run(self, _spec):  # noqa: ANN001
            raise AssertionError("invalid schedule must not reach service")

    monkeypatch.setattr(module, "get_service", lambda: Service())
    client = TestClient(module.app)
    response = client.post("/api/v1/research/walk-forward", json=payload)

    assert response.status_code == 422
    assert "strictly after decision_date" in response.json()["detail"]


def test_walk_forward_health_is_side_effect_free_and_bypasses_research_quota():
    module._limiter._requests.clear()
    client = TestClient(module.app)

    responses = [
        client.get("/api/v1/research/walk-forward/health")
        for _ in range(module.REQUESTS_PER_MINUTE + 2)
    ]

    assert all(response.status_code == 200 for response in responses)
    assert all(
        response.json()["service"] == "backteststock-walk-forward-v1"
        for response in responses
    )
    assert not module._limiter._requests
