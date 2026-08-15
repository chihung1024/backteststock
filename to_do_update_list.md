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

Current production main before Batch 4A-5:

```text
f993bac1877532e1dd16ae4dde6022601ac1b6ca
feat: add continuous Walk-Forward OOS ledger (#157)
```

Walk-Forward foundation already closed and post-main verified:

| Batch | Result |
| --- | --- |
| 4A-1 | Temporal causality firewall + immutable DecisionSnapshot — DONE / PR #154 |
| 4A-2 | SelectionEngine + physical Training/OOS separation — DONE / PR #155 |
| 4A-3 | Existing JavaScript Exhaustive adapter + golden parity — DONE / PR #156 |
| 4A-4 | Continuous OOS Portfolio ledger — DONE / PR #157 |

Batch 4A-4 post-main evidence includes recovery release, main CI #778 SUCCESS and Vercel deployment SUCCESS. Closed detail belongs to Git/PR/Actions rather than being duplicated here.

## 3. Primary Active Batch

### Batch 4A-5 — PIT Resolver / API / Job Orchestration

Status: **ACTIVE / Draft PR #158 / R2 Significant**

Branch:

```text
feat/batch4a5-walk-forward-api-orchestration
```

Base:

```text
main@f993bac1877532e1dd16ae4dde6022601ac1b6ca
```

PR:

```text
#158 — feat: add causal Walk-Forward API orchestration
```

Do not trust a hard-coded candidate head in this file. Re-query PR #158 before review, Ready or merge because this handoff update itself changes the branch head.

Durable semantics:

```text
docs/research/WALK_FORWARD_API_ORCHESTRATION_V1.md
```

## 4. 4A-5 Objective / Architecture Lock

4A-5 makes the already-versioned 4A-1…4A-4 research pipeline callable as one bounded server workflow without creating a new quant/data authority.

Causal path:

```text
explicit period schedule
    ↓
Worker/D1 PIT resolver at exact Decision date
    ↓
one audited Training fetch: exact PIT members + benchmark
    ↓
ResearchDataset candidate view + Exhaustive authority view
    ↓
existing JavaScript Exhaustive numerical authority
    ↓
immutable DecisionSnapshot
    ↓
only now fetch selected-constituent Evaluation data
    ↓
validated Evaluation ResearchDataset
    ↓
Batch 4A-4 continuous OOS Portfolio ledger
    ↓
existing Portfolio v3 metrics
```

Primary invariant remains:

```text
Training data <= Decision point < Evaluation/OOS data
```

## 5. Authority Boundaries

### PIT membership

Worker/D1 remains the sole historical-membership authority. Python only consumes `/api/v2/universes/{id}?asOf=...` and preserves exact provenance.

Public 4A-5 v1 requires authoritative, non-proxy PIT membership. Current membership or current fundamentals must never substitute for missing historical evidence.

### Training / market data

`TWDHistoryService` + `ResearchDatasetV1` remain the data authority. Candidate symbols and benchmark are fetched once per period, then deterministic dataset views are built from the same audited batch.

### Exhaustive numerical authority

`public/exhaustive-optimizer-core.js` remains the numerical/ranking authority. Python does not reimplement score, Sortino, CAGR, MDD, beta, rebalance or tie-break mathematics.

Production placement is a bounded Vercel Node function; Python calls it over a deployment-bound HTTP contract instead of assuming a Node binary exists inside the Python runtime.

### OOS execution / metrics

Batch 4A-4 remains the continuous OOS orchestration authority; Portfolio v3 remains the transaction-cost/portfolio/metric authority.

## 6. Public V1 Methodology Lock

The public request deliberately exposes only methodology that current Training and OOS engines can interpret consistently.

Selector:

```text
universe
benchmark
holdingCount
```

Fixed selection semantics:

```text
Exhaustive authority = existing JavaScript core
weighting = equal
rebalanceMode = never
Training transaction cost = 0
execution delay provenance = 1 trading day
```

OOS request:

```text
initialAmountTwd
transitionCostBps
```

Fixed OOS semantics:

```text
one continuous TWD ledger
no in-segment rebalance
no external cashflow
no leverage
reinvest distributions
transition cost only at later frozen Decision target changes
```

Unversioned public strategy knobs are rejected rather than approximately mapped between different engines.

## 7. Resource / Large-Universe Admission

Current synchronous v1 bounds:

```text
periods <= 24
PIT candidates <= 100
holdingCount <= 20
Exhaustive combinations <= 500,000 per period
Exhaustive combinations <= 2,000,000 per job
public request body <= 128 KiB
Node authority body <= 3 MiB
```

If PIT membership exceeds 100 symbols, fail closed.

Explicitly rejected shortcuts:

- first-100 truncation;
- current-fundamental historical prefilter;
- current-constituent ranking used as PIT evidence;
- silent history-failure candidate drop.

Large-universe historical narrowing belongs to future PIT-fundamentals work after it has causal evidence.

## 8. Current Implementation Surface

New/changed 4A-5 areas include:

```text
apps/api/app/research/pit_client.py
apps/api/app/research/exhaustive_authority_http.py
apps/api/app/research/walk_forward_job.py
api/exhaustive_selection_authority.mjs
api/walk_forward_v1.py
worker/walk_forward_router.js
scripts/smoke_test_walk_forward_v1.mjs
tests/test_walk_forward_pit_client.py
tests/test_walk_forward_job.py
tests/test_walk_forward_api.py
tests/test_exhaustive_authority_http.mjs
tests/test_walk_forward_edge_route.mjs
vercel.json
wrangler.jsonc
package.json
.github/workflows/deploy-cloudflare.yml
docs/research/WALK_FORWARD_API_ORCHESTRATION_V1.md
docs/research/README.md
to_do_update_list.md
```

This batch changes production routing/deployment behavior and therefore remains R2 until post-main runtime verification closes.

## 9. Production Topology / Hardening

Production path:

```text
future UI / caller
    ↓
Cloudflare same-origin Worker
    ↓
Vercel Python Walk-Forward API
    ├─→ Worker/D1 PIT Universe authority
    ├─→ existing market-data services
    └─→ Vercel Node JavaScript Exhaustive authority
```

Hardening currently includes:

- no-store/security headers;
- strict request schemas/body limits;
- edge/backend research rate limits;
- exact deployment-SHA binding for Python→Node authority calls;
- bounded Node combination count;
- optional `WALK_FORWARD_INTERNAL_SECRET` or existing Vercel Automation Bypass secret upgrades selection admission to secret + deployment binding;
- honest bounded fallback if no secret is configured;
- production smoke waits for Node authority and Worker-routed API health to report the expected deployment SHA.

A secret is hardening, not a PIT/quant authority and is not required to preserve research causality.

## 10. Regression Locks

Current tests lock at least:

1. exact Worker PIT response/provenance parsing;
2. noncausal/date-mismatched PIT rejection;
3. proxy truth preservation and public rejection;
4. exact operation order PIT → Training → selection → Evaluation;
5. one shared Training fetch for candidates + benchmark;
6. Evaluation fetch only after DecisionSnapshot;
7. >100-member PIT fail-closed behavior without market-data work;
8. strict public API schema rejecting unversioned strategy knobs;
9. health bypassing research-work quota;
10. Vercel Node raw/pre-parsed body compatibility;
11. optional internal-secret admission;
12. Node Exhaustive combination budget;
13. same-origin edge route body/header sanitation and limits;
14. deployment-SHA readiness smoke syntax;
15. full repository CI/regression gates.

## 11. Self-Review / Root-Cause Record

### A. Python-side reimplementation of PIT or Exhaustive — REJECTED

Would create duplicate authorities and drift. 4A-5 consumes Worker/D1 PIT and existing JavaScript Exhaustive authority directly.

### B. Large-universe arbitrary truncation — REJECTED

Would create a hidden selection rule with no historical evidence. V1 fails closed above 100 PIT members.

### C. Exposing all existing Exhaustive rebalance knobs — REJECTED

Training JavaScript execution semantics are not guaranteed identical to current Portfolio v3 OOS semantics. V1 exposes only gross buy-and-hold selection and decision-transition OOS cost.

### D. Running local `node` subprocess in production Python — REJECTED

Serverless Python cannot be assumed to provide the Node executable used by local tests. The JavaScript authority is placed in its own Vercel Node function.

### E. Mixing Vercel legacy `builds` and `functions` config — FIXED

A preview deployment failed when function-duration configuration was added through a top-level `functions` block alongside the repository's existing `builds` configuration.

Root-cause fix: keep the existing legacy `builds` topology unchanged and configure the Node authority duration inside the Node function itself. Do not migrate unrelated Vercel functions merely to set one duration.

### F. Cloudflare/Vercel deployment race — CONTROLLED BY SMOKE

Cloudflare and Vercel can converge at different times after one main merge. Production acceptance waits until the new Walk-Forward health and Node authority report the exact expected merge SHA.

## 12. Current Verification State

A pre-handoff implementation candidate already achieved full repository CI and a successful Vercel preview before the final self-review hardening.

A later preview exposed the Vercel `functions + builds` configuration incompatibility; that configuration has been removed and the narrow root-cause fix applied.

Because this live handoff write changes the exact branch head, **all previous CI/preview runs are supporting evidence only**. The final handoff-updated head must receive fresh:

1. full exact-head CI;
2. Vercel preview success;
3. independent review on that exact head.

## 13. Remaining R2 Gates for PR #158

1. final exact-head full CI;
2. final exact-head Vercel preview success;
3. final diff self-review / no BLOCKER;
4. independent `cchung911` review on exact head;
5. zero unresolved BLOCKER review threads;
6. Ready transition;
7. `release-backup` pre-merge recovery against exact current main;
8. final head/base/review/CI/recovery TOCTOU;
9. squash merge with expected exact head;
10. post-main recovery;
11. main CI SUCCESS;
12. Vercel production deployment SUCCESS;
13. Cloudflare Worker deploy + remote D1 + Russell / Portfolio / Walk-Forward / Refinery production smokes SUCCESS.

## 14. Roadmap

| Batch | Objective | Status |
| --- | --- | --- |
| 4A-1 | Temporal causality firewall + immutable DecisionSnapshot | DONE |
| 4A-2 | SelectionEngine + physical Training/OOS separation | DONE |
| 4A-3 | Existing Exhaustive adapter + golden parity | DONE |
| 4A-4 | Continuous OOS Portfolio ledger | DONE |
| 4A-5 | PIT Resolver / API / Job Orchestration | **ACTIVE / PR #158** |
| 4A-6 | User-facing Walk-Forward UX | NEXT after 4A-5 closes |
| 4B+ | Research memory / PIT fundamentals / AI automation | BACKLOG until 4A foundation is stable |

## 15. NOW / NEXT / BACKLOG / REJECT

### NOW

Close Batch 4A-5 / PR #158:

```text
handoff-updated exact head
→ full CI + Vercel preview
→ final self-review
→ independent review
→ Ready
→ recovery backup
→ final TOCTOU
→ squash merge
→ post-main CI / Vercel / Cloudflare production smokes
```

### NEXT

Batch 4A-6 — user-facing Walk-Forward UX over the now-versioned server workflow. UX must surface provenance/failure truth rather than hide it.

### BACKLOG

- persistent ResearchRun / research memory;
- PIT fundamentals / large-universe causal narrowing;
- AI research automation/autopilot;
- distributed scale/performance after correctness contracts stabilize.

### REJECT FOR CURRENT 4A-5

- new alpha/ranking formulas;
- Python copies of PIT, Exhaustive or Portfolio mathematics;
- current fundamentals as historical evidence;
- arbitrary large-universe truncation;
- persistent job database/queue merely for convenience;
- 4A-6 UI work;
- unrelated refactors/process expansion;
- reactivating frozen PR #147.

## 16. Exact Resume Point

On resume:

1. read `AI_PROJECT_PLAYBOOK.md` and this file;
2. read `docs/research/WALK_FORWARD_API_ORCHESTRATION_V1.md` plus 4A-1…4A-4 contracts;
3. re-query current `main`, PR #158, exact-head CI, Vercel status, reviews/threads and release state;
4. continue only Batch 4A-5 until R2 production gates close.

Expected state immediately after this handoff commit:

```text
main = f993bac1877532e1dd16ae4dde6022601ac1b6ca
PR #158 = Draft / Batch 4A-5
branch = feat/batch4a5-walk-forward-api-orchestration
next gate = fresh exact-head CI + Vercel preview
```

If remote truth differs, remote truth wins and the discrepancy must be analyzed before merge/rebase/reset.
