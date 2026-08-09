# Metric Authority — Phase 0 Freeze

Status: Phase 0 authority contract. This document classifies the metric implementations that already exist. It does not change production formulas.

## 1. Purpose

Portfolio Refinery must not create a third or fourth independent definition of CAGR, volatility, Sortino, beta, alpha, drawdown, or tail risk. Before shared quantitative primitives are extracted, existing implementations are classified by **semantic role**, not merely by filename.

## 2. Authority classes

### A. Production simple-value metric authority

**Implementation:** `api/metrics.py`

**Current production consumers:**

- `apps/api/app/scan_service.py` -> production `/api/scan` through `api/scan_v2.py`.
- `apps/api/app/backtest_service.py` -> compatibility/full-period TWD portfolio service used by `api/index_v2.py`.
- supporting reproducibility/fingerprint callers.

**Semantic object:** an adjusted total-return **value series** (optionally paired with a benchmark value series).

**Authority:** canonical for simple-value/scanner/full-period compatibility metrics until a separately versioned migration replaces it.

### B. Portfolio v3 ledger metric authority

**Implementation:** `apps/api/app/portfolio/metrics.py`

**Consumer:** `apps/api/app/portfolio/service.py` after `simulate_portfolio_ledger()`.

**Semantic object:** a path-dependent TWD `PortfolioLedger`, including time-weighted return index, external flows, transaction costs, distributions, leverage/debt, and rebalancing events.

**Authority:** canonical for Portfolio v3 path-dependent portfolio reporting. It must not be replaced by simple value-series calculations when cashflows/path dependence matter.

### C. Exhaustive exact historical-search metric engine

**Implementation:** `public/exhaustive-optimizer-core.js::simulateExactPortfolio()` executed by `public/exhaustive-optimizer-worker.js`.

**Input:** signed TWD price snapshot prepared by `api/exhaustive_optimizer.py`.

**Semantic object:** exact historical simulated NAV for a specified equal-weight combination and explicit rebalance/cost policy.

**Authority:** exact metric engine **inside the full-period Exhaustive research/search workflow**. Its common no-flow metrics must remain parity-compatible with the simple-value authority where inputs and assumptions are equivalent.

It is not an out-of-sample validation authority.

### D. Legacy compatibility implementations — not current production authorities

- `api/index.py::calculate_metrics()`
- `api/scan.py::calculate_metrics()`

These files remain runtime dependencies for compatibility validation/constants/routes, but Vercel routes production `/api/scan` to `api/scan_v2.py` and wildcard compatibility traffic to `api/index_v2.py`. New quantitative work must not depend on these legacy metric implementations.

Notably, legacy `api/scan.py` uses CAGR-based Sharpe/Sortino/alpha semantics that intentionally differ from the current production `api.metrics` implementation. Phase 0 records this as legacy behavior rather than trying to force it into the canonical contract.

### E. Optimizer proxy/heuristic metrics — explicitly not performance authorities

**Implementation example:** `public/optimizer-worker.js::proxyMetrics()`.

The proxy engine approximates training/search objectives from means/covariances and even estimates drawdown from volatility/downside-volatility heuristics. These values exist to accelerate candidate search. They must be labelled and tested as **selection proxies**, not reported or reused as exact portfolio-performance metrics.

Likewise, score functions derived from exact metrics (for example `scoreMetrics()` in the Exhaustive core) are ranking formulas, not primitive metric definitions.

## 3. Shared primitive semantics frozen in Phase 0

When two contexts are genuinely equivalent, the following definitions are the shared target semantics for future `apps/api/app/quant/` primitives:

| Primitive | Frozen definition |
| --- | --- |
| Periodic return | arithmetic simple return `V_t / V_(t-1) - 1` |
| Trading-day annualizer | 252 |
| Daily risk-free rate | `(1 + annual_rf) ** (1/252) - 1` |
| Volatility | sample standard deviation of periodic returns (`ddof=1`) × `sqrt(252)` |
| Annualized excess return | mean of `(r - daily_rf)` × 252 |
| Sharpe | annualized arithmetic excess return / annualized volatility |
| Downside deviation | `sqrt(mean(min(r-daily_rf, 0)^2)) × sqrt(252)` |
| Sortino | annualized arithmetic excess return / downside deviation |
| Beta | sample covariance(asset, benchmark) / sample variance(benchmark) |
| Jensen alpha | `[mean(r) - (daily_rf + beta*(mean(rb)-daily_rf))] × 252` |
| Max drawdown | minimum of `level / running_max(level) - 1` |
| Historical daily VaR 95% | empirical 5th percentile under the Portfolio v3 historical-simulation convention |
| Historical daily CVaR 95% | mean of observations `<= VaR` |

Undefined risk ratios are **unavailable**, not economically equal to zero. Python currently represents them as `None`; the browser exact engine uses `NaN` internally. Serialization/UI layers may map unavailable values explicitly, but must not silently turn them into valid zeros.

## 4. Known versioned/contextual differences that Phase 0 does not silently change

### 4.1 CAGR year-length constant

- `api/metrics.py`: `365.25` days/year.
- Exhaustive exact worker: `365.25` days/year.
- Portfolio v3 ledger metrics: `365.2425` days/year.

This produces a small but real CAGR difference on identical levels. The Phase 0 golden fixture records both expected values. No production value is changed in this phase. Any future unification requires an explicit metric-context version bump and regression/compatibility decision.

For the future shared simple-value primitive layer, **365.25 remains the frozen compatibility baseline** unless a dedicated migration changes the contract.

### 4.2 Benchmark alignment

`api/metrics.py` intentionally restricts level metrics to common asset/benchmark price dates when a benchmark is supplied, and derives paired returns without bridging missing price intervals.

Portfolio v3 computes standalone portfolio performance from its ledger return index and aligns the benchmark only for benchmark-relative metrics. This is intentional: benchmark availability must not rewrite a path-dependent portfolio's own TWR/CAGR/MDD history.

Parity is therefore required only on fixtures where the asset/portfolio and benchmark calendars are already identical.

### 4.3 Portfolio-only metrics

XIRR, external-flow accounting, transaction/borrowing costs, income, liquidation status, drawdown-event metadata, period returns, and other ledger-specific outputs remain Portfolio v3 context metrics. They are not candidates for simple-value parity.

### 4.4 Exhaustive-specific path

The Exhaustive exact engine includes its own explicit equal-weight rebalance, delay, and transaction-cost mechanics. Exact NAV-path differences created by those rules are not metric-formula drift. Common metrics should match only after the same NAV/return path has been established.

## 5. Required cross-language golden fixture

`tests/fixtures/quant_authority_v1.json` is the Phase 0 shared golden fixture.

It is consumed by:

- Python parity tests for `api.metrics` and the no-flow Portfolio v3 ledger context.
- JavaScript parity tests for `simulateExactPortfolio()`.

Changing expected values requires an explicit methodology review; the fixture must not be casually regenerated to make a failing test green.

## 6. Future canonical module boundary

Future shared primitives should live under:

```text
apps/api/app/quant/
├── returns.py
├── moments.py
├── tail.py
├── benchmark.py
├── covariance.py       # Phase 2
└── contracts.py
```

Phase 0 **does not migrate production callers** into this namespace. Extraction happens only after parity is proven and must preserve external results unless a separately approved defect/methodology migration is versioned.

## 7. Change-control rule

A change to a shared primitive must include:

1. methodology/contract version decision;
2. golden-fixture review;
3. Python parity tests;
4. browser Exhaustive parity tests when the primitive exists there;
5. Portfolio v3 context test when equivalent;
6. explicit treatment of legacy/proxy engines rather than accidental synchronization;
7. update to root `to_do_update_list.md`.

No future Portfolio Refinery implementation may redefine these shared primitives locally.
