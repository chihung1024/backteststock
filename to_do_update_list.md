# BacktestStock Development Master Plan

> Persistent execution/handoff index for `chihung1024/backteststock` and the Portfolio Refinery program. A phase/batch is not complete until this file records its status, evidence, limitations, and exact resume point.

## 1. Current baseline

- Protected production branch: `main`
- Phase 2 implementation PR: `#59` — `feat: add validated risk mathematics core`
- Phase 2 final implementation head: `9cd00609bcbdde210bdc024fa224016ca3dda6d3`
- Phase 2 implementation merge: `724075ddbb0383f7889e4b622a95a57769d5558c`
- Phase 2 pre backup: `backup-pre-pr59-666c561c0abf`
- Phase 2 post backup: `backup-post-pr59-724075ddbb03`
- Current phase state: **Phase 2 — PASS; becomes CLOSED when this doc-only closeout merges**
- Next implementation phase: **Phase 3 — Read-only Refinery API**
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

**Status: PASS; CLOSED when this closeout PR merges**

### Objective
Implement validated pure quantitative primitives for portfolio structure analysis. Phase 2 is a mathematics/test layer only; no Refinery API/UI, clustering, selection or sizing.

### Completed implementation — PR #59

- [x] Added framework-neutral `apps/api/app/quant/` package.
- [x] Added unbiased sample covariance (`ddof=1`) as diagnostic/reference estimator.
- [x] Added NumPy Ledoit-Wolf spherical-target shrinkage matching `sklearn.covariance.ledoit_wolf`, including centered, one-feature and `p > n` cases.
- [x] Added explicit caller-decay EWMA covariance sensitivity estimator.
- [x] Added covariance symmetry, PSD, eigenvalue, numerical-rank and condition-number diagnostics.
- [x] Added scale-normalized pairwise estimator-dispersion diagnostics.
- [x] Added portfolio variance/volatility, MRC, **signed** RC and Diversification Ratio.
- [x] Added weight-effective holdings and separate gross-RC equivalent holdings without hiding signed hedge RC.
- [x] Added entropy effective rank and participation ratio for correlation/covariance; neither is labelled as exact independent bets.
- [x] Added tactical 63D, medium 252D and structural 156W correlation primitives with explicit caller minimum-observation policies.
- [x] Added downside and benchmark-tail stress correlation with fail-closed insufficient-sample status.
- [x] Corrected conditional sample accounting so condition-ineligible rows are not mislabeled as dropped observations; incomplete eligible rows remain visible as drops.
- [x] Removed benchmark-column-name collision risk using an internal collision-proof alignment label.
- [x] Hardened covariance/risk tolerance calculations so they scale with matrix magnitude instead of an artificial `1.0` floor.
- [x] Added numerical golden, reference-parity, invariant and metamorphic tests.
- [x] Kept Scanner, Portfolio v3, Exhaustive, Worker, UI and all production consumers unchanged.
- [x] `requirements.txt` unchanged; `scikit-learn==1.9.0` is dev/test-only as a reference oracle.

### First CI failure — root cause and disposition

Initial head `bfcb771e69bf26397018bafef303d4279e46903f` failed only three newly added golden assertions while dependency install, pip consistency, compile and Ruff passed; Python result was **190 passed / 3 failed**.

Independent re-derivation showed the manually seeded `tests/fixtures/risk_math_v1.json` expected values were wrong. `sample_covariance()` matched `numpy.cov(..., ddof=1)`, and the NumPy Ledoit-Wolf implementation matched scikit-learn reference tests. Production mathematics was therefore **not modified to fit an incorrect fixture**.

Disposition:

- corrected the golden fixture to independently derived values;
- added a guard test that anchors the fixture itself directly to NumPy sample covariance and scikit-learn Ledoit-Wolf covariance/shrinkage;
- added small-scale covariance/risk tolerance metamorphic tests;
- added conditional-sample metadata and benchmark-name-collision tests.

Retained governance lesson: a committed golden fixture is not an authority until its provenance is independently validated.

### Final Phase 2 evidence

- Implementation PR: `#59`.
- Base SHA: `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`.
- Final implementation head: `9cd00609bcbdde210bdc024fa224016ca3dda6d3`.
- Squash merge: `724075ddbb0383f7889e4b622a95a57769d5558c`.
- Changed-file scope: 10 files only — pure `quant/` primitives, methodology doc, dev-only reference dependency, fixture/tests and this roadmap; no production consumer file changed.
- Final PR-head `validate` run `31300252676`: PASS, including Python/reference/invariant tests, JS/Worker/score tests, Playwright E2E, Vercel config, D1 local migration and Cloudflare dry-run.
- Final PR-head Vercel required context: PASS.
- Final Release Backup Gate: PASS.
- Independent final diff review: PASS and recorded on PR #59 as COMMENT review `4890745183`.
- GitHub platform limitation: the PR author cannot APPROVE their own PR (`422 Review Can not approve your own pull request`). No ruleset requires an approving external account, and no branch-protection requirement was bypassed; the review was therefore recorded as COMMENT rather than fabricating an approval.
- Merge-after-push `main` CI run `31300503126`: PASS.
- Pre backup: `backup-pre-pr59-666c561c0abf` -> `666c561c0abf9d40fcc037ee0ee5d6ea14f007a4`.
- Post backup: `backup-post-pr59-724075ddbb03` -> `724075ddbb0383f7889e4b622a95a57769d5558c`.

### Phase 2 known limitations carried forward

1. `apps/api/app/quant/` is intentionally not wired to a public Refinery API yet.
2. No existing Scanner/Portfolio/Exhaustive consumer migrated to the new risk primitives.
3. Correlation minimum-observation thresholds remain caller policy; Phase 2 does not pretend one universal statistical threshold exists.
4. EWMA decay remains explicit caller policy; no hidden universal decay constant exists.
5. Effective rank/participation ratio are structural diagnostics, not proof of an exact number of independent economic bets.
6. No clustering, factor overlap, marginal experiments, recommendation labels, sizing or OOS claim exists yet.
7. `scikit-learn` is intentionally dev/test-only; production NumPy implementation remains independently tested against it.

### Exit gate

- [x] Methodology contract/version frozen: `risk-math-twd-2026-08-09.1`.
- [x] Reference estimator parity passes.
- [x] Golden provenance independently anchored.
- [x] Mathematical invariants/metamorphic tests pass.
- [x] No API/UI or later-phase logic added.
- [x] Final `validate` PASS.
- [x] Final Vercel PASS.
- [x] Final scope review / independent diff review PASS.
- [x] PR #59 merged by exact expected-head squash.
- [x] Post-merge backup verified.
- [x] Merge-after-push `main` CI PASS.
- [ ] This doc-only closeout must merge; then Phase 2 is `CLOSED / PASS`.

---

## Phase 3 — Read-only Refinery API

**Status: NEXT / NOT STARTED — begin only after this Phase 2 closeout merges**

### Objective
Expose Phase 1 ResearchDataset + Phase 2 risk mathematics through a separate, deterministic, read-only Refinery research API without altering Portfolio v3 ledger semantics or exposing recommendation/sizing behavior.

### First actions

- [ ] Query latest protected `main` SHA after this closeout; do not assume `724075dd...` remains HEAD because this closeout adds a documentation commit.
- [ ] Confirm no unfinished Phase 2 implementation/closeout PR remains.
- [ ] Read `AI_PROJECT_PLAYBOOK.md`, this roadmap, `RESEARCH_DATASET_V1.md`, `RISK_MATHEMATICS_V1.md`, runtime/quant ADRs and current Worker/API security contracts.
- [ ] Inventory current FastAPI/Flask/Worker routing, CORS/allowlist, request/response-size, timeout/rate/computation guards and error-envelope conventions before writing endpoints.
- [ ] Define/version a separate Refinery API contract before implementation.

### Planned work

- [ ] Separate Refinery/research namespace; do not overload Portfolio v3 ledger contract.
- [ ] Read-only `preflight` and `analyze` endpoints only.
- [ ] Approved candidate-pool target: up to 100 requested symbols, subject to explicit resource guards.
- [ ] Explicit request/history/computation/rate/response-size limits.
- [ ] Preserve requested membership and explicit per-symbol failures; no silent ticker deletion.
- [ ] Surface ResearchDataset identity, effective dates, coverage/data-quality evidence and methodology versions.
- [ ] Surface Ledoit-Wolf/sample/EWMA covariance diagnostics, estimator dispersion, portfolio vol/MRC/signed RC/DR/effective counts/ranks and guarded multi-horizon/downside/stress correlation.
- [ ] Fixed Worker route allowlist and security tests.
- [ ] Deterministic serialization and performance tests.
- [ ] Update this roadmap and use the same implementation + doc-only closeout governance.

### Explicit non-goals

- No BUY/SELL/KEEP/TRIM/REPLACE semantics.
- No stock selection or sizing.
- No clustering/redundancy engine.
- No Leave-One-Out/Add-One/Replace-One.
- No Exhaustive integration.
- No OOS recommendation claim.
- No Portfolio v3 contract migration.

### Exit gate

- [ ] API contract/version frozen and documented.
- [ ] Preflight/analyze deterministic and fail-closed.
- [ ] Security/resource guards verified.
- [ ] Existing production regression suite PASS.
- [ ] Required CI/Vercel/review/pre-post backup PASS.
- [ ] Doc-only Phase 3 closeout merged.

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

## 2026-08-09 — Phase 2 / PR #59 + closeout

- Added pure Risk Mathematics V1 without production consumer integration.
- Initial CI exposed three incorrect golden expected values; independent NumPy/scikit-learn derivation proved the implementation correct and fixture wrong.
- Corrected/anchored the fixture instead of changing production mathematics to satisfy bad expectations.
- Added numerical-scale and conditional-sample hardening tests.
- Final implementation head `9cd00609bcbdde210bdc024fa224016ca3dda6d3` passed `validate`, Vercel and Release Backup Gates.
- Independent final diff review PASS; GitHub self-approval limitation documented via COMMENT review `4890745183`.
- Expected-head squash merge `724075ddbb0383f7889e4b622a95a57769d5558c`.
- Pre/post backups verified: `backup-pre-pr59-666c561c0abf`, `backup-post-pr59-724075ddbb03`.
- Merge-after-push `main` CI `31300503126` PASS.
- This doc-only closeout transitions Phase 2 to CLOSED / PASS when merged.

# 8. Exact resume point

After this doc-only Phase 2 closeout merges:

1. Query the latest protected `main` SHA; do not assume the Phase 2 implementation SHA is still HEAD because this closeout itself adds one documentation commit.
2. Confirm no open unfinished Phase 2 implementation/closeout PR remains.
3. Begin **Phase 3 — Read-only Refinery API only**.
4. First read `AI_PROJECT_PLAYBOOK.md`, this file, `docs/research/RESEARCH_DATASET_V1.md`, `docs/quant/RISK_MATHEMATICS_V1.md`, `docs/quant/RISK_MODEL_POLICY.md`, `docs/quant/METRIC_AUTHORITY.md`, `docs/quant/RETURN_SEMANTICS.md`, and runtime/Worker security documentation.
5. Inventory the current FastAPI/Flask/Worker routing and all request/response-size, timeout, rate, computation, CORS/allowlist and error-envelope guards before writing endpoints.
6. Define a separate versioned Refinery API contract and resource budget before implementation.
7. Implement read-only `preflight` and `analyze` over ResearchDataset + Risk Mathematics only. Preserve requested membership and explicit failures; no silent dropping.
8. Do not add UI, clustering, selection, sizing, recommendation labels, Exhaustive integration or OOS claims in Phase 3.
9. Update this file within the Phase 3 implementation PR, then complete the same doc-only closeout process before Phase 4.
