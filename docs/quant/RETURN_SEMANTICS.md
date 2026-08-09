# Return Semantics — Phase 0 Freeze

Status: authoritative semantics inventory for current TWD research/backtest paths. No production calculation is changed by this document.

## 1. Base valuation unit

For current multi-market research and backtest paths, portfolio/comparison values are expressed in TWD under the existing TWD valuation contract:

```text
TWD adjusted level = native adjusted level × TWD per native-currency unit
```

The authoritative data implementation remains under `apps/api/app/data/`.

## 2. Return basis

Unless a context explicitly states otherwise, performance metrics use adjusted total-return levels/returns. Yahoo adjusted-close behavior and corporate-action audit limitations remain governed by the existing market-data/corporate-action contracts.

A future Refinery must not mix raw `Close`, native-currency adjusted close, and TWD adjusted total-return values inside the same risk matrix without an explicit labelled transformation.

## 3. Calendar semantics

### 3.1 Individual TWD asset history

Native market and FX observations are combined under the current TWD valuation contract. Previously observed values may be carried forward where the contract permits; future observations are never backward-filled into earlier dates.

### 3.2 Scanner / simple full-period portfolio calendar

`align_twd_price_frame()` constructs the union of selected TWD valuation calendars, forward-fills only after an actual observation, and drops opening dates before every required series has an observed value.

This preserves FX-only and cross-market valuation changes while avoiding pre-observation look-ahead.

### 3.3 Portfolio v3 ledger calendar

Portfolio v3 aligns **return components** over the overlapping available period. Missing component returns on a union valuation date are filled with zero after the common real-history start/end boundaries. The first aligned return is explicitly zero.

This is a path-dependent ledger context and must not be treated as identical to a simple price-level series when cashflows, distributions, leverage, transaction costs, or liquidation events are present.

### 3.4 Future structural-risk calendar

Phase 2 may introduce synchronized weekly TWD returns for cross-market structural correlation/clustering. That series is a research transformation and must remain separate from the daily TWD return series used to measure the investor's realized daily NAV risk.

## 4. Benchmark semantics

### Simple-value authority

When `api.metrics.calculate_metrics()` receives a benchmark level series, asset and benchmark prices are aligned before paired returns are calculated. Missing asset prices are not bridged by a return spanning a different benchmark interval.

### Portfolio v3

Portfolio standalone performance is calculated from the ledger independent of benchmark availability. Only beta/alpha/correlation use an inner join between portfolio and benchmark return observations.

This difference is intentional and must be retained unless separately versioned.

## 5. Annualization semantics

Shared return/risk primitives currently use:

- trading periods/year: `252`;
- daily risk-free rate: `(1 + annual_rf) ** (1/252) - 1`;
- volatility: sample standard deviation (`ddof=1`) × `sqrt(252)`;
- arithmetic annualized excess return: daily excess mean × 252.

CAGR uses elapsed calendar time. Current contexts differ slightly in calendar-year constant:

- simple-value / Exhaustive exact: `365.25` days;
- Portfolio v3 ledger context: `365.2425` days.

Phase 0 records this as a known versioned difference and does not rewrite historical outputs.

## 6. Cashflow semantics

### Simple-value / Scanner / Exhaustive

No external cashflow adjustment exists in the simple adjusted-level metric function. Exhaustive exact simulation includes explicit trading costs/rebalancing mechanics but not the Portfolio v3 general external cashflow ledger.

### Portfolio v3

`PortfolioLedger.return_index` and `daily_returns` are the time-weighted performance authority. External contributions/withdrawals are removed according to the ledger's published beginning/end timing rules. Money-weighted return is separately reported as XIRR.

Therefore:

- never reconstruct Portfolio v3 TWR by taking `equity.pct_change()` when external flows exist;
- never use XIRR as a substitute for TWR in risk covariance/correlation calculations;
- future Refinery analysis of a current holdings set should operate on asset return series, not on cashflow-contaminated account equity changes.

## 7. Missing data and failure semantics

The project policy is explicit failure, not silent membership mutation.

A quantitative research dataset or Refinery request must not silently:

- delete a ticker because data are missing;
- shorten the requested date range to make a matrix complete;
- backward-fill pre-listing/pre-data history;
- substitute another currency/calendar without metadata;
- convert an undefined metric into a valid numerical zero.

Coverage and effective-observation counts must be exposed separately from metric values.

## 8. Native, FX, and TWD decomposition

For future risk diagnostics, these are distinct objects:

- native equity return;
- FX return to TWD;
- resulting TWD total return.

TWD return is the investor-risk authority. Native/FX components may be reported diagnostically to explain whether a correlation/risk change comes from securities or currency. They must not be combined as if they were independent without respecting the valuation identity and covariance interaction.

## 9. Research vs validation semantics

A return series can be calculated correctly and still be used incorrectly.

- Full-period Exhaustive results are historical search/exploration results.
- Training data may be used to choose candidates/policies.
- Only never-seen periods may support out-of-sample validation claims.
- Current-universe membership or current fundamentals must not be projected backward and described as point-in-time evidence.

These research-validity constraints become executable in Phase 7 but are already part of the semantic contract.
