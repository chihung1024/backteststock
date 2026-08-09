# BacktestStock Development Master Plan

> Persistent execution/handoff index for `chihung1024/backteststock` and the Portfolio Refinery program. A phase/batch is not complete until this file records its status, evidence, limitations, and exact resume point.

## 1. Current baseline

- Protected production branch: `main`
- Current protected `main` SHA at Phase 2 start: `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`
- Phase 1 implementation PR: `#57` — `feat: add reproducible ResearchDatasetV1`
- Phase 1 implementation merge: `7cf3fdcfa248d47a036419213da0acce594ada7c`
- Phase 1 closeout PR: `#58`, merge `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`
- Phase 1 pre backup: `backup-pre-pr57-863039af8036`
- Phase 1 post backup: `backup-post-pr57-7cf3fdcfa248`
- Current phase state: **Phase 2 — VALIDATING / PR #59**
- Active implementation PR: `#59` — `feat: add validated risk mathematics core`
- Phase 2 base SHA: `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`
- Phase 2 pre backup: `backup-pre-pr59-666c561c0abf`
- Latest pre-roadmap-update Phase 2 head: `928307fe7395e9f22720bbaa950a4b7b899b1769`; query PR #59 again before final review because this roadmap update creates a newer head.
- Next implementation phase after Phase 2 closeout only: **Phase 3 — Read-only Refinery API**
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

## 3. Architecture boundaries

- `apps/api/app/data/` — shared TWD market-data, FX, return-component and valuation authority.
- `apps/api/app/portfolio/` — Portfolio v3 ledger/path-dependent analysis authority.
- `apps/api/app/research/` — additive research-domain data/services beginning with `ResearchDatasetV1`; it must not become a second downloader.
- `apps/api/app/quant/` — pure validated quantitative primitives; no API/UI/selection/sizing side effects.
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

### Completed implementation — PR #57

- [x] Added `apps/api/app/research/` package.
- [x] Defined/versioned `ResearchDatasetV1` as `research-dataset-twd-2026-08-09.1`.
- [x] `ResearchDatasetService` delegates fetching to existing `TWDHistoryService`; no second downloader.
- [x] Preserves requested order, resolved order and explicit `HistoryFailure` evidence.
- [x] Enforces exactly-one success/failure outcome per requested symbol; neither and both states are rejected.
- [x] Enforces requested inclusive `[start, end]` isolation for native, FX and TWD source series to prevent wider-history/look-ahead leakage.
- [x] Stores requested/effective dates separately.
- [x] Builds union reference calendar and Exhaustive-compatible first/last availability masks.
- [x] Reports descriptive per-symbol coverage and `_global_complete_case` without embedding Scanner/Exhaustive consumer thresholds.
- [x] Builds aligned daily TWD levels with existing `align_twd_price_frame()` semantics for parity.
- [x] Builds daily arithmetic return matrix excluding the synthetic opening row.
- [x] Builds `W-FRI` structural weekly levels/returns using the last **actual** observation date, never a future Friday label.
- [x] Retains native and FX returns, corporate-action/FX/return-component audits, quote metadata and native/FX/TWD fingerprints.
- [x] Adds canonical JSON export and deterministic SHA-256 dataset identity.
- [x] Canonical serialization sorts mapping/set inputs, normalizes NumPy scalar types and serializes non-finite numbers as JSON `null`.
- [x] `export_payload()` recomputes current content identity and rejects stale hash after mutation; consumers rebuild rather than export changed content as the same dataset.
- [x] Added `docs/research/RESEARCH_DATASET_V1.md`.
- [x] Added tests for membership/failure visibility, coverage/date semantics, weekly actual dates, deterministic/data-sensitive hash, stale-hash mutation rejection, single history fetch, missing outcome rejection, conflicting outcome rejection, out-of-window rejection and parity with current Exhaustive preparation.
- [x] Scanner, Portfolio v3, Worker, UI and `api/exhaustive_optimizer.py` production consumers remained unchanged.

### Phase 1 decisions retained as contract

1. `TWDHistoryService` remains the source authority; ResearchDataset is alignment/audit/reproducibility, not a downloader.
2. Current Exhaustive preparation was used as a parity oracle only. Phase 1 did not migrate production Exhaustive.
3. A partial dataset is valid evidence with `is_complete == false`; strict consumers must reject it explicitly rather than receive a silently reduced universe.
4. Membership outcome is XOR/fail-closed: exactly one success or failure per requested symbol.
5. Coverage is descriptive. Scanner coverage and Exhaustive's 98% rule remain consumer policies.
6. Weekly structural timestamps preserve last actual observations to avoid future-date labelling.
7. Daily alignment deliberately depends on existing `align_twd_price_frame()` for exact semantic parity. Generic calendar-primitive extraction is deferred until a validated consumer migration requires it.
8. The pure builder independently rejects histories outside the requested window to protect future cached/walk-forward use.
9. In-memory pandas/NumPy objects remain mutable for research ergonomics, but export refuses stale identity after mutation.
10. No covariance/correlation, API/UI, selection, sizing or OOS engine was added in Phase 1.

### Final Phase 1 validation / evidence

- Implementation PR: `#57`
- Base SHA: `863039af803671a8caf1d35074d038136ca2332a`
- Final head SHA: `7d7f85ed91cd1b69ed94c7be48503cd12e49e2e0`
- Implementation merge SHA: `7cf3fdcfa248d47a036419213da0acce594ada7c`
- Closeout PR: `#58`, merge `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`.
- Final `validate`: PASS — Python compile/lint/tests, ResearchDataset parity/integrity tests, JS/Worker/score tests, Playwright E2E, Vercel config validation, D1 local migration and Cloudflare dry-run.
- Vercel required check: PASS.
- Independent final diff review: PASS.
- Pre backup: `backup-pre-pr57-863039af8036` -> `863039af803671a8caf1d35074d038136ca2332a`.
- Post backup: `backup-post-pr57-7cf3fdcfa248` -> `7cf3fdcfa248d47a036419213da0acce594ada7c`.

### Known limitations carried forward

- ResearchDataset exists but no production consumer has migrated to it yet.
- Daily calendar alignment still intentionally reuses `align_twd_price_frame()`; generic extraction is deferred.
- Export exists only as an internal JSON-safe object; no public API, compression or server persistence is provided yet.
- ResearchDataset internals are mutable; stale-hash export is blocked, but consumers should treat built datasets as immutable snapshots and rebuild after intended mutation.
- No point-in-time Universe or fundamentals are introduced by Phase 1.

### Exit gate

- [x] Contract versioned.
- [x] Deterministic/data-sensitive dataset identity implemented.
- [x] Exhaustive preparation parity passed on approved in-window fixtures.
- [x] No silent membership/date mutation; ambiguous outcomes and out-of-window histories fail closed.
- [x] Stale-hash export blocked.
- [x] Existing production consumers unchanged.
- [x] Final required checks PASS.
- [x] Independent review PASS.
- [x] PR #57 merged by expected-head squash.
- [x] Post-merge backup verified.
- [x] Closeout PR #58 merged; Phase 1 CLOSED / PASS.

---

## Phase 2 — Risk Mathematics Core

**Status: VALIDATING — implementation PR #59 open as Draft**

### Objective
Implement validated pure quantitative primitives for portfolio structure analysis. Phase 2 is a mathematics/test layer only; no Refinery API/UI or selection logic.

### First actions

- [x] Queried protected `main`; Phase 2 base is `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`.
- [x] Confirmed no unfinished Phase -1/0/1 implementation PR remained before Phase 2 start.
- [x] Inventoried dependencies: production uses NumPy/Pandas/SciPy; scikit-learn was absent from runtime and is added only to dev/test requirements as a reference oracle.
- [x] Verified Ledoit-Wolf semantics against `sklearn.covariance.ledoit_wolf`; production implementation remains NumPy-only.
- [x] Defined `risk-math-twd-2026-08-09.1` and `docs/quant/RISK_MATHEMATICS_V1.md` before any API/UI integration.

### Implemented in PR #59

- [x] Added framework-neutral `apps/api/app/quant/` package.
- [x] Added unbiased sample covariance (`ddof=1`) as diagnostic/reference estimator.
- [x] Added NumPy Ledoit-Wolf spherical-target shrinkage matching scikit-learn reference semantics, including centered and `p > n` cases.
- [x] Added explicit caller-decay EWMA covariance sensitivity estimator.
- [x] Added covariance symmetry/PSD/eigenvalue/numerical-rank/condition-number diagnostics.
- [x] Added estimator-dispersion diagnostics using pairwise relative Frobenius distance.
- [x] Added portfolio variance/volatility, MRC, **signed** RC and Diversification Ratio.
- [x] Added weight-effective holdings and separate gross-RC equivalent holdings without hiding signed hedge RC.
- [x] Added entropy effective rank and participation ratio for correlation/covariance; these remain diagnostics, not an exact independent-bets claim.
- [x] Added tactical 63D, medium 252D and structural 156W correlation primitives with explicit caller-supplied minimum observations.
- [x] Added downside and benchmark-tail stress correlation with fail-closed insufficient-sample status.
- [x] Corrected conditional-sample accounting so condition-ineligible rows are not mislabeled as dropped observations; incomplete eligible asset rows remain visible as drops.
- [x] Removed benchmark-column-name collision risk by using an internal collision-proof alignment label.
- [x] Hardened covariance/risk numerical tolerances to scale with matrix magnitude instead of applying an artificial `1.0` covariance scale floor.
- [x] Added `tests/fixtures/risk_math_v1.json`, `tests/test_risk_mathematics.py`, and `tests/test_risk_mathematics_hardening.py`.
- [x] Added metamorphic/invariant coverage for permutation, duplicate dimensions, signed hedge RC, small-scale covariance diagnostics, positive matrix-scale invariance and materially negative tiny variance rejection.
- [x] Kept Scanner, Portfolio v3, Exhaustive, Worker, UI and runtime consumers unchanged.
- [x] `requirements.txt` remains unchanged; `scikit-learn==1.9.0` is dev/test-only.

### Validation finding — first CI failure and root cause

- Initial PR head `bfcb771e69bf26397018bafef303d4279e46903f` reached Python tests with dependency install, pip consistency, compile and Ruff all PASS.
- Initial CI run `31298692601` failed only at the new Python golden tests: **190 tests passed, 3 new golden tests failed**; later JS/E2E/deployment steps were skipped because Python test failure stopped the job.
- The three failures all traced to incorrect manually seeded values in `tests/fixtures/risk_math_v1.json` (sample covariance, downstream annualized Ledoit-Wolf risk values and effective-rank values).
- The production NumPy Ledoit-Wolf implementation was **not** the root cause: its dedicated multi-shape scikit-learn reference-parity tests did not fail.
- Golden values were recomputed and then independently anchored by a new test directly comparing fixture sample covariance to `numpy.cov(..., ddof=1)` and fixture Ledoit-Wolf covariance/shrinkage to `sklearn.covariance.ledoit_wolf`.
- This finding is retained as test-governance evidence: a golden fixture is not an authority unless its provenance is itself independently verified.

### Current validation state

- Pre backup verified: `backup-pre-pr59-666c561c0abf` -> `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`.
- Release Backup Gates have continued to PASS on subsequent PR heads.
- Vercel check passed on the original Phase 2 head; final-head Vercel must be rechecked after this roadmap update.
- Latest pre-roadmap-update head: `928307fe7395e9f22720bbaa950a4b7b899b1769`.
- Full final-head `validate`, Vercel, changed-file scope review and independent diff review remain **pending after this roadmap commit**.
- Do not mark Phase 2 PASS/CLOSED until the final current head passes all required gates and the post-merge closeout is complete.

Required invariants:

- [x] covariance symmetry/PSD/rank diagnostics use relative matrix-scale tolerance;
- [x] portfolio variance rejects materially negative values rather than clipping them through a unit-scale tolerance;
- [x] `sum(RC) == portfolio volatility` within tolerance;
- [x] asset-order permutation invariance;
- [x] duplicated identical assets do not manufacture structural diversification;
- [x] negative signed hedge RC remains visible;
- [x] insufficient stress/downside samples return unavailable/uncertain rather than false precision;
- [x] conditional sample metadata distinguishes condition filtering from missing-data drops;
- [x] golden covariance/shrinkage values are independently tied to NumPy/scikit-learn references.

### Explicit non-goals

- No Refinery public API.
- No Refinery UI.
- No clustering/redundancy engine.
- No selection or sizing.
- No Exhaustive migration/integration.
- No OOS recommendation claim.

### Exit gate

- [x] Methodology contract/version frozen.
- [x] Reference estimator parity tests implemented.
- [x] Mathematical invariants/metamorphic tests implemented.
- [x] No API/UI or later-phase logic added.
- [ ] Final current-head `validate` PASS after corrected golden fixture/numerical hardening/roadmap update.
- [ ] Final current-head Vercel PASS.
- [ ] Final changed-file scope and independent diff review PASS.
- [ ] PR #59 expected-head squash merge.
- [ ] Post-merge Release backup verified.
- [ ] Doc-only Phase 2 closeout merged.

---

## Phase 3 — Read-only Refinery API

**Status: PLANNED — DO NOT START until Phase 2 closeout is merged**

- [ ] Separate Refinery/research namespace; do not overload Portfolio v3 ledger contract.
- [ ] `preflight` and `analyze` only.
- [ ] Approved candidate-pool target: up to 100 symbols.
- [ ] Strict request/history/computation/rate/response-size guards.
- [ ] Explicit per-symbol failures; no silent membership changes.
- [ ] Return structure/risk diagnosis, covariance diagnostics, effective dimensions, data quality and reproducibility.
- [ ] Fixed Worker allowlist.
- [ ] Security/performance tests.

Non-goal: no BUY/SELL/TRIM/REPLACE or sizing.

---

## Phase 4 — Refinery Diagnostic UI

**Status: PLANNED**

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
| OOS/walk-forward evidence | Required for recommendation claims from Phase 7 onward |
| Pre/post Release backup | Required for runtime/quant-methodology PRs |
| Independent diff review | Required before merge |
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
- Final implementation head `7d7f85ed91cd1b69ed94c7be48503cd12e49e2e0` passed full `validate` and Vercel.
- Independent final review PASS.
- Implementation squash merge `7cf3fdcfa248d47a036419213da0acce594ada7c`.
- Pre/post backups verified: `backup-pre-pr57-863039af8036`, `backup-post-pr57-7cf3fdcfa248`.
- Closeout PR #58 merged `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`; Phase 1 CLOSED / PASS.

## 2026-08-09 — Phase 2 / PR #59 — VALIDATING

- Added pure Risk Mathematics V1 primitives without production consumer integration.
- Dev-only scikit-learn reference oracle added; runtime dependency set unchanged.
- Initial CI run `31298692601`: dependency consistency/compile/Ruff PASS, Python result **190 passed / 3 failed**; all three failures were newly added golden assertions.
- Root-cause review showed the golden fixture numbers were incorrect; independent NumPy/scikit-learn reference calculations agreed with the implementation, so production math was not altered to fit bad expected values.
- Corrected fixture and added a test that anchors fixture values directly to NumPy sample covariance and scikit-learn Ledoit-Wolf.
- Hardened covariance/risk relative tolerance behavior and conditional-correlation sample accounting within Phase 2 scope.
- Pre backup verified: `backup-pre-pr59-666c561c0abf`.
- Current state: rerun final-head gates after this roadmap commit; do not merge or enter Phase 3 until all required checks/review pass.

# 8. Exact resume point

Current task is still **Phase 2 — Risk Mathematics Core / PR #59**.

1. Query PR #59 current head after this roadmap commit; do not use the pre-roadmap SHA as final head.
2. Wait for/check the latest `validate` workflow. If it fails, inspect the exact failed Phase 2 test and fix only the demonstrated mathematics/test-contract defect.
3. Verify final-head Vercel required context is `success`.
4. Verify changed-file scope contains only Phase 2 pure math, tests, dev-reference dependency, methodology docs and this roadmap; no Scanner/Portfolio/Exhaustive/Worker/UI production consumer changes.
5. Independently review the final diff, including corrected golden provenance, Ledoit-Wolf parity, relative tolerance behavior and conditional-sample accounting.
6. Only after all gates PASS: mark PR #59 Ready and squash merge using the exact current head SHA.
7. Verify `backup-post-pr59-<merge-sha-prefix>` points exactly to the merge SHA.
8. Create a doc-only Phase 2 closeout PR recording final implementation head, merge SHA, final CI/Vercel/review, pre/post backups, limitations and the precise Phase 3 resume point.
9. Phase 2 becomes `CLOSED / PASS` only after that closeout merges.
10. **Do not start Phase 3 before step 9.**
