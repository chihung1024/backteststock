# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff. Mutable GitHub / CI / Vercel / Cloudflare / runtime truth must be re-queried before important writes. Durable semantics live in versioned contracts under `docs/`; closed execution history remains reconstructable from Git, PRs and Actions.

Last updated: **2026-08-15**

## 1. North Star

Build BacktestStock into a:

> **Point-in-Time, reproducible, Walk-Forward, eventually AI-automated investment research platform.**

Priority order:

1. Correctness
2. Point-in-Time causality
3. Walk-Forward research
4. Research memory / reproducibility
5. PIT fundamentals
6. AI research automation
7. Scale / performance

Functionality, quantitative correctness, data integrity and user experience outrank optional infrastructure/process work.

## 2. Verified Main Baseline

Current verified `main` before the active Batch 4A-3 candidate:

```text
64b717c38c9522c0c68db5f122aa67ad963690d9
feat: add Walk-Forward selection core (#155)
```

Batch 4A-2 / PR #155 is **CLOSED / MERGED / POST-MAIN VERIFIED (R2)**.

Evidence:

- final candidate received independent approval and zero blocking review threads;
- pre-merge and post-merge recovery releases targeted the exact protected SHAs;
- post-main CI #763 passed at `64b717c38c9522c0c68db5f122aa67ad963690d9`;
- Vercel production deployment completed successfully;
- Cloudflare production runtime deploy was correctly not forced because Batch 4A-2 changed no matching Worker/public/migration runtime path.

Batch 4A-1 / PR #154 remains closed and post-main verified. Earlier PF/UX history remains in Git/PR/Actions rather than being duplicated here.

## 3. Primary Active Batch

### Batch 4A-3 — Existing Exhaustive Adapter + Golden Parity

Status: **ACTIVE / Draft PR #156 / R2 Significant**

Branch:

```text
feat/batch4a3-exhaustive-adapter-parity
```

Base:

```text
main@64b717c38c9522c0c68db5f122aa67ad963690d9
```

PR:

```text
#156 — feat: adapt Exhaustive authority to Walk-Forward selection
```

Do not trust a hard-coded candidate head here. Re-query PR #156 before review, Ready or merge because this handoff commit itself changes the branch head.

## 4. Objective / Architecture Lock

4A-3 adapts the **existing** Exhaustive authority behind the Batch 4A-2 `SelectionEngine` boundary. It must not create a second optimizer or new investment methodology.

Causal path:

```text
PIT candidate Training ResearchDataset
        +
Training-only Exhaustive authority ResearchDataset
(exact candidates + benchmark)
        ↓
ExhaustiveSelectionEngine
        ↓
Node bridge
        ↓
public/exhaustive-optimizer-core.js
        ↓
authoritative winning combination
        ↓
SelectionResult
        ↓
immutable DecisionSnapshot
```

No Evaluation/OOS observations are visible to the selector or JavaScript authority.

`SelectionContext.training_dataset` remains candidate-only so PIT eligibility is unchanged. The separate Exhaustive authority dataset contains the exact candidate sequence followed by the benchmark for the same Training window; the benchmark never becomes an eligible constituent.

## 5. Quant / Data Authority Invariants

### One numerical authority

`public/exhaustive-optimizer-core.js` remains authoritative for:

- exact combination simulation;
- portfolio NAV and rebalance mathematics;
- transaction costs;
- Sortino, CAGR, MDD, volatility, beta and alpha;
- stable/growth/drawdown/optimized scores.

Python owns orchestration, causal admission, provenance and fail-closed result validation only. No Python copy of these formulas is permitted.

### Current winner contract

```text
field     = optimized_score
direction = descending
nonfinite = negative infinity / worst
tie-break = smaller combination rank
```

Golden parity tests compare the bridge winner against direct use of the same current JS core.

### Training evidence

The adapter requires:

- no silently dropped PIT member;
- exact candidates+benchmark authority dataset order;
- exact Training start/end and no observation after Decision;
- identical candidate raw native/FX/TWD history fingerprints and audit evidence across the candidate-only and authority datasets;
- existing 2–100 candidate and 50,000,000-combination ceilings;
- existing minimum-observation and `_strict_full_period_coverage()` policy;
- `verified_standard_actions` for every candidate and benchmark;
- finite positive TWD authority levels.

The authority dataset hash is frozen in selector parameters and revalidated after JS execution.

### Risk-free-rate parity

The adapter does **not** add a new risk-free-rate strategy control. It reads the same server-configured `legacy.RISK_FREE_RATE` used by the existing Exhaustive prepare path, snapshots the exact value into the decision, and passes it unchanged to the existing JS authority.

## 6. Current Implementation Surface

```text
apps/api/app/research/exhaustive_selection.py
apps/api/app/research/__init__.py
scripts/exhaustive_selection_authority.mjs
tests/test_walk_forward_exhaustive_selection.py
tests/test_exhaustive_selection_authority.mjs
docs/research/WALK_FORWARD_EXHAUSTIVE_ADAPTER_V1.md
docs/research/README.md
package.json
to_do_update_list.md
```

No `public/exhaustive-optimizer-core.js` numerical implementation, Worker route, D1 migration or public Walk-Forward UI is changed by this batch.

`NodeExhaustiveAuthorityRunner` is internal research/CI infrastructure for executable cross-language parity. 4A-3 does not assert Node availability in the eventual production Python runtime; deployment/job placement is intentionally deferred to 4A-5.

## 7. Root Cause / General Fix Log

### A. Immutable DecisionSnapshot inspection in new tests — TEST-ONLY FIX

Initial CI #764 passed compile/Ruff but two new Python tests directly subscripted the internal `_FrozenMapping` representation of `selector_parameters`.

Root cause: the tests bypassed the 4A-1 immutable/export contract.

General fix: inspect canonical selector parameters through `DecisionSnapshot.export_payload()`; production code was not weakened.

### B. Adapter initially exposed arbitrary `risk_free_rate` — FIXED BEFORE REVIEW

Self-review found the first adapter constructor allowed an arbitrary risk-free value even though the current production Exhaustive workflow receives its risk-free rate from server configuration.

Impact: no observed result corruption, but it would have introduced a new strategy degree of freedom and broken strict parity.

General fix:

- remove adapter-level `risk_free_rate` constructor input;
- bind to existing `legacy.RISK_FREE_RATE`;
- freeze that value in selector parameters;
- regression proves an attempted constructor override is rejected.

### C. Non-finite tie-break fixture used a positive risk-free rate — TEST-ONLY FIX

CI #768 passed 313 Python tests and the primary direct-core bridge parity test, but one new JS edge-case fixture expected a flat portfolio to produce `NaN` while retaining a 3% risk-free rate.

Current core correctly produced a finite negative Sortino/optimized score in that case.

General fix: set risk-free rate to zero only in the dedicated non-finite fixture so downside deviation is zero and the intended NaN/non-finite ranking path is genuinely exercised. Production behavior was unchanged.

## 8. Verification Evidence

Functional candidate before this handoff commit:

```text
head = 0b76ff38e5e5cc3c80bb4ede6e7a44f9d4612cd5
CI #769 = SUCCESS
```

CI #769 passed:

- Python dependency consistency;
- compile and Ruff;
- full Python suite, including 4A-3 Python→Node→existing JS authority→DecisionSnapshot regression;
- JavaScript syntax checks;
- Worker/Exhaustive tests, including direct-core winner golden parity and non-finite smaller-rank tie-break;
- existing canonical Exhaustive quant-authority fixture;
- score-formula tests;
- Portfolio type-check/build and source contracts;
- committed production-asset verification;
- Chromium E2E;
- Vercel configuration;
- local D1 migrations;
- Cloudflare bundle dry-run.

Because this handoff update changes the PR head, **CI #769 is functional-candidate evidence, not the final exact-head merge gate**. The new final head must receive fresh CI before independent review/merge.

## 9. Remaining R2 Gates

For PR #156:

1. fresh exact-head CI after this handoff commit;
2. independent review on that exact head;
3. zero unresolved BLOCKER review threads;
4. Ready transition;
5. `release-backup` pre-merge recovery verification against exact current `main`;
6. final head/base/review/CI/recovery TOCTOU;
7. squash merge using `expected_head_sha`;
8. post-main recovery, CI and deployment-state verification.

Independent review focus:

- no numerical formula duplication in Python;
- no OOS observations in selection;
- candidates+benchmark Training evidence remains causal and hash-bound;
- benchmark never enters PIT eligibility;
- current server-configured risk-free authority is preserved;
- golden winner/tie-break semantics match current Exhaustive behavior;
- Node execution placement is not falsely treated as a production-runtime guarantee.

## 10. Walk-Forward Roadmap

| Batch | Objective | Status |
| --- | --- | --- |
| 4A-1 | Temporal causality firewall + immutable `DecisionSnapshot` | **DONE / PR #154 / post-main verified** |
| 4A-2 | `SelectionEngine` + physical Training/OOS separation | **DONE / PR #155 / post-main verified** |
| 4A-3 | Existing Exhaustive adapter + golden parity | **ACTIVE / PR #156** |
| 4A-4 | Continuous OOS Portfolio ledger across decisions | **NEXT** |
| 4A-5 | PIT resolver/API/job orchestration | PLANNED |
| 4A-6 | User-facing Walk-Forward UX | PLANNED |
| 4B+ | Research memory / PIT fundamentals / AI automation | BACKLOG until 4A foundation is stable |

4A-4 must create one continuous investable OOS ledger across decisions. Do not reset NAV per period and stitch/average period-local results as though they were one portfolio history.

## 11. Authority Boundaries / Risk Register

### Market / FX / research data

Authority remains `ResearchDatasetV1`, `TWDHistoryService` and existing TWD valuation/corporate-action/FX contracts. Do not add another downloader or valuation path.

### PIT membership

Authority remains Worker/D1 PIT archive and its causality/integrity rules. Historical research must fail closed where causally valid archived membership is unavailable.

### Exhaustive optimization

Authority remains `public/exhaustive-optimizer-core.js`; 4A-3 only adapts it behind SelectionEngine.

### OOS execution

Continuous execution accounting belongs to 4A-4.

### Fundamentals

Current fundamentals are not PIT evidence and remain excluded from historical selection until a separately governed PIT source exists.

### Key active risks

- future-data leakage: controlled structurally by Training/OOS separation;
- duplicate quant authority: controlled by JS authority delegation + golden parity;
- cross-language execution placement: intentionally deferred to 4A-5, not solved by duplicating formulas;
- historical PIT/data incompleteness: fail closed, never fabricate;
- PR #147 security/perimeter work remains frozen/deferred and is not a 4A blocker.

## 12. NOW / NEXT / BACKLOG / REJECT

### NOW

Close Batch 4A-3 / PR #156:

```text
handoff commit
→ exact-head CI
→ independent review
→ Ready
→ recovery backup
→ final TOCTOU
→ squash merge
→ post-main verification
```

### NEXT

Batch 4A-4 — continuous OOS Portfolio ledger across decisions.

### BACKLOG

- 4A-5 PIT/API/job orchestration;
- 4A-6 Walk-Forward UX;
- ResearchRun persistence / research memory;
- PIT fundamentals;
- AI research automation/autopilot;
- scale/performance after correctness contracts stabilize.

### REJECT FOR CURRENT 4A-3

- new selection/ranking/alpha methodology;
- Python duplication of Exhaustive mathematics;
- new risk-free-rate tuning surface;
- OOS ledger implementation;
- public Walk-Forward API/UI;
- persistence migration for convenience;
- reactivating PR #147;
- unrelated refactors/process expansion.

## 13. Exact Resume Point

On resume:

1. read `AI_PROJECT_PLAYBOOK.md` and this file;
2. read `RESEARCH_DATASET_V1.md`, `WALK_FORWARD_TEMPORAL_CONTRACT_V1.md`, `WALK_FORWARD_SELECTION_CORE_V1.md` and `WALK_FORWARD_EXHAUSTIVE_ADAPTER_V1.md`;
3. re-query `main`, PR #156, exact-head CI, reviews/threads and release state;
4. continue only Batch 4A-3 until its R2 gates close.

Expected state immediately after this handoff commit:

```text
main = 64b717c38c9522c0c68db5f122aa67ad963690d9
PR #156 = Draft / Batch 4A-3
branch = feat/batch4a3-exhaustive-adapter-parity
next gate = fresh exact-head CI on the handoff-updated head
```

If remote truth differs, remote truth wins and the discrepancy must be analyzed before merge/rebase/reset.
