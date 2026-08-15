# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff. Mutable GitHub / CI / Vercel / Cloudflare / runtime truth must be re-queried before important writes. Durable methodology belongs in versioned contracts under `docs/`. Closed execution history must remain in this handoff or an explicit archived section; Git/PR/Actions are supporting evidence, not a substitute for preserving project decisions.

Last updated: **2026-08-16**

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

Primary product contract:

```text
sum(asset weights) < 100%  -> residual cash
sum(asset weights) = 100%  -> fully invested
sum(asset weights) > 100%  -> financed gross exposure
```

The user-confirmed execution semantic is:

- each Portfolio column has its **own** target gross exposure derived from its entered total percentage;
- `VT 200%` means that Portfolio targets 200% gross exposure;
- `QQQ 100%` means that separate Portfolio is unlevered and follows only its configured allocation-rebalance policy;
- `USD 50%` means that separate Portfolio holds 50% asset exposure plus 50% residual ledger cash;
- any non-100% Portfolio resets **total gross exposure** to its own target at each close;
- a pure daily gross reset preserves the Portfolio's current internal asset mix;
- internal asset weights are restored to their original target mix only when the configured periodic/drift-threshold asset-allocation rebalance independently fires;
- if allocation rebalance and gross reset coincide, one consistent ledger trade restores both target mix and target gross, with no duplicate trade;
- no `daily return × leverage` shortcut is permitted.

Example locked by user confirmation:

```text
VT 100% + QQQ 50% => 150% target gross exposure
```

Daily close reset restores total gross to 150%, but VT/QQQ may drift relative to each other until the configured allocation rebalance fires.

## 4. Master Plan / Batch Boundaries

### L1 — Ledger Authority

Status: **DONE foundation / original exact-head CI + Vercel preview verified at `3b4d7fea90bb2298d89f62f9a0d4fe0c886cb9cc`; narrowly reopened and corrected during L2 after the user clarified underinvested daily-reset semantics.**

Locked:

- weight-defined residual cash and gross exposure;
- daily close gross-exposure reset inside the existing Portfolio v3 ledger;
- debt/cash/interest/transaction-cost/reset-trade accounting;
- gross/net exposure diagnostics;
- liquidation/invalid-initial-margin guards;
- 100% no-leverage compatibility;
- Walk-Forward OOS continues to use the same Portfolio ledger authority.

### L2 — API Contract

Status: **FINAL CANDIDATE / implementation + targeted/full Python regression verified; final user-authored exact-head CI/Vercel pending**.

Implemented:

- public Portfolio asset-weight totals may be below/equal/above 100% within the Portfolio domain gross-exposure bound;
- API upper-bound admission derives from `MAX_TARGET_GROSS_EXPOSURE` and domain tolerance rather than a second hard-coded 500% authority;
- existing 100% requests remain valid;
- non-100% weight-defined exposure combined with explicit legacy leverage fails closed as ambiguous;
- result serialization exposes existing L1 ledger cash/debt/gross/net exposure ratios, target gross/cash/mix and exposure-reset count without reimplementing calculations;
- route/model/service regressions cover 80%, 100%, 150%, >domain-limit rejection and ambiguous legacy leverage behavior.

Verification record:

- initial L2 candidate source + targeted API tests + full Python regression passed before publish;
- an obsolete route regression still expected a 90% Portfolio to return 422; this was correctly replaced with >domain-limit rejection plus route-level 80%/150% acceptance and ambiguous-leverage rejection;
- L2 self-review found hard-coded `500%` duplicated the domain authority; the repair now imports/derives from `MAX_TARGET_GROSS_EXPOSURE`;
- the final domain-authority repair workflow passed source patch, compile, ruff, targeted API tests and full Python regression and atomically removed both temporary L2 verifier workflows;
- bot-authored product head after that repair was `349dcd81d6a1202e8a4d3a1bcb0c4aa4d0423680`; standard CI on that bot-authored head reported `action_required` because no job was allowed to start under the actor policy, not because of a test failure;
- user clarification exposed a real underinvested correctness blocker: the initial L1 policy reset only >100% targets daily; <100% targets merely started with residual cash and then drifted;
- the underinvested repair now resets every non-100% target at each close, preserves current internal asset mix, recomputes cash from post-cost equity, and leaves periodic/threshold rules as the only authority that restores target internal mix; focused + full Python regression passed before publish;
- the unreleased event/result contract was generalized to `exposure_reset` / `exposure_reset_count` so 50% cash and 150% leverage share one truthful name; focused + full Python regression passed before publish;
- canonical `docs/PORTFOLIO_V3_CONTRACT.md` has been updated with the opened API contract and the user-confirmed gross-reset/internal-mix semantics;
- the final user-authored L2 candidate must still pass formal exact-head full-repository CI and Vercel preview before L2 is marked DONE.

### L3 — UX

Status: **PLANNING ONLY / do not write until user confirms final UI details and L2 closes**.

Required UX direction already established:

- percentage cells become the direct leverage/cash control;
- each Portfolio's total percentage is its own target gross exposure;
- individual asset entries must no longer be capped at 100%; the Portfolio domain cap remains the sole gross-exposure authority;
- non-100% totals must not be shown as invalid merely because they differ from 100%; they should be described as cash / fully invested / leveraged exposure;
- remove or demote the global `fixed_ratio` leverage selector from the normal user flow so it cannot imply one common leverage ratio across all Portfolios;
- keep legacy leverage only as compatibility behavior, not the primary new UI authority;
- show that daily gross reset is automatic for non-100% totals, while internal allocation rebalance follows the user's periodic/threshold settings;
- preserve responsive desktop/mobile Portfolio editing and existing 100% flows.

Do not start L3 source writes until L2 exact-head verification is complete and the final UI change list has been presented to the user for confirmation.

## 5. L1 Locked Ledger Semantics

1. Portfolio weights are equity-relative target exposures, with current domain gross bound `(0, 500%]`.
2. `target_allocation` preserves raw user-entered exposure weights.
3. `target_asset_mix` is normalized asset-only composition.
4. Weight total below 100% creates ledger cash; it is not a synthetic cash-price series.
5. Weight total above 100% creates ledger debt and a target gross exposure ratio.
6. Non-100% gross exposure resets at every close after returns/distributions/interest/flows and before final state recording.
7. A pure gross reset preserves current asset mix unless an independently configured allocation rebalance fires on that close.
8. Periodic/threshold allocation rebalance restores target asset mix and target gross in one ledger trade; no redundant gross-reset trade follows.
9. Allocation-threshold checks normalized internal asset mix for non-100% Portfolios; gross/cash drift is handled by the independent daily exposure reset and cannot by itself trigger internal rebalancing.
10. Underinvested daily reset recomputes target asset gross and residual cash from post-cost equity and does not create debt merely to preserve a stale cash amount.
11. Reset/rebalance transaction costs are solved against post-cost equity through the ledger; no leveraged-return multiplication approximation is allowed.
12. Borrowing interest remains explicit ledger cost.
13. Existing fixed-ratio leverage routes through the same daily-reset authority.
14. Fixed-debt remains explicit/separate.
15. Non-100% weight-defined exposure plus explicit legacy leverage fails closed as ambiguous.
16. Existing 100% / no-leverage Portfolio behavior remains the compatibility baseline.
17. Initial leveraged states must satisfy the configured maintenance-margin guard before day-zero state is recorded.
18. Existing direct `PortfolioLedger(...)` construction and Walk-Forward OOS `_rebalance(..., target_weights, ...)` remain compatible adapters into the same Portfolio authority.

## 6. L1 Root-Cause / Verification Record

The initial published L1 candidate passed **20/20 targeted ledger tests**. Broad CI later exposed two integration compatibility failures: new ledger diagnostic fields had become required constructor arguments, and `_rebalance` no longer accepted the established Walk-Forward target-weight vector. The permanent repair kept diagnostics derivable/optional and preserved the weight-vector adapter into the same `ExposurePolicy` authority; Walk-Forward was not modified to duplicate Portfolio math.

Self-review also found that 5x exposure with the default 25% maintenance margin is invalid at inception. Initial states now pass the same margin/non-positive-equity guard before day zero is recorded. 3x with 25% remains admissible; 5x with 25% fails honestly.

Final L1 exact-head CI #834 and Vercel preview both succeeded.

During L2 product review, the user clarified that a 50% Portfolio must also reset total exposure to 50% at every close, not merely start with 50% cash. This reopened one narrow L1 policy edge. Evidence showed `_exposure_policy()` only assigned `daily_reset_ratio` above 100%, so underinvested Portfolios drifted after inception. Root-cause repair now assigns the daily reset to every non-100% weight-defined exposure (excluding legacy fixed-debt), solves underinvested target cash from post-cost equity with zero debt, and lets allocation thresholds inspect normalized internal asset mix only. The correction passed focused plus full Python regression before atomic publish at product head `6849140495ed4eef8dfaafec0fa265f1659bbff9`.

Because the same reset now applies to both cash and leveraged Portfolios, the unreleased public/ledger naming was generalized from `leverage_reset` / `leverage_reset_count` to `exposure_reset` / `exposure_reset_count`. That contract-only rename also passed focused plus full Python regression before atomic publish at `16855490bfef000e76ea7cc2d39e0e638d6cf579`.

## 7. Current Public Product Boundary

At the L2 final candidate:

- Portfolio API admission supports below/equal/above 100% weight-defined exposure within the domain bound;
- API serializer exposes ledger exposure truth directly;
- browser Allocation Editor still has the old 100%-only UX validation and per-cell 100% cap;
- browser Settings still exposes the old global leverage selector;
- therefore the new behavior is **not yet a complete user-facing feature** until L3 is implemented and verified;
- production main remains unchanged at `e93e3ba51...` until PR #162 completes R3 review/merge gates.

## 8. NOW / NEXT / BACKLOG / REJECT

### NOW

Close L2 only:

```text
user-authored final candidate
→ full repository CI
→ Vercel preview
→ self-review exact diff
→ L2 DONE only if all gates pass
```

### NEXT

Present the final L3 UI change list for user confirmation, then implement only the leverage/cash UX if authorized.

### AFTER L3

Perform R3 final review, pre-merge recovery, exact-head independent review, squash merge, post-main recovery, main CI, Vercel production and live Portfolio production regression for representative 50% / 100% / 150%+ cases.

### BACKLOG

- Batch 4A-6 Walk-Forward user-facing UX;
- ResearchRun / research memory;
- PIT fundamentals / large-universe causal narrowing;
- AI research automation/autopilot;
- distributed scale/performance after correctness contracts stabilize.

### REJECT FOR CURRENT FEATURE

- `daily return × leverage` approximation;
- one global leverage multiplier as the new Portfolio UX authority;
- daily forced restoration of every asset's raw target weight when only gross reset is due;
- a second Portfolio performance engine;
- a second leverage state outside Portfolio v3 ledger;
- unrelated refactors;
- reactivating frozen PR #147.

## 9. Risks / Reopen Conditions

Reopen the ledger/API design if evidence shows any of:

- 100% no-leverage parity regression;
- cash/debt accounting identity failure;
- target gross exposure not restored after required daily reset;
- pure reset changes internal asset mix without allocation rebalance;
- allocation threshold fires solely because gross exposure drifted;
- transaction cost is excluded from post-cost equity target solving;
- margin/liquidation ordering creates an impossible state;
- Walk-Forward OOS parity/shared-ledger integration regresses;
- API or browser begins maintaining a second exposure-limit/leverage authority.

## 10. Exact Resume Point

On resume:

1. read `AI_PROJECT_PLAYBOOK.md`, `README.md`, this file and `docs/PORTFOLIO_V3_CONTRACT.md`;
2. re-query main, PR #162, exact branch head, CI/Vercel and review state;
3. verify production main is still `e93e3ba51...` or analyze divergence before important writes;
4. treat the corrected L1 ledger semantics as locked unless new correctness evidence reopens them;
5. finish L2 exact-head formal verification;
6. do not write L3 UX until its final change list has been presented to the user and authorized;
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
