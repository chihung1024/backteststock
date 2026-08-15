"""HTTP placement for the existing JavaScript Exhaustive selection authority.

The numerical implementation remains JavaScript. Batch 4A-5 places that
implementation in a bounded Vercel Node function and lets the Python
orchestrator call it over a deployment-bound HTTP contract instead of assuming
that a ``node`` executable exists inside the Python serverless runtime.
"""

from __future__ import annotations

import gzip
import json
import os
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlparse

import requests

EXHAUSTIVE_AUTHORITY_HTTP_CONTRACT_VERSION = (
    "exhaustive-authority-http-2026-08-15.1"
)
EXHAUSTIVE_AUTHORITY_PATH = "/api/internal/research/exhaustive-selection"
MAX_AUTHORITY_WIRE_BYTES = 3 * 1024 * 1024
MAX_AUTHORITY_JSON_BYTES = 16 * 1024 * 1024
GZIP_THRESHOLD_BYTES = 512 * 1024


@dataclass(slots=True)
class HttpExhaustiveAuthorityRunner:
    """Invoke the repository's Node Exhaustive authority from Python runtime."""

    origin: str = field(default_factory=lambda: _configured_origin())
    timeout_seconds: float = 240.0
    deployment_sha: str = field(
        default_factory=lambda: os.getenv("VERCEL_GIT_COMMIT_SHA", "").strip()
    )
    internal_secret: str = field(
        default_factory=lambda: (
            os.getenv("WALK_FORWARD_INTERNAL_SECRET", "").strip()
            or os.getenv("VERCEL_AUTOMATION_BYPASS_SECRET", "").strip()
        ),
        repr=False,
    )
    session: requests.Session = field(default_factory=requests.Session, repr=False)

    def __post_init__(self) -> None:
        self.origin = _validated_origin(self.origin)
        timeout = float(self.timeout_seconds)
        if not 0.0 < timeout <= 300.0:
            raise ValueError("Exhaustive authority timeout_seconds must be in (0, 300]")
        self.timeout_seconds = timeout
        if self.deployment_sha and not _looks_like_sha(self.deployment_sha):
            raise ValueError("VERCEL_GIT_COMMIT_SHA must be a 40-character hex commit SHA")

    def identity(self) -> Mapping[str, str]:
        payload = self._post({"type": "version"})
        return {
            "authorityVersion": _required_text(
                payload.get("authorityVersion"), "authorityVersion"
            ),
            "bridgeVersion": _required_text(
                payload.get("bridgeVersion"), "bridgeVersion"
            ),
        }

    def select_best(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._post(dict(payload))

    def _post(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        body, content_encoding = _encode_payload(payload)
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "cache-control": "no-store",
            "user-agent": "backteststock-walk-forward/1",
        }
        if content_encoding:
            headers["content-encoding"] = content_encoding
        if self.deployment_sha:
            headers["x-backteststock-internal-deployment"] = self.deployment_sha
        if self.internal_secret:
            headers["x-backteststock-internal-secret"] = self.internal_secret
            if self.internal_secret == os.getenv(
                "VERCEL_AUTOMATION_BYPASS_SECRET", ""
            ).strip():
                headers["x-vercel-protection-bypass"] = self.internal_secret
        try:
            response = self.session.post(
                f"{self.origin}{EXHAUSTIVE_AUTHORITY_PATH}",
                data=body,
                timeout=self.timeout_seconds,
                headers=headers,
            )
        except requests.RequestException as exc:
            raise RuntimeError("Exhaustive authority service is temporarily unavailable") from exc
        if response.status_code != 200:
            detail = _response_detail(response)
            raise RuntimeError(
                detail or f"Exhaustive authority service returned HTTP {response.status_code}"
            )
        if self.deployment_sha:
            returned_sha = response.headers.get("x-backteststock-deployment-sha", "").strip()
            if returned_sha != self.deployment_sha:
                raise RuntimeError("Exhaustive authority response came from a different deployment")
        try:
            decoded = response.json()
        except ValueError as exc:
            raise RuntimeError("Exhaustive authority service returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Exhaustive authority service must return a JSON object")
        return decoded


def _encode_payload(payload: Mapping[str, Any]) -> tuple[bytes, str | None]:
    try:
        raw = json.dumps(
            dict(payload),
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Exhaustive authority payload must be finite JSON") from exc
    if len(raw) > MAX_AUTHORITY_JSON_BYTES:
        raise RuntimeError(
            "Exhaustive authority JSON exceeds the 16 MiB decoded safety ceiling; "
            "shorten the Training window or reduce PIT candidates"
        )
    if len(raw) < GZIP_THRESHOLD_BYTES:
        if len(raw) > MAX_AUTHORITY_WIRE_BYTES:
            raise RuntimeError("Exhaustive authority request exceeds the wire safety ceiling")
        return raw, None
    compressed = gzip.compress(raw, compresslevel=6, mtime=0)
    if len(compressed) > MAX_AUTHORITY_WIRE_BYTES:
        raise RuntimeError(
            "Exhaustive authority compressed request exceeds the 3 MiB wire safety ceiling; "
            "shorten the Training window or reduce PIT candidates"
        )
    return compressed, "gzip"


def _configured_origin() -> str:
    explicit = os.getenv("EXHAUSTIVE_AUTHORITY_ORIGIN", "").strip()
    if explicit:
        return explicit
    if os.getenv("VERCEL_ENV", "").strip() == "production":
        production_url = os.getenv("VERCEL_PROJECT_PRODUCTION_URL", "").strip()
        if production_url:
            return f"https://{production_url}"
    vercel_url = os.getenv("VERCEL_URL", "").strip()
    if vercel_url:
        return f"https://{vercel_url}"
    raise RuntimeError(
        "Exhaustive authority origin is unavailable; set EXHAUSTIVE_AUTHORITY_ORIGIN "
        "or run inside Vercel with VERCEL_URL/VERCEL_PROJECT_PRODUCTION_URL"
    )


def _validated_origin(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Exhaustive authority origin must be an absolute HTTP(S) origin")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("Exhaustive authority origin must not contain path/query/fragment")
    return f"{parsed.scheme}://{parsed.netloc}"


def _looks_like_sha(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdefABCDEF" for character in value)


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Exhaustive authority {label} is missing")
    return value.strip()


def _response_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    for key in ("error", "detail", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:1000]
    return ""
