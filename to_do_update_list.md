# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff snapshot. Mutable GitHub / Vercel / Cloudflare / runtime state must be re-queried before important actions. Durable architecture belongs in README/contracts/ADRs; completed execution detail is reconstructable from Git/PR/Issue history.

## 1. Current Functional Goal

**Primary functional goal: Phase 6 / Issue #77 — deliver the usable Remove-One / Add-One / Replace-One Refinery MVP.**

#79, #80 and #78 are closed. Do not reopen them without new production evidence.

### Completion-before-convergence rule

Convergence is an exit discipline, not an early-stop rule. For each functional batch:

1. complete the necessary root-cause / capability work;
2. clear coupled material blockers required for safe acceptance;
3. run relevant regression and end-to-end verification;
4. perform production/runtime verification when deployment affects behavior;
5. do not leave a known material defect that invalidates acceptance or predictably contaminates the next dependent batch;
6. only then classify remaining work as NEXT / BACKLOG / REJECT and stop unnecessary expansion.

---

## 2. Stable Production State

Repository: `chihung1024/backteststock`.

Current **functionally production-verified** runtime baseline:

`bd35440a2ec4419677bbbb0433df2e23a729c757`

Important closed foundations:

- Phase -1 through 4: governance, TWD/quant authority, ResearchDataset, Refinery API/UI — CLOSED/PASS.
- Phase 5 / #65 + #75 + #94: clustering/redundancy + hardened production acceptance — CLOSED/PASS/PRODUCTION VERIFIED.
- #83 + #84 + #80: scanner retry/cache/progress/reliability — CLOSED/PASS.
- #90: Vercel Deployment Economy — CLOSED/PASS/VERIFIED.
- #79 + PR #98: Portfolio multi-runnable common-window authority — CLOSED/PASS/PRODUCTION VERIFIED.
- #78 + PR #104: Scanner selected-tickers → Optimizer restored-job handoff — CLOSED/PASS/PRODUCTION VERIFIED.

### #78 final acceptance evidence

`main@bd35440a2ec4419677bbbb0433df2e23a729c757` is deployed through Vercel production and Cloudflare Worker/static assets.

Dedicated production-browser acceptance against `backteststock.chired.workers.dev` verified:

- restored legacy `scan-job-v3` remains raw in persisted storage;
- Scanner manual selection writes canonical provenance;
- `/optimizer.html?mode=manual` receives exactly `AAA, BBB`;
- canonical dates are `2025-01-01 -> 2025-12-31`;
- benchmark remains `QQQ`;
- ordinary `/optimizer.html` still receives full source `AAA, BBB, CCC`.

Root cause was closed with one shared pure scan-job date normalization authority. Strict sourceJobId / membership / coverage / benchmark / TWD validation remains intact; persistence schema and optimizer math were not changed.

---

## 3. Primary Active Batch — Phase 6 / #77 MVP

Issue #77 is now titled **Phase 6 MVP: common-sample marginal Remove-One / Add-One / Replace-One experiments**.

The old opening `PLANNING / BLOCKED / do not implement yet` banner in its long body is historical stale status. An authoritative 2026-08-12 status override records that all blockers are complete and implementation is **READY / PRIMARY ACTIVE**.

The detailed V1 specification remains **FROZEN / SATURATED**. Do not restart broad planning or expand the feature set without implementation evidence.

### P6-A — backend usable core

Deliver the smallest correct backend capability that supports explicit:

- Remove-One;
- Add-One;
- Replace-One.

Required invariants:

- reuse existing `normalize_symbol()` authority;
- explicit operations only; no hidden N×M replacement explosion;
- separate operation-count and experiment-union symbol caps, chosen from measured runtime/response-size evidence;
- one authoritative market-history union fetch per request;
- preserve existing Phase 3–5 baseline semantics;
- build/freeze one `daily_global` and one `weekly_global` complete-case sample across the full experiment union;
- variants are column selection from the frozen global matrices only — never re-`dropna()` per variant;
- distinguish existing baseline from Phase 6 `experiment_baseline`;
- every Phase 6 delta = variant − experiment_baseline on the identical effective sample;
- expose daily/weekly effective start/end/observations/canonical symbols/exact sample SHA-256;
- experiment-only market-data failure fails the Phase 6 layer closed without destroying a valid Phase 3–5 baseline;
- reuse validated covariance/effective-dimension/correlation/hierarchical-clustering primitives;
- retained-pair raw correlations must remain invariant on the frozen sample;
- no per-variant full Phase 5 bootstrap in minimal V1;
- no invented weights, ranking, sizing, recommendation or magic score.

### P6-B — user-usable Refinery UI

After P6-A contract/core is usable, add the minimum UI needed to:

- choose Remove-One / Add-One / Replace-One explicitly;
- provide required symbol input(s);
- run existing Refinery preflight/analyze operations;
- compare experiment baseline vs variant;
- show effective-dimension/correlation/cluster changes;
- show common-sample evidence, failures and warnings clearly;
- invalidate stale evidence when baseline or experiment input changes.

Keep persisted Refinery workspace schema unchanged unless implementation evidence proves persistence is required.

### Phase 6 exit gate

Before closing Phase 6:

- no-plan parity proves Phase 3–5 output did not drift;
- Remove/Add/Replace operation validation is fail-closed;
- common-sample identity/invariance tests pass;
- resource caps are justified by measured deployment behavior;
- UI can complete the three workflows;
- focused and broad regression pass;
- production preflight/analyze and user workflow are verified;
- no known material defect remains that would invalidate the subsequent cross-workflow integration pass.

---

## 4. Immediate Next Functional Batches

### F2 — Phase 6 / #77 MVP

**PRIMARY ACTIVE.** Implement P6-A backend core, then P6-B usable UI. Planning is already saturated.

### F3 — Core workflow integration

After Phase 6 MVP is production verified, test the actual user journey:

```text
Scanner
-> selected tickers
-> Optimizer
-> candidate portfolio
-> Portfolio backtest
-> Refinery structural analysis / marginal experiments
```

Fix only material handoff, data-consistency, recovery or UI defects found by this journey before adding dependent capabilities.

### Phase 7+

**CONDITIONAL BACKLOG, not an automatic sequence.**

Promote only when actual product use creates a concrete need. Possible future capabilities include OOS/walk-forward validation, selection, sizing, Exhaustive integration or point-in-time data; completion of Phase 6 alone is not an unlock reason.

---

## 5. Locked Decisions Still Relevant

- `AI_PROJECT_PLAYBOOK.md` remains frozen engineering-governance authority; do not rewrite it for feature-specific lessons without a reopen condition.
- `docs/PROJECT_DOCUMENTATION_POLICY.md` owns documentation authority/freshness/lifecycle/duplication/handoff quality. Documentation exists to prevent project memory loss and distortion, not to become a parallel project.
- Keep one Primary Active Batch. Supporting review/research/docs must not create a competing implementation stream.
- `internal-*` branches suppress automatic Vercel Preview. Promote a converged implementation to deliberate `candidate-*` only when genuine deployment evidence is required. Keep `main` production enabled.
- Before CLOSED/PASS, reconcile remote PR/Issue state, blocker reviews/threads, deployment/runtime evidence and remaining material debt.
- Quant/data authorities remain:
  - `TWDHistoryService`: audited market history / TWD valuation authority;
  - `apps/api/app/portfolio/`: Portfolio ledger/metrics/comparison/analytics composition;
  - `apps/api/app/research/` + `apps/api/app/refinery/`: ResearchDataset / Refinery evidence composition;
  - `apps/api/app/quant/`: pure validated quantitative primitives;
  - browser: presentation/workflow only; no second quantitative authority.

---

## 6. Open Risks / Technical Debt

No known open root cause currently blocks Phase 6 start.

Functional risks to watch during Phase 6:

- global experiment common-sample construction must not silently shorten/change existing Phase 3–5 baseline output;
- Remove-One must not regain observations after global sample freeze;
- Add/Replace external-symbol failure must remain localized to the marginal layer;
- operation/resource caps must reject excessive plans before expensive calculation;
- browser/UI must not introduce parallel quantitative formulas;
- Phase 6 must remain diagnostic/in-sample and must not drift into recommendation, optimization or sizing.

Technical debt — BACKLOG unless promoted by new evidence:

- **Scanner presentation-only residual from #80:** retry-requeued displayed batch range can temporarily be mislabelled; verified not to change execution, settled/success/failure counts or resume semantics.
- Yahoo request amplification / metadata fan-out and scanner diagnostics hardening;
- instrument/security master and regional factor routing;
- traceable theme provider/taxonomy;
- distributed Refinery rate limiting;
- Cloudflare timeout-vs-retry-budget formal alignment;
- GitHub Actions immutable-SHA pinning review;
- historical Actions registry cleanup where supported;
- single-portfolio + shorter-benchmark strict-comparison policy separate from completed #79;
- point-in-time Universe/fundamentals for a future PIT phase.

Deferred unless evidence requires them:

- Phase 6 variant-level full Phase 5 bootstrap;
- persistent experiment plans;
- automatic selection/ranking/sizing;
- OOS claims from in-sample evidence.

---

## 7. Exact Resume Point

1. re-query current `main`, Issue #77 and open PR state;
2. inspect current `Phase5RefineryService`, `RefineryRequest`, ResearchDataset preparation, quant primitives and Refinery preflight/analyze/UI dataflow before modifying code;
3. create one clean `internal-*` Phase 6 branch from exact current main;
4. implement P6-A contract/normalization/caps first with deterministic tests;
5. extend preparation to fetch the full experiment union once while preserving the existing baseline view;
6. construct and freeze daily/weekly global common samples once, with exact evidence fingerprints;
7. compute experiment baseline and explicit variants only from frozen column selections;
8. add structural deltas using existing quant authorities and prove retained-pair/sample invariants;
9. verify experiment-only failure remains localized and no-plan Phase 3–5 parity holds;
10. measure runtime/response size and set bounded caps from evidence;
11. add P6-B UI only after backend contract is stable enough to use;
12. run focused + broad regression, independent falsification review, candidate deployment and production verification;
13. after Phase 6 completes, update this handoff once and run the bounded F3 cross-workflow integration pass.

**Primary Active Batch = Phase 6 / #77 MVP.**
