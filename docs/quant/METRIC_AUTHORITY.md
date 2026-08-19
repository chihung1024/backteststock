# Metric Authority and Reproducibility Contract

Status: **Current quantitative metric/reproducibility authority map.**

Current simple-value metric definition: `METRIC_DEFINITION_VERSION = "2026-08-01.2"`.

This document consolidates the former metric-authority and reproducibility documents. It classifies existing numerical authorities and preserves the shared return, corporate-action and audit semantics without forcing semantically different engines into one implementation.

## 1. Authority classes

### Simple-value production metrics

`api/metrics.py` is the production authority for simple adjusted-value metrics used by current Scanner and compatibility/full-period TWD backtest paths.

Its semantic object is a total-return value series, optionally paired with a benchmark value series.

### Portfolio v3 ledger metrics

`apps/api/app/portfolio/metrics.py` is the authority for path-dependent Portfolio v3 reporting after `PortfolioLedger` simulation.

Cashflows, transaction/borrowing costs, distributions, leverage/debt and path-dependent state mean this context must not be replaced by a simple value-series shortcut.

### Exhaustive exact historical-search metrics

`public/exhaustive-optimizer-core.js` owns exact portfolio simulation/metrics inside the full-period Exhaustive search workflow.

It is a historical search authority, not an OOS-validation authority. Where the resulting NAV/return path and assumptions are genuinely equivalent, common metrics should remain parity-compatible with the simple-value authority.

### Legacy compatibility implementations

`api/index.py` and `api/scan.py` still support compatibility/runtime dependencies. Their older local metric functions are not authorities for new quantitative work.

### Proxy/heuristic search metrics

Any optimizer proxy used only to accelerate candidate search is not an exact performance authority. Proxy output must not be presented as accepted portfolio CAGR/Sortino/MDD or silently replace exact validation.

## 2. Market-data and total-return basis

Current production simple-value data uses Yahoo Finance daily history under the pinned runtime contract:

```text
interval = 1d
auto_adjust = false
repair = true
actions = true
keepna = false
```

The system intentionally retains:

- raw `Close` for adjustment/corporate-action audit;
- `Adj Close` as the native-currency gross total-return value series.

`auto_adjust=false` does not mean unadjusted performance is used. It preserves both raw and adjusted evidence so the adjustment can be audited.

Current return-basis interpretation is gross adjusted total return with distributions reflected through Yahoo adjusted prices. It does not include investor-specific taxes, withholding tax, ADR fees, commissions, bid/ask slippage or other costs unless a specific Portfolio contract explicitly models them.

## 3. TWD valuation before performance metrics

All cross-market production research follows the shared TWD valuation contract:

```text
TWD adjusted close[t]
= native adjusted close[t] × FX(native currency → TWD, t)
```

Metric formulas consume the resulting audited TWD evidence where the product contract says TWD is authoritative. Native returns may be used only by a separately scoped diagnostic such as the Refinery factor model.

Calendar/forward-fill rules belong to the TWD/data contracts and must never backward-fill from future observations.

## 4. Shared primitive definitions

When contexts are genuinely equivalent, the shared target semantics are:

| Primitive | Definition |
| --- | --- |
| Periodic return | `V_t / V_(t-1) - 1` |
| Trading-day annualizer | 252 |
| Daily risk-free | `(1 + annual_rf) ** (1/252) - 1` |
| Volatility | sample standard deviation of periodic returns (`ddof=1`) × `sqrt(252)` |
| Annualized excess return | `mean(r - daily_rf) × 252` |
| Sharpe | annualized arithmetic excess return / annualized volatility |
| Downside deviation | `sqrt(mean(min(r-daily_rf, 0)^2)) × sqrt(252)` |
| Sortino | annualized arithmetic excess return / downside deviation |
| Beta | `cov(asset, benchmark) / var(benchmark)` |
| Jensen alpha | `[mean(r) - (daily_rf + beta*(mean(rb)-daily_rf))] × 252` |
| Max drawdown | `min(level / running_max(level) - 1)` |
| Historical daily VaR 95% | empirical 5th percentile under the Portfolio v3 historical-simulation convention |
| Historical daily CVaR 95% | mean of observations `<= VaR` |

Undefined risk ratios are unavailable, not economically equal to zero.

## 5. CAGR and context-specific differences

Simple-value and current Exhaustive compatibility paths use a 365.25-day year for CAGR.

Portfolio v3 currently uses 365.2425 days/year.

This small difference is recorded context, not a reason to silently rewrite accepted historical results. A future unification requires a deliberate methodology/version migration.

Benchmark alignment also differs by semantic object:

- simple-value comparison may restrict comparable level/return samples to common valid asset/benchmark dates;
- Portfolio v3 standalone path metrics come from the portfolio ledger, while benchmark availability affects benchmark-relative metrics rather than rewriting the portfolio's own path.

Parity is required only where the actual semantic inputs/assumptions are equivalent.

## 6. Corporate-action audit

Standard Yahoo/yfinance events reflected in adjusted prices may include:

- ordinary and special distributions represented by the vendor;
- splits/reverse splits;
- capital-gain distributions;
- vendor price/action repairs.

The system records audit evidence such as event counts, repaired rows, adjustment changes and unexplained anomalies.

Normal audit state is:

```text
verified_standard_actions
```

Evidence that needs human review is represented explicitly, for example:

```text
review_required
```

A review-required state does not authorize the program to invent a replacement price series.

## 7. Non-standard event limitation

Yahoo adjusted price history cannot by itself guarantee economically complete treatment of every corporate event, including some:

- spin-offs;
- rights/warrants;
- cash/stock mergers;
- ticker/exchange/share-class transitions;
- ADR-ratio changes;
- delisting/liquidation outcomes;
- investor-specific taxes/fees.

These may require a security master, event terms and old/new instrument mapping that the public price feed does not prove.

Therefore BacktestStock must not claim that every possible corporate action is reconstructed with 100% certainty.

## 8. Price-index benchmark disclosure

Yahoo symbols beginning with `^` are often price indices rather than investable total-return series.

The system may warn that comparing an adjusted total-return asset/portfolio to such an index is not a pure total-return excess-return comparison. It must not silently replace a user-requested benchmark with another symbol.

## 9. Coverage and sample rules

Metrics use explicit effective samples rather than treating missing data as zero.

For simple asset/benchmark comparison, paired risk metrics use matching return observations and must not bridge a missing interval into a false one-day return.

Portfolio comparison contracts may require a complete/common sample for directly comparable portfolios.

Coverage describes observed evidence. Forward-filled alignment used for another legitimate purpose does not retroactively make source observations complete.

## 10. Reproducibility evidence

Depending on the endpoint/context, reproducibility metadata includes applicable:

- metric/methodology version;
- data-source settings/version;
- return basis;
- requested/effective dates;
- valuation currency and TWD contract version;
- benchmark;
- risk-free rate;
- corporate-action audit;
- requested/resolved/failure membership;
- price/history fingerprints;
- dataset/job/decision identities.

Fingerprints answer whether the same exact inputs were used. They cannot reconstruct a vendor history that the system never stored after the vendor later revises it.

## 11. Upstream revisions

Yahoo/yfinance may revise historical prices/actions.

A deterministic fingerprint can detect that current input differs from an earlier run when the earlier fingerprint/result was persisted. It is not an archival market-data store and cannot recover old vendor bytes by itself.

Research claims must reflect this limitation.

## 12. Biases not solved by adjusted prices

Correct distribution/split adjustment does not solve:

- survivorship bias;
- look-ahead bias;
- delisting bias;
- missing historical Universe/fundamental membership.

Those require PIT/provenance contracts and fail-closed research design. They must not be described as solved merely because `Adj Close` is used.

## 13. Golden parity fixture

`tests/fixtures/quant_authority_v1.json` is the shared cross-language golden fixture for compatible primitive behavior.

It is consumed by Python and JavaScript parity tests. Expected values must not be casually regenerated just to make a changed implementation green; a real methodology change needs explicit review/versioning.

## 14. Change discipline

A material shared-metric semantic change should include:

- explicit methodology/version decision;
- relevant golden/reference fixture review;
- targeted Python tests;
- JavaScript Exhaustive parity where the same primitive exists;
- Portfolio v3 parity/context tests where equivalent;
- explicit treatment of legacy/proxy engines.

Do not force synchronization between engines whose semantic objects genuinely differ, and do not create a new local metric definition inside Refinery/Optimizer/Browser code.
