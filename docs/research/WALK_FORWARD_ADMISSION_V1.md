# Walk-Forward Executable Admission V1

Status: **Versioned product/edge admission contract.**

Contract version:

```text
walk-forward-admission-2026-08-17.1
```

Public route:

```text
GET /api/v1/research/walk-forward/admission
```

## 1. Purpose

The Walk-Forward research UI must not advertise a default request that is structurally valid in the browser but predictably rejected by the authoritative research runtime.

Admission therefore answers one narrow question from already-stored Point-in-Time evidence:

> Which enabled Universe, Decision date and holding count currently have a causal snapshot and fit the synchronous public Walk-Forward capacity bounds?

Admission is an **early product guard**, not a second research authority. A successful admission response never guarantees that later market-data, selector or OOS execution will succeed. `POST /api/v1/research/walk-forward` remains the final fail-closed authority.

## 2. Authority boundary

Admission is computed by the Cloudflare Worker directly from the existing D1 Universe/PIT archive.

It must not:

- infer historical membership from current constituents;
- convert proxy membership into authoritative membership;
- truncate a historical Universe to the first N symbols;
- download market history or fundamentals to manufacture eligibility;
- recompute Exhaustive ranking, Portfolio ledger or performance metrics;
- persist or mutate a Walk-Forward research result.

The browser consumes admission only to bootstrap/recover executable settings and to explain blocked Universes.

## 3. V1 capacity rules

V1 mirrors the already-versioned public Walk-Forward synchronous bounds:

```text
PIT candidates <= 100
holdingCount <= 20
Exhaustive combinations <= 500,000 per period
PIT snapshot age <= 10 calendar days from source_as_of to Decision
Decision >= source_as_of
Decision >= date(fetched_at)
Evaluation must be able to begin strictly after Decision
```

A recommendation is only emitted when all admission-level rules are simultaneously satisfiable.

For a PIT member count `n`, the recommended holding count is the largest integer at or below 10 (and at or below the public holding limit) whose exact combination count fits the per-period budget. This is an admission/capacity choice only; it does not alter Exhaustive scoring or ranking.

Example:

```text
30 choose 10 = 30,045,015  -> blocked by synchronous budget
30 choose 5  =    142,506  -> admissible
```

## 4. Universe states

Each enabled D1 Universe is reported as either `eligible` or `blocked`.

Blocked reason codes are explicit:

```text
no_pit_snapshots
proxy_membership_only
candidate_limit
no_causal_snapshot_window
combination_budget
```

The UI may translate these codes for humans but must not silently substitute another data source.

## 5. Recommendation semantics

An eligible Universe includes:

- earliest and latest currently admissible Decision date;
- recommended Decision date;
- PIT member count;
- recommended holding count;
- exact Exhaustive combination count;
- source/evidence dates and snapshot version.

The top-level `recommended` object selects the first eligible Universe under the repository's existing enabled-Universe ordering. This ordering is product navigation only; it does not change historical membership or selector mathematics.

If no Universe is eligible, `recommended` is `null`. The system must say so rather than fabricate an executable default.

## 6. Browser migration / persistence

`localStorage` remains convenience state only.

On first use, the browser may seed the Walk-Forward workspace from live admission. The browser may also replace the known legacy 4A-6 first-run default (`sp500`, holding count 10, one period), because production evidence proved that exact default could not pass the V1 admission contract.

Other user-authored workspace settings are not silently overwritten. The user receives an explicit **套用可執行預設** action to restore the live recommendation.

Admission does not become ResearchRun persistence and does not grant local browser state any research-authority status.

## 7. Root-cause record

The 2026-08-17 production D1 audit found:

- S&P 500 archive: roughly 500 members and proxy membership;
- Russell 2000 archive: roughly 1,960 members and proxy membership;
- NASDAQ-100 archive: 102–103 authoritative members, above the V1 100-candidate ceiling;
- SOXX archive: 30 authoritative members;
- causal PIT archive availability began on 2026-07-29 rather than the old UI's approximately 180-day-old default Decision date.

Therefore the old `sp500 / 10 holdings / ~180 days ago` first-run request was predictably non-executable even though browser-only date validation could call it valid.

The systemic correction is dynamic D1 admission, not a hard-coded SOXX date patch.

## 8. Regression and production locks

Required regression coverage:

1. proxy-only Universe is blocked;
2. authoritative Universe above 100 candidates is blocked;
3. exact combination budget determines an admissible holding count;
4. admission is served from D1 and is never proxied to the Vercel backend;
5. missing D1 fails closed;
6. legacy impossible browser default is upgraded before the workspace mounts;
7. explicit admission reset restores an executable model after manual edits;
8. existing Walk-Forward execution/cancel/result/provenance behavior remains unchanged;
9. production deploy smoke requires at least one executable admission recommendation and verifies its capacity/date invariants.

A one-time release acceptance should additionally execute the recommended public Walk-Forward request end-to-end. That expensive execution is not required on every future deployment.
