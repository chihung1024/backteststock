# BacktestStock — Live Project Status & Handoff

> Repository-internal live execution authority. Mutable operational facts such as current SHA, PR/check state, deployment state and ruleset state must always be re-queried before acting. Durable architecture belongs in README/contracts/ADRs; detailed execution history remains reconstructable from Git/PR history.

## 1. Primary Goal

Complete **Phase 5 — Clustering & Redundancy**, merge it safely to current production `main`, complete post-main verification, and only then begin Phase 6.

**Primary Active Batch: PR #65 parent final validation / merge / closeout.**

Do not start Phase 6 or add unrelated feature work while Phase 5 remains open.

---

## 2. Production / Stable State

### Production `main`

- Repository: `chihung1024/backteststock`.
- Current production checkpoint before Phase 5 merge: `af1cd83e41b23df745e27f39b9992e7a8a56fde0`.
- PR #68 — V3 governance/document authority cleanup: **CLOSED / PASS / POST-MAIN VERIFIED**.
- PR #70 / Issue #69 — Portfolio common comparison window + side-by-side comparison: **CLOSED / PASS / POST-MAIN VERIFIED**.
- #70 production closeout passed main Full CI, Portfolio web CI, Cloudflare deploy/smoke, Vercel and post-merge backup.

### Recovery anchors

- Phase 4 closeout: `db3e692e3e4ce1962d6953988464947b35d5ef82`.
- Phase 5 corrected-parent checkpoint after PR #71: `bd3efe66a85893981dd19af9867fd0b3559951d5`.
- Latest production main integrated into Phase 5: `af1cd83e41b23df745e27f39b9992e7a8a56fde0`.
- Latest-main reconciliation merge into Phase 5 parent: `b52904119a2c7b85ef704ad362a50a15d0efabfd` before final status-document convergence.

Always re-query the actual remote head before merge. Do not treat these checkpoints as a substitute for current remote state.

---

## 3. Phase 5 Parent — PR #65

- PR: **#65 — `feat: add Phase 5 clustering and redundancy diagnostics`**.
- head branch: `phase5/clustering-redundancy`.
- base: current `main`.
- risk: **R2 — quantitative methodology / API evidence / production UI integration**.
- status: **ACTIVE — FINAL EXACT-HEAD VALIDATION**.
- PR #65 must remain Draft until the final exact-head gates and independent review pass.

### Branch ancestry is reconciled

Latest-main reconciliation is complete:

- recovery child: `phase5/reconcile-main-2026-08-11`;
- PR #74 latest-main reconciliation: **MERGED / PASS**;
- current production `main@af1cd83...` is now an actual ancestor of the Phase 5 parent;
- GitHub compare after reconciliation: `behind_by=0`, Phase 5 branch is ahead only;
- #65 final diff therefore represents Phase 5 work rather than reintroducing already-deployed #68/#70 changes.

### Historical docs child

PR #66 is **CLOSED / SUPERSEDED / NOT MERGED**.

Its useful Phase5-specific evidence has been promoted into current contracts/review records. Its obsolete general README/Deployment/TODO and old different-GitHub-account review wording must not be wholesale merged back into the parent.

---

## 4. P5-CORR — CLOSED / PASS

### M1 — bootstrap effective-input identity

- one shared effective-sample preparation path;
- exact effective symbols/dates/values fingerprint;
- `ResearchDataset.dataset_hash` remains separate;
- seed includes effective fingerprint + contract/linkage/cut/window/block/replicates;
- primitive verifies supplied fingerprint against the actual effective sample.

### M2 — factor boundary-month exclusion

- `boundary-month-exclusion-v1`;
- first and last represented calendar periods excluded;
- no invented exchange-calendar completeness authority;
- no fabricated pre-window return;
- minimum observation rule applies after exclusion.

### M3 — factor computability vs verdict applicability

Separate:

- `factor_computable`;
- `factor_model_scope`;
- `factor_corroboration_eligible`.

Current policy remains `fail_closed_without_traceable_instrument_scope_v1`; diagnostic factor evidence may display but cannot upgrade redundancy verdicts without traceable eligibility authority.

### M4 — one global systematic relationship sample

- individual diagnostics may keep individual valid samples;
- one returned matrix uses one global common monthly sample;
- relationship betas and `Sigma_F` use exactly the same rows;
- insufficient common sample fails closed;
- no pairwise-cell sample switching.

Corrected identities:

```text
REFINERY_CLUSTERING_CONTRACT_VERSION = refinery-clustering-twd-2026-08-10.2
REFINERY_API_CONTRACT_VERSION        = refinery-v1
REFINERY_API_SCHEMA_VERSION          = refinery-v1-2026-08-10.3
```

No persisted Refinery workspace schema bump was introduced.

---

## 5. P5-SEC — CLOSED / PASS

Precise dev-tool remediation:

- `wrangler@4.120.1`;
- `@cloudflare/workers-types@5.20260810.1`;
- `miniflare@5.20260804.0-alpha`;
- transitive `undici@7.29.0`.

No `--force`, `--legacy-peer-deps` or blanket `npm audit fix` was used.

Fresh post-reconciliation security evidence from read-only diagnostic run #146:

- full `npm audit --json`: **0 vulnerabilities**;
- production-only `npm audit --omit=dev --json`: **0 vulnerabilities**;
- info / low / moderate / high / critical all 0;
- installed remediated chain verified explicitly.

`package.json` and `package-lock.json` survived latest-main reconciliation without dependency drift from the corrected Phase 5 parent.

---

## 6. Latest-main / Generated-asset Reconciliation — CLOSED / PASS

The only actual three-way conflict between production main and corrected Phase 5 was generated `public/portfolio` output.

Resolution discipline:

1. generated assets were neutralized on a recovery child rather than hand-merged;
2. GitHub standard three-way merge then proved source histories compatible;
3. production #70 Portfolio source and Phase 5 Refinery source existed simultaneously;
4. combined TypeScript/source-contract validation passed before bundle regeneration;
5. `public/portfolio` was rebuilt from the combined source in the normal PR synthetic-merge context;
6. two consecutive builds had to be byte-identical;
7. generated diff was restricted to the expected CSS/JS/map/index replacement;
8. temporary write/audit workflow logic was removed;
9. final read-only Portfolio workflow returned to content SHA `304ba63b61b96850f3c9d8b650b7f12da39789ab`.

PR #74 final evidence:

- Full CI #512: PASS;
- Portfolio web CI #148: PASS;
- Vercel required status: SUCCESS;
- fresh npm audit evidence: 0 / 0 vulnerabilities;
- V3 transition review: PASS / BLOCKER=0;
- normal merge into Phase 5 parent completed.

---

## 7. Parent Final Validation Evidence Before This Status Refresh

On reconciled parent checkpoint `b529041...`:

- Portfolio web CI #149: **PASS**;
- Full CI #513: **PASS**;
- required Vercel status: **SUCCESS**;
- Release Backup Gates #368: **PASS**;
  - `create-pre-merge-backup` actually executed and succeeded;
  - post-merge job correctly remained skipped before merge.

These checks establish that reconciliation is sound, but the final merge candidate is the **new exact head after this status-document convergence**. Therefore all required exact-head checks must be re-queried/rerun once more before #65 leaves Draft.

---

## 8. Exact Remaining Work for PR #65

1. Query the new #65 exact head after final status-document convergence.
2. Confirm final diff remains Phase5-only relative to current main and no temporary workflow/helper file exists.
3. Require exact-head:
   - Full CI PASS;
   - Portfolio web CI PASS;
   - required Vercel SUCCESS;
   - pre-merge release backup still valid/successful on the current base.
4. Re-confirm fresh security evidence remains applicable because package/lock blobs are unchanged; rerun only if dependency blobs or advisory evidence materially changes.
5. Freeze candidate and perform **V3 Same-AI Independent Review** from current exact diff/contracts/tests/security/recovery evidence.
6. Findings only: BLOCKER / FOLLOW-UP / BACKLOG / REJECT.
7. Any BLOCKER: exit reviewer mode -> fix root cause -> new head -> rerun applicable gates -> focused re-review.
8. If BLOCKER=0 and all required statuses remain green:
   - mark #65 Ready;
   - final TOCTOU re-check;
   - **expected-head squash merge #65 -> main**.

---

## 9. P5-CLOSE — Required After #65 Main Merge

Phase 5 is not CLOSED merely because the PR merges.

Required post-main evidence:

- query new main SHA;
- main Full CI PASS;
- Portfolio web CI PASS;
- Cloudflare deploy PASS;
- applicable Russell / Portfolio / Refinery production smoke PASS;
- Vercel production status green;
- post-merge release backup PASS;
- record known limitations:
  - full-period Phase 5 evidence is not out-of-sample validation;
  - factor model remains a scoped U.S.-factor co-movement diagnostic;
  - instrument master/regional factor routing/theme provider remain later work.
- update this file to **Phase 5 CLOSED / PASS** and set the exact Phase 6 resume point.

Only after this closeout may Phase 6 begin.

---

## 10. Roadmap

| Phase / Batch | Objective | Status |
| --- | --- | --- |
| -1 | Governance & Architecture Hardening | CLOSED / PASS |
| 0 | Quant Authority Freeze | CLOSED / PASS |
| 1 | ResearchDatasetV1 | CLOSED / PASS |
| 2 | Risk Mathematics Core | CLOSED / PASS |
| 3 | Read-only Refinery API | CLOSED / PASS |
| 4 | Refinery Diagnostic UI | CLOSED / PASS |
| DOC-CLEAN / #68 | V3 governance + document authority cleanup | CLOSED / PASS / POST-MAIN VERIFIED |
| Portfolio #69/#70 | common comparison window + side-by-side results | CLOSED / PASS / POST-MAIN VERIFIED |
| P5-CORR A–D | M1–M4 correctness convergence | CLOSED / PASS |
| P5-SEC | security remediation | CLOSED / PASS |
| P5 main reconciliation / #74 | integrate current main into corrected Phase 5 | CLOSED / PASS |
| 5 / #65 | Clustering & Redundancy | **ACTIVE — FINAL VALIDATION / MERGE** |
| P5-CLOSE | post-main deploy/smoke/backup/limitations | NEXT |
| 6 | Marginal Experiments | PLANNED / BLOCKED BY P5-CLOSE |
| 7 | Walk-Forward / Research Validity | PLANNED |
| 8 | Selection Policy | PLANNED |
| 9 | Sizing | PLANNED |
| 10 | Validated Exhaustive Integration | PLANNED |
| 11 | Point-in-Time Universe / Fundamentals | PLANNED |

---

## 11. NOW / NEXT / BACKLOG / REJECT

### NOW

- Final exact-head validation and Independent Review for #65.
- Expected-head squash merge only if BLOCKER=0 and all gates are green.

### NEXT

- P5-CLOSE post-main verification.
- Update live handoff to Phase 5 CLOSED / PASS.
- Start Phase 6 only after closeout.

### BACKLOG

- instrument/security master and regional factor routing;
- traceable theme taxonomy/provider;
- globally distributed Refinery rate limiting;
- Vercel preview quota optimization;
- Actions immutable-SHA pinning review;
- point-in-time Universe/fundamentals in Phase 11;
- stale historical Actions registry cleanup when a supported mutation path is available.

### REJECT for Phase 5

- magic 0–100 redundancy score;
- KEEP/TRIM/REPLACE;
- Phase 6 marginal experiments;
- sizing / HRP / ERC / min-var;
- Exhaustive selection integration;
- OOS claims from full-period evidence;
- untraceable themes;
- branch-protection/Vercel bypass;
- forced dependency remediation;
- hand-merging generated production bundles;
- reopening superseded PR #66 general docs;
- further V3 governance expansion without a documented Reopen Condition.

---

## 12. Exact Resume Point

Primary active batch: **PR #65 final exact-head validation**.

1. Query #65 current head / mergeability / changed-file scope.
2. Wait for final exact-head Full CI + Portfolio web CI + Vercel after this document refresh.
3. Verify Release Backup gate and security evidence applicability.
4. Freeze candidate; perform final V3 Independent Review.
5. BLOCKER=0 + all required statuses green -> Ready -> TOCTOU check -> expected-head squash merge to `main`.
6. Execute P5-CLOSE post-main verification.
7. Only after Phase 5 is recorded CLOSED / PASS begin Phase 6.
