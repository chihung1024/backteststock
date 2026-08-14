from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

import api.portfolio_v3 as portfolio_api
from apps.api.app.portfolio.api_models import (
    AssetSearchResult,
    BacktestResponse,
    PreflightResponse,
)


class FakeService:
    def search_assets(self, query: str, limit: int = 8):
        assert query == "SPY"
        assert limit == 5
        return [AssetSearchResult(symbol="SPY", name="SPDR S&P 500 ETF Trust")]

    def preflight(self, request):
        return PreflightResponse(
            request_id="preflight-id",
            generated_at="2026-08-04T00:00:00+00:00",
            contract_version="portfolio-v3",
            schema_version="portfolio-v3-2026-08-04.1",
            base_currency="TWD",
            requested_start=request.start_date.isoformat(),
            requested_end=request.end_date.isoformat(),
            effective_end=request.end_date.isoformat(),
            assets=[],
            portfolios=[],
            warnings=[],
        )

    def backtest(self, request):
        return BacktestResponse(
            request_id="backtest-id",
            generated_at="2026-08-04T00:00:00+00:00",
            contract_version="portfolio-v3",
            schema_version="portfolio-v3-2026-08-04.1",
            base_currency="TWD",
            requested_start=request.start_date.isoformat(),
            requested_end=request.end_date.isoformat(),
            effective_end=request.end_date.isoformat(),
            results=[{"name": "Core", "metrics": {"cagr": 0.1}}],
            failures=[],
            assets=[],
            warnings=[],
            timing={"total_ms": 1.0},
            reproducibility={"api_schema_version": "portfolio-v3-2026-08-04.1"},
        )


def _payload() -> dict:
    return {
        "contract_version": "portfolio-v3",
        "portfolios": [
            {
                "name": "Core",
                "assets": [{"symbol": "SPY", "weight": 100}],
            }
        ],
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
    }


def test_health_exposes_self_owned_contract_versions(monkeypatch) -> None:
    monkeypatch.setattr(portfolio_api, "get_service", lambda: FakeService())
    client = TestClient(portfolio_api.app)

    response = client.get(
        "/api/v3/portfolio/health",
        headers={"x-forwarded-for": "203.0.113.1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "backteststock-portfolio-v3"
    assert payload["contract_version"] == "portfolio-v3"
    assert payload["ledger_contract_version"].startswith("portfolio-ledger-twd-")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-portfolio-api-schema-version"].startswith("portfolio-v3-")


def test_search_preflight_and_backtest_routes_use_typed_contract(monkeypatch) -> None:
    monkeypatch.setattr(portfolio_api, "get_service", lambda: FakeService())
    monkeypatch.setattr(
        portfolio_api.date_policy,
        "latest_complete_utc_date",
        lambda _now=None: date(2026, 8, 13),
    )
    client = TestClient(portfolio_api.app)

    search = client.get(
        "/api/v3/portfolio/assets/search?q=SPY&limit=5",
        headers={"x-forwarded-for": "203.0.113.2"},
    )
    preflight = client.post(
        "/api/v3/portfolio/preflight",
        json=_payload(),
        headers={"x-forwarded-for": "203.0.113.3"},
    )
    backtest = client.post(
        "/api/v3/portfolio/backtests",
        json=_payload(),
        headers={"x-forwarded-for": "203.0.113.4"},
    )

    assert search.status_code == 200
    assert search.json()[0]["symbol"] == "SPY"
    assert preflight.status_code == 200
    assert preflight.json()["request_id"] == "preflight-id"
    assert preflight.headers["x-as-of-date"] == "2026-08-13"
    assert preflight.headers["x-as-of-policy"] == portfolio_api.date_policy.AS_OF_POLICY
    assert backtest.status_code == 200
    assert backtest.json()["results"][0]["metrics"]["cagr"] == 0.1
    assert backtest.headers["x-as-of-date"] == "2026-08-13"
    assert backtest.headers["x-as-of-policy"] == portfolio_api.date_policy.AS_OF_POLICY


def test_api_rejects_unknown_fields_invalid_weights_and_oversized_requests(monkeypatch) -> None:
    monkeypatch.setattr(portfolio_api, "get_service", lambda: FakeService())
    client = TestClient(portfolio_api.app, raise_server_exceptions=False)

    invalid = _payload()
    invalid["unknown"] = True
    invalid_response = client.post(
        "/api/v3/portfolio/preflight",
        json=invalid,
        headers={"x-forwarded-for": "203.0.113.5"},
    )
    weight_payload = _payload()
    weight_payload["portfolios"][0]["assets"][0]["weight"] = 90
    weight_response = client.post(
        "/api/v3/portfolio/preflight",
        json=weight_payload,
        headers={"x-forwarded-for": "203.0.113.6"},
    )
    oversized = client.post(
        "/api/v3/portfolio/backtests",
        content=b"{}",
        headers={
            "content-type": "application/json",
            "content-length": str(portfolio_api.MAX_REQUEST_BYTES + 1),
            "x-forwarded-for": "203.0.113.7",
        },
    )

    assert invalid_response.status_code == 422
    assert weight_response.status_code == 422
    assert oversized.status_code == 413


def test_portfolio_routes_reject_incomplete_end_date_before_service(monkeypatch) -> None:
    monkeypatch.setattr(
        portfolio_api.date_policy,
        "latest_complete_utc_date",
        lambda _now=None: date(2026, 8, 13),
    )

    def service_must_not_run():
        raise AssertionError("Portfolio service must not run for an incomplete date")

    monkeypatch.setattr(portfolio_api, "get_service", service_must_not_run)
    client = TestClient(portfolio_api.app, raise_server_exceptions=False)
    payload = _payload()
    payload["start_date"] = "2026-01-02"
    payload["end_date"] = "2026-08-14"

    preflight = client.post(
        "/api/v3/portfolio/preflight",
        json=payload,
        headers={"x-forwarded-for": "203.0.113.8"},
    )
    backtest = client.post(
        "/api/v3/portfolio/backtests",
        json=payload,
        headers={"x-forwarded-for": "203.0.113.9"},
    )

    assert preflight.status_code == 422
    assert "2026-08-13" in preflight.json()["detail"]
    assert backtest.status_code == 422
    assert "2026-08-13" in backtest.json()["detail"]
