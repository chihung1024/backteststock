# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff only. Re-query mutable GitHub, CI, Vercel, Cloudflare and runtime state before an important action. Durable API/UI semantics remain in their current contracts; Git/PR/Issue/Actions retain the execution history.

## Current Status

**PF-1D Scanner edge-cache namespace invalidation — CLOSED / DEPLOYED / POST-MAIN VERIFIED (R2).**

- [PR #135](https://github.com/chihung1024/backteststock/pull/135) passed exact-head candidate CI [#674](https://github.com/chihung1024/backteststock/actions/runs/31728923886), received an independent exact-head review, was marked Ready, and was squash-merged to main as [`f8c08caa2e604acf193263667fd6815cbad1c2ec`](https://github.com/chihung1024/backteststock/commit/f8c08caa2e604acf193263667fd6815cbad1c2ec) on 2026-08-13.
- Post-main CI [#675](https://github.com/chihung1024/backteststock/actions/runs/31729216617), Vercel production [deployment](https://vercel.com/cchungs-projects/back-test/CNiBXJ8bAsxK3cmfA6RV9VuX5LTr), and [Deploy Cloudflare Worker #65](https://github.com/chihung1024/backteststock/actions/runs/31729216623) all passed at the merged SHA; Cloudflare production smoke covered Russell 2000, Portfolio v3 and Refinery v1.
- Direct production edge smoke against [`backteststock.chired.workers.dev`](https://backteststock.chired.workers.dev) returned `/api/scan` 200 with `MISS` on the first identical request and `HIT` on the second; both rows were AAPL `ok` with full `1.0` coverage. This verifies namespace deployment and cache behavior, not the sparse `0.5` data case.
- Local validation passed 272 Python tests, Ruff, JavaScript checks, Worker tests (77), score tests (12), Portfolio check/build, source contracts, and git diff --check. Local browser E2E remains NOT VERIFIED because the sandbox lacks Playwright Chromium; candidate CI ran Chromium E2E successfully.
- The change only invalidates the old `/api/scan` cache namespace; API formulas, cache TTL/policy, frontend relative coverage, selection/handoff, persistence, data and other routes are unchanged.

**PF-1C TWD Scanner raw-calendar coverage audit — CLOSED / DEPLOYED / POST-MAIN VERIFIED (R2).**

- [PR #133](https://github.com/chihung1024/backteststock/pull/133) passed exact-head candidate CI [#669](https://github.com/chihung1024/backteststock/actions/runs/31726757514), received an independent exact-head review, was marked Ready, and was squash-merged to main as [`47ca2ea0cd2850774470080916d53896a9d463c6`](https://github.com/chihung1024/backteststock/commit/47ca2ea0cd2850774470080916d53896a9d463c6) on 2026-08-13.
- Post-main CI [#670](https://github.com/chihung1024/backteststock/actions/runs/31727065558) passed all repository gates, including Chromium E2E. Vercel production reported success at [the merged deployment](https://vercel.com/cchungs-projects/back-test/EgMeRex9WRhjzq2j7sCnwAcYovD7).
- Cloudflare Worker did not trigger for this merge because no Worker or public static asset changed; the candidate Cloudflare dry-run passed. No manual deployment command, protection bypass, or direct production write was used.
- Local validation passed 272 Python tests, Ruff, JavaScript checks, Worker tests (76), score tests (12), Portfolio check/build, source contracts, and git diff --check. PF-1D later added a production edge smoke; the sparse partial-calendar coverage assertion remains NOT VERIFIED.
- The correction is limited to API audit semantics: raw TWD valuation calendars now feed `data_coverage` / `benchmark_calendar_coverage` before metric-calendar forward-fill. Metric values, trading-day range, selection thresholds, handoff behavior, persistence, and data sources are unchanged.

**PF-1B Scanner → Portfolio legacy-date handoff — CLOSED / DEPLOYED / POST-MAIN VERIFIED (R2).**

- [PR #131](https://github.com/chihung1024/backteststock/pull/131) passed exact-head candidate CI [#665](https://github.com/chihung1024/backteststock/actions/runs/31719788695), was independently reviewed, marked Ready, and squash-merged to main as [`3a93afe12b92965676bd33c52b315f415303574c`](https://github.com/chihung1024/backteststock/commit/3a93afe12b92965676bd33c52b315f415303574c) on 2026-08-13.
- Post-main CI [#666](https://github.com/chihung1024/backteststock/actions/runs/31720172713), Vercel production and [Deploy Cloudflare Worker #64](https://github.com/chihung1024/backteststock/actions/runs/31720172734) all passed at the merged SHA; Cloudflare smoke covered Russell 2000, Portfolio v3 and Refinery v1.
- Local non-browser validation passed `npm run check`, `npm run test:worker` (76 tests), `npm run test:score` (12 tests), `npm run check:portfolio`, route-contract tests and `git diff --check`. Local Chromium was unavailable; candidate CI ran the legacy-date Portfolio browser regression successfully.
- The merge push triggered the configured production workflows automatically; no manual deployment command, protection bypass or direct production write was used.

**UX-1B Scanner destination capacity — CLOSED / DEPLOYED / POST-MAIN VERIFIED (R1).**

- [PR #127](https://github.com/chihung1024/backteststock/pull/127) passed exact-head candidate CI #656, was marked Ready, and was squash-merged to main as [21a7e5ff4bccbc77616bd6dec7397c12b7f81867](https://github.com/chihung1024/backteststock/commit/21a7e5ff4bccbc77616bd6dec7397c12b7f81867) on 2026-08-13.
- Candidate CI [#656](https://github.com/chihung1024/backteststock/actions/runs/31700763590) passed JavaScript checks, Portfolio/Refinery contracts, Chromium E2E and all repository validation gates.
- Post-main CI [#657](https://github.com/chihung1024/backteststock/actions/runs/31701086294) passed on the merged head. Vercel reported success and [Deploy Cloudflare Worker #62](https://github.com/chihung1024/backteststock/actions/runs/31701086369) passed Russell 2000, Portfolio v3 and Refinery v1 production smoke tests.
- The merge push triggered the repository's configured production workflows automatically; no manual deployment command, protection bypass or direct production write was used.
- UX-1A remains closed at [4598ecf1a2870bcec7b71c69b5d7642601e0c55a](https://github.com/chihung1024/backteststock/commit/4598ecf1a2870bcec7b71c69b5d7642601e0c55a).

Primary Goal completed: make Scanner execution scale, pending-first-result state, and downstream destination capacity explicit without changing data, quant, defaults, selection semantics, retry/resume behavior or persistence contracts.

## Closed Batch — PF-1D / R2

### Objective / Scope Lock

- **Objective:** prevent stale Worker edge-cache responses from hiding the PF-1C TWD Scanner coverage-audit correction after the Vercel API merge.
- **In scope:** bump the `/api/scan` cache namespace from `2026-08-11.1` to `2026-08-14.1`, add a stale-namespace regression, and verify the production Worker MISS→HIT behavior.
- **Out of scope:** API calculations, cache TTL or admission policy, other routes, frontend relative coverage, selection/handoff, persistence, data sources, migrations, and unrelated cleanup.
- **Risk class:** R2 externally observable cache/data consistency; exact-head review, full candidate CI, protected merge, Cloudflare production smoke and post-main verification were required.
- **Rollback:** normal revert of PR #135; no data, storage, persistence, or schema migration is introduced.

### Evidence / Root Cause

- **Reproduction:** before this batch, a cached `/api/scan` response under namespace `2026-08-11.1` returned the pre-fix `data_coverage=1` while backend call count remained zero; the corrected backend would return `0.5` for a sparse calendar case.
- **Failure point:** PF-1C changed the Vercel API implementation but did not change the Worker cache namespace, so identical requests could remain stale for the 15-minute edge TTL.
- **Downstream impact:** Scanner audit/CSV consumers could temporarily observe the old coverage value after the API fix had deployed.

### Closure / Stable Checkpoint

- Worker namespace is now `2026-08-14.1`; the regression proves old-version entries miss, the corrected backend is called, and the response is marked `MISS`.
- Candidate CI [#674](https://github.com/chihung1024/backteststock/actions/runs/31728923886) passed all checks at exact head `70bf4aff2ba11ae71e953895a847a65fe3e87397`; the independent review found no blocking issue.
- Post-main CI [#675](https://github.com/chihung1024/backteststock/actions/runs/31729216617), Vercel production, and Cloudflare Deploy [#65](https://github.com/chihung1024/backteststock/actions/runs/31729216623) passed at merged head `f8c08caa2e604acf193263667fd6815cbad1c2ec`.
- Direct production smoke confirmed first-request `MISS` and second-request `HIT` on the deployed Worker; the live AAPL row was fully covered at `1.0`, so sparse partial-calendar `0.5` output remains NOT VERIFIED in production.
- Rollback is a normal revert of PR #135; no data, storage, persistence, or schema migration is involved.

## Closed Batch — PF-1C / R2

### Objective / Scope Lock

- **Objective:** make the TWD Scanner API coverage audit reflect raw valuation observations instead of the forward-filled metric calendar.
- **In scope:** pass the raw benchmark history into the success-row audit calculation, expose the explicit `benchmark_calendar_coverage` field, add a sparse-calendar regression, and document the API/browser coverage distinction.
- **Out of scope:** quant formulas, metric-calendar alignment or forward-fill, TWD valuation, data sources, retry/resume behavior, frontend relative-max coverage, selection or handoff thresholds, persistence, migrations, workflows, and unrelated cleanup.
- **Risk class:** R2 externally observable data-integrity/audit semantics; exact-head independent review, full candidate CI, protected merge and post-main verification were required.
- **Rollback:** normal revert of PR #133; no data, storage, persistence, or schema migration is introduced.

### Evidence / Root Cause

- **Reproduction:** with two raw candidate dates (2025-01-02, 2025-01-06) and four raw benchmark dates (2025-01-02, 2025-01-03, 2025-01-06, 2025-01-07), the pre-fix aligned series reported four trading days and `data_coverage=1.0`; raw calendar coverage is `0.5`.
- **Failure point:** `apps/api/app/scan_service.py::TWDScanService.run` calculated `data_coverage` after benchmark alignment and forward-fill, so missing raw candidate observations were counted as if observed.
- **Downstream impact:** the API/CSV audit field could claim complete benchmark coverage even when the candidate had only partial raw observations; the browser's separate relative max-day display and selection threshold were not changed.

### Closure / Stable Checkpoint

- `_success_row` now calculates `data_coverage` and `benchmark_calendar_coverage` from the raw asset and raw benchmark histories before metric-calendar forward-fill.
- The focused regression preserves the four-day metric result while asserting both audit fields are approximately `0.5`.
- Candidate CI [#669](https://github.com/chihung1024/backteststock/actions/runs/31726757514) passed all checks at exact head 2ab671c986f8ebe2ead9e41feee4ffe4bff823b4; the independent review found no blocking issue.
- Post-main CI [#670](https://github.com/chihung1024/backteststock/actions/runs/31727065558) passed at merged head 47ca2ea0cd2850774470080916d53896a9d463c6; Vercel production reported success. Cloudflare was intentionally not invoked because the Worker/public asset surface was unchanged.
- A later production edge smoke verified the new Worker namespace with MISS→HIT behavior on a fully covered AAPL row; the sparse partial-calendar `0.5` provider response remains NOT VERIFIED. The repository-level contract and regression gates are green.
- Rollback is a normal revert of PR #133; no data, storage, persistence, or schema migration is involved.

## Closed Batch — PF-1A / R2

### Objective / Scope Lock

- **Objective:** keep the validated Scanner manual Optimizer handoff intact after a Scanner → Portfolio → Scanner round trip, so the next manual Optimizer launch still has the same source-job provenance and date/benchmark/currency contract.
- **In scope:** preserve an existing rich `backteststock-optimizer-manual-selection-v2` record only when its `sourceJobId` matches the Portfolio handoff and its `selectionMode` is the validated manual fixed-source-pool mode; add focused route-contract and browser regressions.
- **Out of scope:** quant formulas, coverage methodology, API/data sources, Portfolio/Optimizer capacity, retry/resume behavior, storage schema migration, deployment/workflow cleanup and unrelated UI refactors.
- **Risk class:** R2 shared local persistence and cross-page handoff; independent review and full CI are required. Existing incomplete records remain fail-closed.
- **Verification:** `npm run check`, `npm run test:worker`, `npm run test:score`, `npm run check:portfolio`, route-contract tests, focused Chromium E2E, candidate CI, post-main CI and required production smoke only if the protected merge changes deployed public assets.
- **Rollback:** revert the single PF-1A merge; no data or persistence migration is introduced.

### Evidence / Root Cause

- `public/portfolio-route-bridge.js::restoreSelection()` previously replaced the rich manual Optimizer record with only `version`, `sourceJobId`, `coverageThresholdPercent` and `tickers`.
- `public/exhaustive-optimizer.js::validatedManualHandoff()` intentionally requires `selectionMode`, exact dates, benchmark and `valuationCurrency`; after return those fields were absent, so the Optimizer safely rejected the otherwise valid selection.

### Closure / Stable Checkpoint

- PR [#129](https://github.com/chihung1024/backteststock/pull/129) passed exact-head candidate CI [#660](https://github.com/chihung1024/backteststock/actions/runs/31716727603), was marked Ready, and was squash-merged to main as [`15a5f4497bcb70e216bc58bdd506f1b3693987f8`](https://github.com/chihung1024/backteststock/commit/15a5f4497bcb70e216bc58bdd506f1b3693987f8) on 2026-08-13.
- Post-main CI [#661](https://github.com/chihung1024/backteststock/actions/runs/31717045836), Vercel production and Cloudflare Deploy [#63](https://github.com/chihung1024/backteststock/actions/runs/31717045754) all passed at the merged SHA; Cloudflare smoke covered Russell 2000, Portfolio v3 and Refinery v1.
- Local verification passed `npm run check`, `npm run test:worker` (76 tests), `npm run test:score` (12 tests), `npm run check:portfolio`, `node --test tests/test_portfolio_route_bridge.mjs` and `git diff --check`. Local Chromium was unavailable in the sandbox; candidate CI ran the focused browser regression successfully.
- The merge push triggered the configured production workflows automatically; no manual deployment command, protection bypass or direct production write was used.
- Rollback is a normal revert of PR #129; no data, storage or persistence migration is introduced.

## Closed Batch — PF-1B / R2

### Objective / Scope Lock

- **Objective:** keep the Scanner → Portfolio handoff's source date range correct when a restored v3 scan still stores legacy `startYear`/`startMonth`/`endYear`/`endMonth` fields instead of canonical ISO dates.
- **In scope:** normalize the persisted scan job at the Portfolio route bridge using the existing Scanner date contract; add a focused browser regression and cache-key update for the bridge module.
- **Out of scope:** quant formulas, coverage methodology, API/data sources, Optimizer validation rules, Portfolio capacity, retry/resume behavior, storage schema migration, deployment/workflow cleanup and unrelated UI refactors.
- **Risk class:** R2 shared local persistence and cross-page data handoff; exact-head candidate CI, independent review and post-main verification are required.
- **Verification:** route-contract tests, focused Chromium E2E, `npm run check`, `npm run test:worker`, `npm run test:score`, `npm run check:portfolio`, candidate CI and post-main CI; production smoke only if the protected merge changes public runtime assets.
- **Rollback:** revert the single PF-1B merge; no data or persistence migration is introduced.

### Evidence / Root Cause

- **Reproduction:** a v3 job with `startYear: 2025`, `startMonth: 1`, `endYear: 2025`, `endMonth: 12` and a valid manual selection produced a Portfolio handoff record with empty `startDate`/`endDate`.
- **Failure point:** `public/portfolio-route-bridge.js::readScanJob()` returned raw localStorage payloads while `public/app.js::loadScanJob()` normalized the same job only in memory.
- **Downstream impact:** `apps/portfolio-web/src/handoff.ts` rejected the empty dates and silently retained its default ten-year model range, so Portfolio could execute on a period different from the Scanner source. The existing Optimizer path already normalizes the job independently.

### Closure / Stable Checkpoint

- `public/portfolio-route-bridge.js::readScanJob()` now applies the existing `scan-job-normalizer.js` contract with the Scanner's ten-year rolling fallback, preserving fail-safe raw-job behavior if normalization cannot run.
- The bridge and all affected Scanner module assets received new query-string cache keys so the fix is served instead of a stale cached module.
- The focused browser regression asserts the session handoff record, Portfolio banner and imported model all retain `2025-01-01` → `2025-12-31` for a legacy year/month scan payload.
- Candidate CI [#665](https://github.com/chihung1024/backteststock/actions/runs/31719788695) passed Chromium E2E, JavaScript/Worker checks, Portfolio/Refinery contracts, Vercel configuration, local D1 migrations and Cloudflare dry-run at exact head `94eab5448d3f27e123d1fca9ddf2f565b352474b`.
- Post-main CI [#666](https://github.com/chihung1024/backteststock/actions/runs/31720172713), Vercel production and Cloudflare Deploy #64 passed at merged head `3a93afe12b92965676bd33c52b315f415303574c`.
- Rollback is a normal revert of PR #131; no data, storage or persistence migration is introduced.

## Closed Batch — UX-1A / R1

### Completed Scope

- show the exact ticker count and deterministic 100-ticker batch count after Universe filtering or manual input;
- show a pending-first-result state instead of zero-value metric cards/table before any ticker settles;
- preserve cancel/resume semantics and correctly describe an empty paused job;
- add focused browser regressions for the plan, the pending→settled transition, and empty filter output;
- record the merged, deployed and verified state without introducing a runtime change.

### Out of Scope

- API, data-source, quant, scoring, default all-candidate scan, retry policy, local-storage schema, visual-system redesign, workflow cleanup, or unrelated refactors;
- manually bypassing protection, required statuses, review, or deployment gates.

## Closed Batch — UX-1B / R1

### Completed Scope

- show a live, accessible status for the same coverage-qualified selection against Portfolio (1–20檔) and Exhaustive Optimizer (2–100檔);
- keep existing handoff button enablement, selection persistence, coverage filtering, scan output, formulas, and navigation semantics unchanged;
- add a focused Chromium regression for empty selection, Portfolio-ready/Optimizer-not-ready, and Portfolio-over-limit/Optimizer-ready states;
- bump the Scanner score asset cache key so the updated destination status is served.

### Out of Scope

- API, data source, quant formulas, defaults, retry/resume behavior, persistence schema, optimizer algorithm, capacity limits, workflow definitions, or unrelated cleanup;
- changing Portfolio or Optimizer capacity; the UI only reports the existing contracts.

### Root Cause / Resolution Record

- **Symptom:** a selected Scanner candidate could be valid for one destination but invalid for the other, while the toolbar did not continuously show both constraints.
- **Resolution:** add one live capacity status that reports current selection count, minimum, maximum and readiness for both destinations; existing action gates remain authoritative.
- **Regression protection:** the focused browser test covers the three boundary states while the existing handoff and cross-tab tests remain unchanged.

### Files / Functional Change

- `public/scan-composite-score.js`: render and update the destination capacity status without changing selection or handoff logic.
- `public/index.html`: bump the score module cache key.
- `tests/e2e/scan_optimizer_handoff.spec.mjs`: add destination-capacity browser coverage.

### Verification

- Candidate CI [#656](https://github.com/chihung1024/backteststock/actions/runs/31700763590) passed at exact head `cd7f123f94628bca812cd9d1fa4ce3f0aa1c280a`.
- Post-main CI [#657](https://github.com/chihung1024/backteststock/actions/runs/31701086294) passed at merged head `21a7e5ff4bccbc77616bd6dec7397c12b7f81867`.
- Vercel and Cloudflare production smoke checks passed after the protected merge.

### Stable State / Rollback

- Revert PR #127 if rollback is needed; no data migration, persistence migration or schema rollback is involved.

## Root Cause / Resolution Record

- **Symptom:** a newly started Scanner job showed zero-value summary/table content before any ticker response had settled.
- **Failure point:** `renderScanJobState()` rendered the ordinary result surface from an empty metrics collection.
- **Root cause:** the UI did not distinguish a pending first response from a settled empty/partial result set.
- **Resolution:** render an accessible execution plan and a dedicated pending-first-result state; reveal the existing summary/table only after a settled result, while keeping paused/retryable state truthful.
- **Regression protection:** focused Playwright coverage for plan counts, no-candidate output, and pending→settled rendering; existing scan/retry regressions remain in the suite.

## Files / Functional Change

- `public/app.js`: derive exact execution plan; render pending-first-result, paused and terminal states without changing scan payload, retry or persistence behavior.
- `public/index.html` and `public/styles.css`: add accessible execution-plan and pending-result surfaces.
- `tests/e2e/app.spec.mjs` and `tests/e2e/scan_first_result_pending.spec.mjs`: Scanner browser regression coverage.
- `to_do_update_list.md`: status/handoff record only; no runtime contract change.

## Verification

- Local implementation validation passed: `npm run check`, `npm run test:worker` (75 tests), `npm run test:score` (12 tests), and `git diff --check`.
- Local Chromium execution was unavailable because the sandbox lacked the Playwright browser; this was not treated as a green gate.
- GitHub CI #651 for initial implementation head `66f83f5` passed: Python compile/lint/tests, JavaScript/Worker/score checks, Portfolio build/contracts, Chromium E2E, Vercel configuration, local D1 migrations and Cloudflare dry-run.
- The handoff-correction head `4a146c3` passed exact-head candidate CI #652 and Vercel Preview.
- Merged main `4598ecf` passed post-main CI #653, Vercel production deployment, Cloudflare Worker deployment and all configured production smoke tests.

## Stable State / Rollback

- Current functional recovery baseline: `main` [`f8c08caa2e604acf193263667fd6815cbad1c2ec`](https://github.com/chihung1024/backteststock/commit/f8c08caa2e604acf193263667fd6815cbad1c2ec).
- Previous verified baseline: [`47ca2ea0cd2850774470080916d53896a9d463c6`](https://github.com/chihung1024/backteststock/commit/47ca2ea0cd2850774470080916d53896a9d463c6).
- Rollback for UX-1B is a normal revert of PR #127; UX-1A remains a normal revert of PR #125. No data migration, persistence migration or schema change is involved.
- The current functional baseline includes:
  - Phase 6 Refinery marginal experiments from [#116](https://github.com/chihung1024/backteststock/pull/116), merged as `72b15c4`;
  - Portfolio shared-link tab behavior from [#117](https://github.com/chihung1024/backteststock/pull/117), merged as `f96ef33`;
  - Scanner retry batch labels from [#118](https://github.com/chihung1024/backteststock/pull/118), merged as `6856736`;
  - Legacy Backtest cache-policy correction from [#121](https://github.com/chihung1024/backteststock/pull/121), merged as `8aff7b0`;
  - Scanner cross-tab visible-job consistency from `35ebae0`;
  - Scanner execution clarity from PR #125 / `4598ecf`;
  - Scanner destination capacity from PR #127 / `21a7e5f`.
  - Scanner → Portfolio → Optimizer handoff provenance from PR #129 / `15a5f44`.
  - Scanner → Portfolio legacy-date handoff from PR #131 / `3a93afe`;
  - TWD Scanner raw-calendar coverage audit from PR #133 / `47ca2ea`;
  - Scanner edge-cache namespace invalidation from PR #135 / `f8c08ca`.

## Deployment Record

The protected PF-1D merge automatically triggered the configured Vercel production deployment and Cloudflare Worker deployment; both reported success at the merged SHA, and Cloudflare smoke covered Russell 2000, Portfolio v3 and Refinery v1. The direct edge smoke confirmed the new `/api/scan` namespace with MISS→HIT behavior. The sparse partial-calendar coverage assertion remains NOT VERIFIED.

## NOW / NEXT / BACKLOG / REJECT

### NOW

No active runtime implementation batch. Preserve `main` `f8c08ca` as the current functional recovery point; PF-1D, PF-1C, PF-1B and PF-1A are closed and repository/CI verified. The sparse partial-calendar coverage assertion remains NOT VERIFIED.

### NEXT

Re-run Product Functionality Review as a new single active batch only after querying current `main`, PRs, checks, deployment state and applicable contracts; keep the current Scanner audit table, exports, selection semantics, methodology, and destination contracts unchanged unless a new functional invariant is proven.

### BACKLOG

- distributed Refinery rate limiting;
- instrument/security master and regional factor routing;
- traceable theme provider/taxonomy;
- public sourcemap policy only as a dedicated build/deployment batch;
- exception-taxonomy hardening only when a reproducible invariant failure exists.

### REJECT FOR THE NEXT FUNCTIONAL BATCH

- arbitrary Cartesian experiment generation;
- recommendation, ranking, selection, sizing, optimization, or OOS claims;
- changing Phase 5/6 methodology without a separately reviewed contract;
- persistence migration merely for convenience;
- deleting active workflows/files or mixing unrelated cleanup into a functional release.

## Exact Resume Point

PF-1D is closed at main `f8c08ca`. The Worker now invalidates stale `/api/scan` cache entries after the PF-1C audit correction; candidate CI #674, post-main CI #675, Vercel production, Cloudflare Deploy #65 and direct MISS→HIT edge smoke passed. The sparse partial-calendar `0.5` output remains NOT VERIFIED in production. The next action is a fresh Product Functionality Review with one narrow scope lock; do not reopen PF-1D, PF-1C, PF-1B or PF-1A unless their invariants regress.
