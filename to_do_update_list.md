# BacktestStock Development Master Plan

> Persistent execution/handoff index for `chihung1024/backteststock` and the Portfolio Refinery program. A phase/batch is not complete until this file records its status, evidence, limitations, and exact resume point.

## 1. Current baseline

- Protected production branch: `main`
- Phase 0 implementation merge: `68cbd58d570ce7d806c2a73903b5bdb506c9bae1`
- Phase 0 closeout merge: `d173f1d15a671e7d2f3c096a56e7ee3ef9f0a183`
- AI collaboration playbook PR `#56`: merge `863039af803671a8caf1d35074d038136ca2332a`; only `AI_PROJECT_PLAYBOOK.md`, no Phase 1 code conflict.
- Phase 1 implementation PR: `#57` — `feat: add reproducible ResearchDatasetV1`
- Phase 1 base: `863039af803671a8caf1d35074d038136ca2332a`
- Current phase: **Phase 1 — ResearchDataset**
- Current state: **VALIDATING — implementation frozen pending final-head gates**
- Next phase only after Phase 1 closeout: **Phase 2 — Risk Mathematics Core**
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
- `apps/api/app/research/` — additive research-domain data/services beginning with Phase 1; it must not become a second downloader.
- `api/portfolio_v3.py` — production FastAPI Portfolio v3 entrypoint.
- `api/index_v2.py`, `api/scan_v2.py`, `api/screener.py` — current compatibility/production entrypoints as documented.
- `api/exhaustive_optimizer.py` — full-period historical research/search snapshot path, not an OOS validation engine.
- `apps/portfolio-web/` — Portfolio v3 production web source.
- New Refinery logic must not be added to legacy `api/index.py` or `api/optimizer.py`.
- Portfolio v3 retains its strict production portfolio boundary; Refinery is a separate research/diagnostic domain.

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
- `docs/research/RESEARCH_DATASET_V1.md` (Phase 1 PR #57)

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

**Status: VALIDATING — PR #57; implementation frozen pending final-head gates**

### Objective
Create one reproducible framework-neutral research dataset contract over existing audited TWD histories, usable by future Refinery and eventually reusable by Exhaustive only after parity validation.

### Inventory completed

- [x] `TWDHistoryService` partial-success/failure semantics.
- [x] TWD native×FX valuation and no-backfill calendar policy.
- [x] TWD return-component decomposition/audits.
- [x] `align_twd_price_frame()` cross-market union-calendar semantics.
- [x] Exhaustive reference calendar, availability masks, 98% strict-coverage policy, audits/fingerprints and signed snapshot preparation.
- [x] Existing Exhaustive tests used as the current parity oracle.

### Work completed in PR #57

- [x] Add `apps/api/app/research/` package.
- [x] Define/version `ResearchDatasetV1` as `research-dataset-twd-2026-08-09.1`.
- [x] Add `ResearchDatasetService` that delegates fetching to existing `TWDHistoryService`; no second downloader.
- [x] Preserve normalized requested order, resolved order and explicit per-symbol `HistoryFailure` objects.
- [x] Enforce XOR outcome integrity: each requested symbol must have exactly one success or failure; neither-outcome and simultaneous success+failure states are rejected.
- [x] Enforce requested inclusive time-window isolation: native, FX and TWD source series outside `[start, end]` are rejected instead of silently leaking wider/future history into a dataset.
- [x] Store requested and effective date ranges separately.
- [x] Build reference calendar and Exhaustive-compatible first/last availability masks.
- [x] Report per-symbol coverage and `_global_complete_case`; the dataset reports evidence but does not enforce Exhaustive's 98% acceptance threshold.
- [x] Build aligned daily TWD levels with existing `align_twd_price_frame()` semantics for exact parity.
- [x] Build daily arithmetic return matrix excluding the synthetic opening row.
- [x] Build synchronized `W-FRI` structural weekly levels/returns using the **last actual observation date**, never a future Friday label.
- [x] Retain per-asset native and FX return series.
- [x] Retain corporate-action, FX and return-component audits plus quote-currency/native-scale metadata.
- [x] Retain native/FX/original-TWD/aligned-TWD level fingerprints.
- [x] Add canonical JSON export payload and deterministic SHA-256 dataset hash.
- [x] Harden canonical serialization: sorted mapping keys, deterministic set/frozenset serialization, NumPy bool/int/float normalization, non-finite numeric values -> JSON `null`.
- [x] Make export fail closed against stale identity: `export_payload()` recomputes the dataset hash and rejects mutated content that no longer matches the construction-time hash.
- [x] Add `docs/research/RESEARCH_DATASET_V1.md`, including explicit window-isolation, outcome-integrity and stale-hash export semantics.
- [x] Add tests for membership/failure visibility, coverage/date semantics, actual weekly dates, deterministic/data-sensitive hash, stale-hash mutation rejection, single history fetch, missing outcome rejection, conflicting outcome rejection, out-of-window history rejection and parity with current Exhaustive preparation.
- [x] Keep Scanner, Portfolio v3, Worker, UI and `api/exhaustive_optimizer.py` production consumers unchanged.
- [x] Update this roadmap.

### Phase 1 findings / decisions

1. `TWDHistoryService` remains the data-source authority; ResearchDataset is an alignment/audit/reproducibility layer, not a downloader.
2. Current Exhaustive preparation is a **parity oracle only** in Phase 1. No production consumer cutover occurs here.
3. A partial dataset is valid evidence with `is_complete == false`; a strict consumer must explicitly reject it rather than receive a silently reduced universe.
4. Requested membership is fail-closed: each requested symbol must resolve to exactly one of success/failure, never neither and never both.
5. ResearchDataset coverage is descriptive. Scanner coverage and Exhaustive's current 98% acceptance rule remain separate consumer policies.
6. Structural weekly dates preserve the last actual observed research date to avoid future-date labelling at mid-week cutoffs.
7. Daily alignment deliberately calls the existing `align_twd_price_frame()` to guarantee semantic parity. Extracting a more generic shared calendar primitive is deferred until a separately validated consumer migration requires it.
8. The pure builder independently rejects histories extending outside the requested window even though `ResearchDatasetService` already requests the exact window. This is a deliberate defense against future cached/walk-forward history reuse causing look-ahead leakage.
9. `ResearchDataset` keeps pandas/NumPy objects mutable for research ergonomics, but export revalidates the content hash and refuses a stale-hash snapshot. Consumers should rebuild after mutation rather than treat an altered object as the same dataset identity.
10. No covariance/correlation implementation is allowed in Phase 1.
11. PR #56 added `AI_PROJECT_PLAYBOOK.md` immediately before Phase 1; it changed no code and introduces no conflict. It is now a required handoff reference.

### Explicit non-goals

- No production Exhaustive migration.
- No covariance/correlation estimators.
- No clustering/redundancy.
- No Refinery API/UI.
- No selection/sizing.
- No OOS/walk-forward engine.
- No public ResearchDataset API or server persistence.

### Validation state

- [x] Earlier PR #57 heads passed Python compile/lint/tests, ResearchDataset/Exhaustive parity, Worker/Node, Playwright, D1 and Cloudflare validation before the last integrity hardening.
- [x] In-scope self-review fixed deterministic set serialization and invalid synthetic hash test construction.
- [x] Added explicit missing-outcome rejection + test.
- [x] Added explicit requested-window isolation + test; corrected the synthetic Exhaustive parity history so observations fall inside the requested interval.
- [x] Added conflicting success/failure rejection + test.
- [x] Added stale dataset-hash export rejection + mutation test.
- [x] Pre-merge backup verified: `backup-pre-pr57-863039af8036` -> `863039af803671a8caf1d35074d038136ca2332a`.
- [ ] Final-head `validate` after the final integrity/test/doc/roadmap commits: pending.
- [ ] Final-head Vercel required check: pending.
- [ ] Independent final diff review after required checks.
- [ ] Squash merge with expected final head.
- [ ] Verify post-merge backup.
- [ ] Doc-only Phase 1 closeout PR.

### Exit gate

- [x] Contract versioned.
- [x] Same valid inputs yield deterministic dataset hash; changed valid data changes the hash.
- [x] Current Exhaustive preparation parity implemented on approved in-window synthetic histories.
- [x] No silent membership/date mutation; membership ambiguity and out-of-window histories are rejected.
- [x] Stale-hash export is rejected after in-memory mutation.
- [x] Existing production consumers intentionally unchanged.
- [ ] Final-head required checks PASS.
- [ ] Independent review PASS.
- [ ] PR #57 merge/post-backup verified.
- [ ] Phase 1 closeout merged; only then Phase 1 is `CLOSED / PASS`.

---

## Phase 2 — Risk Mathematics Core

**Status: BLOCKED UNTIL PHASE 1 CLOSEOUT**

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
- [ ] Golden numerical fixtures, mathematical invariants and metamorphic tests.

Required invariants: covariance symmetry, non-negative variance within tolerance, `sum(RC)=portfolio volatility`, permutation invariance, no fake diversification from duplicate assets, preserved negative hedge RC.

Exit gate: reference parity + invariants pass; no API/UI yet.

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

- User-added `AI_PROJECT_PLAYBOOK.md` only; merge `863039af803671a8caf1d35074d038136ca2332a`.
- Read and adopted as repository-wide AI governance. No Phase 1 code conflict.

## 2026-08-09 — Phase 1 / PR #57

- Inventoried TWD history/valuation/return-component/calendar and Exhaustive preparation semantics.
- Added `ResearchDatasetV1`, service, contract docs, deterministic export/hash, daily/weekly/native/FX matrices and audits/fingerprints.
- Added parity/reproducibility/outcome tests plus explicit requested-window isolation to prevent wider-history look-ahead leakage.
- Final in-scope integrity review additionally made membership outcomes XOR/fail-closed and made export reject stale hashes after mutation.
- Implementation is now frozen; only final-head gates/review/merge/closeout remain.
- No production consumer migration and no Phase 2 risk mathematics started.

# 8. Exact resume point

Current AI / next AI must remain on **Phase 1 only** until closeout:

1. Obtain PR #57 final head after the latest integrity/test/doc/roadmap commits; do not add more functionality unless a required gate reveals an in-scope defect.
2. Verify changed files remain limited to `apps/api/app/research/*`, `docs/research/RESEARCH_DATASET_V1.md`, `tests/test_research_dataset.py`, and this roadmap. No Scanner/Portfolio/Exhaustive production consumer should change.
3. Pre-backup is already verified: `backup-pre-pr57-863039af8036` -> `863039af803671a8caf1d35074d038136ca2332a`.
4. Wait for final-head `validate` and `Vercel`; investigate failures only inside Phase 1.
5. Perform independent final diff review. Confirm XOR membership outcomes, requested-window isolation, deterministic/stale-hash export integrity, Exhaustive parity, and no covariance/API/UI/selection/sizing/production-migration change.
6. If clean, mark ready and squash merge with expected final head SHA.
7. Verify `backup-post-pr57-<mergeSHA12>` points to the implementation merge.
8. Create doc-only `docs/phase1-closeout` PR updating this file with final merge/check/review/backup evidence, known limitations and Phase 2 resume point.
9. Only after that closeout merges may **Phase 2 — Risk Mathematics Core** begin.
10. Phase 2 must start with pure risk-math dependency/method inventory and tests; do not start Refinery API/UI early.
