"""Vercel ASGI entrypoint for the self-owned Portfolio v3 API."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path
from typing import Any

_CACHE_ROOT = Path("/tmp/.cache")
_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HOME", "/tmp")
os.environ.setdefault("XDG_CACHE_HOME", str(_CACHE_ROOT))

from fastapi import FastAPI, HTTPException, Query, Request, Response, status  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

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
    docs_url=None if os.getenv("VERCEL") else "/api/v3/portfolio/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://backteststock.chired.workers.dev",
        "http://localhost:8787",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-Id"],
    max_age=86_400,
)


@lru_cache
def get_service() -> PortfolioAPIService:
    return PortfolioAPIService()


@app.middleware("http")
async def request_guard(request: Request, call_next: Any) -> Response:
    path = request.url.path
    if path.startswith("/api/v3/portfolio/"):
        forwarded = request.headers.get("x-forwarded-for", "")
        fallback = request.client.host if request.client else "unknown"
        client_key = forwarded.split(",")[0].strip() or fallback
        if not _general_limiter.allow(client_key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Portfolio API rate limit exceeded. Try again in one minute.",
            )
        if path.endswith("/backtests") and not _backtest_limiter.allow(client_key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Portfolio backtest rate limit exceeded. Try again in one minute.",
            )
        declared = int(request.headers.get("content-length") or "0")
        if declared > MAX_REQUEST_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Portfolio request body is too large.",
            )
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Portfolio-API-Schema-Version"] = PORTFOLIO_API_SCHEMA_VERSION
    return response


@app.get("/api/v3/portfolio/health")
def health() -> dict[str, str]:
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
async def preflight(payload: PortfolioRequest) -> PreflightResponse:
    try:
        return await asyncio.to_thread(get_service().preflight, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post(
    "/api/v3/portfolio/backtests",
    response_model=BacktestResponse,
)
async def backtests(payload: PortfolioRequest) -> BacktestResponse:
    try:
        return await asyncio.to_thread(get_service().backtest, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.exception_handler(Exception)
async def unexpected_error(_request: Request, exc: Exception) -> Response:
    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Unexpected Portfolio v3 API failure", exc_info=exc)
    return Response(
        content='{"detail":"Unexpected Portfolio v3 API failure."}',
        status_code=500,
        media_type="application/json",
    )
