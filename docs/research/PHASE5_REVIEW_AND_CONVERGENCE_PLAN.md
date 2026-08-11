# Phase 5 Review & Convergence Plan

Status: **M1–M4 + P5-SEC RESOLVED / LATEST-MAIN RECONCILIATION CLOSED / PARENT FINAL VALIDATION ACTIVE**.

Parent: PR #65 `feat: add Phase 5 clustering and redundancy diagnostics`.
Correctness/security convergence: PR #71 `fix: converge Phase 5 correctness contracts` — merged into the Phase 5 parent.
Latest-main reconciliation: PR #74 — merged into the Phase 5 parent with current production `main@af1cd83e41b23df745e27f39b9992e7a8a56fde0` preserved as an actual ancestor.
Historical docs child: PR #66 — closed as superseded without merge. Its useful Phase5-specific evidence is preserved in current contracts/history; its stale general README/Deployment/TODO material must not be reintroduced.

## 1. Governance transition

The historical review plan was written under the old `Independent Third-Party Review` wording. Repository governance V3 uses an **Independent Review Gate** based on independent reasoning, relevant competence and exact-head evidence rather than a different GitHub identity. This transition does not waive correctness, security, required CI/Vercel or rollback gates.

P5-CORR A–D, P5-SEC and the latest-main reconciliation each received exact-head validation and focused independent review. PR #65 still requires one final exact-head parent review before production merge.

## 2. Corrected identities

```text
REFINERY_CLUSTERING_CONTRACT_VERSION = refinery-clustering-twd-2026-08-10.2
REFINERY_API_CONTRACT_VERSION        = refinery-v1
REFINERY_API_SCHEMA_VERSION          = refinery-v1-2026-08-10.3
```

No Refinery persisted workspace-storage schema bump is required because P5-CORR changes analytical evidence, not persisted request state.

## 3. M1 — bootstrap input identity — RESOLVED

Root cause: the draft hashed the entire weekly frame and repurposed `ResearchDataset.dataset_hash`, while bootstrap actually resampled a trailing-window complete-case sample.

Accepted implementation:
- shared effective sample preparation;
- fingerprint exact effective symbols/dates/values only;
- preserve ResearchDataset hash unchanged;
- primitive verifies fingerprint/sample identity;
- seed includes fingerprint + methodology version/linkage/cut/window/block/replicates;
- public evidence exposes bootstrap input fingerprint + window.

Evidence: P5-CORR-A Full CI #466 + Portfolio web CI #104 PASS; focused review PASS/BLOCKER=0.

## 4. M2 — boundary-month factor alignment — RESOLVED

Accepted V1 policy:
- normalize native daily returns;
- compound represented calendar months;
- exclude first and last represented periods;
- no exchange-calendar completeness claim;
- no fabricated pre-window return;
- require 36 observations after exclusion;
- policy `boundary-month-exclusion-v1`.

## 5. M4 — common systematic relationship sample — RESOLVED

Accepted implementation:
- individual diagnostics may keep individual valid samples;
- matrix membership begins with individually valid assets;
- one global common monthly intersection across all matrix members + factor frame;
- refit every relationship beta on that exact sample;
- compute `Sigma_F` from the same rows;
- no pairwise-cell sample switching;
- expose observations/start/end/common-sample fingerprint;
- insufficient common sample fails closed.

Evidence for M2+M4: P5-CORR-B Full CI #473 + Portfolio web CI #111 PASS; focused review PASS/BLOCKER=0.

## 6. M3 — factor computability vs verdict applicability — RESOLVED

Accepted implementation:
- separate `factor_computable`, `factor_model_scope`, `factor_corroboration_eligible`;
- model scope = `U.S.-factor co-movement diagnostic`;
- computable betas/R²/systematic correlation remain visible;
- policy = `fail_closed_without_traceable_instrument_scope_v1`;
- current eligibility false with `unavailable_no_traceable_instrument_scope`;
- factor correlation affects verdict only when eligibility is explicitly true and threshold is met;
- instrument master/regional factor routing remains BACKLOG.

Evidence: P5-CORR-C Full CI #479 + Portfolio web CI #117 PASS; focused review PASS/BLOCKER=0.

## 7. P5-SEC — RESOLVED

Initial full npm graph contained one high + two moderate advisory nodes on the dev-tool chain; production-only audit was already zero.

Accepted remediation:
- `wrangler 4.115.0 -> 4.120.1`;
- `@cloudflare/workers-types 5.20260729.1 -> 5.20260810.1`;
- transitive `undici -> 7.29.0`;
- no `--force`, no `--legacy-peer-deps`, no blanket audit fix.

After latest-main reconciliation, a fresh read-only audit against the current advisory database reconfirmed:
- full `npm audit --json`: **0 vulnerabilities**;
- `npm audit --omit=dev --json`: **0 vulnerabilities**;
- installed chain: `wrangler@4.120.1 -> miniflare@5.20260804.0-alpha -> undici@7.29.0`, with `@cloudflare/workers-types@5.20260810.1`.

## 8. Latest-main reconciliation — RESOLVED

Production main advanced through V3/document authority cleanup (#68) and Portfolio common-window comparison (#70) while Phase 5 corrections were developed on the parent branch.

The reconciliation path intentionally used a recovery child:
- the only actual three-way conflict was generated `public/portfolio` output;
- generated assets were neutralized rather than hand-merged;
- current main was merged into the recovery child with normal Git history preservation;
- combined #70 + Phase5 source passed TypeScript/source-contract checks;
- `public/portfolio` was rebuilt from the combined source with deterministic double-build evidence and strict generated-only diff controls;
- temporary workflow write/audit machinery was removed before final validation;
- PR #74 exact-head Full CI, Portfolio web CI and Vercel passed; independent transition review PASS/BLOCKER=0;
- PR #74 then normal-merged into the Phase 5 parent, leaving current production main as the actual merge base for #65.

## 9. Accepted Phase 5 scope

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

## 10. Explicit non-goals

- KEEP/TRIM/REPLACE;
- marginal Remove-One/Add-One/Replace-One experiments;
- sizing/HRP/ERC/min-var;
- Exhaustive selection integration;
- OOS/walk-forward claims;
- instrument/security master or regional factor routing;
- untraceable theme taxonomy.

## 11. Remaining gates

- [x] M1 implementation/tests/review;
- [x] M2 implementation/tests/review;
- [x] M4 implementation/tests/review;
- [x] M3 implementation/tests/review;
- [x] clustering `.2` / API response `.3` convergence;
- [x] P5-SEC remediation + fresh post-reconciliation audit evidence;
- [x] preserve current main documentation authority during branch transition;
- [x] combined production bundle regeneration and transition review;
- [x] parent pre-merge recovery backup created/verified on the reconciled parent;
- [ ] final exact-head parent CI / Portfolio web / Playwright / Vercel after this final documentation convergence;
- [ ] V3 independent final exact-head review of PR #65;
- [ ] expected-head squash merge #65 -> main;
- [ ] post-main deployment/smoke/backup/limitations closeout.

## 12. Exact resume point

Primary active work is **PR #65 parent final validation**.

1. Refresh the live handoff and PR #65 description to current resolved facts.
2. Re-run final exact-head CI / Portfolio web / Vercel on the resulting candidate.
3. Freeze the candidate and perform the final V3 Independent Review.
4. If BLOCKER=0 and all required statuses remain green, mark #65 Ready and expected-head squash merge to main.
5. Perform P5-CLOSE post-main deployment, smoke, backup and limitations verification.
6. Only after Phase 5 is explicitly CLOSED / PASS may Phase 6 begin.
