# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff only. Re-query mutable GitHub, CI, Vercel, Cloudflare and runtime state before an important action. Durable API/UI semantics live in the current contracts; Git/PR/Issue/Actions retain completed execution history.

## 1. Current Goal

**Primary active batch: Phase 6 / Issue #77 — common-sample marginal Remove-One / Add-One / Replace-One MVP.**

Implementation and local validation are converging on an isolated Phase 6 worktree based on remote `main` `797919369bec776dceb09fe26d60b897839d7668`. This batch remains unmerged and must not be confused with draft PR #115 (the unrelated Edge-cache contract correction).

The active goal is functional delivery and candidate validation. Documentation is limited to the current public contract and this handoff; do not restart a broad cleanup or planning program while Phase 6 gates are active.

## 2. Recovery / Scope Boundary

- functional worktree: `backteststock-phase6-p6a`, candidate branch `candidate-phase6-refinery-marginal-2026-08-13` (created from the isolated internal Phase 6 commit);
- recovery tag before this batch: `backup-post-pr114-797919369bec`;
- original documentation worktree contains separate user-owned Phase 5 wording edits and must not be staged with Phase 6;
- open draft PR #115 is out of scope and must neither be rebased, merged nor bundled into the Phase 6 candidate.

No direct production merge or deployment is authorized by this handoff. The deliberate `candidate-*` branch is created from the exact green tree; pushing it and opening one Draft PR are the next publication gates.

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

Passed on the final local candidate tree:

- Ruff for `apps/api`, `apps`, and `tests`;
- full Python regression (`271 passed`), including focused Phase 6/API coverage;
- Portfolio/Refinery source-contract suite (`28 passed`), including the Phase 6 static browser boundary;
- Portfolio TypeScript check and Vite production build, including committed-asset regeneration;
- repository JavaScript syntax checks;
- Worker route/runtime suite (`73 passed`);
- score/coverage suite (`12 passed`).

Full browser Playwright execution is currently **environment-blocked**, not product-failed: this runner has no system Chromium and the Playwright Chromium download repeatedly returned a corrupt/truncated archive through its restricted network path. Candidate GitHub CI must run the normal browser suite; a missing or failed browser gate blocks merge.

## 6. Independent Falsification Status

Completed review found no confirmed calculation defect. It identified and closed these acceptance-coverage gaps:

- direct frozen-sample primitive and stable-ID parity for all three operation forms;
- explicit operation-cap rejection;
- proof that union provenance remains independent from frozen sample identity;
- browser workflow coverage for Remove/Add/Replace order and narrow-screen containment.

Residual observation, not a current blocker: unexpected internal invariant exceptions still use the existing generic API error boundary. Do not expand exception taxonomy in this release without concrete failure evidence; consider it only as a separately scoped hardening item.

## 7. NOW / NEXT / BACKLOG / REJECT

### NOW

1. push the reviewed candidate branch and open one Draft PR against current `main`;
2. use the candidate PR to obtain required GitHub CI, Vercel preview and backup evidence. Browser E2E must pass there before merge consideration.

### NEXT

After all candidate gates and independent review pass, merge with expected-head protection, then verify post-main CI/backup and production routing. Only then run the bounded Scanner → Optimizer → Portfolio → Refinery integration pass.

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

Continue from the Phase 6 worktree only. First re-query `main`, Issue #77 and the Draft PR list. If `main` moved, rebase/revalidate deliberately; otherwise commit the reviewed exact tree, create/push one `candidate-*` branch and Draft PR. Treat GitHub `validate`, Vercel and browser E2E as merge gates, not post-merge cleanup.

**Primary Active Batch = P6 candidate validation. No other functional batch is active.**
