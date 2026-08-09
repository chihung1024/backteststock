# BacktestStock Development Master Plan

> Persistent execution/handoff index for `chihung1024/backteststock` and the Portfolio Refinery program. A phase/batch is not complete until this file records its status, evidence, limitations, and exact resume point.

## 1. Current baseline

- Protected production branch: `main`
- Phase 3 start/main SHA: `4cea3b18fdce7db5e464196172f59930abf6b7d9`
- Active implementation PR: `#61` — `feat: add read-only Portfolio Refinery API`
- Phase 3 base SHA: `4cea3b18fdce7db5e464196172f59930abf6b7d9`
- Phase 3 pre backup: `backup-pre-pr61-4cea3b18fdce`
- Latest pre-roadmap-update Phase 3 head: `ecb4a04364c38822637f571238f17d82951bbf7c`; query PR #61 again before final review because this roadmap update creates a newer head.
- Current phase state: **Phase 3 — VALIDATING / PR #61**
- Next implementation phase after Phase 3 closeout only: **Phase 4 — Refinery Diagnostic UI**
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
- `api/refinery_v1.py` — dedicated Phase 3 FastAPI entrypoint for `/api/v1/refinery/*`.
- `api/portfolio_v3.py` — production FastAPI Portfolio v3 entrypoint.
- `api/index_v2.py`, `api/scan_v2.py`, `api/screener.py` — current compatibility/production entrypoints as documented.
- `api/exhaustive_optimizer.py` — full-period historical research/search snapshot path, not an OOS validation engine.
- `apps/portfolio-web/` — Portfolio v3 production web source.
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

Implementation:

- PR `#54`, merge `68cbd58d570ce7d806c2a73903b5bdb506c9bae1`
- Pre: `backup-pre-pr54-bc8ce721a829`
- Post: `backup-post-pr54-68cbd58d570c`
- Final CI/Portfolio-web/Vercel PASS; independent review PASS.
- Added metric/return/risk-policy authority docs, shared golden fixture, Python parity tests and JS Exhaustive exact parity test.
- Preserved the existing 365.25 vs 365.2425 CAGR year-length difference as an explicit versioned distinction rather than silently changing production.

Closeout:

- PR `#55`, merge `d173f1d15a671e7d2f3c096a56e7ee3ef9f0a183`
- Doc-only; required checks PASS.

Known Phase 0 limitations retained:

- 365.25 vs 365.2425 CAGR year-length difference remains documented but not normalized.
- Production callers were intentionally not migrated to a shared quant primitive layer in Phase 0.

---

## Phase 1 — ResearchDataset

**Status: CLOSED / PASS**

### Objective
Create one reproducible framework-neutral research dataset contract over existing audited TWD histories, usable by future Refinery and eventually reusable by Exhaustive only after parity validation.

### Completed implementation

- PR `#57`, implementation merge `7cf3fdcfa248d47a036419213da0acce594ada7c`.
- Closeout PR `#58`, merge `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`.
- Contract/version: `ResearchDatasetV1` / `research-dataset-twd-2026-08-09.1`.
- `ResearchDatasetService` delegates fetching to existing `TWDHistoryService`; no second downloader.
- Preserves requested/resolved membership and explicit failures; exactly-one success/failure outcome is fail-closed.
- Enforces requested inclusive `[start, end]` isolation for native, FX and TWD source series.
- Builds union reference calendar, availability masks, descriptive coverage, aligned daily TWD levels/returns and actual-date `W-FRI` structural weekly levels/returns.
- Retains native/FX returns, corporate-action/FX/return-component audits, quote metadata and fingerprints.
- Canonical JSON identity is deterministic; stale-hash export after mutation is rejected.
- Exhaustive preparation parity tests pass while production Exhaustive remains unchanged.

### Final Phase 1 evidence

- Final implementation head: `7d7f85ed91cd1b69ed94c7be48503cd12e49e2e0`.
- Final `validate` and Vercel: PASS.
- Independent final diff review: PASS.
- Pre: `backup-pre-pr57-863039af8036`.
- Post: `backup-post-pr57-7cf3fdcfa248`.

### Known limitations carried forward

- ResearchDataset exists but production consumers have not migrated to it.
- Daily alignment intentionally reuses `align_twd_price_frame()` for semantic parity.
- Export is internal JSON-safe data only; no public persistence/compression API yet.
- No point-in-time Universe or fundamentals are introduced by Phase 1.

---

## Phase 2 — Risk Mathematics Core

**Status: CLOSED / PASS**

### Objective
Implement validated pure quantitative primitives for portfolio structure analysis. Phase 2 is a mathematics/test layer only; no Refinery API/UI, clustering, selection or sizing.

### Completed implementation / evidence

- Implementation PR `#59`, final head `9cd00609bcbdde210bdc024fa224016ca3dda6d3`, squash merge `724075ddbb0383f7889e4b622a95a57769d5558c`.
- Closeout PR `#60`, merge `4cea3b18fdce7db5e464196172f59930abf6b7d9`.
- Contract/version: `risk-math-twd-2026-08-09.1`.
- Added sample/Ledoit-Wolf/EWMA covariance, numerical diagnostics, estimator dispersion, portfolio variance/volatility/MRC/signed RC/DR, effective counts/ranks and guarded multi-horizon/downside/stress correlation.
- NumPy Ledoit-Wolf is independently anchored to scikit-learn; scikit-learn remains dev/test-only.
- Initial CI exposed three incorrect manually seeded golden expected values; NumPy/scikit-learn re-derivation proved fixture wrong and implementation correct. Fixture provenance was then independently anchored rather than modifying production mathematics to fit bad expected values.
- Final PR-head `validate`, Vercel, Release Backup Gates, independent diff review and merge-after-push `main` CI PASS.
- Pre: `backup-pre-pr59-666c561c0abf`.
- Post: `backup-post-pr59-724075ddbb03`.
- GitHub author self-approval limitation documented via COMMENT review `4890745183`; no branch-protection requirement was bypassed.

### Known limitations carried forward

1. Correlation minimum-observation thresholds remain caller policy.
2. EWMA decay remains caller policy.
3. Effective rank/participation ratio are structural diagnostics, not proof of exact independent economic bets.
4. No clustering, factor overlap, marginal experiments, recommendation labels, sizing or OOS claim exists yet.

---

## Phase 3 — Read-only Refinery API

**Status: VALIDATING — implementation PR #61 open as Draft**

### Objective
Expose Phase 1 ResearchDataset + Phase 2 Risk Mathematics through a separate deterministic read-only research API without changing Portfolio v3 ledger semantics or exposing clustering/selection/sizing/recommendation behavior.

### Completed design/inventory

- [x] Queried latest protected `main`; Phase 3 base is `4cea3b18fdce7db5e464196172f59930abf6b7d9`.
- [x] Confirmed no unfinished Phase 2 PR remained before Phase 3 start.
- [x] Read AI playbook, roadmap, ResearchDataset/Risk Mathematics contracts, ADRs, Worker routing/security, Vercel routes and current API/resource conventions before endpoint implementation.
- [x] Identified existing edge budgets: general API 256 KiB, Portfolio v3 512 KiB, Exhaustive prepare 3 MiB, 240s API timeout. Refinery was assigned an explicit separate 512 KiB request budget rather than inheriting Exhaustive's exception.
- [x] Defined `docs/research/REFINERY_API_V1.md` before implementation.
- [x] Frozen contract identifiers: `refinery-v1` / `refinery-v1-2026-08-09.1`.

### Implemented in PR #61

- [x] Added separate `apps/api/app/refinery/` request/service boundary.
- [x] Added dedicated FastAPI entrypoint `api/refinery_v1.py`; Refinery is not embedded in Portfolio v3 or legacy Flask handlers.
- [x] Added dedicated Vercel route `/api/v1/refinery/(.*)` before the legacy catch-all.
- [x] Added fixed Worker allowlist for exactly `POST preflight` and `POST analyze`; unknown paths/wrong methods fail closed.
- [x] Candidate request contract: 2–100 unique normalized symbols, explicit dates, optional explicit benchmark, optional exact candidate weights, explicit EWMA decay/stress quantile.
- [x] Reuses existing `normalize_symbol()` including Taiwan numeric shorthand; no second symbol-normalization rule.
- [x] No benchmark default is fabricated; missing benchmark explicitly disables downside/stress diagnostics.
- [x] No equal-weight default is fabricated; portfolio variance/MRC/RC/DR/weight-effective diagnostics are unavailable if weights are omitted.
- [x] Explicit weights must cover every candidate exactly once and total 100% within ±0.05 percentage point. Accepted tolerance is mechanically normalized proportionally to exact unit sum for Phase 2 risk math; raw weights/raw total and normalization policy remain visible.
- [x] Performs one authoritative `TWDHistoryService.histories_partial()` fetch for candidates plus optional distinct benchmark.
- [x] Builds separate candidate and benchmark ResearchDataset views from the same audited batch so benchmark choice cannot alter candidate complete-case covariance/correlation samples.
- [x] `preflight` may expose partial data/failure evidence; partial complete-case counts are descriptive over resolved evidence only.
- [x] Any unresolved **candidate** forces status `incomplete` and `analysis=null`; no silent reduced-universe risk calculation.
- [x] Benchmark failure preserves candidate structural analysis and disables only conditional correlations with explicit unavailable state/failure evidence.
- [x] Candidate-complete but short history returns `insufficient_data`; no false precision.
- [x] Ledoit-Wolf annualized covariance is primary formal risk estimator; sample/EWMA remain diagnostics/sensitivity.
- [x] Exposes covariance numerical diagnostics/dispersion, structural effective dimensions, optional explicit-weight portfolio risk and guarded tactical/medium/structural/downside/stress correlation views.
- [x] Public response omits raw price arrays and full ResearchDataset exports.
- [x] Canonical deterministic JSON, 4 MiB response bound, 512 KiB request bounds, no-store/security headers and best-effort general/analyze rate limits implemented.
- [x] Worker strips authorization/cookies and backend-identifying headers; dedicated route bypasses generic edge cache.
- [x] Runtime upstream failures are logged server-side but client receives a generic stable `upstream_failure` rather than raw provider/internal exception text.
- [x] CI compile list, Worker test suite and Vercel deployment contract updated for dedicated Refinery entrypoint/route.

### Phase 3 tests implemented

- [x] Symbol normalization/duplicate/resource/date/weight contract tests.
- [x] Weight tolerance proportional-normalization test.
- [x] One-fetch candidate/benchmark separation test.
- [x] Benchmark invariance test for candidate dataset/covariance/effective/correlation structural views.
- [x] Candidate partial-data fail-closed test.
- [x] Benchmark-failure conditional-only degradation test.
- [x] No-weights/no-equal-weight test.
- [x] Direct Phase 2 risk wiring parity test.
- [x] Repeated injected-data deterministic payload test.
- [x] Canonical/security-header/validation/body-size/response-size/rate-limit/upstream-error API tests.
- [x] Worker route allowlist/method/body/header sanitization/no-cache tests.
- [x] Vercel route/build contract test.

### First CI failure — root cause and disposition

Initial PR #61 CI run `31301415964` reached Python tests after dependency install, pip consistency, compile and Ruff all PASS. Python result was **210 passed / 1 failed**; later Node/E2E/deployment steps were skipped only because the Python job failed.

The failing test was `test_incomplete_candidate_blocks_formal_analysis_without_silent_deletion`.

Root cause:

- the service had already correctly classified a candidate dataset with a failed symbol as `incomplete`;
- but before returning diagnostic preflight evidence, `_finite_complete_case()` still selected `request.symbols` from a DataFrame containing only `resolved_symbols`, causing a pandas `KeyError` for the failed candidate;
- this was a mismatch between **partial evidence accounting** and **formal requested-membership semantics**, not a reason to remove the failed candidate.

Disposition:

- complete-case evidence counts now use `candidate_dataset.resolved_symbols`;
- requested/resolved/failure membership remains explicit;
- status remains `incomplete` and formal `analysis` remains `null` whenever any candidate is unresolved;
- zero-resolved-symbol evidence is handled as an empty frame rather than another indexing failure;
- no reduced-universe calculation was introduced.

### Additional same-scope hardening found during review

1. Weight total tolerance originally allowed e.g. 99.99%, while Phase 2 requires unit-sum weights. Accepted raw weights now preserve proportions but normalize mechanically to exact unit sum; this is explicit in contract/payload/tests and is not sizing.
2. Raw `RuntimeError` text was initially returned for an upstream failure. It is now logged server-side and replaced with a generic client error to prevent provider/internal-detail leakage.

### Current validation evidence

- Pre backup verified: `backup-pre-pr61-4cea3b18fdce` -> `4cea3b18fdce7db5e464196172f59930abf6b7d9`.
- Release Backup Gates have repeatedly PASSed on later heads.
- Portfolio web CI on pre-roadmap head `ecb4a04364c38822637f571238f17d82951bbf7c`: PASS.
- Full `validate` run `31301739846` on pre-roadmap head `ecb4a04364c38822637f571238f17d82951bbf7c`: **PASS** — dependencies/pip check, compile, Ruff, all Python tests, JS syntax, Worker tests, score tests, Playwright E2E, Vercel config validation, D1 local migration and Cloudflare dry-run all succeeded.
- Vercel required context for that pre-roadmap head was still pending when this roadmap update was prepared.
- This roadmap update creates a new PR head, therefore the previous PASS is evidence only, **not final-head authorization to merge**.
- Final current-head `validate`, Vercel, final changed-file scope review and independent diff review remain required after this commit.

### Explicit non-goals preserved

- No UI.
- No clustering/redundancy engine or verdicts.
- No BUY/SELL/KEEP/TRIM/REPLACE.
- No selection or sizing.
- No HRP/ERC/minimum-variance optimizer.
- No Leave-One-Out/Add-One/Replace-One.
- No Exhaustive integration.
- No OOS/walk-forward claim.
- No Portfolio v3 ledger migration.

### Exit gate

- [x] API contract/version frozen and documented.
- [x] Separate Refinery runtime/edge route defined.
- [x] Preflight/analyze deterministic/fail-closed behavior implemented.
- [x] Candidate/benchmark sample isolation implemented/tested.
- [x] Request/response/rate/error/security guards implemented/tested.
- [x] First CI defect root-caused without silent candidate deletion.
- [x] Pre-roadmap implementation head passed full `validate`.
- [ ] Query new current PR head after this roadmap commit.
- [ ] Final current-head `validate` PASS.
- [ ] Final current-head Vercel required context PASS.
- [ ] Final changed-file scope + independent diff review PASS.
- [ ] PR #61 expected-head squash merge.
- [ ] Post-merge backup verified.
- [ ] Merge-after-push `main` CI PASS.
- [ ] Doc-only Phase 3 closeout merged; only then Phase 3 becomes `CLOSED / PASS`.

---

## Phase 4 — Refinery Diagnostic UI

**Status: PLANNED — DO NOT START until Phase 3 closeout is merged**

- [ ] Separate `RefineryWorkspaceModel` and persisted schema from Portfolio workspace.
- [ ] Workspace switch: Portfolio backtest / holding refinement.
- [ ] Structure summary.
- [ ] Capital weight vs signed risk contribution.
- [ ] Effective holdings/risk dimensions and Diversification Ratio.
- [ ] Tactical/structural/downside/stress correlation views.
- [ ] Data confidence/effective observations.
- [ ] Covariance stability diagnostics.
- [ ] Large-matrix rendering guard.

Exit gate: deterministic read-only diagnosis; existing Portfolio UI unchanged.

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

- Added `ResearchDatasetV1` and reproducibility/parity/integrity tests without production consumer migration.
- Implementation squash merge `7cf3fdcfa248d47a036419213da0acce594ada7c`; pre/post backups and final gates PASS.
- Closeout PR #58 merged `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`; Phase 1 CLOSED / PASS.

## 2026-08-09 — Phase 2 / PR #59 + closeout #60

- Added pure Risk Mathematics V1 without recommendation/selection/sizing logic.
- Incorrect golden fixture root-caused and independently re-anchored instead of changing valid mathematics.
- Implementation squash merge `724075ddbb0383f7889e4b622a95a57769d5558c`; final gates/backups PASS.
- Closeout PR #60 merged `4cea3b18fdce7db5e464196172f59930abf6b7d9`; Phase 2 CLOSED / PASS.

## 2026-08-09 — Phase 3 / PR #61 — VALIDATING

- Defined read-only Refinery V1 contract before implementation.
- Added dedicated FastAPI/Vercel/Worker route boundary and ResearchDataset + Risk Mathematics composition.
- Initial CI run `31301415964`: 210 Python tests passed / 1 failed after compile/Ruff PASS. Root cause was partial candidate evidence-count indexing requested membership rather than resolved evidence.
- Fixed evidence counting while preserving fail-closed formal membership; no silent candidate deletion.
- Added proportional unit-sum normalization for accepted explicit-weight total tolerance and sanitized upstream runtime errors.
- Pre-roadmap head `ecb4a04364c38822637f571238f17d82951bbf7c` passed full `validate` run `31301739846`; Portfolio web CI and Release Backup Gates also PASS.
- Pre backup verified: `backup-pre-pr61-4cea3b18fdce`.
- Current state: this roadmap commit creates a newer head; rerun final-head gates, then independent review/merge only if all remain PASS.

# 8. Exact resume point

Current task remains **Phase 3 — Read-only Refinery API / PR #61**.

1. Query PR #61 current head after this roadmap commit; do not reuse `ecb4a043...` as final head.
2. Wait for/check latest `validate`; if it fails, inspect exact evidence and fix only the demonstrated Phase 3 contract/implementation defect.
3. Verify latest current-head Vercel required context is `success`.
4. Verify Release Backup Gate remains PASS and `backup-pre-pr61-4cea3b18fdce` still points to Phase 3 base/main.
5. Verify final changed-file scope contains only dedicated Refinery backend/edge/deployment contract/tests/docs/CI wiring/roadmap; no Portfolio UI, clustering, selection, sizing or Exhaustive logic.
6. Independently review the final diff, specifically requested-vs-resolved partial semantics, candidate/benchmark sample isolation, no hidden equal weights, weight normalization traceability, response exposure, route/resource/security guards and Phase 2 wiring.
7. Only after all gates PASS: mark PR #61 Ready and squash merge using the exact current head SHA.
8. Verify `backup-post-pr61-<merge-sha-prefix>` points exactly to the merge SHA.
9. Verify merge-after-push `main` CI.
10. Create a doc-only Phase 3 closeout PR recording final implementation head/merge/checks/review/pre-post backups/limitations and exact Phase 4 resume point.
11. Phase 3 becomes `CLOSED / PASS` only after that closeout merges.
12. **Do not start Phase 4 before step 11.**
