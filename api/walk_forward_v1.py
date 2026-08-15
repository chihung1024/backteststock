"""Vercel ASGI entrypoint for causal Walk-Forward research orchestration v1."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections import defaultdict, deque
from datetime import date
from functools import lru_cache
from typing import Annotated

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api import date_policy
from apps.api.app.research.pit_client import PITResolverError
from apps.api.app.research.walk_forward import WalkForwardPeriod
from apps.api.app.research.walk_forward_job import (
    MAX_WALK_FORWARD_PERIODS,
    WALK_FORWARD_JOB_CONTRACT_VERSION,
    WalkForwardExecutionSpec,
    WalkForwardJobService,
    WalkForwardJobSpec,
    WalkForwardSelectorSpec,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

WALK_FORWARD_API_CONTRACT_VERSION = "walk-forward-api-2026-08-15.1"
MAX_REQUEST_BYTES = 128 * 1024
REQUESTS_PER_MINUTE = 2


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


_limiter = MinuteRateLimiter(REQUESTS_PER_MINUTE)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PeriodRequest(StrictModel):
    period_id: Annotated[str, Field(alias="periodId", min_length=1, max_length=80)]
    training_start: date = Field(alias="trainingStart")
    training_end: date = Field(alias="trainingEnd")
    decision_date: date = Field(alias="decisionDate")
    evaluation_start: date = Field(alias="evaluationStart")
    evaluation_end: date = Field(alias="evaluationEnd")

    @field_validator("period_id")
    @classmethod
    def clean_period_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("periodId is required")
        return cleaned


class SelectorRequest(StrictModel):
    universe: Annotated[str, Field(min_length=1, max_length=64)]
    benchmark: Annotated[str, Field(min_length=1, max_length=20)] = "SPY"
    holding_count: Annotated[int, Field(alias="holdingCount", ge=1, le=20)] = 10

    @field_validator("universe")
    @classmethod
    def clean_universe(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("benchmark")
    @classmethod
    def clean_benchmark(cls, value: str) -> str:
        return value.strip().upper()


class ExecutionRequest(StrictModel):
    initial_amount_twd: Annotated[
        float,
        Field(alias="initialAmountTwd", gt=0.0, le=1e12),
    ] = 10_000.0
    transition_cost_bps: Annotated[
        float,
        Field(alias="transitionCostBps", ge=0.0, le=1000.0),
    ] = 0.0


class WalkForwardRequest(StrictModel):
    periods: Annotated[
        list[PeriodRequest],
        Field(min_length=1, max_length=MAX_WALK_FORWARD_PERIODS),
    ]
    selector: SelectorRequest
    execution: ExecutionRequest = ExecutionRequest()


app = FastAPI(
    title="Backteststock Walk-Forward Research API",
    version=WALK_FORWARD_API_CONTRACT_VERSION,
    docs_url=None if os.getenv("VERCEL") else "/api/v1/research/walk-forward/docs",
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
def get_service() -> WalkForwardJobService:
    return WalkForwardJobService()


def _secure_response(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Walk-Forward-API-Contract-Version"] = WALK_FORWARD_API_CONTRACT_VERSION
    response.headers["X-Walk-Forward-Job-Contract-Version"] = WALK_FORWARD_JOB_CONTRACT_VERSION
    deployment_sha = os.getenv("VERCEL_GIT_COMMIT_SHA", "").strip()
    if deployment_sha:
        response.headers["X-Deployment-Sha"] = deployment_sha
    return response


def _error_response(status_code: int, detail: str) -> JSONResponse:
    return _secure_response(
        JSONResponse(status_code=status_code, content={"detail": detail})
    )


@app.middleware("http")
async def request_guard(request: Request, call_next):  # type: ignore[no-untyped-def]
    path = request.url.path
    if path.startswith("/api/v1/research/walk-forward"):
        forwarded = request.headers.get("x-forwarded-for", "")
        fallback = request.client.host if request.client else "unknown"
        client_key = forwarded.split(",")[0].strip() or fallback
        if not _limiter.allow(client_key):
            return _error_response(
                429,
                "Walk-Forward research rate limit exceeded. Try again in one minute.",
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
                return _error_response(413, "Walk-Forward request body is too large.")
        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if len(body) > MAX_REQUEST_BYTES:
                return _error_response(413, "Walk-Forward request body is too large.")
    return _secure_response(await call_next(request))


@app.get("/api/v1/research/walk-forward/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "backteststock-walk-forward-v1",
        "api_contract_version": WALK_FORWARD_API_CONTRACT_VERSION,
        "job_contract_version": WALK_FORWARD_JOB_CONTRACT_VERSION,
        "deployment_sha": os.getenv("VERCEL_GIT_COMMIT_SHA", ""),
    }


@app.post("/api/v1/research/walk-forward")
async def run_walk_forward(payload: WalkForwardRequest, response: Response) -> dict:
    try:
        spec = _domain_spec(payload)
        result = await asyncio.to_thread(get_service().run, spec)
        response.headers["X-Walk-Forward-Job-Hash"] = result.job_hash
        response.headers["X-As-Of-Date"] = result.as_of_date.isoformat()
        response.headers["X-As-Of-Policy"] = date_policy.AS_OF_POLICY
        return result.export_payload()
    except PITResolverError as exc:
        status = 409 if exc.status_code in {400, 404, 409} else 502
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except (ValueError, TypeError, date_policy.DatePolicyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.exception_handler(Exception)
async def unexpected_error(_request: Request, exc: Exception) -> Response:
    logger.exception("Unexpected Walk-Forward API failure", exc_info=exc)
    return _error_response(500, "Unexpected Walk-Forward research failure.")


def _domain_spec(payload: WalkForwardRequest) -> WalkForwardJobSpec:
    periods = tuple(
        WalkForwardPeriod(
            period_id=item.period_id,
            training_start=item.training_start,
            training_end=item.training_end,
            decision_date=item.decision_date,
            evaluation_start=item.evaluation_start,
            evaluation_end=item.evaluation_end,
        )
        for item in payload.periods
    )
    return WalkForwardJobSpec(
        periods=periods,
        selector=WalkForwardSelectorSpec(
            universe_id=payload.selector.universe,
            benchmark_symbol=payload.selector.benchmark,
            holding_count=payload.selector.holding_count,
        ),
        execution=WalkForwardExecutionSpec(
            initial_amount=payload.execution.initial_amount_twd,
            transition_cost_bps=payload.execution.transition_cost_bps,
        ),
    )
