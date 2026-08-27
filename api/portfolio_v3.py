"""Vercel ASGI entrypoint for the self-owned Portfolio v3 API."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

_CACHE_ROOT = Path("/tmp/.cache")
_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HOME", "/tmp")
os.environ.setdefault("XDG_CACHE_HOME", str(_CACHE_ROOT))

from fastapi import FastAPI, HTTPException, Query, Request, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from api import date_policy  # noqa: E402
from apps.api.app.portfolio.analytics import (  # noqa: E402
    PORTFOLIO_ANALYTICS_CONTRACT_VERSION,
)
from apps.api.app.portfolio.api_models import (  # noqa: E402
    PORTFOLIO_API_CONTRACT_VERSION,
    PORTFOLIO_API_SCHEMA_VERSION,
    AssetSearchResult,
    BacktestResponse,
    PortfolioRequest,
    PreflightResponse,
)
from apps.api.app.portfolio.api_service import PortfolioAPIService  # noqa: E402
from apps.api.app.portfolio.ledger import (  # noqa: E402
    PORTFOLIO_LEDGER_CONTRACT_VERSION,
)
from apps.api.app.portfolio.metrics import (  # noqa: E402
    PORTFOLIO_METRIC_CONTEXT_VERSION,
)
from apps.api.app.portfolio.models import MAX_PORTFOLIOS  # noqa: E402
from apps.api.app.portfolio.service import (  # noqa: E402
    PORTFOLIO_SERVICE_CONTRACT_VERSION,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

MAX_REQUEST_BYTES = 512 * 1024
GENERAL_REQUESTS_PER_MINUTE = 20
BACKTEST_REQUESTS_PER_MINUTE = 4


class MinuteRateLimiter:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.RLock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            window = self._requests[key]
            while window and now - window[0] > 60.0:
                window.popleft()
            if len(window) >= self.limit:
                return False
            window.append(now)
            return True


_general_limiter = MinuteRateLimiter(GENERAL_REQUESTS_PER_MINUTE)
_backtest_limiter = MinuteRateLimiter(BACKTEST_REQUESTS_PER_MINUTE)

app = FastAPI(
    title="Backteststock Portfolio v3 API",
    version=PORTFOLIO_API_SCHEMA_VERSION,
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://backteststock.chired.workers.dev"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-Id"],
    max_age=86_400,
)


@lru_cache
def get_service() -> PortfolioAPIService:
    return PortfolioAPIService()


def _secure_response(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Portfolio-API-Schema-Version"] = PORTFOLIO_API_SCHEMA_VERSION
    return response


def _error_response(status_code: int, detail: str) -> JSONResponse:
    return _secure_response(
        JSONResponse(status_code=status_code, content={"detail": detail})
    )


def _complete_period(payload: PortfolioRequest) -> date_policy.CompletePeriod:
    """Validate Portfolio v3's inclusive end date against the shared daily-bar policy."""

    return date_policy.require_complete_period(
        payload.start_date,
        payload.end_date + timedelta(days=1),
    )


def _apply_as_of_headers(response: Response, period: date_policy.CompletePeriod) -> None:
    response.headers["X-As-Of-Date"] = period.as_of_date.isoformat()
    response.headers["X-As-Of-Policy"] = period.as_of_policy


def _request_schema_max_portfolios() -> int | None:
    """Return the effective Pydantic request limit deployed in this runtime."""

    schema = PortfolioRequest.model_json_schema()
    value = schema.get("properties", {}).get("portfolios", {}).get("maxItems")
    return int(value) if isinstance(value, int) else None


@app.middleware("http")
async def request_guard(request: Request, call_next: Any) -> Response:
    path = request.url.path
    if path.startswith("/api/v3/portfolio/"):
        forwarded = request.headers.get("x-forwarded-for", "")
        fallback = request.client.host if request.client else "unknown"
        client_key = forwarded.split(",")[0].strip() or fallback
        if not _general_limiter.allow(client_key):
            return _error_response(
                429,
                "Portfolio API rate limit exceeded. Try again in one minute.",
            )
        if path.endswith("/backtests") and not _backtest_limiter.allow(client_key):
            return _error_response(
                429,
                "Portfolio backtest rate limit exceeded. Try again in one minute.",
            )
        declared_header = request.headers.get("content-length")
        if declared_header:
            try:
                declared = int(declared_header)
            except ValueError:
                return _error_response(400, "Content-Length must be an integer.")
            if declared < 0:
                return _error_response(400, "Content-Length cannot be negative.")
            if declared > MAX_REQUEST_BYTES:
                return _error_response(413, "Portfolio request body is too large.")
        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if len(body) > MAX_REQUEST_BYTES:
                return _error_response(413, "Portfolio request body is too large.")
    return _secure_response(await call_next(request))


@app.get("/api/v3/portfolio/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "backteststock-portfolio-v3",
        "contract_version": PORTFOLIO_API_CONTRACT_VERSION,
        "schema_version": PORTFOLIO_API_SCHEMA_VERSION,
        "ledger_contract_version": PORTFOLIO_LEDGER_CONTRACT_VERSION,
        "metric_context_version": PORTFOLIO_METRIC_CONTEXT_VERSION,
        "service_contract_version": PORTFOLIO_SERVICE_CONTRACT_VERSION,
        "analytics_contract_version": PORTFOLIO_ANALYTICS_CONTRACT_VERSION,
        "deployment_sha": os.getenv("VERCEL_GIT_COMMIT_SHA", ""),
        "max_portfolios": MAX_PORTFOLIOS,
        "request_schema_max_portfolios": _request_schema_max_portfolios(),
    }


@app.get(
    "/api/v3/portfolio/assets/search",
    response_model=list[AssetSearchResult],
)
async def search_assets(
    q: str = Query(min_length=1, max_length=64),
    limit: int = Query(default=8, ge=1, le=12),
) -> list[AssetSearchResult]:
    return await asyncio.to_thread(get_service().search_assets, q, limit)


@app.post(
    "/api/v3/portfolio/preflight",
    response_model=PreflightResponse,
)
async def preflight(payload: PortfolioRequest, response: Response) -> PreflightResponse:
    try:
        period = _complete_period(payload)
        result = await asyncio.to_thread(get_service().preflight, payload)
        _apply_as_of_headers(response, period)
        return result
    except (ValueError, date_policy.DatePolicyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post(
    "/api/v3/portfolio/backtests",
    response_model=BacktestResponse,
)
async def backtests(payload: PortfolioRequest, response: Response) -> BacktestResponse:
    try:
        period = _complete_period(payload)
        result = await asyncio.to_thread(get_service().backtest, payload)
        _apply_as_of_headers(response, period)
        return result
    except (ValueError, date_policy.DatePolicyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.exception_handler(Exception)
async def unexpected_error(_request: Request, exc: Exception) -> Response:
    logger.exception("Unexpected Portfolio v3 API failure", exc_info=exc)
    return _error_response(500, "Unexpected Portfolio v3 API failure.")
