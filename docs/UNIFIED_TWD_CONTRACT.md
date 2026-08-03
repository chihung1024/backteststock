# Unified TWD valuation contract

Status: **implemented in the merge branch; production deployment is still pending**.

The unified `backteststock` product uses TWD as its only valuation currency.
For every asset, benchmark, scanner result, portfolio path, and optimizer score:

```text
TWD adjusted close[t] = native adjusted close[t] × FX(native → TWD, t)
```

`native adjusted close` is the audited Yahoo `Adj Close` total-return series.
`FX(native → TWD, t)` is TWD per one unit of the source quote currency.  A TWD
quote uses an FX rate of exactly `1.0`.

## Daily calendar rule

Each asset is valued on the union of its native-price dates and FX dates:

- On an FX-only day, carry the last observed native adjusted close forward and
  recalculate TWD value with that day's FX rate.
- On a local-market-only day, carry the last observed FX rate forward.
- Before either source has an observed value, do not create a valuation.
- Never backward-fill price or FX data from a future observation.

Therefore the result tracks the FX trend daily without future-data leakage.
The resulting TWD adjusted-close series—not a separately compounded native and
FX return approximation—is the source for all later performance calculations.

## Runtime boundary

The branch's public compatibility routes now call this framework-neutral core:

- `/api/backtest` → `TWDPortfolioBacktestService`
- `/api/scan` → `TWDScanService`
- `/api/optimizer/exhaustive/prepare` → signed TWD price snapshot

The outer Vercel runtime remains Flask during the staged migration; the shared
calculation and data services live under `apps/api/app/` so a later FastAPI
entrypoint will not fork the valuation logic.  This is not a claim about the
currently deployed production revision until this branch is released.
