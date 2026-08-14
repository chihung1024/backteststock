"""Shared backend request perimeter and finite-work budget helpers.

The public Cloudflare Worker is the intended API entry point.  The Worker and
the Vercel origin share a static service secret through
``BACKTESTSTOCK_EDGE_SECRET``.  A request may also carry an opaque
``X-Backteststock-Client-Id`` value; that value is trusted only after the
service secret has been verified.  Until the Worker rollout is complete,
local/test execution remains usable when no secret is configured.  Vercel
runtime requests fail closed when the secret is missing or invalid.

This module deliberately does not implement a distributed rate limiter.  The
existing in-process limiters are still useful as a per-instance overload
brake, while the authenticated client identity is the stable key that an
edge/global quota can use in a later rollout.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import os
from dataclasses import dataclass
from datetime import date
from typing import Mapping


EDGE_SECRET_ENV = "BACKTESTSTOCK_EDGE_SECRET"
EDGE_REQUIRED_ENV = "BACKTESTSTOCK_REQUIRE_EDGE_AUTH"
EDGE_AUTH_HEADER = "x-backteststock-edge-auth"
EDGE_CLIENT_ID_HEADER = "x-backteststock-client-id"
MIN_EDGE_SECRET_LENGTH = 32
MAX_REQUEST_BYTES = 512 * 1024

# These are intentionally shared by the high-cost scan/optimizer boundaries.
# The values are a finite resource contract, not a claim about upstream
# provider capacity.
# Preserve the established ability to submit a manual list larger than one
# Worker chunk.  The ticker-day budget below remains the real cost ceiling.
MAX_SCAN_TICKERS = 500
MAX_SCAN_HISTORY_DAYS = 15 * 366
MAX_SCAN_TICKER_DAYS = 750_000
MAX_SCAN_SECONDS = 180.0
MAX_BACKTEST_HISTORY_DAYS = 15 * 366
MAX_BACKTEST_TICKER_DAYS = 750_000
MAX_BACKTEST_SECONDS = 180.0
MAX_EXHAUSTIVE_HISTORY_DAYS = 15 * 366
MAX_EXHAUSTIVE_TICKER_DAYS = 750_000
MAX_EXHAUSTIVE_SECONDS = 180.0


@dataclass(frozen=True, slots=True)
class GuardFailure:
    """A framework-neutral rejection that callers can serialize locally."""

    status_code: int
    code: str
    message: str
    retryable: bool = False


@dataclass(frozen=True, slots=True)
class EdgeIdentity:
    """Authenticated edge state and the client key for instance-local brakes."""

    authenticated: bool
    client_id: str
    mode: str


def _env_truthy(name: str) -> bool:
    raw = os.getenv(name, "").strip().lower()
    return raw in {"1", "true", "yes", "on", "required"}


def production_runtime() -> bool:
    """Return whether this process is a deployed/protected runtime.

    Vercel sets ``VERCEL`` for deployed functions.  The explicit environment
    aliases make the same fail-closed behavior testable in other hosts.
    """

    runtime = (
        os.getenv("BACKTESTSTOCK_RUNTIME")
        or os.getenv("BACKTESTSTOCK_ENV")
        or os.getenv("ENVIRONMENT")
        or ""
    ).strip().lower()
    return bool(os.getenv("VERCEL")) or runtime in {
        "production",
        "prod",
        "staging",
        "stage",
    }


def edge_auth_required() -> bool:
    """Whether a request must carry the configured edge service secret."""

    configured_mode = os.getenv(EDGE_REQUIRED_ENV)
    if configured_mode is not None and configured_mode.strip():
        # An explicit false value supports the documented two-phase rollout.
        # Once the edge is forwarding credentials, production must set this
        # to true; an absent setting remains fail closed in production.
        return _env_truthy(EDGE_REQUIRED_ENV)
    return production_runtime()


def _header(headers: Mapping[str, str], name: str) -> str:
    # Starlette/Flask header containers are case-insensitive; plain mappings
    # used by unit tests are not, so support both forms without normalizing a
    # potentially attacker-controlled full mapping.
    value = headers.get(name)
    if value is None:
        value = headers.get(name.lower())
    if value is None:
        value = headers.get(name.title())
    return str(value or "").strip()


def _safe_client_id(value: str) -> str | None:
    value = value.strip()
    if not value or len(value) > 128 or any(ord(char) < 0x20 for char in value):
        return None
    return value


def authorize_edge_request(
    headers: Mapping[str, str],
    *,
    fallback_client_id: str = "unknown",
) -> EdgeIdentity | GuardFailure:
    """Authenticate the Worker and resolve a non-spoofable client key.

    The header is intentionally a bearer-style service secret for this first
    perimeter batch.  The Worker must strip any client-supplied copies and
    set the header from its private secret binding before forwarding.  A
    future HMAC-per-request scheme can replace this comparison without
    changing endpoint call sites.
    """

    configured = os.getenv(EDGE_SECRET_ENV, "").strip()
    provided = _header(headers, EDGE_AUTH_HEADER)
    if len(configured) < MIN_EDGE_SECRET_LENGTH:
        if edge_auth_required():
            return GuardFailure(
                503,
                "edge_auth_not_configured",
                "Backend edge authentication is not securely configured.",
                retryable=False,
            )
        client_id = _safe_client_id(fallback_client_id) or "unknown"
        return EdgeIdentity(False, client_id, "local-unconfigured")

    if not provided or not hmac.compare_digest(provided, configured):
        return GuardFailure(
            403,
            "edge_auth_required",
            "A trusted edge service identity is required.",
            retryable=False,
        )

    supplied_client = _safe_client_id(_header(headers, EDGE_CLIENT_ID_HEADER))
    client_id = supplied_client or _safe_client_id(fallback_client_id) or "edge"
    return EdgeIdentity(True, client_id, "edge-authenticated")


def resolve_local_client_id(
    headers: Mapping[str, str],
    *,
    fallback_client_id: str = "unknown",
) -> str:
    """Resolve a best-effort local key without treating XFF as production truth."""

    if not production_runtime():
        forwarded = _header(headers, "x-forwarded-for")
        if forwarded:
            candidate = forwarded.split(",", 1)[0].strip()
            if _safe_client_id(candidate):
                return candidate
    return _safe_client_id(fallback_client_id) or "unknown"


def request_body_failure(
    headers: Mapping[str, str],
    body: bytes | bytearray | memoryview | None = None,
    *,
    maximum_bytes: int = MAX_REQUEST_BYTES,
    message: str = "Request body is too large.",
) -> GuardFailure | None:
    """Validate declared and already-read body sizes.

    Flask/ASGI adapters call this before JSON validation.  Frameworks still
    own the bounded read itself; this pure function keeps the contract and
    error shape identical across handlers.
    """

    if maximum_bytes <= 0:
        raise ValueError("maximum_bytes must be positive")
    declared = _header(headers, "content-length")
    if declared:
        try:
            length = int(declared)
        except ValueError:
            return GuardFailure(400, "invalid_content_length", "Content-Length must be an integer.")
        if length < 0:
            return GuardFailure(400, "invalid_content_length", "Content-Length cannot be negative.")
        if length > maximum_bytes:
            return GuardFailure(413, "request_too_large", message)
    if body is not None and len(body) > maximum_bytes:
        return GuardFailure(413, "request_too_large", message)
    return None


def validate_work_budget(
    start: date,
    end_exclusive: date,
    unit_count: int,
    *,
    max_history_days: int,
    max_unit_days: int,
    label: str,
) -> GuardFailure | None:
    """Reject unbounded historical work before any market-data call."""

    try:
        history_days = (end_exclusive - start).days
    except TypeError:
        return GuardFailure(400, "invalid_period", f"{label} period is invalid.")
    if history_days <= 0:
        return GuardFailure(400, "invalid_period", f"{label} period must be positive.")
    if history_days > max_history_days:
        return GuardFailure(
            400,
            "history_budget_exceeded",
            f"{label} history is limited to {max_history_days:,} calendar days.",
        )
    if isinstance(unit_count, bool) or not isinstance(unit_count, int) or unit_count <= 0:
        return GuardFailure(400, "invalid_work_units", f"{label} ticker count is invalid.")
    work_units = history_days * unit_count
    if work_units > max_unit_days:
        return GuardFailure(
            400,
            "work_budget_exceeded",
            f"{label} request exceeds the bounded work budget ({max_unit_days:,} ticker-days).",
        )
    return None


def elapsed_budget_failure(
    started_at: float,
    now: float,
    *,
    maximum_seconds: float,
    label: str,
) -> GuardFailure | None:
    """Return a retryable failure when a finite soft deadline is exceeded."""

    elapsed = now - started_at
    if not math.isfinite(elapsed) or elapsed > maximum_seconds:
        return GuardFailure(
            504,
            "time_budget_exceeded",
            f"{label} exceeded its {maximum_seconds:.0f}-second time budget.",
            retryable=True,
        )
    return None


def body_limit_message(service: str) -> str:
    return f"{service} request body is too large."


def constant_time_digest(value: str) -> str:
    """Stable non-secret identity helper for logs/tests (never the bearer)."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
