# BacktestStock — Live Project Status & Handoff

> Repository-internal live execution authority. Mutable facts such as SHA, PR/check/deployment state and protection rules must always be re-queried before acting. Durable architecture belongs in README/contracts/ADRs; detailed execution history remains reconstructable from Git/PR history.

## 1. Current objective

Phase 5 implementation and methodology are merged to production `main`; the remaining primary work is **P5-CLOSE production acceptance**.

**Primary Active Batch: PR #75 — permanent Refinery Phase 5 production smoke gate.**

Do not start Phase 6 until all explicit unlock gates in §7 are CLOSED/PASS.

---

## 2. Production / stable state

- Repository: `chihung1024/backteststock`.
- Current production `main` checkpoint at this handoff: `2c9ed83cedea9aee9acc09fa3f0a2029c3004907` (Phase 5 parent #65 merged).
- PR #68 — V3 governance/document authority cleanup: **CLOSED / PASS / POST-MAIN VERIFIED**.
- PR #70 / Issue #69 — Portfolio common comparison window + side-by-side results: **CLOSED / PASS / POST-MAIN VERIFIED**.
- PR #71 — Phase 5 M1–M4 correctness/security convergence: **MERGED / PASS**.
- PR #74 — latest-main reconciliation into the corrected Phase 5 parent: **MERGED / PASS**.
- PR #65 — Phase 5 clustering/redundancy implementation: **MERGED TO MAIN / IMPLEMENTATION PASS**.

Phase 5 public identities on main:

```text
REFINERY_CLUSTERING_CONTRACT_VERSION = refinery-clustering-twd-2026-08-10.2
REFINERY_API_CONTRACT_VERSION        = refinery-v1
REFINERY_API_SCHEMA_VERSION          = refinery-v1-2026-08-10.3
```

Security remediation remains:

- `wrangler@4.120.1`;
- `@cloudflare/workers-types@5.20260810.1`;
- `miniflare@5.20260804.0-alpha`;
- transitive `undici@7.29.0`;
- last fresh full/prod npm audit evidence: **0 / 0 vulnerabilities**.

Always re-query current remote truth before any merge or deployment action.

---

## 3. P5-CLOSE — PR #75 — ACTIVE / EXTERNAL GATE BLOCKED

PR #75 adds a permanent bounded production smoke for Refinery Phase 5 and wires it into the existing Cloudflare deployment acceptance flow.

Last validated exact head:

`5305149a40d7c3b4390589ccb23c9b8f04d07842`

Known exact-head evidence:

- Full CI #522: **PASS**;
- Portfolio web CI #158: **PASS**;
- R2 Release Backup Gates #379/#380: **PASS**;
- Independent Review: **PASS / BLOCKER=0**;
- source ↔ production-smoke contract parity: **PASS**;
- changed scope: deployment workflow + smoke script/test/package validation wiring only.

### Current blocker

Required GitHub `Vercel` status is failing because the Vercel Free-plan daily deployment quota was exceeded (`api-deployments-free-per-day`). This is an external platform quota blocker, not a proven build defect.

Rules while blocked:

- no no-op/empty commit to retrigger Vercel;
- no removal/weakening of the required `Vercel` check;
- no generic deployment used as a substitute for the exact Git revision;
- no merge until the exact candidate receives a genuine required Vercel SUCCESS.

When Vercel recovers: re-query head/mergeability/statuses → final TOCTOU → expected-head squash merge #75 → require new-main Full CI, Portfolio CI, Vercel production, post-merge backup and Cloudflare deployment where Russell, Portfolio and `Smoke test production Refinery v1 Phase 5 flow` actually execute and PASS. Only then record **P5-CLOSE CLOSED/PASS**.

Known Phase 5 limitations to preserve at closeout:

- full-period evidence is in-sample, not OOS validation;
- factor model remains a scoped `U.S.-factor co-movement diagnostic`;
- instrument/security master, regional factor routing and traceable theme authority remain later work.

---

## 4. Vercel Deployment Economy — PR #76 — INTERNAL VALIDATION PASS

Draft PR #76 validates a deployment-economy model without consuming Preview quota during internal iteration.

Last validated internal head:

`7ef82fa6353cbf41781449d7321a5e2739937b26`

Evidence:

- `internal-*` is disabled through `git.deploymentEnabled` while unspecified branches remain enabled;
- two independent internal pushes produced **GitHub Full CI PASS and zero Vercel Preview/status** (#523/#524);
- deployment-contract regression test prevents accidental global Vercel disable;
- focused review: **PASS / BLOCKER=0**;
- official Vercel semantics agree with the branch-pattern policy.

This internal evidence does **not** yet prove candidate/main behavior. After P5-CLOSE, reconcile with current main, promote one deliberate `candidate-*`, obtain one genuine Vercel Preview, run exact-head gates/review/recovery, merge, and verify production main deployment remains enabled.

Operational principle going forward: internal RCA/iteration should not consume Preview deployments; multi-file changes should prefer atomic commits; Vercel should validate real candidates rather than every intermediate AI edit.

---

## 5. Priority correctness / reliability work after Deployment Economy

### #79 — P0 correctness — benchmark bypasses common comparison window

**Priority: first product fix after Deployment Economy.**

Confirmed production defect: requested portfolios are recomputed on the common comparison window, while `PortfolioAPIService._benchmark_payload()` can re-simulate the benchmark from the original full history. This can mix different periods under one common-window warning and corrupt comparability of final balance, CAGR, income and tail-risk sample counts.

Execution authority: Issue #79 body plus the frozen implementation/review comments recorded on GitHub. Key invariant: one authoritative effective bounded/reset benchmark source must serve portfolio benchmark metrics, benchmark serialization and benchmark-dependent analytics while common-window mode is active.

### #80 — P1 reliability — 500-symbol scan stops after 300

User production observation: `已還原 300 / 500 檔，未完成 200 檔` with a resumable button instead of completing all five 100-symbol chunks.

Confirmed architecture:

- frontend chunk size = 100;
- backend `/api/scan` max request = 100;
- therefore 300 is **not** a configured cap;
- existing tests cover 101/125-symbol multi-chunk happy paths and one-symbol repeated 503 termination, but not a 500-symbol five-chunk run or a fourth-chunk failure/resume scenario.

Issue #80 owns RCA and mandatory tests. Do not “fix” by increasing chunk size; find the orchestration/interruption root cause and preserve exact pending/result invariants.

### #78 — UX correctness — selected scanner symbols not auto-loaded into optimizer

After #79 and #80, fix scanner → optimizer manual-selection handoff using one shared scan-job normalization/provenance authority. Preserve fail-closed provenance and add legacy saved-job → select 20 → optimizer exact 20 regression.

---

## 6. Documentation / governance state

- `AI_PROJECT_PLAYBOOK.md` V3 remains the governance constitution; **do not reopen it** merely because operational status changed.
- `docs/README.md` is documentation navigation, not live status.
- `docs/research/README.md` owns the current research contract map.
- `docs/research/PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md` is Phase 5 convergence/closeout evidence, not the live task queue.
- Historical `docs/portfolio-migration/*` and `docs/PHASE_MINUS1_GOVERNANCE.md` remain only for unique audit value.
- PR #66 remains **CLOSED / SUPERSEDED / NOT MERGED**; never wholesale restore its stale general docs.

---

## 7. Roadmap / unlock gates

| Phase / Batch | Objective | Status |
| --- | --- | --- |
| -1 through 4 | Governance, quant authority, dataset, risk math, Refinery API/UI | CLOSED / PASS |
| 5 / #65 | Clustering & Redundancy implementation | MERGED / IMPLEMENTATION PASS |
| P5-CLOSE / #75 | permanent Refinery production smoke + final acceptance | **ACTIVE — VERCEL QUOTA BLOCKED** |
| Deployment Economy / #76 | internal/candidate/main Preview control | INTERNAL PASS / CANDIDATE PROOF PENDING |
| #79 | Benchmark/common-window correctness | P0 / IMPLEMENTATION-READY / BLOCKED BY ABOVE |
| #80 | 500-symbol scan completion reliability | P1 / RCA + IMPLEMENTATION PLANNING |
| #78 | Scanner selection → optimizer handoff | HIGH / IMPLEMENTATION-READY |
| 6 / #77 | Marginal Experiments | SPEC FROZEN / SATURATED / LOCKED |
| 7 | Walk-Forward / Research Validity | PLANNED |
| 8 | Selection Policy | PLANNED |
| 9 | Sizing | PLANNED |
| 10 | Validated Exhaustive Integration | PLANNED |
| 11 | Point-in-Time Universe / Fundamentals | PLANNED |

**Phase 6 unlock requires all of:**

1. P5-CLOSE #75 CLOSED/PASS;
2. Deployment Economy merged/post-main verified;
3. #79 CLOSED/PASS;
4. #80 CLOSED/PASS;
5. #78 CLOSED/PASS.

Then re-read current main + this live handoff + Issue #77 body and start **only P6-A: contract + one-fetch common experiment sample**.

---

## 8. NOW / NEXT / BACKLOG / REJECT

### NOW

- Keep #75 exact candidate frozen while Vercel quota is the only blocker.
- Continue non-deployment RCA/spec/test-design/document-quality work that does not create a second runtime implementation lane.
- Maintain #76 internal evidence without claiming candidate/main proof.

### NEXT

1. #75 final merge and production closeout when Vercel succeeds.
2. #76 candidate promotion / merge / production verification.
3. #79 P0 correctness.
4. #80 P1 scan reliability.
5. #78 optimizer handoff.
6. P6-A only after all unlock gates pass.

### BACKLOG

- instrument/security master and regional factor routing;
- traceable theme taxonomy/provider;
- globally distributed Refinery rate limiting;
- Cloudflare deploy timeout-vs-retry-budget formal alignment;
- Actions immutable-SHA pinning review;
- point-in-time Universe/fundamentals in Phase 11;
- stale historical Actions registry cleanup if a supported mutation path becomes available;
- single-portfolio + shorter-benchmark strict-comparison policy (separate from #79 multi-portfolio defect).

### REJECT / guardrails

- branch-protection/Vercel bypass;
- no-op quota-retry commits;
- hand-merging generated bundles;
- forced dependency remediation;
- magic 0–100 redundancy score;
- hidden KEEP/TRIM/REPLACE or sizing recommendations before their validated phases;
- OOS claims from full-period evidence;
- reopening superseded #66 general docs;
- further V3 governance expansion without a documented Reopen Condition.

---

## 9. Exact resume point

1. Re-query PR #75 exact head and required Vercel status.
2. If Vercel remains the same quota failure, do not mutate #75; continue only safe supporting work.
3. If Vercel is genuine SUCCESS with head unchanged, execute #75 TOCTOU → expected-head merge → complete production acceptance.
4. Reconcile/promote #76 into one deliberate Vercel-enabled candidate and post-main verify.
5. Execute #79 from its frozen Issue authority.
6. Execute #80 from its RCA/mandatory-test authority.
7. Execute #78.
8. Only then unlock Issue #77 / P6-A.
