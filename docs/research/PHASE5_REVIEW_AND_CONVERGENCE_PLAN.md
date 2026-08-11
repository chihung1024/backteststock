# Phase 5 Review & Convergence Record

Status: **IMPLEMENTATION / M1–M4 / P5-SEC / PARENT MERGE RESOLVED; P5-CLOSE OPERATIONAL ACCEPTANCE RECONCILIATION ACTIVE**.

This document is retained as Phase 5 implementation, convergence and closeout evidence. **Live execution status belongs in root `to_do_update_list.md`.**

## 1. Merge / branch history

- Parent PR #65 `feat: add Phase 5 clustering and redundancy diagnostics`: **MERGED to production main**.
- Production main checkpoint immediately after the Phase 5 parent merge: `2c9ed83cedea9aee9acc09fa3f0a2029c3004907`.
- Correctness/security convergence PR #71: merged into the Phase 5 parent.
- Latest-main reconciliation PR #74: merged into the Phase 5 parent before final parent validation.
- Historical docs child PR #66: **CLOSED / SUPERSEDED / NOT MERGED**. Its useful Phase5-specific evidence was promoted; stale general docs must not be restored wholesale.
- Later production runtime advanced through scanner fixes #83 and #84. These do not change the accepted Phase 5 methodology, but they make the old P5-CLOSE #75 candidate stale relative to the runtime baseline and therefore require reconciliation before merge.

Repository governance V3 uses an **Independent Review Gate** based on independent reasoning, competence and exact-head evidence; it does not require a different GitHub identity.

## 2. Current contract identities

```text
REFINERY_CLUSTERING_CONTRACT_VERSION = refinery-clustering-twd-2026-08-10.2
REFINERY_API_CONTRACT_VERSION        = refinery-v1
REFINERY_API_SCHEMA_VERSION          = refinery-v1-2026-08-10.3
```

No persisted Refinery workspace-storage schema bump was introduced because the corrections changed analytical evidence rather than persisted request state.

## 3. M1 — bootstrap effective-input identity — RESOLVED

Initial defect: the draft hashed an entire weekly frame and repurposed `ResearchDataset.dataset_hash`, while bootstrap actually operated on a trailing-window complete-case sample.

Accepted implementation:

- one shared effective-sample preparation path;
- exact fingerprint of effective symbols/dates/values;
- ResearchDataset hash remains a separate provenance identity;
- primitive verifies fingerprint/sample identity;
- seed includes effective fingerprint + methodology version/linkage/cut/window/block/replicates;
- public evidence exposes bootstrap input fingerprint and window.

Evidence: P5-CORR-A Full CI #466 + Portfolio web CI #104 PASS; focused review PASS/BLOCKER=0.

## 4. M2 — boundary-month factor alignment — RESOLVED

Accepted V1 policy:

- normalize native daily returns;
- compound represented calendar periods;
- exclude first and last represented periods;
- no invented exchange-calendar completeness authority;
- no fabricated pre-window return;
- minimum observation rule applies after exclusion;
- policy `boundary-month-exclusion-v1`.

## 5. M4 — one global systematic relationship sample — RESOLVED

Accepted implementation:

- individual diagnostics may retain individual valid samples;
- matrix membership begins with individually valid assets;
- one global common monthly intersection across all matrix members + factor frame;
- relationship betas are refit on that exact common sample;
- `Sigma_F` uses the same rows;
- no pairwise-cell sample switching;
- observations/start/end/common-sample fingerprint are exposed;
- insufficient common sample fails closed.

Evidence for M2+M4: P5-CORR-B Full CI #473 + Portfolio web CI #111 PASS; focused review PASS/BLOCKER=0.

## 6. M3 — factor computability vs verdict applicability — RESOLVED

Accepted implementation:

- separate `factor_computable`, `factor_model_scope`, `factor_corroboration_eligible`;
- model scope = `U.S.-factor co-movement diagnostic`;
- computable betas/R²/systematic correlation remain visible;
- policy = `fail_closed_without_traceable_instrument_scope_v1`;
- factor evidence affects redundancy verdict only when eligibility is explicitly true;
- instrument/security master and regional factor routing remain later work.

Evidence: P5-CORR-C Full CI #479 + Portfolio web CI #117 PASS; focused review PASS/BLOCKER=0.

## 7. P5-SEC — RESOLVED

Accepted direct dev-tool remediation:

- `wrangler 4.115.0 -> 4.120.1`;
- `@cloudflare/workers-types 5.20260729.1 -> 5.20260810.1`;
- transitive `undici -> 7.29.0`;
- no `--force`, no `--legacy-peer-deps`, no blanket `npm audit fix`.

Fresh post-reconciliation evidence recorded during Phase 5:

- full `npm audit --json`: **0 vulnerabilities**;
- `npm audit --omit=dev --json`: **0 vulnerabilities**;
- installed chain verified as `wrangler@4.120.1 -> miniflare@5.20260804.0-alpha -> undici@7.29.0`, with `@cloudflare/workers-types@5.20260810.1`.

## 8. Latest-main / generated-asset reconciliation — RESOLVED

Production main advanced through governance/document authority cleanup (#68) and Portfolio common-window comparison (#70) while Phase 5 corrections were developed.

Resolution discipline:

1. reconciliation occurred on a recovery child rather than directly on the parent;
2. the only actual three-way conflict was generated `public/portfolio` output;
3. generated assets were neutralized instead of hand-merged;
4. GitHub standard merge proved source histories compatible;
5. combined #70 + Phase5 source passed TypeScript/source-contract validation before bundle regeneration;
6. generated output was rebuilt from combined source in the normal PR synthetic-merge context;
7. deterministic double-build and strict generated-only diff controls were used;
8. temporary workflow machinery was removed before final validation.

PR #74 final evidence included Full CI #512 PASS, Portfolio web #148 PASS, Vercel SUCCESS and transition review PASS/BLOCKER=0.

## 9. Parent #65 final validation / merge — RESOLVED

Final exact-head parent evidence included:

- Full CI #515: PASS;
- Portfolio web CI #151: PASS;
- required Vercel status: SUCCESS;
- pre-merge recovery backup #370: PASS;
- final Independent Review ID `4902365653`: PASS / BLOCKER=0;
- expected-head squash merge completed to production main `2c9ed83cedea9aee9acc09fa3f0a2029c3004907`.

Initial post-merge production evidence also passed:

- main Full CI #516: PASS;
- Portfolio web CI #152: PASS;
- Cloudflare deploy #48: PASS for the then-existing deploy gates;
- Vercel production: SUCCESS;
- post-merge recovery backup #372: PASS.

## 10. Why P5-CLOSE remains open

The Cloudflare deployment workflow at the time of #65 merge explicitly smoked Russell and Portfolio but did **not** permanently exercise the Refinery Phase 5 `preflight + analyze` production path. Therefore generic deployment success could not honestly be labeled Phase 5 production-smoke acceptance.

PR #75 is the narrow prevention/closeout fix. It adds a bounded, contract-oriented Refinery Phase 5 production smoke and wires it into the permanent deployment acceptance flow.

Previously validated #75 exact head:

`5305149a40d7c3b4390589ccb23c9b8f04d07842`

Historical gates on that head:

- Full CI #522: PASS;
- Portfolio web CI #158: PASS;
- R2 Release Backup Gates #379/#380: PASS;
- Independent Review: PASS / BLOCKER=0;
- source ↔ smoke parity: PASS.

The old exact-head Vercel status failed with a Free-plan build-rate-limit target. That evidence remains historical; it is not permission to bypass the check.

## 11. P5-CLOSE reconciliation state at C0-B branch point

Last runtime-verified production baseline before the docs-only C0-B publication:

`670086fdb7a74a054bdd39e69ec38aa9ad5d6e8d`

That runtime baseline includes #83/#84 and has fresh Full CI, Portfolio CI, Cloudflare production deployment/smokes and a genuine Vercel production SUCCESS.

C0-B itself is documentation-only and may advance the repository `main` SHA when merged. It does **not** create a new runtime baseline. Actual `main` must therefore be re-queried before #75 reconciliation.

PR #75 branch-point compare evidence against `670086f...`:

- merge base: `2c9ed83cedea9aee9acc09fa3f0a2029c3004907`;
- status: **diverged**;
- #75: **ahead 9 / behind 2**;
- changed scope: `.github/workflows/deploy-cloudflare.yml`, `package.json`, `scripts/smoke_test_refinery_v1.mjs`, `tests/test_refinery_smoke.mjs`.

These compare counts are historical branch-point evidence only. If C0-B merges, #75 will be at least one additional docs-only commit behind repository main; run a fresh compare before acting.

Therefore the current blocker is not correctly summarized as “Vercel quota only.” Before merge, #75 must be reconciled with the actual then-current main and receive fresh exact-head evidence. `package.json` must preserve the scan-progress validation added by #84 while adding the Refinery smoke wiring from #75.

No Phase 5 clustering/API methodology change is required by this reconciliation.

## 12. Accepted Phase 5 scope / non-goals

Accepted:

- synchronized weekly TWD structural input;
- correlation distance `sqrt((1-rho)/2)`;
- average linkage primary, complete sensitivity;
- flat cut 0.50;
- 52/104/156-week stability;
- 200 × 4-week circular moving-block bootstrap;
- HIGH/MEDIUM/LOW/UNCERTAIN descriptive redundancy evidence;
- no numeric magic score;
- theme evidence unavailable without traceable provenance;
- browser is presentation only.

Still non-goals / later phases:

- KEEP/TRIM/REPLACE recommendations;
- marginal Remove-One/Add-One/Replace-One experiments;
- sizing/HRP/ERC/min-var;
- Exhaustive selection integration;
- OOS/walk-forward claims;
- instrument/security master or regional factor routing;
- untraceable theme taxonomy.

## 13. Remaining P5-CLOSE gates

Resolved:

- [x] M1–M4 implementation/tests/review.
- [x] clustering `.2` / API response `.3` convergence.
- [x] P5-SEC remediation + fresh zero-vulnerability evidence.
- [x] parent/latest-main reconciliation for the Phase 5 implementation branch.
- [x] parent final exact-head CI / Portfolio web / Vercel.
- [x] parent final V3 Independent Review.
- [x] expected-head squash merge #65 → main.
- [x] initial post-main CI / Portfolio / Vercel / backup / then-existing deploy gates.
- [x] permanent Refinery production smoke implemented and historically validated in #75.

Current closeout work:

- [ ] re-query actual main after C0-B publication and reconcile the #75 four-file smoke/deployment scope;
- [ ] confirm reconciled diff preserves all then-current-main scanner/package/workflow behavior;
- [ ] fresh exact-head Full CI / Portfolio web CI / genuine required Vercel SUCCESS;
- [ ] fresh/applicable recovery gate;
- [ ] exact-head Independent Review BLOCKER=0;
- [ ] expected-head squash merge #75;
- [ ] post-merge main Full CI / Portfolio CI / Vercel / backup where applicable;
- [ ] Cloudflare deployment executes and passes Russell + Portfolio + `Smoke test production Refinery v1 Phase 5 flow`;
- [ ] record Phase 5 **CLOSED / PASS** with limitations.

## 14. Closeout limitations to preserve

When P5-CLOSE is complete, record explicitly:

- Phase 5 full-period evidence is in-sample and is not OOS validation;
- factor evidence remains scoped to a U.S.-factor co-movement diagnostic;
- instrument/security master, regional factor routing and traceable theme authority remain later work.

For the current execution order and post-Phase-5 priorities, read root `to_do_update_list.md` rather than extending this historical record into a second live task tracker.
