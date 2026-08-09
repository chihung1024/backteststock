# BacktestStock Development Master Plan

> Persistent execution/handoff index for `chihung1024/backteststock` and the Portfolio Refinery program. A phase/batch is not complete until this file records its status, evidence, limitations, and exact resume point.

## 1. Current baseline

- Protected production branch: `main`
- Phase 0 implementation merge SHA: `68cbd58d570ce7d806c2a73903b5bdb506c9bae1`
- Last completed implementation PR: `#54` — Quant Authority Freeze
- Last verified pre-merge backup: `backup-pre-pr54-bc8ce721a829`
- Last verified post-merge backup: `backup-post-pr54-68cbd58d570c`
- Governance ruleset: `main-protection`
  - enforcement: active
  - target: default branch
  - bypass list: empty
  - deletion: blocked
  - force/non-fast-forward pushes: blocked
  - PR required
  - squash only
  - required checks: `validate` (GitHub Actions) + `Vercel`
- Current phase state: **Phase 0 — CLOSED / PASS after this doc-only closeout merges**
- Next implementation phase: **Phase 1 — ResearchDataset**

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
    - final implementation merge SHA;
    - post-merge backup tag;
    - final CI/preview/review result;
    - known limitations;
    - phase status `CLOSED / PASS` or `FAIL`;
    - exact next resume point.
12. A phase is not `CLOSED` until that closeout record is merged. The closeout PR's own squash SHA does not require another recursive closeout; the next AI must query the current `main` SHA before starting work.
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
- `docs/quant/METRIC_AUTHORITY.md`
- `docs/quant/RETURN_SEMANTICS.md`
- `docs/quant/RISK_MODEL_POLICY.md`

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

**Status: CLOSED / PASS after this doc-only closeout merges**

### Objective
Prevent current Scanner/simple-value metrics, Portfolio v3 ledger metrics, Exhaustive exact metrics, legacy compatibility formulas, optimizer proxies, and future Refinery calculations from being confused as equivalent authorities.

### Completed work — PR #54

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

### Phase 0 findings retained as contract

1. **CAGR day-count difference remains intentionally unchanged**:
   - `api/metrics.py` and Exhaustive exact: `365.25` days/year.
   - Portfolio v3 ledger metrics: `365.2425` days/year.
   - Golden fixture records both. Any unification requires an explicit versioned migration.
2. `api.metrics` with a benchmark computes simple-value metrics on common price dates; Portfolio v3 computes standalone ledger performance independently and aligns the benchmark only for relative metrics. Parity is required only when calendars/contexts are actually equivalent.
3. Legacy `api/scan.py` uses older CAGR-based Sharpe/Sortino/alpha semantics; production `/api/scan` routes to `api/scan_v2.py`, whose shared service uses `api.metrics`.
4. Exhaustive backend prepares a signed TWD price snapshot; exact combination metrics are calculated in the browser exact engine.
5. Optimizer proxy MDD and related proxy quantities are approximations for search acceleration and must never be promoted to exact performance metrics.

### Final validation / evidence

- Implementation PR: `#54`
- Implementation merge SHA: `68cbd58d570ce7d806c2a73903b5bdb506c9bae1`
- Final-head SHA before merge: `c9e3f330e8b7be19817961bff24802f3c1c51895`
- Final-head `validate`: PASS, including Python compile/lint/tests, new Python parity tests, JavaScript/Worker tests including Exhaustive parity, score tests, Playwright E2E, Vercel-config validation, local D1 migrations and Cloudflare dry-run.
- Portfolio web CI: PASS.
- Vercel required check: PASS.
- Independent final diff review: PASS; changed scope restricted to quant docs, tests/fixture, test-script registration and this roadmap; no production formula/API/UI/risk/optimizer runtime modification.
- Pre backup: `backup-pre-pr54-bc8ce721a829` -> `bc8ce721a82938c32ed8b9af7c91fba25a161f8a`.
- Post backup: `backup-post-pr54-68cbd58d570c` -> `68cbd58d570ce7d806c2a73903b5bdb506c9bae1`.

### Known limitations carried forward

- The 365.25 vs 365.2425 CAGR year-length difference is documented but not normalized.
- Phase 0 defines the future `apps/api/app/quant/` boundary conceptually; production callers are intentionally not migrated yet.
- The shared golden fixture is a short synthetic formula/parity fixture, not an economic performance benchmark.
- Phase 0 does not create ResearchDataset, covariance, clustering, Refinery API/UI, selection or sizing functionality.

### Exit gate

- [x] Metric authority boundaries documented.
- [x] Shared-vs-context-specific definitions frozen.
- [x] Golden parity fixtures implemented and passing.
- [x] Known differences explicitly documented rather than silently normalized.
- [x] Final-head required checks passed.
- [x] Independent review passed.
- [x] PR #54 merged with expected-head squash.
- [x] Post-merge backup verified.
- [x] This doc-only closeout records final evidence; Phase 0 becomes `CLOSED / PASS` when it merges.

---

## Phase 1 — ResearchDataset

**Status: NEXT / NOT STARTED — begin only after this Phase 0 closeout merges**

### Objective
Create one reproducible research dataset contract consumed by future Refinery and, only after parity, Exhaustive research paths.

### Planned work

- [ ] Inventory current TWD history, calendar, return-component, coverage, fingerprint and Exhaustive snapshot-preparation code before writing the new contract.
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
- [ ] Update this master roadmap with Phase 1 implementation evidence and exact resume point.

Exit gate:

- [ ] Contract versioned.
- [ ] Same input yields deterministic hash.
- [ ] Exhaustive preparation parity passes on approved fixtures.
- [ ] No silent membership/date mutation.
- [ ] Existing production behavior remains stable until an explicitly validated migration.

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

## 2026-08-09 — Phase 0 implementation / PR #54

- Inventory identified five semantic classes: production simple-value, Portfolio ledger, Exhaustive exact, legacy compatibility, optimizer proxy.
- Added three authority/semantics/risk-policy docs.
- Added one shared cross-language synthetic golden fixture.
- Added Python simple-value/Portfolio parity tests and JavaScript Exhaustive exact parity test.
- Preserved the existing 365.25 vs 365.2425 CAGR difference as an explicit versioned finding rather than silently modifying production.
- Final-head required CI and Vercel checks passed.
- Independent final diff review passed.
- Squash merged to `68cbd58d570ce7d806c2a73903b5bdb506c9bae1`.
- Pre/post backups verified: `backup-pre-pr54-bc8ce721a829`, `backup-post-pr54-68cbd58d570c`.
- No production metric formula/API/UI/risk/optimizer runtime implementation was changed.

# 8. Exact resume point

After this doc-only closeout PR merges:

1. Query and record mentally the latest protected `main` SHA; do not assume the Phase 0 implementation SHA is still HEAD because the closeout itself adds one documentation commit.
2. Confirm no open earlier-phase implementation PR remains.
3. Begin **Phase 1 — ResearchDataset** only.
4. First Phase 1 action: inventory/retrieve the existing `TWDHistoryService`, TWD valuation/calendar/return-component helpers, coverage/fingerprint logic, and `api/exhaustive_optimizer.py` snapshot preparation before changing code.
5. Define `ResearchDatasetV1` contract and parity fixtures before migrating any production consumer.
6. Do not switch Exhaustive to the new dataset until parity passes.
7. Do not begin covariance, Refinery API/UI, clustering, selection, sizing or Exhaustive/Refinery integration early.
8. Update this file inside the Phase 1 implementation PR, then perform the same doc-only closeout after Phase 1 implementation merges.
