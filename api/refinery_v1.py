"""Vercel ASGI entrypoint for the read-only Portfolio Refinery V1 API."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path
from typing import Any

_CACHE_ROOT = Path("/tmp/.cache")
_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HOME", "/tmp")
os.environ.setdefault("XDG_CACHE_HOME", str(_CACHE_ROOT))

from fastapi import FastAPI, Request, Response  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.request_guard import (  # noqa: E402
    MAX_REQUEST_BYTES,
    authorize_edge_request,
    request_body_failure,
    resolve_local_client_id,
)
from apps.api.app.refinery import (  # noqa: E402
    ANALYZE_REQUESTS_PER_MINUTE,
    GENERAL_REQUESTS_PER_MINUTE,
    MAX_RESPONSE_BYTES,
    REFINERY_API_CONTRACT_VERSION,
    REFINERY_API_SCHEMA_VERSION,
    RefineryRequest,
    RefineryService,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

REFINERY_PREFIX = "/api/v1/refinery/"


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
_analyze_limiter = MinuteRateLimiter(ANALYZE_REQUESTS_PER_MINUTE)

app = FastAPI(
    title="Backteststock Portfolio Refinery V1 API",
    version=REFINERY_API_SCHEMA_VERSION,
    docs_url=None if os.getenv("VERCEL") else "/api/v1/refinery/docs",
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
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-Id"],
    max_age=86_400,
)


@lru_cache
def get_service() -> RefineryService:
    return RefineryService()


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _secure_response(response: Response, request_id: str) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    response.headers["X-Refinery-API-Schema-Version"] = REFINERY_API_SCHEMA_VERSION
    response.headers["X-Request-Id"] = request_id
    return response


def _response(payload: Any, *, status_code: int, request_id: str) -> Response:
    raw = _canonical_bytes(payload)
    if len(raw) > MAX_RESPONSE_BYTES:
        raw = _canonical_bytes(
            {
                "error": {
                    "code": "response_too_large",
                    "message": (
                        "Refinery response exceeds the safe size limit; "
                        "reduce the requested candidate set."
                    ),
                    "retryable": False,
                },
                "contract_version": REFINERY_API_CONTRACT_VERSION,
                "schema_version": REFINERY_API_SCHEMA_VERSION,
            }
        )
        status_code = 422
    return _secure_response(
        Response(content=raw, status_code=status_code, media_type="application/json"),
        request_id,
    )


def _error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    request_id: str,
    retryable: bool = False,
) -> Response:
    return _response(
        {
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
            },
            "contract_version": REFINERY_API_CONTRACT_VERSION,
            "schema_version": REFINERY_API_SCHEMA_VERSION,
        },
        status_code=status_code,
        request_id=request_id,
    )


def _upstream_failure(exc: RuntimeError, *, request_id: str) -> Response:
    logger.warning("Refinery upstream failure request_id=%s: %s", request_id, exc)
    return _error_response(
        502,
        "upstream_failure",
        "Refinery market-data service is temporarily unavailable.",
        request_id=request_id,
        retryable=True,
    )


@app.middleware("http")
async def request_guard(request: Request, call_next: Any) -> Response:
    request_id = request.headers.get("x-request-id", "").strip() or str(uuid.uuid4())
    request.state.request_id = request_id
    path = request.url.path
    if path.startswith(REFINERY_PREFIX):
        fallback = request.client.host if request.client else "unknown"
        identity = authorize_edge_request(
            request.headers,
            fallback_client_id=fallback,
        )
        if not hasattr(identity, "client_id"):
            return _error_response(
                identity.status_code,
                identity.code,
                identity.message,
                request_id=request_id,
                retryable=identity.retryable,
            )
        client_key = (
            identity.client_id
            if identity.authenticated
            else resolve_local_client_id(request.headers, fallback_client_id=fallback)
        )
        request.state.client_identity = client_key
        if not _general_limiter.allow(client_key):
            return _error_response(
                429,
                "rate_limit",
                "Refinery API rate limit exceeded. Try again in one minute.",
                request_id=request_id,
                retryable=True,
            )
        if path.endswith("/analyze") and not _analyze_limiter.allow(client_key):
            return _error_response(
                429,
                "analyze_rate_limit",
                "Refinery analyze rate limit exceeded. Try again in one minute.",
                request_id=request_id,
                retryable=True,
            )

        failure = request_body_failure(
            request.headers,
            maximum_bytes=MAX_REQUEST_BYTES,
            message="Refinery request body is too large.",
        )
        if failure:
            return _error_response(
                failure.status_code,
                failure.code,
                failure.message,
                request_id=request_id,
                retryable=failure.retryable,
            )
        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            failure = request_body_failure(
                request.headers,
                body,
                maximum_bytes=MAX_REQUEST_BYTES,
                message="Refinery request body is too large.",
            )
            if failure:
                return _error_response(
                    failure.status_code,
                    failure.code,
                    failure.message,
                    request_id=request_id,
                    retryable=failure.retryable,
                )

    response = await call_next(request)
    return _secure_response(response, request_id)


@app.post("/api/v1/refinery/preflight")
async def preflight(payload: RefineryRequest, request: Request) -> Response:
    request_id = request.state.request_id
    try:
        result = await asyncio.to_thread(get_service().preflight, payload)
        return _response(result, status_code=200, request_id=request_id)
    except ValueError as exc:
        return _error_response(
            422,
            "invalid_analysis_input",
            str(exc),
            request_id=request_id,
        )
    except RuntimeError as exc:
        return _upstream_failure(exc, request_id=request_id)


@app.post("/api/v1/refinery/analyze")
async def analyze(payload: RefineryRequest, request: Request) -> Response:
    request_id = request.state.request_id
    try:
        result = await asyncio.to_thread(get_service().analyze, payload)
        return _response(result, status_code=200, request_id=request_id)
    except ValueError as exc:
        return _error_response(
            422,
            "invalid_analysis_input",
            str(exc),
            request_id=request_id,
        )
    except RuntimeError as exc:
        return _upstream_failure(exc, request_id=request_id)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> Response:
    issues = [
        {
            "location": [str(item) for item in error.get("loc", ())],
            "message": str(error.get("msg", "invalid value")),
            "type": str(error.get("type", "value_error")),
        }
        for error in exc.errors()
    ]
    return _response(
        {
            "error": {
                "code": "invalid_request",
                "message": "Refinery request validation failed.",
                "retryable": False,
                "issues": issues,
            },
            "contract_version": REFINERY_API_CONTRACT_VERSION,
            "schema_version": REFINERY_API_SCHEMA_VERSION,
        },
        status_code=422,
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> Response:
    logger.exception("Unexpected Refinery API failure", exc_info=exc)
    return _error_response(
        500,
        "unexpected_error",
        "Unexpected Refinery API failure.",
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        retryable=True,
    )
