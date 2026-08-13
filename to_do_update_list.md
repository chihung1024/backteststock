# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff only. Re-query mutable GitHub, CI, Vercel, Cloudflare and runtime state before an important action. Durable API/UI semantics remain in their current contracts; Git/PR/Issue/Actions retain the execution history.

## Current Status

**No active production functional change.** The last known-good functional release is [`8aff7b0fa67b667e3335ffb8352f18775cba3228`](https://github.com/chihung1024/backteststock/commit/8aff7b0fa67b667e3335ffb8352f18775cba3228), verified on 2026-08-13. Re-query `main` before a change.

The current functional baseline includes:

- Phase 6 Refinery marginal experiments from [#116](https://github.com/chihung1024/backteststock/pull/116), merged as `72b15c4`.
- Shared `?model` / `?handoff` links initially open Portfolio without preventing a later user switch to Refinery, fixed by [#117](https://github.com/chihung1024/backteststock/pull/117), merged as `f96ef33`.
- Scanner retry batch labels use immutable original ticker positions and use `本次批次` for non-contiguous subsets, fixed by [#118](https://github.com/chihung1024/backteststock/pull/118), merged as `6856736`.
- Legacy Backtest is consistently uncached at both Worker layers while Scanner retains its existing cache policy, fixed by [#121](https://github.com/chihung1024/backteststock/pull/121), merged as `8aff7b0`.

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

No active functional repair. Before starting any change, re-query `main`, open PRs/issues, CI, Vercel, Cloudflare, and the affected runtime path.

### NEXT

Run a bounded end-to-end regression pass across Scanner → Optimizer → Portfolio → Refinery. Treat any newly observed user-facing failure as its own small root-cause batch; do not infer a change from this handoff alone.

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

Start with current remote truth, then select one observable functional path and verify it end to end. `main` `8aff7b0` is the recovery baseline; preserve it until a separately reviewed candidate has passed CI and production verification.
