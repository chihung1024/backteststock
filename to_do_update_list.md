# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff only. Re-query mutable GitHub, CI, Vercel, Cloudflare and runtime state before an important action. Durable API/UI semantics remain in their current contracts; Git/PR/Issue/Actions retain the execution history.

## Current Status

**UX-1A Scanner execution clarity — CLOSED / DEPLOYED / POST-MAIN VERIFIED (R1).**

- [PR #125](https://github.com/chihung1024/backteststock/pull/125) passed exact-head GitHub CI and Vercel Preview, was marked Ready, and was squash-merged to `main` as [`4598ecf1a2870bcec7b71c69b5d7642601e0c55a`](https://github.com/chihung1024/backteststock/commit/4598ecf1a2870bcec7b71c69b5d7642601e0c55a) on 2026-08-13.
- Candidate CI [#652](https://github.com/chihung1024/backteststock/actions/runs/31693019799) and post-main CI [#653](https://github.com/chihung1024/backteststock/actions/runs/31693330484) both passed, including Chromium E2E, D1 migration validation and Cloudflare dry-run.
- Vercel production deployment for `4598ecf` completed successfully. [Deploy Cloudflare Worker #61](https://github.com/chihung1024/backteststock/actions/runs/31693330458) deployed the Worker/static assets and passed Russell 2000, Portfolio v3 and Refinery v1 production smoke tests.

Primary Goal completed: make Scanner execution scale and the pre-first-result state explicit without changing data, quant, default all-candidate scanning, batch/retry, local persistence, or contract semantics.

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

- Current functional recovery baseline: `main` [`4598ecf1a2870bcec7b71c69b5d7642601e0c55a`](https://github.com/chihung1024/backteststock/commit/4598ecf1a2870bcec7b71c69b5d7642601e0c55a).
- Previous verified baseline: [`35ebae01adaeb65f967a59eb0881ef886b2b7ffc`](https://github.com/chihung1024/backteststock/commit/35ebae01adaeb65f967a59eb0881ef886b2b7ffc).
- Rollback for UX-1A is a normal revert of PR #125; no data migration, persistence migration or schema change is involved.
- The current functional baseline includes:
  - Phase 6 Refinery marginal experiments from [#116](https://github.com/chihung1024/backteststock/pull/116), merged as `72b15c4`;
  - Portfolio shared-link tab behavior from [#117](https://github.com/chihung1024/backteststock/pull/117), merged as `f96ef33`;
  - Scanner retry batch labels from [#118](https://github.com/chihung1024/backteststock/pull/118), merged as `6856736`;
  - Legacy Backtest cache-policy correction from [#121](https://github.com/chihung1024/backteststock/pull/121), merged as `8aff7b0`;
  - Scanner cross-tab visible-job consistency from `35ebae0`;
  - Scanner execution clarity from PR #125 / `4598ecf`.

## Deployment Record

The public Scanner assets were released only after the protected merge. Normal Git-integrated Vercel production deployment completed successfully, followed by the Cloudflare Worker deployment and its scoped production smoke suite. No manual deployment or protection bypass was used.

## NOW / NEXT / BACKLOG / REJECT

### NOW

No active runtime implementation batch. Preserve `4598ecf` as the current functional recovery point and re-query remote state before any new work.

### NEXT

Evaluate UX-1B as a separate R1 batch: Scanner result readability and explicit destination capacities (Portfolio vs Optimizer). Keep the current complete audit table, exports, selection semantics, and methodology visible.

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

UX-1A has no remaining implementation or production blocker. Before starting UX-1B, query current `main`, active PRs, checks, deployment state and the applicable Scanner contract; then define a separate, narrow R1 batch with its own validation and rollback path.
