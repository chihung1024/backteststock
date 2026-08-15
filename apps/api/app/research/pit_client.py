"""Server-side client for the existing Worker/D1 point-in-time Universe authority.

Batch 4A-5 deliberately consumes the edge resolver instead of duplicating D1
archive queries or historical-membership policy in Python.  The client accepts
only causally closed PIT responses and preserves their exact provenance in the
existing ``ResolvedPITUniverse`` contract.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping, Protocol
from urllib.parse import quote, urlparse

import requests

from apps.api.app.research.walk_forward import ResolvedPITUniverse

PIT_UNIVERSE_CLIENT_CONTRACT_VERSION = "pit-universe-client-2026-08-15.1"
DEFAULT_PIT_RESOLVER_ORIGIN = "https://backteststock.chired.workers.dev"
PIT_SELECTION_MODE = "point_in_time_last_causally_available"


class PITUniverseResolver(Protocol):
    def resolve(self, universe_id: str, requested_as_of: date) -> ResolvedPITUniverse:
        ...


class PITResolverError(RuntimeError):
    """An edge PIT resolver failure with the upstream HTTP status preserved."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(slots=True)
class PITUniverseClient:
    """Fetch and validate one historical Universe observation from the Worker."""

    origin: str = field(
        default_factory=lambda: os.getenv(
            "PIT_RESOLVER_ORIGIN", DEFAULT_PIT_RESOLVER_ORIGIN
        )
    )
    timeout_seconds: float = 20.0
    session: requests.Session = field(default_factory=requests.Session, repr=False)

    def __post_init__(self) -> None:
        self.origin = _validated_origin(self.origin)
        timeout = float(self.timeout_seconds)
        if not 0.0 < timeout <= 120.0:
            raise ValueError("PIT resolver timeout_seconds must be in (0, 120]")
        self.timeout_seconds = timeout

    def resolve(self, universe_id: str, requested_as_of: date) -> ResolvedPITUniverse:
        universe = str(universe_id or "").strip().lower()
        if not universe or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in universe):
            raise ValueError("universe_id must contain only lowercase letters, digits or hyphens")
        if not isinstance(requested_as_of, date):
            raise TypeError("requested_as_of must be a date")

        url = (
            f"{self.origin}/api/v2/universes/{quote(universe, safe='')}"
            f"?asOf={requested_as_of.isoformat()}"
        )
        try:
            response = self.session.get(
                url,
                timeout=self.timeout_seconds,
                headers={
                    "accept": "application/json",
                    "cache-control": "no-store",
                    "user-agent": "backteststock-walk-forward/1",
                },
            )
        except requests.RequestException as exc:
            raise PITResolverError("PIT Universe resolver is temporarily unavailable") from exc

        if response.status_code != 200:
            detail = _error_detail(response)
            raise PITResolverError(
                detail or f"PIT Universe resolver returned HTTP {response.status_code}",
                status_code=int(response.status_code),
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise PITResolverError("PIT Universe resolver returned invalid JSON", status_code=502) from exc
        return parse_pit_universe_payload(
            payload,
            expected_universe_id=universe,
            expected_requested_as_of=requested_as_of,
        )


def parse_pit_universe_payload(
    payload: Mapping[str, Any],
    *,
    expected_universe_id: str,
    expected_requested_as_of: date,
) -> ResolvedPITUniverse:
    """Fail closed unless the Worker response proves causal PIT membership."""

    if not isinstance(payload, Mapping):
        raise PITResolverError("PIT Universe payload must be an object", status_code=502)
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise PITResolverError("PIT Universe payload is missing data", status_code=502)

    universe_id = _required_text(data.get("id"), "PIT universe id").lower()
    if universe_id != expected_universe_id:
        raise PITResolverError("PIT Universe response is bound to a different universe", status_code=502)
    requested_as_of = _iso_date(data.get("requestedAsOf"), "requestedAsOf")
    if requested_as_of != expected_requested_as_of:
        raise PITResolverError("PIT Universe response is bound to a different research date", status_code=502)
    if data.get("selectionMode") != PIT_SELECTION_MODE:
        raise PITResolverError("PIT Universe response uses an unexpected selection mode", status_code=502)
    if data.get("pointInTime") is not True or data.get("membershipCausal") is not True:
        raise PITResolverError("PIT Universe response is not causally point-in-time", status_code=502)

    authoritative = data.get("membershipAuthoritative")
    if not isinstance(authoritative, bool):
        raise PITResolverError("PIT membershipAuthoritative must be boolean", status_code=502)
    source = data.get("source")
    if not isinstance(source, Mapping):
        raise PITResolverError("PIT Universe source provenance is missing", status_code=502)
    source_is_proxy = source.get("isProxy")
    if not isinstance(source_is_proxy, bool):
        raise PITResolverError("PIT source isProxy must be boolean", status_code=502)

    raw_members = data.get("members")
    if not isinstance(raw_members, list) or not raw_members:
        raise PITResolverError("PIT Universe members must be a non-empty array", status_code=502)
    members: list[str] = []
    for item in raw_members:
        if not isinstance(item, Mapping):
            raise PITResolverError("PIT Universe member must be an object", status_code=502)
        ticker = _required_text(item.get("ticker"), "PIT member ticker")
        if ticker != ticker.strip().upper():
            raise PITResolverError("PIT member tickers must already be canonical", status_code=502)
        members.append(ticker)

    try:
        return ResolvedPITUniverse(
            universe_id=universe_id,
            requested_as_of=requested_as_of,
            source_as_of=_iso_date(data.get("sourceAsOf"), "sourceAsOf"),
            evidence_available_as_of=_iso_date(
                data.get("evidenceAvailableAsOf"), "evidenceAvailableAsOf"
            ),
            fetched_at=_required_text(data.get("fetchedAt"), "fetchedAt"),
            version=_required_text(data.get("version"), "version"),
            checksum=_required_text(data.get("checksum"), "checksum"),
            members=tuple(members),
            membership_policy=_required_text(
                data.get("membershipPolicy"), "membershipPolicy"
            ),
            membership_authoritative=authoritative,
            source_label=_required_text(source.get("label"), "source.label"),
            source_url=_required_text(source.get("url"), "source.url"),
            source_is_proxy=source_is_proxy,
        )
    except (TypeError, ValueError) as exc:
        raise PITResolverError(f"invalid PIT Universe provenance: {exc}", status_code=502) from exc


def _validated_origin(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("PIT_RESOLVER_ORIGIN must be an absolute HTTP(S) origin")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("PIT_RESOLVER_ORIGIN must not contain a path, query or fragment")
    return f"{parsed.scheme}://{parsed.netloc}"


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PITResolverError(f"{label} must be a non-empty string", status_code=502)
    return value.strip()


def _iso_date(value: Any, label: str) -> date:
    raw = _required_text(value, label)
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise PITResolverError(f"{label} must be an ISO calendar date", status_code=502) from exc
    if parsed.isoformat() != raw:
        raise PITResolverError(f"{label} must be canonical YYYY-MM-DD", status_code=502)
    return parsed


def _error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, Mapping):
        return ""
    for key in ("error", "detail", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:1000]
    return ""
