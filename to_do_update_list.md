# BacktestStock Development Master Plan

> Persistent execution/handoff index for `chihung1024/backteststock` and the Portfolio Refinery program. A phase/batch is not complete until this file records its status, evidence, limitations, and exact resume point.

## 1. Current baseline

- Protected production branch: `main`
- Current `main` before Phase 0: `bc8ce721a82938c32ed8b9af7c91fba25a161f8a`
- Last completed PR: `#53` — persistent development master roadmap
- Last verified pre-merge backup: `backup-pre-pr53-9135bdd33a46`
- Last verified post-merge backup: `backup-post-pr53-bc8ce721a829`
- Governance ruleset: `main-protection`
  - enforcement: active
  - target: default branch
  - bypass list: empty
  - deletion: blocked
  - force/non-fast-forward pushes: blocked
  - PR required
  - squash only
  - required checks: `validate` (GitHub Actions) + `Vercel`
- Current phase: **Phase 0 — Quant Authority Freeze**
- Current Phase 0 PR: `#54`
- Phase 0 state: **VALIDATING**
- Next phase after Phase 0 closes: **Phase 1 — ResearchDataset**

## 2. Mandatory execution discipline

1. Execute phases in the approved order. Do not start a later phase before the current exit gate passes.
2. Avoid unrelated refactors or feature expansion.
3. Implementation and quantitative-methodology work must use a non-`main` branch and PR.
4. Never force-push or use direct implementation commits on `main`.
5. Use squash merge and expected-head verification where supported.
6. Runtime-changing or quantitative-methodology PRs use the generic `release-backup` gate.
7. Do not silently delete tickers, shorten requested dates, substitute calendars/currencies, backfill future data, or turn unavailable metrics into valid zeroes.
8. Keep historical search/exploration separate from out-of-sample validation claims.
9. Preserve explicit methodology/contract versions whenever externally observable semantics change.
10. Update this file in every implementation PR with all information known before merge.
11. Because the final squash SHA and post-merge backup do not exist until after merge, every phase-ending implementation PR is followed by a **doc-only closeout PR** that records:
    - final merge SHA;
    - post-merge backup tag;
    - final CI/preview/review result;
    - known limitations;
    - phase status `CLOSED / PASS` or `FAIL`;
    - exact next resume point.
12. A phase is not `CLOSED` until that closeout record is merged.
13. If validation fails, preserve the last valid production behavior, record the failure here, and fix only within the current phase.
14. A future AI must read this file and the referenced authority docs before making changes.

## 3. Architecture boundaries

- `apps/api/app/data/` — shared TWD market-data, FX, return-component and valuation authority.
- `apps/api/app/portfolio/` — Portfolio v3 ledger and path-dependent portfolio-analysis authority.
- `api/portfolio_v3.py` — production self-owned FastAPI Portfolio v3 entrypoint.
- `api/index_v2.py`, `api/scan_v2.py`, `api/screener.py` — current compatibility/production entrypoints as documented.
- `api/exhaustive_optimizer.py` — full-period historical research/search snapshot path, **not** an OOS validation engine.
- `apps/portfolio-web/` — Portfolio v3 production web source.
- New Refinery logic must not be added to legacy `api/index.py` or `api/optimizer.py`.
- Portfolio v3 retains its strict production portfolio boundary; Refinery is a separate research/diagnostic domain.

Primary references:

- `docs/PHASE_MINUS1_GOVERNANCE.md`
- `docs/adr/0001-runtime-and-quant-authority.md`
- `docs/UNIFIED_TWD_CONTRACT.md`
- `docs/METRICS_REPRODUCIBILITY.md`
- `docs/EXHAUSTIVE_OPTIMIZER_V3.md`
- `docs/quant/METRIC_AUTHORITY.md` (Phase 0 PR #54)
- `docs/quant/RETURN_SEMANTICS.md` (Phase 0 PR #54)
- `docs/quant/RISK_MODEL_POLICY.md` (Phase 0 PR #54)

---

# 4. Roadmap

## Phase -1 — Governance & Architecture Hardening

**Status: CLOSED / PASS**

Completed:

- [x] Align documentation with deployed Cloudflare + Vercel compatibility + FastAPI Portfolio v3 architecture.
- [x] Add runtime inventory and ADR 0001.
- [x] Retire superseded PR19/PR38 one-off backup workflows.
- [x] Keep generic Release Backup Gates as canonical backup mechanism.
- [x] Create and activate `main-protection` ruleset.
- [x] Block branch deletion and force/non-fast-forward pushes.
- [x] Require PRs, squash-only merge, `validate`, and `Vercel`.
- [x] Confirm bypass list empty.

Evidence:

- PR `#52`
- Merge `9135bdd33a46afee4f4a12b9030ca4504114924f`
- CI: PASS
- Vercel: PASS
- Pre backup: `backup-pre-pr52-a0c640783dc9`
- Post backup: `backup-post-pr52-9135bdd33a46`
- GitHub API verified ruleset active and `main` protected.

---

## Continuity governance — persistent master roadmap

**Status: CLOSED / PASS**

- [x] Add root `to_do_update_list.md`.
- [x] Require future implementation/closeout records.

Evidence:

- PR `#53`
- Merge `bc8ce721a82938c32ed8b9af7c91fba25a161f8a`
- CI: PASS
- Vercel: PASS
- Pre backup: `backup-pre-pr53-9135bdd33a46`
- Post backup: `backup-post-pr53-bc8ce721a829`

---

## Phase 0 — Quant Authority Freeze

**Status: VALIDATING — PR #54**

### Objective
Prevent current Scanner/simple-value metrics, Portfolio v3 ledger metrics, Exhaustive exact metrics, legacy compatibility formulas, optimizer proxies, and future Refinery calculations from being confused as equivalent authorities.

### Work completed in PR #54

- [x] Inventory current metric implementations and major production callers.
- [x] Classify `api/metrics.py` as production simple-value metric authority.
- [x] Classify `apps/api/app/portfolio/metrics.py` as Portfolio v3 path-dependent ledger metric authority.
- [x] Classify `public/exhaustive-optimizer-core.js::simulateExactPortfolio()` as exact Exhaustive historical-search metric engine.
- [x] Classify `api/index.py::calculate_metrics()` and `api/scan.py::calculate_metrics()` as legacy compatibility implementations, not current production metric authorities.
- [x] Classify `public/optimizer-worker.js::proxyMetrics()` as a selection/search heuristic, not exact performance metrics.
- [x] Document canonical return semantics and context boundaries.
- [x] Add `docs/quant/METRIC_AUTHORITY.md`.
- [x] Add `docs/quant/RETURN_SEMANTICS.md`.
- [x] Add `docs/quant/RISK_MODEL_POLICY.md`.
- [x] Define future shared primitive namespace conceptually under `apps/api/app/quant/` without migrating production callers.
- [x] Add `tests/fixtures/quant_authority_v1.json` shared golden fixture.
- [x] Add Python parity tests for `api.metrics` and equivalent no-flow Portfolio v3 ledger metrics.
- [x] Add JavaScript parity test for Exhaustive exact metrics using the same fixture.
- [x] Add the JavaScript parity test to existing CI scripts.
- [x] Freeze shared definitions for arithmetic return, 252-day annualization, daily RF conversion, sample volatility, arithmetic Sharpe, lower-partial-moment Sortino, beta, Jensen alpha, and MDD.
- [x] Record Portfolio v3 historical daily VaR/CVaR semantics.
- [x] Record intentional context differences instead of forcing false parity.
- [x] Update this master roadmap.

### Important Phase 0 findings

1. **CAGR day-count difference exists and is intentionally not changed in PR #54**:
   - `api/metrics.py` and Exhaustive exact: `365.25` days/year.
   - Portfolio v3 ledger metrics: `365.2425` days/year.
   - Golden fixture records both results. Any later unification requires an explicit versioned migration.
2. `api.metrics` with a benchmark intentionally computes its simple-value metrics on common price dates; Portfolio v3 computes standalone ledger performance independently and aligns the benchmark only for relative metrics. Parity is required only when calendars/contexts are actually equivalent.
3. Legacy `api/scan.py` uses older CAGR-based Sharpe/Sortino/alpha semantics; production `/api/scan` routes to `api/scan_v2.py`, whose shared service uses `api.metrics`.
4. Exhaustive backend prepares a signed TWD price snapshot; exact combination metrics are calculated in the browser engine.
5. Optimizer proxy MDD and related proxy quantities are approximations for search acceleration and must never be promoted to exact performance metrics.

### Explicit non-goals

- No production metric formula changes.
- No Portfolio Refinery API/UI.
- No ResearchDataset implementation.
- No covariance/clustering implementation.
- No optimizer behavior change.

### Validation state

- [x] Python compile/lint reached PASS in initial PR #54 CI run.
- [x] New Python parity tests reached PASS in initial PR #54 CI run.
- [x] New Node/Exhaustive parity test reached PASS in initial PR #54 CI run.
- [x] Existing Worker/score tests reached PASS in initial PR #54 CI run.
- [x] Portfolio web CI: PASS on initial PR #54 head.
- [ ] Full CI final head: pending after this roadmap update.
- [ ] Vercel required check: pending final head.
- [ ] Pre-merge release backup: verify final PR base/head state.
- [ ] Independent diff review.
- [ ] Squash merge with expected head.
- [ ] Post-merge backup verification.
- [ ] Phase 0 doc-only closeout PR.

### Exit gate

- [x] Metric authority boundaries documented.
- [x] Shared-vs-context-specific definitions frozen.
- [x] Golden parity fixtures implemented.
- [x] Known differences explicitly documented rather than silently normalized.
- [ ] Final-head required checks pass.
- [ ] Independent review passes.
- [ ] PR #54 merged and post-backup verified.
- [ ] Closeout record merged; then Phase 0 becomes `CLOSED / PASS`.

---

## Phase 1 — ResearchDataset

**Status: PLANNED / BLOCKED UNTIL PHASE 0 CLOSEOUT**

### Objective
Create one reproducible research dataset contract consumed by future Refinery and, only after parity, Exhaustive research paths.

### Planned work

- [ ] Define/version `ResearchDatasetV1`.
- [ ] Preserve requested symbol order and explicit per-symbol failures.
- [ ] Store requested/effective date ranges.
- [ ] Store TWD levels/daily returns.
- [ ] Store native and FX return components where available.
- [ ] Separate scanner coverage from matrix coverage/effective observations.
- [ ] Carry corporate-action and FX audit metadata.
- [ ] Carry source/methodology versions and per-series fingerprints.
- [ ] Add deterministic dataset hash.
- [ ] Define synchronized weekly TWD research returns for structural cross-market analysis.
- [ ] Build golden parity against current Exhaustive snapshot/data preparation.
- [ ] Do not switch Exhaustive production consumption until parity passes.
- [ ] Define optional exportable research snapshot for durable reproducibility.

Exit gate:

- [ ] Contract versioned.
- [ ] Same input yields deterministic hash.
- [ ] Exhaustive preparation parity passes.
- [ ] No silent membership/date mutation.

---

## Phase 2 — Risk Mathematics Core

**Status: PLANNED**

### Objective
Implement validated pure quantitative primitives for portfolio structure analysis.

Planned work:

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
- [ ] Tactical daily, medium daily, structural synchronized-weekly correlations.
- [ ] Downside/stress correlation with minimum-observation and uncertainty guards.
- [ ] Golden numerical fixtures, mathematical invariants, metamorphic tests.

Required invariants include covariance symmetry, non-negative variance within tolerance, `sum(RC)=portfolio volatility`, permutation invariance, no fake diversification from duplicate assets, and preserved negative hedge RC.

Exit gate: reference parity + invariants pass; no API/UI yet.

---

## Phase 3 — Read-only Refinery API

**Status: PLANNED**

- [ ] Separate Refinery/research namespace; do not overload Portfolio v3 ledger contract.
- [ ] `preflight` and `analyze` only.
- [ ] Approved candidate-pool boundary target: up to 100 symbols.
- [ ] Strict request/history/computation/rate/response-size guards.
- [ ] Explicit per-symbol failures; no silent membership changes.
- [ ] Return structure/risk diagnosis, covariance diagnostics, effective dimensions, data quality, reproducibility.
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
- [ ] Effective holdings/risk dimensions.
- [ ] Diversification Ratio.
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

- [ ] Remove-One.
- [ ] Add-One.
- [ ] Replace-One.
- [ ] Every experiment must state funding policy: pro-rata survivors / cash / cluster champion / selected replacement.
- [ ] Recompute volatility, CVaR diagnostics, DR, effective counts/ranks, risk/cluster concentration.
- [ ] Clear before/after decomposition.
- [ ] Historical diagnostic semantics only; no implied future alpha.

---

## Phase 7 — Research Validity / Walk-Forward

**Status: PLANNED**

- [ ] Trial registry for every model/policy configuration.
- [ ] Fixed-candidate-universe anchored walk-forward V1.
- [ ] Training-only refinement/selection.
- [ ] Never-seen forward evaluation windows.
- [ ] Turnover and transaction-cost accounting.
- [ ] OOS original-vs-refined comparison.
- [ ] Track trial count/selection breadth.
- [ ] Probabilistic/Deflated Sharpe where appropriate.
- [ ] PBO/CSCV only if search grid is large enough to justify it.
- [ ] Explicit fixed-universe survivorship limitation.

Non-goal: no point-in-time Universe claim before Phase 11.

---

## Phase 8 — Selection Policy

**Status: PLANNED**

- [ ] Cluster tournament policy.
- [ ] Greedy selection with marginal utility recomputed after each addition.
- [ ] Pairwise swap search.
- [ ] Replacement hurdle/hysteresis.
- [ ] Stop on diminishing marginal benefit, not hard-coded holding count.
- [ ] N-vs-efficiency curve.
- [ ] OOS selection-frequency/stability reporting.
- [ ] Only after validation expose KEEP / TRIM / REPLACE semantics.
- [ ] Historical price-derived alpha remains labelled historical proxy unless forward data are valid.

---

## Phase 9 — Sizing Engine

**Status: PLANNED**

Compare under the same OOS framework:

- [ ] Equal weight.
- [ ] Inverse volatility.
- [ ] Equal Risk Contribution.
- [ ] HRP benchmark.
- [ ] Ledoit-Wolf minimum variance.
- [ ] Constrained risk budget.
- [ ] User-visible capital/risk/cluster constraints.
- [ ] Deterministic optimizer/multi-start policy and safe fallback.
- [ ] OOS CAGR, vol, Sharpe, Sortino, MDD, Calmar, CVaR, turnover, DR and effective-rank comparison.

No method, including HRP, is the default winner before evidence.

---

## Phase 10 — Validated Exhaustive Integration

**Status: PLANNED**

- [ ] Training window only: ResearchDataset -> Refinery -> candidate reduction -> Exhaustive search.
- [ ] Freeze selected portfolio/policy before OOS evaluation.
- [ ] Never present full-period Refinery + Exhaustive winner as forward evidence.
- [ ] Track trial/combination counts for multiple-testing diagnostics.
- [ ] Benchmark against simpler non-exhaustive policies.
- [ ] Mechanically enforce training/OOS separation for candidate preparation, tuning and evaluation.

---

## Phase 11 — Point-in-Time Universe / Alpha / Economic Factors

**Status: PLANNED**

- [ ] Point-in-time Universe membership with effective dates.
- [ ] Historical delisting/membership handling as data permit.
- [ ] Point-in-time fundamentals.
- [ ] Point-in-time analyst/revision data only from valid/licensed source.
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
| Quant golden fixtures | Required from Phase 0 onward where applicable |
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

- Governance and architecture hardening completed.
- Squash merge: `9135bdd33a46afee4f4a12b9030ca4504114924f`.
- CI/Vercel PASS; pre/post backups verified.
- `main-protection` later activated and API-verified.

## 2026-08-09 — Persistent roadmap / PR #53

- Added root persistent execution/handoff index.
- Squash merge: `bc8ce721a82938c32ed8b9af7c91fba25a161f8a`.
- CI/Vercel PASS; pre/post backups verified.

## 2026-08-09 — Phase 0 / PR #54

- Inventory identified five semantic classes: production simple-value, Portfolio ledger, Exhaustive exact, legacy compatibility, optimizer proxy.
- Added three authority/semantics/risk-policy docs.
- Added one shared cross-language golden fixture.
- Added Python simple-value/Portfolio parity tests and JS Exhaustive exact parity test.
- Preserved the existing 365.25 vs 365.2425 CAGR difference as an explicit versioned finding rather than silently modifying production.
- Initial PR head reached PASS for Python tests, Node/Worker tests, score tests, and Portfolio web CI; final-head full CI/Vercel still required after this roadmap commit.
- PR #54 remains `VALIDATING`; no Phase 1 work has started.

# 8. Exact resume point

Current AI / next AI must:

1. Stay on **Phase 0 only**.
2. Wait for PR #54 final-head `validate` and `Vercel` checks.
3. Verify the PR #54 pre-merge backup points to the current protected `main` base.
4. Independently inspect the final diff; reject any production-formula/API/UI/covariance/clustering change.
5. If clean, mark ready and squash merge with expected head SHA.
6. Verify the PR #54 post-merge backup points to the merge SHA.
7. Open a **doc-only Phase 0 closeout PR** updating this file with final merge SHA, post-backup tag, review/CI evidence, known limitations, `Phase 0 CLOSED / PASS`, and `Phase 1` as the next resume point.
8. Only after that closeout PR merges may Phase 1 — ResearchDataset begin.
9. Do **not** start covariance, Refinery API/UI, clustering, selection, sizing, or Exhaustive integration early.
