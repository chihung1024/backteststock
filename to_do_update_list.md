# BacktestStock — Live Project Status & Handoff

> Repository-internal live execution authority. Mutable facts such as current SHA, PR/check/deployment state and protection rules must always be re-queried before acting. Durable architecture belongs in README/contracts/ADRs; detailed execution history remains reconstructable from Git/PR history.

## 1. Project Status

Primary goal: finish **Phase 5 production closeout**, then complete the already-identified correctness/reliability gates before Phase 6 implementation.

Last runtime-verified production baseline before this docs-only C0-B publication:

`670086fdb7a74a054bdd39e69ec38aa9ad5d6e8d`

C0-B may advance the repository `main` SHA when this documentation PR merges, but it changes no runtime/API/quant behavior. **Always re-query actual `main` after this document lands.**

Phase 5 clustering/redundancy methodology and implementation are merged and authoritative; **P5-CLOSE remains open** because the permanent bounded Refinery production smoke in PR #75 has not yet been reconciled/merged and exercised in production.

Next implementation batch after this documentation publication:

**C1-A / PR #75 — reconcile the previously validated Refinery production-smoke candidate with the then-current `main`, then obtain fresh exact-head gates.**

Do not start Phase 6 implementation until the unlock gates in §5 are closed.

---

## 2. Stable State

### Runtime-verified baseline

- Repository: `chihung1024/backteststock`.
- Last runtime-verified code/runtime baseline: `670086fdb7a74a054bdd39e69ec38aa9ad5d6e8d`.
- PR #65 — Phase 5 clustering/redundancy implementation: **MERGED / IMPLEMENTATION PASS**.
- PR #83 — Issue #80 80-FIX-A retryable scan edge-cache poisoning: **MERGED / DEPLOYED / VERIFIED**.
- PR #84 — Issue #80 80-FIX-B settled-vs-success progress semantics: **MERGED / DEPLOYED / VERIFIED**.

### C0-A / #84 post-main evidence

For runtime baseline `670086f...`:

- Full CI run `31508980958`: **PASS**.
- Portfolio web CI run `31508980982`: **PASS**.
- Cloudflare deployment run `31508980934`: **PASS**.
- Production Russell 2000 smoke: **PASS**.
- Production Portfolio v3 smoke: **PASS**.
- GitHub `Vercel` status: **SUCCESS**.
- GitHub `Cloudflare Worker` status: **SUCCESS**.

The #84 merge used expected-head squash from exact head `49b929f17ba7fb64a14d1e3a24323c15cdd7978b` after Full CI / Portfolio CI / Vercel / focused review BLOCKER=0. An initial merge attempt was correctly blocked because GitHub left a successful `validate` job metadata record in `in_progress`; the same exact-head job was rerun without code mutation or bypass and completed successfully before merge.

Rollback anchor for C0-A: prior verified production main `b937b9e0578eb17f5b9280597565fa78825db021` or a normal source revert of #84 if a regression is discovered.

### Phase 5 public identities

```text
REFINERY_CLUSTERING_CONTRACT_VERSION = refinery-clustering-twd-2026-08-10.2
REFINERY_API_CONTRACT_VERSION        = refinery-v1
REFINERY_API_SCHEMA_VERSION          = refinery-v1-2026-08-10.3
```

### Security checkpoint

Last accepted Phase 5 dependency remediation remains:

- `wrangler@4.120.1`;
- `@cloudflare/workers-types@5.20260810.1`;
- `miniflare@5.20260804.0-alpha`;
- transitive `undici@7.29.0`;
- last recorded full/prod npm audit evidence: **0 / 0 vulnerabilities**.

The SHAs above are recovery/evidence anchors, not substitutes for fresh remote-state queries.

---

## 3. Architecture Notes

Durable architecture authority remains README + ADRs + versioned contracts. Current boundaries relevant to the next work are:

- `TWDHistoryService` owns audited market-history / TWD valuation input semantics.
- `apps/api/app/portfolio/` owns Portfolio v3 ledger, metrics, comparison and analytics composition.
- `apps/api/app/research/` + `apps/api/app/refinery/` own reproducible research data and Refinery evidence composition.
- `apps/api/app/quant/` owns pure quantitative primitives; browser code renders evidence and must not silently become a second quantitative authority.
- Cloudflare Worker owns same-origin routing/static delivery/edge policy; Vercel owns Python API runtime.
- Scanner requests remain bounded at 100 symbols per chunk/request. The prior 300/500 symptom was not a configured 300-symbol cap.
- Phase 5 public methodology remains descriptive/in-sample historical evidence; it does not issue KEEP/TRIM/REPLACE, sizing or OOS claims.

Locked architectural decisions are not reopened merely because a new session/agent starts.

---

## 4. Current Phase / Batch

### C0-B — Documentation truth recovery — PUBLICATION BATCH / NO RUNTIME CHANGE

This update is a docs-only convergence based on runtime-verified `670086f...`. It supersedes the stale execution snapshot on production main and absorbs the useful authority corrections prepared in PR #81 without merging #81's older internal branch wholesale.

In scope:

- live project state;
- documentation/research contract indexes;
- Phase 5 convergence/closeout record;
- exact next execution order.

Out of scope:

- runtime/API/quant changes;
- dependency changes;
- Phase 6 implementation;
- rewriting `AI_PROJECT_PLAYBOOK.md`.

### C1-A — P5-CLOSE / PR #75 — NEXT IMPLEMENTATION BATCH

PR #75 adds a permanent bounded Refinery Phase 5 production smoke to the Cloudflare deployment acceptance flow.

Previously validated head:

`5305149a40d7c3b4390589ccb23c9b8f04d07842`

Historical evidence on that head:

- Full CI #522: PASS;
- Portfolio web CI #158: PASS;
- R2 Release Backup Gates #379/#380: PASS;
- Independent Review: PASS / BLOCKER=0;
- source ↔ smoke contract parity: PASS.

Remote truth at the **C0-B branch point**:

- runtime baseline: `670086f...`;
- #75 merge base: `2c9ed83...`;
- compare against `670086f...`: **diverged / ahead 9 / behind 2**;
- changed scope remains four files: Cloudflare deploy workflow, `package.json`, Refinery smoke script and its test;
- #75's old exact-head `Vercel` status is still failure with the historical build-rate-limit target;
- runtime baseline `670086f...` itself received a genuine Vercel production SUCCESS.

**The `ahead 9 / behind 2` numbers are branch-point evidence, not a post-C0-B cached truth.** This docs-only PR will itself advance `main` if merged, so #75 must be compared again before reconciliation.

Therefore the blocker is not accurately described as “quota only.” The candidate is stale relative to the runtime baseline and must be reconciled with the actual then-current main, then all applicable exact-head gates must be fresh.

C1-A contract:

1. re-query actual `main` after C0-B lands;
2. reconcile only the four-file #75 smoke/deployment scope;
3. preserve #83/#84 scanner changes and all then-current-main behavior;
4. do not reopen Phase 5 methodology/API semantics;
5. require fresh Full CI / Portfolio CI / genuine Vercel SUCCESS / Independent Review BLOCKER=0 / applicable recovery gate;
6. expected-head squash merge only after all gates are green;
7. post-main acceptance must actually execute Russell + Portfolio + Refinery Phase 5 smoke and PASS before Phase 5 is marked CLOSED.

---

## 5. Master Plan

| Phase / Batch | Objective | Status |
| --- | --- | --- |
| -1 through 4 | Governance, quant authority, ResearchDataset, risk math, Refinery API/UI | CLOSED / PASS |
| 5 / #65 | Clustering & Redundancy implementation | MERGED / IMPLEMENTATION PASS |
| C0-A / #84 | Scanner progress truthfulness | **CLOSED / PASS / POST-MAIN VERIFIED** |
| C0-B | Documentation truth recovery | **PUBLICATION BATCH / NO RUNTIME CHANGE** |
| C1 / #75 | Permanent Refinery production smoke + Phase 5 final acceptance | **NEXT / RECONCILIATION REQUIRED** |
| C2 / #76 | Vercel Deployment Economy internal→candidate→main proof | INTERNAL PASS / CANDIDATE PROOF PENDING |
| C3 / #79 | Benchmark/common-window financial correctness | P0 / IMPLEMENTATION-READY |
| C4 / #80 | Scanner acceptance reconciliation after #83/#84 | PARTIALLY CLOSED / ISSUE STILL OPEN |
| C5 / #78 | Scanner selection → optimizer handoff | HIGH / RCA COMPLETE / IMPLEMENTATION-READY |
| 6 / #77 | Marginal Remove/Add/Replace experiments | SPEC FROZEN / SATURATED / LOCKED |
| 7 | Walk-Forward / Research Validity | PLANNED |
| 8 | Selection Policy | PLANNED |
| 9 | Sizing | PLANNED |
| 10 | Validated Exhaustive Integration | PLANNED |
| 11 | Point-in-Time Universe / Fundamentals | PLANNED |

Phase 6 unlock requires all of:

1. P5-CLOSE #75 CLOSED/PASS;
2. Deployment Economy merged/post-main verified;
3. #79 CLOSED/PASS;
4. #80 acceptance reconciled/CLOSED or its remaining blocker explicitly separated;
5. #78 CLOSED/PASS.

When unlocked, begin only **P6-A: contract + one-fetch experiment union + frozen global common daily/weekly samples + exact sample fingerprints + no-plan parity**. Do not implement P6-B–D in the same batch.

---

## 6. Decision Log

### D-01 — Governance V3 remains frozen
Decision: `AI_PROJECT_PLAYBOOK.md` remains engineering governance authority. Operational progress is not a Reopen Condition. Status: LOCKED.

### D-02 — Contract authority is separate from operational closeout
Decision: merged Phase 5 clustering/redundancy contract `.2` and API response schema `.3` are current authorities even while P5-CLOSE production-smoke acceptance remains pending. Status: LOCKED.

### D-03 — No branch-protection / Vercel bypass
Decision: external quota/control-plane failures are classified separately but do not justify weakening required checks, force merge, or no-op commits. #84's stuck required `validate` state was resolved by rerunning the same exact-head workflow. Status: LOCKED.

### D-04 — #79 is a comparison-context authority defect
Decision: fix #79 by carrying one authoritative common comparison context/effective bounded benchmark source across the Portfolio service/API boundary. Do not patch only `_benchmark_payload()` with an ad-hoc date slice. Status: IMPLEMENTATION-READY.

### D-05 — #80 fixed scope remains convergent
Decision: #83 and #84 close two proven root/presentation defects. Do not reopen cache/back-end orchestration merely because Issue #80 is still open; first reconcile the original acceptance matrix and isolate only remaining reproducible gaps. Status: LOCKED FOR C4 REVIEW.

### D-06 — Phase 6 planning is saturated
Decision: Issue #77 is the authoritative frozen Phase 6 V1 plan. No additional Phase 6 features/formulas/ranking/sizing work before unlock. Status: LOCKED.

---

## 7. Root Cause Log

### RC-79 — Benchmark bypasses common comparison window — OPEN / P0

Symptom: portfolio rows are recomputed on `common-runnable-portfolios-v1` while separately serialized benchmark metrics can represent longer full history.

Failure point: `PortfolioAPIService._benchmark_payload()` independently simulates from original `histories.histories`.

Root cause: `PortfolioLedgerService` computes the authoritative common comparison window but `PortfolioBatchResult` does not carry that context across the service boundary.

Systemic cause: orchestration/effective-sample context ownership is incomplete across layers.

Required prevention: API-level parity tests for dates, tail-risk observations, CAGR/final-balance identity, income window and benchmark-dependent analytics.

### RC-80-A — Retryable scan edge-cache poisoning — RESOLVED

Root cause: Cloudflare admitted `/api/scan` HTTP-200 responses without proving all requested symbols resolved; retryable symbol failures could therefore be cached and replayed.

Fix: PR #83 caches scan responses only when valid `X-Scan-Requested` and `X-Scan-Resolved` prove complete resolution; missing/invalid/mismatched evidence fails closed. Verification: merged/deployed/verified at `b937b9e...`.

### RC-80-B — Settled count mislabeled as successful/completed count — RESOLVED

Root cause: presentation semantics treated `job.results.length` as success/completion even though terminal failures are also settled results.

Fix: PR #84 reports settled/success/failed/unfinished truthfully without changing scanner orchestration. Verification: merged to runtime baseline `670086f...`; Full CI, Portfolio CI, Cloudflare deploy/smokes and Vercel PASS.

### RC-78 — Scanner/optimizer migration authority mismatch — OPEN / R1

Root cause: scanner normalizes legacy date payloads before writing the manual handoff; optimizer validates against the raw persisted job without the same normalization authority.

Required fix: one shared pure scan-job normalizer, preserving strict provenance/fail-closed validation.

---

## 8. Change Log

### 2026-08-11 — Phase 5 parent
- #65 merged Phase 5 clustering/redundancy methodology/implementation.
- Initial post-main CI / Portfolio / Vercel / existing Cloudflare gates passed.
- Permanent bounded Refinery production analyze smoke remained missing, creating P5-CLOSE #75.

### 2026-08-11 — 80-FIX-A / PR #83
- deterministic root-cause reproduction identified retryable `/api/scan` HTTP-200 edge-cache poisoning;
- narrow cache-admission fix merged and production verified;
- no chunk-size/retry-budget shotgun change.

### 2026-08-11 — C0-A / PR #84
- corrected settled-vs-success UI semantics;
- added deterministic 500-symbol regression coverage;
- fixed parent asset cache-busting before merge;
- exact-head review BLOCKER=0;
- expected-head squash merge → `670086f...`;
- post-main Full CI / Portfolio CI / Cloudflare deploy + Russell/Portfolio smokes / Vercel PASS.

### 2026-08-11 — C0-B documentation convergence
- restore remote-truth alignment from runtime-verified baseline;
- promote `REFINERY_CLUSTERING_V1.md` into canonical research indexes;
- stop describing #65 as pre-merge;
- replace stale “#75 quota-only blocker” wording with current-main reconciliation requirements;
- record #83/#84 outcomes and #80 acceptance-convergence status;
- absorb #81's useful content without its stale branch ancestry;
- classify exact SHAs/compare counts as branch-point evidence so the handoff does not become stale merely because this docs PR advances `main`.

---

## 9. Known Issues

### #75 — P5-CLOSE production smoke
OPEN / reconciliation required. At the C0-B branch point the old candidate was two commits behind runtime baseline `670086f...`; this docs merge itself may add another docs-only commit. **Fresh compare required after C0-B lands.**

### #79 — P0 financial/backtest correctness
OPEN / implementation-ready. Must precede #80 closeout/#78/Phase 6 after Deployment Economy.

### #80 — Scanner reliability umbrella
OPEN / acceptance reconciliation pending.

Resolved children:
- 80-FIX-A / #83: root cache defect CLOSED/PASS/production verified;
- 80-FIX-B / #84: settlement presentation CLOSED/PASS/production verified.

Remaining review:
- compare original #80 mandatory test/behavior matrix against landed #83/#84 coverage;
- verify whether any true whole-job interruption remains after root cache fix;
- residual presentation candidate: retry-requeued chunk range can temporarily be inferred from settled count and show a misleading range (for example first 401–500 request displayed as 301–400). Separate narrow NEXT item only if still reproducible/valuable.

### #78 — Scanner → optimizer manual handoff
OPEN / root cause identified / R1 implementation-ready after #80 acceptance closeout.

### #76 — Deployment Economy
Internal-stage PASS only. Candidate/main behavior remains unproven and must be demonstrated after P5-CLOSE.

---

## 10. Technical Debt

BACKLOG unless promoted by new evidence:

- 80-HARDEN: reduce Yahoo request amplification / metadata fan-out and improve scan production diagnostics;
- instrument/security master and regional factor routing;
- traceable theme taxonomy/provider;
- globally distributed Refinery rate limiting;
- Cloudflare deploy timeout-vs-retry-budget formal alignment;
- GitHub Actions immutable-SHA pinning review;
- stale historical Actions registry cleanup if a supported mutation path becomes available;
- single-portfolio + shorter-benchmark strict-comparison policy, separate from #79's confirmed multi-portfolio defect;
- point-in-time Universe/fundamentals in Phase 11.

Do not pull these into the active batch without an Expansion Trigger.

---

## 11. Deferred / Rejected Candidates

### Deferred
- instrument/security master;
- regional factor routing;
- traceable theme provider;
- variant-level full Phase 5 bootstrap inside marginal experiments unless later performance/methodology evidence justifies it;
- persistence of Phase 6 experiment plans unless real user need requires a schema migration.

### Rejected for current requirements
- branch-protection or Vercel bypass;
- no-op/empty commits to retry deployment quota;
- increasing scanner chunk size merely to hide a reliability symptom;
- hand-merging generated bundles;
- forced dependency remediation without evidence;
- magic 0–100 redundancy score;
- hidden KEEP/TRIM/REPLACE, selection or sizing before their validated phases;
- OOS claims from full-period Phase 5 evidence;
- reopening superseded PR #66 general docs;
- merging PR #81 wholesale from its stale internal base;
- further V3 governance expansion without a documented Reopen Condition.

---

## 12. Risks

| Risk | Current control |
| --- | --- |
| Live docs drift from remote truth | Remote state has precedence; exact SHAs/compare counts are labeled branch-point evidence; re-query before acting |
| #75 carries stale base / old Vercel evidence | Reconcile from actual current main and rerun all applicable exact-head gates |
| Quantitative period/sample contamination (#79) | P0 before Phase 6; one comparison-context authority + orchestration-level regression |
| Scanner issue scope re-expands after #83/#84 | C4 acceptance reconciliation first; only reproducible residual gaps become new narrow work |
| Vercel Preview quota churn | Complete #76 internal→candidate→main operating model; never bypass required check |
| Phase 6 scope creep | #77 SPEC FROZEN/SATURATED; unlock gates + P6-A only |
| Generated/static asset cache drift | Explicit cache-busting and browser/E2E validation; #84 review caught and fixed this class |

Priority: **Safety / data integrity / production stability > current feature > optimization.**

---

## 13. NOW / NEXT / BACKLOG / REJECT

### NOW
- Publish this documentation convergence through normal PR/review/CI.
- Preserve #75 scope while preparing its current-main reconciliation; do not mutate the old candidate merely to retrigger Vercel.

### NEXT
1. C1 / #75 current-main reconciliation → exact-head gates → expected-head merge → Refinery production smoke closeout.
2. C2 / #76 reconcile/promote one deliberate `candidate-*` → genuine Vercel proof → merge/post-main verification.
3. C3 / #79 P0 common-window benchmark correctness.
4. C4 / #80 acceptance reconciliation; close or isolate only residual reproducible issue(s).
5. C5 / #78 shared scan-job normalization handoff fix.
6. Phase 6 P6-A only after all unlock gates pass.

### BACKLOG
Use §10 Technical Debt.

### REJECT
Use §11 Rejected candidates.

---

## 14. Next Actions / Exact Resume Point

After this documentation snapshot lands on `main`:

1. re-query actual `main` SHA and PR #75 head/base/mergeability/statuses;
2. run a fresh compare of #75 against that actual `main`; do not reuse the C0-B `ahead 9 / behind 2` snapshot as current truth;
3. create a recovery/current-main reconciliation path for #75 without expanding its four-file scope;
4. preserve current `package.json` additions from #83/#84 while adding only #75 smoke/test wiring;
5. verify the reconciled diff contains no scanner/runtime/methodology changes outside the smoke/deploy gate;
6. run exact-head Full CI + Portfolio CI + genuine required Vercel + applicable recovery gate;
7. perform exact-head Independent Review; findings only BLOCKER/FOLLOW-UP/BACKLOG/REJECT;
8. BLOCKER=0 + all gates green → expected-head squash merge #75;
9. require new-main CI / Portfolio / Vercel / backup where applicable and Cloudflare deployment with Russell + Portfolio + **Refinery Phase 5** smoke actually PASS;
10. only then record Phase 5 **CLOSED / PASS** and proceed to #76.

Primary implementation work remains single-lane: **C1-A / #75 reconciliation**.
