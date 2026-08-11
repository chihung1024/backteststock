# BacktestStock — Live Project Status & Handoff

> Repository-internal live execution authority. Mutable facts such as current SHA, PR/check/deployment state and protection rules must always be re-queried before acting. Durable architecture belongs in README/contracts/ADRs; detailed execution history remains reconstructable from Git/PR history.

## 1. Project Status

Primary goal: execute **C3 / Issue #79 — P0 financial/backtest correctness: one authoritative common comparison context for requested portfolios and benchmark**.

Last runtime-verified production baseline before this docs-only handoff publication:

`79a71bb5f9d6e73a29b4f4e4598fe320dce73730`

This handoff publication may advance repository `main` without changing runtime behavior. Always re-query actual `main` before implementation.

Closed foundations:

- Phase 5 clustering/redundancy: **CLOSED / PASS / PRODUCTION VERIFIED**.
- C2 Vercel Deployment Economy: **CLOSED / PASS / INTERNAL→CANDIDATE→MAIN VERIFIED**.

**Primary Active Batch after this handoff lands: C3 / #79 P0 correctness.**

Do not start #80, #78 or Phase 6 implementation while #79 is active.

---

## 2. Stable State

### Runtime / production baseline

- Repository: `chihung1024/backteststock`.
- Last runtime-verified main: `79a71bb5f9d6e73a29b4f4e4598fe320dce73730`.
- #65 Phase 5 clustering/redundancy: MERGED / VERIFIED.
- #83 scanner retryable edge-cache root fix: MERGED / VERIFIED.
- #84 scanner settled-vs-success presentation: MERGED / VERIFIED.
- #75 permanent Refinery production smoke / P5-CLOSE: MERGED / VERIFIED.
- #90 Vercel Deployment Economy policy: MERGED / VERIFIED.

### Phase 5 final acceptance

At `dd051ba793ab63260b4815ae35020cb40f55c7d5`:

- Full CI #550 PASS;
- Portfolio web CI #170 PASS;
- Vercel production SUCCESS;
- post-merge recovery #413 PASS;
- Cloudflare deploy #51 PASS;
- Russell + Portfolio v3 + Refinery v1 / Phase 5 production smokes PASS.

Phase 5 limitations remain explicit: full-period evidence is in-sample, factor evidence remains a scoped U.S.-factor co-movement diagnostic, and instrument/security master / regional factor routing / traceable theme authority remain later work.

### C2 Deployment Economy final acceptance

Policy now on `main`:

```json
"git": {
  "deploymentEnabled": {
    "internal-*": false
  }
}
```

Verified behavior:

- current-main internal head `4e09485cf35f458aeca9b965440ec0c37e882a93`, tree `413272b20a1cc715abe3cb0ad86e6026d71fdd72`:
  - Full CI #554 PASS;
  - Vercel commit statuses remained empty before/during/after CI;
  - focused review PASS / BLOCKER=0.
- candidate head `9c80dbee3ba75bbe2625d4a04476af76bcbc2b77` used the **same tree** `413272b...`:
  - Full CI #555 PASS;
  - genuine Vercel Preview SUCCESS;
  - R2 pre-merge recovery PASS;
  - Independent Review PASS / BLOCKER=0.
- expected-head squash merge PR #90 → `main@79a71bb...`:
  - Full CI #556 PASS;
  - genuine Vercel production SUCCESS;
  - post-merge recovery PASS;
  - no Cloudflare production deploy was invented because the changed files do not match Cloudflare deploy trigger/runtime paths.
- old internal evidence PR #76 and current-main validation PR #89 are CLOSED / NOT MERGED.

Operational conclusion: **iterate on `internal-*` with GitHub CI and zero automatic Vercel Preview; promote only a converged tree to deliberate `candidate-*`; keep `main` production deployment enabled.**

Rollback/recovery remains normal source revert + verified releases/deployments; never force history to recover production.

---

## 3. Architecture Notes

Locked authorities:

- `TWDHistoryService` — audited market history / TWD valuation authority.
- `apps/api/app/portfolio/` — Portfolio ledger, metrics, comparison and analytics composition.
- `apps/api/app/research/` + `apps/api/app/refinery/` — ResearchDataset / Refinery evidence composition.
- `apps/api/app/quant/` — pure quantitative primitives.
- browser code — presentation only; no second quantitative authority.
- Cloudflare Worker — same-origin routing/static/edge policy and production acceptance.
- Vercel — Python API runtime; Deployment Economy branch policy is current operational authority.

### C3 architecture boundary — LOCKED

The existing multi-portfolio common-window design is fundamentally correct at the service layer; do **not** rewrite Portfolio v3.

Current defect boundary:

```text
PortfolioLedgerService.run()
    computes comparison_start / comparison_end
    bounds compared portfolio histories
    ↓
PortfolioBatchResult
    currently loses authoritative comparison context
    ↓
PortfolioAPIService.backtest()
    serializes requested portfolio ledgers correctly
    BUT _benchmark_payload() resimulates benchmark from original full histories
```

C3 must restore one authoritative comparison context across this service/API boundary with the smallest correct change.

---

## 4. Current Phase / Batch

### C2 — CLOSED / PASS

Objective: reduce avoidable Vercel Preview consumption while preserving genuine candidate/main deployment validation.

Final result: internal suppression, candidate Preview, main production deployment and pre/post recovery were all independently demonstrated. Policy is now durable in `docs/VERCEL_DEPLOYMENT_ECONOMY.md` and guarded by `tests/test_deployment_contract.py`.

Reopen only if an explicit policy reopen condition occurs: internal branches still deploy, candidate cannot obtain required Vercel status, Vercel branch-rule semantics change, deployment model moves to Actions-managed deployment, or the current budget materially blocks safe delivery.

### C3 / Issue #79 — PRIMARY ACTIVE / P0 / R2

Issue: **benchmark bypasses the multi-portfolio common comparison window and can mix incomparable backtest periods.**

Confirmed production symptom: requested portfolios can report the shared `common-runnable-portfolios-v1` period while separately serialized benchmark balance/CAGR/tail-risk samples reflect a longer original history.

#### Root Cause

`PortfolioLedgerService.run()` owns `comparison_start` / `comparison_end`, but `PortfolioBatchResult` does not carry that effective-sample context across the service boundary. `PortfolioAPIService._benchmark_payload()` therefore independently simulates the benchmark from original `histories.histories`.

Systemic cause: **comparison/effective-sample authority is lost across orchestration layers.**

#### Scope Lock

In scope:

- one explicit authoritative comparison context from `PortfolioLedgerService`;
- carry that context through `PortfolioBatchResult`;
- build the benchmark from history/components bounded **before** simulation;
- align benchmark-dependent analytics to the ledger/effective sample where same-window comparability is required;
- API/orchestration-level regression tests;
- focused Portfolio browser regression where required by Issue #79.

Out of scope:

- Portfolio v3 redesign;
- unrelated metric formula changes;
- changing the existing multi-portfolio comparison policy;
- changing single-runnable-portfolio full-history behavior;
- Phase 6 common-sample implementation;
- scanner / optimizer work;
- broad persistence/schema redesign.

Allowed investigation:

- `PortfolioBatchResult` consumers;
- `PortfolioAPIService.backtest()` / `_benchmark_payload()` / `_analytics_for_result()`;
- common-window helpers and current Portfolio API models/tests;
- CSV/JSON/chart serialization paths only to classify whether they consume bounded ledger output correctly.

Expansion Trigger: public schema/persistence changes, a second independent comparison-window defect, or evidence that current service ownership cannot safely carry the required context. Any trigger requires plan review before expansion.

#### Mandatory regression invariants

1. multi-portfolio requested portfolios **and `response.benchmark`** share exact effective start/end;
2. benchmark tail-risk observations are bounded by the common-window ledger sample under documented initialization/drop semantics;
3. one-asset no-flow/no-cost/reinvested benchmark satisfies CAGR ↔ initial/final balance ↔ elapsed-period consistency;
4. benchmark distributions before `common_start` do not appear in common-window income/cumulative income;
5. if response claims `common-runnable-portfolios-v1`, every item presented as comparable, including benchmark, actually honors it;
6. Portfolio browser/E2E coverage exercises a deliberately unequal-history benchmark scenario;
7. single-runnable-portfolio behavior remains backward compatible.

#### C3 Batch sequence

**C3-A — Reproduce + contract regression**

- create current-main `internal-*` branch;
- add/extend API orchestration test that fails on current behavior;
- independently prove lower-level `PortfolioLedgerService` is not the failure point;
- record exact failure evidence before implementation.

**C3-B — Authoritative comparison context fix**

- add the smallest explicit comparison context carrier to service result;
- reuse one audited history-bounding authority before benchmark simulation;
- preserve single-portfolio semantics;
- no browser-side/math workaround.

**C3-C — Analytics / presentation regression**

- classify benchmark-dependent analytics: SAME-WINDOW REQUIRED / INTENTIONALLY DIFFERENT + explicit label / N/A;
- close only real same-window bypasses caused by the root defect;
- add focused API/E2E regression.

**C3-D — Candidate / production closeout**

- internal exact-tree CI + review;
- promote converged tree to `candidate-*`;
- genuine Vercel Preview + R2 recovery + Independent Review;
- expected-head merge;
- post-main CI/Vercel and applicable production verification;
- close #79 only when all mandatory invariants are verified.

---

## 5. Master Plan

| Phase / Batch | Objective | Status |
| --- | --- | --- |
| -1 through 4 | Governance, quant authority, dataset, risk math, Refinery API/UI | CLOSED / PASS |
| 5 / #65 + #75 | Clustering/Redundancy + production closeout | CLOSED / PASS / VERIFIED |
| C0 / #84/#86 | Scanner progress truth + docs truth recovery | CLOSED / PASS |
| C2 / #90 | Vercel Deployment Economy | **CLOSED / PASS / VERIFIED** |
| C3 / #79 | Benchmark/common-window financial correctness | **PRIMARY ACTIVE / P0 / R2** |
| C4 / #80 | Scanner acceptance reconciliation after #83/#84 | NEXT |
| C5 / #78 | Scanner selection → optimizer handoff | RCA COMPLETE / BLOCKED BY C4 |
| 6 / #77 | Marginal Remove/Add/Replace experiments | SPEC FROZEN / SATURATED / LOCKED |
| 7–11 | OOS, selection, sizing, Exhaustive integration, PIT data | PLANNED |

Phase 6 unlock requires:

1. #79 CLOSED/PASS;
2. #80 acceptance reconciled/CLOSED or residual issue explicitly separated;
3. #78 CLOSED/PASS.

C2 is no longer an unlock blocker. Then start only P6-A.

---

## 6. Decision Log

### D-01 — Governance V3 frozen
`AI_PROJECT_PLAYBOOK.md` remains process authority. Status: LOCKED.

### D-02 — Phase 5 CLOSED
Implementation and operational production closeout are both complete. Status: CLOSED.

### D-03 — No branch/Vercel bypass
Required deployment evidence must remain genuine. No no-op quota commits, force history or branch-protection weakening. Status: LOCKED.

### D-04 — Deployment Economy
`internal-*` automatic Vercel deployment suppression + deliberate `candidate-*` + `main` deployment is now production-verified. Status: **CLOSED / LOCKED**. Reopen only under policy reopen conditions in `docs/VERCEL_DEPLOYMENT_ECONOMY.md`.

### D-05 — #79 comparison-context authority
Fix the service/API context boundary, not merely `_benchmark_payload()` with an ad-hoc date slice or post-hoc ledger clipping. Status: **LOCKED / ACTIVE**.

### D-06 — #80 convergence
#83/#84 are resolved. Reconcile original #80 acceptance matrix before new scanner implementation. Status: LOCKED / NEXT.

### D-07 — Phase 6 planning saturated
Issue #77 remains authoritative frozen Phase 6 V1 plan. Status: LOCKED.

---

## 7. Root Cause Log

### RC-79 — OPEN / P0

Symptom: common-window requested portfolio rows are displayed beside benchmark output derived from a longer sample.

Failure point: `_benchmark_payload()` independently simulates benchmark from original full histories.

Contributing factor: service slices benchmark returns for requested-portfolio metric context, but that bounded context is not carried into API benchmark serialization/analytics.

Root cause: `PortfolioBatchResult` loses the authoritative common comparison window/effective-sample context.

Systemic cause: orchestration context ownership stops at the service boundary.

Prevention: explicit comparison context + API-level/sample-identity regression + focused browser parity test.

### RC-80-A — RESOLVED
Retryable `/api/scan` HTTP-200 results could be edge-cached without proof all requested symbols resolved. #83 added fail-closed cache admission.

### RC-80-B — RESOLVED
Settled rows were mislabeled as completed/successful. #84 added truthful settled/success/failed/unfinished presentation.

### RC-78 — OPEN / R1
Scanner normalizes legacy persisted scan-job dates while optimizer validates raw persisted data. Future fix: shared pure scan-job normalizer with strict provenance preserved.

---

## 8. Change Log

### 2026-08-11 — Phase 5 / P5-CLOSE
#65 and #75 completed methodology implementation and permanent production Refinery acceptance; Phase 5 CLOSED/PASS.

### 2026-08-11 — C0
#83/#84 resolved scanner cache/progress defects; #86 rebuilt live documentation truth.

### 2026-08-11 — C2 Deployment Economy
- old #76 policy was revalidated on current main through internal PR #89;
- internal `4e09485...` CI #554 PASS with zero Vercel status;
- same tree promoted to candidate `9c80dbe...`;
- candidate CI #555 / Vercel Preview / recovery / review PASS;
- PR #90 expected-head squash merged to `79a71bb...`;
- new-main CI #556 / Vercel production / post-merge recovery PASS;
- #76 and #89 closed without merge as historical/internal evidence;
- C2 **CLOSED / PASS**.

---

## 9. Known Issues

### #79 — P0 financial/backtest correctness
**PRIMARY ACTIVE.** Confirmed RCA; implement only after current-main reproduction/regression evidence.

### #80 — scanner reliability umbrella
OPEN / acceptance reconciliation pending. #83/#84 are production-verified. Do not reopen their fixed scope without new evidence.

Residual candidate only if reproducible: retry-requeued batch range can be temporarily mislabeled due to presentation inference.

### #78 — scanner → optimizer manual handoff
OPEN / RCA complete / R1 implementation-ready after #80 reconciliation.

---

## 10. Technical Debt

BACKLOG unless promoted by evidence:

- Yahoo request amplification / metadata fan-out and scanner diagnostics hardening;
- instrument/security master and regional factor routing;
- traceable theme provider/taxonomy;
- distributed Refinery rate limiting;
- Cloudflare timeout-vs-retry-budget formal alignment;
- GitHub Actions immutable-SHA pinning review;
- historical Actions registry cleanup where supported;
- single-portfolio + shorter-benchmark strict-comparison policy separate from #79;
- point-in-time Universe/fundamentals in Phase 11.

---

## 11. Deferred / Rejected

Deferred: instrument master, regional factor routing, traceable themes, Phase 6 variant bootstrap, experiment-plan persistence.

Rejected now:

- branch/Vercel bypass;
- no-op deployment retry commits;
- scanner chunk-size workaround;
- hand-merging generated bundles;
- forced dependency remediation without evidence;
- magic scores / hidden recommendation or sizing logic;
- OOS claims from in-sample evidence;
- broad Portfolio v3 rewrite for #79;
- Phase 6 scope expansion before unlock.

---

## 12. Risks

| Risk | Control |
| --- | --- |
| #79 silently mixes periods/samples | P0 single-lane root-cause fix; explicit comparison context + orchestration/E2E regression |
| Fix only patches benchmark display | require bounded history **before** simulation and audit benchmark-dependent analytics |
| C3 expands into Portfolio redesign | Scope Lock + Expansion Trigger; preserve existing service architecture |
| Internal AI work consumes Vercel quota | production-verified `internal-*` suppression; candidate-only Preview |
| Scanner work re-expands | #80 acceptance reconciliation after #79 |
| Phase 6 scope creep | #77 frozen; P6-A only after remaining gates |

Priority: **Safety / data integrity / production stability > current feature > optimization.**

---

## 13. NOW / NEXT / BACKLOG / REJECT

### NOW

- publish this C2 closeout / C3 handoff through the validated internal→candidate process;
- execute only C3 / #79 after it lands.

### NEXT

1. C3-A reproduce #79 with an API/orchestration failing regression.
2. C3-B implement one comparison-context authority + bounded benchmark resimulation.
3. C3-C analytics/E2E regression and convergence.
4. C3-D candidate/recovery/review/merge/post-main verification.
5. C4 / #80 acceptance reconciliation.
6. C5 / #78 shared scan-job normalization fix.
7. P6-A only after remaining unlock gates.

### BACKLOG / REJECT
Use §§10–11.

---

## 14. Next Actions / Exact Resume Point

After this docs-only handoff lands:

1. re-query actual `main` and Issue #79 remote state;
2. create `internal-p79-common-window-context` from exact current main;
3. inspect all `PortfolioBatchResult` consumers and current contract/version tests before changing code;
4. **C3-A first:** add an API-level deterministic reproduction where two runnable portfolios create a common window but benchmark has longer history; prove requested portfolios are bounded and serialized benchmark is not;
5. preserve the failing evidence, then implement the smallest explicit comparison-context carrier from service to API;
6. bound benchmark audited history/components **before** `simulate_portfolio_ledger()`; do not post-hoc clip the ledger;
7. audit `_analytics_for_result()` and benchmark-dependent analytics against the same effective sample; classify unrelated factor/style/inflation paths rather than refactoring them blindly;
8. run focused Portfolio service/API/common-window tests and required invariant tests;
9. add/extend Playwright only for the user-visible benchmark parity contract;
10. run full internal CI; verify no Vercel status on the internal branch;
11. exact-tree Independent Review; BLOCKER=0 → promote same converged tree to `candidate-*`;
12. genuine Vercel Preview + R2 recovery + final review → expected-head merge;
13. post-main CI/Vercel/applicable production verification;
14. close #79 only with every mandatory invariant verified.

**Primary Active Batch = C3 / #79.**
