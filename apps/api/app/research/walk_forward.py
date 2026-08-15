"""Temporal causality contracts for deterministic walk-forward research.

Batch 4A-1 is deliberately framework-neutral. It defines the time firewall and
immutable decision identity without fetching market data, resolving universes,
or running a selector. Later orchestration layers must construct these objects
before any out-of-sample evaluation is allowed to run.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Iterable, Mapping

WALK_FORWARD_TEMPORAL_CONTRACT_VERSION = "walk-forward-temporal-2026-08-15.1"
WALK_FORWARD_DECISION_HASH_ALGORITHM = "sha256-canonical-json-v1"
DECISION_TIMING_AFTER_CLOSE = "after_close"

_JSON_SCALAR = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class _FrozenMapping:
    items: tuple[tuple[str, Any], ...]


@dataclass(frozen=True, slots=True)
class _FrozenSequence:
    items: tuple[Any, ...]


_FROZEN_VALUE = _JSON_SCALAR | _FrozenMapping | _FrozenSequence


@dataclass(frozen=True, slots=True)
class WalkForwardPeriod:
    """One training/decision/evaluation period with a strict future-data firewall."""

    period_id: str
    training_start: date
    training_end: date
    decision_date: date
    evaluation_start: date
    evaluation_end: date
    decision_timing: str = DECISION_TIMING_AFTER_CLOSE

    def __post_init__(self) -> None:
        period_id = self.period_id.strip()
        if not period_id:
            raise ValueError("walk-forward period_id is required")
        object.__setattr__(self, "period_id", period_id)
        if self.training_start > self.training_end:
            raise ValueError("training_start must not be after training_end")
        if self.training_end > self.decision_date:
            raise ValueError("training data must end on or before decision_date")
        if self.evaluation_start <= self.decision_date:
            raise ValueError("evaluation_start must be strictly after decision_date")
        if self.evaluation_start > self.evaluation_end:
            raise ValueError("evaluation_start must not be after evaluation_end")
        if self.decision_timing != DECISION_TIMING_AFTER_CLOSE:
            raise ValueError("walk-forward v1 supports only after_close decisions")


@dataclass(frozen=True, slots=True)
class ResolvedPITUniverse:
    """One causally available, integrity-checked PIT membership observation."""

    universe_id: str
    requested_as_of: date
    source_as_of: date
    evidence_available_as_of: date
    fetched_at: str
    version: str
    checksum: str
    members: tuple[str, ...]
    membership_policy: str
    membership_authoritative: bool
    source_label: str
    source_url: str
    source_is_proxy: bool

    def __post_init__(self) -> None:
        universe_id = self.universe_id.strip().lower()
        version = self.version.strip()
        checksum = self.checksum.strip().lower()
        policy = self.membership_policy.strip()
        source_label = self.source_label.strip()
        source_url = self.source_url.strip()
        fetched_at = _canonical_utc_timestamp(self.fetched_at)
        members = tuple(str(member) for member in self.members)
        if (
            not universe_id
            or not version
            or not checksum
            or not policy
            or not source_label
            or not source_url
        ):
            raise ValueError("PIT universe provenance fields must be non-empty")
        if not members or any(not member for member in members):
            raise ValueError("PIT universe must contain at least one non-empty member")
        if any(member != member.strip().upper() for member in members):
            raise ValueError("PIT universe members must already be canonical symbols")
        if len(set(members)) != len(members):
            raise ValueError("PIT universe members must be unique")
        if self.source_as_of > self.requested_as_of:
            raise ValueError("PIT source_as_of must not be after requested_as_of")
        if self.evidence_available_as_of < self.source_as_of:
            raise ValueError("PIT evidence cannot predate its source observation")
        fetched_date = datetime.fromisoformat(
            fetched_at.replace("Z", "+00:00")
        ).date()
        if fetched_date != self.evidence_available_as_of:
            raise ValueError("PIT fetched_at UTC date must equal evidence_available_as_of")
        if self.evidence_available_as_of > self.requested_as_of:
            raise ValueError(
                "PIT evidence must have been available on or before requested_as_of"
            )
        if self.membership_authoritative and self.source_is_proxy:
            raise ValueError("proxy membership cannot be marked authoritative")
        object.__setattr__(self, "universe_id", universe_id)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "checksum", checksum)
        object.__setattr__(self, "membership_policy", policy)
        object.__setattr__(self, "source_label", source_label)
        object.__setattr__(self, "source_url", source_url)
        object.__setattr__(self, "fetched_at", fetched_at)
        object.__setattr__(self, "members", members)


@dataclass(frozen=True, slots=True)
class DecisionSnapshot:
    """Immutable selection decision created before any OOS data is consumed."""

    period: WalkForwardPeriod
    pit_universe: ResolvedPITUniverse
    training_dataset_hash: str
    training_effective_start: date
    training_effective_end: date
    selector_contract_version: str
    selector_rule: str
    selector_parameters: _FrozenMapping
    eligible_candidates: tuple[str, ...]
    selected_constituents: tuple[str, ...]
    weights: tuple[float, ...]
    decision_hash: str
    contract_version: str = WALK_FORWARD_TEMPORAL_CONTRACT_VERSION

    def export_payload(self) -> dict[str, Any]:
        payload = _decision_payload(self, include_hash=False)
        current = _canonical_hash(payload)
        if current != self.decision_hash:
            raise ValueError("decision snapshot identity mismatch")
        return {**payload, "decisionHash": self.decision_hash}


def create_decision_snapshot(
    *,
    period: WalkForwardPeriod,
    pit_universe: ResolvedPITUniverse,
    training_dataset_hash: str,
    training_effective_start: date,
    training_effective_end: date,
    selector_contract_version: str,
    selector_rule: str,
    selector_parameters: Mapping[str, Any] | None,
    eligible_candidates: Iterable[str],
    selected_constituents: Iterable[str],
    weights: Iterable[float],
) -> DecisionSnapshot:
    """Validate and freeze one decision before OOS evaluation is possible."""

    if pit_universe.requested_as_of != period.decision_date:
        raise ValueError("PIT requested_as_of must equal the walk-forward decision_date")
    if training_effective_start < period.training_start:
        raise ValueError("training effective data starts before the requested training window")
    if training_effective_end > period.training_end:
        raise ValueError("training effective data extends beyond training_end")
    if training_effective_end > period.decision_date:
        raise ValueError("training effective data extends beyond decision_date")
    if training_effective_start > training_effective_end:
        raise ValueError("training effective start must not be after effective end")

    dataset_hash = training_dataset_hash.strip().lower()
    selector_version = selector_contract_version.strip()
    selector_rule_value = selector_rule.strip()
    if not dataset_hash or not selector_version or not selector_rule_value:
        raise ValueError("dataset hash and selector identity fields must be non-empty")

    eligible = _normalized_symbols(eligible_candidates, label="eligible candidates")
    selected = _normalized_symbols(selected_constituents, label="selected constituents")
    if not selected:
        raise ValueError("at least one selected constituent is required")
    if not set(selected).issubset(set(eligible)):
        raise ValueError("selected constituents must be a subset of eligible candidates")
    if not set(eligible).issubset(set(pit_universe.members)):
        raise ValueError("eligible candidates must be a subset of the exact PIT membership")

    normalized_weights = tuple(float(value) for value in weights)
    if len(normalized_weights) != len(selected):
        raise ValueError("weight count must equal selected constituent count")
    if (
        not normalized_weights
        or not all(math.isfinite(value) and value > 0.0 for value in normalized_weights)
        or not math.isclose(sum(normalized_weights), 1.0, abs_tol=1e-10)
    ):
        raise ValueError("weights must be finite positive fractions summing to one")

    frozen_parameters = _freeze_mapping(selector_parameters or {})
    provisional = DecisionSnapshot(
        period=period,
        pit_universe=pit_universe,
        training_dataset_hash=dataset_hash,
        training_effective_start=training_effective_start,
        training_effective_end=training_effective_end,
        selector_contract_version=selector_version,
        selector_rule=selector_rule_value,
        selector_parameters=frozen_parameters,
        eligible_candidates=eligible,
        selected_constituents=selected,
        weights=normalized_weights,
        decision_hash="",
    )
    decision_hash = _canonical_hash(_decision_payload(provisional, include_hash=False))
    return DecisionSnapshot(
        period=provisional.period,
        pit_universe=provisional.pit_universe,
        training_dataset_hash=provisional.training_dataset_hash,
        training_effective_start=provisional.training_effective_start,
        training_effective_end=provisional.training_effective_end,
        selector_contract_version=provisional.selector_contract_version,
        selector_rule=provisional.selector_rule,
        selector_parameters=provisional.selector_parameters,
        eligible_candidates=provisional.eligible_candidates,
        selected_constituents=provisional.selected_constituents,
        weights=provisional.weights,
        decision_hash=decision_hash,
    )


def validate_period_schedule(
    periods: Iterable[WalkForwardPeriod],
) -> tuple[WalkForwardPeriod, ...]:
    """Return an ordered schedule only when OOS windows never overlap or rewind."""

    ordered = tuple(periods)
    if not ordered:
        raise ValueError("walk-forward schedule requires at least one period")
    if len({period.period_id for period in ordered}) != len(ordered):
        raise ValueError("walk-forward period_id values must be unique")
    for previous, current in zip(ordered, ordered[1:]):
        if current.decision_date <= previous.decision_date:
            raise ValueError("walk-forward decision dates must be strictly increasing")
        if current.evaluation_start <= previous.evaluation_end:
            raise ValueError("walk-forward evaluation windows must not overlap")
        if current.decision_date < previous.evaluation_end:
            raise ValueError(
                "next decision date must not precede the prior evaluation end"
            )
    return ordered


def _canonical_utc_timestamp(value: str) -> str:
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("PIT fetched_at must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("PIT fetched_at must include a timezone")
    canonical = (
        parsed.astimezone(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    if raw != canonical:
        raise ValueError("PIT fetched_at must use canonical UTC seconds with Z")
    return raw


def _normalized_symbols(values: Iterable[str], *, label: str) -> tuple[str, ...]:
    symbols = tuple(str(value) for value in values)
    if any(not symbol for symbol in symbols):
        raise ValueError(f"{label} contain an empty symbol")
    if any(symbol != symbol.strip().upper() for symbol in symbols):
        raise ValueError(f"{label} must already contain canonical symbols")
    if len(set(symbols)) != len(symbols):
        raise ValueError(f"{label} must be unique")
    return symbols


def _freeze_mapping(values: Mapping[str, Any]) -> _FrozenMapping:
    if any(not isinstance(key, str) for key in values):
        raise TypeError("selector parameter mapping keys must be strings")
    return _FrozenMapping(
        items=tuple(
            (key, _freeze_value(value))
            for key, value in sorted(values.items(), key=lambda pair: pair[0])
        )
    )


def _freeze_value(value: Any) -> _FROZEN_VALUE:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("selector parameters must not contain non-finite floats")
        return 0.0 if value == 0.0 else value
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return _FrozenSequence(items=tuple(_freeze_value(item) for item in value))
    raise TypeError(f"unsupported selector parameter value: {type(value).__name__}")


def _thaw_value(value: _FROZEN_VALUE) -> Any:
    if isinstance(value, _FrozenMapping):
        return {key: _thaw_value(item) for key, item in value.items}
    if isinstance(value, _FrozenSequence):
        return [_thaw_value(item) for item in value.items]
    return value


def _decision_payload(snapshot: DecisionSnapshot, *, include_hash: bool) -> dict[str, Any]:
    period = snapshot.period
    universe = snapshot.pit_universe
    payload: dict[str, Any] = {
        "contractVersion": snapshot.contract_version,
        "hashAlgorithm": WALK_FORWARD_DECISION_HASH_ALGORITHM,
        "period": {
            "periodId": period.period_id,
            "trainingStart": period.training_start.isoformat(),
            "trainingEnd": period.training_end.isoformat(),
            "decisionDate": period.decision_date.isoformat(),
            "decisionTiming": period.decision_timing,
            "evaluationStart": period.evaluation_start.isoformat(),
            "evaluationEnd": period.evaluation_end.isoformat(),
        },
        "pitUniverse": {
            "universeId": universe.universe_id,
            "requestedAsOf": universe.requested_as_of.isoformat(),
            "sourceAsOf": universe.source_as_of.isoformat(),
            "evidenceAvailableAsOf": universe.evidence_available_as_of.isoformat(),
            "fetchedAt": universe.fetched_at,
            "version": universe.version,
            "checksum": universe.checksum,
            "members": list(universe.members),
            "membershipPolicy": universe.membership_policy,
            "membershipAuthoritative": universe.membership_authoritative,
            "sourceLabel": universe.source_label,
            "sourceUrl": universe.source_url,
            "sourceIsProxy": universe.source_is_proxy,
        },
        "trainingDataset": {
            "datasetHash": snapshot.training_dataset_hash,
            "effectiveStart": snapshot.training_effective_start.isoformat(),
            "effectiveEnd": snapshot.training_effective_end.isoformat(),
        },
        "selector": {
            "contractVersion": snapshot.selector_contract_version,
            "rule": snapshot.selector_rule,
            "parameters": _thaw_value(snapshot.selector_parameters),
        },
        "eligibleCandidates": list(snapshot.eligible_candidates),
        "selectedConstituents": list(snapshot.selected_constituents),
        "weights": list(snapshot.weights),
    }
    if include_hash:
        payload["decisionHash"] = snapshot.decision_hash
    return payload


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
