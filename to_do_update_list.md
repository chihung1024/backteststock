# BacktestStock — Live Project Status & Handoff

> Repository-internal live execution authority. Mutable facts such as current SHA, PR/check/deployment state and protection rules must always be re-queried before acting. Durable architecture belongs in README/contracts/ADRs; detailed execution history remains reconstructable from Git/PR history.

## 1. Project Status

Primary goal: complete **C2 — Vercel Deployment Economy** safely, then execute the frozen correctness/reliability sequence before Phase 6.

Last runtime-verified production checkpoint before this docs-only closeout publication:

`dd051ba793ab63260b4815ae35020cb40f55c7d5`

**Phase 5 = CLOSED / PASS / POST-MAIN PRODUCTION VERIFIED.**

P5-CLOSE PR #75 is merged. The permanent Cloudflare production acceptance flow now executes Russell 2000, Portfolio v3 and bounded Refinery v1 / Phase 5 production smoke tests.

Current Primary Active Batch after this closeout record lands:

**C2 — Vercel Deployment Economy: reconcile validated internal policy #76 with current main, prove one genuine `candidate-*` Vercel Preview, then merge/post-main verify.**

Do not begin #79 implementation or Phase 6 while C2 is active.

---

## 2. Stable State

### Runtime / production

- Repository: `chihung1024/backteststock`.
- Last runtime-verified main: `dd051ba793ab63260b4815ae35020cb40f55c7d5`.
- #65 Phase 5 clustering/redundancy: MERGED / implementation PASS.
- #83 scanner retryable edge-cache root fix: MERGED / production verified.
- #84 scanner settled-vs-success presentation: MERGED / production verified.
- #86 documentation truth recovery: MERGED / post-main CI PASS.
- #75 permanent Refinery production smoke / P5-CLOSE: MERGED / production verified.

### P5-CLOSE final evidence at `dd051ba...`

- Full CI #550: **PASS**.
- Portfolio web CI #170: **PASS**.
- Vercel production status: **SUCCESS**.
- Release Backup Gates #413 `create-post-merge-backup`: **PASS**; pre-merge release verified.
- Cloudflare deployment #51: **PASS**.
- `Smoke test production Russell 2000 flow`: **PASS**.
- `Smoke test production Portfolio v3 flow`: **PASS**.
- `Smoke test production Refinery v1 Phase 5 flow`: **PASS**.

Phase 5 limitations remain explicit:

- full-period Phase 5 evidence is in-sample, not OOS validation;
- factor evidence remains a scoped U.S.-factor co-movement diagnostic;
- instrument/security master, regional factor routing and traceable theme authority remain later work.

Rollback/recovery: use verified release backups created by the generic Release Backup Gates and normal source revert/redeploy procedures. Never force history to recover a production regression.

---

## 3. Architecture Notes

Locked authorities remain unchanged:

- `TWDHistoryService` — audited market history / TWD valuation authority.
- `apps/api/app/portfolio/` — Portfolio ledger, metrics, comparison and analytics composition.
- `apps/api/app/research/` + `apps/api/app/refinery/` — ResearchDataset and Refinery evidence composition.
- `apps/api/app/quant/` — pure quantitative primitives.
- browser code — presentation only; no second quantitative authority.
- Cloudflare Worker — same-origin routing/static/edge policy and production acceptance path.
- Vercel — Python API deployment runtime.

Current Phase 5 public identities remain:

```text
REFINERY_CLUSTERING_CONTRACT_VERSION = refinery-clustering-twd-2026-08-10.2
REFINERY_API_CONTRACT_VERSION        = refinery-v1
REFINERY_API_SCHEMA_VERSION          = refinery-v1-2026-08-10.3
```

Do not reopen V3 governance, Phase 5 methodology or Phase 6 frozen semantics without a documented Reopen Condition.

---

## 4. Current Phase / Batch

### C1 / P5-CLOSE — CLOSED / PASS

PR #75 merged to `main@dd051ba...` using expected-head squash after:

- exact-head Full CI #548 PASS;
- Portfolio CI #169 PASS;
- R2 Release Backup Gates #409 PASS;
- Vercel SUCCESS;
- exact-head Independent Review on reconciled `4a431af...`: PASS / BLOCKER=0;
- GitHub current-main compare remained a four-file product diff and mergeable.

Post-main production acceptance then passed all required gates listed in §2.

### C2 / PR #76 — PRIMARY ACTIVE BATCH

Purpose: reduce wasteful Vercel Preview churn during internal AI iteration without weakening required candidate/main deployment validation.

Validated internal-stage head:

`7ef82fa6353cbf41781449d7321a5e2739937b26`

Internal scope is exactly four files:

- `vercel.json` — `git.deploymentEnabled["internal-*"] = false`;
- `docs/DEPLOYMENT.md` — branch/deployment-budget operating procedure;
- `docs/VERCEL_DEPLOYMENT_ECONOMY.md` — detailed policy contract;
- `tests/test_deployment_contract.py` — regression guard against global Vercel disable.

Historical internal evidence:

- two `internal-*` pushes ran GitHub Full CI but produced no Vercel Preview/status;
- Full CI #523/#524 PASS;
- focused internal review BLOCKER=0;
- candidate/main behavior intentionally remained unproven.

Current remote state at this closeout branch point:

- #76 is open Draft / internal validation only;
- #76 head `7ef82fa...`;
- against runtime main `dd051ba...`: **diverged / ahead 2 / behind 4**;
- actual diff remains exactly the intended four deployment-governance files;
- PR itself is not a merge candidate and must remain internal evidence.

C2 execution contract:

1. re-query actual main after this docs-only closeout lands;
2. reconstruct/reconcile the validated four-file policy on that main without reopening scope;
3. validate on an `internal-*` branch that GitHub CI runs while Vercel Preview/status remains absent;
4. promote the exact validated tree to one deliberate Vercel-enabled `candidate-*` branch;
5. require genuine candidate Vercel SUCCESS plus applicable CI/review/recovery gates;
6. merge only the candidate PR, not the stale #76 internal PR;
7. verify main production Vercel deployment remains enabled/successful;
8. close/supersede #76 only after candidate/post-main proof.

---

## 5. Master Plan

| Phase / Batch | Objective | Status |
| --- | --- | --- |
| -1 through 4 | Governance, quant authority, dataset, risk math, Refinery API/UI | CLOSED / PASS |
| 5 / #65 | Clustering & Redundancy implementation | CLOSED / PASS |
| C0-A / #84 | Scanner progress truthfulness | CLOSED / PASS / VERIFIED |
| C0-B / #86 | Documentation truth recovery | CLOSED / PASS |
| C1 / #75 | Refinery production smoke + Phase 5 closeout | **CLOSED / PASS / PRODUCTION VERIFIED** |
| C2 / #76 | Vercel Deployment Economy | **PRIMARY ACTIVE — INTERNAL→CANDIDATE→MAIN PROOF** |
| C3 / #79 | Benchmark/common-window financial correctness | NEXT / P0 / IMPLEMENTATION-READY |
| C4 / #80 | Scanner acceptance reconciliation after #83/#84 | NEXT AFTER #79 |
| C5 / #78 | Scanner selection → optimizer handoff | RCA COMPLETE / BLOCKED BY C4 |
| 6 / #77 | Marginal Remove/Add/Replace experiments | SPEC FROZEN / SATURATED / LOCKED |
| 7–11 | OOS, selection, sizing, Exhaustive integration, PIT data | PLANNED |

Phase 6 unlock requires:

1. C2 Deployment Economy CLOSED/PASS;
2. #79 CLOSED/PASS;
3. #80 acceptance reconciled/CLOSED or residual issue explicitly separated;
4. #78 CLOSED/PASS.

Then start only P6-A.

---

## 6. Decision Log

### D-01 — Governance V3 frozen
`AI_PROJECT_PLAYBOOK.md` remains process authority. Status: LOCKED.

### D-02 — Phase 5 contract vs acceptance
Phase 5 implementation authority and operational closeout are now both complete. Status: CLOSED.

### D-03 — No Vercel/branch-protection bypass
Quota/control-plane failures are classified separately but never justify weakening required checks or no-op commits. Status: LOCKED.

### D-04 — Deployment Economy policy
`internal-*` may suppress automatic Vercel Git deployments; `candidate-*` and `main` must remain Vercel-enabled. Candidate/main proof is mandatory before C2 closeout. Status: ACTIVE.

### D-05 — #79 comparison-context authority
#79 must carry one authoritative common comparison context across Portfolio service/API boundaries; no ad-hoc benchmark date-slice patch. Status: LOCKED / NEXT.

### D-06 — #80 convergence
#83/#84 are resolved; reconcile original #80 acceptance matrix before opening any further scanner implementation. Status: LOCKED.

### D-07 — Phase 6 planning saturated
Issue #77 is frozen authoritative plan; no further feature/formula expansion before unlock. Status: LOCKED.

---

## 7. Root Cause Log

### RC-79 — OPEN / P0
`PortfolioLedgerService` owns the common comparison window, but `PortfolioBatchResult` does not carry that context to `PortfolioAPIService`; benchmark serialization can therefore resimulate from original full histories. Systemic cause: effective-sample context authority is lost across layers.

### RC-80-A — RESOLVED
Retryable `/api/scan` HTTP-200 results were admitted to edge cache without proof of complete symbol resolution. #83 introduced fail-closed cache admission.

### RC-80-B — RESOLVED
`job.results.length` represented settled rows but UI labeled it as completed/successful. #84 introduced truthful settled/success/failed/unfinished semantics.

### RC-78 — OPEN / R1
Scanner normalizes legacy persisted scan-job dates while optimizer validates raw persisted data. Required fix: one shared pure normalization authority, preserving strict provenance validation.

---

## 8. Change Log

### 2026-08-11 — C0-A / #84
Scanner progress truth fix merged and production verified.

### 2026-08-11 — C0-B / #86
Live handoff and documentation indexes rebuilt from current main; old #81 closed as superseded.

### 2026-08-11 — C1 / #75
- reconciled #75 with runtime main while preserving #83/#84 scanner validation;
- exact-head CI/Portfolio/backup/Vercel/review passed;
- expected-head squash merged to `dd051ba...`;
- post-main CI #550, Portfolio #170, Vercel, backup #413 and Cloudflare deploy #51 all passed;
- Russell + Portfolio + Refinery Phase 5 production smokes all passed;
- **Phase 5 CLOSED / PASS**.

---

## 9. Known Issues

### #76 Deployment Economy
ACTIVE / internal validation PASS / candidate and main proof pending.

### #79 P0 financial correctness
OPEN / implementation-ready; next product correctness batch after C2.

### #80 scanner reliability umbrella
OPEN / acceptance reconciliation pending. #83 and #84 are already production-verified; do not reopen their fixed scope without new evidence.

Residual candidate: retry-requeued chunk range may temporarily display a misleading range due to presentation inference. Separate only if reproducible/valuable.

### #78 scanner → optimizer manual handoff
OPEN / RCA complete / R1 implementation-ready after #80 reconciliation.

---

## 10. Technical Debt

BACKLOG:

- Yahoo request amplification / metadata fan-out and scanner diagnostics hardening;
- instrument/security master and regional factor routing;
- traceable theme taxonomy/provider;
- distributed Refinery rate limiting;
- Cloudflare timeout-vs-retry-budget formal alignment;
- GitHub Actions immutable-SHA pinning review;
- historical Actions registry cleanup where supported;
- single-portfolio + shorter-benchmark strict-comparison policy;
- point-in-time Universe/fundamentals in Phase 11.

---

## 11. Deferred / Rejected

Deferred: instrument master, regional factor routing, traceable themes, Phase 6 variant bootstrap, experiment-plan persistence.

Rejected now: branch/Vercel bypass, no-op quota commits, scanner chunk-size workaround, generated-bundle hand merge, forced dependency remediation without evidence, magic scores, hidden recommendations/sizing, OOS claims from in-sample evidence, V3 governance expansion, Phase 6 scope expansion.

---

## 12. Risks

| Risk | Control |
| --- | --- |
| Internal AI commits consume Vercel quota | C2 `internal-*` suppression + explicit candidate/main proof |
| Deployment policy accidentally disables all Vercel Git deploys | regression test requires branch-pattern object and candidate/main enabled |
| #79 financial sample contamination | P0 immediately after C2; one comparison-context authority + API/E2E regression |
| Scanner work re-expands | reconcile #80 acceptance first |
| Phase 6 scope creep | #77 frozen; P6-A only after gates |

Priority remains: **Safety / data integrity / production stability > current feature > optimization.**

---

## 13. NOW / NEXT / BACKLOG / REJECT

### NOW
- publish this P5-CLOSE status update;
- execute only C2 Deployment Economy.

### NEXT
1. C2 current-main internal validation → candidate proof → merge/post-main Vercel proof.
2. C3 / #79 P0 correctness.
3. C4 / #80 acceptance reconciliation.
4. C5 / #78 handoff fix.
5. P6-A only after unlock.

### BACKLOG / REJECT
Use §§10–11.

---

## 14. Next Actions / Exact Resume Point

After this docs-only Phase 5 closeout record lands:

1. re-query actual main and #76 remote state;
2. create a current-main-based `internal-*` recovery branch containing exactly the validated four-file Deployment Economy policy;
3. verify diff scope and run Full CI while confirming **no Vercel Preview/status** on the internal head;
4. Independent Review the exact internal tree;
5. promote the same validated tree to one deliberate `candidate-*` branch;
6. require genuine Vercel Preview SUCCESS plus CI/review/recovery gates;
7. merge the candidate PR by expected head;
8. verify `main` production Vercel deployment still occurs and succeeds;
9. close/supersede #76 and record C2 CLOSED/PASS;
10. begin C3 / #79 only after C2 is complete.

**Primary Active Batch = C2 Deployment Economy.**
