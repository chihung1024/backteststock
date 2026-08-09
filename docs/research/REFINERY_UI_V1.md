# Portfolio Refinery Diagnostic UI V1

Status: Phase 4 contract. This UI consumes Phase 3 `refinery-v1` read-only diagnostics only. It does not classify redundancy, rank stocks, recommend actions, run marginal experiments, select holdings, size positions, optimize portfolios, integrate Exhaustive, or make OOS claims.

## Contract identity

```text
REFINERY_UI_SCHEMA_VERSION = refinery-ui-v1-2026-08-09.1
REFINERY_WORKSPACE_STORAGE_KEY = backteststock.refinery.workspace.v1
ACTIVE_WORKSPACE_STORAGE_KEY = backteststock.portfolio.active-workspace.v1
```

The existing Portfolio persistence contract remains unchanged:

```text
backteststock.portfolio.model.v1
```

The existing Portfolio model schema, scanner/main handoff, sharing query `?model=...`, import/export behavior, Portfolio v3 client and ledger semantics must not be widened into a generic union model.

## 1. Workspace boundary

The existing `/portfolio/` direct page gains one explicit workspace switch:

```text
portfolio  = 投資組合回測
refinery   = 持股精煉診斷
```

The switch selects presentation/workflow only. It does not copy or mutate data between the two workspace models.

Routing precedence:

1. `?handoff=...` always opens the Portfolio workspace because the existing scanner/main handoff writes the Portfolio model contract.
2. `?model=...` always opens the Portfolio workspace because it is the existing Portfolio share encoding.
3. Otherwise the last active workspace may be restored from `ACTIVE_WORKSPACE_STORAGE_KEY`.
4. Invalid/missing active-workspace values fall back to `portfolio`.

Theme and locale remain shared UI preferences. Portfolio and Refinery research state remain separate.

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

- 2–100 candidate rows after normalization/blank filtering;
- symbols must be unique after UI normalization;
- benchmark is optional and visible; no hidden SPY/default benchmark assumption;
- `useWeights=false` means the API receives no weights and portfolio-specific RC/DR remains unavailable;
- `useWeights=true` requires one positive weight for every candidate and total 100% within the Phase 3 ±0.05 percentage-point contract;
- accepted weights are still normalized by Phase 3 before Phase 2 math; UI must display the raw total and explain this behavior rather than reimplementing risk normalization;
- start/end must be valid and ordered; end may not be future; UI respects the API 15×366-day maximum span;
- `ewmaDecay` and `stressQuantile` are explicit advanced parameters, not hidden optimization knobs.

Default Refinery model:

- two blank candidate rows;
- benchmark blank;
- `useWeights=false`;
- five-year visible date window ending today;
- `ewmaDecay=0.94`;
- `stressQuantile=0.10`.

The five-year UI default is a convenience only, not a claim of an optimal risk lookback.

## 3. Persistence and migration

Refinery state is persisted independently to:

```text
backteststock.refinery.workspace.v1
```

Persistence is local-browser only in V1. Invalid stored data fail closed to a fresh default model. Migration/validation must be explicit and must never read/write `backteststock.portfolio.model.v1`.

Phase 4 does not introduce cross-workspace copy, scanner→Refinery handoff, or Portfolio→Refinery conversion. Those require a separate reviewed contract if desired later.

## 4. API client boundary

Refinery UI uses a separate client module and only:

```text
POST /api/v1/refinery/preflight
POST /api/v1/refinery/analyze
```

Portfolio UI continues to use only:

```text
/api/v3/portfolio/*
```

No client may call a foreign API origin. Both namespaces are same-origin/self-owned.

Refinery client errors preserve HTTP status and `X-Request-Id` when available, but the UI displays stable human-readable messages and never assumes a failed request implies a valid zero metric.

## 5. Workflow

Refinery workflow:

1. edit candidates/date/optional benchmark/optional weights;
2. run `preflight`;
3. inspect membership/data readiness/failures/effective observations;
4. run `analyze` only when local validation passes; API may still return `incomplete` or `insufficient_data` and the UI must honor it;
5. inspect deterministic risk diagnostics.

A model edit invalidates the prior preflight/analyze result. Requests are abortable; starting a new request cancels the previous one.

Phase 4 does not automatically chain `preflight` into `analyze` as an implicit approval of incomplete data. The user sees the preflight state and explicitly starts analysis.

## 6. Diagnostic presentation

### Structure summary

Display only values present in Phase 3 response:

- requested/resolved candidate count;
- complete-case daily/weekly observations;
- covariance entropy effective rank;
- covariance participation ratio;
- medium-correlation effective rank/participation ratio;
- Diversification Ratio only when explicit weights make it available;
- Ledoit-Wolf shrinkage;
- maximum estimator dispersion.

Do not rename effective rank as an exact number of independent economic bets.

### Capital vs signed risk contribution

Only when weights were explicitly supplied and portfolio risk status is available:

- symbol;
- normalized capital weight used by API;
- signed component RC in annualized volatility units;
- signed RC share `component RC / portfolio volatility` as a presentation-only decomposition;
- negative hedge contribution stays negative.

No recommendation color/verdict is attached to a negative/positive RC.

### Covariance stability

Display:

- Ledoit-Wolf shrinkage;
- sample/Ledoit-Wolf/EWMA observation/method/PSD/rank/condition diagnostics;
- pairwise relative Frobenius estimator dispersion;
- maximum dispersion.

No estimator is presented as a future-return signal.

### Data confidence

Display:

- candidate dataset hash prefix;
- methodology versions;
- requested/resolved/failure evidence;
- effective date range;
- reference/daily/weekly complete-case observation counts;
- coverage diagnostics;
- benchmark status/failure;
- explicit `incomplete` / `insufficient_data` / unavailable states.

### Correlation views

Tabs/views:

- tactical daily;
- medium daily;
- structural weekly;
- downside benchmark-negative;
- stress benchmark lower-tail.

Every view retains API status, input/effective/dropped observations, condition/window/threshold and matrix availability.

## 7. Large-matrix rendering guard

The API may accept up to 100 candidates, but the browser must not always render five raw 100×100 tables.

```text
MAX_FULL_CORRELATION_MATRIX_SYMBOLS = 20
MAX_CORRELATION_PAIR_ROWS = 30
```

If matrix size ≤20:

- render the full labelled matrix inside an accessible horizontal/vertical scroll region.

If matrix size >20:

- do not mount the full N×N cell table;
- render a deterministic pair summary produced from the returned matrix only;
- exclude diagonal self-pairs;
- sort by descending absolute correlation, then symbol names for deterministic ties;
- show at most 30 pairs;
- label it clearly as `大型矩陣摘要`, not clustering/redundancy analysis.

This is a DOM/performance presentation guard, not a Phase 5 redundancy engine.

## 8. Responsive/accessibility behavior

- Preserve existing direct-page desktop/mobile behavior and minimum 320px support.
- Workspace switch must remain keyboard accessible and identify the active workspace.
- Input candidate table may horizontally scroll on desktop; mobile uses stacked candidate rows rather than forcing a 100-column/row matrix editor.
- Fixed action bar must respect safe-area inset and never hide primary content.
- Tables/matrices use labelled regions and scroll containers.
- Loading, cancellation, error, incomplete, insufficient and unavailable states must have text labels; do not rely on color alone.

## 9. Existing Portfolio behavior that must remain unchanged

Phase 4 must preserve existing Portfolio defaults and tests, including:

- `/portfolio/` defaults to Portfolio workspace when no valid saved workspace exists;
- `?model=` Portfolio share decoding;
- scanner/main `?handoff=` import and return-link behavior;
- existing `backteststock.portfolio.model.v1` persistence;
- five-portfolio / twenty-asset Portfolio editor limits;
- direct full-page/no-dialog/no-iframe behavior;
- Portfolio preflight/backtest/export flows;
- 390px focused Portfolio editor behavior;
- `/api/v3/portfolio` client namespace.

## 10. Phase 4 source-contract tests

Update source-contract protection from "Portfolio app only talks to Portfolio v3" to the stronger two-workspace rule:

- Portfolio API module contains `/api/v3/portfolio` and does not contain Refinery prefix;
- Refinery API module contains `/api/v1/refinery` and does not contain Portfolio v3 prefix;
- neither uses third-party/foreign API origins;
- existing Portfolio model storage key remains unchanged;
- Refinery storage key is separate;
- `?model=` and `?handoff=` force Portfolio workspace;
- scanner handoff code still only writes Portfolio model;
- no Refinery code imports Portfolio ledger request/response types as a generic data bag.

## 11. E2E gates

Add browser coverage for:

1. existing Portfolio direct-page flow remains unchanged;
2. workspace switch to `持股精煉診斷`;
3. separate Refinery model persistence and reload;
4. `?model=` and `?handoff=` force Portfolio workspace;
5. Refinery preflight `ready`, `incomplete`, `insufficient_data` states;
6. no-weights analysis shows portfolio risk unavailable without fabricating equal weights;
7. explicit-weights analysis shows capital vs signed RC/DR;
8. covariance/effective-dimension diagnostics;
9. five correlation views and unavailable benchmark state;
10. >20-symbol correlation response uses pair-summary rendering and does not mount full matrix cells;
11. 390px Refinery form/actions remain usable without horizontal page overflow.

## 12. Explicit non-goals

Phase 4 does not implement:

- clustering or dendrograms;
- redundancy HIGH/MEDIUM/LOW verdicts;
- factor/economic-theme overlays;
- KEEP/TRIM/REPLACE/ranking;
- Leave-One-Out/Add-One/Replace-One;
- selection or sizing;
- HRP/ERC/minimum-variance optimization;
- Exhaustive integration;
- OOS/walk-forward claims;
- scanner→Refinery or Portfolio→Refinery handoff/copy.

Those remain later phases or separately reviewed future work.
