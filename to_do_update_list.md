# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff only. Re-query mutable GitHub, CI, Vercel, Cloudflare and runtime state before an important action. Durable API/UI semantics remain in their current contracts; Git/PR/Issue/Actions retain the execution history.

## Current Status

**UX-1A Scanner execution clarity — VALIDATING (R1).**

- Draft PR: [#125](https://github.com/chihung1024/backteststock/pull/125), branch `feat/scanner-execution-clarity`, targeting `main`.
- The implementation candidate was published as `66f83f59f01ea38743e609e55e8eb43d32e643b1`, based on `main` [`35ebae01adaeb65f967a59eb0881ef886b2b7ffc`](https://github.com/chihung1024/backteststock/commit/35ebae01adaeb65f967a59eb0881ef886b2b7ffc).
- That implementation head passed GitHub CI [#651](https://github.com/chihung1024/backteststock/actions/runs/31683643871), including Chromium E2E, and its Vercel Preview was ready.
- This handoff correction is an intentional status-only follow-up on the same PR. Its new exact head must receive a fresh green `validate` and Vercel status before readiness or merge. It is not merged or deployed at the time of this record.

Primary Goal: make Scanner execution scale and the pre-first-result state explicit without changing data, quant, default all-candidate scanning, batch/retry, local persistence, or handoff contracts.

## Current Batch — UX-1A / R1

### In Scope

- show the exact ticker count and deterministic 100-ticker batch count after Universe filtering or manual input;
- show a pending-first-result state instead of zero-value metric cards/table before any ticker settles;
- preserve cancel/resume semantics and correctly describe an empty paused job;
- add focused browser regressions for the plan, the pending→settled transition, and empty filter output;
- correct this live handoff so the published PR, validation gate and next deployment path are unambiguous.

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
- `to_do_update_list.md`: this status-only handoff correction.

## Verification

- Local implementation validation passed: `npm run check`, `npm run test:worker` (75 tests), `npm run test:score` (12 tests), and `git diff --check`.
- Local Chromium execution was unavailable because the sandbox lacked the Playwright browser; this is not treated as a green gate.
- GitHub CI #651 for implementation head `66f83f5` passed: Python compile/lint/tests, JavaScript/Worker/score checks, Portfolio build/contracts, Chromium E2E, Vercel configuration, local D1 migrations and Cloudflare dry-run.
- **Required now:** exact-head CI and Vercel Preview for the status-correction commit. Do not reuse the previous success for a changed head.

## Stable State / Rollback

- Current recovery baseline: `main` [`35ebae01adaeb65f967a59eb0881ef886b2b7ffc`](https://github.com/chihung1024/backteststock/commit/35ebae01adaeb65f967a59eb0881ef886b2b7ffc).
- Rollback for UX-1A is a normal revert of PR #125; no data migration, persistence migration or schema change is involved.
- The current functional baseline includes:
  - Phase 6 Refinery marginal experiments from [#116](https://github.com/chihung1024/backteststock/pull/116), merged as `72b15c4`;
  - Portfolio shared-link tab behavior from [#117](https://github.com/chihung1024/backteststock/pull/117), merged as `f96ef33`;
  - Scanner retry batch labels from [#118](https://github.com/chihung1024/backteststock/pull/118), merged as `6856736`;
  - Legacy Backtest cache-policy correction from [#121](https://github.com/chihung1024/backteststock/pull/121), merged as `8aff7b0`;
  - Scanner cross-tab visible-job consistency from `35ebae0`.

## Deployment Decision

The public Scanner assets change, so this batch requires post-main deployment verification. The normal repository path is intentionally:

`validated PR → squash merge to main → Git-integrated Vercel production deployment + Deploy Cloudflare Worker workflow → scoped production smoke`.

No pre-merge production deployment is used: it would make a non-`main` candidate externally live before the final protected merge gate. Production deployment is permitted only after the exact merged SHA is known and post-main automation is observable.

## NOW / NEXT / BACKLOG / REJECT

### NOW

1. Wait for the new exact PR head's GitHub `validate` and Vercel Preview statuses.
2. Re-check PR mergeability, ruleset, review threads and exact SHA. If green and no blocker, mark #125 Ready for review and squash-merge it to `main`.
3. Verify post-main CI, Vercel production deployment, Cloudflare Worker deployment and the scoped production smoke tests. Do not manually bypass or duplicate the normal deployment path.

### NEXT

After UX-1A closes, evaluate UX-1B as a separate R1 batch: Scanner result readability and explicit destination capacities (Portfolio vs Optimizer). Keep the current complete audit table, exports, selection semantics, and methodology visible.

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

Use [PR #125](https://github.com/chihung1024/backteststock/pull/125) as the sole UX-1A candidate. Query its current head rather than relying on a cached SHA. When its exact-head `validate` and Vercel statuses are green and no review blocker exists, mark Ready, squash-merge to `main`, then verify the normal post-main Vercel and Cloudflare deployments before declaring the batch CLOSED.
