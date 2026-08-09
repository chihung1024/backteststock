# BacktestStock Development Master Plan

> This file is the persistent handoff index for the BacktestStock / Portfolio Refinery program. Every implementation PR must update this file before the phase or batch is considered complete.

## 1. Current baseline

- Repository: `chihung1024/backteststock`
- Current protected branch: `main`
- Baseline `main` SHA before this roadmap PR: `9135bdd33a46afee4f4a12b9030ca4504114924f`
- Last completed PR: `#52` — `chore: harden architecture governance before Portfolio Refinery`
- Last verified pre-merge backup: `backup-pre-pr52-a0c640783dc9`
- Last verified post-merge backup: `backup-post-pr52-9135bdd33a46`
- Current governance ruleset: `main-protection`
  - enforcement: `active`
  - target: default branch
  - bypass actors: none
  - branch deletion: blocked
  - force/non-fast-forward push: blocked
  - pull request required
  - allowed merge method: squash only
  - required checks: `validate` (GitHub Actions), `Vercel`
- Current program status: **Phase -1 CLOSED / PASS**
- Next program phase: **Phase 0 — Quant Authority Freeze**

## 2. Mandatory execution discipline

These rules apply to every phase below unless a phase explicitly states otherwise.

1. Work in the approved phase order. Do not start a later phase before the current phase exit gate passes.
2. Avoid unrelated refactors and feature expansion.
3. Runtime-changing or quantitative-methodology changes must be made on a branch and merged by pull request.
4. `main` must not be force-pushed or directly used for implementation work.
5. Use squash merge with expected-head verification where supported.
6. Use the generic `release-backup` gate for runtime-changing or quantitative-methodology PRs.
7. Preserve explicit contract/methodology versioning when externally observable semantics change.
8. No silent ticker deletion, date truncation, calendar substitution, or data-quality fallback.
9. Keep research/exploration outputs separate from out-of-sample validation claims.
10. Update this file in every implementation PR with:
    - work completed;
    - PR number;
    - merge SHA;
    - CI/result evidence;
    - release backup tags when applicable;
    - known limitations;
    - exact next resume point.
11. If a phase fails validation, keep the last valid production behavior and document the failure here before proceeding.
12. A future AI should read this file first, then the referenced ADRs/docs, before making any project change.

## 3. Architecture boundaries that must remain true

- `apps/api/app/data/` is the shared TWD market-data / FX / valuation authority.
- `apps/api/app/portfolio/` is the Portfolio v3 ledger and path-dependent portfolio-analysis authority.
- `api/portfolio_v3.py` is the self-owned FastAPI Portfolio v3 production entrypoint.
- Existing Flask routes remain compatibility surfaces until explicitly retired by a later approved phase.
- `api/exhaustive_optimizer.py` is a full-period historical research/search engine, not an out-of-sample validation engine.
- New Portfolio Refinery logic must not be added to legacy `api/index.py` or `api/optimizer.py`.
- Portfolio v3 keeps its strict production portfolio boundary; Refinery is a separate research/diagnostic domain.

Primary architecture references:

- `docs/PHASE_MINUS1_GOVERNANCE.md`
- `docs/adr/0001-runtime-and-quant-authority.md`
- `docs/UNIFIED_TWD_CONTRACT.md`
- `docs/METRICS_REPRODUCIBILITY.md`
- `docs/EXHAUSTIVE_OPTIMIZER_V3.md`

---

# 4. Roadmap

## Phase -1 — Governance & Architecture Hardening

**Status: CLOSED / PASS**

### Objective
Establish repository governance and one current architecture source of truth before new quantitative work.

### Completed work
- [x] Align root README with the deployed Cloudflare + Vercel Flask compatibility + FastAPI Portfolio v3 architecture.
- [x] Align `apps/api/README.md` with completed Portfolio v3 FastAPI cutover.
- [x] Align deployment runbook and production smoke description.
- [x] Add explicit runtime inventory and classification.
- [x] Add ADR 0001 for runtime and quantitative authority boundaries.
- [x] Retire superseded PR19 and PR38 one-off backup workflows.
- [x] Preserve the generic `.github/workflows/release-backups.yml` unchanged.
- [x] Create and activate repository ruleset `main-protection`.
- [x] Protect default branch from deletion and force/non-fast-forward push.
- [x] Require PRs and squash-only merge.
- [x] Require `validate` and `Vercel` status checks.
- [x] Confirm bypass list is empty.

### Validation / evidence
- PR: `#52`
- Merge SHA: `9135bdd33a46afee4f4a12b9030ca4504114924f`
- PR CI: passed
- Vercel preview: passed
- Pre backup: `backup-pre-pr52-a0c640783dc9`
- Post backup: `backup-post-pr52-9135bdd33a46`
- GitHub API: `main` reports protected; ruleset `main-protection` reports enforcement `active`.

### Known limitations
- Classic branch-protection API fields may not mirror repository ruleset internals; the repository ruleset itself is the governance source of truth.

### Exit gate
- [x] Governance protection active.
- [x] Architecture documentation matches production runtime.
- [x] No runtime/quantitative behavior change in Phase -1.

---

## Phase 0 — Quant Authority Freeze

**Status: NEXT / NOT STARTED**

### Objective
Prevent Scanner/legacy metrics, Portfolio v3 metrics, and future Refinery metrics from becoming three independent quantitative authorities.

### Planned work
- [ ] Inventory every current metric implementation and caller.
- [ ] Document canonical return semantics and calculation contexts.
- [ ] Define which quantities are genuinely shared primitives versus context-specific portfolio metrics.
- [ ] Add `docs/quant/METRIC_AUTHORITY.md`.
- [ ] Add `docs/quant/RETURN_SEMANTICS.md`.
- [ ] Add `docs/quant/RISK_MODEL_POLICY.md`.
- [ ] Build fixed synthetic parity fixtures covering CAGR, volatility, Sharpe, Sortino, beta, alpha, MDD, and historical tail risk where contexts are equivalent.
- [ ] Compare `api/metrics.py` and `apps/api/app/portfolio/metrics.py` under identical return-series assumptions.
- [ ] Record every intentional semantic difference; do not force parity across genuinely different contexts.
- [ ] Define the future canonical shared quantitative primitive layer under `apps/api/app/quant/` without prematurely migrating production callers.
- [ ] Add regression tests proving no production output changes in this phase unless an explicitly approved defect is found.
- [ ] Update this master plan with results and exact Phase 1 entry conditions.

### Explicit non-goals
- No Portfolio Refinery API/UI.
- No covariance or clustering implementation.
- No broad production metric refactor before parity is proven.
- No optimizer behavior changes.

### Exit gate
- [ ] Metric authority document accepted.
- [ ] Shared-vs-context-specific metric definitions frozen.
- [ ] Parity fixtures and tests pass.
- [ ] Any differences are explicitly documented and reviewed.
- [ ] Production behavior remains stable.

---

## Phase 1 — ResearchDataset

**Status: PLANNED**

### Objective
Create one reproducible research data object used by future Refinery and, after parity validation, Exhaustive research paths.

### Planned work
- [ ] Define `ResearchDatasetV1` contract.
- [ ] Include requested symbols and order.
- [ ] Include requested and effective date ranges.
- [ ] Include TWD price levels and daily TWD returns.
- [ ] Include native returns and FX returns where available.
- [ ] Include scanner/data coverage separately from matrix/effective observation coverage.
- [ ] Include per-symbol corporate-action and FX audit metadata.
- [ ] Include price/data fingerprints and methodology contract versions.
- [ ] Include dataset-level deterministic hash.
- [ ] Preserve explicit partial failures; never silently delete failed tickers.
- [ ] Define synchronized weekly research returns for structural cross-market analysis.
- [ ] Build parity tests against the current exhaustive snapshot/data-preparation path.
- [ ] Do not switch Exhaustive production consumption until parity passes.
- [ ] Define optional exportable research snapshot for reproducibility.

### Exit gate
- [ ] Dataset contract versioned.
- [ ] Same inputs produce deterministic hashes.
- [ ] Exhaustive preparation parity established on golden fixtures.
- [ ] No silent membership/date changes.

---

## Phase 2 — Risk Mathematics Core

**Status: PLANNED**

### Objective
Implement validated pure quantitative primitives for portfolio structure analysis.

### Planned work
- [ ] Covariance estimator interface.
- [ ] Sample covariance diagnostic estimator.
- [ ] Ledoit-Wolf shrinkage estimator with reference parity validation.
- [ ] EWMA covariance sensitivity estimator.
- [ ] Symmetry validation.
- [ ] PSD/eigenvalue validation.
- [ ] Condition-number / instability diagnostics.
- [ ] Effective observation counts.
- [ ] Estimator-dispersion diagnostics.
- [ ] Portfolio volatility.
- [ ] Marginal risk contribution (MRC).
- [ ] Signed component risk contribution (RC).
- [ ] Diversification Ratio.
- [ ] Weight-effective holdings `1/sum(w^2)`.
- [ ] Gross risk-contribution equivalent holdings using normalized `abs(RC)` with signed RC retained separately.
- [ ] Correlation effective rank.
- [ ] Covariance effective rank.
- [ ] Tactical daily correlation.
- [ ] Medium-horizon daily correlation.
- [ ] Structural synchronized weekly correlation.
- [ ] Downside/stress correlation with minimum-observation guardrails.
- [ ] Confidence/observation metadata.
- [ ] Mathematical invariant tests.
- [ ] Metamorphic tests.
- [ ] Golden numerical fixtures.

### Required invariants
- [ ] Covariance symmetric within tolerance.
- [ ] Portfolio variance non-negative within numerical tolerance.
- [ ] `sum(RC) == portfolio volatility` within tolerance.
- [ ] Asset-order permutation does not change portfolio-level results.
- [ ] Duplicate identical assets do not create artificial diversification.
- [ ] Valid hedge behavior is preserved; negative signed RC is not hidden.

### Exit gate
- [ ] Reference parity and invariants pass.
- [ ] Numerical edge cases documented.
- [ ] No API/UI yet.

---

## Phase 3 — Read-only Refinery API

**Status: PLANNED**

### Objective
Expose diagnosis-only Portfolio Refinery analysis without recommendation semantics.

### Planned work
- [ ] Create separate Refinery/research API namespace; do not overload Portfolio v3 ledger contract.
- [ ] `preflight` endpoint.
- [ ] `analyze` endpoint.
- [ ] Up to approved candidate-pool boundary (target design: 100 symbols).
- [ ] Strict request-size and history-period guards.
- [ ] Dedicated computation/rate guard.
- [ ] Explicit per-symbol failure reporting.
- [ ] No silent membership modification.
- [ ] Response: summary, capital/risk weights, diversification, correlations, covariance diagnostics, effective dimensions, data quality, reproducibility metadata.
- [ ] Fixed Worker allowlist routes.
- [ ] Performance/response-size tests.
- [ ] Security and abuse tests.

### Explicit non-goals
- No BUY/SELL/TRIM/REPLACE recommendations.
- No sizing.

### Exit gate
- [ ] API contract frozen and versioned.
- [ ] Full CI/security/performance gates pass.

---

## Phase 4 — Refinery Diagnostic UI

**Status: PLANNED**

### Objective
Add a dedicated read-only Portfolio Refinery workspace without overloading existing Portfolio result tabs.

### Planned work
- [ ] Separate `RefineryWorkspaceModel` from `PortfolioWorkspaceModel`.
- [ ] Separate persisted state/schema version.
- [ ] Add workspace switch: portfolio backtest vs holding refinement.
- [ ] Portfolio structure summary.
- [ ] Capital weight vs signed risk contribution.
- [ ] Effective-holdings diagnostics.
- [ ] Diversification Ratio.
- [ ] Tactical/structural/downside/stress correlation views.
- [ ] Data-confidence and effective-observation display.
- [ ] Covariance-estimator stability display.
- [ ] Large-matrix rendering/performance guard.

### Exit gate
- [ ] Read-only diagnosis is understandable and deterministic.
- [ ] Existing Portfolio UI behavior unchanged.

---

## Phase 5 — Clustering & Redundancy

**Status: PLANNED**

### Objective
Detect repeated risk exposures without collapsing the result into a single opaque score.

### Planned work
- [ ] Hierarchical clustering with correlation distance.
- [ ] Average linkage default.
- [ ] Complete-linkage sensitivity comparison.
- [ ] Multi-window cluster stability.
- [ ] Bootstrap same-cluster stability.
- [ ] Asset-level factor diagnostics where valid.
- [ ] Prefer factor-implied covariance/correlation over simple beta-vector cosine as the primary factor-overlap statistic.
- [ ] Treat U.S. Fama-French factors as secondary evidence outside U.S. equities.
- [ ] Add economic-theme overlay only as traceable read-only metadata in this phase.
- [ ] Redundancy evidence stack: price, downside, stress, factor, theme, confidence.
- [ ] Verdict classes: HIGH / MEDIUM / LOW / UNCERTAIN.
- [ ] Do not introduce a magic 0-100 redundancy score.

### Exit gate
- [ ] Cluster/redundancy results stable on controlled fixtures.
- [ ] Uncertainty is visible when samples are insufficient.

---

## Phase 6 — Marginal Experiments

**Status: PLANNED**

### Objective
Quantify portfolio changes caused by explicit remove/add/replace counterfactuals.

### Planned work
- [ ] Remove-One experiment.
- [ ] Add-One experiment.
- [ ] Replace-One experiment.
- [ ] Explicit funding policy for every experiment:
  - pro-rata survivors;
  - cash;
  - cluster champion;
  - selected replacement.
- [ ] Recompute volatility, CVaR diagnostics, DR, effective counts/ranks, risk concentration, and cluster exposure.
- [ ] Preserve historical/diagnostic semantics; do not imply future alpha.
- [ ] Add clear before/after decomposition.

### Exit gate
- [ ] Counterfactual funding assumptions are never implicit.
- [ ] Results reproduce from dataset + policy + version metadata.

---

## Phase 7 — Research Validity / Walk-Forward

**Status: PLANNED**

### Objective
Separate historical search from genuine out-of-sample evidence.

### Planned work
- [ ] Trial registry for every model/policy configuration tested.
- [ ] Fixed-candidate-universe anchored walk-forward V1.
- [ ] Training-only refinement/selection.
- [ ] Never-seen forward evaluation windows.
- [ ] Turnover and transaction-cost accounting.
- [ ] Compare original vs refined portfolios on OOS metrics.
- [ ] Track number of trials and selection breadth.
- [ ] Add Probabilistic/Deflated Sharpe diagnostics where appropriate.
- [ ] Evaluate PBO/CSCV only if the research grid becomes large enough to justify it.
- [ ] Clearly label fixed-universe survivorship limitation.

### Explicit non-goals
- No claim of point-in-time Universe validity before Phase 11 data exists.

### Exit gate
- [ ] Training and OOS boundaries are mechanically enforced.
- [ ] Research trial history is reproducible.

---

## Phase 8 — Selection Policy

**Status: PLANNED**

### Objective
Convert validated structural and marginal evidence into a stable selection policy.

### Planned work
- [ ] Define cluster tournament policy.
- [ ] Greedy selection with full marginal recomputation after each addition.
- [ ] Pairwise swap search.
- [ ] Replacement hurdle / hysteresis to reduce churn.
- [ ] Stop based on diminishing marginal benefit rather than a hard-coded optimal holding count.
- [ ] Generate N-vs-efficiency curve.
- [ ] Record selection frequency across OOS windows.
- [ ] Only after validation expose KEEP / TRIM / REPLACE semantics.
- [ ] Keep historical price-derived alpha explicitly labeled as historical proxy unless forward information is valid.

### Exit gate
- [ ] Selection policy improves or preserves predefined OOS objectives with acceptable turnover.
- [ ] No full-period search result is promoted directly to recommendation.

---

## Phase 9 — Sizing Engine

**Status: PLANNED**

### Objective
Compare robust allocation methods after constituent selection has been validated.

### Planned work
- [ ] Equal weight baseline.
- [ ] Inverse volatility.
- [ ] Equal Risk Contribution.
- [ ] HRP benchmark.
- [ ] Ledoit-Wolf minimum variance.
- [ ] Constrained risk budget.
- [ ] User-configurable capital/risk/cluster constraints.
- [ ] Deterministic optimizer settings/multi-start where needed.
- [ ] Safe fallback when numerical optimization fails.
- [ ] OOS comparison of CAGR, vol, Sharpe, Sortino, MDD, Calmar, CVaR, turnover, DR, effective ranks.
- [ ] Do not designate HRP or any optimizer as default winner before evidence.

### Exit gate
- [ ] Sizing recommendation is based on OOS evidence, not in-sample fit.

---

## Phase 10 — Validated Exhaustive Integration

**Status: PLANNED**

### Objective
Allow Refinery to reduce the search space before Exhaustive optimization without leaking future information.

### Planned work
- [ ] Training window: ResearchDataset -> Refinery -> candidate reduction -> Exhaustive search.
- [ ] Freeze selected portfolio/policy before OOS evaluation.
- [ ] Never run full-period Refinery + Exhaustive and present the winner as forward evidence.
- [ ] Track combination count/trial count for multiple-testing diagnostics.
- [ ] Benchmark refined/exhaustive pipeline against simpler non-exhaustive baselines.

### Exit gate
- [ ] Mechanically enforced training/OOS separation.
- [ ] No leakage through candidate preparation, tuning, or validation.

---

## Phase 11 — Point-in-Time Universe / Alpha / Economic Factors

**Status: PLANNED**

### Objective
Add genuinely historical constituent/fundamental information so the platform can test alpha-oriented selection without look-ahead or survivorship shortcuts.

### Planned work
- [ ] Point-in-time Universe membership with effective dates.
- [ ] Historical delisting/membership handling as data permits.
- [ ] Point-in-time fundamentals.
- [ ] Point-in-time analyst/revision data if a valid licensed source is available.
- [ ] Revenue/EPS/FCF/ROIC/balance-sheet/valuation dimensions.
- [ ] Traceable economic-factor taxonomy with source/effective date/confidence.
- [ ] Never allow current fundamentals to enter historical backtests.
- [ ] Re-run walk-forward validation with true time-valid information.

### Exit gate
- [ ] Data provenance and effective dates are sufficient to substantiate point-in-time claims.

---

# 5. Cross-phase validation matrix

Every applicable PR should report these categories explicitly.

| Validation | Requirement |
| --- | --- |
| Existing regression suite | Must pass |
| Python lint/compile/tests | Must pass when Python touched |
| Worker tests | Must pass when routing/proxy touched |
| Portfolio web type/build/source-contract tests | Must pass when Portfolio web touched |
| Browser E2E | Must pass for user-flow changes |
| Vercel config/preview | Must pass when deployment surface is affected |
| D1 migration validation | Must pass when D1 touched |
| Cloudflare dry-run | Must pass when Worker/static deployment touched |
| Quant golden fixtures | Required from Phase 0/2 as applicable |
| Mathematical invariants/metamorphic tests | Required from Phase 2 onward as applicable |
| OOS/walk-forward evidence | Required for recommendation claims from Phase 7 onward |
| Pre/post Release backup | Required for runtime/quant methodology PRs |
| Independent diff review | Required before merge |
| `to_do_update_list.md` update | Required before phase/batch completion |

# 6. Status vocabulary

Use only these status labels for phases/tasks where practical:

- `NOT STARTED`
- `IN PROGRESS`
- `BLOCKED`
- `VALIDATING`
- `PASS`
- `FAIL`
- `CLOSED`
- `DEFERRED`

Do not mark a phase `CLOSED` until its explicit exit gate has passed.

# 7. Execution log

## 2026-08-09 — Phase -1 completed

- Completed governance and architecture hardening in PR `#52`.
- Merged with squash to `main` SHA `9135bdd33a46afee4f4a12b9030ca4504114924f`.
- Full PR CI passed.
- Vercel preview passed.
- Pre/post Release backups verified.
- Repository ruleset `main-protection` created and activated after PR #52.
- GitHub API verified the ruleset targets the default branch, has no bypass actors, blocks deletion/non-fast-forward pushes, requires PRs, permits squash only, and requires `validate` + `Vercel` checks.
- Phase -1 status changed to `CLOSED / PASS`.
- Next implementation phase: Phase 0 — Quant Authority Freeze.

## 2026-08-09 — Persistent master roadmap requested

- Added requirement that every future implementation PR update this file with result evidence and the exact resume point.
- This roadmap PR is documentation/governance continuity only; it does not modify runtime or quantitative behavior.

# 8. Current resume point for the next AI

1. Read this file completely.
2. Read `docs/PHASE_MINUS1_GOVERNANCE.md` and `docs/adr/0001-runtime-and-quant-authority.md`.
3. Confirm the latest `main` SHA and that `main-protection` is still active.
4. Confirm there is no unfinished earlier-phase PR.
5. Start **Phase 0 — Quant Authority Freeze** only.
6. First Phase 0 action should be inventory/retrieval of existing metric implementations and their callers before changing code.
7. Do **not** begin ResearchDataset, covariance, Refinery API/UI, clustering, selection, sizing, or Exhaustive integration until the corresponding earlier exit gates pass.
8. Update this file in the Phase 0 PR before marking Phase 0 complete.
