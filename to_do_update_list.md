# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff only. Re-query mutable GitHub, CI, Vercel, Cloudflare and runtime state before an important action. Durable API/UI semantics remain in their current contracts; Git/PR/Issue/Actions retain the execution history.

## Current Status

**UX-1A Scanner execution clarity is ACTIVE.** Local candidate: `feat/scanner-execution-clarity` / `072a5bd63e856f908b967ac5d1d1c175df112e0d`, based on remote `main` [`35ebae01adaeb65f967a59eb0881ef886b2b7ffc`](https://github.com/chihung1024/backteststock/commit/35ebae01adaeb65f967a59eb0881ef886b2b7ffc), re-verified on 2026-08-13. It is not pushed, merged, or deployed.

Primary Goal: make Scanner execution scale and the pre-first-result state explicit without changing data, quant, default all-candidate scanning, batch/retry, local persistence, or handoff contracts.

Current Batch — **UX-1A / R1**:

- show the exact ticker count and deterministic 100-ticker batch count after Universe filtering or manual input;
- show a pending-first-result state instead of zero-value metric cards/table before any ticker settles;
- preserve cancel/resume semantics and correctly describe an empty paused job;
- add focused browser regressions for the plan, the pending→settled transition, and empty filter output.

Local `npm run check`, `npm run test:worker` (75 tests), `npm run test:score` (12 tests), diff check, and Playwright test discovery pass. Local Chromium E2E is **NOT VERIFIED**: the sandbox lacks the Playwright browser and the browser download endpoint is blocked. Exact-head GitHub CI remains the required browser-validation gate before merge. Publishing this candidate for CI is currently blocked pending explicit approval to push this exact branch to `chihung1024/backteststock` and create a draft PR.

The current functional baseline includes:

- Phase 6 Refinery marginal experiments from [#116](https://github.com/chihung1024/backteststock/pull/116), merged as `72b15c4`.
- Shared `?model` / `?handoff` links initially open Portfolio without preventing a later user switch to Refinery, fixed by [#117](https://github.com/chihung1024/backteststock/pull/117), merged as `f96ef33`.
- Scanner retry batch labels use immutable original ticker positions and use `本次批次` for non-contiguous subsets, fixed by [#118](https://github.com/chihung1024/backteststock/pull/118), merged as `6856736`.
- Legacy Backtest is consistently uncached at both Worker layers while Scanner retains its existing cache policy, fixed by [#121](https://github.com/chihung1024/backteststock/pull/121), merged as `8aff7b0`.
- Scanner UI state remains bound to the visible scan job across browser tabs, fixed by [`35ebae0`](https://github.com/chihung1024/backteststock/commit/35ebae01adaeb65f967a59eb0881ef886b2b7ffc).

Issues [#77](https://github.com/chihung1024/backteststock/issues/77) and [#85](https://github.com/chihung1024/backteststock/issues/85) are closed as completed.

## Last Known-Good Evidence

- [#117 post-main CI](https://github.com/chihung1024/backteststock/actions/runs/31662009374), [Cloudflare deployment](https://github.com/chihung1024/backteststock/actions/runs/31662009395), and Vercel passed; production Russell, Portfolio v3, and Refinery v1 smoke tests passed.
- [#118 exact-head CI](https://github.com/chihung1024/backteststock/actions/runs/31662267456) passed, including Chromium E2E, D1 migration, and Cloudflare bundle validation.
- [#121 candidate CI](https://github.com/chihung1024/backteststock/actions/runs/31664285971) and [Vercel Preview](https://vercel.com/cchungs-projects/back-test/AXHdLdPgNtQ2muzEoewg5rsTKu7a) passed. Post-main [CI](https://github.com/chihung1024/backteststock/actions/runs/31664505910) and [Cloudflare deployment](https://github.com/chihung1024/backteststock/actions/runs/31664505794) passed; production Russell, Portfolio v3, and Refinery v1 smoke tests are green.

## Scope Boundary

- Functional correctness and production verification are the first priority.
- Keep each change isolated, exact-head reviewed, fully gated, and reversible.
- Do not bundle documentation cleanup, workflow removal, cache-policy changes, or unrelated refactors with a functional batch.
- The Phase 6 public contracts remain in `docs/research/REFINERY_API_V1.md`, `docs/research/REFINERY_UI_V1.md`, and `docs/research/README.md`.

## NOW / NEXT / BACKLOG / REJECT

### NOW

Obtain explicit approval to push local candidate `072a5bd63e856f908b967ac5d1d1c175df112e0d` on `feat/scanner-execution-clarity` to `chihung1024/backteststock` and create a draft PR. Then require exact-head GitHub CI (including Chromium E2E) before any merge decision. Do not deploy before merge and post-main verification.

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

With explicit publication approval, push and validate local candidate `072a5bd63e856f908b967ac5d1d1c175df112e0d` on `feat/scanner-execution-clarity`. `main` `35ebae0` is the recovery baseline; preserve it until a separately reviewed candidate has passed CI and, after merge, production verification.
