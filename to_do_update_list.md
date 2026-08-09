# BacktestStock Development Master Plan

> Persistent execution/handoff index for `chihung1024/backteststock` and the Portfolio Refinery program. A phase/batch is not complete until this file records its status, evidence, limitations, and exact resume point.

## 1. Current baseline

- Protected production branch: `main`
- Phase 1 implementation PR: `#57` — `feat: add reproducible ResearchDatasetV1`
- Phase 1 final implementation head: `7d7f85ed91cd1b69ed94c7be48503cd12e49e2e0`
- Phase 1 implementation merge: `7cf3fdcfa248d47a036419213da0acce594ada7c`
- Phase 1 pre backup: `backup-pre-pr57-863039af8036`
- Phase 1 post backup: `backup-post-pr57-7cf3fdcfa248`
- Current phase state: **Phase 1 — CLOSED / PASS after this doc-only closeout merges**
- Next implementation phase: **Phase 2 — Risk Mathematics Core**
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
- `apps/api/app/quant/` remains a conceptual future shared primitive boundary; production callers were intentionally not migrated.

---

## Phase 1 — ResearchDataset

**Status: CLOSED / PASS after this doc-only closeout merges**

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
- Changed files: exactly 5 — `apps/api/app/research/__init__.py`, `apps/api/app/research/dataset.py`, `docs/research/RESEARCH_DATASET_V1.md`, `tests/test_research_dataset.py`, `to_do_update_list.md`.
- Final `validate`: PASS — Python compile/lint/tests, ResearchDataset parity/integrity tests, JS/Worker/score tests, Playwright E2E, Vercel config validation, D1 local migration and Cloudflare dry-run.
- Vercel required check: PASS.
- Independent final diff review: PASS.
- Pre backup: `backup-pre-pr57-863039af8036` -> `863039af803671a8caf1d35074d038136ca2332a`.
- Post backup: `backup-post-pr57-7cf3fdcfa248` -> `7cf3fdcfa248d47a036419213da0acce594ada7c`.

### Known limitations carried forward

- ResearchDataset exists but no production consumer has migrated to it yet.
- Daily calendar alignment still intentionally reuses `align_twd_price_frame()`; generic extraction is deferred.
- Weekly structural return policy exists, but covariance/correlation calculations do not exist until Phase 2.
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
- [x] This closeout records final evidence; Phase 1 becomes `CLOSED / PASS` when it merges.

---

## Phase 2 — Risk Mathematics Core

**Status: NEXT / NOT STARTED — begin only after this Phase 1 closeout merges**

### Objective
Implement validated pure quantitative primitives for portfolio structure analysis. Phase 2 is a mathematics/test layer only; no Refinery API/UI or selection logic.

### First actions

- [ ] Query current protected `main` SHA after this closeout.
- [ ] Confirm no open Phase -1/0/1 implementation PR remains.
- [ ] Inventory current dependency versions (`numpy`, `pandas`, `scipy`, whether `scikit-learn` is present only in dev/absent) and all current risk/covariance/correlation helpers before code changes.
- [ ] Verify the intended Ledoit-Wolf formula against a primary/reference implementation; do not assume a hand implementation is correct without parity tests.
- [ ] Define the Phase 2 methodology contract and pure module boundary before API/UI integration.

### Planned work

- [ ] Covariance estimator interface.
- [ ] Sample covariance diagnostic estimator.
- [ ] Ledoit-Wolf shrinkage estimator with reference parity.
- [ ] EWMA sensitivity estimator.
- [ ] Symmetry, PSD/eigenvalue, condition-number and estimator-dispersion diagnostics.
- [ ] Effective observation metadata.
- [ ] Portfolio volatility, MRC, signed RC, Diversification Ratio.
- [ ] Weight-effective holdings.
- [ ] Gross risk-contribution equivalent holdings while retaining signed RC.
- [ ] Correlation effective rank and covariance effective rank.
- [ ] Tactical daily, medium daily and structural synchronized-weekly correlations using Phase 1 ResearchDataset matrices.
- [ ] Downside/stress correlation with minimum-observation and uncertainty guards.
- [ ] Golden numerical fixtures, mathematical invariants and metamorphic tests.
- [ ] Update this roadmap and perform the same implementation/closeout governance.

Required invariants:

- covariance symmetry within tolerance;
- portfolio variance non-negative within tolerance;
- `sum(RC) == portfolio volatility` within tolerance;
- asset-order permutation invariance;
- duplicated identical assets do not manufacture structural diversification;
- negative signed hedge RC remains visible;
- insufficient stress/downside samples return unavailable/uncertain rather than false precision.

### Explicit non-goals

- No Refinery public API.
- No Refinery UI.
- No clustering/redundancy engine.
- No selection or sizing.
- No Exhaustive migration/integration.
- No OOS recommendation claim.

### Exit gate

- [ ] Methodology contract/version frozen.
- [ ] Reference estimator parity passes.
- [ ] Mathematical invariants/metamorphic tests pass.
- [ ] No API/UI or later-phase logic added.
- [ ] Required checks/review/pre-post backup complete.
- [ ] Doc-only Phase 2 closeout merged.

---

## Phase 3 — Read-only Refinery API

**Status: PLANNED**

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

## 2026-08-09 — Phase 1 / PR #57

- Added `ResearchDatasetV1` and reproducibility/parity/integrity tests without production consumer migration.
- Final head `7d7f85ed91cd1b69ed94c7be48503cd12e49e2e0` passed full `validate` and Vercel.
- Independent final review PASS.
- Squash merge `7cf3fdcfa248d47a036419213da0acce594ada7c`.
- Pre/post backups verified: `backup-pre-pr57-863039af8036`, `backup-post-pr57-7cf3fdcfa248`.
- This closeout transitions Phase 1 to CLOSED / PASS.

# 8. Exact resume point

After this doc-only Phase 1 closeout merges:

1. Query the latest protected `main` SHA; do not assume the Phase 1 implementation SHA is still HEAD because the closeout itself adds one documentation commit.
2. Confirm there is no open unfinished Phase -1/0/1 implementation PR.
3. Begin **Phase 2 — Risk Mathematics Core only**.
4. First read `AI_PROJECT_PLAYBOOK.md`, this file, `docs/quant/RISK_MODEL_POLICY.md`, `docs/quant/METRIC_AUTHORITY.md`, `docs/quant/RETURN_SEMANTICS.md`, and `docs/research/RESEARCH_DATASET_V1.md`.
5. Inventory installed dependency versions and current risk/covariance/correlation helper functions before implementing anything.
6. Validate Ledoit-Wolf against an authoritative/reference implementation; do not introduce a hand-coded estimator without parity evidence.
7. Implement pure risk mathematics/tests only. Do not add Refinery API/UI, clustering, selection, sizing or Exhaustive migration in Phase 2.
8. Update this file within the Phase 2 implementation PR, then complete the same doc-only closeout process before Phase 3.
