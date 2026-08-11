# Portfolio Refinery Diagnostic UI V1

Status: **Phase 4 workspace/persistence baseline with corrected Phase 5 additive read-only results extension. P5-CORR A–D response semantics are implementation-aligned.**

The Phase 4 contract froze workspace isolation, persistence, request editing and risk/correlation presentation. Phase 5 reuses that workspace and adds server-returned clustering/redundancy/factor/theme evidence panels. It does **not** change the persisted workspace schema, copy Portfolio state into Refinery, or make the browser a second quantitative authority.

## Contract identity

```text
REFINERY_UI_SCHEMA_VERSION       = refinery-ui-v1-2026-08-09.1
REFINERY_WORKSPACE_STORAGE_KEY   = backteststock.refinery.workspace.v1
ACTIVE_WORKSPACE_STORAGE_KEY     = backteststock.portfolio.active-workspace.v1
PORTFOLIO_MODEL_STORAGE_KEY      = backteststock.portfolio.model.v1
```

Phase 5 currently requires no Refinery workspace storage-version bump because no new persisted request fields are introduced. Additive analysis response types are API/methodology evolution, not a persistence-model migration.

## 1. Workspace boundary

`/portfolio/` contains two explicit workspaces:

```text
portfolio  = 投資組合回測
refinery   = 持股精煉診斷
```

The switch changes presentation/workflow only. It does not copy or mutate data between models.

Routing precedence remains:

1. `?handoff=...` opens Portfolio because Scanner handoff encodes Portfolio state.
2. `?model=...` opens Portfolio because it is the Portfolio share contract.
3. otherwise restore a valid saved active workspace when available;
4. invalid/missing active workspace falls back to `portfolio`.

Theme/locale may be shared preferences; Portfolio and Refinery research state remain separate.

## 2. Refinery workspace model

```ts
interface RefineryWorkspaceModel {
  schemaVersion: 1;
  symbols: RefineryAssetRow[];
  benchmark: string;
  startDate: string;
  endDate: string;
  useWeights: boolean;
  ewmaDecay: number;
  stressQuantile: number;
}

interface RefineryAssetRow {
  id: string;
  symbol: string;
  weightPercent: number | null;
}
```

Rules:

- 2–100 candidates after normalization/blank filtering;
- symbols unique after normalization;
- benchmark optional and visible; no implicit SPY;
- `useWeights=false` sends no weights and portfolio-specific risk stays unavailable;
- `useWeights=true` requires one positive weight per candidate and total 100% within API tolerance;
- UI shows raw total/normalization behavior but does not reimplement risk normalization;
- dates must be valid/ordered and comply with API maximum span/future-date guards;
- `ewmaDecay` / `stressQuantile` remain explicit advanced research parameters.

Phase 5 clustering uses these existing candidate/date/benchmark inputs and introduces no hidden browser-side clustering controls.

## 3. Persistence and migration

Refinery state persists independently at:

```text
backteststock.refinery.workspace.v1
```

Invalid stored state fails closed to a fresh default. Refinery persistence must not read/write `backteststock.portfolio.model.v1`.

Phase 5 does not add scanner→Refinery, Portfolio→Refinery copy, or cross-workspace migration.

## 4. API client boundary

Refinery client only uses same-origin:

```text
POST /api/v1/refinery/preflight
POST /api/v1/refinery/analyze
```

Portfolio client remains under:

```text
/api/v3/portfolio/*
```

No Refinery component may call a foreign API origin directly for candidate prices, factors, themes or other evidence. Those sources belong behind reviewed backend/research authorities.

Client errors preserve useful HTTP/request-id evidence but a failed request never becomes a valid zero metric.

## 5. Workflow

1. edit candidates/date/optional benchmark/optional weights/advanced API parameters;
2. run `preflight`;
3. inspect readiness, membership, failures, coverage/effective observations;
4. run `analyze` only after local validation and user action;
5. inspect Phase 3/4 risk diagnostics plus any available Phase 5 descriptive evidence.

Any model edit invalidates stale preflight/analyze results. Requests are abortable; newer requests supersede previous in-flight work.

The UI must honor server `incomplete`, `insufficient_data`, unavailable and error states rather than guessing a fallback.

## 6. Phase 3/4 diagnostic presentation baseline

### Structure summary

Display returned values only:

- requested/resolved counts;
- complete-case daily/weekly observations;
- covariance entropy effective rank / participation ratio;
- medium-correlation effective dimensions;
- Diversification Ratio only when explicit weights exist;
- Ledoit-Wolf shrinkage;
- estimator dispersion.

Effective rank is not renamed into an exact count of independent economic bets.

### Capital vs signed risk contribution

Only with explicit weights and valid portfolio risk:

- symbol;
- normalized capital weight used by API;
- signed component RC;
- signed RC share as presentation decomposition.

Negative hedge contribution remains negative and receives no recommendation label.

### Covariance stability

Display primary/sensitivity estimator diagnostics and dispersion without presenting estimator disagreement as an alpha signal.

### Data confidence / reproducibility

Display, as applicable:

- dataset hash prefix;
- methodology/schema versions;
- requested/resolved/failure evidence;
- effective range and observation counts;
- coverage;
- benchmark state/failure;
- explicit incomplete/insufficient/unavailable state.

### Correlation views

- tactical daily;
- medium daily;
- structural weekly;
- downside;
- stress.

Every view preserves server status/sample/condition/window/threshold semantics.

## 7. Phase 5 additive result panels

Phase 5 adds read-only result presentation inside the existing Refinery workspace.

### `群聚結構`

May display:

- clustering methodology version;
- average-linkage primary clusters;
- complete-linkage sensitivity evidence;
- flat display cut;
- 52/104/156-week availability/agreement;
- bootstrap requested/usable counts and cluster stability summaries;
- server-provided hierarchy/merge evidence where presentation permits.

The browser **must not** run SciPy-equivalent linkage, assign new cluster IDs or recompute a verdict.

### `重複曝險證據`

May display pair evidence including:

- HIGH / MEDIUM / LOW / UNCERTAIN historical redundancy verdict;
- separate evidence confidence;
- structural/medium/downside/stress correlations;
- average/complete cluster agreement;
- stability-window agreement;
- bootstrap co-cluster probability;
- factor/theme evidence/status where the server declares it usable.

Rules:

- HIGH is not colored/worded as an automatic sell instruction;
- no 0–100 aggregate score;
- unavailable is not converted to zero;
- sorting/filtering is presentation only and cannot change server verdict.

### `因子關係`

Display source/scope/sample, per-asset regression evidence, R-squared/betas where returned, and factor-implied systematic relationship where available.

The API explicitly separates `factor_computable`, `factor_model_scope` and `factor_corroboration_eligible`. The UI keeps computable betas/R²/systematic correlation visible as diagnostics while separately showing whether factor evidence may affect a redundancy verdict. Current Phase 5 eligibility is fail-closed without traceable instrument-scope authority; the browser must not infer applicability from ticker or USD denomination.

### `主題關係`

Display provenance only when the backend has a traceable source. Otherwise explicitly show unavailable status; do not ask the browser/LLM layer to invent themes from ticker names.

## 8. Large-result rendering guards

### Phase 4 correlation matrices

```text
MAX_FULL_CORRELATION_MATRIX_SYMBOLS = 20
MAX_CORRELATION_PAIR_ROWS           = 30
```

For >20 symbols, render a deterministic pair summary rather than all N×N cells. This remains a presentation/performance guard and not a redundancy engine.

### Phase 5 redundancy pairs

The API can represent up to `C(100,2) = 4,950` unordered pairs. The UI must not mount an unbounded table on desktop/mobile.

Presentation may use deterministic sorting, limiting, filtering or progressive display, provided:

- returned API evidence is not semantically truncated by the client;
- displayed subset is clearly labelled as presentation;
- summary counts/verdict totals remain tied to the full server evidence where provided;
- no hidden top-N becomes a de facto selection rule.

## 9. Responsive/accessibility behavior

- preserve minimum 320px support and tested 390px behavior;
- workspace switch remains keyboard accessible and active state identifiable;
- candidate editing stacks safely on mobile;
- fixed actions respect safe-area and do not cover content;
- tables/matrices/pair evidence use labelled scroll regions or bounded presentation;
- loading/cancel/error/incomplete/insufficient/unavailable states use text, not color alone;
- Phase 5 panels must not introduce page-level horizontal overflow.

## 10. Existing Portfolio behavior that must remain unchanged

- Portfolio default when no valid saved workspace exists;
- `?model=` share decoding;
- Scanner `?handoff=` import/return flow;
- `backteststock.portfolio.model.v1` persistence;
- Portfolio editor limits and ledger semantics;
- direct full-page/no-dialog/no-iframe behavior;
- Portfolio preflight/backtest/export;
- responsive Portfolio editor behavior;
- `/api/v3/portfolio` namespace.

Phase 5 Refinery code must remain unable to widen Portfolio request/response models into a generic mixed research bag.

## 11. Source-contract gates

The two-workspace boundary remains protected:

- Portfolio API module contains Portfolio v3 path and not Refinery path;
- Refinery API module contains Refinery path and not Portfolio v3 path;
- no direct foreign API origins;
- storage keys remain isolated;
- `?model=` / `?handoff=` force Portfolio;
- Scanner handoff writes Portfolio model only;
- Refinery does not import Portfolio ledger request/response types as generic research types;
- Phase 5 UI types reflect server evidence but contain no independent clustering/verdict formulas.

## 12. Browser/E2E gates

Required coverage across Phase 4 + Phase 5 includes:

1. existing Portfolio direct-page workflow;
2. workspace switch / independent persistence;
3. handoff/share forcing Portfolio;
4. Refinery preflight ready/incomplete/insufficient states;
5. no-weight unavailable portfolio risk;
6. explicit-weight signed RC/DR;
7. covariance/effective-dimension and five correlation views;
8. cluster/stability panel rendering;
9. average vs complete sensitivity evidence;
10. HIGH/MEDIUM/LOW/UNCERTAIN rendering without action labels;
11. factor computable/model-scope/verdict-eligibility presentation;
12. explicit unavailable theme state;
13. large candidate/pair rendering guard;
14. 390px Refinery no page-level horizontal overflow.

## 13. Historical Phase 4 baseline note

The original Phase 4 contract explicitly listed clustering, redundancy verdicts and factor/theme overlays as non-goals. That statement remains historically correct for the Phase 4 implementation/closeout. Phase 5 is an approved additive extension; the old non-goal is not evidence that the Phase 5 branch is violating the workspace contract.

The unchanged boundary is that the UI remains **diagnostic/read-only** and does not become a selection/sizing/OOS engine.

## 14. Explicit non-goals through Phase 5

- KEEP/TRIM/REPLACE or buy/sell recommendations;
- Remove-One/Add-One/Replace-One experiments;
- stock selection/action ranking;
- position sizing / HRP / ERC / minimum-variance optimization;
- Exhaustive candidate selection;
- OOS/walk-forward claims;
- point-in-time Universe/fundamental claims;
- browser-side clustering/redundancy/factor math;
- untraceable automatic theme classification;
- Scanner→Refinery or Portfolio→Refinery hidden conversion.
