# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff only. Re-query mutable GitHub, CI, Vercel, Cloudflare and runtime state before an important action. Durable API/UI semantics remain in their current contracts; Git/PR/Issue/Actions retain the execution history.

## Current Status

**UX-1B Scanner destination capacity — CLOSED / DEPLOYED / POST-MAIN VERIFIED (R1).**

- [PR #127](https://github.com/chihung1024/backteststock/pull/127) passed exact-head candidate CI #656, was marked Ready, and was squash-merged to main as [21a7e5ff4bccbc77616bd6dec7397c12b7f81867](https://github.com/chihung1024/backteststock/commit/21a7e5ff4bccbc77616bd6dec7397c12b7f81867) on 2026-08-13.
- Candidate CI [#656](https://github.com/chihung1024/backteststock/actions/runs/31700763590) passed JavaScript checks, Portfolio/Refinery contracts, Chromium E2E and all repository validation gates.
- Post-main CI [#657](https://github.com/chihung1024/backteststock/actions/runs/31701086294) passed on the merged head. Vercel reported success and [Deploy Cloudflare Worker #62](https://github.com/chihung1024/backteststock/actions/runs/31701086369) passed Russell 2000, Portfolio v3 and Refinery v1 production smoke tests.
- The merge push triggered the repository's configured production workflows automatically; no manual deployment command, protection bypass or direct production write was used.
- UX-1A remains closed at [4598ecf1a2870bcec7b71c69b5d7642601e0c55a](https://github.com/chihung1024/backteststock/commit/4598ecf1a2870bcec7b71c69b5d7642601e0c55a).

Primary Goal completed: make Scanner execution scale, pending-first-result state, and downstream destination capacity explicit without changing data, quant, defaults, selection semantics, retry/resume behavior or persistence contracts.

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

- Current functional recovery baseline: `main` [`21a7e5ff4bccbc77616bd6dec7397c12b7f81867`](https://github.com/chihung1024/backteststock/commit/21a7e5ff4bccbc77616bd6dec7397c12b7f81867).
- Previous verified baseline: [`4598ecf1a2870bcec7b71c69b5d7642601e0c55a`](https://github.com/chihung1024/backteststock/commit/4598ecf1a2870bcec7b71c69b5d7642601e0c55a).
- Rollback for UX-1B is a normal revert of PR #127; UX-1A remains a normal revert of PR #125. No data migration, persistence migration or schema change is involved.
- The current functional baseline includes:
  - Phase 6 Refinery marginal experiments from [#116](https://github.com/chihung1024/backteststock/pull/116), merged as `72b15c4`;
  - Portfolio shared-link tab behavior from [#117](https://github.com/chihung1024/backteststock/pull/117), merged as `f96ef33`;
  - Scanner retry batch labels from [#118](https://github.com/chihung1024/backteststock/pull/118), merged as `6856736`;
  - Legacy Backtest cache-policy correction from [#121](https://github.com/chihung1024/backteststock/pull/121), merged as `8aff7b0`;
  - Scanner cross-tab visible-job consistency from `35ebae0`;
  - Scanner execution clarity from PR #125 / `4598ecf`;
  - Scanner destination capacity from PR #127 / `21a7e5f`.

## Deployment Record

The public Scanner assets were released only after the protected merge. The merge push automatically triggered the configured Vercel production deployment and Cloudflare Worker deployment; both completed successfully, including the scoped Russell 2000, Portfolio v3 and Refinery v1 smoke suite. No manual deployment or protection bypass was used. If a future change must be absolutely non-deploying, the push-triggered deployment workflows need an explicit gate before merging public-asset changes.

## NOW / NEXT / BACKLOG / REJECT

### NOW

No active runtime implementation batch. Preserve `21a7e5f` as the current functional recovery point and re-query remote state before any new work.

### NEXT

Begin the planned Product Functionality Review as the next separate batch. Classify findings as NOW / NEXT / BACKLOG / REJECT; keep the current Scanner audit table, exports, selection semantics, methodology, and destination contracts unchanged unless a new functional invariant is proven.

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

UX-1B has no remaining implementation or production blocker. The current main head is 21a7e5f with candidate CI #656, post-main CI #657, Vercel success and Cloudflare smoke success. Before the next Product Functionality Review batch, query current `main`, active PRs, checks, deployment state and the applicable contracts; then define one narrow batch with its own validation and rollback path.
