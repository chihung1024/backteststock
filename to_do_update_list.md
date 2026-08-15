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

Functionality, quantitative correctness, data integrity and user experience outrank optional infrastructure/process work.

## 2. Verified Main Baseline

Current remote baseline before the active P0 fix:

```text
main@b260a50fcbdf71fafa1d3d3c8e1b11bf5b4d7156
ci: verify Walk-Forward production after Vercel changes (#160)
```

Walk-Forward foundation is closed through 4A-5:

| Batch | Result |
| --- | --- |
| 4A-1 | Temporal causality firewall + immutable DecisionSnapshot — DONE / PR #154 |
| 4A-2 | SelectionEngine + physical Training/OOS separation — DONE / PR #155 |
| 4A-3 | Existing JavaScript Exhaustive adapter + golden parity — DONE / PR #156 |
| 4A-4 | Continuous OOS Portfolio ledger — DONE / PR #157 |
| 4A-5 | PIT Resolver / API / Job Orchestration — DONE / PR #158 plus runtime closure PR #159 and production-verification PR #160 |

4A-5 final production evidence on `main@b260a50f...`:

- post-main recovery release exists;
- main CI #810 SUCCESS;
- Vercel production points to the exact main SHA;
- `Verify Walk-Forward Production` executed the existing real production smoke against the exact deployment and returned `status=ok`;
- existing production Worker routed successfully to the deployment-bound Exhaustive authority;
- no Cloudflare runtime code change was required merely to verify a Vercel-only authority change.

Do not reopen 4A-5 unless new evidence shows a regression.

## 3. Primary Active Work — P0 Correctness

### Pre-inception / ticker-reuse history leakage

Status: **ACTIVE / Draft PR #161 / R2 P0 correctness**

Branch:

```text
fix/p0-listing-date-causality
```

Base:

```text
main@b260a50fcbdf71fafa1d3d3c8e1b11bf5b4d7156
```

PR:

```text
#161 — fix: enforce current-instrument listing-date causality
```

Do not trust a hard-coded candidate head in this file. Re-query PR #161 before review, Ready or merge because tests/docs may advance the branch head.

Durable contract update:

```text
docs/UNIFIED_TWD_CONTRACT.md
```

## 4. User-visible Reproduction / External Truth

The incident was reproduced conceptually with `VFLO`:

- the current VictoryShares Free Cash Flow ETF is a June 2023 product;
- the current Yahoo instrument lifecycle boundary used by this regression is **2023-06-22**;
- a backtest request starting in 2016 could nevertheless show VFLO performance before the current ETF existed.

The fix must never hard-code VFLO. VFLO is a regression example for the general ticker-reuse/history-stitching defect class.

## 5. Root Cause — LOCKED

The frontend is not fabricating history:

- `ResultsDashboard` renders backend `result.series[{date,value}]` directly;
- Portfolio API serialization uses the ledger index directly;
- TWD valuation never backward-fills a later native price into an earlier date;
- FX union-calendar logic begins only after an actual native observation exists.

Therefore the false pre-inception history already existed in the native Yahoo adjusted-close series before TWD valuation.

Root cause:

> **The authoritative market-data boundary verified that a ticker had real prices and corporate-action evidence, but did not verify that those rows belonged to the instrument currently represented by that ticker.**

Ticker text is not instrument identity. A ticker can be reused or Yahoo can stitch history across an instrument change. Existing code even documented `ticker_or_exchange_change_history_stitching` as a corporate-action limitation, but no lifecycle guard prevented those rows from entering Scanner / Portfolio / Research / Exhaustive calculations.

## 6. P0 Fix Contract

New versioned identity authority:

```text
INSTRUMENT_IDENTITY_CONTRACT_VERSION = yahoo-first-trade-date-2026-08-15.1
source = yahoo_history_metadata.firstTradeDate
```

Required invariants:

1. current Yahoo `firstTradeDate` must be verified before ticker-keyed history is usable;
2. all adjusted-close rows before that date are removed;
3. Raw Close, dividends, capital gains, stock splits and repair flags are clipped to the same boundary;
4. corporate-action audit is rebuilt after clipping;
5. identity audit records first-trade date, original/effective first dates, removed row count and clipping status;
6. metadata failure is **fail closed / retryable** — never `audit=unverified` while still calculating a performance result;
7. an entirely pre-inception requested window returns no usable current-instrument series;
8. market-data cache identity includes the new contract version, so pre-fix cached histories are not reused;
9. no UI patch, benchmark substitution, synthetic proxy or hard-coded instrument date may satisfy this contract.

Implementation surface is intentionally narrow:

```text
api/instrument_identity.py
api/market_data.py
tests/test_instrument_identity.py
docs/UNIFIED_TWD_CONTRACT.md
to_do_update_list.md
```

No quant formulas, Portfolio ledger math, PIT resolver, Walk-Forward selector/OOS semantics, Worker routing or leverage behavior are changed.

## 7. Why Shared `api.market_data` Is the Correct Boundary

Production compatibility backtest in `api/index_v2.py`, `TWDHistoryService`, Scanner/Portfolio services, ResearchDataset and Exhaustive preparation already converge on the shared audited market-data path.

Fixing only Portfolio v3 or only the chart would leave the same defect available to other research consumers. The guard therefore runs before TWD valuation and before return/portfolio metrics.

The historical legacy downloader retained in `api/index.py` is not the production backtest authority; `api/index_v2.py` replaces the production backtest handler and delegates market data to `api.market_data`. Do not expand this P0 into an unrelated legacy refactor unless remote runtime truth shows an active affected path.

Existing downstream regression also locks the alignment rule: a later-starting asset is never backward-filled into an earlier common portfolio date. Portfolio v3 starts from the common genuinely available interval; it does not need a second lifecycle authority.

## 8. Regression Locks Added

Targeted tests cover:

1. Yahoo `firstTradeDate` parsing from epoch seconds, milliseconds and ISO dates;
2. simultaneous clipping of adjusted price and time-indexed component attrs;
3. VFLO-class ticker-reuse rows removed before downstream use;
4. corporate-action event counts rebuilt after pre-inception event removal;
5. market-data frame audit preserves the verified identity boundary;
6. unverifiable identity metadata fails closed instead of producing results;
7. an entirely pre-inception window returns no usable current-instrument history;
8. a batched multi-instrument fixture enforces distinct lifecycle boundaries while an ordinary long-history control remains unchanged;
9. existing TWD backtest regression confirms a later-starting asset cannot be backward-filled before its first observation.

Full repository CI remains authoritative for cross-system regression.

## 9. Current Verification State

Current candidate work has passed targeted compile/lint/Python tests during exact-head CI after the systemic regression expansion. The final exact head still requires all R2 gates to finish before merge.

Required gates:

1. full repository CI SUCCESS;
2. Vercel preview SUCCESS;
3. final diff self-review / no BLOCKER;
4. independent review on the exact final head;
5. zero unresolved BLOCKER threads;
6. pre-merge recovery against exact current main;
7. squash merge with exact expected head;
8. post-main backup + main CI + Vercel production;
9. production regression proving a 2016-requested VFLO path/effective history cannot begin before the current instrument's verified first-trade boundary.

Recovery status:

```text
backup-pre-pr161-b260a50fcbdf
→ target_commitish = b260a50fcbdf71fafa1d3d3c8e1b11bf5b4d7156
→ verified by Release Backup Gates
```

## 10. Performance / Reliability Constraints

The identity resolver must not turn a 100-symbol scan into unbounded serial metadata work.

Current design:

- bounded concurrent resolver workers;
- two metadata attempts per uncached symbol;
- successful identity evidence cached for six hours;
- metadata failures cached only briefly (30 seconds) to suppress duplicate lookups inside a finite retry cycle without creating a multi-hour outage;
- market-data download retry remains finite.

Do not trade correctness for speed by silently accepting unverified ticker-only history. If later profiling shows unacceptable latency, optimize the metadata acquisition mechanism while preserving the exact identity invariant.

Known provider caveat: Yahoo/yfinance metadata retrieval is an upstream availability dependency. A metadata outage must fail closed rather than revive ticker-only history. Availability/performance optimization is NEXT/BACKLOG unless production evidence shows it is a release-blocking regression.

## 11. NOW / NEXT / BACKLOG / REJECT

### NOW

Close PR #161 as an R2 P0 correctness batch:

```text
final exact-head CI + Vercel preview
→ final self-review
→ independent review
→ Ready
→ release-backup pre-merge recovery
→ final TOCTOU
→ squash merge
→ post-main CI / Vercel production
→ live VFLO pre-inception production regression
```

### NEXT AFTER P0

Batch 4A-6 — user-facing Walk-Forward UX over the already-versioned server workflow. UX must surface provenance/failure truth rather than hide it.

### BACKLOG

- ResearchRun / research memory;
- PIT fundamentals / large-universe causal narrowing;
- AI research automation/autopilot;
- distributed scale/performance after correctness contracts stabilize;
- profile/optimize Yahoo lifecycle metadata acquisition only if real runtime evidence shows unacceptable latency or availability impact.

### REJECT FOR CURRENT P0

- hard-coded VFLO listing date;
- chart-only truncation;
- synthetic/proxy history before inception;
- current-fundamental historical evidence;
- new alpha/ranking formulas;
- Portfolio/Exhaustive/PIT math duplication;
- leverage changes;
- 4A-6 UI implementation;
- unrelated legacy refactors/process expansion;
- reactivating frozen PR #147.

## 12. Exact Resume Point

On resume:

1. read `AI_PROJECT_PLAYBOOK.md`, `README.md`, this file and `docs/UNIFIED_TWD_CONTRACT.md`;
2. re-query GitHub `main`, PR #161, exact head/base, CI, Vercel, reviews/threads and releases;
3. inspect the exact PR diff rather than trusting this handoff;
4. confirm `firstTradeDate` verification remains upstream of all TWD/return/portfolio calculations;
5. confirm metadata failure remains fail closed;
6. confirm the historical appendix below remains preserved when updating this file;
7. finish the R2 gates above;
8. only after production VFLO regression is clean, mark this P0 CLOSED and activate 4A-6.

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
