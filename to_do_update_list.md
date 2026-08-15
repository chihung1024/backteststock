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

Current verified main before Batch 4A-4:

```text
61513aeb0544494416064e66316d5b2a8caf94a2
feat: adapt Exhaustive authority to Walk-Forward selection (#156)
```

Batch 4A-3 / PR #156 is **CLOSED / MERGED / POST-MAIN VERIFIED / PRODUCTION VERIFIED (R2)**.

Verified closure evidence:

- exact-head independent approval before merge;
- protected pre/post merge recovery releases;
- squash merge to `61513aeb0544494416064e66316d5b2a8caf94a2`;
- post-main CI #771 SUCCESS;
- Vercel deployment SUCCESS;
- Cloudflare Worker deployment + remote D1 migration + Russell 2000 / Portfolio v3 / Refinery production smokes SUCCESS.

Batch 4A-1 / PR #154 and Batch 4A-2 / PR #155 are also closed and post-main verified. Closed implementation history belongs to Git/PR/Actions rather than being duplicated here.

## 3. Primary Active Batch

### Batch 4A-4 — Continuous OOS Portfolio Ledger

Status: **ACTIVE / Draft PR #157 / R2 Significant**

Branch:

```text
feat/batch4a4-continuous-oos-ledger
```

Base:

```text
main@61513aeb0544494416064e66316d5b2a8caf94a2
```

PR:

```text
#157 — feat: add continuous Walk-Forward OOS ledger
```

Do not trust a hard-coded candidate head in this file. Re-query PR #157 before review, Ready or merge because this handoff update itself changes the branch head.

## 4. 4A-4 Objective / Architecture Lock

4A-4 converts frozen Walk-Forward decisions plus validated Evaluation datasets into **one continuous investable TWD OOS ledger**.

It must not:

- reset NAV to 1 or initial capital at each Evaluation period;
- average/stitch period-local metrics as though they were one portfolio history;
- create a second portfolio simulator or transaction-cost formula;
- widen Evaluation windows to obtain hidden observations;
- modify PIT, selection, Exhaustive numerical authority, public API, Worker route or UI.

Causal path:

```text
PIT + Training
    ↓
SelectionEngine / existing Exhaustive authority
    ↓
immutable DecisionSnapshot
    ↓
validated Evaluation ResearchDataset
    ↓
existing Portfolio v3 segment ledger authority
    ↓
existing Portfolio v3 rebalance authority at Decision transitions
    ↓
one continuous OOS PortfolioLedger
    ↓
existing Portfolio metric authority
```

Durable semantics: `docs/research/WALK_FORWARD_OOS_LEDGER_V1.md`.

## 5. Quant / Data Authority Invariants

### Decision identity

Every `DecisionSnapshot` hash is revalidated before execution. OOS evidence never mutates the decision or becomes selection evidence.

### Evaluation identity

Every Evaluation dataset must pass `validate_evaluation_dataset()` against its frozen decision. Exact Evaluation dataset hashes are recorded in period audit.

### One Portfolio execution authority

Within each OOS segment, execution delegates to:

```text
apps/api/app/portfolio/ledger.py::simulate_portfolio_ledger()
```

Inter-decision turnover/cost delegates to the same module's existing `_rebalance()` implementation using the prior segment's **actual ending equity/allocation**, not prior target weights.

No research-specific copy of transaction-cost or portfolio-return mathematics is permitted.

### One metric authority

Final metrics are computed once from the combined continuous `PortfolioLedger` through existing `compute_metric_report()`. Period-local metric reports are not aggregated.

### V1 return-component boundary

`ResearchDataset` exposes adjusted/total-return TWD levels, not separate cash distribution components. Therefore 4A-4 v1 requires:

```text
reinvest_distributions = True
cashflow.type = none
leverage.type = none
```

Unsupported state fails closed instead of being reconstructed from incomplete evidence.

Periodic/threshold rebalancing inside an Evaluation segment remains Portfolio v3 authority behavior.

### Initial deployment cost semantics

V1 deliberately preserves existing Portfolio v3 semantics: the **first OOS initial capital allocation is not counted as a rebalance/transition transaction cost**. `transaction_cost_bps` applies to later Decision target transitions and any existing Portfolio v3 in-segment rebalance triggers. A different initial-deployment-cost convention would require a separately versioned contract change.

## 6. Temporal / Gap / Transition Policies

Execution policy:

```text
target-at-first-effective-oos-close-v1
```

The first effective OOS level is the segment execution/baseline close. The first attributed market return is the next effective valuation interval.

Gap policy:

```text
carry-last-audited-state-flat-no-invented-return-v1
```

Evaluation-window gaps do not authorize synthetic market returns. The last audited equity/allocation state is carried flat until the next validated OOS baseline; no hidden row is created.

At a later Decision boundary, target transition cost is represented as a real negative strategy return on the next segment baseline. Example for 100% AAA → 100% BBB, prior equity 110, cost 100 bps:

```text
sell AAA = 110
buy BBB  = 110
traded notional = 220
cost = 2.2
next OOS starting equity = 107.8
```

## 7. Current Implementation Surface

```text
apps/api/app/research/oos_ledger.py
apps/api/app/research/__init__.py
tests/test_walk_forward_oos_ledger.py
tests/test_walk_forward_oos_ledger_parity.py
docs/research/WALK_FORWARD_OOS_LEDGER_V1.md
docs/research/README.md
to_do_update_list.md
```

No Worker/public/migration/package/deployment workflow file is changed by 4A-4.

## 8. Required Regression Locks

Targeted tests currently lock:

1. full sell+buy traded notional and transaction cost for a disjoint target transition;
2. continuous equity and return index across Decision boundaries;
3. no fabricated rows/returns in Evaluation gaps;
4. zero transition turnover when an unchanged 100% target already matches actual ending allocation;
5. exact decision/Evaluation dataset identity in period audit;
6. fail-closed non-reinvested distribution, external-cashflow and leverage requests;
7. at least two effective valuation dates per OOS segment;
8. golden parity: unchanged-target split Walk-Forward ledger equals one ordinary Portfolio v3 ledger over the equivalent TWD level path.

The implementation also enforces:

```text
equity[t] == initial_amount * continuous_return_index[t]
```

within numerical tolerance for supported v1 state.

## 9. Verification Evidence

Pre-handoff candidate:

```text
head = cd93102f4a96455eabeeb835241e915bcac55875
CI #776 = in progress when this handoff commit was prepared
```

Observed before the handoff write:

- dependency install/consistency SUCCESS;
- compile SUCCESS;
- Ruff SUCCESS;
- full Python suite SUCCESS, including 4A-4 targeted and golden-parity tests;
- JavaScript SUCCESS;
- Worker SUCCESS;
- score-formula SUCCESS;
- Portfolio type-check/build SUCCESS;
- Portfolio/Refinery source contracts SUCCESS;
- committed Portfolio production assets SUCCESS;
- browser stages were still completing.

Because this file changes the branch head, **CI #776 is not the final merge gate**. The handoff-updated exact head must receive a fresh complete CI run.

## 10. Self-Review / Convergence Log

### A. Naive period-NAV stitching — REJECTED

Rejected because it loses real prior allocation drift and inter-period turnover cost.

General fix: carry actual ending OOS equity/allocation and apply the next target through existing Portfolio v3 rebalance authority.

### B. Hidden gap-market-return inference — REJECTED

Rejected because Evaluation datasets do not prove market returns outside their requested windows.

General fix: explicit flat audited-state carry policy; no synthetic OOS observations.

### C. Reconstructing non-reinvested distributions from total-return levels — REJECTED

Rejected because ResearchDataset does not preserve the required separate cash-distribution components.

General fix: v1 requires reinvested distributions and fails closed otherwise.

### D. Carrying external cashflow/leverage state by approximation — REJECTED

Rejected because period-local restart could change flow growth/timing, debt interest clocks or margin state.

General fix: 4A-4 v1 disallows these states until a future contract supplies exact continuous component/state evidence.

### E. Split-boundary numerical drift — CONTROLLED BY GOLDEN PARITY

An unchanged 100% target split across two Evaluation segments must equal one existing Portfolio v3 ledger over the equivalent total-return path. This proves segmentation alone does not reset or alter NAV.

## 11. Remaining R2 Gates for PR #157

1. fresh exact-head CI after this handoff commit;
2. self-review of final diff and temporal/quant authority boundaries;
3. independent review on the final exact head;
4. zero unresolved BLOCKER review threads;
5. Ready transition;
6. `release-backup` pre-merge recovery verification against exact current main;
7. final head/base/review/CI/recovery TOCTOU;
8. squash merge using `expected_head_sha`;
9. post-main recovery, CI and deployment-state verification.

Independent-review focus:

- no OOS influence on frozen decisions;
- no period-local NAV reset;
- no duplicate Portfolio/transaction-cost/metric authority;
- transition uses actual ending allocation, not target allocation;
- gap policy does not invent returns;
- unsupported ResearchDataset state fails closed;
- initial-deployment-cost semantics are explicit;
- unchanged-target golden parity holds;
- no public/runtime surface is accidentally expanded.

## 12. Walk-Forward Roadmap

| Batch | Objective | Status |
| --- | --- | --- |
| 4A-1 | Temporal causality firewall + immutable `DecisionSnapshot` | **DONE / PR #154 / post-main verified** |
| 4A-2 | `SelectionEngine` + physical Training/OOS separation | **DONE / PR #155 / post-main verified** |
| 4A-3 | Existing Exhaustive adapter + golden parity | **DONE / PR #156 / production verified** |
| 4A-4 | Continuous OOS Portfolio ledger across decisions | **ACTIVE / PR #157** |
| 4A-5 | PIT resolver/API/job orchestration | **NEXT after 4A-4 closes** |
| 4A-6 | User-facing Walk-Forward UX | PLANNED |
| 4B+ | Research memory / PIT fundamentals / AI automation | BACKLOG until 4A foundation is stable |

## 13. Authority Boundaries / Risk Register

### Market / FX / research data

Authority remains `ResearchDatasetV1`, `TWDHistoryService` and existing TWD valuation/corporate-action/FX contracts. Do not add another downloader or valuation path.

### PIT membership

Authority remains Worker/D1 PIT archive and its causality/integrity rules. Historical research fails closed where causally valid archived membership is unavailable.

### Selection / Exhaustive

Selection remains Batch 4A-2 `SelectionEngine`; existing `public/exhaustive-optimizer-core.js` remains Exhaustive numerical/ranking authority.

### OOS execution

Batch 4A-4 owns continuous OOS orchestration/state carry only. Portfolio math remains Portfolio v3 authority.

### Key active risks

- future-data leakage: controlled by physical Training/OOS separation and immutable decisions;
- period reset bias: controlled by continuous equity/allocation carry and golden parity;
- duplicate quant authority: controlled by direct delegation to existing Portfolio/Exhaustive engines;
- unproven gap returns: controlled by flat carry/no invented observations;
- incomplete return-component state: controlled by fail-closed v1 scope;
- historical PIT/data incompleteness: fail closed, never fabricate;
- PR #147 security/perimeter remains frozen/deferred and is not a 4A blocker.

## 14. NOW / NEXT / BACKLOG / REJECT

### NOW

Close Batch 4A-4 / PR #157:

```text
handoff-updated exact head
→ full CI
→ final self-review
→ independent review
→ Ready
→ recovery backup
→ final TOCTOU
→ squash merge
→ post-main verification
```

### NEXT

Batch 4A-5 — PIT resolver/API/job orchestration around the already-versioned 4A-1…4A-4 internal contracts.

### BACKLOG

- 4A-6 Walk-Forward UX;
- ResearchRun persistence / research memory;
- PIT fundamentals;
- AI research automation/autopilot;
- scale/performance after correctness contracts stabilize.

### REJECT FOR CURRENT 4A-4

- new selection/ranking/alpha methodology;
- Python duplication of Exhaustive or Portfolio mathematics;
- hidden expansion of Evaluation data windows;
- public Walk-Forward API/UI;
- non-reinvested distribution reconstruction;
- cross-period external cashflow/leverage approximation;
- persistence migration for convenience;
- reactivating PR #147;
- unrelated refactors/process expansion.

## 15. Exact Resume Point

On resume:

1. read `AI_PROJECT_PLAYBOOK.md` and this file;
2. read `RESEARCH_DATASET_V1.md`, `WALK_FORWARD_TEMPORAL_CONTRACT_V1.md`, `WALK_FORWARD_SELECTION_CORE_V1.md`, `WALK_FORWARD_EXHAUSTIVE_ADAPTER_V1.md`, and `WALK_FORWARD_OOS_LEDGER_V1.md`;
3. re-query current `main`, PR #157, exact-head CI, reviews/threads and release state;
4. continue only Batch 4A-4 until its R2 gates close.

Expected state immediately after this handoff commit:

```text
main = 61513aeb0544494416064e66316d5b2a8caf94a2
PR #157 = Draft / Batch 4A-4
branch = feat/batch4a4-continuous-oos-ledger
next gate = fresh exact-head full CI
```

If remote truth differs, remote truth wins and the discrepancy must be analyzed before merge/rebase/reset.
