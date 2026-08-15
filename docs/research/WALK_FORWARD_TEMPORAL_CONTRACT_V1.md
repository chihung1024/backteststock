# Walk-Forward Temporal Contract V1

Status: **Batch 4A-1 implementation contract; additive and not yet exposed as a production API/UI.**

## Purpose

This contract establishes the temporal causality firewall for BacktestStock walk-forward research before any selector, optimizer, Portfolio ledger integration, or public route is added.

The primary invariant is:

```text
Training data <= Decision point < Evaluation / OOS data
```

A selection decision must be completely determined and frozen before evaluation data can be consumed. OOS data may evaluate a decision but may never mutate or retroactively improve that same decision identity.

## Authority boundaries

Batch 4A-1 does not create a second market-data, FX, Universe, Scanner, Exhaustive, Portfolio, or metrics authority.

- Historical membership authority remains the PIT Universe archive and its causality/integrity rules.
- Audited research-market-data authority remains `ResearchDatasetV1` / `TWDHistoryService`.
- Existing deterministic quant and Portfolio engines remain unchanged.
- This layer owns only walk-forward period semantics and immutable decision identity.

## Contract identity

```text
WALK_FORWARD_TEMPORAL_CONTRACT_VERSION = walk-forward-temporal-2026-08-15.1
WALK_FORWARD_DECISION_HASH_ALGORITHM    = sha256-canonical-json-v1
Decision timing                         = after_close
```

## WalkForwardPeriod

One period records:

- `training_start` / `training_end`;
- `decision_date`;
- `evaluation_start` / `evaluation_end`;
- `decision_timing`.

V1 requires:

1. `training_start <= training_end`;
2. `training_end <= decision_date`;
3. `evaluation_start > decision_date`;
4. `evaluation_start <= evaluation_end`;
5. decision timing is `after_close`.

The strict `evaluation_start > decision_date` rule prevents a decision made using a decision-date close from being represented as though it could execute on that same already-observed close.

## PIT Universe causality

A `ResolvedPITUniverse` may be attached to a decision only when:

- `source_as_of <= evidence_available_as_of <= requested_as_of`;
- exact canonical UTC `fetched_at` is preserved, and its UTC date equals `evidence_available_as_of`;
- source label and source URL are preserved with the snapshot provenance;
- exact members are non-empty and unique;
- exact members are already canonical symbols and are not silently rewritten after the upstream checksum/provenance boundary;
- proxy membership is never labelled authoritative.

The object preserves exact PIT members and provenance. It does not reconstruct missing history and does not permit fallback to current membership.

For a `DecisionSnapshot`, `pit_universe.requested_as_of` must equal the period `decision_date` exactly.

## Training-data isolation

The immutable decision records both the requested training window and the `ResearchDataset` effective window/hash supplied by later orchestration.

The effective training sample must satisfy:

- `effective_start >= training_start`;
- `effective_end <= training_end`;
- `effective_end <= decision_date`.

This is an additional consumer-side guard. `ResearchDatasetV1` separately rejects source observations outside its own requested interval.

Batch 4A-1 intentionally has no field for an Evaluation/OOS dataset in `create_decision_snapshot()`. Future selection orchestration must preserve this separation instead of constructing one broad future-inclusive object and trusting downstream code to ignore it.

## Immutable DecisionSnapshot

A decision freezes:

- period identity and temporal boundaries;
- exact PIT Universe provenance (`source_as_of`, `evidence_available_as_of`, `fetched_at`, source label/URL, proxy/authority state, checksum/policy) and membership;
- training dataset hash/effective interval;
- selector contract/rule/parameters;
- eligible candidates;
- selected constituents;
- weights.

Selected constituents must be a subset of eligible candidates, and eligible candidates must be a subset of exact PIT membership. Candidate symbols must already be canonical; this layer validates but does not normalize provenance-sensitive membership.

Weights must be finite, positive, count-match the selected constituents, and sum to one.

Selector parameters are recursively converted into explicitly typed immutable mapping/sequence containers. Mapping keys must be strings, unordered containers and non-finite floats fail closed, and negative zero is canonicalized to `0.0`. Mutating the caller's original dictionaries/lists after the decision is created therefore cannot mutate the decision or its hash.

## Decision hash

`decision_hash` is SHA-256 over canonical JSON containing all material decision inputs above, excluding the hash field itself.

The hash answers:

> Did this exact PIT evidence + training dataset + selector configuration produce this exact frozen portfolio decision under the same temporal contract?

Changing a material training dataset identity, PIT membership/provenance, selector parameter, selected constituent, or weight changes the decision hash.

`export_payload()` recomputes the identity and fails closed if an inconsistent snapshot is somehow constructed.

## Schedule invariants

`validate_period_schedule()` requires:

- at least one period;
- unique period IDs;
- strictly increasing decision dates;
- non-overlapping Evaluation/OOS windows;
- a later decision cannot occur before the previous Evaluation/OOS window has ended.

Later Batch 4A work will add continuous OOS ledger execution across these periods. This contract deliberately does not imply that independent period returns may be averaged or stitched by resetting NAV.

## Explicit non-goals

Batch 4A-1 does not implement:

- selector/ranking policy;
- Exhaustive optimization parity;
- Refinery-driven selection;
- continuous OOS Portfolio ledger;
- turnover or transaction-cost calculation between decisions;
- PIT fundamentals;
- public Walk-Forward API/UI;
- ResearchRun persistence.

Those remain later Batch 4A / 4B work and must consume this temporal contract rather than bypass it.

## Required regression properties

Tests must prove at minimum:

- training cannot extend past decision;
- OOS cannot begin on/before decision;
- PIT source/evidence cannot come from after decision or form impossible source/evidence ordering;
- exact `fetched_at`/source URL provenance is retained, and fetched timestamp/date evidence cannot drift;
- PIT requested date must match the exact decision date;
- PIT/candidate symbols are not silently rewritten across the provenance boundary;
- selected/eligible membership fails closed;
- weights fail closed;
- decision identity is deterministic despite mapping key order;
- mapping/sequence selector parameters retain unambiguous container identity;
- caller-side parameter mutation cannot mutate a frozen decision;
- non-finite/unordered selector parameter values fail closed;
- material decision changes alter the decision hash;
- OOS schedules cannot overlap or pre-decide the next allocation before the prior evaluation window ends.
