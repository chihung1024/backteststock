# BacktestStock Development Master Plan

> Persistent execution / handoff authority for `chihung1024/backteststock`. This file must describe the **current remote reality**, not merely the intended process. A phase/batch is not DONE until status, evidence, limitations, rollback/recovery information, and exact next action are recorded here.

## 0. Document authority and staleness rule

- Engineering governance authority: `AI_PROJECT_PLAYBOOK.md`.
- Product/architecture overview: `README.md`.
- **Live project status authority inside the repository: this file.**
- Methodology/schema semantics: versioned contract docs under `docs/quant/`, `docs/research/`, ADRs and deployment/governance docs.
- Operational truth that can change outside the repository (current `main`, PR head, checks, ruleset, deployment, release) must be queried from GitHub/Vercel/Cloudflare before acting.
- If this file conflicts with current remote state, classify it as **documentation drift**, correct the file in the current Batch, and do not infer a new plan from stale text.
- Detailed document precedence and freshness requirements: `docs/PROJECT_DOCUMENTATION_POLICY.md`.

---

# 1. Project Status

## Primary Goal

Complete **Phase 5 — Clustering & Redundancy** correctly and close it before starting Phase 6.

## Current authoritative remote state

- Production branch: `main`.
- Current `main`: `db3e692e3e4ce1962d6953988464947b35d5ef82` — Phase 4 closeout PR #64.
- Phase 4: **CLOSED / PASS**.
- Active implementation PR: **#65** — `feat: add Phase 5 clustering and redundancy diagnostics`.
- PR #65 base: `main@db3e692e3e4ce1962d6953988464947b35d5ef82`.
- PR #65 implementation head before this documentation convergence batch: `0dd3c12b3097975bdcd4d36aeab5504987efbe29`.
- PR #65 state: **OPEN / DRAFT / MERGEABLE, but NOT MERGE-APPROVED**.
- Current support batch branch: `docs/phase5-convergence-plan`, created from the exact PR #65 head above.
- Current active Batch: **P5-DOC — Documentation & Methodology Convergence**.

## Current verification evidence on PR #65 head `0dd3c12b...`

- Main CI run `31344110155`: PASS.
  - Python pytest: **244 passed**.
  - Worker/Node: **47 passed**.
  - score tests: **12 passed**.
  - Playwright: **41 passed**.
  - compile, Ruff, dependency consistency, Vercel config, D1 local migrations, Cloudflare dry-run: PASS.
- Portfolio web CI run `31344110161`: PASS.
- Release Backup Gates run `31344110147`: PASS.
- Vercel required status: **FAIL — deployment rate limited / retry in 24 hours**; current evidence indicates quota/rate limiting, not a proven application build failure.
- Independent final PR review submissions: **none yet**.

## Merge decision

**NO-GO** until the Phase 5 methodology/documentation blockers below are resolved, final exact-head CI is green, Vercel required status is green, persistent handoff is current, and independent final review is recorded.

---

# 2. Stable State

Last Known Good production state is Phase 4 closeout on protected `main`:

- Phase 4 implementation PR #63 merge: `e59c1402011c7e8c940f806e79c9ce4b0da3f47f`.
- Phase 4 closeout PR #64 merge / current main: `db3e692e3e4ce1962d6953988464947b35d5ef82`.
- Phase 4 pre backup: `backup-pre-pr63-17f0dd88aeae`.
- Phase 4 post backup: `backup-post-pr63-e59c1402011c`.
- Phase 4 post-main CI / Portfolio web CI / Vercel / Cloudflare deploy-smoke: PASS as recorded in the historical phase record below.

Recovery principle: if Phase 5 causes a production regression after merge, restore the last known good Phase 4 production candidate first, then perform RCA and re-deploy a verified fix.

---

# 3. Architecture Notes

## Canonical boundaries

- `apps/api/app/data/` — TWD market-data, FX, return-component and valuation authority.
- `apps/api/app/portfolio/` — Portfolio v3 ledger and path-dependent analytics authority.
- `apps/api/app/research/` — reproducible research datasets and shared research-data adapters; **not a second market-price downloader**.
- `apps/api/app/quant/` — pure quantitative primitives; no API/UI/selection/sizing side effects.
- `apps/api/app/refinery/` — read-only Refinery composition and evidence policy; no Portfolio ledger absorption and no unvalidated selection policy.
- `api/refinery_v1.py` — dedicated `/api/v1/refinery/*` FastAPI entrypoint.
- `api/portfolio_v3.py` — Portfolio v3 FastAPI entrypoint.
- `api/exhaustive_optimizer.py` — full-period historical research/search, not an OOS validation engine.
- `apps/portfolio-web/` — separate Portfolio and Refinery workspace state/API boundaries.

## Research architecture

```text
TWDHistoryService
  -> ResearchDatasetV1
      -> Risk Mathematics
      -> Refinery API
          -> Refinery UI
          -> Phase 5 clustering/redundancy evidence
              -> later marginal experiments
                  -> later walk-forward validity
                      -> only then selection/sizing claims
```

## Locked architecture decisions

1. TWD remains the Taiwanese-investor valuation/risk authority.
2. ResearchDataset preserves requested/resolved/failure membership and deterministic dataset identity.
3. Formal analysis never silently removes failed candidates.
4. Browser code renders evidence; it does not become a second quant authority.
5. Portfolio ledger, Refinery diagnostics, Exhaustive historical search and future OOS validation remain separate semantic domains.
6. Full-period historical winners are not forward-performance evidence.
7. No point-in-time claim before time-valid Universe/fundamental provenance exists.

---

# 4. Master Plan

| Phase | Name | Status |
| --- | --- | --- |
| -1 | Governance & Architecture Hardening | CLOSED / PASS |
| 0 | Quant Authority Freeze | CLOSED / PASS |
| 1 | ResearchDatasetV1 | CLOSED / PASS |
| 2 | Risk Mathematics Core | CLOSED / PASS |
| 3 | Read-only Refinery API | CLOSED / PASS |
| 4 | Refinery Diagnostic UI | CLOSED / PASS |
| **5** | **Clustering & Redundancy** | **IN PROGRESS / PR #65 / NO-GO** |
| 6 | Marginal Experiments | PLANNED / BLOCKED BY PHASE 5 |
| 7 | Research Validity / Walk-Forward | PLANNED |
| 8 | Selection Policy | PLANNED |
| 9 | Sizing Engine | PLANNED |
| 10 | Validated Exhaustive Integration | PLANNED |
| 11 | Point-in-Time Universe / Alpha / Economic Factors | PLANNED |

Phase order is a working baseline. Do not reopen an earlier locked decision without new evidence, a material defect, an architecture conflict, an external platform change, or clearly superior benefit relative to migration risk.

---

# 5. Current Phase / Batch — Phase 5

## Phase 5 objective

Add deterministic, traceable clustering and multi-evidence redundancy diagnosis on top of ResearchDataset/Risk Mathematics/Refinery **without** crossing into marginal experiments, selection, sizing, Exhaustive candidate selection, or OOS recommendation claims.

## Implemented on PR #65 as of `0dd3c12b...`

- Correlation-distance hierarchical clustering.
- Average linkage primary / complete linkage sensitivity.
- 52/104/156-week stability windows.
- Deterministic 200-replicate, 4-week circular block bootstrap.
- HIGH / MEDIUM / LOW / UNCERTAIN historical redundancy verdicts.
- Factor-implied systematic relationship diagnostics using Kenneth French monthly U.S. factors + momentum.
- Explicit unavailable theme evidence when no traceable source exists.
- Additive Refinery API response fields.
- Read-only Phase 5 UI panels and large-pair/mobile rendering guards.
- Pure quant, API, source-contract and browser tests.

## Current Batch: P5-DOC — Documentation & Methodology Convergence

### Single goal

Make all Phase 5 handoff/contract/index documents reflect the real implementation state and convert review findings into explicit, actionable merge gates.

### In scope

- README / documentation hierarchy.
- `to_do_update_list.md` live state and historical continuity.
- research-document index.
- Refinery API/UI cross-phase documentation.
- Phase 5 methodology review amendments and evidence references.
- explicit NOW/NEXT/BACKLOG/REJECT classification.

### Out of scope

- Python/TypeScript production logic changes.
- changing redundancy thresholds in code.
- adding new data vendors / instrument master.
- Phase 6 marginal experiments.
- selection/sizing/OOS work.
- GitHub ruleset mutation.

### Allowed investigation

Only investigation required to verify documentation correctness, methodology applicability, current GitHub state, tests/checks and contract/code drift.

### Expansion trigger

Escalate out of P5-DOC only if investigation finds a Critical issue (security/data corruption/auth bypass) or a Phase 5 correctness problem that must be fixed in production code. Such items are recorded for the next dedicated Batch; implementation remains single-threaded.

---

# 6. Phase 5 Review Findings

## NOW — merge blockers

### P5-M1 — Bootstrap seed identity contract drift

**Symptom:** `REFINERY_CLUSTERING_V1.md` says seed material includes candidate `dataset_hash`.

**Implementation evidence:** `Phase5RefineryService` computes a canonical fingerprint from sorted structural weekly returns and temporarily supplies that fingerprint as the dataset hash used by bootstrap seeding.

**Why it matters:** request-order permutation should not change labelled clustering evidence; using a full ResearchDataset identity that includes request-order metadata can conflict with this requirement.

**Decision state:** implementation direction appears preferable for clustering determinism, but documentation and contract identity are inconsistent.

**Required permanent fix:** explicitly adopt one seed identity, update code + contract + tests together, and bump clustering contract version if externally observable methodology semantics change.

**Status:** BLOCKER / NOW.

### P5-M2 — Monthly factor partial-period alignment is underspecified

Current asset monthly returns are compounded with calendar-month resampling. If a requested research interval starts or ends mid-month, the asset observation can represent only a partial month while the Kenneth French monthly factor row represents the complete calendar month.

**Required permanent fix:** define complete-month eligibility; incomplete first/last asset months must not be regressed against full-month factor observations. Add mid-month start/end tests and expose the effective factor sample.

**Status:** BLOCKER / NOW.

### P5-M3 — Factor computability and factor applicability are conflated

Current V1 eligibility uses USD quote currency + native returns + minimum observations. Official U.S. Fama/French factors are constructed from U.S. equity universes; USD denomination alone does not establish that a factor relationship is an economically appropriate redundancy corroborator for every USD-denominated instrument.

**Required permanent fix:** distinguish:

- `factor_computable` — data can be regressed;
- `factor_scope/applicability` — evidence is approved for interpretation/corroboration.

Until a traceable instrument-scope rule exists, factor output may remain a labelled diagnostic but must not silently become a decisive redundancy corroborator solely because quote currency is USD.

**Status:** BLOCKER / NOW.

### P5-M4 — Factor beta / covariance common-sample semantics

Per-asset regressions can have different valid month sets while systematic covariance uses a factor covariance matrix over a broader factor frame.

**Required permanent fix:** freeze a common-sample policy (preferred for V1) or explicitly version pairwise/common-window semantics; tests must prove the factor-implied matrix uses the same intended observation universe.

**Status:** BLOCKER / NOW.

### P5-V1 — Vercel required check not green

Current required Vercel status on `0dd3c12b...` is failure due deployment rate limit. Do not remove the required check as a workaround. Final merge head must receive an actual green Vercel required status.

**Status:** BLOCKER / NOW.

### P5-R1 — Independent final review not yet recorded

PR #65 currently has no submitted review. Final review must target the exact final head after methodology/code/doc convergence.

**Status:** BLOCKER / NOW.

---

# 7. Phase 5 Batch Plan

## P5-DOC — Documentation & Methodology Convergence

**Status: ACTIVE**

Deliverables:

- repair stale Phase 4/Phase 5 handoff state;
- establish documentation precedence/freshness policy;
- add research-doc index;
- reconcile Refinery API schema documentation with current additive Phase 5 schema;
- document Phase 5 UI extension without rewriting the Phase 4 persistence contract;
- mark clustering methodology as under final review and enumerate required amendments;
- preserve historical decisions and exact resume point.

Verification:

- docs-only diff review;
- internal link/path review;
- no runtime files changed;
- parent PR remains functional because this Batch changes no code.

Rollback: drop/revert the documentation commit; parent PR head remains recoverable at `0dd3c12b...`.

## P5-CORR — Methodology Correctness Convergence

**Status: NEXT**

Single goal: resolve P5-M1..M4 with minimal production-code changes.

Required sequence:

1. freeze amended methodology decision;
2. update clustering/factor contract version where required;
3. implement canonical seed identity;
4. implement complete-month factor alignment;
5. implement factor applicability/corroboration policy;
6. implement common-sample factor relationship policy;
7. add targeted unit/invariant/regression tests;
8. update API/UI types only if the versioned evidence schema changes;
9. update this file before commit.

## P5-SEC — Dependency vulnerability triage

**Status: NEXT / CONDITIONAL**

Latest CI `npm ci` reported 3 vulnerabilities (2 moderate, 1 high). This is not yet evidence of a production-reachable vulnerability.

Process:

1. obtain `npm audit --json` evidence;
2. identify direct/transitive and production/dev scope;
3. determine reachability/exploitability;
4. if production-reachable high severity -> promote to Critical and fix before Phase 5 merge;
5. otherwise document and schedule the minimal safe dependency remediation.

Do not run `npm audit fix --force` without impact analysis.

## P5-VAL — Final validation and independent review

**Status: BLOCKED BY P5-CORR**

- compile / Ruff / Python tests;
- Worker/Node tests;
- score tests;
- Portfolio web type/build/source-contract tests;
- Playwright full regression;
- D1 local migrations / Cloudflare dry-run as required by full CI;
- Vercel required check green;
- Release Backup Gate green;
- independent exact-head review;
- all BLOCKER review findings resolved or explicitly rejected with evidence.

## P5-MERGE — Expected-head squash merge

**Status: BLOCKED**

Only after P5-VAL PASS. No bypass, force push or direct main commit.

## P5-CLOSE — Post-main verification and closeout

**Status: BLOCKED**

Record:

- merge SHA;
- post backup/release checkpoint;
- main CI / Portfolio web CI;
- Vercel / Cloudflare deployment and smoke where runtime changed;
- known limitations;
- Phase 5 CLOSED / PASS;
- exact Phase 6 resume point.

---

# 8. NEXT / BACKLOG / REJECT

## NEXT

1. P5-CORR methodology correctness convergence.
2. P5-SEC vulnerability triage.
3. P5-VAL final exact-head validation/review.
4. Separate governance hardening Batch after Phase 5 implementation is stable.

## BACKLOG

- full instrument/security master for explicit asset taxonomy and region/model applicability;
- deterministic traceable economic-theme provider/taxonomy;
- globally distributed Refinery rate limiting;
- Vercel preview-deployment quota optimization;
- immutable-SHA pinning review for GitHub Actions where appropriate;
- richer factor-region models only after explicit scope/provenance governance.

## REJECT for current Phase

- 0–100 magic redundancy score;
- automatic KEEP / TRIM / REPLACE labels;
- Phase 6 Remove-One/Add-One/Replace-One inside PR #65;
- HRP/ERC/minimum-variance sizing;
- Exhaustive candidate selection;
- OOS/walk-forward claims;
- current fundamentals injected into historical tests;
- untraceable LLM theme labels;
- removing Vercel required checks to bypass quota failure.

---

# 9. Decision Log

## D-001 — TWD canonical investor-risk authority

**Status:** LOCKED.

Native/FX components remain auditable, but cross-market Taiwanese-investor valuation and risk use TWD semantics.

Reopen only for a documented requirement change or evidence that current TWD contract is mathematically/data incorrect.

## D-002 — Requested membership is never silently reduced

**Status:** LOCKED.

Partial evidence may be displayed; formal analysis must fail closed when requested candidate membership is incomplete.

## D-003 — ResearchDataset is a reproducibility boundary, not a strategy

**Status:** LOCKED.

No hidden selection/sizing policy belongs in ResearchDataset.

## D-004 — Historical search is not OOS evidence

**Status:** LOCKED.

Full-period Scanner/Exhaustive/Refinery output remains descriptive until Phase 7 walk-forward validation.

## D-005 — Phase 5 verdict semantics remain descriptive classes

**Status:** LOCKED FOR PHASE 5.

Use HIGH / MEDIUM / LOW / UNCERTAIN evidence; no action/replacement semantics.

## D-006 — Average linkage primary, complete linkage sensitivity

**Status:** WORKING BASELINE.

SciPy accepts average/complete linkage on a condensed distance matrix; Ward is intentionally not the V1 default for the precomputed correlation-distance path.

## D-007 — Bootstrap seed identity amendment

**Original decision:** seed includes full candidate `dataset_hash`.

**New evidence:** permutation-invariant clustering requires an order-insensitive canonical structural identity; current implementation already derives a structural weekly fingerprint.

**Proposed change:** make canonical structural-weekly fingerprint the explicit seed-data identity and bump methodology version with tests.

**Status:** REOPENED / P5-M1 BLOCKER.

## D-008 — U.S. factor evidence scope

**Original decision:** USD quote currency + native history + 36 months makes factor evidence usable.

**New evidence:** official U.S. Fama/French factors are U.S.-equity factor portfolios; USD denomination alone is a data property, not an applicability taxonomy.

**Proposed change:** separate computability from applicability/corroboration.

**Status:** REOPENED / P5-M3 BLOCKER.

---

# 10. Root Cause Log

## RC-001 — Phase 3 partial-evidence indexing failure

- Symptom: incomplete candidate test raised pandas `KeyError`.
- Failure point: diagnostic sample accounting indexed requested symbols against a resolved-only frame.
- Root cause: evidence accounting mixed requested membership with resolved data columns.
- Fix: use `resolved_symbols` for descriptive evidence while keeping requested membership authoritative and `analysis=null`.
- Prevention: explicit membership/fail-closed tests.
- Status: CLOSED.

## RC-002 — Phase 4 stale production bundle

- Symptom: TypeScript source and committed production assets diverged.
- Root cause: source/build artifact synchronization was not an enforced deterministic gate.
- Fix: locked rebuild + committed-asset parity verification.
- Status: CLOSED.

## RC-003 — Phase 4 CSS leakage / orphan stylesheet

- Failure: Refinery stylesheet was initially outside the Vite graph; when enabled, generic selectors could leak into Portfolio UI.
- Root cause: missing import-path and CSS namespace invariants.
- Fix: import after Portfolio styles; scope under `.refinery-workspace`; source-contract regression guard.
- Status: CLOSED.

## RC-004 — Phase 5 handoff document drift

- Symptom: PR #65 had 53 commits while `to_do_update_list.md` still said Phase 5 `NEXT / NOT STARTED` and Phase 4 closeout pending.
- Root cause: Phase 5 implementation advanced without updating the persistent handoff file required by project governance.
- Impact: a new Agent could restart Phase 5, reopen Phase 4 or make an incorrect merge decision.
- Fix: P5-DOC resets live status from current GitHub evidence and establishes a staleness rule.
- Prevention: implementation PR must update this file before each phase-ending merge; final review checks remote-vs-document state.
- Status: FIXED BY CURRENT DOC BATCH, pending merge into parent Phase 5 branch.

---

# 11. Known Issues

1. **Phase 5 P5-M1..M4 methodology blockers** — NOW.
2. **Vercel deployment rate limit on current PR head** — NOW; external quota state, not permission to bypass required status.
3. **No independent PR #65 final review yet** — NOW.
4. **GitHub ruleset governance drift** — `main-protection` is active and requires PR + squash + `validate` + `Vercel`, but currently has `strict_required_status_checks_policy=false`, zero required approvals and no required review-thread resolution. Handle in a separate governance Batch; do not mix into Phase 5 quant correctness unless it directly blocks merge safety.
5. **npm audit signal** — CI reported vulnerabilities; reachability not yet established.

---

# 12. Technical Debt

- Refinery backend rate limiting is best-effort/in-process rather than global.
- Instrument taxonomy is insufficient to make broad factor-model applicability claims automatically.
- Theme evidence remains intentionally unavailable without traceable taxonomy/provider.
- Point-in-time Universe/fundamental history is not yet implemented.
- Vercel preview deployment frequency can exhaust free-plan quota during large multi-commit PRs.
- Some historical docs are phase-frozen and require additive extension notes rather than rewriting old semantics.

---

# 13. Deferred / Rejected Candidates

### Deferred

- regional/developed factor models;
- instrument master;
- theme provider;
- global rate limiter;
- advanced deployment quota optimization;
- Phase 6+ research functionality.

### Rejected for Phase 5

- stock action labels;
- unversioned magic score;
- hidden equal weighting;
- silent fallback to different factor/calendar/currency/universe;
- recommendation claims without Phase 7+ evidence.

---

# 14. Risks

| Risk | Severity | Current control |
| --- | --- | --- |
| Methodology/doc mismatch changes reproducibility | High | P5-M1 contract convergence + versioning |
| Partial-month factor alignment biases regression | High | P5-M2 complete-month policy/tests |
| Factor evidence over-interpreted outside scope | High | P5-M3 applicability separation |
| Different regression samples feed one factor covariance interpretation | High | P5-M4 common-sample policy |
| Vercel quota blocks required check | Medium | wait/retry on final head; no gate removal |
| Governance ruleset weaker than documented workflow | Medium | manual discipline now; separate hardening Batch |
| Dependency alert is production-reachable | Unknown/High if confirmed | evidence-based audit triage |
| Survivorship/look-ahead overclaim | High | explicit descriptive/OOS boundaries; Phase 7/11 gates |

---

# 15. Cross-phase Validation Matrix

| Validation | Requirement |
| --- | --- |
| Existing regression suite | PASS |
| Python compile/lint/tests | Required when Python/quant/API touched |
| Worker/Node tests | Required when routing/worker/optimizer touched; full CI currently runs them |
| Portfolio web type/build/source-contract | Required when Portfolio/Refinery web touched |
| Browser E2E | Required for user-flow changes and final regression |
| Vercel required check | PASS before merge |
| D1 migration validation | Required when D1 touched / by full CI |
| Cloudflare dry-run | Required when Worker/static deploy touched / by full CI |
| Production deploy/smoke | Required when deployed runtime/edge behavior changes |
| Quant reference/parity fixtures | Required where applicable |
| Mathematical invariants/metamorphic tests | Required from Phase 2 onward |
| API security/resource/fail-closed tests | Required from Phase 3 onward |
| OOS/walk-forward evidence | Required before recommendation claims |
| Release backup gate | Required for runtime/quant-methodology PRs |
| Independent exact-head review | Required before merge |
| `to_do_update_list.md` current-state check | Required before merge and closeout |

---

# 16. Historical Change Log / Phase Records

## Phase -1 — Governance & Architecture Hardening

**CLOSED / PASS**

- PR #52 merge `9135bdd33a46afee4f4a12b9030ca4504114924f`.
- Pre `backup-pre-pr52-a0c640783dc9`; post `backup-post-pr52-9135bdd33a46`.
- Architecture/runtime inventory aligned; obsolete backup workflows retired; main protection activated afterward.

## Continuity governance

**CLOSED / PASS**

- PR #53 merge `bc8ce721a82938c32ed8b9af7c91fba25a161f8a`.
- Added root persistent roadmap/handoff discipline.

## Phase 0 — Quant Authority Freeze

**CLOSED / PASS**

- Implementation PR #54 merge `68cbd58d570ce7d806c2a73903b5bdb506c9bae1`.
- Closeout PR #55 merge `d173f1d15a671e7d2f3c096a56e7ee3ef9f0a183`.
- Metric/return/risk authorities frozen; known CAGR year-length difference remains explicit/versioned.

## AI engineering playbook

- PR #56 merge `863039af803671a8caf1d35074d038136ca2332a`.
- `AI_PROJECT_PLAYBOOK.md` adopted as repository-wide engineering governance.

## Phase 1 — ResearchDatasetV1

**CLOSED / PASS**

- PR #57 merge `7cf3fdcfa248d47a036419213da0acce594ada7c`.
- Closeout #58 merge `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`.
- Contract `research-dataset-twd-2026-08-09.1`.
- Requested/resolved/failure evidence, window isolation, daily/weekly TWD matrices, coverage/audits/fingerprints/hash implemented.
- Exhaustive preparation parity passed without migrating Exhaustive.

## Phase 2 — Risk Mathematics Core

**CLOSED / PASS**

- PR #59 merge `724075ddbb0383f7889e4b622a95a57769d5558c`.
- Closeout #60 merge `4cea3b18fdce7db5e464196172f59930abf6b7d9`.
- Contract `risk-math-twd-2026-08-09.1`.
- Sample/Ledoit-Wolf/EWMA covariance, diagnostics, risk decomposition, effective dimensions and guarded correlation views implemented.
- Ledoit-Wolf fixture independently anchored; an initially incorrect golden fixture was corrected rather than changing valid math to fit it.

## Phase 3 — Read-only Refinery API

**CLOSED / PASS**

- PR #61 final head `4899199a50d01189904ef0842c5d5247afc4d09d`.
- Merge `6e18726dcc1383e0b839e4bd0bded46e720e2707`.
- Closeout #62 merge `17f0dd88aeaeff61f84ac6598c7b6258135d4ca4`.
- Pre `backup-pre-pr61-4cea3b18fdce`; post `backup-post-pr61-6e18726dcc13`.
- Final CI/Portfolio web/Vercel/backup/review/post-main/deployment evidence PASS.
- Key RCA: incomplete-candidate evidence indexing fixed without silently shrinking membership.

## Phase 4 — Refinery Diagnostic UI

**CLOSED / PASS**

- PR #63 final head `4439e4e721f8c93cc77161affbd5f24554de516f`.
- Merge `e59c1402011c7e8c940f806e79c9ce4b0da3f47f`.
- Closeout #64 / current main `db3e692e3e4ce1962d6953988464947b35d5ef82`.
- Pre `backup-pre-pr63-17f0dd88aeae`; post `backup-post-pr63-e59c1402011c`.
- Final PR CI: Python 216/216, Worker 47/47, score 12/12, Playwright 39/39; Portfolio web CI/Vercel/backup/review/post-main/deployment PASS.
- RCAs included stale generated assets, stylesheet graph omission, CSS leakage, ambiguous E2E labels and focused-gate coverage gaps.

## Phase 5 — Clustering & Redundancy

**IN PROGRESS**

- PR #65 base `db3e692e...`, current implementation head before docs convergence `0dd3c12b...`.
- 53 commits / 31 changed files at the start of P5-DOC.
- Latest main CI / Portfolio web CI / Release Backup Gates PASS.
- Vercel required status rate-limited.
- Methodology correctness review reopened P5-M1..M4.
- Documentation drift found and classified RC-004.

---

# 17. Exact Next Actions / Resume Point

A new Agent must not restart Phase 5 from the old planning checklist. Resume exactly here:

1. Read `AI_PROJECT_PLAYBOOK.md`, `README.md`, this file and `docs/PROJECT_DOCUMENTATION_POLICY.md`.
2. Query current `main`, PR #65 exact head, checks, reviews and ruleset; compare with this snapshot.
3. Confirm P5-DOC has been merged into the Phase 5 branch or otherwise preserve its decisions.
4. Execute **P5-CORR only**: resolve P5-M1 seed identity, P5-M2 complete-month factor alignment, P5-M3 factor applicability/corroboration, P5-M4 common-sample semantics.
5. Update `REFINERY_CLUSTERING_V1.md` contract identity and code constants together if methodology semantics change.
6. Add targeted tests before broad regression.
7. Triage npm vulnerabilities without shotgun/force upgrades.
8. Run P5-VAL full exact-head verification.
9. Obtain independent final review on the exact reviewed head.
10. Require actual green `validate` + `Vercel` and backup gate; no bypass.
11. Squash merge with expected head SHA.
12. Post-main verification, production deploy/smoke where applicable, backup/release checkpoint, then a doc-only Phase 5 closeout.
13. Only after Phase 5 is `CLOSED / PASS` begin Phase 6 — Marginal Experiments.

---

# 18. Status Vocabulary

Use only: `NOT STARTED`, `IN PROGRESS`, `BLOCKED`, `VALIDATING`, `PASS`, `FAIL`, `CLOSED`, `DEFERRED` plus explicit `NO-GO` for merge readiness.

Do not mark a phase `CLOSED` until implementation, required validation, review, merge, post-main evidence, rollback/recovery record and closeout are complete.
