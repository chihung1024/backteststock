# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff only. Mutable GitHub / Vercel / Cloudflare / runtime state must be re-queried before important actions. Durable architecture belongs in README/contracts/ADRs; completed execution detail remains recoverable from Git/PR/Issue/Actions history.

## 1. Current Goal

**Primary active batch: pre-Phase-6 repository hygiene closeout.**

The user explicitly required a full cleanup/audit before formal Phase 6 implementation. Cleanup is not permission to remove active functionality: anything with uncertain runtime, deployment, security, recovery or contract value must be proven safe before deletion.

Phase 6 / Issue #77 remains the **next functional batch**, not currently under implementation.

### Completion-before-convergence

For every batch:

1. finish the intended capability/root-cause work;
2. investigate materially coupled defects/dependencies;
3. fix blockers or prove residuals non-blocking;
4. run focused + broad regression and production verification where relevant;
5. only then converge and move on.

---

## 2. Stable Production State

Repository: `chihung1024/backteststock`.

Current main after completed source/document cleanup:

`d421d05358eab5890654bba98fd14a0a91198c99`

Latest accepted cleanup evidence:

- **Cleanup A — retired code/process debris:** merged as `0a40a1d8d11668b6b9eefbcc39f32d03120466d8`; removed proven retired optimizer runtime/UI/workers/direct dead-code tests, unreferenced UI/CSS and closed process narratives. Post-main Full CI #620, Vercel production and Cloudflare #55 production smokes passed.
- **Cleanup P — Portfolio migration history convergence:** merged as `d421d05358eab5890654bba98fd14a0a91198c99`; replaced migration-era semantic authority with `docs/PORTFOLIO_V3_CONTRACT.md`, removed migration-only docs/test/fixtures, while preserving the one live synthetic return-components fixture under its current authority. CI #621 correctly exposed that hidden dependency before merge; corrected internal/candidate CI #623/#624 passed; post-main CI #625, Vercel production and post-merge backup #510 passed.

Important closed functional foundations remain #79, #80 and #78; do not reopen without new evidence.

---

## 3. Primary Active Batch — Cleanup W

**Goal:** remove the now-redundant Portfolio-specific GitHub Actions workflow without reducing merge protection.

Evidence before deletion:

- repository ruleset `main-protection` requires only GitHub check `validate` and `Vercel`;
- `.github/workflows/ci.yml` runs on every PR and main push;
- global `validate` already performs Portfolio type-check/build, Portfolio/Refinery source-contract tests and committed production-asset drift verification;
- `.github/workflows/portfolio-web-ci.yml` repeated exactly those three checks under `portfolio-web-validate` and was not a required status check.

Current internal branch:

`internal-cleanup-w-redundant-portfolio-ci-2026-08-13`

Current change:

- delete `.github/workflows/portfolio-web-ci.yml` only;
- update this live handoff to remove stale status and record the actual cleanup boundary.

Exit gate:

- exact diff contains no runtime/code/config behavior changes other than removal of the duplicate workflow;
- full global `validate` passes on the branch;
- independent review finds no lost unique trigger/check/permission/security behavior;
- candidate Vercel + required checks pass;
- post-main CI/backup pass.

---

## 4. Cleanup Audit Classification

### Proven debris already removed

- retired legacy optimizer backend/UI/workers and direct dead-code tests;
- unreferenced legacy UI enhancement script and orphan stylesheet;
- closed Phase/process rollout narratives with no unique semantic value;
- Portfolio migration self-validation package after durable semantics moved to current contract/tests;
- redundant Portfolio-specific CI workflow is the current Cleanup W target.

### Audited KEEP — not garbage

- **Root homepage Backtest:** active default user-facing tab in `public/index.html`; `public/app.js` still posts to `/api/backtest`. Removal would break normal functionality. Keep until an explicit, production-verified replacement/redirect is implemented.
- **Legacy `/api/backtest` compatibility surface:** still consumed by the active homepage; keep fail-safe Edge/API behavior and tests.
- **Portfolio source map:** Vite currently declares `sourcemap: true`; the `.map` file is generated build output, not an accidental orphan. Do not delete independently. A future build-policy change may disable public sourcemaps only if the generated production asset set is rebuilt and asset-drift/production checks pass.
- **Scanner UI/progress/output modules and observers:** current functionality/tests still depend on them. Refactor only for a concrete defect or measured maintenance problem; do not call them debris merely because responsibility is distributed.
- **CI, Cloudflare deploy, Release Backup and Universe update workflows:** each retains a distinct active role.

### Tool-limited metadata cleanup

Old branches / historical workflow-run registry / releases may contain visual clutter, but the current GitHub connector does not expose safe delete-ref / delete-workflow-run / delete-release mutations. Do not fake cleanup by repointing refs or rewriting recovery history. Treat this as tool-blocked metadata housekeeping, not a functional blocker.

---

## 5. Remaining Pre-Phase-6 Work

After Cleanup W closes, perform **one final independent debris sweep** against current main. The purpose is falsification, not to invent more cleanup work.

The sweep must classify each finding as:

- REMOVE NOW — proven unused/redundant and safe;
- KEEP — active runtime/deployment/security/contract/recovery value;
- BACKLOG — useful cleanup but requires a separate functional migration/refactor;
- TOOL-BLOCKED — safe cleanup cannot be executed with available connector mutations.

If no new REMOVE NOW item remains, repository hygiene is considered converged and Phase 6 starts immediately. Do not continue polishing documents or searching indefinitely for cosmetic work.

---

## 6. Next Functional Batch — Phase 6 / Issue #77

**Phase 6 MVP: common-sample marginal Remove-One / Add-One / Replace-One experiments.** Planning is already saturated; do not restart broad design work.

### P6-A backend usable core

Required invariants:

- explicit Remove-One / Add-One / Replace-One operations only;
- reuse existing symbol normalization and quantitative authorities;
- separate operation-count and experiment-union caps before expensive compute;
- one market-history union fetch per request;
- existing Phase 3–5 baseline semantics remain unchanged;
- build/freeze one daily and one weekly global complete-case experiment sample;
- every variant is only a column selection from those frozen matrices — never re-`dropna()` per variant;
- compare every variant with one `experiment_baseline` on the identical sample;
- expose sample start/end/observations/canonical symbols/exact SHA-256;
- experiment-only data failure fails the marginal layer closed without destroying a valid existing baseline;
- reuse validated covariance/effective-dimension/correlation/clustering primitives;
- retained-pair correlations remain invariant on the frozen sample;
- no full Phase-5 bootstrap per variant in minimal V1;
- no invented weights, ranking, sizing, recommendation or forward-return claims.

### P6-B usable UI

Provide only the minimum interface to enter explicit Remove/Add/Replace operations, run preflight/analyze, compare experiment baseline vs variant, show structural/sample evidence and invalidate stale evidence when inputs change.

### Phase 6 exit gate

- no-plan parity for Phase 3–5;
- fail-closed operation validation;
- common-sample identity/invariance regression;
- measured resource caps;
- all three user workflows usable;
- focused + broad CI pass;
- independent falsification review;
- candidate deployment + production workflow verification;
- no known material residual that would contaminate the subsequent cross-workflow integration pass.

---

## 7. After Phase 6

Run one bounded end-to-end integration pass:

```text
Scanner
-> selected tickers
-> Optimizer
-> candidate portfolio
-> Portfolio backtest
-> Refinery structural analysis / marginal experiments
```

Fix only material handoff/data-consistency/recovery/UI defects revealed by that journey.

Phase 7+ remains conditional backlog. OOS/walk-forward validation, selection/sizing, deeper Exhaustive integration or point-in-time data are not automatically unlocked merely because Phase 6 finishes.

---

## 8. Technical Debt / Backlog

Keep unless promoted by new evidence:

- Scanner presentation-only retry-range label residual from #80; execution/count/resume semantics are already verified unaffected;
- Yahoo request amplification / metadata fan-out and diagnostics hardening;
- instrument/security master and regional factor routing;
- traceable theme provider/taxonomy;
- distributed Refinery rate limiting;
- Cloudflare timeout-vs-retry-budget formal alignment;
- GitHub Actions immutable-SHA pinning review;
- single-portfolio + shorter-benchmark strict-comparison policy separate from completed #79;
- point-in-time Universe/fundamentals for a future PIT phase;
- optional public sourcemap policy change only as a proper build/deployment batch;
- root homepage Backtest retirement only after an explicit replacement and production acceptance.

---

## 9. Exact Resume Point

1. finish Cleanup W full CI + independent review;
2. promote the exact green tree to `candidate-*`, pass required `validate` + Vercel + backup gates, merge with expected-head protection;
3. run post-main CI/backup and verify the ruleset still requires `validate` + Vercel;
4. run one final debris falsification sweep against that main;
5. if no new safe REMOVE NOW item exists, declare pre-Phase-6 hygiene CLOSED;
6. re-query Issue #77 and current main;
7. create one clean `internal-*` Phase 6 branch and start P6-A implementation immediately.

**Primary Active Batch = Cleanup W. Next Functional Batch = Phase 6 / #77 MVP.**
