# Phase 5 Review & Convergence Record

Status: **CLOSED / PASS / POST-MAIN PRODUCTION VERIFIED**.

This document is retained as Phase 5 implementation, methodology-correction, security, merge and production-closeout evidence. Live execution status belongs in root `to_do_update_list.md`.

## 1. Final Phase 5 state

Phase 5 clustering/redundancy methodology and implementation are merged and production-accepted.

Final public identities:

```text
REFINERY_CLUSTERING_CONTRACT_VERSION = refinery-clustering-twd-2026-08-10.2
REFINERY_API_CONTRACT_VERSION        = refinery-v1
REFINERY_API_SCHEMA_VERSION          = refinery-v1-2026-08-10.3
```

Final P5-CLOSE production checkpoint:

`dd051ba793ab63260b4815ae35020cb40f55c7d5`

No persisted Refinery workspace-storage schema bump was introduced by Phase 5 because the accepted changes affect analytical evidence rather than persisted request state.

---

## 2. Merge / convergence history

- Parent PR #65 — Phase 5 clustering/redundancy: MERGED.
- PR #71 — M1–M4 correctness/security convergence: merged into Phase 5 parent.
- PR #74 — current-main/generated-asset reconciliation: merged into Phase 5 parent.
- PR #66 — historical docs child: CLOSED / SUPERSEDED / NOT MERGED.
- PR #75 — permanent bounded Refinery production smoke / P5-CLOSE prevention gate: MERGED and production verified.

Phase 5 parent merge checkpoint was `2c9ed83cedea9aee9acc09fa3f0a2029c3004907`; later scanner fixes #83/#84 and documentation convergence #86 advanced main before final P5-CLOSE. PR #75 was reconciled without reopening Phase 5 methodology and then merged by expected head.

---

## 3. M1 — bootstrap effective-input identity — RESOLVED

Initial defect: bootstrap identity represented a broader weekly frame / dataset identity than the exact trailing-window complete-case sample actually resampled.

Accepted correction:

- shared effective-sample preparation;
- exact effective symbols/dates/values fingerprint;
- `ResearchDataset.dataset_hash` remains a distinct provenance identity;
- primitive verifies supplied fingerprint against actual effective sample;
- deterministic seed includes effective fingerprint + method/version/cut/window/block/replicates;
- public evidence exposes exact bootstrap input identity.

Evidence: P5-CORR-A Full CI #466 + Portfolio web #104 PASS; review BLOCKER=0.

---

## 4. M2 — factor boundary-month alignment — RESOLVED

Accepted `boundary-month-exclusion-v1`:

- normalize native daily returns;
- compound represented calendar periods;
- exclude first and last represented periods;
- no fabricated pre-window return;
- no invented exchange-calendar completeness authority;
- minimum observation requirement applies after exclusion.

---

## 5. M4 — one global systematic relationship sample — RESOLVED

Accepted implementation:

- individual factor diagnostics may retain individual valid samples;
- returned systematic relationship matrix uses one exact global common monthly intersection across all matrix members + factor frame;
- relationship betas and `Sigma_F` use the same rows;
- no pairwise-cell sample switching;
- observations/start/end/common-sample fingerprint exposed;
- insufficient common sample fails closed.

M2/M4 evidence: P5-CORR-B Full CI #473 + Portfolio web #111 PASS; review BLOCKER=0.

---

## 6. M3 — factor computability vs verdict applicability — RESOLVED

Accepted separation:

- `factor_computable`;
- `factor_model_scope`;
- `factor_corroboration_eligible`.

Model scope remains `U.S.-factor co-movement diagnostic`. Current policy `fail_closed_without_traceable_instrument_scope_v1` allows diagnostic evidence to display while preventing factor evidence from upgrading redundancy verdicts without traceable applicability authority.

Evidence: P5-CORR-C Full CI #479 + Portfolio web #117 PASS; review BLOCKER=0.

---

## 7. P5-SEC — RESOLVED

Accepted direct dev-tool remediation:

- `wrangler 4.115.0 -> 4.120.1`;
- `@cloudflare/workers-types 5.20260729.1 -> 5.20260810.1`;
- transitive `undici -> 7.29.0`;
- no `--force`, no `--legacy-peer-deps`, no blanket audit fix.

Accepted Phase 5 security evidence recorded full/prod npm audit at 0 vulnerabilities.

---

## 8. Parent #65 acceptance — RESOLVED

Final parent evidence included:

- Full CI #515 PASS;
- Portfolio web #151 PASS;
- required Vercel SUCCESS;
- pre-merge recovery backup #370 PASS;
- final Independent Review PASS / BLOCKER=0;
- expected-head squash merge to `2c9ed83...`.

Initial post-merge evidence:

- Full CI #516 PASS;
- Portfolio web #152 PASS;
- then-existing Cloudflare deploy #48 PASS;
- Vercel production SUCCESS;
- post-merge recovery backup #372 PASS.

That deployment did not yet contain a permanent bounded Refinery `preflight + analyze` production smoke, so operational Phase 5 closeout intentionally remained open.

---

## 9. P5-CLOSE / PR #75 — CLOSED / PASS

Purpose: permanently add a bounded Refinery v1 / Phase 5 production smoke to the existing Cloudflare deployment acceptance gate.

Final reconciled candidate head:

`4a431af9ec309dee9d62165cf7f0e493767c4899`

The reconciliation preserved #83/#84 scanner validation while keeping #75 product scope to four files:

- `.github/workflows/deploy-cloudflare.yml`;
- `package.json`;
- `scripts/smoke_test_refinery_v1.mjs`;
- `tests/test_refinery_smoke.mjs`.

Pre-merge final evidence:

- Full CI #548: PASS;
- Portfolio web CI #169: PASS;
- R2 Release Backup Gates #409: PASS;
- Vercel: SUCCESS;
- exact-head Independent Review ID `4908369197`: PASS / BLOCKER=0;
- unresolved review threads: 0;
- expected-head squash merge completed to `main@dd051ba793ab63260b4815ae35020cb40f55c7d5`.

### Post-main production acceptance

For `dd051ba...`:

- Full CI #550: **PASS**;
- Portfolio web CI #170: **PASS**;
- Vercel production: **SUCCESS**;
- Release Backup Gates #413 `create-post-merge-backup`: **PASS** and pre-merge release verified;
- Cloudflare Worker deployment #51: **PASS**;
- `Smoke test production Russell 2000 flow`: **PASS**;
- `Smoke test production Portfolio v3 flow`: **PASS**;
- `Smoke test production Refinery v1 Phase 5 flow`: **PASS**.

The Refinery production smoke completed after Portfolio confirmed the expected Vercel deployment, so the Phase 5 smoke did not silently validate a stale backend.

**P5-CLOSE acceptance criteria are fully satisfied. Phase 5 is CLOSED / PASS.**

---

## 10. Accepted Phase 5 semantics

- synchronized weekly TWD structural input;
- correlation distance `sqrt((1-rho)/2)`;
- average linkage primary / complete linkage sensitivity;
- flat display cut 0.50;
- 52/104/156-week stability;
- 200-replicate, 4-week circular moving-block bootstrap;
- exact effective bootstrap sample fingerprinting;
- one global common systematic factor relationship sample;
- factor computability separated from verdict applicability;
- HIGH/MEDIUM/LOW/UNCERTAIN descriptive redundancy evidence;
- theme evidence unavailable without traceable provenance;
- browser presentation does not recompute methodology.

---

## 11. Explicit limitations / non-goals preserved at closeout

Phase 5 does **not** claim:

- out-of-sample validity from full-period evidence;
- KEEP/TRIM/REPLACE recommendations;
- marginal Remove-One/Add-One/Replace-One experiments;
- position sizing / HRP / ERC / min-var;
- Exhaustive selection integration;
- traceable economic themes without provider/taxonomy authority;
- general instrument applicability for U.S. factor diagnostics without instrument/security master evidence.

Future work belongs to later phases and must not retroactively reinterpret Phase 5 output.

---

## 12. Final closeout checklist

- [x] M1–M4 correctness resolved and reviewed.
- [x] clustering `.2` / API schema `.3` aligned.
- [x] P5-SEC resolved with zero-vulnerability evidence.
- [x] current-main/generated-asset reconciliation completed.
- [x] parent #65 exact-head gates/review/recovery completed.
- [x] #65 merged and initial post-main validation passed.
- [x] permanent bounded Refinery production smoke implemented/tested.
- [x] #75 reconciled with current runtime main without scope expansion.
- [x] #75 exact-head CI / Portfolio / Vercel / recovery / review passed.
- [x] #75 expected-head merged.
- [x] post-main Full CI / Portfolio / Vercel / post-merge backup passed.
- [x] Cloudflare Russell smoke passed.
- [x] Cloudflare Portfolio smoke passed.
- [x] Cloudflare Refinery Phase 5 production smoke passed.
- [x] limitations recorded.

**FINAL STATUS: PHASE 5 CLOSED / PASS / PRODUCTION VERIFIED.**

Current execution authority has moved to root `to_do_update_list.md`; do not extend this record into a second live roadmap.
