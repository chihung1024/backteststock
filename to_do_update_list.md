# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff only. Re-query mutable GitHub, CI, Vercel, Cloudflare and runtime state before an important action. Durable API/UI semantics live in the current contracts; Git/PR/Issue/Actions retain completed execution history.

## 1. Current Goal

**Primary active batch: P6-C — Phase 6 / Issue #77 exact-head independent merge-readiness review.**

Implementation is published as Draft PR [#116](https://github.com/chihung1024/backteststock/pull/116) against remote `main` `797919369bec776dceb09fe26d60b897839d7668`. Its tested functional head is `df6b92e18a5e8ed0a2d74449bb598eade3db78ee`; the candidate remains unmerged and must not be confused with draft PR #115 (the unrelated Edge-cache contract correction).

The active goal is merge-readiness evidence for the functional delivery. Documentation is limited to the current public contract and this handoff; do not restart a broad cleanup or planning program while Phase 6 gates are active.

## 2. Recovery / Scope Boundary

- functional worktree: `backteststock-phase6-p6a`, candidate branch `candidate-phase6-refinery-marginal-2026-08-13`; local functional head `0a1258a5906ea09471649703741fbffe46a53d1c` and remote tested functional commit `df6b92e18a5e8ed0a2d74449bb598eade3db78ee` share tree `c6fcb3bc041caf7fc923514b8eb6a4dc485426ee`; re-query #116 before any action because a handoff-only commit may sit above that tree;
- recovery tag before this batch: `backup-post-pr114-797919369bec`;
- original documentation worktree contains separate user-owned Phase 5 wording edits and must not be staged with Phase 6;
- open draft PR #115 is out of scope and must neither be rebased, merged nor bundled into the Phase 6 candidate.

No direct production merge or deployment is authorized by this handoff. The deliberate `candidate-*` branch and Draft PR are published; the remaining gate is exact-head independent review, then an explicit merge authorization.

## 3. Implemented Phase 6 Surface

### P6-A backend

- `experiment_plan` is optional and accepts only explicit normalized `remove_one`, `add_one`, and `replace_one` operations;
- validation rejects invalid operation shape, duplicate normalized operations, invalid baseline membership, baseline re-addition, removing below two candidates, more than 12 operations and an experiment union over 24 symbols;
- the one authoritative market-history batch includes baseline, distinct experiment externals and an optional distinct benchmark;
- Phase 3–5 baseline preparation/analysis remains unchanged. With no plan, `Phase6RefineryService` delegates to exact Phase 5 behavior;
- the plan builds a union ResearchDataset from that fetched batch, freezes one daily and one weekly full-union finite complete-case matrix, then makes every baseline/variant a column selection from those matrices;
- union provenance (`experiment_union_dataset_hash`) stays distinct from daily/weekly frozen effective-sample SHA-256 identities;
- only unweighted Ledoit-Wolf/effective-dimension/multi-horizon correlation/average+complete point-clustering evidence is produced for variants; no implicit allocation, bootstrap, redundancy verdict, rank, recommendation, selection, sizing or OOS claim;
- experiment-only membership/data failure or frozen-sample insufficiency fails the marginal layer closed while preserving a separately valid existing baseline;
- shared retained-pair correlations have an executable `1e-12` invariance guard and pair-impact output is bounded by the union cap.

### P6-B UI

- the Refinery workspace offers a minimal explicit plan editor and shows only requested operation order;
- plan state is page-scoped, excluded from `backteststock.refinery.workspace.v1`, and invalidates stale preflight/analyze evidence on change;
- client usage remains only the existing Refinery preflight/analyze routes;
- preflight shows union/common-sample readiness and experiment-only failures; results show frozen samples, baseline/variant/delta structural evidence and bounded pair impacts;
- the UI contains no market-data fetch, quantitative calculation, sorting into a winner or action label; wide Phase 6 tables use labelled horizontal scroll regions.

## 4. Contract Decision

```text
REFINERY_API_SCHEMA_VERSION         = refinery-v1-2026-08-10.3
PHASE6_MARGINAL_CONTRACT_VERSION    = refinery-phase6-marginal-v1-2026-08-13.1
```

Schema `.3` remains the Phase 3–5 envelope for planless parity. The opt-in marginal payload has a separate public version identity. Any externally visible Phase 6 semantic change requires review/bump of the Phase 6 marginal contract; it must not silently reinterpret `.3`.

The canonical current details are in:

- `docs/research/REFINERY_API_V1.md`
- `docs/research/REFINERY_UI_V1.md`
- `docs/research/README.md`

## 5. Current Verification Evidence

Passed on the final local functional candidate tree:

- Ruff for `apps/api`, `apps`, and `tests`;
- full Python regression (`271 passed`), including focused Phase 6/API coverage;
- Portfolio/Refinery source-contract suite (`28 passed`), including the Phase 6 static browser boundary;
- Portfolio TypeScript check and Vite production build, including committed-asset regeneration;
- repository JavaScript syntax checks;
- Worker route/runtime suite (`73 passed`);
- score/coverage suite (`12 passed`).

Local browser Playwright remains **environment-blocked**: this runner has no system Chromium and its restricted download returned a corrupt archive. That is not a candidate blocker: GitHub Actions CI #631 passed the full browser user-flow suite (48 cases) on `df6b92e…`, alongside Python, Worker, source-contract, asset-drift, Vercel-configuration, local D1-migration and Cloudflare-bundle gates. Vercel's Git preview is **Ready** with zero unresolved feedback. Release Backup Gates are skipped on a Draft PR by the existing event condition; no merge or production backup has been run.

### Candidate CI correction / root cause

- **Symptom:** CI #630 timed out in the established 100-candidate Phase 5 browser flow because `資料預檢` was disabled.
- **Failure point / root cause:** the new Phase 6 client validator applied its 24-symbol experiment-union limit even when `experimentPlan` was empty, unintentionally invalidating the existing no-plan 2–100 candidate workflow.
- **Fix:** `validateRefineryExperimentPlan()` now returns no Phase 6 issues for an empty plan; a source-contract regression locks that no-plan behavior. The Vite bundle was regenerated.
- **Regression evidence:** exact remote fix head `df6b92e…` passed CI #631, including the previously failing 100-candidate browser case. No workaround or gate weakening was used.

## 6. Independent Falsification Status

The pre-fix review found no confirmed calculation defect and identified / closed these acceptance-coverage gaps:

- direct frozen-sample primitive and stable-ID parity for all three operation forms;
- explicit operation-cap rejection;
- proof that union provenance remains independent from frozen sample identity;
- browser workflow coverage for Remove/Add/Replace order and narrow-screen containment.

The no-plan validation correction created a new exact candidate head, so the prior review conclusion does not automatically carry forward. P6-C independent review is now active and must cover the final head. Residual observation, not a current blocker: unexpected internal invariant exceptions still use the existing generic API error boundary. Do not expand exception taxonomy in this release without concrete failure evidence; consider it only as a separately scoped hardening item.

## 7. NOW / NEXT / BACKLOG / REJECT

### NOW

1. complete independent adversarial review of the final #116 head against Issue #77, the Phase 6 contracts and CI evidence;
2. if there are zero BLOCKER findings, report `READY TO MERGE` and wait for explicit authorization to merge the exact reviewed head.

### NEXT

After explicit merge authorization and a successful expected-head merge, verify post-main CI/backup and production routing. Only then run the bounded Scanner → Optimizer → Portfolio → Refinery integration pass.

### BACKLOG

- distributed Refinery rate limiting;
- instrument/security master and regional factor routing;
- traceable theme provider/taxonomy;
- public sourcemap policy change only as a dedicated build/deployment batch;
- exception-taxonomy hardening only when an actual invariant failure provides a reproducible cause.

### REJECT FOR THIS BATCH

- arbitrary Cartesian experiment generation;
- any recommendation, preferred operation, ranking, selection, sizing, optimization or OOS claim;
- Phase 5 bootstrap/redundancy verdict recomputation per variant;
- plan persistence or cross-workspace Scanner/Portfolio conversion;
- deleting active workflows/files or changing PR #115 while validating Phase 6.

## 8. Exact Resume Point

Continue from the Phase 6 worktree only. Re-query `main`, #116's exact head, CI / Vercel state and review threads. If `main` or the PR head moved, re-evaluate/revalidate deliberately; otherwise finish P6-C independent review. Do not merge until the user explicitly authorizes the expected reviewed head.

**Primary Active Batch = P6-C independent merge-readiness review. No other functional batch is active.**
