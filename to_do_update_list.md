# BacktestStock — Live Project Status & Handoff

> Repository-internal live execution authority. Mutable operational facts (current SHA, PR/check state, ruleset, deployment) must be re-queried before acting. Durable architecture belongs in README/ADRs/contracts; detailed history remains reconstructable from Git/PR history.

## 1. Primary Goal

Complete **Phase 5 — Clustering & Redundancy** correctly, close it, then begin Phase 6.

Current one-time prerequisite Batch: **DOC-CLEAN** — restore the agreed complete V3 governance baseline, remove demonstrably useless/stale documentation, and converge documentation authority before Phase 5 resumes.

## 2. Current Operational Snapshot

### Production / main

- Repository: `chihung1024/backteststock`
- Production candidate branch: `main`
- DOC-CLEAN base: `main@b116b73c7dbc189fb0eae34624925fe2e16b81ae`
- Last product-code Phase 4 closeout before that governance-only commit: `db3e692e3e4ce1962d6953988464947b35d5ef82`
- PR #67 / `b116b73...` replaced the complete playbook with only the V3 Final Hardening patch (`+160/-2563`), leaving an incomplete governance file. DOC-CLEAN treats this as an R2 governance-document correctness defect.

### Current Batch — DOC-CLEAN

- Branch: `docs/v3-governance-doc-cleanup`
- PR: **#68** — `docs: restore V3 governance and clean stale documentation`
- Risk Class: **R2 — Significant** because engineering-governance/document authority changes.
- Current candidate head: **query PR #68 / GitHub immediately before validation or merge**. Do not store a self-referential branch-head SHA in this file because updating this file necessarily changes that SHA.
- Status: **VALIDATING**.

### Phase 5 work paused during DOC-CLEAN

- Parent implementation PR #65: `phase5/clustering-redundancy` -> `main`
  - last queried head: `0dd3c12b3097975bdcd4d36aeab5504987efbe29`
  - OPEN / DRAFT / not merge-ready.
- Child docs PR #66: `docs/phase5-convergence-plan` -> `phase5/clustering-redundancy`
  - last queried head: `1a5364c414f724706fa89eec60f44391bfa3439b`
  - contains useful Phase 5-specific contract/review work, but its review-gate prose predates V3 and must be transitioned before use.

Do not merge #65/#66 until DOC-CLEAN lands and Phase 5 is reconciled with the new `main` baseline.

---

## 3. Stable State / Recovery

Last Known Good product state is Phase 4 CLOSED/PASS.

- Phase 4 implementation PR #63 merge: `e59c1402011c7e8c940f806e79c9ce4b0da3f47f`
- Phase 4 closeout PR #64 merge: `db3e692e3e4ce1962d6953988464947b35d5ef82`
- pre backup: `backup-pre-pr63-17f0dd88aeae`
- post backup: `backup-post-pr63-e59c1402011c`

PR #67 changed governance documentation only; product runtime code did not intentionally change. DOC-CLEAN source rollback is a revert of PR #68 if needed; product recovery remains anchored to the Phase 4 checkpoints above.

---

## 4. Documentation Authority

1. `AI_PROJECT_PLAYBOOK.md` — engineering governance; V3.0 is GOVERNANCE BASELINE LOCKED / FROZEN after DOC-CLEAN.
2. `README.md` — durable product/architecture/run/test/deploy overview.
3. `to_do_update_list.md` — current Phase/Batch/blockers/exact next action.
4. `docs/PROJECT_DOCUMENTATION_POLICY.md` — documentation authority/freshness/cleanup rules.
5. `docs/README.md` and `docs/research/README.md` — canonical navigation.
6. `docs/quant/*`, `docs/research/*`, ADRs — semantic/architecture authorities.
7. Current GitHub/Vercel/Cloudflare remote state — operational truth for mutable facts.

If documents conflict with remote state, classify documentation drift; do not infer a new plan from stale prose.

---

## 5. DOC-CLEAN Completed Scope

### Governance repair

- Restored the **agreed full V3.0 structure** rather than a patch-only or newly compressed substitute.
- Integrated only the accepted Final Hardening controls: Docs Risk Escalation, Risk Classification/higher-risk default/final reclassification, Same-AI review isolation + reviewer/implementer separation, competence-insufficiency handling, governance transition/non-retroactivity + Grandfather anti-bypass.
- V3.0 ends in Governance Freeze; no further feature expansion without a documented Reopen Condition.

### Documentation convergence

- Added `docs/PROJECT_DOCUMENTATION_POLICY.md`.
- Added `docs/README.md`.
- Added `docs/research/README.md`.
- Reworked root README around current Portfolio v3 + Refinery v1 architecture and clear document authority.
- Updated `apps/api/README.md` so merged Refinery v1 is current while unmerged Phase 5 is not presented as `main` methodology.
- Updated `docs/DEPLOYMENT.md` with real Refinery POST smoke surfaces and V3 risk-proportional gates.
- Updated `docs/EXHAUSTIVE_OPTIMIZER_V3.md` to remove stale rollout/deployment-state prose.
- Marked `docs/PHASE_MINUS1_GOVERNANCE.md` explicitly HISTORICAL / CLOSED / PASS.
- Marked `docs/portfolio-migration/README.md` historical; PR7 is not an active instruction.
- Compressed this live handoff instead of retaining hundreds of lines of chronological execution detail.

### Deleted as demonstrably superseded live-tree files

- `docs/OPTIMIZER_IMPLEMENTATION_STATUS.md`
- `docs/EXHAUSTIVE_OPTIMIZER_V2.md`
- `docs/PORTFOLIO_OPTIMIZER_MVP.md`

Their history remains in Git.

### Deliberately retained

- `docs/PHASE_MINUS1_GOVERNANCE.md` — unique historical Phase -1 evidence.
- `docs/portfolio-migration/*` — still contains unique Portfolio ledger/API/cutover evidence; do not delete until current versioned authorities demonstrably absorb it.
- All five actual `.github/workflows/*.yml` files — each has a current responsibility.

---

## 6. GitHub Actions Cleanup Finding

Current source tree contains only **5** workflow YAMLs, all useful:

1. full CI;
2. Portfolio web CI;
3. Cloudflare deploy;
4. generic Release Backup Gates;
5. Universe membership update.

GitHub Actions registry/API nevertheless reports **54 active workflow registrations**, including many historical one-off `apply-*`, `diagnose-*`, and temporary Phase workflows whose YAML files are no longer in `main`.

- Source-tree workflow garbage: already absent.
- Historical registrations/run history: operational UI/API residue, not current source authority.
- Available GitHub connector exposes no supported disable/delete-workflow mutation, so those stale registrations were **not** falsely claimed removed.
- Future cleanup may disable/remove only registrations with no source workflow, using a supported GitHub UI/API path; do not touch the five current workflows.

---

## 7. Phase Roadmap

| Phase | Objective | Status |
| --- | --- | --- |
| -1 | Governance & Architecture Hardening | CLOSED / PASS |
| 0 | Quant Authority Freeze | CLOSED / PASS |
| 1 | ResearchDatasetV1 | CLOSED / PASS |
| 2 | Risk Mathematics Core | CLOSED / PASS |
| 3 | Read-only Refinery API | CLOSED / PASS |
| 4 | Refinery Diagnostic UI | CLOSED / PASS |
| DOC-CLEAN | V3 governance/document cleanup | **VALIDATING / PR #68** |
| 5 | Clustering & Redundancy | ACTIVE / PAUSED FOR DOC-CLEAN / PR #65 |
| 6 | Marginal Experiments | PLANNED / BLOCKED BY PHASE 5 |
| 7 | Walk-Forward / Research Validity | PLANNED |
| 8 | Selection Policy | PLANNED |
| 9 | Sizing | PLANNED |
| 10 | Validated Exhaustive Integration | PLANNED |
| 11 | Point-in-Time Universe / Fundamentals | PLANNED |

Historical merge checkpoints:

- Phase -1 #52: `9135bdd33a46afee4f4a12b9030ca4504114924f`
- continuity #53: `bc8ce721a82938c32ed8b9af7c91fba25a161f8a`
- Phase 0 #54/#55: `68cbd58d570ce7d806c2a73903b5bdb506c9bae1` / `d173f1d15a671e7d2f3c096a56e7ee3ef9f0a183`
- Phase 1 #57/#58: `7cf3fdcfa248d47a036419213da0acce594ada7c` / `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`
- Phase 2 #59/#60: `724075ddbb0383f7889e4b622a95a57769d5558c` / `4cea3b18fdce7db5e464196172f59930abf6b7d9`
- Phase 3 #61/#62: `6e18726dcc1383e0b839e4bd0bded46e720e2707` / `17f0dd88aeaeff61f84ac6598c7b6258135d4ca4`
- Phase 4 #63/#64: `e59c1402011c7e8c940f806e79c9ce4b0da3f47f` / `db3e692e3e4ce1962d6953988464947b35d5ef82`

Use Git/PR history for detailed old Batch logs; do not expand this file back into a chronological transcript.

---

## 8. Phase 5 Correctness Blockers — Frozen Specification

These are real correctness/methodology blockers and are **not removed** by the V3 reviewer-policy change.

### M1 — Bootstrap effective-sample identity

- Shared `prepare_bootstrap_sample(weekly_returns, window)`: numeric -> canonical symbol order -> trailing window -> inf->NaN -> complete-case.
- Fingerprint exact effective sample: symbols + dates + values.
- Seed includes input fingerprint, clustering contract version, linkage, cut distance, window, block weeks, replicates.
- Never mutate/repurpose `ResearchDataset.dataset_hash`.
- Rename ambiguous `dataset_hash` primitive input to `input_fingerprint` equivalent.
- Public evidence field explicit, e.g. `bootstrap_input_fingerprint_sha256`.
- Tests: permutation invariant; effective-sample value/date mutation changes seed; pre-window mutation does not; complete-case-excluded row does not; ResearchDataset hash distinct; methodology params affect seed.

### M2 — Factor boundary-month exclusion

- No invented exchange-calendar completeness authority.
- Exclude first and last represented calendar periods from native daily-return -> monthly factor regression.
- Compound only interior months and join factors there.
- Preserve minimum observation requirement after exclusion.
- No fabricated pre-window/backfilled return to rescue a boundary month.

### M3 — Factor computability vs applicability

Separate:

- `factor_computable`
- `factor_model_scope`
- `factor_corroboration_eligible`

USD denomination/history may make U.S.-factor regression computable; absent authoritative instrument taxonomy it does not make the evidence eligible to upgrade redundancy verdicts. Diagnostic beta/R²/systematic relationship may remain visible with explicit scope/reason.

### M4 — Global common relationship sample

- Individual diagnostic exposures may retain individual valid samples.
- One returned systematic relationship matrix uses one global common monthly index across included valid assets and factor frame.
- Refit relationship betas and factor covariance on the same rows.
- Fail closed if common observations insufficient.
- Expose relationship sample count/start/end/fingerprint.

### Version consequence

- clustering methodology `.1` -> `refinery-clustering-twd-2026-08-10.2`
- request contract remains `refinery-v1`
- public API schema `.2` -> `refinery-v1-2026-08-10.3`
- no persisted workspace schema bump unless input persistence changes.

---

## 9. Phase 5 Execution Order After DOC-CLEAN

1. Transition/sync new `main` V3/docs baseline into Phase 5 parent branch.
2. Re-evaluate PR #66; preserve useful Phase 5 contract/review content but remove obsolete different-account reviewer blocker. If conflict cost is excessive, close #66 as superseded and recreate only the clean Phase 5 docs delta.
3. **P5-CORR-A — M1**.
4. **P5-CORR-B — M2 + M4**.
5. **P5-CORR-C — M3**.
6. **P5-CORR-D — methodology/API versions + docs/types**.
7. **P5-SEC — `npm audit --json` reachability triage; no force upgrade**.
8. **P5-VAL — targeted tests + full applicable CI + Portfolio web + Playwright + required Vercel green + recovery evidence + V3 Independent Review**.
9. **P5-MERGE — expected-head squash merge #65; no bypass**.
10. **P5-CLOSE — post-main verification, limitations, CLOSED status, exact Phase 6 resume point**.
11. Only then start Phase 6.

---

## 10. V3 Transition for Existing Phase 5

- Do not reopen CLOSED Phase -1..4 solely because V3 changed.
- Active Phase 5 adopts V3 at its next gates.
- Old different-GitHub-account review requirement becomes fresh primary evidence + relevant competence + exact-head independent reasoning.
- Governance correction does **not** remove M1–M4, required Vercel status, security/data-integrity or other real blockers.
- Same-AI review obeys finding -> exit review -> fix -> new candidate -> focused re-review.

---

## 11. NOW / NEXT / BACKLOG / REJECT

### NOW

- Finish PR #68 exact-head CI, final R2 reclassification, focused independent re-review and merge if blocker=0.
- Then transition Phase 5 branches and resume M1–M4.

### NEXT

- P5-SEC npm vulnerability reachability triage.
- P5 final validation/merge/closeout.

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
- sizing/HRP/ERC/min-var in Phase 5;
- Exhaustive selection integration before validation;
- OOS claims from full-period winners;
- untraceable themes;
- removing required Vercel checks to bypass quota;
- deleting useful current workflows merely to reduce Actions count;
- further V3 governance feature expansion without a documented Reopen Condition.

---

## 12. Exact Resume Point

Current Batch: **DOC-CLEAN / PR #68**.

1. Query PR #68 exact head and applicable checks after the latest governance/TODO correction.
2. Confirm diff remains documentation-only.
3. Final Risk Reclassification: keep R2 unless new evidence justifies otherwise.
4. Enter Same-AI Independent Review Mode without modifying the candidate; focused re-review the previously found governance-structure blocker plus overall request/scope/document-authority correctness.
5. Findings: BLOCKER / FOLLOW-UP / BACKLOG / REJECT.
6. If any BLOCKER: record -> exit review -> fix -> new head -> validate -> re-review.
7. If blocker=0 and required checks pass: expected-head squash merge PR #68.
8. Re-query new main; then begin Phase 5 transition/sync.
