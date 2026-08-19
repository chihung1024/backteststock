"""Vercel ASGI entrypoint for causal Walk-Forward research orchestration v1."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import threading
import time
from collections import defaultdict, deque
from datetime import date
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api import date_policy
from apps.api.app.research.parameter_optimization import (
    InnerValidationSpec,
    ParameterSearchSpace,
)
from apps.api.app.research.pit_client import PITResolverError
from apps.api.app.research.walk_forward import WalkForwardPeriod
from apps.api.app.research.walk_forward_job import (
    DUAL_MOMENTUM_ALLOCATION_JOB_CONTRACT_VERSION,
    DUAL_MOMENTUM_JOB_CONTRACT_VERSION,
    DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_JOB_CONTRACT_VERSION,
    MAX_CONFIGURED_STRATEGY_SYMBOLS,
    MAX_INNER_FOLDS,
    MAX_PARAMETER_CANDIDATES,
    MAX_TUNING_EVALUATIONS_PER_JOB,
    MAX_WALK_FORWARD_PERIODS,
    WALK_FORWARD_JOB_CONTRACT_VERSION,
    DualMomentumParameterOptimizationSpec,
    DualMomentumSelectorSpec,
    WalkForwardExecutionSpec,
    WalkForwardJobService,
    WalkForwardJobSpec,
    WalkForwardSelectorSpec,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

WALK_FORWARD_API_CONTRACT_VERSION = "walk-forward-api-2026-08-18.4"
WALK_FORWARD_PATH = "/api/v1/research/walk-forward"
WALK_FORWARD_HEALTH_PATH = f"{WALK_FORWARD_PATH}/health"
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


AllocationMethodRequest = Literal[
    "equal",
    "inverse_volatility",
    "risk_parity_erc",
]


class ParameterSearchSpaceRequest(StrictModel):
    lookback_months: Annotated[
        list[Annotated[int, Field(ge=1, le=60)]],
        Field(alias="lookbackMonths", min_length=1, max_length=60),
    ]
    top_k: Annotated[
        list[Annotated[int, Field(ge=1, le=20)]],
        Field(alias="topK", min_length=1, max_length=20),
    ]
    absolute_thresholds: Annotated[
        list[float],
        Field(alias="absoluteThresholds", min_length=1, max_length=64),
    ]
    allocation_methods: Annotated[
        list[AllocationMethodRequest],
        Field(alias="allocationMethods", min_length=1, max_length=3),
    ]

    @field_validator("absolute_thresholds")
    @classmethod
    def finite_thresholds(cls, values: list[float]) -> list[float]:
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("absoluteThresholds must contain only finite values")
        return values


class InnerValidationRequest(StrictModel):
    fold_count: Annotated[int, Field(alias="foldCount", ge=1, le=MAX_INNER_FOLDS)]
    evaluation_months: Annotated[
        int,
        Field(alias="evaluationMonths", ge=1, le=60),
    ] = 1
    step_months: Annotated[
        int,
        Field(alias="stepMonths", ge=1, le=60),
    ] = 1


class ParameterOptimizationRequest(StrictModel):
    search_space: ParameterSearchSpaceRequest = Field(alias="searchSpace")
    inner_validation: InnerValidationRequest = Field(alias="innerValidation")


class SelectorRequest(StrictModel):
    """Backward-compatible tagged selector request.

    Requests saved before 4B-1 omit ``strategy`` and therefore keep the existing
    Exhaustive behavior. New Dual Momentum requests must opt in explicitly.
    Phase 4B-3 uses a separate nested ``parameterOptimization`` object so manual
    4B-1/4B-2 fields retain their frozen omission/identity semantics.
    """

    strategy: Literal["exhaustive", "dual_momentum"] = "exhaustive"
    universe: Annotated[str | None, Field(min_length=1, max_length=64)] = None
    benchmark: Annotated[str, Field(min_length=1, max_length=20)] = "SPY"
    holding_count: Annotated[int, Field(alias="holdingCount", ge=1, le=20)] = 10
    risky_symbols: list[str] = Field(
        default_factory=list,
        alias="riskySymbols",
        max_length=MAX_CONFIGURED_STRATEGY_SYMBOLS,
    )
    defensive_symbols: list[str] = Field(
        default_factory=list,
        alias="defensiveSymbols",
        max_length=MAX_CONFIGURED_STRATEGY_SYMBOLS,
    )
    lookback_months: Annotated[int, Field(alias="lookbackMonths", ge=1, le=60)] = 12
    top_k: Annotated[int, Field(alias="topK", ge=1, le=20)] = 1
    absolute_threshold: float = Field(alias="absoluteThreshold", default=0.0)
    allocation_method: AllocationMethodRequest | None = Field(
        alias="allocationMethod",
        default=None,
    )
    parameter_optimization: ParameterOptimizationRequest | None = Field(
        alias="parameterOptimization",
        default=None,
    )

    @field_validator("universe")
    @classmethod
    def clean_universe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        return cleaned or None

    @field_validator("benchmark")
    @classmethod
    def clean_benchmark(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("risky_symbols", "defensive_symbols")
    @classmethod
    def clean_configured_symbols(cls, values: list[str]) -> list[str]:
        canonical = [str(value).strip().upper() for value in values]
        if any(not symbol for symbol in canonical):
            raise ValueError("configured strategy symbols must be non-empty")
        if len(set(canonical)) != len(canonical):
            raise ValueError("configured strategy symbols must be unique within each role")
        return canonical

    @field_validator("absolute_threshold")
    @classmethod
    def finite_manual_threshold(cls, value: float) -> float:
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError("absoluteThreshold must be finite")
        return numeric

    @model_validator(mode="after")
    def validate_strategy_fields(self) -> "SelectorRequest":
        if self.strategy == "exhaustive":
            if not self.universe:
                raise ValueError("universe is required for exhaustive selection")
            if self.risky_symbols or self.defensive_symbols:
                raise ValueError(
                    "riskySymbols/defensiveSymbols require strategy=dual_momentum"
                )
            if self.allocation_method is not None:
                raise ValueError(
                    "allocationMethod requires strategy=dual_momentum"
                )
            if self.parameter_optimization is not None:
                raise ValueError(
                    "parameterOptimization requires strategy=dual_momentum"
                )
            return self

        if self.universe is not None:
            raise ValueError(
                "Dual Momentum uses explicit risky/defensive symbols, not a PIT universe id"
            )
        if not self.risky_symbols or not self.defensive_symbols:
            raise ValueError(
                "Dual Momentum requires non-empty riskySymbols and defensiveSymbols"
            )
        if set(self.risky_symbols).intersection(self.defensive_symbols):
            raise ValueError("Dual Momentum risky and defensive symbols must not overlap")
        if len(self.risky_symbols) + len(self.defensive_symbols) > MAX_CONFIGURED_STRATEGY_SYMBOLS:
            raise ValueError(
                f"Dual Momentum supports at most {MAX_CONFIGURED_STRATEGY_SYMBOLS} total symbols"
            )

        if self.parameter_optimization is not None:
            manual_fields = {
                "lookback_months",
                "top_k",
                "absolute_threshold",
                "allocation_method",
            }
            conflicting = sorted(manual_fields.intersection(self.model_fields_set))
            if conflicting:
                aliases = {
                    "lookback_months": "lookbackMonths",
                    "top_k": "topK",
                    "absolute_threshold": "absoluteThreshold",
                    "allocation_method": "allocationMethod",
                }
                names = ", ".join(aliases[item] for item in conflicting)
                raise ValueError(
                    "parameterOptimization cannot be combined with explicit manual tuning fields: "
                    + names
                )
            return self

        if self.top_k > len(self.risky_symbols):
            raise ValueError("Dual Momentum topK cannot exceed riskySymbols count")
        return self


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
    execution: ExecutionRequest = Field(default_factory=ExecutionRequest)


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


def _secure_response(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Walk-Forward-API-Contract-Version"] = WALK_FORWARD_API_CONTRACT_VERSION
    if "X-Walk-Forward-Job-Contract-Version" not in response.headers:
        response.headers["X-Walk-Forward-Job-Contract-Version"] = (
            WALK_FORWARD_JOB_CONTRACT_VERSION
        )
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
    if path == WALK_FORWARD_HEALTH_PATH:
        return _secure_response(await call_next(request))
    if path == WALK_FORWARD_PATH:
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


@lru_cache
def get_service() -> WalkForwardJobService:
    return WalkForwardJobService()


@app.get(WALK_FORWARD_HEALTH_PATH)
def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "service": "backteststock-walk-forward-v1",
        "api_contract_version": WALK_FORWARD_API_CONTRACT_VERSION,
        "job_contract_version": WALK_FORWARD_JOB_CONTRACT_VERSION,
        "dual_momentum_job_contract_version": DUAL_MOMENTUM_JOB_CONTRACT_VERSION,
        "dual_momentum_allocation_job_contract_version": (
            DUAL_MOMENTUM_ALLOCATION_JOB_CONTRACT_VERSION
        ),
        "dual_momentum_parameter_optimization_job_contract_version": (
            DUAL_MOMENTUM_PARAMETER_OPTIMIZATION_JOB_CONTRACT_VERSION
        ),
        "max_parameter_candidates": MAX_PARAMETER_CANDIDATES,
        "max_inner_folds": MAX_INNER_FOLDS,
        "max_tuning_evaluations_per_job": MAX_TUNING_EVALUATIONS_PER_JOB,
        "deployment_sha": os.getenv("VERCEL_GIT_COMMIT_SHA", ""),
    }


@app.post(WALK_FORWARD_PATH)
async def run_walk_forward(payload: WalkForwardRequest, response: Response) -> dict:
    try:
        spec = _domain_spec(payload)
        result = await asyncio.to_thread(get_service().run, spec)
        response.headers["X-Walk-Forward-Job-Hash"] = result.job_hash
        response.headers["X-Walk-Forward-Job-Contract-Version"] = result.contract_version
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
    selector: (
        WalkForwardSelectorSpec
        | DualMomentumSelectorSpec
        | DualMomentumParameterOptimizationSpec
    )
    if payload.selector.strategy == "exhaustive":
        if payload.selector.universe is None:
            raise ValueError("universe is required for exhaustive selection")
        selector = WalkForwardSelectorSpec(
            universe_id=payload.selector.universe,
            benchmark_symbol=payload.selector.benchmark,
            holding_count=payload.selector.holding_count,
        )
    elif payload.selector.parameter_optimization is not None:
        optimization = payload.selector.parameter_optimization
        selector = DualMomentumParameterOptimizationSpec(
            risky_symbols=tuple(payload.selector.risky_symbols),
            defensive_symbols=tuple(payload.selector.defensive_symbols),
            search_space=ParameterSearchSpace(
                lookback_months=tuple(optimization.search_space.lookback_months),
                top_k=tuple(optimization.search_space.top_k),
                absolute_thresholds=tuple(
                    optimization.search_space.absolute_thresholds
                ),
                allocation_methods=tuple(
                    optimization.search_space.allocation_methods
                ),
            ),
            inner_validation=InnerValidationSpec(
                fold_count=optimization.inner_validation.fold_count,
                evaluation_months=(
                    optimization.inner_validation.evaluation_months
                ),
                step_months=optimization.inner_validation.step_months,
            ),
        )
    else:
        selector = DualMomentumSelectorSpec(
            risky_symbols=tuple(payload.selector.risky_symbols),
            defensive_symbols=tuple(payload.selector.defensive_symbols),
            lookback_months=payload.selector.lookback_months,
            top_k=payload.selector.top_k,
            absolute_threshold=payload.selector.absolute_threshold,
            allocation_method=payload.selector.allocation_method,
        )
    return WalkForwardJobSpec(
        periods=periods,
        selector=selector,
        execution=WalkForwardExecutionSpec(
            initial_amount=payload.execution.initial_amount_twd,
            transition_cost_bps=payload.execution.transition_cost_bps,
        ),
    )