# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff. Mutable GitHub / CI / Vercel / Cloudflare / runtime truth must be re-queried before important writes. Durable methodology belongs in versioned contracts under `docs/`; closed execution history is reconstructable from Git, PRs and Actions.

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

- VictoryShares Free Cash Flow ETF was launched in June 2023;
- Nasdaq began listing/trading ticker `VFLO` on **2023-06-22**;
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

## 8. Regression Locks Added

Targeted tests cover:

1. Yahoo `firstTradeDate` parsing from epoch seconds, milliseconds and ISO dates;
2. simultaneous clipping of adjusted price and time-indexed component attrs;
3. VFLO-class ticker-reuse rows removed before downstream use;
4. corporate-action event counts rebuilt after pre-inception event removal;
5. market-data frame audit preserves the verified identity boundary;
6. unverifiable identity metadata fails closed instead of producing results;
7. an entirely pre-inception window returns no usable current-instrument history.

Full repository CI remains authoritative for cross-system regression.

## 9. Current Verification State

An earlier candidate passed Python compile/lint/tests plus JS/Worker/Portfolio source contracts before self-review tightened the metadata policy from `unverified-but-usable` to **fail closed**.

Because fail-closed and documentation changes advanced the branch head, earlier CI is supporting evidence only. The final exact head still requires fresh:

1. full repository CI SUCCESS;
2. Vercel preview SUCCESS;
3. final diff self-review / no BLOCKER;
4. independent review on the exact final head;
5. zero unresolved BLOCKER threads;
6. pre-merge recovery against exact current main;
7. squash merge with exact expected head;
8. post-main backup + main CI + Vercel production;
9. production regression proving a 2016-requested VFLO path/effective history cannot begin before the current instrument's verified first-trade boundary.

## 10. Performance / Reliability Constraints

The identity resolver must not turn a 100-symbol scan into unbounded serial metadata work.

Current design:

- bounded concurrent resolver workers;
- two metadata attempts per uncached symbol;
- successful identity evidence cached for six hours;
- metadata failures cached only briefly (30 seconds) to suppress duplicate lookups inside a finite retry cycle without creating a multi-hour outage;
- market-data download retry remains finite.

Do not trade correctness for speed by silently accepting unverified ticker-only history. If later profiling shows unacceptable latency, optimize the metadata acquisition mechanism while preserving the exact identity invariant.

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
- distributed scale/performance after correctness contracts stabilize.

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
6. finish the R2 gates above;
7. only after production VFLO regression is clean, mark this P0 CLOSED and activate 4A-6.
