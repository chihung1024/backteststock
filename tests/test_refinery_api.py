from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from api import refinery_v1
from apps.api.app.refinery import (
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    REFINERY_API_SCHEMA_VERSION,
)


class FakeRefineryService:
    def preflight(self, payload):
        return {
            "contract_version": payload.contract_version,
            "schema_version": REFINERY_API_SCHEMA_VERSION,
            "endpoint": "preflight",
            "status": "ready",
            "symbols": list(payload.symbols),
        }

    def analyze(self, payload):
        return {
            "contract_version": payload.contract_version,
            "schema_version": REFINERY_API_SCHEMA_VERSION,
            "endpoint": "analyze",
            "status": "ok",
            "symbols": list(payload.symbols),
        }


def _payload() -> dict:
    return {
        "contract_version": "refinery-v1",
        "symbols": ["AAA", "BBB"],
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    }


def _client(monkeypatch, service=None) -> TestClient:
    monkeypatch.setattr(
        refinery_v1,
        "get_service",
        lambda: service or FakeRefineryService(),
    )
    monkeypatch.setattr(
        refinery_v1,
        "_general_limiter",
        refinery_v1.MinuteRateLimiter(10_000),
    )
    monkeypatch.setattr(
        refinery_v1,
        "_analyze_limiter",
        refinery_v1.MinuteRateLimiter(10_000),
    )
    return TestClient(refinery_v1.app)


def test_refinery_api_returns_canonical_secure_response(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/api/v1/refinery/preflight",
        json=_payload(),
        headers={"x-request-id": "test-request-id"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-refinery-api-schema-version"] == REFINERY_API_SCHEMA_VERSION
    assert response.headers["x-request-id"] == "test-request-id"
    assert response.content == refinery_v1._canonical_bytes(response.json())


def test_refinery_api_sanitizes_validation_errors(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/api/v1/refinery/preflight",
        json={
            **_payload(),
            "symbols": ["AAA"],
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_request"
    assert body["error"]["retryable"] is False
    assert "traceback" not in response.text.lower()


def test_refinery_api_rejects_declared_oversized_request(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/api/v1/refinery/preflight",
        content="{}",
        headers={
            "content-type": "application/json",
            "content-length": str(MAX_REQUEST_BYTES + 1),
        },
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_refinery_api_fails_closed_when_serialized_response_is_too_large(monkeypatch) -> None:
    class HugeService(FakeRefineryService):
        def analyze(self, payload):
            return {"data": "x" * (MAX_RESPONSE_BYTES + 1)}

    client = _client(monkeypatch, HugeService())
    response = client.post("/api/v1/refinery/analyze", json=_payload())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "response_too_large"
    assert len(response.content) < 2_000


def test_refinery_api_rate_limit_is_explicit(monkeypatch) -> None:
    client = _client(monkeypatch)
    monkeypatch.setattr(
        refinery_v1,
        "_general_limiter",
        refinery_v1.MinuteRateLimiter(1),
    )
    headers = {"x-forwarded-for": "203.0.113.50"}

    first = client.post("/api/v1/refinery/preflight", json=_payload(), headers=headers)
    second = client.post("/api/v1/refinery/preflight", json=_payload(), headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limit"
    assert second.json()["error"]["retryable"] is True


def test_refinery_api_rejects_future_end_date_without_calling_service(monkeypatch) -> None:
    class MustNotRun(FakeRefineryService):
        def preflight(self, payload):  # pragma: no cover - should never execute
            raise AssertionError("service must not run")

    client = _client(monkeypatch, MustNotRun())
    response = client.post(
        "/api/v1/refinery/preflight",
        json={
            **_payload(),
            "end_date": date.today().replace(year=date.today().year + 1).isoformat(),
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
