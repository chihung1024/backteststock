from __future__ import annotations

from datetime import date

from api.request_guard import (
    EDGE_AUTH_HEADER,
    EDGE_CLIENT_ID_HEADER,
    EDGE_REQUIRED_ENV,
    EDGE_SECRET_ENV,
    GuardFailure,
    MAX_REQUEST_BYTES,
    authorize_edge_request,
    elapsed_budget_failure,
    request_body_failure,
    resolve_local_client_id,
    validate_work_budget,
)


def _local_env(monkeypatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("BACKTESTSTOCK_RUNTIME", raising=False)
    monkeypatch.delenv("BACKTESTSTOCK_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv(EDGE_REQUIRED_ENV, raising=False)
    monkeypatch.delenv(EDGE_SECRET_ENV, raising=False)


def test_missing_secret_is_available_for_local_and_test_runtime(monkeypatch) -> None:
    _local_env(monkeypatch)

    decision = authorize_edge_request({}, fallback_client_id="127.0.0.1")

    assert decision.authenticated is False
    assert decision.mode == "local-unconfigured"
    assert decision.client_id == "127.0.0.1"


def test_production_fails_closed_when_secret_is_missing(monkeypatch) -> None:
    _local_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")

    decision = authorize_edge_request({}, fallback_client_id="127.0.0.1")

    assert isinstance(decision, GuardFailure)
    assert decision.status_code == 503
    assert decision.code == "edge_auth_not_configured"


def test_configured_secret_only_trusts_edge_supplied_client_identity(monkeypatch) -> None:
    _local_env(monkeypatch)
    secret = "test-edge-secret-with-at-least-32-bytes"
    monkeypatch.setenv(EDGE_SECRET_ENV, secret)

    missing = authorize_edge_request({}, fallback_client_id="127.0.0.1")
    valid = authorize_edge_request(
        {
            EDGE_AUTH_HEADER: secret,
            EDGE_CLIENT_ID_HEADER: "cf-client-123",
            "x-forwarded-for": "198.51.100.9",
        },
        fallback_client_id="127.0.0.1",
    )

    assert isinstance(missing, GuardFailure)
    assert missing.status_code == 403
    assert valid.authenticated is True
    assert valid.client_id == "cf-client-123"
    assert valid.mode == "edge-authenticated"


def test_explicit_false_auth_mode_supports_only_the_documented_rollout(monkeypatch) -> None:
    _local_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv(EDGE_REQUIRED_ENV, "false")

    decision = authorize_edge_request({}, fallback_client_id="127.0.0.1")

    assert decision.authenticated is False
    assert decision.mode == "local-unconfigured"


def test_rollout_bypass_survives_secret_provisioning_until_worker_is_ready(
    monkeypatch,
) -> None:
    _local_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv(EDGE_REQUIRED_ENV, "false")
    secret = "test-edge-secret-with-at-least-32-bytes"
    monkeypatch.setenv(EDGE_SECRET_ENV, secret)

    missing = authorize_edge_request({}, fallback_client_id="127.0.0.1")
    invalid = authorize_edge_request(
        {EDGE_AUTH_HEADER: "wrong-edge-credential-with-at-least-32-bytes"},
        fallback_client_id="127.0.0.1",
    )
    valid = authorize_edge_request(
        {
            EDGE_AUTH_HEADER: secret,
            EDGE_CLIENT_ID_HEADER: "cf-client-123",
        },
        fallback_client_id="127.0.0.1",
    )

    assert missing.authenticated is False
    assert missing.mode == "migration-bypass"
    assert isinstance(invalid, GuardFailure)
    assert invalid.status_code == 403
    assert valid.authenticated is True
    assert valid.client_id == "cf-client-123"


def test_local_xff_is_only_a_best_effort_limiter_key(monkeypatch) -> None:
    _local_env(monkeypatch)
    assert resolve_local_client_id(
        {"x-forwarded-for": "198.51.100.8, 10.0.0.1"},
        fallback_client_id="127.0.0.1",
    ) == "198.51.100.8"

    monkeypatch.setenv("VERCEL", "1")
    assert resolve_local_client_id(
        {"x-forwarded-for": "198.51.100.8"},
        fallback_client_id="127.0.0.1",
    ) == "127.0.0.1"


def test_request_body_contract_checks_declared_and_read_sizes() -> None:
    invalid = request_body_failure({"content-length": "not-an-int"})
    negative = request_body_failure({"content-length": "-1"})
    declared = request_body_failure(
        {"content-length": str(MAX_REQUEST_BYTES + 1)},
    )
    actual = request_body_failure(
        {"content-length": "2"},
        b"123",
        maximum_bytes=2,
    )

    assert invalid.code == "invalid_content_length"
    assert negative.code == "invalid_content_length"
    assert declared.status_code == 413
    assert actual.status_code == 413


def test_work_budget_rejects_long_history_and_excessive_ticker_days() -> None:
    long_history = validate_work_budget(
        date(2020, 1, 1),
        date(2025, 1, 1),
        1,
        max_history_days=365,
        max_unit_days=10_000,
        label="Scan",
    )
    expensive = validate_work_budget(
        date(2024, 1, 1),
        date(2024, 2, 1),
        100,
        max_history_days=365,
        max_unit_days=1_000,
        label="Scan",
    )

    assert long_history.code == "history_budget_exceeded"
    assert expensive.code == "work_budget_exceeded"


def test_elapsed_budget_is_soft_and_retryable() -> None:
    assert elapsed_budget_failure(
        10.0,
        10.5,
        maximum_seconds=1.0,
        label="Scan",
    ) is None
    failure = elapsed_budget_failure(
        10.0,
        12.0,
        maximum_seconds=1.0,
        label="Scan",
    )

    assert failure.code == "time_budget_exceeded"
    assert failure.status_code == 504
    assert failure.retryable is True


def test_flask_expensive_boundaries_fail_closed_in_vercel_runtime(monkeypatch) -> None:
    _local_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")

    from api import exhaustive_optimizer, index_v2, scan_v2

    scan_response = scan_v2.app.test_client().post(
        "/api/scan",
        json={"tickers": ["AAA"], "benchmark": "SPY"},
    )
    backtest_response = index_v2.app.test_client().post(
        "/api/backtest",
        json={"portfolios": []},
    )
    exhaustive_response = exhaustive_optimizer.app.test_client().post(
        "/api/optimizer/exhaustive/prepare",
        json={},
    )

    assert scan_response.status_code == 503
    assert backtest_response.status_code == 503
    assert exhaustive_response.status_code == 503
    assert scan_response.get_json()["error"]


def test_fastapi_expensive_boundaries_fail_closed_in_vercel_runtime(monkeypatch) -> None:
    _local_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")

    from fastapi.testclient import TestClient

    from api import portfolio_v3, refinery_v1

    portfolio_response = TestClient(portfolio_v3.app).get(
        "/api/v3/portfolio/health"
    )
    refinery_response = TestClient(refinery_v1.app).post(
        "/api/v1/refinery/preflight",
        json={"contract_version": "refinery-v1"},
    )

    assert portfolio_response.status_code == 503
    assert refinery_response.status_code == 503


def test_screener_and_autocomplete_boundaries_fail_closed_in_vercel_runtime(
    monkeypatch,
) -> None:
    _local_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")

    from api import screener

    client = screener.app.test_client()
    screener_response = client.post("/api/v2/screener", json={})
    legacy_response = client.post("/api/screener", json={})
    autocomplete_response = client.get("/api/all-tickers")

    assert screener_response.status_code == 503
    assert legacy_response.status_code == 503
    assert autocomplete_response.status_code == 503


def test_scan_ticker_and_history_budgets_reject_before_service_call(monkeypatch) -> None:
    _local_env(monkeypatch)
    from api import scan_v2

    calls = []

    class MustNotRun:
        def run(self, *args, **kwargs):  # pragma: no cover - guard must reject first
            calls.append((args, kwargs))
            raise AssertionError("scan service must not run")

    monkeypatch.setattr(scan_v2, "twd_scan_service", MustNotRun())
    client = scan_v2.app.test_client()
    too_many = client.post(
        "/api/scan",
        json={
            "tickers": [f"T{index:03d}" for index in range(501)],
            "benchmark": "SPY",
            "startDate": "2024-01-01",
            "endDate": "2024-01-31",
        },
    )
    too_long = client.post(
        "/api/scan",
        json={
            "tickers": ["AAA"],
            "benchmark": "SPY",
            "startDate": "2000-01-01",
            "endDate": "2025-01-01",
        },
    )

    assert too_many.status_code == 400
    assert too_long.status_code == 400
    assert calls == []


def test_flask_request_body_ceiling_is_enforced_before_json_parse(monkeypatch) -> None:
    _local_env(monkeypatch)
    from api import scan_v2

    response = scan_v2.app.test_client().post(
        "/api/scan",
        data=b"x" * (MAX_REQUEST_BYTES + 1),
        content_type="application/json",
    )

    assert response.status_code == 413
    assert response.get_json()["retryable"] is False
