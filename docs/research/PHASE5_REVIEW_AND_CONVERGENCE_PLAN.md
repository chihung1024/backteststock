# Phase 5 Review & Convergence Plan

Status: **M1–M4 RESOLVED / P5-CORR A–D IMPLEMENTED; P5-SEC + P5-VAL + PARENT MERGE PENDING**.

Parent: PR #65 `feat: add Phase 5 clustering and redundancy diagnostics`.
Correctness convergence: Draft PR #71 `fix: converge Phase 5 correctness contracts`.
Historical docs child: PR #66. Its Phase5-specific evidence is preserved here; its general README/Deployment/TODO changes are superseded by the current main documentation-convergence path and are not wholesale merged.

## 1. Governance transition

The historical review plan was written under the old `Independent Third-Party Review` wording. Repository governance V3 uses an **Independent Review Gate** based on independent reasoning, relevant competence and exact-head evidence rather than a different GitHub identity. This transition does not waive correctness, security, required CI/Vercel or rollback gates.

P5-CORR A/B/C each received focused Same-AI Independent Review after exact-head validation. D and the final Phase 5 candidate require the same evidence discipline.

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

## 7. Accepted Phase 5 scope

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

## 8. Explicit non-goals

- KEEP/TRIM/REPLACE;
- marginal Remove-One/Add-One/Replace-One experiments;
- sizing/HRP/ERC/min-var;
- Exhaustive selection integration;
- OOS/walk-forward claims;
- instrument/security master or regional factor routing;
- untraceable theme taxonomy.

## 9. Remaining gates

- [x] M1 implementation/tests/review;
- [x] M2 implementation/tests/review;
- [x] M4 implementation/tests/review;
- [x] M3 implementation/tests/review;
- [x] clustering `.2` / API response `.3` convergence in P5-CORR-D;
- [ ] P5-SEC `npm audit --json` evidence and reachability classification;
- [ ] final exact-head Python/Worker/score/Portfolio web/Playwright validation;
- [ ] required Vercel status green on final candidate;
- [ ] release-backup gate as applicable;
- [ ] V3 independent final exact-head review;
- [ ] preserve current main documentation authority during branch transition;
- [ ] expected-head parent merge and post-main deployment/smoke/backup closeout.

## 10. Exact resume point

After P5-CORR-D validation, execute **P5-SEC only**. Do not start Phase 6. New findings are NOW only if they block Phase 5 correctness/security/data integrity; otherwise classify NEXT/BACKLOG/REJECT.
