# BacktestStock — Live Project Status & Handoff

> Repository-internal live execution authority. Mutable operational facts (current SHA, PR/check state, deployment, ruleset) must be re-queried before acting. Durable architecture belongs in README/contracts/ADRs; detailed execution history remains reconstructable from Git/PR history.

## 1. Primary Goal

Complete the current **main documentation/governance transition**, then converge the already-corrected Phase 5 parent onto that `main` baseline, close Phase 5, and only then begin Phase 6.

A separate high-priority Portfolio correctness improvement — **Issue #69 / PR #70: Common Comparison Window + side-by-side portfolio comparison** — is already implemented/validated on a stacked branch and must be transitioned to `main` after the documentation baseline is stable.

---

## 2. Current Operational Snapshot

### `main`

- Repository: `chihung1024/backteststock`
- Production candidate branch: `main`
- Current documentation/governance transition base: `main@b116b73c7dbc189fb0eae34624925fe2e16b81ae`
- Last product-code Phase 4 closeout before that governance-only commit: `db3e692e3e4ce1962d6953988464947b35d5ef82`
- PR #67 / `b116b73...` accidentally replaced the complete playbook with only the V3 Final Hardening fragment. PR #68 repairs this and is therefore an R2 governance-document correctness change.

### Primary Active Merge/Transition Batch — DOC-CLEAN / PR #68

- Branch: `docs/v3-governance-doc-cleanup`
- PR: **#68** — `docs: restore V3 governance and clean stale documentation`
- Risk: **R2 — Significant** because engineering-governance/document authority changes.
- Content scope: complete V3 governance restoration, documentation authority/index cleanup, stale document removal, live handoff convergence.
- Prior exact candidate passed Full CI and independent content review but its required Vercel status was left red by the previous free-tier daily deployment quota.
- This live-handoff refresh intentionally creates a new meaningful candidate so CI/Vercel can revalidate after quota recovery; do not use an empty/no-op retry commit.
- Before merge: query #68 exact head/checks again, perform focused exact-head review of this live-state-only delta, then expected-head squash merge if blocker=0.

### Phase 5 parent — corrected implementation already merged into parent branch

- Parent PR: **#65** — `phase5/clustering-redundancy` -> `main`
- PR remains the Phase 5 merge authority.
- Correctness-convergence child PR **#71** has been expected-head squash-merged into the Phase 5 parent.
- #71 merge SHA on `phase5/clustering-redundancy`: `bd3efe66a85893981dd19af9867fd0b3559951d5`.
- P5-CORR A–D, P5-SEC and child-level P5-VAL were completed before that merge.
- #71 pre/post release-backup workflow executed under the `release-backup` gate; re-query remote release/run state when audit detail is needed.
- Parent #65 must **not** merge to `main` until #68 establishes the current main documentation/governance authority and #65 is reconciled/revalidated against that new main.

### Historical Phase 5 docs child — PR #66

- PR #66 contains useful Phase5-specific historical review evidence but also obsolete general documentation/reviewer-gate prose.
- Its Phase5-specific contract/review content was promoted through #71.
- Do **not** wholesale merge #66.
- After verifying no unique current evidence remains only in #66, close it as superseded rather than reintroducing stale README/Deployment/TODO/governance content.

### High-priority Portfolio correctness — Issue #69 / PR #70

- Issue #69: common comparison window + simultaneous side-by-side portfolio results.
- PR #70: `fix/portfolio-common-comparison-window`, intentionally stacked on #68.
- Exact reviewed implementation checkpoint: `7eda99e6383c44359fd5e49c89f7f21b5ec5f83c`.
- Full CI #461 PASS; Portfolio web CI #99 PASS; V3 independent review PASS / BLOCKER=0.
- Semantics: when >=2 sibling portfolios are runnable, recompute every portfolio from one shared intersection window; no post-hoc curve clipping/relabeling; single-portfolio full-history behavior preserved; no common window fails explicitly; browser shows server metrics only.
- After #68 lands, retarget/sync #70 to `main`, re-evaluate material diff, rerun required gates, then merge/close #69 before lower-priority feature expansion.

---

## 3. Stable State / Recovery

### Product baseline

Last production-closeout product checkpoint before current unmerged work:

- Phase 4 implementation #63: `e59c1402011c7e8c940f806e79c9ce4b0da3f47f`
- Phase 4 closeout #64: `db3e692e3e4ce1962d6953988464947b35d5ef82`
- pre backup: `backup-pre-pr63-17f0dd88aeae`
- post backup: `backup-post-pr63-e59c1402011c`

### Phase 5 correction checkpoint

- Original Phase 5 correction recovery point: `0dd3c12b3097975bdcd4d36aeab5504987efbe29`
- Corrected parent merge checkpoint after #71: `bd3efe66a85893981dd19af9867fd0b3559951d5`

Do not infer production deployment from branch merge alone. `main`, required statuses, deployment and smoke state must be queried directly.

---

## 4. Documentation Authority

1. `AI_PROJECT_PLAYBOOK.md` — engineering governance; V3.0 is the locked/frozen baseline once PR #68 lands.
2. `README.md` — durable product/architecture/run/test/deploy overview.
3. `to_do_update_list.md` — current Phase/Batch/blockers/exact next action.
4. `docs/PROJECT_DOCUMENTATION_POLICY.md` — documentation authority/freshness/cleanup rules.
5. `docs/README.md` + `docs/research/README.md` — canonical navigation.
6. `docs/quant/*`, `docs/research/*`, ADRs — versioned semantic/architecture authorities.
7. GitHub/Vercel/Cloudflare remote state — current operational truth for mutable facts.

If documentation conflicts with remote state, classify documentation drift and repair the live authority; do not infer operational facts from stale prose.

---

## 5. DOC-CLEAN Scope

### Completed content work

- Restored the agreed **complete V3.0** playbook rather than a patch-only or newly invented compressed substitute.
- Integrated the accepted Final Hardening controls without reopening governance architecture.
- Added `docs/PROJECT_DOCUMENTATION_POLICY.md`, `docs/README.md`, `docs/research/README.md`.
- Reworked root/API/deployment documentation around current Portfolio v3 + Refinery v1 boundaries.
- Marked Phase -1 and Portfolio migration plans historical where appropriate.
- Removed demonstrably superseded live-tree documents:
  - `docs/OPTIMIZER_IMPLEMENTATION_STATUS.md`
  - `docs/EXHAUSTIVE_OPTIMIZER_V2.md`
  - `docs/PORTFOLIO_OPTIMIZER_MVP.md`
- Retained historical material that still contains unique audit/contract value.
- Audited workflow source: only five current YAML workflows remain and each has a real responsibility.

### GitHub Actions registry residue

GitHub Actions UI/API still contains many historical one-off workflow registrations whose YAML source files are already absent. Treat those as operational registry residue, not source-tree authority. Clean only through a supported GitHub UI/API mutation; do not delete the five useful current workflows merely to reduce counts.

---

## 6. Phase 5 Correctness Convergence — RESOLVED in Parent Branch

The four previously frozen correctness blockers have been implemented, tested and independently reviewed through PR #71.

### M1 — bootstrap effective-sample identity — RESOLVED

- shared effective sample preparation: numeric -> canonical symbols -> trailing window -> non-finite->NaN -> complete-case;
- fingerprint exact effective symbols/dates/values only;
- `ResearchDataset.dataset_hash` remains independent and is never repurposed;
- primitive verifies supplied fingerprint matches its effective sample;
- seed material includes input fingerprint + clustering version/linkage/cut/window/block/replicates;
- API evidence exposes explicit bootstrap input fingerprint/window.

### M2 — factor boundary-month exclusion — RESOLVED

- policy: `boundary-month-exclusion-v1`;
- first/last represented calendar periods excluded;
- no exchange-calendar completeness claim;
- no fabricated pre-window return;
- minimum 36 observations required after exclusion.

### M4 — one global systematic relationship sample — RESOLVED

- individual diagnostics may retain individual valid samples;
- matrix uses one deterministic global common monthly sample across matrix members + factor frame;
- relationship betas refit and `Sigma_F` computed on exactly those rows;
- insufficient common sample fails closed;
- no pairwise-cell fallback;
- observations/start/end/common-sample fingerprint exposed.

### M3 — factor computability vs verdict applicability — RESOLVED

Separate:

- `factor_computable`
- `factor_model_scope`
- `factor_corroboration_eligible`

Current scope/policy:

- model = `U.S.-factor co-movement diagnostic`;
- current corroboration policy = `fail_closed_without_traceable_instrument_scope_v1`;
- computable diagnostic beta/R²/systematic correlation may remain visible;
- without traceable instrument-scope authority, factor evidence cannot upgrade a redundancy verdict.

### Corrected identities

```text
REFINERY_CLUSTERING_CONTRACT_VERSION = refinery-clustering-twd-2026-08-10.2
REFINERY_API_CONTRACT_VERSION        = refinery-v1
REFINERY_API_SCHEMA_VERSION          = refinery-v1-2026-08-10.3
```

No persisted Refinery workspace schema bump was introduced because persisted request/input state did not change.

---

## 7. P5-SEC — RESOLVED in Parent Branch

Initial audit evidence on #71:

- full npm dependency graph: 3 vulnerability nodes = 1 high + 2 moderate;
- production-only audit: **0 vulnerabilities**;
- vulnerable path was dev tooling only: `wrangler@4.115.0 -> miniflare@4.20260722.1 -> undici@7.28.0`.

Remediation:

- no `--force`, no `--legacy-peer-deps`, no blanket audit fix;
- precise peer-compatible updates:
  - `wrangler 4.115.0 -> 4.120.1`
  - `@cloudflare/workers-types 5.20260729.1 -> 5.20260810.1`
- patched transitive `undici@7.29.0`;
- post-fix full audit: **0 vulnerabilities**;
- post-fix production-only audit: **0 vulnerabilities**;
- exact-head Full CI included Worker tests + Cloudflare bundle dry-run and passed.

Security focused review: PASS / BLOCKER=0.

---

## 8. Phase Roadmap

| Phase / Batch | Objective | Current status |
| --- | --- | --- |
| -1 | Governance & Architecture Hardening | CLOSED / PASS |
| 0 | Quant Authority Freeze | CLOSED / PASS |
| 1 | ResearchDatasetV1 | CLOSED / PASS |
| 2 | Risk Mathematics Core | CLOSED / PASS |
| 3 | Read-only Refinery API | CLOSED / PASS |
| 4 | Refinery Diagnostic UI | CLOSED / PASS |
| DOC-CLEAN / #68 | V3 governance + document authority cleanup | **ACTIVE MERGE TRANSITION** |
| Portfolio #69/#70 | Common comparison window + side-by-side results | **IMPLEMENTED / VALIDATED / STACKED** |
| 5 / #65 | Clustering & Redundancy | **ACTIVE — CORRECTIONS MERGED TO PARENT; MAIN TRANSITION PENDING** |
| P5-CORR A–D | M1–M4 correctness convergence | CLOSED / PASS |
| P5-SEC | dependency security triage/remediation | CLOSED / PASS |
| P5-VAL child | #71 exact-head final validation | CLOSED / PASS before parent merge |
| P5 parent VAL/MERGE | reconcile new main + final #65 gates | NEXT |
| 6 | Marginal Experiments | PLANNED / BLOCKED BY PHASE 5 CLOSEOUT |
| 7 | Walk-Forward / Research Validity | PLANNED |
| 8 | Selection Policy | PLANNED |
| 9 | Sizing | PLANNED |
| 10 | Validated Exhaustive Integration | PLANNED |
| 11 | Point-in-Time Universe / Fundamentals | PLANNED |

---

## 9. Required Transition Order

1. **DOC-CLEAN / #68**
   - validate latest meaningful TODO refresh;
   - required Vercel green;
   - focused exact-head review;
   - expected-head squash merge to `main`.
2. **#70 / Portfolio correctness transition**
   - retarget/sync to new `main`;
   - re-evaluate material diff;
   - exact-head CI/Vercel/review;
   - merge + production closeout + close #69.
3. **Phase 5 parent #65**
   - sync/reconcile the new `main` V3/docs authority into `phase5/clustering-redundancy` without resurrecting #66 stale general docs;
   - verify #71 corrected code/contracts remain intact;
   - full parent exact-head CI + Portfolio web + Playwright + required Vercel + backup + independent review;
   - expected-head squash merge #65 to `main`;
   - post-main deploy/smoke/backup/limitations closeout.
4. **Phase 6** only after Phase 5 is CLOSED.

If #70 and #65 have no code-level dependency, their preparation may occur in parallel, but only one Primary Active implementation/merge batch should be mutated at a time.

---

## 10. NOW / NEXT / BACKLOG / REJECT

### NOW

- Finish #68 retry candidate validation/review/merge with required Vercel green.

### NEXT

- Transition and merge validated Portfolio #70 / close #69.
- Reconcile/revalidate Phase 5 parent #65 against the new main documentation/governance baseline.
- Phase 5 parent merge + post-main closeout.

### BACKLOG

- instrument/security master and regional factor routing;
- traceable theme taxonomy/provider;
- globally distributed Refinery rate limiting;
- Vercel preview quota optimization;
- Actions immutable-SHA pinning review;
- point-in-time Universe/fundamentals in Phase 11;
- stale historical Actions registry cleanup when a supported mutation path is available.

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
- deleting useful current workflows merely to reduce Actions counts;
- further V3 governance expansion without a documented Reopen Condition.

---

## 11. Exact Resume Point

Primary active batch: **DOC-CLEAN / PR #68**.

1. Query #68 exact head, mergeability, Full CI, Vercel required status and Release Backup applicability after this live-handoff refresh.
2. Confirm the new delta since the previously reviewed #68 candidate is limited to this live-state handoff refresh.
3. Final risk remains R2 because the overall PR changes governance/document authority.
4. Enter Same-AI Independent Review Mode; focused review the latest delta + re-confirm prior content-review conclusions.
5. Findings: BLOCKER / FOLLOW-UP / BACKLOG / REJECT.
6. If BLOCKER=0 and required checks are green: use expected-head squash merge #68 to `main`.
7. Re-query `main` and dependent PR bases immediately after merge.
8. Continue with #70 transition, then Phase 5 parent #65 transition/validation/merge/closeout.
