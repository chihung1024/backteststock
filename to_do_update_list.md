# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff. Mutable GitHub / CI / Vercel / Cloudflare / runtime truth must be re-queried before important writes. Durable semantics live in versioned contracts under `docs/`; detailed closed execution history remains reconstructable from Git, PRs and Actions.

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

## 2. Remote Baseline

Current verified `main` before the active Batch 4A-2 candidate:

```text
98f0de31b6a59451bbf01ae60384f7265dca30f2
feat: add Walk-Forward temporal causality contract (#154)
```

Batch 4A-1 / PR #154 is **CLOSED / MERGED / POST-MAIN VERIFIED (R2)**.

Evidence:

- PR #154 was independently approved and squash-merged.
- Main CI #757 passed at `98f0de31b6a59451bbf01ae60384f7265dca30f2`.
- Pre/post merge recovery releases were verified against the exact protected SHAs.
- Vercel completed successfully.
- Cloudflare production deploy was correctly not triggered because Batch 4A-1 changed no Worker/public/migration deployment path.

Previous pre-4A functional baseline culminated at `cf584139a42eaa46365edddf99273c0c05acf7ec` / PR #153. Earlier PF/UX closure details remain in repository history and the corresponding PR/Actions records rather than being duplicated as the live resume point.

## 3. Primary Active Batch

### Batch 4A-2 — Walk-Forward Selection Core

Status: **ACTIVE / Draft PR #155 / R2 Significant**

Branch:

```text
feat/batch4a2-selection-core
```

Base:

```text
main@98f0de31b6a59451bbf01ae60384f7265dca30f2
```

PR:

```text
#155 — feat: add Walk-Forward selection core
```

Do not trust a hard-coded candidate head here. Re-query PR #155 before review, Ready or merge because this handoff update itself changes the branch head.

### Objective

Create the causal Selection boundary that consumes Batch 4A-1 without creating a second data, universe, optimizer, Portfolio or metrics authority.

Required causal order:

```text
PIT membership at Decision
        +
exact Training ResearchDataset
        ↓
SelectionEngine
        ↓
immutable DecisionSnapshot
        ↓
Evaluation / OOS ResearchDataset
```

### In Scope

- `SelectionEngine` protocol.
- immutable selection context.
- exact Training `ResearchDataset` boundary.
- exact PIT membership accounting.
- explicit resolved-history vs `HistoryFailure` outcomes.
- deterministic eligible-candidate order.
- selector identity and parameters snapshotted before execution.
- Training dataset identity revalidated after selector execution.
- existing Batch 4A-1 `create_decision_snapshot()` remains final validation/freeze authority.
- Evaluation/OOS dataset accepted only after a frozen decision exists.
- configured equal-weight reference engine only for orchestration verification.
- future-data mutation regression: materially different OOS paths, including approximately +5000% / -99%, must not change selected constituents, weights or decision hash.

### Out of Scope

- new ranking/alpha methodology.
- duplicating current Exhaustive formulas or simulation.
- Refinery-driven selection.
- current-fundamental fallback or PIT fundamentals.
- continuous OOS Portfolio ledger.
- cross-period turnover/transaction-cost accounting.
- public Walk-Forward API/UI.
- ResearchRun persistence.
- reactivating frozen security/perimeter PR #147.
- unrelated cleanup/refactors.

## 4. Batch 4A-2 Current Implementation

Candidate files:

```text
apps/api/app/research/selection.py
apps/api/app/research/__init__.py
docs/research/WALK_FORWARD_SELECTION_CORE_V1.md
docs/research/README.md
tests/test_walk_forward_selection.py
tests/test_walk_forward_selection_identity.py
```

No production route, Worker, migration, public UI or Exhaustive formula has been changed by this batch.

### Selection Core invariants

`SelectionContext` exposes:

- `WalkForwardPeriod`;
- exact `ResolvedPITUniverse`;
- exact Training `ResearchDataset`;
- eligible candidates;
- explicit unavailable-candidate evidence.

It intentionally exposes **no Evaluation/OOS dataset or future observations**.

`build_selection_context()` requires:

- `PIT.requested_as_of == decision_date`;
- Training requested start/end exactly equal the period Training window;
- Training requested symbols exactly equal PIT membership order;
- every PIT member has exactly one explicit resolved/failure outcome;
- no resolved/failure overlap;
- dataset hash/export identity is intact;
- effective Training observations stay inside Training and at/before Decision;
- at least one eligible candidate.

`run_selection()`:

- has no Evaluation/OOS argument;
- snapshots selector identity/parameters before selector execution;
- captures Training dataset identity before execution;
- revalidates Training identity after execution so selector mutation fails closed;
- freezes output only through Batch 4A-1 `create_decision_snapshot()`.

`validate_evaluation_dataset()`:

- operates only on an already-created `DecisionSnapshot`;
- requires exact Evaluation window;
- validates Evaluation dataset identity;
- requires every selected constituent to be requested and resolved;
- allows additional evaluation symbols such as a benchmark;
- cannot modify the frozen decision identity.

## 5. Root Cause / General Fix Log

### 4A-2 provenance identity gap — FIXED BEFORE REVIEW

Initial implementation stored only the engine-reported selector version in `DecisionSnapshot.selector_contract_version`, while the built-in reference engine's version/rule could be constructor-overridden.

Root cause:

- selector identity represented the adapter/engine but did not explicitly bind the 4A-2 orchestration contract itself;
- built-in identity metadata was represented as dataclass fields rather than immutable class identity.

Impact:

- no future-data leak and no quantitative result corruption was observed;
- provenance/reproducibility could become ambiguous if the orchestration boundary changed while an engine version did not.

General fix:

```text
DecisionSnapshot.selector_contract_version
= <selection-core-version> + <engine-version>
```

Built-in engine identity uses `ClassVar`, so constructor callers cannot spoof it.

Regression:

- dedicated identity test proves the composite version is frozen into the decision;
- constructor spoofing of the built-in engine version raises `TypeError`.

## 6. Verification Evidence

Pre-handoff code candidate CI:

```text
CI #761
head before this handoff commit: f7588d274cab5a2c1b382cbe86b96d9bab3b959b
result: SUCCESS
```

CI #761 passed:

- Python dependency consistency;
- Python compile;
- Ruff;
- full pytest suite, including 4A-1/4A-2 regressions;
- JavaScript checks;
- Worker tests;
- score-formula tests;
- Portfolio type-check/build;
- Portfolio/Refinery source contracts;
- committed production-asset verification;
- Chromium browser user flow;
- Vercel configuration validation;
- local D1 migrations;
- Cloudflare bundle dry-run.

Because this handoff correction changes the PR head, **CI #761 is evidence for the code candidate but is not the final exact-head merge gate**. The new final candidate must receive a fresh exact-head CI run.

## 7. Independent Review Gate

Required for Batch 4A-2 because risk remains R2.

Preferred independent reviewer:

```text
cchung911
```

Review focus:

- no OOS observations can enter `SelectionEngine`;
- exact Training/PIT accounting is fail-closed;
- selector cannot silently mutate Training data;
- selector/core identity is fully reproducible;
- reference engine is not treated as a production strategy;
- 4A-2 does not duplicate Exhaustive quant authority;
- future-data mutation property is meaningful and deterministic.

Do not mark the batch closed solely from CI. APPROVED + zero blocking review threads are required.

## 8. Recovery / Merge Policy for 4A-2

Before merge:

1. re-query PR #155 head/base and current `main`;
2. verify exact-head CI success;
3. verify independent APPROVED and zero unresolved BLOCKER threads;
4. mark Ready only after those candidate gates are valid;
5. add `release-backup` label;
6. verify the pre-merge backup release points to the exact current `main` SHA;
7. perform final TOCTOU;
8. squash merge using `expected_head_sha`.

After merge:

- verify `main` points to the returned squash SHA;
- verify post-merge recovery release points to the exact new `main`;
- verify main CI;
- verify Vercel status if triggered;
- do not expect or force a Cloudflare production deployment unless changed paths actually match the deploy workflow.

Rollback for Batch 4A-2 is a normal revert of its single squash merge. No DB/persistence migration or destructive state change is introduced.

## 9. Walk-Forward Roadmap

| Batch | Objective | Status |
| --- | --- | --- |
| 4A-1 | Temporal causality firewall + immutable `DecisionSnapshot` | **DONE / PR #154 / post-main verified** |
| 4A-2 | `SelectionEngine` + physical Training/OOS separation | **ACTIVE / PR #155** |
| 4A-3 | Existing Exhaustive adapter + golden parity | **NEXT** |
| 4A-4 | Continuous OOS Portfolio ledger across decisions | PLANNED |
| 4A-5 | PIT resolver/API orchestration | PLANNED |
| 4A-6 | User-facing Walk-Forward UX | PLANNED |
| 4B+ | Research memory / PIT fundamentals / AI automation | BACKLOG until 4A foundation is stable |

### Batch 4A-3 acceptance direction

4A-3 must adapt the **existing** Exhaustive authority rather than reimplementing it.

Required emphasis:

- same deterministic combination enumeration/ranking semantics where applicable;
- same simulation/rebalance/metric authority;
- golden fixtures/parity against current Exhaustive behavior;
- adapter receives Training data only;
- no OOS mutation can alter selection;
- deterministic failure semantics for incomplete candidate history;
- no public UX expansion yet.

## 10. Authority Boundaries

### Market / FX / Research data

Authority remains:

```text
ResearchDatasetV1
TWDHistoryService
existing TWD valuation / corporate-action / FX contracts
```

Do not create a second downloader or duplicate valuation path for Walk-Forward.

### PIT membership

Authority remains Worker/D1 PIT archive and its causality/integrity rules.

Historical research is valid only for dates where archived evidence is causally available. Never fabricate historical membership from today's constituents.

### Exhaustive optimization

Current Exhaustive simulation/metrics/ranking remains authoritative until 4A-3 adapts it behind `SelectionEngine` with parity evidence.

### Portfolio OOS execution

Continuous OOS accounting belongs to 4A-4. Do not create period-local NAV resets and average/stitch them as though they were one investable history.

### Fundamentals

Current fundamentals are not PIT evidence. Walk-Forward historical selection must not use them until a separately governed PIT fundamentals source exists.

## 11. Risk Register

### R1 — Historical PIT availability

Some old dates may lack causally valid archived membership evidence.

Policy: fail closed / shorten the valid research horizon / explicitly disclose availability. Never synthesize history from current membership.

### R2 — Training-history incompleteness

A PIT member can have missing/failed market history.

Policy: preserve explicit `HistoryFailure`; never silently shrink membership. Selection adapters must declare whether partial eligibility is acceptable or fatal.

### R3 — Future-data leakage

Highest Walk-Forward correctness risk.

Policy: structural Training/OOS separation plus mutation property tests, not naming conventions or developer discipline alone.

### R4 — Duplicate quant authority

Reimplementing Exhaustive formulas in Python would create parity drift.

Policy: 4A-3 adapter + golden parity; no second optimizer mathematics in 4A-2.

### R5 — Decision provenance drift

Policy: composite selection-core + engine contract version, exact Training dataset hash, exact PIT provenance/membership and immutable DecisionSnapshot hash.

### R6 — Frozen security/perimeter work

PR #147 is still deferred/frozen. It is not a blocker for current quant/functionality work and must not be opportunistically merged into 4A.

## 12. NOW / NEXT / BACKLOG / REJECT

### NOW

Stabilize and close Batch 4A-2 / PR #155:

```text
final handoff commit
→ exact-head CI
→ independent review
→ Ready
→ recovery backup
→ final TOCTOU
→ squash merge
→ post-main verification
```

### NEXT

Batch 4A-3 — Existing Exhaustive adapter + golden parity.

### BACKLOG

- 4A-4 continuous OOS ledger;
- 4A-5 PIT/API orchestration;
- 4A-6 Walk-Forward UX;
- ResearchRun persistence / research memory;
- PIT fundamentals;
- AI research automation/autopilot;
- scale/performance work after correctness contracts stabilize;
- distributed Refinery rate limiting;
- instrument/security master and regional factor routing;
- traceable theme provider/taxonomy.

### REJECT FOR CURRENT 4A-2

- inventing a new ranking or alpha methodology;
- current-fundamental fallback in historical selection;
- duplicate market-data/FX/universe/metrics authority;
- duplicate Exhaustive mathematics;
- continuous OOS ledger work before 4A-3 parity;
- public API/UI expansion;
- persistence migration for convenience;
- reactivating PR #147;
- unrelated refactors/process optimization.

## 13. Exact Resume Point

When another AI/session resumes:

1. read `AI_PROJECT_PLAYBOOK.md`;
2. read this file;
3. read `docs/research/RESEARCH_DATASET_V1.md`;
4. read `docs/research/WALK_FORWARD_TEMPORAL_CONTRACT_V1.md`;
5. read `docs/research/WALK_FORWARD_SELECTION_CORE_V1.md`;
6. re-query `main`, PR #155, CI/checks, reviews/threads and release state;
7. continue only the current single active batch unless a proven NOW blocker requires expansion.

Expected active state at this checkpoint:

```text
main = 98f0de31b6a59451bbf01ae60384f7265dca30f2
PR #155 = Draft / Batch 4A-2
branch = feat/batch4a2-selection-core
next gate = final exact-head CI after this handoff commit
```

If remote truth differs, remote truth wins and the discrepancy must be analyzed before any merge/rebase/reset operation.
