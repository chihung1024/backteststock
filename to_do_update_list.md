# BacktestStock — Live Project Status & Handoff

> Repository-internal live execution authority. Mutable operational facts such as current SHA, PR/check state, deployment state and ruleset state must always be re-queried before acting. Durable architecture belongs in README/contracts/ADRs; detailed execution history remains reconstructable from Git/PR history.

## 1. Primary Goal

Complete **Phase 5 — Clustering & Redundancy** on top of the current production `main`, close it with post-main verification, and only then begin Phase 6.

The current Primary Active Batch is the **latest-main reconciliation of Phase 5 through PR #74**. Do not start Phase 6 or add unrelated feature work while this transition/final-validation path is open.

---

## 2. Current Production / Stable State

### Production `main`

- Repository: `chihung1024/backteststock`
- Current production main checkpoint: `af1cd83e41b23df745e27f39b9992e7a8a56fde0`
- PR #68 — V3 governance/document authority cleanup: **MERGED / CLOSED / POST-MAIN VERIFIED**.
- PR #70 / Issue #69 — common Portfolio comparison window + side-by-side comparison: **MERGED / CLOSED / POST-MAIN VERIFIED**.
- PR #70 production closeout passed:
  - post-merge release backup;
  - main Full CI #504;
  - Portfolio web CI #140;
  - Cloudflare deploy #47 including Russell + Portfolio v3 production smoke;
  - Vercel production status.

### Recovery anchors

- Last Phase 4 product closeout: `db3e692e3e4ce1962d6953988464947b35d5ef82`.
- Corrected Phase 5 parent checkpoint after PR #71: `bd3efe66a85893981dd19af9867fd0b3559951d5`.
- Latest production main before Phase 5 transition: `af1cd83e41b23df745e27f39b9992e7a8a56fde0`.

Do not infer deployment state from Git history alone. Re-query GitHub/Vercel/Cloudflare before any merge or closeout action.

---

## 3. Phase 5 Parent

- Parent PR: **#65** — `phase5/clustering-redundancy` -> `main`.
- Parent branch: `phase5/clustering-redundancy`.
- Parent checkpoint before latest-main reconciliation: `bd3efe66a85893981dd19af9867fd0b3559951d5`.
- PR #71 correctness/security convergence has already been squash-merged into this parent.
- #65 PR body is stale and must be refreshed after PR #74 lands; do not use its old NO-GO wording as current operational truth.

### Resolved correctness work already in parent

P5-CORR A–D are **CLOSED / PASS**:

- **M1 — bootstrap effective-sample identity**
  - one shared effective-sample preparation path;
  - fingerprint exact effective symbols/dates/values;
  - `ResearchDataset.dataset_hash` remains separate;
  - seed material includes effective fingerprint + clustering contract/linkage/cut/window/block/replicates.
- **M2 — factor boundary-month exclusion**
  - first/last represented calendar periods excluded;
  - no fabricated pre-window return;
  - minimum observation requirement enforced after exclusion.
- **M3 — factor computability vs verdict applicability**
  - separate `factor_computable`, `factor_model_scope`, `factor_corroboration_eligible`;
  - current U.S.-factor diagnostic remains fail-closed for verdict corroboration without traceable instrument-scope authority.
- **M4 — one global systematic relationship sample**
  - one deterministic common monthly sample for the returned relationship matrix;
  - betas and factor covariance refit on the same rows;
  - insufficient common sample fails closed.

Corrected identities:

```text
REFINERY_CLUSTERING_CONTRACT_VERSION = refinery-clustering-twd-2026-08-10.2
REFINERY_API_CONTRACT_VERSION        = refinery-v1
REFINERY_API_SCHEMA_VERSION          = refinery-v1-2026-08-10.3
```

No persisted Refinery workspace schema bump was required.

### P5-SEC — CLOSED / PASS

Precise dev-tool remediation already in the Phase 5 line:

- `wrangler 4.120.1`
- `@cloudflare/workers-types 5.20260810.1`
- `miniflare 5.20260804.0-alpha`
- transitive `undici 7.29.0`

No `--force`, no `--legacy-peer-deps`, no blanket `npm audit fix`.

---

## 4. Primary Active Batch — PR #74 Main Reconciliation

PR #74: **`chore: reconcile latest main into Phase 5 parent`**

- head branch: `phase5/reconcile-main-2026-08-11`
- base branch: `phase5/clustering-redundancy`
- risk: **R2 — significant branch transition / quantitative product integration**
- remains **Draft** until final transition gates and independent review pass.

### Recovery design

1. Recovery child was created exactly from Phase 5 parent checkpoint `bd3efe66...`.
2. GitHub three-way merge initially proved the only real conflict with latest main was generated `public/portfolio` output.
3. Generated Portfolio output was reset to the common ancestor on the recovery child only; Phase 5 source remained untouched.
4. Fresh sync PR #73 then proved source histories were mergeable and merged current `main@af1cd83...` into the recovery child with a **normal merge commit**, preserving both histories.
5. Combined source therefore contains simultaneously:
   - V3/general-document authority from #68;
   - Portfolio common-window feature from #70;
   - Phase 5 M1–M4 implementation/contracts/UI;
   - Phase 5 security remediation.
6. `public/portfolio` was then regenerated from the combined source tree, not hand-merged.

### Generated-asset reconciliation evidence

Initial combined-source validation proved:

- TypeScript/build PASS;
- Portfolio + Refinery source-contract tests PASS;
- Python/Ruff/Worker/score PASS;
- the only browser failures were the two Phase 5 E2E tests loading the intentionally stale pre-rebuild production bundle.

Controlled rebuild then required:

- same PR synthetic-merge context;
- two consecutive builds byte-identical;
- `package-lock.json` unchanged;
- generated diff restricted to one stale CSS + JS + map replacement, one new CSS + JS + matching map, and `public/portfolio/index.html`;
- generated-only bot commit;
- immediate restoration of the read-only Portfolio workflow.

After regeneration:

- Portfolio web CI #145: **PASS**;
- Full CI #509: **PASS**, including Phase 5 Playwright, Vercel config, D1 migrations and Cloudflare bundle dry-run;
- Vercel required status on that validation candidate: **SUCCESS**.

### Fresh security evidence after reconciliation

A read-only diagnostic run re-queried the current npm advisory database against the reconciled lockfile:

- `npm audit --json`: **0 vulnerabilities** across info/low/moderate/high/critical;
- `npm audit --omit=dev --json`: **0 vulnerabilities**;
- verified chain:
  - `@cloudflare/workers-types@5.20260810.1`
  - `wrangler@4.120.1`
  - `miniflare@5.20260804.0-alpha`
  - `undici@7.29.0`
- diagnostic Portfolio run #146: **PASS**, including TypeScript/build, 23 source-contract tests and production-asset integrity.

The diagnostic workflow additions are temporary and must not remain in the final PR diff.

---

## 5. Exact Remaining Work Before PR #74 May Merge

1. Restore `.github/workflows/portfolio-web-ci.yml` byte-for-byte to the accepted read-only baseline (`contents: read`; no audit/write temporary steps).
2. Treat the resulting branch tip as the new final candidate.
3. Confirm the #74 diff contains no temporary workflow machinery or unrelated Phase 6 work.
4. Run exact-head gates again:
   - Full CI;
   - Portfolio web CI;
   - required Vercel status.
5. Re-confirm preserved invariants:
   - current-main V3/general docs authority;
   - #70 common-window Portfolio source and tests;
   - Phase 5 M1–M4 source/contracts/UI;
   - security-remediated package/lock graph;
   - regenerated production bundle aligned to combined source.
6. V3 Same-AI Independent Review on the unchanged exact head; findings only BLOCKER / FOLLOW-UP / BACKLOG / REJECT.
7. If BLOCKER=0 and all required statuses remain green, transition PR #74 to Ready and merge it into `phase5/clustering-redundancy` with expected-head safety. Prefer a **normal merge** for this branch-transition PR if repository rules allow, so latest `main@af1cd83...` remains an actual ancestor of the Phase 5 parent.
8. Re-query #65 exact head immediately after #74 merge.

---

## 6. Phase 5 Parent Final Gate After PR #74

Once reconciliation is in the parent:

1. Refresh #65 PR body to current facts; remove obsolete M1–M4/security NO-GO wording.
2. Confirm no unique current authority remains only in historical PR #66; close #66 as superseded rather than wholesale merging stale general docs.
3. Run parent exact-head validation:
   - Full CI;
   - Portfolio web CI;
   - Playwright;
   - required Vercel;
   - fresh/recent security evidence;
   - release-backup pre-merge gate;
   - independent final Phase 5 review.
4. Findings:
   - BLOCKER = must fix before merge;
   - FOLLOW-UP = valid non-blocking follow-up;
   - BACKLOG = later phase;
   - REJECT = intentionally excluded from current scope.
5. If BLOCKER=0 and all required gates are green, mark #65 Ready and **expected-head squash merge #65 -> main**.

---

## 7. P5-CLOSE After Main Merge

Phase 5 is not CLOSED merely because #65 merges.

Required post-main evidence:

- new main SHA queried directly;
- main Full CI PASS;
- Portfolio web CI PASS;
- Cloudflare deploy PASS;
- applicable Russell / Portfolio / Refinery production smoke PASS;
- Vercel production status green;
- post-merge release backup PASS;
- limitations recorded:
  - full-period Phase 5 evidence is not out-of-sample validation;
  - factor model remains a scoped U.S.-factor diagnostic;
  - instrument master/regional factor routing/theme provider remain later work.
- update this handoff to **Phase 5 CLOSED / PASS** and set the exact Phase 6 start point.

Only after this closeout may Phase 6 begin.

---

## 8. Phase Roadmap

| Phase / Batch | Objective | Status |
| --- | --- | --- |
| -1 | Governance & Architecture Hardening | CLOSED / PASS |
| 0 | Quant Authority Freeze | CLOSED / PASS |
| 1 | ResearchDatasetV1 | CLOSED / PASS |
| 2 | Risk Mathematics Core | CLOSED / PASS |
| 3 | Read-only Refinery API | CLOSED / PASS |
| 4 | Refinery Diagnostic UI | CLOSED / PASS |
| DOC-CLEAN / #68 | V3 governance + document authority cleanup | CLOSED / PASS / POST-MAIN VERIFIED |
| Portfolio #69/#70 | Common comparison window + side-by-side results | CLOSED / PASS / POST-MAIN VERIFIED |
| 5 / #65 | Clustering & Redundancy | **ACTIVE — latest-main reconciliation/final validation** |
| P5-CORR A–D | M1–M4 correctness convergence | CLOSED / PASS |
| P5-SEC | dependency security remediation | CLOSED / PASS; reconciliation audit reconfirmed 0 vulnerabilities |
| P5 main transition / #74 | integrate current main into corrected Phase 5 parent | **ACTIVE** |
| P5 parent VAL/MERGE | final #65 gates and merge | NEXT |
| P5-CLOSE | post-main deployment/smoke/backup/limitations | NEXT |
| 6 | Marginal Experiments | PLANNED / BLOCKED BY P5-CLOSE |
| 7 | Walk-Forward / Research Validity | PLANNED |
| 8 | Selection Policy | PLANNED |
| 9 | Sizing | PLANNED |
| 10 | Validated Exhaustive Integration | PLANNED |
| 11 | Point-in-Time Universe / Fundamentals | PLANNED |

---

## 9. NOW / NEXT / BACKLOG / REJECT

### NOW

- Finish PR #74 final workflow restoration, exact-head validation and independent transition review.
- Merge #74 into Phase 5 parent only with BLOCKER=0 and expected-head safety.

### NEXT

- Refresh and final-validate parent PR #65.
- Pre-merge recovery gate + independent Phase 5 review.
- Merge #65 -> main if all required evidence is green.
- P5-CLOSE post-main verification.

### BACKLOG

- instrument/security master and regional factor routing;
- traceable theme taxonomy/provider;
- globally distributed Refinery rate limiting;
- Vercel preview quota optimization;
- Actions immutable-SHA pinning review;
- point-in-time Universe/fundamentals in Phase 11;
- stale historical GitHub Actions registry cleanup when a supported mutation path is available.

### REJECT for current scope

- magic 0–100 redundancy score;
- KEEP/TRIM/REPLACE before later validation;
- Phase 6 marginal experiments inside Phase 5;
- sizing/HRP/ERC/min-var inside Phase 5;
- Exhaustive selection integration before validation;
- OOS claims from full-period winners;
- untraceable themes;
- branch-protection/Vercel bypass;
- forced dependency remediation;
- hand-merging generated JS/CSS bundles;
- wholesale merge of stale PR #66 general documentation;
- further V3 governance expansion without a documented Reopen Condition.

---

## 10. Exact Resume Point

Primary active batch: **PR #74 — latest-main reconciliation into Phase 5 parent**.

1. Verify current PR #74 head and that the fresh security diagnostic completed successfully.
2. Restore Portfolio web CI to the accepted read-only baseline and confirm temporary audit steps leave the final diff.
3. Re-run exact-head Full CI + Portfolio web CI + Vercel.
4. Freeze candidate and perform V3 Same-AI Independent Review over the transition invariants and exact diff.
5. If any BLOCKER: record -> exit reviewer mode -> fix -> new head -> validate -> focused re-review.
6. If BLOCKER=0 and all required statuses are green: Ready + expected-head normal merge #74 into `phase5/clustering-redundancy` if allowed.
7. Re-query #65 and proceed to parent final validation/merge/closeout.
