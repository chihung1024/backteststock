# Walk-Forward Research Contract

Status: **Current production Walk-Forward contract.**

This document consolidates the former temporal, selection, Exhaustive-adapter, OOS-ledger, API, admission and UI phase documents. The implementation and tests remain the exact authority for current version strings and limits; this document preserves the durable semantic boundaries.

## 1. First principle: future data cannot choose the same decision

The invariant is:

```text
Training data <= Decision point < Evaluation / OOS data
```

A `DecisionSnapshot` must be fully determined and frozen before Evaluation observations are available to the selection path. Evaluation may score that frozen decision but may not mutate its membership, weights, parameters, provenance or identity.

Decision timing is `after_close`; Evaluation starts strictly after the Decision date.

## 2. Authority boundaries

Walk-Forward orchestrates existing authorities rather than duplicating them:

- historical membership: Worker/D1 PIT archive;
- market data / FX / TWD valuation: `TWDHistoryService` and `ResearchDataset`;
- PIT/Exhaustive numerical search: existing JavaScript authority `public/exhaustive-optimizer-core.js`;
- configured strategy selection/allocation: versioned backend research modules;
- OOS execution and transition costs: Portfolio v3 ledger;
- OOS metrics: existing Portfolio v3 metric authority;
- durable saved research: D1 ResearchRun;
- browser: request editing, cancellation and evidence presentation only.

No Walk-Forward layer may create a second downloader, metric engine, Portfolio simulator, PIT resolver or browser-side numerical authority.

## 3. Period and schedule semantics

One period binds:

- Training start/end;
- Decision date;
- Evaluation start/end;
- `after_close` timing.

Required ordering:

```text
training_start <= training_end <= decision_date < evaluation_start <= evaluation_end
```

Across periods:

- decision dates are strictly increasing;
- Evaluation windows do not overlap;
- a later decision cannot predate the end of the previous Evaluation window.

The schedule may contain gaps. A gap does not authorize invented market observations.

## 4. PIT provenance

For PIT-based research, exact membership evidence is attached to the Decision date. The system preserves at least:

- requested/source/evidence-availability dates;
- exact fetch timestamp;
- source label/URL;
- version/checksum/policy;
- ordered members;
- authoritative/proxy truth.

Causal evidence must have been available no later than the requested Decision. Proxy evidence never becomes authoritative by relabeling. Missing historical evidence never falls back to current membership.

For a PIT `DecisionSnapshot`, PIT `requested_as_of` equals the period Decision date exactly.

## 5. Training isolation and SelectionContext

`SelectionContext` receives one exact Training `ResearchDataset` plus membership and explicit unavailable-candidate accounting.

It contains no Evaluation/OOS observations.

The Training dataset must:

- represent the requested Training window;
- preserve requested membership and explicit failures;
- remain internally hash-consistent;
- have effective observations inside Training and no later than Decision.

Changing future OOS paths, even materially, must not change the frozen selection or decision hash.

## 6. Immutable DecisionSnapshot and identity

A Decision freezes all material choice evidence, including as applicable:

- period and timing;
- PIT or configured-membership provenance;
- Training dataset identity/effective range;
- selector contract/rule/parameters;
- eligible candidates and explicit failures;
- selected constituents;
- final weights;
- selection/allocation/tuning evidence.

Selected constituents must be eligible; weights must be finite, positive and sum to one.

Identity is deterministic SHA-256 over canonical JSON of the material decision payload. Mutation of any material input must change the decision identity. Caller-side mutation after freeze must not change the snapshot.

## 7. Existing Exhaustive authority

PIT/Exhaustive Walk-Forward uses the existing JavaScript numerical authority rather than a Python rewrite.

Python orchestration may:

- validate causal evidence;
- prepare versioned ResearchDataset views;
- call the existing authority;
- validate returned authority identity/result;
- convert the winning exact combination into the common selection boundary.

Python must not independently reimplement the authoritative combination simulation, score formulas, rebalance mechanics or ranking tie-break merely for Walk-Forward.

Candidate-only Training evidence and candidates-plus-benchmark Exhaustive evidence may be separate `ResearchDataset` views only when they are built from the same audited history and candidate history identity is preserved.

## 8. Continuous OOS ledger

Evaluation periods are evidence partitions, not independent portfolios.

The result is one continuous TWD OOS ledger:

```text
Frozen decision
→ validated Evaluation evidence
→ Portfolio v3 segment execution
→ target transition/cost
→ carried capital state
→ next segment
→ one continuous ledger
→ one final metric report
```

Rules:

- never reset NAV at each Evaluation period;
- carry actual ending equity/allocation into the next period;
- use Portfolio v3 for transition turnover and transaction costs;
- compute final metrics from the continuous ledger, not averages of period-local metrics;
- gap dates are not fabricated; last audited state carries flat until the next observed baseline;
- V1 research OOS uses reinvested-distribution evidence with no external cashflow/leverage state unless a separately versioned contract proves otherwise.

The unchanged-target split case must remain parity-compatible with the equivalent ordinary Portfolio v3 path.

## 9. Public API and causal orchestration

Public surface includes:

```text
POST /api/v1/research/walk-forward
GET  /api/v1/research/walk-forward/health
GET  /api/v1/research/walk-forward/admission
```

For PIT/Exhaustive execution the required order is:

```text
validate schedule
→ resolve PIT for exact Decision date
→ apply bounded admission
→ one audited Training fetch for candidates + benchmark
→ create causal Training views
→ invoke existing Exhaustive authority
→ freeze DecisionSnapshot
→ only then load Evaluation data
→ validate Evaluation against frozen Decision
→ execute one continuous OOS ledger
```

No error path may substitute current membership, current fundamentals, approximate portfolio math or another optimizer.

## 10. Current bounded public limits

The implementation currently enforces, among other guards:

```text
MAX_WALK_FORWARD_PERIODS = 24
MAX_SERVER_EXHAUSTIVE_CANDIDATES = 100
MAX_SERVER_EXHAUSTIVE_COMBINATIONS_PER_PERIOD = 500_000
MAX_SERVER_EXHAUSTIVE_COMBINATIONS_PER_JOB = 2_000_000
MAX_PUBLIC_HOLDING_COUNT = 20
MAX_CONFIGURED_STRATEGY_SYMBOLS = 50
MAX_PARAMETER_CANDIDATES = 48
MAX_INNER_FOLDS = 6
MAX_TUNING_EVALUATIONS_PER_JOB = 216
```

The constants in code are authoritative. Raising a resource ceiling requires evidence that the product workload and runtime can support it without silently degrading methodology.

## 11. Admission

Admission is an early D1-backed product guard, not final research authority.

It may recommend an enabled Universe/Decision/holding-count combination only when current PIT evidence satisfies causal and synchronous-capacity constraints. It must not download history, rank securities, truncate oversized membership or convert proxy evidence into authoritative evidence.

A successful admission response means only that the request is structurally plausible. The final POST remains fail-closed on market-data, selection and OOS evidence.

Current PIT admission includes candidate and combination limits and a bounded snapshot-age rule. If no eligible recommendation exists, the result is explicitly unavailable rather than fabricated.

## 12. Browser contract

The Walk-Forward workspace is presentation/orchestration only.

It may:

- edit/validate obvious request structure;
- show normalized requests;
- submit/cancel synchronous jobs;
- invalidate stale results after material request edits;
- display backend metrics, series, hashes and provenance;
- store convenience workspace settings.

It must not:

- resolve PIT membership;
- silently truncate candidates;
- fetch replacement history;
- recompute selection, Portfolio paths, CAGR, Sortino, MDD or costs;
- fabricate an OOS benchmark;
- convert a failed job to partial success;
- create retry loops that hide public rate limits.

Browser validation improves UX but never supersedes backend causal/resource validation.

## 13. Job and deployment identity

Current runtime maintains separately versioned identities for PIT/Exhaustive jobs and configured Optimizer Hub variants. Exact constants live in `apps/api/app/research/walk_forward_job.py`.

A completed job binds normalized request plus versioned evidence identities into deterministic backend-produced result identity. Durable `run_id` is a separate ResearchRun identity.

Production readiness for the split Cloudflare/Vercel topology must verify the actual expected backend/edge revision when deployment correctness depends on it.

## 14. Fail-closed rules

Reject rather than silently normalize when material evidence is invalid, including:

- impossible or overlapping temporal schedule;
- missing/noncausal PIT evidence;
- proxy membership where authoritative public PIT evidence is required;
- candidate or combination budgets exceeded;
- missing required Training history;
- Training/authority identity drift;
- authority version/result mismatch;
- Evaluation loaded outside the frozen decision contract;
- unsupported OOS state;
- inconsistent continuous ledger;
- deployment/readiness identity mismatch where required.

Tests, code and runtime evidence supersede stale prose.
