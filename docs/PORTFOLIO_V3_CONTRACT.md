# Portfolio v3 Current Contract

Status: **CURRENT / CANONICAL PRODUCT-SEMANTIC CONTRACT.**

This document preserves the durable Portfolio v3 behavior that future changes must keep or explicitly version. Exact schema/version constants, limits and implementation details are authoritative in current code and tests; this document does not freeze obsolete migration-era snapshots.

## 1. Authority boundary

Portfolio v3 is the self-owned Portfolio research path in this repository.

- Public API entrypoint: `api/portfolio_v3.py`.
- Domain implementation: `apps/api/app/portfolio/`.
- Market/FX/TWD valuation authority: `apps/api/app/data/`.
- Browser workspace source: `apps/portfolio-web/`; production page: `/portfolio/`.
- Edge routing/security authority: `worker/router.js`.
- Current behavior is verified by the direct Portfolio tests under `tests/`; historical migration fixtures are not a runtime authority.

Portfolio and Scanner/Exhaustive may share audited market/TWD data semantics, but Portfolio ledger behavior remains path-dependent Portfolio domain logic.

## 2. Valuation and ledger semantics

Portfolio valuation is TWD-based. The ledger consumes audited TWD price/total/distribution return components; it does not establish a second market-data or FX authority.

For each valuation interval, the economic ordering is:

1. beginning external cashflow;
2. asset price return and distribution treatment;
3. borrowing interest;
4. ending external cashflow;
5. periodic and/or drift-threshold rebalance plus transaction costs;
6. maintenance-margin evaluation and any forced liquidation;
7. record equity, cash, debt, gross exposure, allocation and audit events.

External deposits/withdrawals must not be misclassified as investment performance. Beginning and ending cashflows are handled consistently with time-weighted-return semantics.

### Distributions

- Reinvested distributions use total-return economics without adding the same distribution again as cash.
- Cash-retained distributions use price-return economics and add the distribution to cash/income.
- On the distribution date, reinvest and cash-retention policies must not double count value; subsequent paths may diverge because retained cash does not receive the asset's later market return.

### Rebalancing and costs

- Supported periodic policies and threshold rebalancing are domain configuration, not UI-only behavior.
- A drift threshold may independently trigger rebalancing.
- Transaction costs are based on traded notional and reduce portfolio equity; trades/costs remain auditable.
- Periodic logic must not invent economically meaningless terminal trades solely because the requested range ends.

### Leverage and liquidation

- Fixed-ratio leverage maintains the configured gross-exposure relationship when flows/rebalances require adjustment.
- Fixed-debt leverage preserves debt principal except where the domain operation explicitly changes it.
- Borrowing interest accrues through the ledger rather than being hidden in asset returns.
- Maintenance-margin breach is represented as a `margin_liquidation` ledger event/result state; it is not converted into a generic API failure.

## 3. Core metrics

Portfolio metrics are derived from the same effective ledger sample used by the serialized result.

Durable semantics include:

- return/growth/risk metrics such as Total Return, CAGR, volatility, Sharpe, Sortino, maximum drawdown and Calmar;
- benchmark-dependent Beta/Jensen Alpha/correlation only when an admissible benchmark sample exists;
- XIRR status is explicit: `unique`, `multiple`, or `no_solution`; multiple roots must not be collapsed into an arbitrary single answer;
- tail risk is explicitly historical simulation with disclosed confidence/horizon/sample;
- drawdown events expose peak/trough/recovery/depth/duration/recovered state;
- annual/monthly period returns identify actual boundaries and mark partial boundary periods.

Unavailable benchmark-dependent analytics remain unavailable; they must not erase an otherwise valid portfolio result or be silently converted to zero.

## 4. Multi-portfolio comparison sample

When multiple runnable portfolios are compared, comparison metrics/series and benchmark-dependent analytics must use the effective common comparison window established by the Portfolio service contract. The API must not silently rebuild the benchmark from a longer raw history and thereby compare different samples.

A benchmark may fail to cover the required comparison window. In that case benchmark-dependent outputs fail closed/degrade without shrinking or corrupting the valid portfolio common window.

Single-runnable behavior remains distinct where the current service contract permits the portfolio and benchmark to retain their own admissible full histories.

## 5. Public API contract

Current Portfolio v3 routes are:

```text
GET  /api/v3/portfolio/health
GET  /api/v3/portfolio/assets/search
POST /api/v3/portfolio/preflight
POST /api/v3/portfolio/backtests
```

Requests are typed and strict:

- unknown fields are rejected rather than ignored;
- symbols are canonicalized by current shared Portfolio/data rules;
- portfolio names/symbols must satisfy uniqueness constraints;
- weights must satisfy the current 100% tolerance contract;
- portfolio/asset/request-size resource caps are enforced by current models/Edge tests;
- TWD is the supported Portfolio valuation currency;
- future/invalid date ranges are rejected;
- cashflow, distribution, rebalancing, transaction-cost, leverage and analytics configuration is converted into domain models rather than reimplemented in the browser.

Exact numeric caps and schema/version strings must be read from current implementation/tests so this document does not preserve stale migration-era values.

## 6. Preflight and partial-success semantics

Preflight is a data/dependency readiness operation, not a second backtest engine. It reports current asset/portfolio/benchmark/dependency readiness, effective periods, failures and available audit/fingerprint evidence.

Failure isolation is mandatory:

- one asset failure only invalidates dependent portfolios;
- one portfolio failure does not erase independent successful siblings;
- benchmark failure does not erase valid core portfolio results;
- optional analytics/provider failure degrades to structured warning/unavailable evidence rather than destroying the core ledger result when the core result remains valid;
- failure/retryability information remains explicit instead of silently deleting a symbol or shortening a period.

## 7. Analytics semantics

### Factor + FX

For TWD Portfolio diagnostics, factor analysis separates equity-factor co-movement from non-TWD FX exposure. The response must disclose currency/model/sample limitations. This is historical decomposition, not a claim of predictive factor exposure for every global instrument.

### Style

Style decomposition uses a constrained solution with nonnegative exposures that sum to one over the current proxy set. It must not reproduce the obsolete pattern of unconstrained OLS followed by clipping/renormalization.

### Regimes

Market/macro regimes are retrospective classifications. Thresholds, sample counts and limitations remain visible. Observations lacking required moving-average/YoY evidence remain unclassified instead of being silently assigned to a default regime.

### Inflation/FRED-dependent analysis

FRED-dependent analytics are optional. Missing credentials/upstream data degrade to warnings without erasing the core Portfolio result. U.S. CPI-based inflation adjustment must disclose that it is not Taiwan CPI or the user's personal consumption basket.

## 8. Edge and security contract

Portfolio v3 Edge routing is allowlisted by known path/method. The Edge preserves path/query/body while enforcing current request-size and timeout policies and sanitizing sensitive proxy headers.

- Browser credentials/authorization/origin/referer are not impersonated toward the backend.
- Sensitive backend response headers such as `set-cookie`/server identity are stripped by current proxy policy.
- A request ID is attached for traceability.
- Missing/invalid self-owned backend origin fails closed.
- API responses use the current no-store/security-header policy where defined by the API contract.

Current Edge tests, not migration prose, are authoritative for exact limits and forwarding behavior.

## 9. Regression authority

The durable behaviors above are directly exercised by current runtime-facing tests, including:

- `tests/test_portfolio_ledger.py`
- `tests/test_portfolio_ledger_contract.py`
- `tests/test_portfolio_metrics.py`
- `tests/test_portfolio_api_models.py`
- `tests/test_portfolio_api_service.py`
- `tests/test_portfolio_analytics.py`
- `tests/test_portfolio_v3_api.py`
- `tests/test_portfolio_v3_edge_route.mjs`
- Portfolio common-window, runtime-cutover, smoke-readiness and web-contract regressions.

A future change that intentionally alters an externally observable semantic must update implementation, direct regression tests, exposed version/schema where applicable, and this contract in the same functional batch.

## 10. Historical migration boundary

The original Portfolio migration source, intermediate capability matrix, legacy request/response-shape fixtures and PR rollout documents are historical development evidence. They are recoverable from Git history and are not required in the active tree once the durable semantics are preserved here and by current runtime-facing tests.
