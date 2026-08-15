# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff. Mutable GitHub / CI / Vercel / Cloudflare / runtime truth must be re-queried before important writes. Durable methodology belongs in versioned contracts under `docs/`. Closed execution history must remain in this handoff or an explicit archived section; Git/PR/Actions are supporting evidence, not a substitute for preserving project decisions.

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

Functionality, quantitative correctness, data integrity, causal validity and user experience outrank optional infrastructure/process work.

## 2. Verified Production Baseline

Current production main before the active Portfolio exposure feature:

```text
main@e93e3ba51fa6b082ccc5b6adbf446f3b3268728a
fix: enforce current-instrument listing-date causality (#161)
```

P0 pre-inception/ticker-reuse correctness incident is **CLOSED / MERGED / POST-MAIN VERIFIED / PRODUCTION VERIFIED**.

Closure evidence:

- PR #161 exact-head independent approval and squash merge completed;
- post-merge recovery release `backup-post-pr161-e93e3ba51fa6` targets exact main;
- main CI #822 SUCCESS;
- Vercel production deployment is bound to exact main `e93e3ba51...` and succeeded;
- real production VFLO regression requested history beginning in 2016 but returned first Portfolio observation and effective metric start on **2023-06-22**, matching the verified current-instrument first-trade boundary;
- the production regression contained 808 observations and no pre-inception rows;
- Cloudflare Walk-Forward health simultaneously reported `status=ok` and deployment SHA `e93e3ba51...`.

Do not reopen P0 unless new runtime evidence shows lifecycle leakage or an identity-boundary regression.

## 3. Primary Active Work — Portfolio Weight-Defined Exposure

Status: **ACTIVE / Draft PR #162 / R3 Portfolio-calculation change**

Branch:

```text
feat/portfolio-weight-defined-exposure
```

Base:

```text
main@e93e3ba51fa6b082ccc5b6adbf446f3b3268728a
```

PR:

```text
#162 — feat: add weight-defined Portfolio exposure semantics
```

Do not trust a hard-coded candidate head in this file. Re-query PR #162 before important writes/reviews because verification and docs may advance the branch head.

Primary product contract:

```text
sum(asset weights) < 100%  -> residual cash
sum(asset weights) = 100%  -> fully invested
sum(asset weights) > 100%  -> financed gross exposure
```

For gross exposure above 100%, the Portfolio v3 ledger must reset target gross exposure at each close. This is separate from asset-allocation rebalance, which continues to follow periodic/threshold policy.

No `daily return × leverage` shortcut is permitted.

## 4. Master Plan / Batch Boundaries

### L1 — Ledger Authority

Status: **IMPLEMENTED / targeted + full Python regression verified / final exact-head full repository CI still required**.

In scope:

- weight-defined residual cash and gross exposure;
- daily close leverage reset inside the existing Portfolio v3 ledger;
- debt/cash/interest/transaction-cost/reset-trade accounting;
- gross/net exposure diagnostics;
- liquidation/invalid-initial-margin guards;
- preserve existing 100% no-leverage behavior;
- preserve Walk-Forward OOS use of the same Portfolio ledger authority.

Out of scope:

- public API admission changes;
- browser/UI changes;
- new Portfolio performance engine;
- PIT/Exhaustive/Walk-Forward methodology changes.

### L2 — API Contract

Status: **NEXT after L1 exact-head gates close**.

Objective:

- allow public Portfolio asset-weight totals below/above 100% within the domain bound;
- expose ledger cash/debt/gross/net/reset truth through the existing API result;
- define compatibility/deprecation behavior for the legacy explicit leverage schema without creating two active leverage authorities.

### L3 — UX

Status: **DEFERRED until L2**.

Objective:

- let the user enter/display residual cash and gross leverage directly from weights;
- clearly distinguish asset-allocation rebalance from daily leverage reset;
- remove ambiguous duplicate leverage controls;
- keep responsive Portfolio user flows and existing 100% portfolios unchanged.

## 5. L1 Locked Ledger Semantics

1. Portfolio weights are equity-relative target exposures, with current domain gross bound `(0, 500%]`.
2. `target_allocation` preserves the raw user-entered exposure weights.
3. `target_asset_mix` is the normalized asset-only composition.
4. Weight total below 100% creates ledger cash; it is not represented by a synthetic cash-price series.
5. Weight total above 100% creates ledger debt and a target gross exposure ratio.
6. Leveraged gross exposure resets at every close after returns/distributions/interest/flows and before final state recording.
7. A leverage reset preserves the current asset mix unless an independently configured allocation rebalance fires on that close.
8. Periodic/threshold allocation rebalance restores target asset mix and target gross in one ledger trade; it must not be followed by a redundant leverage-reset trade.
9. Leveraged allocation-threshold checks normalized asset mix, so gross-exposure drift alone cannot masquerade as allocation drift.
10. Underinvested allocation-threshold semantics include intentional residual cash.
11. Reset/rebalance transaction costs are solved against post-cost equity through the ledger; no leveraged-return multiplication approximation is allowed.
12. Borrowing interest remains explicit ledger cost.
13. Existing fixed-ratio leverage routes through the same daily-reset authority.
14. Fixed-debt remains explicit/separate.
15. Non-100% weight-defined exposure plus an explicit legacy leverage overlay fails closed as ambiguous.
16. Existing 100% / no-leverage Portfolio behavior remains the compatibility baseline.
17. Initial leveraged states must already satisfy the configured maintenance-margin guard. For example, 3x with a 25% maintenance margin is admissible, while 5x with a 25% maintenance margin is rejected before a fictitious initial state can be recorded.
18. Existing direct `PortfolioLedger(...)` construction and Walk-Forward OOS `_rebalance(..., target_weights, ...)` integration remain compatible adapters into the same Portfolio authority.

Current ledger diagnostics include:

- cash;
- debt;
- gross exposure;
- net exposure;
- gross exposure ratio;
- net exposure ratio;
- target gross exposure ratio;
- target cash allocation;
- target asset mix;
- leverage reset count/events.

## 6. L1 Root-Cause / Verification Record

### A. Targeted implementation gate

The implementation candidate was kept off the feature ref until exact source hashes, compile and focused ledger regressions passed. The initial published L1 candidate passed **20/20 targeted ledger tests**.

A test fixture originally expected a 5% threshold rebalance after one leg of a 50/50 portfolio rose 20%. Evidence showed normalized allocation only moved to 54.545%/45.455%, i.e. 4.545 percentage points of drift. The fixture was corrected to 4%; production logic was not changed for this failure.

### B. Broad-regression integration failure

First formal PR CI after L1 implementation produced **8 Python failures** while compile/lint and targeted math were otherwise valid.

Root causes:

1. new `PortfolioLedger` diagnostic fields were made required constructor arguments, breaking existing quant fixtures and Walk-Forward OOS direct construction;
2. `_rebalance` had changed its established input from a target-weight vector to `ExposurePolicy`, while Walk-Forward OOS intentionally consumes that shared helper.

Permanent fix:

- preserve the established constructor prefix and make new diagnostics optional/derivable from existing ledger truth;
- accept the existing weight-vector `_rebalance` adapter and immediately convert it into the same `ExposurePolicy` authority;
- do **not** modify Walk-Forward OOS to duplicate calculations.

The repair passed compile, ruff and the full Python regression before commit.

### C. Initial-margin self-review blocker

Self-review found that a 5x initial target with the default 25% maintenance margin has only 20% equity/gross, yet the previous flow would not evaluate margin until the next valuation date.

Permanent fix:

- validate the initial target state through the same liquidation guard before recording day zero;
- apply the guard to weight-defined/fixed-ratio and fixed-debt states;
- fail honestly for an invalid initial configuration instead of emitting a temporarily invalid ledger state.

Targeted and full Python regression passed before this repair was committed.

### D. Validation-workflow noise

Temporary GitHub Actions assemblers were used only to keep large multi-file candidates off the feature ref until source-hash and regression gates passed. Several candidate-generation runs stopped before product commits because whitespace-sensitive or transport guards were too strict. These were tooling/verification noise, not product failures; permanent source changes were never published from a failed runner.

## 7. L1 Current Verification State

Verified so far:

- exact candidate source/hash validation before initial publish;
- targeted ledger regression 20/20 on initial L1 candidate;
- integration repair: compile + ruff + full Python regression SUCCESS before commit;
- initial-margin repair: targeted + full Python regression SUCCESS before commit;
- current branch contains no intended temporary verification workflow in the final product diff after each verified repair commit.

Still required before L1 may be marked DONE:

1. durable `docs/PORTFOLIO_V3_CONTRACT.md` update;
2. user-authored final exact head;
3. formal full repository CI SUCCESS on that exact head;
4. Vercel preview SUCCESS on that exact head;
5. final diff/self-review with no L1 BLOCKER;
6. confirm main/base has not moved incompatibly.

L1 completion does **not** authorize merge of PR #162. The PR remains Draft while L2/L3 are unfinished.

## 8. Current Public Product Boundary

Until L2/L3 are completed:

- public Portfolio API still enforces the existing approximately-100% weight contract;
- browser Allocation Editor still treats non-100% totals as invalid and currently caps each weight at 100%;
- therefore L1 is an internal ledger-authority foundation and is not yet a user-visible feature;
- production main remains unchanged at `e93e3ba51...`.

This staged boundary is intentional so each batch remains usable and independently rollbackable.

## 9. NOW / NEXT / BACKLOG / REJECT

### NOW

Close L1 only:

```text
durable Portfolio contract + handoff
→ final exact-head full CI + Vercel preview
→ final L1 self-review
→ mark L1 DONE
```

### NEXT

L2 API Contract, then L3 UX.

### AFTER L3

Perform R3 final review/recovery/merge/post-main production verification for PR #162. Only then resume the broader product roadmap.

### BACKLOG

- Batch 4A-6 Walk-Forward user-facing UX;
- ResearchRun / research memory;
- PIT fundamentals / large-universe causal narrowing;
- AI research automation/autopilot;
- distributed scale/performance after correctness contracts stabilize.

### REJECT FOR CURRENT L1

- `daily return × leverage` approximation;
- a second Portfolio performance engine;
- a second leverage state outside Portfolio v3 ledger;
- mixing L2 API or L3 UI work into L1 before its gates close;
- unrelated refactors;
- reactivating frozen PR #147.

## 10. Risks / Reopen Conditions

Reopen L1 design if evidence shows any of:

- 100% no-leverage parity regression;
- cash/debt accounting identity failure;
- target gross exposure not restored after a leverage reset;
- reset changes asset mix when allocation rebalance did not fire;
- allocation threshold fires solely because gross exposure drifted;
- transaction cost is not included in post-cost equity target solving;
- margin/liquidation ordering creates an impossible state;
- Walk-Forward OOS parity or shared-ledger integration regresses;
- API implementation in L2 cannot represent the L1 truth without duplicating authority.

## 11. Exact Resume Point

On resume:

1. read `AI_PROJECT_PLAYBOOK.md`, `README.md`, this file and `docs/PORTFOLIO_V3_CONTRACT.md`;
2. re-query main, PR #162, exact branch head, CI/Vercel and open review state;
3. verify production main is still the last known good `e93e3ba51...` or analyze any divergence before rebasing;
4. finish L1 exact-head gates only;
5. after L1 is explicitly DONE, start L2 API Contract;
6. do not start L3 UX until L2 is verified;
7. preserve the historical appendix below when updating this file.

---

# Historical Execution Record — Batch 4A-5

> The following record is intentionally retained from the pre-P0 handoff so a new session does not lose the architecture, rejected alternatives, resource bounds, regression locks, or runtime decisions that produced the current Walk-Forward baseline. Status text in this appendix is historical; Section 2 above is the current truth.

## H1. 4A-5 Objective / Architecture Lock

4A-5 made the already-versioned 4A-1…4A-4 research pipeline callable as one bounded server workflow without creating a new quant/data authority.

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

Primary invariant:

```text
Training data <= Decision point < Evaluation/OOS data
```

## H2. 4A-5 Authority Boundaries

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

## H3. Public V1 Methodology Lock

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

## H4. Resource / Large-Universe Admission

Synchronous v1 bounds established in 4A-5:

```text
periods <= 24
PIT candidates <= 100
holdingCount <= 20
Exhaustive combinations <= 500,000 per period
Exhaustive combinations <= 2,000,000 per job
public request body <= 128 KiB
Exhaustive authority wire body <= 3 MiB
Exhaustive authority decoded JSON <= 16 MiB
large authority payloads use deterministic gzip transport
```

If PIT membership exceeds 100 symbols, fail closed.

Explicitly rejected shortcuts:

- first-100 truncation;
- current-fundamental historical prefilter;
- current-constituent ranking used as PIT evidence;
- silent history-failure candidate drop.

Large-universe historical narrowing belongs to future PIT-fundamentals work after it has causal evidence.

## H5. 4A-5 Implementation Surface

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
tests/test_exhaustive_authority_http_client.py
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

## H6. Production Topology / Hardening

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

Hardening decisions retained from 4A-5:

- no-store/security headers;
- strict request schemas/body limits;
- edge/backend research rate limits;
- exact deployment-SHA binding for Python→Node authority calls;
- bounded Node combination count;
- deterministic gzip transport for large Training matrices with independent wire/decoded ceilings;
- optional `WALK_FORWARD_INTERNAL_SECRET` or existing Vercel Automation Bypass secret upgrades selection admission to secret + deployment binding;
- honest bounded fallback if no secret is configured;
- production smoke waits for Node authority and Worker-routed API health to report the expected deployment SHA.

A secret is hardening, not a PIT/quant authority and is not required to preserve research causality.

## H7. 4A-5 Regression Locks

Tests established during 4A-5 lock at least:

1. exact Worker PIT response/provenance parsing;
2. noncausal/date-mismatched PIT rejection;
3. proxy truth preservation and public rejection;
4. exact operation order PIT → Training → selection → Evaluation;
5. one shared Training fetch for candidates + benchmark;
6. Evaluation fetch only after DecisionSnapshot;
7. >100-member PIT fail-closed behavior without market-data work;
8. strict public API schema rejecting unversioned strategy knobs;
9. health bypassing research-work quota;
10. Vercel Node raw/pre-parsed/gzip body compatibility;
11. optional internal-secret admission;
12. Node Exhaustive combination budget;
13. independent authority wire/decoded payload ceilings and non-finite JSON rejection;
14. same-origin edge route body/header sanitation and limits;
15. deployment-SHA readiness smoke syntax;
16. full repository CI/regression gates.

## H8. 4A-5 Self-Review / Root-Cause Record

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

### G. Large Training matrix HTTP payload — FIXED SYSTEMICALLY

4A-3 authority payload contains daily TWD price matrices, so a long Training window with many PIT candidates can exceed a small raw JSON request limit even when candidate/combination admission is otherwise valid.

Root-cause fix: retain the exact same authority JSON semantics but gzip large Python→Node payloads. Keep an independent 3 MiB compressed-wire ceiling and 16 MiB decoded-JSON ceiling; reject unsupported encodings and non-finite JSON before numerical work. Do not shorten historical windows merely to fit transport.

## H9. Historical P0 Incident Definition Preserved from 4A-5 Handoff

The pre-P0 handoff explicitly required investigation across:

```text
raw market-data response
→ ticker/symbol resolution
→ TWDHistoryService / legacy history loaders
→ alignment / fill / fallback logic
→ ResearchDataset
→ backtest/portfolio engines
→ frontend chart serialization/rendering
```

It also locked these acceptance rules before implementation began:

1. determine the instrument's actual first tradable observation from authoritative raw history; do not hard-code VFLO dates as the fix;
2. no forward-fill/backfill/benchmark/substitute/synthetic series may create an instrument observation before its first genuine market observation;
3. alignment may create `NaN`/unavailable state before inception, never a fabricated price;
4. portfolio math must define explicit pre-inception availability semantics instead of silently treating synthetic prices as investable history;
5. requested-period UX must disclose effective common start / unavailable assets when history begins later than the requested date;
6. add systemic regression fixtures for multiple recent-listing instruments plus ordinary long-history controls;
7. audit all download/cache/fallback paths for the same defect class, not only VFLO.

Those constraints remain the reason PR #161 is treated as P0 / R2 and are not superseded by the shorter current-status sections above.
