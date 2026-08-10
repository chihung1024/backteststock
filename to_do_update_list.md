# BacktestStock — Live Project Status & Handoff

> Repository-internal live execution authority. Mutable operational facts (current SHA, PR/check state, ruleset, deployment) must be re-queried before acting. Durable architecture belongs in README/ADRs/contracts; full historical detail remains reconstructable from Git/PR history.

## 1. Primary Goal

Complete **Phase 5 — Clustering & Redundancy** correctly, close it, then begin Phase 6. Before resuming Phase 5, finish the current one-time **DOC-CLEAN** Batch requested by the owner: restore the complete V3 governance baseline, remove demonstrably useless/stale documentation, and converge documentation authority.

## 2. Current Operational Snapshot

### Production / main

- Repository: `chihung1024/backteststock`
- Production candidate branch: `main`
- Current main at DOC-CLEAN start: `b116b73c7dbc189fb0eae34624925fe2e16b81ae`
- Parent before that commit: `db3e692e3e4ce1962d6953988464947b35d5ef82` (Phase 4 closeout)
- Commit `b116b73...` / PR #67 accidentally replaced the full playbook with only the V3 Final Hardening patch (`+160/-2563`). This is an R2 governance-document correctness defect, not a valid complete V3 baseline.

### Current Batch — DOC-CLEAN

- Branch: `docs/v3-governance-doc-cleanup`
- Risk Class: **R2 — Significant** because engineering governance/document authority is being corrected.
- Started from exact `main@b116b73...`.
- Current branch head after core cleanup edits: `a4b097b9e462cc02e79630c812875bd2c818299b` (re-query before merge; later documentation commits may advance it).
- Status: **ACTIVE / final documentation convergence**.

### Phase 5 PRs paused during DOC-CLEAN

- Parent implementation PR #65: `phase5/clustering-redundancy` -> `main`
  - head: `0dd3c12b3097975bdcd4d36aeab5504987efbe29`
  - state at latest query: OPEN / DRAFT; not merge-ready.
- Child docs PR #66: `docs/phase5-convergence-plan` -> `phase5/clustering-redundancy`
  - head: `1a5364c414f724706fa89eec60f44391bfa3439b`
  - contains valuable Phase 5-specific contract/review work, but its body still encodes the superseded “actual third-party reviewer” blocker and must be transitioned to V3 governance before use.

Do not merge #65/#66 until DOC-CLEAN lands and the Phase 5 branches are reconciled with the new main baseline.

---

## 3. Stable State

### Last Known Good product state

Phase 4 Refinery diagnostic UI is CLOSED/PASS on the product code inherited from `db3e692e3e4ce1962d6953988464947b35d5ef82`.

Key Phase 4 recovery evidence:

- implementation PR #63 merge: `e59c1402011c7e8c940f806e79c9ce4b0da3f47f`
- closeout PR #64 merge: `db3e692e3e4ce1962d6953988464947b35d5ef82`
- pre backup: `backup-pre-pr63-17f0dd88aeae`
- post backup: `backup-post-pr63-e59c1402011c`

PR #67 changed governance documentation only; product runtime code did not intentionally change, but the repository governance file became incomplete and must be corrected before further high-risk engineering.

---

## 4. Documentation Authority

1. `AI_PROJECT_PLAYBOOK.md` — engineering governance; V3.0, once this Batch lands, is GOVERNANCE BASELINE LOCKED / FROZEN.
2. `README.md` — durable product/architecture/run/test/deploy overview.
3. `to_do_update_list.md` — current Phase/Batch/blockers/exact next action.
4. `docs/PROJECT_DOCUMENTATION_POLICY.md` — documentation authority/freshness/cleanup rules.
5. `docs/README.md` and `docs/research/README.md` — canonical document navigation.
6. `docs/quant/*`, `docs/research/*`, ADRs — versioned semantic/architecture authorities.
7. GitHub/Vercel/Cloudflare current remote state — operational truth for mutable facts.

If documentation conflicts with remote state, classify documentation drift; do not infer a new plan from stale prose.

---

## 5. DOC-CLEAN Work Completed

### Governance repair

- Restored a complete integrated `AI_PROJECT_PLAYBOOK.md` V3.0 instead of the patch-only fragment.
- V3 includes R0–R3 risk classes, Docs Risk Escalation, final risk reclassification, Same-AI Independent Review isolation, Reviewer/Implementer role separation, competence insufficiency handling, governance transition/non-retroactivity, Grandfather anti-bypass and Governance Freeze.

### Documentation authority / navigation

- Added `docs/PROJECT_DOCUMENTATION_POLICY.md`.
- Added `docs/README.md`.
- Added `docs/research/README.md`.
- Rewrote root README to reflect current Refinery/Portfolio architecture and document authority.
- Updated `apps/api/README.md` so merged Refinery v1 is current while unmerged Phase 5 methodology is not misrepresented as main authority.
- Updated `docs/DEPLOYMENT.md` with real Refinery POST smoke surfaces and risk-proportional deployment governance.
- Updated `docs/EXHAUSTIVE_OPTIMIZER_V3.md` to remove stale rollout/deployment status and retain only durable contract semantics.

### Deleted as demonstrably useless/superseded live-tree documents

- `docs/OPTIMIZER_IMPLEMENTATION_STATUS.md` — stale rollout/status snapshot.
- `docs/EXHAUSTIVE_OPTIMIZER_V2.md` — explicitly superseded v2 history; reconstructable from Git.
- `docs/PORTFOLIO_OPTIMIZER_MVP.md` — explicitly retired historical MVP; reconstructable from Git.

### Deliberately retained

- `docs/PHASE_MINUS1_GOVERNANCE.md` — historical Phase -1 evidence; no longer current governance authority.
- `docs/portfolio-migration/*` — historical migration material still contains unique Portfolio ledger/API/cutover evidence. Do not delete until those unique semantics are proven absorbed by current authorities.
- Current five workflow YAMLs under `.github/workflows/` — each still owns a real responsibility: CI, Portfolio web CI, Cloudflare deploy, Release Backup Gates, Universe update.

---

## 6. GitHub Actions Cleanup Finding

Current source tree contains only **5** workflow YAMLs, all still useful.

GitHub Actions registry/API nevertheless reports **54 active workflow registrations**, including many old one-off `apply-*`, `diagnose-*`, and temporary Phase workflows whose YAML files are no longer present on `main`.

Classification:

- Source-tree workflow garbage: **already absent**.
- Historical workflow registrations/run history: operational UI/API residue, not current source authority.
- Available GitHub connector in this session exposes no disable/delete-workflow action, so those stale registrations cannot be safely removed programmatically here.

Do not claim they were disabled. If the GitHub UI/API later exposes a supported cleanup path, remove/disable only registrations whose source workflow no longer exists; do not touch the five current workflows.

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
| DOC-CLEAN | V3 governance/document cleanup | **ACTIVE** |
| 5 | Clustering & Redundancy | ACTIVE / PAUSED FOR DOC-CLEAN / PR #65 |
| 6 | Marginal Experiments | PLANNED / BLOCKED BY PHASE 5 |
| 7 | Walk-Forward / Research Validity | PLANNED |
| 8 | Selection Policy | PLANNED |
| 9 | Sizing | PLANNED |
| 10 | Validated Exhaustive Integration | PLANNED |
| 11 | Point-in-Time Universe / Fundamentals | PLANNED |

### Historical checkpoint compression

- Phase -1: PR #52 merge `9135bdd33a46afee4f4a12b9030ca4504114924f`.
- Continuity governance: PR #53 merge `bc8ce721a82938c32ed8b9af7c91fba25a161f8a`.
- Phase 0: PR #54 merge `68cbd58d570ce7d806c2a73903b5bdb506c9bae1`; closeout #55 `d173f1d15a671e7d2f3c096a56e7ee3ef9f0a183`.
- Phase 1: PR #57 merge `7cf3fdcfa248d47a036419213da0acce594ada7c`; closeout #58 `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`.
- Phase 2: PR #59 merge `724075ddbb0383f7889e4b622a95a57769d5558c`; closeout #60 `4cea3b18fdce7db5e464196172f59930abf6b7d9`.
- Phase 3: PR #61 merge `6e18726dcc1383e0b839e4bd0bded46e720e2707`; closeout #62 `17f0dd88aeaeff61f84ac6598c7b6258135d4ca4`.
- Phase 4: PR #63 merge `e59c1402011c7e8c940f806e79c9ce4b0da3f47f`; closeout #64 `db3e692e3e4ce1962d6953988464947b35d5ef82`.

Use Git/PR history for detailed old Batch logs; do not expand this live file back into a chronological transcript.

---

## 8. Phase 5 Correctness Blockers — Frozen Specification

Phase 5 must resolve these before merge. These are real methodology/correctness blockers and are **not** removed by the V3 reviewer-policy change.

### M1 — Bootstrap effective-sample identity

- Add one shared `prepare_bootstrap_sample(weekly_returns, window)` path: numeric -> canonical symbol order -> trailing structural window -> inf->NaN -> complete-case.
- Fingerprint the exact effective sample: symbols + dates + values.
- Seed material includes input fingerprint, clustering contract version, linkage, cut distance, window, block weeks, replicates.
- Never mutate/repurpose `ResearchDataset.dataset_hash`.
- Rename primitive input from ambiguous `dataset_hash` to `input_fingerprint` equivalent.
- Public evidence field should be explicit, e.g. `bootstrap_input_fingerprint_sha256`.
- Tests: permutation invariant; effective-sample value/date mutation changes seed; pre-window mutation does not; complete-case-excluded row does not; ResearchDataset hash remains distinct; methodology params affect seed as intended.

### M2 — Factor boundary-month exclusion

- Do not invent exchange-calendar completeness authority.
- For native daily-return -> monthly factor regression, exclude first and last represented calendar periods.
- Compound only interior months and join factors there.
- Preserve minimum observation requirement after exclusion.
- No fabricated pre-window/backfilled return to rescue a boundary month.

### M3 — Factor computability vs applicability

Separate:

- `factor_computable`
- `factor_model_scope`
- `factor_corroboration_eligible`

USD denomination/history can make a U.S.-factor regression mechanically computable, but absent authoritative instrument taxonomy it does not make factor evidence eligible to upgrade redundancy verdicts. Diagnostic beta/R²/systematic relationship may remain visible with explicit scope/reason.

### M4 — Global common relationship sample

- Individual diagnostic exposures may retain individual valid samples.
- One returned systematic relationship matrix uses one exact global common monthly index across included valid assets and factor frame.
- Refit relationship betas and factor covariance on the same rows.
- Fail closed if common observations are insufficient.
- Expose relationship sample count/start/end/fingerprint.

### Version consequence when M1–M4 land

- clustering methodology: `refinery-clustering-twd-2026-08-10.1` -> `.2`
- request contract remains `refinery-v1`
- public API schema: `.2` -> `refinery-v1-2026-08-10.3`
- no persisted workspace schema bump unless input persistence changes.

---

## 9. Phase 5 Execution Order After DOC-CLEAN

1. **Transition/sync** new `main` V3/docs baseline into the Phase 5 parent branch.
2. Re-evaluate PR #66. Preserve its useful Phase 5 contract/review content, but remove obsolete third-party-account blocker; if conflict/rebase cost is higher than recreating a clean child docs delta, close #66 as superseded and create a fresh Phase5 docs child.
3. **P5-CORR-A — M1** exact bootstrap effective-sample identity.
4. **P5-CORR-B — M2 + M4** boundary-month exclusion + global common relationship sample.
5. **P5-CORR-C — M3** diagnostic computability/scope/corroboration gate.
6. **P5-CORR-D** methodology/API version and contract/type convergence.
7. **P5-SEC** evidence-based `npm audit --json` triage; no `--force` upgrade.
8. **P5-VAL** exact-head targeted tests + full applicable CI + Portfolio web + Playwright + required Vercel green + backup/recovery evidence + V3 Independent Review.
9. **P5-MERGE** expected-head squash merge #65; no bypass.
10. **P5-CLOSE** post-main verification, known limitations, Phase 5 CLOSED, exact Phase 6 resume point.
11. Only then start Phase 6.

---

## 10. V3 Governance Transition for Existing Phase 5 Work

V3 governance correction is legitimate because PR #67 left the playbook incomplete and the former “different account” requirement created process theater in a solo repository.

Transition rule:

- Do **not** reopen already CLOSED Phase -1..4 solely because V3 changed.
- Active Phase 5 adopts V3 at its next gates.
- The old “actual third-party GitHub reviewer” requirement is replaced by a V3 Independent Review Gate based on fresh primary evidence + relevant competence + exact-head discipline.
- This governance change does **not** remove M1–M4, Vercel-required-status, security/data-integrity or other real correctness blockers.
- Same-AI review must obey Reviewer/Implementer role separation: finding -> exit review -> fix -> new head -> re-review.

---

## 11. NEXT / BACKLOG / REJECT

### NOW

- Finish DOC-CLEAN exact-head validation/review/merge.
- Then transition Phase 5 branches and resume M1–M4.

### NEXT

- P5-SEC npm vulnerability reachability triage.
- P5 final validation/merge/closeout.

### BACKLOG

- instrument/security master and regional factor routing;
- traceable theme taxonomy/provider;
- globally distributed Refinery rate limiting;
- Vercel preview quota optimization;
- GitHub Actions immutable-SHA pinning review;
- point-in-time Universe/fundamentals in Phase 11;
- GitHub UI/API cleanup of stale historical workflow registrations when a supported mutation path is available.

### REJECT for current scope

- magic 0–100 redundancy score;
- KEEP/TRIM/REPLACE before later validation;
- Phase 6 marginal experiments inside Phase 5;
- sizing/HRP/ERC/min-var in Phase 5;
- Exhaustive selection integration before validation phase;
- OOS claims from full-period winners;
- untraceable themes;
- removing required Vercel checks to bypass quota;
- deleting current useful workflows merely to reduce Actions count;
- further V3 governance feature expansion without a documented Reopen Condition.

---

## 12. Exact Resume Point

Current Batch: **DOC-CLEAN**.

Next actions, in order:

1. compare `main@b116b73...` vs current `docs/v3-governance-doc-cleanup` head and confirm changed files are documentation-only;
2. open a docs/governance cleanup PR to `main`;
3. run/inspect exact-head applicable CI/checks;
4. enter V3 Same-AI Independent Review Mode without modifying the candidate; review original request, final diff, playbook, indexes, TODO and CI evidence; classify BLOCKER/FOLLOW-UP/BACKLOG/REJECT;
5. if BLOCKER exists: record -> exit reviewer mode -> fix -> new head -> validate -> focused re-review;
6. if blocker=0 and required checks are satisfied: expected-head squash merge;
7. re-query new main and begin the Phase 5 transition/sync step above.
