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

Portfolio and Scanner/Exhaustive may share audited market/TWD data semantics, but Portfolio ledger behavior remains path-dependent Portfolio domain logic. Cash, debt, exposure-reset trades and portfolio performance must be represented by this ledger rather than by a second performance engine.

## 2. Valuation and ledger semantics

Portfolio valuation is TWD-based. The ledger consumes audited TWD price/total/distribution return components; it does not establish a second market-data or FX authority.

For each valuation interval, the economic ordering is:

1. beginning external cashflow;
2. asset price return and distribution treatment;
3. borrowing interest;
4. ending external cashflow;
5. maintenance-margin/non-positive-equity guard before voluntary trades;
6. periodic/drift-threshold asset-allocation rebalance **or**, when no allocation rebalance fires, the required daily gross-exposure reset;
7. post-trade maintenance-margin/non-positive-equity guard;
8. record equity, cash, debt, gross/net exposure, allocation and audit events.

External deposits/withdrawals must not be misclassified as investment performance. Beginning and ending cashflows are handled consistently with time-weighted-return semantics.

### Distributions

- Reinvested distributions use total-return economics without adding the same distribution again as cash.
- Cash-retained distributions use price-return economics and add the distribution to cash/income.
- On the distribution date, reinvest and cash-retention policies must not double count value; subsequent paths may diverge because retained cash does not receive the asset's later market return.

### Weight-defined cash and gross exposure

The Portfolio domain interprets asset weights as **equity-relative target exposures**. The current domain gross-exposure bound is `(0, 500%]`; exact numeric limits remain authoritative in code/tests.

The ledger semantics are:

```text
sum(asset weights) < 100%  -> residual ledger cash
sum(asset weights) = 100%  -> fully invested
sum(asset weights) > 100%  -> financed gross exposure / ledger debt
```

These rules are ledger economics, not a synthetic return transformation:

- Residual cash is explicit ledger cash and does not receive an invented asset return.
- Leveraged gross exposure is explicit asset market value financed by explicit debt.
- `target_allocation` preserves the raw equity-relative exposure weights.
- `target_asset_mix` is the normalized asset-only composition.
- The ledger records target/realized gross exposure, net exposure, cash, debt and `exposure_reset` events.
- Any non-100% target gross exposure is reset at each close to its configured gross-exposure ratio. This reset is separate from asset-allocation rebalance.
- For an underinvested target, the close reset recomputes both asset gross exposure and residual cash from post-cost equity; it does not create debt merely to preserve an old cash amount.
- A pure daily gross-exposure reset **preserves the current asset mix**. It must not silently restore each asset to its original raw target weight.
- Example: a portfolio entered as `VT 100% + QQQ 50%` has 150% target gross exposure. Daily close reset restores total gross exposure to 150%, while VT/QQQ may drift relative to each other. Their internal mix returns to the original target only when the configured periodic or drift-threshold asset-allocation rebalance independently fires.
- Example: a single-asset 50% Portfolio restores asset exposure to 50% of post-cost equity and residual cash to 50% at each close.
- If an allocation rebalance fires on the same close, that single rebalance restores target asset mix and target gross exposure; a redundant exposure-reset trade must not be added afterward.
- Allocation-threshold logic compares normalized asset mix. Gross/cash drift is handled by the independent daily exposure reset and must not by itself masquerade as internal allocation drift.
- `exposure_reset_count` counts close resets that actually trade non-zero notional; it is not a count of elapsed valuation dates where the target happened to already be satisfied.
- Transaction costs for reset/rebalance trades are solved inside the ledger against post-cost equity. The implementation must not approximate this contract as `daily return × leverage`.
- Borrowing interest remains an explicit ledger cost.

Initial exposure is subject to the same maintenance-margin/non-positive-equity guard before the first state is recorded. An input that starts already outside the configured margin constraint fails honestly rather than emitting an impossible day-zero ledger state.

### Rebalancing and costs

- Supported periodic policies and threshold rebalancing are domain configuration, not UI-only behavior.
- A drift threshold may independently trigger asset-allocation rebalancing.
- Asset-allocation rebalance and daily gross-exposure reset are distinct concepts and distinct ledger event semantics.
- A 100% total target has no weight-defined cash/leverage exposure-reset requirement; its asset allocation follows the configured rebalance policy.
- A non-100% total target has daily gross-exposure reset in addition to the independently configured asset-allocation policy.
- Transaction costs are based on traded notional and reduce portfolio equity; trades/costs remain auditable.
- Periodic logic must not invent economically meaningless terminal trades solely because the requested range ends.

### Legacy leverage compatibility and liquidation

- Existing fixed-ratio leverage is adapted into the **same daily gross-exposure reset authority**; it is not a second calculation engine.
- Fixed-debt leverage preserves debt principal except where the domain operation explicitly changes it.
- A non-100% weight-defined exposure combined with an explicit legacy leverage overlay is ambiguous and fails closed rather than multiplying leverage twice.
- Borrowing interest accrues through the ledger rather than being hidden in asset returns.
- Maintenance-margin/non-positive-equity failures are represented by explicit ledger liquidation state/events rather than being silently ignored or approximated.
- Existing direct `PortfolioLedger(...)` construction and the Walk-Forward OOS weight-vector `_rebalance(...)` call remain compatibility adapters into this same Portfolio authority; Walk-Forward does not reimplement Portfolio math.

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
- public Portfolio asset weights are equity-relative target exposures and may total below, equal to, or above 100% within the current Portfolio domain gross-exposure bound;
- the public API derives its maximum exposure admission from the Portfolio domain authority rather than maintaining a second hard-coded leverage cap;
- a request with non-100% weight-defined exposure and explicit legacy leverage fails closed as ambiguous;
- existing 100% / no-leverage requests remain the compatibility baseline;
- Portfolio result serialization exposes the ledger's cash/debt/gross/net exposure diagnostics, target gross/cash/mix truth and `exposure_reset_count` rather than recalculating them in the API layer;
- portfolio/asset/request-size resource caps are enforced by current models/Edge tests;
- TWD is the supported Portfolio valuation currency;
- future/invalid date ranges are rejected;
- cashflow, distribution, rebalancing, transaction-cost, leverage and analytics configuration is converted into domain models rather than reimplemented in the browser.

The API is therefore capable of the weight-defined exposure contract before the browser necessarily exposes it. Browser admission and removal of ambiguous legacy controls are the separate L3 UX boundary.

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
- `tests/test_portfolio_weight_defined_exposure.py`
- `tests/test_portfolio_ledger_compatibility.py`
- `tests/test_portfolio_metrics.py`
- `tests/test_portfolio_api_models.py`
- `tests/test_portfolio_api_service.py`
- `tests/test_portfolio_analytics.py`
- `tests/test_portfolio_v3_api.py`
- `tests/test_portfolio_v3_edge_route.mjs`
- Portfolio common-window, runtime-cutover, smoke-readiness and web-contract regressions.

A future change that intentionally alters an externally observable semantic must update implementation, direct regression tests, exposed version/schema where applicable, and this contract in the same functional batch.

## 10. Staged rollout boundary

The current weight-defined exposure implementation is intentionally staged:

1. **L1 Ledger Authority** — domain/ledger semantics and compatibility regressions.
2. **L2 API Contract** — public admission and serialized ledger truth.
3. **L3 UX** — editing/display and removal of ambiguous duplicate leverage controls.

L1 and L2 must not be interpreted as permission to bypass the browser's own validation before L3 is verified. L3 must consume the L1/L2 contract rather than reproduce leverage calculations in the browser.

## 11. Historical migration boundary

The original Portfolio migration source, intermediate capability matrix, legacy request/response-shape fixtures and PR rollout documents are historical development evidence. They are recoverable from Git history and are not required in the active tree once the durable semantics are preserved here and by current runtime-facing tests.
