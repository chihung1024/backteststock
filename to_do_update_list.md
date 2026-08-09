# BacktestStock Development Master Plan

> Persistent execution/handoff index for `chihung1024/backteststock` and the Portfolio Refinery program. A phase/batch is not complete until this file records its status, evidence, limitations, and exact resume point.

## 1. Current baseline

- Protected production branch: `main`
- Phase 3 implementation PR: `#61` — `feat: add read-only Portfolio Refinery API`
- Phase 3 final implementation head: `4899199a50d01189904ef0842c5d5247afc4d09d`
- Phase 3 implementation merge: `6e18726dcc1383e0b839e4bd0bded46e720e2707`
- Phase 3 pre backup: `backup-pre-pr61-4cea3b18fdce`
- Phase 3 post backup: `backup-post-pr61-6e18726dcc13`
- Current phase state: **Phase 3 — PASS; becomes CLOSED when this doc-only closeout merges**
- Next implementation phase: **Phase 4 — Refinery Diagnostic UI**
- Governance ruleset: `main-protection`
  - enforcement active; default branch target; bypass empty
  - deletion and force/non-fast-forward pushes blocked
  - PR required; squash only
  - required checks: `validate` (GitHub Actions) + `Vercel`

## 2. Mandatory execution discipline

1. Read `AI_PROJECT_PLAYBOOK.md` first; it is the repository-wide AI engineering governance document.
2. Execute phases in order. Do not start a later phase before the current exit gate passes.
3. Avoid unrelated refactors/feature expansion; new discoveries go NOW/NEXT/BACKLOG/REJECT per the playbook.
4. Implementation and quantitative-methodology work uses a non-`main` branch and PR.
5. Never force-push or use direct implementation commits on `main`.
6. Use squash merge and expected-head verification where supported.
7. Runtime/quant-methodology PRs use generic `release-backup`.
8. Never silently delete tickers, shorten requested dates, substitute calendars/currencies, backfill future data, or turn unavailable metrics into valid zeros.
9. Keep historical search/exploration separate from OOS validation claims.
10. Preserve explicit methodology/contract versions when externally observable semantics change.
11. Update this file in each implementation PR with all information known before merge.
12. A phase-ending implementation PR is followed by a **doc-only closeout PR** recording final merge SHA, post-backup, final checks/review, limitations, phase status and next resume point.
13. The closeout PR does not recursively require another closeout; the next AI queries current `main` before work.
14. If validation fails, preserve last valid production behavior and fix only inside the current phase.
15. A golden fixture is not an authority merely because it is committed; where practical, its provenance must be independently anchored to a reference implementation or separately derived invariant.
16. Partial research evidence may be reported, but formal analysis must never silently redefine requested membership by dropping failed candidates.

## 3. Architecture boundaries

- `apps/api/app/data/` — shared TWD market-data, FX, return-component and valuation authority.
- `apps/api/app/portfolio/` — Portfolio v3 ledger/path-dependent analysis authority.
- `apps/api/app/research/` — additive research-domain data/services beginning with `ResearchDatasetV1`; it must not become a second downloader.
- `apps/api/app/quant/` — pure validated quantitative primitives; no API/UI/selection/sizing side effects.
- `apps/api/app/refinery/` — read-only Refinery request/service boundary beginning in Phase 3; may compose ResearchDataset + Risk Mathematics but must not absorb Portfolio v3 ledger logic or later selection/sizing policy.
- `api/refinery_v1.py` — dedicated FastAPI entrypoint for `/api/v1/refinery/*`.
- `api/portfolio_v3.py` — production FastAPI Portfolio v3 entrypoint.
- `api/index_v2.py`, `api/scan_v2.py`, `api/screener.py` — current compatibility/production entrypoints as documented.
- `api/exhaustive_optimizer.py` — full-period historical research/search snapshot path, not an OOS validation engine.
- `apps/portfolio-web/` — Portfolio v3 production web source; Phase 4 may add a separate Refinery workspace but must preserve Portfolio workspace behavior.
- New Refinery logic must not be added to legacy `api/index.py` or `api/optimizer.py`.
- Portfolio v3 retains its strict production portfolio boundary; Refinery remains a separate research/diagnostic domain.

Primary references:

- `AI_PROJECT_PLAYBOOK.md`
- `docs/PHASE_MINUS1_GOVERNANCE.md`
- `docs/adr/0001-runtime-and-quant-authority.md`
- `docs/UNIFIED_TWD_CONTRACT.md`
- `docs/METRICS_REPRODUCIBILITY.md`
- `docs/EXHAUSTIVE_OPTIMIZER_V3.md`
- `docs/quant/METRIC_AUTHORITY.md`
- `docs/quant/RETURN_SEMANTICS.md`
- `docs/quant/RISK_MODEL_POLICY.md`
- `docs/quant/RISK_MATHEMATICS_V1.md`
- `docs/research/RESEARCH_DATASET_V1.md`
- `docs/research/REFINERY_API_V1.md`

---

# 4. Roadmap

## Phase -1 — Governance & Architecture Hardening

**Status: CLOSED / PASS**

- PR `#52`, merge `9135bdd33a46afee4f4a12b9030ca4504114924f`
- CI/Vercel PASS
- Pre: `backup-pre-pr52-a0c640783dc9`
- Post: `backup-post-pr52-9135bdd33a46`
- Architecture docs/runtime inventory aligned; obsolete PR19/PR38 backup workflows retired; `main-protection` activated afterward.

## Continuity governance — persistent roadmap

**Status: CLOSED / PASS**

- PR `#53`, merge `bc8ce721a82938c32ed8b9af7c91fba25a161f8a`
- CI/Vercel PASS
- Pre: `backup-pre-pr53-9135bdd33a46`
- Post: `backup-post-pr53-bc8ce721a829`
- Added root `to_do_update_list.md` and implementation/closeout handoff discipline.

## Phase 0 — Quant Authority Freeze

**Status: CLOSED / PASS**

- PR `#54`, merge `68cbd58d570ce7d806c2a73903b5bdb506c9bae1`; pre/post backups and final CI/Vercel/review PASS.
- Closeout PR `#55`, merge `d173f1d15a671e7d2f3c096a56e7ee3ef9f0a183`.
- Metric/return/risk authorities frozen; existing 365.25 vs 365.2425 CAGR year-length difference remains explicit/versioned rather than silently normalized.

---

## Phase 1 — ResearchDataset

**Status: CLOSED / PASS**

- Implementation PR `#57`, merge `7cf3fdcfa248d47a036419213da0acce594ada7c`.
- Closeout PR `#58`, merge `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`.
- Contract/version: `ResearchDatasetV1` / `research-dataset-twd-2026-08-09.1`.
- One TWD market-data authority, explicit requested/resolved/failure evidence, window isolation, union calendar, daily/weekly TWD matrices, coverage/audits/fingerprints and deterministic hash implemented.
- Exhaustive preparation parity passed without migrating production Exhaustive.
- Pre `backup-pre-pr57-863039af8036`; post `backup-post-pr57-7cf3fdcfa248`.

Known limitations retained:

- Production consumers are not generally migrated to ResearchDataset.
- Daily alignment intentionally reuses `align_twd_price_frame()` for semantic parity.
- No point-in-time Universe/fundamentals are introduced.

---

## Phase 2 — Risk Mathematics Core

**Status: CLOSED / PASS**

- Implementation PR `#59`, final head `9cd00609bcbdde210bdc024fa224016ca3dda6d3`, merge `724075ddbb0383f7889e4b622a95a57769d5558c`.
- Closeout PR `#60`, merge `4cea3b18fdce7db5e464196172f59930abf6b7d9`.
- Contract/version: `risk-math-twd-2026-08-09.1`.
- Sample/Ledoit-Wolf/EWMA covariance, diagnostics/dispersion, portfolio variance/vol/MRC/signed RC/DR, effective counts/ranks and guarded tactical/medium/structural/downside/stress correlation implemented.
- NumPy Ledoit-Wolf independently anchored to scikit-learn; scikit-learn remains dev/test-only.
- Initial bad golden fixture was independently re-derived and corrected rather than modifying valid mathematics to fit wrong expectations.
- Pre `backup-pre-pr59-666c561c0abf`; post `backup-post-pr59-724075ddbb03`.

Known limitations retained:

- Minimum-observation and EWMA-decay policies remain consumer-level choices.
- Effective rank/participation ratio are structural diagnostics, not proof of exact independent economic bets.
- No clustering, selection, sizing or OOS claim exists in Phase 2.

---

## Phase 3 — Read-only Refinery API

**Status: PASS; CLOSED when this closeout PR merges**

### Objective
Expose Phase 1 ResearchDataset + Phase 2 Risk Mathematics through a separate deterministic read-only research API without changing Portfolio v3 ledger semantics or exposing clustering/selection/sizing/recommendation behavior.

### Completed implementation — PR #61

- [x] Defined `docs/research/REFINERY_API_V1.md` before implementation.
- [x] Frozen API contract/schema: `refinery-v1` / `refinery-v1-2026-08-09.1`.
- [x] Added separate `apps/api/app/refinery/` request/service boundary.
- [x] Added dedicated FastAPI entrypoint `api/refinery_v1.py` and dedicated Vercel `/api/v1/refinery/(.*)` route.
- [x] Added fixed Worker allowlist for exactly `POST preflight` and `POST analyze`.
- [x] Candidate contract: 2–100 unique normalized symbols, explicit dates, optional benchmark, optional explicit candidate weights, explicit EWMA decay/stress quantile.
- [x] Reuses existing `normalize_symbol()` including Taiwan numeric shorthand; no second symbol-normalization rule.
- [x] No benchmark default and no equal-weight default are fabricated.
- [x] Explicit weights must cover every candidate exactly once and total 100% within ±0.05 percentage point; accepted tolerance is proportionally normalized to exact unit sum while raw weights/raw total/normalization policy remain visible.
- [x] Performs one authoritative `TWDHistoryService.histories_partial()` fetch for candidates + optional benchmark.
- [x] Builds separate candidate and benchmark ResearchDataset views from that one audited batch so benchmark choice cannot alter candidate covariance/correlation sample.
- [x] Partial preflight evidence may report resolved-symbol sample counts, but any unresolved candidate forces status `incomplete` and `analysis=null`; no reduced-universe formal analysis.
- [x] Benchmark failure preserves candidate structural analysis and disables only conditional diagnostics with explicit failure/unavailable evidence.
- [x] Candidate-complete but insufficient history returns `insufficient_data`.
- [x] Ledoit-Wolf annualized covariance is primary formal risk estimator; sample/EWMA remain diagnostics/sensitivity.
- [x] Exposes covariance diagnostics/dispersion, structural effective dimensions, optional explicit-weight portfolio risk and guarded tactical/medium/structural/downside/stress correlations.
- [x] Public API omits raw price arrays/full ResearchDataset exports.
- [x] Canonical deterministic JSON, 4 MiB response bound, 512 KiB request bound, 240s edge timeout, no-store/security headers and best-effort backend rate limits implemented.
- [x] Worker strips authorization/cookies/backend-identifying headers and bypasses generic edge cache for Refinery.
- [x] Upstream RuntimeError detail is logged server-side and sanitized to a stable client `upstream_failure` response.
- [x] Vercel/Worker/CI deployment contracts and tests updated without changing Portfolio UI, Exhaustive or later-phase logic.

### Validation defect found and root-caused

Initial PR #61 CI run `31301415964` reached Python tests after dependencies/pip consistency/compile/Ruff PASS. Result: **210 passed / 1 failed**.

Failure: `test_incomplete_candidate_blocks_formal_analysis_without_silent_deletion`.

Root cause:

- service correctly classified a candidate set with a failed symbol as `incomplete`;
- diagnostic complete-case evidence still indexed the full requested symbol list against a DataFrame containing only resolved symbols, causing a pandas `KeyError`;
- this was an evidence-accounting bug, not justification to delete the failed candidate.

Fix:

- evidence sample counts use `candidate_dataset.resolved_symbols`;
- requested/resolved/failure membership remains explicit;
- unresolved candidates still force `analysis=null`;
- zero-resolved-symbol evidence is handled safely;
- no silent smaller-portfolio calculation was introduced.

Additional same-scope hardening:

1. Accepted 100% ±0.05 percentage-point weight totals are proportionally normalized to exact unit sum for Phase 2 primitives, preserving relative weights and exposing the raw total/policy.
2. Upstream RuntimeError text is no longer exposed to clients.

### Final Phase 3 evidence

- Implementation PR: `#61`.
- Base SHA: `4cea3b18fdce7db5e464196172f59930abf6b7d9`.
- Final implementation head: `4899199a50d01189904ef0842c5d5247afc4d09d`.
- Squash merge: `6e18726dcc1383e0b839e4bd0bded46e720e2707`.
- Final changed-file scope: dedicated Refinery backend/edge/deployment wiring, tests/docs/CI and roadmap only; no Portfolio UI, clustering, selection, sizing or Exhaustive logic.
- Final PR-head `validate` run `31301902120`: PASS — dependency/pip check, compile, Ruff, all Python tests, JS syntax, Worker tests, score tests, Playwright E2E, Vercel config, D1 local migration and Cloudflare dry-run.
- Final Portfolio web CI run `31301902143`: PASS.
- Final PR-head Vercel required context: PASS.
- Final Release Backup Gate: PASS.
- Independent final diff review: PASS, recorded as COMMENT review `4890806477`.
- Merge-after-push `main` CI run `31302059179`: PASS.
- Production Vercel status for merge SHA: PASS.
- Production Cloudflare Worker deploy run `31302059197`: PASS, including D1 migrations, Worker/static deploy, Russell 2000 smoke and Portfolio v3 smoke.
- Pre backup: `backup-pre-pr61-4cea3b18fdce` -> `4cea3b18fdce7db5e464196172f59930abf6b7d9`.
- Post backup: `backup-post-pr61-6e18726dcc13` -> `6e18726dcc1383e0b839e4bd0bded46e720e2707`.

### Known limitations carried forward

1. Phase 3 is API-only; no user-facing Refinery UI exists yet.
2. Backend rate limiting is deliberately best-effort/in-process, not a globally distributed quota.
3. Correlation observation thresholds and EWMA decay are versioned consumer policies, not universal statistical truths.
4. API V1 returns structural/risk diagnosis only; it does not classify redundancy, recommend stocks, select holdings or size positions.
5. No Leave-One-Out/Add-One/Replace-One, clustering, factor/economic-theme overlay, Exhaustive integration or OOS validation exists yet.
6. The current UI remains Portfolio-focused; Phase 4 must use a separate Refinery workspace model/schema rather than overloading Portfolio v3 persisted state.

### Exit gate

- [x] API contract/version frozen/documented.
- [x] Separate runtime/edge route implemented.
- [x] Preflight/analyze deterministic/fail-closed semantics implemented/tested.
- [x] Candidate/benchmark sample isolation implemented/tested.
- [x] Request/response/rate/error/security guards implemented/tested.
- [x] Initial defect root-caused without silent candidate deletion.
- [x] Final PR-head `validate`, Portfolio web CI, Vercel and Release Backup Gates PASS.
- [x] Independent diff review PASS.
- [x] PR #61 exact-head squash merge.
- [x] Post-merge backup verified.
- [x] Merge-after-push `main` CI PASS.
- [x] Production Vercel and Cloudflare deployment/smoke PASS.
- [ ] This doc-only closeout must merge; then Phase 3 is `CLOSED / PASS`.

---

## Phase 4 — Refinery Diagnostic UI

**Status: NEXT / NOT STARTED — begin only after this Phase 3 closeout merges**

### Objective
Add a separate deterministic read-only Refinery workspace that consumes Phase 3 API diagnostics without changing Portfolio v3 behavior or introducing Phase 5+ clustering/recommendation semantics.

### First actions

- [ ] Query latest protected `main` after this closeout; do not assume `6e18726d...` remains HEAD because closeout adds a documentation commit.
- [ ] Confirm no unfinished Phase 3 implementation/closeout PR remains.
- [ ] Read `AI_PROJECT_PLAYBOOK.md`, this roadmap, `REFINERY_API_V1.md`, ResearchDataset/Risk Mathematics contracts and current Portfolio web source-contract/persistence docs/tests.
- [ ] Inventory `apps/portfolio-web/` routing, workspace model, persisted schema/versioning, API client/bridge, responsive layout, error/loading states and source-contract tests before UI changes.
- [ ] Define a separate `RefineryWorkspaceModel` + persisted schema/version before implementation; do not reuse Portfolio v3 ledger payload as a generic bag.

### Planned work

- [ ] Workspace switch: Portfolio backtest / holding refinement.
- [ ] Separate Refinery input/state persistence.
- [ ] Preflight data-quality/reproducibility status.
- [ ] Structure summary.
- [ ] Capital weight vs signed risk contribution.
- [ ] Effective holdings/risk dimensions and Diversification Ratio.
- [ ] Tactical/medium/structural/downside/stress correlation views.
- [ ] Data confidence/effective observations.
- [ ] Covariance stability/estimator-dispersion diagnostics.
- [ ] Large-matrix/rendering guard and responsive behavior.
- [ ] Explicit unavailable/incomplete/error states matching API semantics.

### Explicit non-goals

- No clustering/redundancy verdicts.
- No KEEP/TRIM/REPLACE or stock ranking.
- No Leave-One-Out/Add-One/Replace-One.
- No selection/sizing/optimization.
- No Exhaustive integration.
- No OOS recommendation claim.

Exit gate: deterministic read-only diagnosis UI; existing Portfolio behavior remains unchanged; full regression/deployment gates PASS; doc-only Phase 4 closeout merged.

---

## Phase 5 — Clustering & Redundancy

**Status: PLANNED**

- [ ] Correlation-distance hierarchical clustering.
- [ ] Average linkage default; complete-linkage sensitivity.
- [ ] Multi-window and bootstrap cluster stability.
- [ ] Asset-level factor diagnostics where valid.
- [ ] Prefer factor-implied covariance/correlation to simple beta-vector cosine for factor-overlap evidence.
- [ ] Treat U.S. Fama-French factors as secondary evidence outside U.S. equities.
- [ ] Economic-theme overlay remains traceable/read-only in this phase.
- [ ] Evidence stack: price, downside, stress, factor, theme, confidence.
- [ ] Verdicts: HIGH / MEDIUM / LOW / UNCERTAIN.
- [ ] No magic 0–100 redundancy score.

---

## Phase 6 — Marginal Experiments

**Status: PLANNED**

- [ ] Remove-One, Add-One, Replace-One.
- [ ] Every experiment states funding policy: pro-rata survivors / cash / cluster champion / selected replacement.
- [ ] Recompute volatility, CVaR diagnostics, DR, effective counts/ranks, risk/cluster concentration.
- [ ] Clear before/after decomposition.
- [ ] Historical diagnostic semantics only; no implied future alpha.

---

## Phase 7 — Research Validity / Walk-Forward

**Status: PLANNED**

- [ ] Trial registry for every model/policy configuration.
- [ ] Fixed-candidate-universe anchored walk-forward V1.
- [ ] Training-only refinement/selection; never-seen forward evaluation.
- [ ] Turnover/transaction-cost accounting and OOS original-vs-refined comparison.
- [ ] Track trial count/selection breadth.
- [ ] Probabilistic/Deflated Sharpe where appropriate; PBO/CSCV only if research grid warrants it.
- [ ] Explicit fixed-universe survivorship limitation.

Non-goal: no point-in-time Universe claim before Phase 11.

---

## Phase 8 — Selection Policy

**Status: PLANNED**

- [ ] Cluster tournament policy.
- [ ] Greedy selection with marginal utility recomputed after each addition.
- [ ] Pairwise swap search and replacement hurdle/hysteresis.
- [ ] Stop on diminishing marginal benefit, not hard-coded holding count.
- [ ] N-vs-efficiency curve and OOS selection-frequency/stability reporting.
- [ ] Only after validation expose KEEP / TRIM / REPLACE semantics.
- [ ] Historical price-derived alpha remains labelled historical proxy unless forward data are valid.

---

## Phase 9 — Sizing Engine

**Status: PLANNED**

Compare under the same OOS framework:

- [ ] Equal weight, inverse volatility, ERC, HRP benchmark, Ledoit-Wolf minimum variance, constrained risk budget.
- [ ] User-visible capital/risk/cluster constraints.
- [ ] Deterministic optimizer/multi-start policy and safe fallback.
- [ ] OOS CAGR, vol, Sharpe, Sortino, MDD, Calmar, CVaR, turnover, DR and effective-rank comparison.

No method, including HRP, is the default winner before evidence.

---

## Phase 10 — Validated Exhaustive Integration

**Status: PLANNED**

- [ ] Training only: ResearchDataset -> Refinery -> candidate reduction -> Exhaustive search.
- [ ] Freeze selected portfolio/policy before OOS evaluation.
- [ ] Never present full-period Refinery + Exhaustive winner as forward evidence.
- [ ] Track trial/combination counts and benchmark against simpler policies.
- [ ] Mechanically enforce training/OOS separation for preparation, tuning and evaluation.

---

## Phase 11 — Point-in-Time Universe / Alpha / Economic Factors

**Status: PLANNED**

- [ ] Point-in-time Universe membership/effective dates and historical delisting handling as data permit.
- [ ] Point-in-time fundamentals and valid/licensed analyst/revision data if available.
- [ ] Revenue/EPS/FCF/ROIC/balance-sheet/valuation dimensions.
- [ ] Traceable economic-factor taxonomy with source/effective date/confidence.
- [ ] Never inject current fundamentals into historical backtests.
- [ ] Re-run walk-forward with time-valid information.

Exit gate: provenance/effective dates support actual point-in-time claims.

---

# 5. Cross-phase validation matrix

| Validation | Requirement |
| --- | --- |
| Existing regression suite | Pass |
| Python compile/lint/tests | Pass when Python touched |
| Worker/Node tests | Pass when JS/routing/optimizer touched |
| Portfolio web type/build/source-contract tests | Pass when Portfolio web touched |
| Browser E2E | Pass for user-flow changes and full regression gate |
| Vercel required check | Pass |
| D1 migration validation | Pass when D1 touched / full CI requires it |
| Cloudflare dry-run | Pass when Worker/static deployment touched / full CI requires it |
| Production deployment/smoke | Pass when deployed runtime/edge behavior changes |
| Quant golden/parity fixtures | Required from Phase 0 onward where applicable |
| Mathematical invariants/metamorphic tests | Required from Phase 2 onward |
| API security/resource/fail-closed tests | Required from Phase 3 onward |
| OOS/walk-forward evidence | Required for recommendation claims from Phase 7 onward |
| Pre/post Release backup | Required for runtime/quant-methodology PRs |
| Independent diff review | Required before merge; COMMENT evidence is acceptable when GitHub forbids self-approval and branch protection does not require another approver |
| `to_do_update_list.md` update | Required in implementation PR and phase closeout |

# 6. Status vocabulary

Use: `NOT STARTED`, `IN PROGRESS`, `BLOCKED`, `VALIDATING`, `PASS`, `FAIL`, `CLOSED`, `DEFERRED`.

Do not mark a phase `CLOSED` until its exit gate and closeout record are complete.

# 7. Execution log

## 2026-08-09 — Phase -1 / PR #52

- Governance/architecture hardening completed; merge `9135bdd33a46afee4f4a12b9030ca4504114924f`.
- CI/Vercel PASS; pre/post backups verified; `main-protection` later activated/API-verified.

## 2026-08-09 — Persistent roadmap / PR #53

- Added root execution/handoff index; merge `bc8ce721a82938c32ed8b9af7c91fba25a161f8a`.
- CI/Vercel PASS; pre/post backups verified.

## 2026-08-09 — Phase 0 / PR #54 + closeout #55

- Quant authority freeze merged `68cbd58d570ce7d806c2a73903b5bdb506c9bae1`; full checks/review/backups PASS.
- Closeout merged `d173f1d15a671e7d2f3c096a56e7ee3ef9f0a183`; Phase 0 CLOSED / PASS.

## 2026-08-09 — AI playbook / PR #56

- Added `AI_PROJECT_PLAYBOOK.md`; merge `863039af803671a8caf1d35074d038136ca2332a`.
- Adopted as repository-wide AI governance.

## 2026-08-09 — Phase 1 / PR #57 + closeout #58

- ResearchDataset implementation merge `7cf3fdcfa248d47a036419213da0acce594ada7c`; closeout `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`; Phase 1 CLOSED / PASS.

## 2026-08-09 — Phase 2 / PR #59 + closeout #60

- Risk Mathematics implementation merge `724075ddbb0383f7889e4b622a95a57769d5558c`; closeout `4cea3b18fdce7db5e464196172f59930abf6b7d9`; Phase 2 CLOSED / PASS.

## 2026-08-09 — Phase 3 / PR #61 + closeout

- Defined read-only Refinery V1 contract before implementation and added dedicated API/edge boundary.
- Initial CI `31301415964` found one real partial-evidence indexing defect; fixed resolved-evidence accounting without silently reducing candidate membership.
- Added explicit weight-normalization traceability and upstream error sanitization.
- Final head `4899199a50d01189904ef0842c5d5247afc4d09d` passed `validate`, Portfolio web CI, Vercel and Release Backup Gates.
- Independent final review PASS via COMMENT `4890806477`.
- Expected-head squash merge `6e18726dcc1383e0b839e4bd0bded46e720e2707`.
- Pre/post backups verified: `backup-pre-pr61-4cea3b18fdce`, `backup-post-pr61-6e18726dcc13`.
- Merge-after-push `main` CI PASS; production Vercel and Cloudflare deploy/smokes PASS.
- This doc-only closeout transitions Phase 3 to CLOSED / PASS when merged.

# 8. Exact resume point

After this doc-only Phase 3 closeout merges:

1. Query latest protected `main`; do not assume `6e18726d...` is still HEAD because this closeout itself adds a documentation commit.
2. Confirm no open unfinished Phase 3 implementation/closeout PR remains.
3. Begin **Phase 4 — Refinery Diagnostic UI only**.
4. Read `AI_PROJECT_PLAYBOOK.md`, this roadmap, `docs/research/REFINERY_API_V1.md`, `docs/research/RESEARCH_DATASET_V1.md`, `docs/quant/RISK_MATHEMATICS_V1.md`, current Portfolio web source-contract/persistence docs and tests.
5. Inventory `apps/portfolio-web/` routing, workspace/store model, persisted schema/version/migrations, API bridge/client, responsive layout, error/loading states, matrix/table rendering and source-contract/E2E tests before changing UI.
6. Define a separate versioned `RefineryWorkspaceModel` + persistence schema before implementation; existing Portfolio workspace/ledger state must remain unchanged.
7. Add only read-only diagnostic UI consuming Phase 3 `preflight`/`analyze`: structure/risk summary, capital vs signed RC, DR/effective dimensions, covariance stability, tactical/medium/structural/downside/stress correlation, data confidence and explicit incomplete/unavailable states.
8. Apply rendering/performance guards for up to 100 symbols; do not assume a full 100×100 matrix should always be rendered as raw cells on mobile.
9. Do not add clustering/redundancy verdicts, recommendation labels, marginal experiments, selection, sizing, optimization, Exhaustive integration or OOS claims in Phase 4.
10. Update this file in the Phase 4 implementation PR and complete the same doc-only closeout process before Phase 5.
