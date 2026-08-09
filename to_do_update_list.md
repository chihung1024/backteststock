# BacktestStock Development Master Plan

> Persistent execution/handoff index for `chihung1024/backteststock` and the Portfolio Refinery program. A phase/batch is not complete until this file records its status, evidence, limitations, and exact resume point.

## 1. Current baseline

- Protected production branch: `main`
- Phase 4 implementation PR: `#63` — `feat: add read-only Portfolio Refinery diagnostic UI`
- Phase 4 final implementation head: `4439e4e721f8c93cc77161affbd5f24554de516f`
- Phase 4 implementation merge: `e59c1402011c7e8c940f806e79c9ce4b0da3f47f`
- Phase 4 pre backup: `backup-pre-pr63-17f0dd88aeae`
- Phase 4 post backup: `backup-post-pr63-e59c1402011c`
- Current phase state: **Phase 4 — PASS; becomes CLOSED when this doc-only closeout merges**
- Next implementation phase: **Phase 5 — Clustering & Redundancy**
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
- `apps/portfolio-web/` — Portfolio v3 plus a separate Phase 4 Refinery diagnostic workspace; Portfolio and Refinery persistence/API contracts remain isolated.
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
- `docs/research/REFINERY_UI_V1.md`

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

**Status: CLOSED / PASS**

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
- [x] Closeout PR `#62` merged as `17f0dd88aeaeff61f84ac6598c7b6258135d4ca4`; Phase 3 is `CLOSED / PASS`.

---

## Phase 4 — Refinery Diagnostic UI

**Status: PASS; CLOSED when this closeout PR merges**

### Objective
Add a separate deterministic read-only Refinery workspace that consumes Phase 3 diagnostics without changing Portfolio v3 behavior or introducing clustering, redundancy verdict, selection, sizing, optimization or OOS recommendation semantics.

### Completed implementation — PR #63

- [x] Added explicit workspace switch between Portfolio backtest and `持股精煉診斷` without iframe/modal shell.
- [x] Added separate `RefineryWorkspaceModel` and persistence key `backteststock.refinery.workspace.v1`; existing Portfolio persisted model remains separate.
- [x] Shared Portfolio model/handoff links force Portfolio mode so Scanner/Portfolio handoff behavior is unchanged.
- [x] Added same-origin Refinery client isolated to `/api/v1/refinery/preflight` and `/api/v1/refinery/analyze`; Portfolio API client remains `/api/v3/portfolio/*` only.
- [x] Candidate editor supports 2–100 normalized symbols, optional benchmark, optional explicit capital weights, date window and existing Phase 3 EWMA/stress settings.
- [x] No hidden equal-weight portfolio is fabricated when weights are absent; portfolio risk is explicitly unavailable instead.
- [x] Preflight is mandatory before analysis and preserves `ready` / `incomplete` / `insufficient_data` fail-closed semantics.
- [x] Added data/reproducibility evidence, effective observations, structure/effective-dimension summary, Diversification Ratio and covariance stability/estimator-dispersion diagnostics.
- [x] Added capital weight vs signed component risk contribution only when explicit weights exist; negative risk contribution remains signed rather than being silently converted to positive risk.
- [x] Added tactical 63D, medium 252D, structural 156W, downside and stress correlation views; unavailable benchmark-conditioned views stay explicitly unavailable.
- [x] Full matrix rendering is limited to <=20 assets; >20 assets render deterministic top-30 absolute-correlation pairs as presentation only, never as a redundancy verdict.
- [x] Added responsive/mobile behavior with a 390px no-page-overflow browser gate.
- [x] Loaded `refinery.css` into the Vite graph after existing Portfolio styles and scoped shared utility selectors under `.refinery-workspace` to prevent cascade into existing Portfolio UI.
- [x] Added/strengthened focused Portfolio web CI path filters, Portfolio/Refinery source-contract tests and Phase 4 browser acceptance tests.
- [x] Committed deterministic Vite production assets; final focused gate verifies rebuild parity with `git diff --exit-code -- package-lock.json public/portfolio`.
- [x] Phase 5+ semantics remain absent: no clustering, redundancy verdict, KEEP/TRIM/REPLACE, marginal experiments, sizing, Exhaustive integration or OOS selection claim.

### Defects found by independent review and root-caused

1. **Stale production bundle** — Phase 4 TypeScript source compiled, but committed `public/portfolio` initially lagged the source. The fix was a deterministic locked-dependency Vite rebuild with generated-path allowlist and race guard; no minified asset was hand-edited.
2. **Ambiguous Playwright labels** — desktop labels such as `Refinery 持股 1 代碼` also substring-matched the mobile label. E2E selectors were corrected with exact accessible-name matching; production UI was not distorted to satisfy a bad selector.
3. **Acceptance-gate coverage gap** — formal browser evidence was missing for `incomplete`, `insufficient_data`, explicit-weight signed RC/DR, covariance diagnostics and all five correlation views. A dedicated Phase 4 contract E2E suite was added.
4. **Focused CI omission** — Refinery E2E and source-contract files were not initially included in the focused Portfolio web workflow. Path filters and the source-contract command were extended so future Refinery-only changes cannot bypass the focused gate.
5. **Orphan stylesheet** — `refinery.css` existed but was not in the Vite import graph. It is now imported from `main.tsx` after `styles.css`.
6. **Contract-test substring false positives** — broad regexes incorrectly matched legal identifiers such as `RefineryWorkspaceModel` and `RefineryPreflightResponse`. Tests now guard exact import boundaries/whole legacy identifiers.
7. **CSS cascade leakage after enabling the stylesheet** — generic names such as `.toggle-row` and `.weight-total` could override existing Portfolio classes because Refinery CSS loads later. Shared Refinery utilities are now scoped beneath `.refinery-workspace`, with a source-contract invariant preventing regression.

### Final Phase 4 evidence

- Implementation PR: `#63`.
- Base SHA: `17f0dd88aeaeff61f84ac6598c7b6258135d4ca4`.
- Final implementation head: `4439e4e721f8c93cc77161affbd5f24554de516f`.
- Squash merge: `e59c1402011c7e8c940f806e79c9ce4b0da3f47f`.
- Final PR-head CI run `31309682808`: PASS — Python **216/216**, Worker **47/47**, score **12/12**, Playwright **39/39**, Vercel config, D1 local migrations and Cloudflare dry-run all PASS.
- Final PR-head Portfolio web CI run `31309682811`: PASS, including TypeScript/Vite build, Portfolio + Refinery source contracts and deterministic committed-asset parity.
- Final PR-head Vercel required context: PASS.
- Final Release Backup Gate on the final PR head: PASS.
- Independent final audit: PASS, COMMENT review `4891193075`, with no remaining blocking finding.
- Exact-head squash merge performed with expected head `4439e4e721f8c93cc77161affbd5f24554de516f`.
- Merge-after-push main CI run `31309999532`: PASS.
- Merge-after-push Portfolio web CI run `31309999527`: PASS.
- Production Vercel status for merge SHA: PASS.
- Production Cloudflare Worker deploy run `31309999511`: PASS, including D1 migrations, Worker/static assets, Russell 2000 smoke and Portfolio v3 smoke.
- Pre backup: `backup-pre-pr63-17f0dd88aeae` -> `17f0dd88aeaeff61f84ac6598c7b6258135d4ca4`.
- Post backup: `backup-post-pr63-e59c1402011c` -> `e59c1402011c7e8c940f806e79c9ce4b0da3f47f`.
- Temporary deterministic-build helpers are not part of the final implementation diff.

### Known limitations carried forward

1. Phase 4 is diagnosis-only. It does not classify redundancy or tell the user to KEEP/TRIM/REPLACE any holding.
2. Downside/stress correlation still depends on a usable benchmark; missing/failed benchmark remains explicit unavailable evidence rather than a fabricated zero or fallback.
3. The >20-asset top-pair summary is a rendering/performance policy only, not a clustering or redundancy methodology.
4. Phase 3 backend rate limiting remains best-effort/in-process rather than a globally distributed quota.
5. No factor-implied relationship engine, economic-theme evidence, cluster stability, marginal experiment, sizing or OOS validation exists yet.
6. No Scanner -> Refinery conversion/handoff is introduced; Portfolio handoff remains the existing contract.
7. Historical correlation/effective-rank diagnostics are descriptive evidence and must not be promoted into future-performance claims in Phase 5.

### Exit gate

- [x] Separate Refinery workspace/model/storage implemented without overloading Portfolio v3 state.
- [x] Existing Portfolio and shared handoff behavior preserved/tested.
- [x] Preflight/analyze UI semantics preserve Phase 3 fail-closed behavior.
- [x] Explicit-weight signed RC and no-weight unavailable behavior tested.
- [x] Covariance/effective-dimension/correlation diagnostics rendered and tested.
- [x] Large-matrix and 390px responsive gates PASS.
- [x] Focused source-contract/E2E gates protect workspace/API/CSS isolation.
- [x] Final PR-head CI, Portfolio web CI, Vercel and Release Backup Gates PASS.
- [x] Independent final audit PASS.
- [x] PR #63 exact-head squash merge.
- [x] Post-merge backup verified.
- [x] Merge-after-push main CI PASS.
- [x] Production Vercel and Cloudflare deployment/smoke PASS.
- [ ] This doc-only closeout must merge; then Phase 4 is `CLOSED / PASS`.

---

## Phase 5 — Clustering & Redundancy

**Status: NEXT / NOT STARTED — begin only after this Phase 4 closeout merges**

### Objective
Add deterministic, traceable clustering and multi-evidence redundancy diagnosis on top of the existing ResearchDataset/Risk Mathematics/Refinery contracts, without crossing into marginal experiments, selection, sizing or future-performance recommendations.

### First actions

- [ ] Query latest protected `main` after this closeout; do not assume `e59c1402...` remains HEAD because closeout adds a documentation commit.
- [ ] Confirm no unfinished Phase 4 implementation/closeout PR remains.
- [ ] Read `AI_PROJECT_PLAYBOOK.md`, this roadmap, `REFINERY_API_V1.md`, `REFINERY_UI_V1.md`, ResearchDataset and Risk Mathematics contracts before designing Phase 5.
- [ ] Freeze a Phase 5 clustering/redundancy methodology contract before runtime implementation; do not implement from UI intuition or a magic aggregate score.
- [ ] Decide the canonical backend/pure-quant boundary for clustering and factor-implied relationship calculations before adding UI controls; browser code should render evidence, not become a second quantitative authority.
- [ ] Preserve the Phase 4 UI/API fail-closed and workspace-isolation contracts.
- [ ] Keep redundancy output descriptive as HIGH / MEDIUM / LOW / UNCERTAIN evidence; no KEEP/TRIM/REPLACE until the later validated selection phase.

### Planned work

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

## 2026-08-09 — Phase 3 / PR #61 + closeout #62

- Defined read-only Refinery V1 contract before implementation and added dedicated API/edge boundary.
- Initial CI `31301415964` found one real partial-evidence indexing defect; fixed resolved-evidence accounting without silently reducing candidate membership.
- Added explicit weight-normalization traceability and upstream error sanitization.
- Final head `4899199a50d01189904ef0842c5d5247afc4d09d` passed `validate`, Portfolio web CI, Vercel and Release Backup Gates.
- Independent final review PASS via COMMENT `4890806477`.
- Expected-head squash merge `6e18726dcc1383e0b839e4bd0bded46e720e2707`.
- Pre/post backups verified: `backup-pre-pr61-4cea3b18fdce`, `backup-post-pr61-6e18726dcc13`.
- Merge-after-push `main` CI PASS; production Vercel and Cloudflare deploy/smokes PASS.
- Closeout PR `#62` merged `17f0dd88aeaeff61f84ac6598c7b6258135d4ca4`; Phase 3 CLOSED / PASS.

## 2026-08-09 — Phase 4 / PR #63 + closeout #64

- Added isolated read-only Refinery diagnostic workspace and deterministic browser/source-contract gates.
- Independent review root-caused stale generated assets, missing stylesheet import, CSS cascade leakage, ambiguous E2E selectors and incomplete focused-test coverage before merge.
- Final head `4439e4e721f8c93cc77161affbd5f24554de516f` passed full CI, focused Portfolio web CI, Vercel and Release Backup Gates; Playwright 39/39.
- Independent final audit PASS via COMMENT `4891193075`.
- Expected-head squash merge `e59c1402011c7e8c940f806e79c9ce4b0da3f47f`.
- Pre/post backups verified: `backup-pre-pr63-17f0dd88aeae`, `backup-post-pr63-e59c1402011c`.
- Merge-after-push main CI and Portfolio web CI PASS; production Vercel and Cloudflare deploy/smokes PASS.
- This doc-only closeout transitions Phase 4 to CLOSED / PASS when merged.

# 8. Exact resume point

After this doc-only Phase 4 closeout merges:

1. Query latest protected `main`; do not assume `e59c1402...` is still HEAD because this closeout itself adds a documentation commit.
2. Confirm no open unfinished Phase 4 implementation/closeout PR remains.
3. Begin **Phase 5 — Clustering & Redundancy only**.
4. Read `AI_PROJECT_PLAYBOOK.md`, this roadmap, `docs/research/REFINERY_API_V1.md`, `docs/research/REFINERY_UI_V1.md`, `docs/research/RESEARCH_DATASET_V1.md`, `docs/quant/RISK_MATHEMATICS_V1.md`, current Refinery backend/API/UI contracts and tests.
5. Freeze a Phase 5 methodology/contract before runtime implementation. Correlation-distance, linkage defaults/sensitivity, stability, confidence and verdict semantics must be explicit/versioned before code becomes authoritative.
6. Keep quantitative clustering/factor relationship calculations in the canonical backend/pure-quant authority; browser code renders evidence and state only.
7. Structural dependency evidence should prioritize synchronized weekly TWD returns, with tactical daily TWD views remaining distinct; do not collapse them into one universal correlation matrix.
8. Add average-linkage hierarchical clustering with complete-linkage sensitivity and multi-window/bootstrap stability; do not use Ward as the default on correlation distance.
9. Add traceable multi-evidence redundancy diagnosis (price/downside/stress/factor/theme/confidence) with HIGH / MEDIUM / LOW / UNCERTAIN only; no magic 0–100 score.
10. Treat U.S. factor models as secondary evidence outside appropriate U.S. equity contexts; prefer factor-implied covariance/correlation to raw beta-vector cosine when factor overlap is used.
11. Keep economic-theme evidence deterministic/traceable/read-only; do not inject ungoverned labels into optimization.
12. Do not add Leave-One-Out/Add-One/Replace-One, KEEP/TRIM/REPLACE, sizing, Exhaustive selection or OOS recommendation claims in Phase 5.
13. Preserve Phase 4 candidate completeness, benchmark isolation, explicit-unavailable semantics, workspace/API/storage isolation and responsive/performance guards.
14. Update this file in the Phase 5 implementation PR and complete the same doc-only closeout process before Phase 6.
