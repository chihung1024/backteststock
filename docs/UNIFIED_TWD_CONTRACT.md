# Unified TWD valuation contract

Status: **production TWD valuation implemented; return-component extension is under PR 1 validation**.

The unified `backteststock` product uses TWD as its only valuation currency.
For every asset, benchmark, scanner result, portfolio path, and optimizer score:

```text
TWD adjusted close[t] = native adjusted close[t] × FX(native → TWD, t)
```

`native adjusted close` is the audited Yahoo `Adj Close` total-return series,
normalized from a minor quote unit such as `GBp`, `ZAc`, or `ILA` to its major
currency before valuation. The raw Yahoo currency and applied price scale stay
in the FX audit metadata.

`FX(native → TWD, t)` is TWD per one unit of the source quote currency. A TWD
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

## Return-component extension

A total-return adjusted-close series is sufficient when all distributions are
reinvested. It is not sufficient when a portfolio must retain dividends or
capital-gain distributions as cash. The Portfolio Lab migration therefore adds
a versioned decomposition without replacing the existing adjusted-close truth.

Source contract:

```text
RETURN_COMPONENT_SOURCE_VERSION = yahoo-close-events-2026-08-04.1
```

TWD component contract:

```text
RETURN_COMPONENTS_CONTRACT_VERSION = twd-return-components-2026-08-04.1
```

Yahoo download results retain the following cleaned inputs in each adjusted
series' audit attrs:

- Raw `Close`
- `Dividends`
- `Capital Gains`
- `Stock Splits`
- `Repaired?`

The native-currency additive contract is:

```text
Native Total Return = Native Price Return + Native Distribution Return
```

Reported distributions are divided by the previous valid Raw Close. Price
return is defined as exact adjusted-close total return minus the distribution
return. This preserves the total-return truth and prevents a raw-price split
scale change from becoming a false investment loss.

The TWD conversion contract is:

```text
TWD Total Return = (1 + Native Total Return) × (1 + FX Return) - 1
TWD Distribution Return = Native Distribution Return × (1 + FX Return)
TWD Price Return = TWD Total Return - TWD Distribution Return
```

The following invariants are mandatory:

- `TWD Total Return = TWD Price Return + TWD Distribution Return` within the
  published numerical tolerance.
- The component total return reproduces the existing TWD adjusted-close daily
  return on exactly the same calendar.
- Distribution returns are non-negative because this layer models reported
  gross cash distributions, not taxes or fees.
- Minor quote-unit scaling applies to prices and cash amounts, but never to
  split ratios.
- Histories without component attrs remain usable through a `total_return_only`
  compatibility result. Their existing Scanner, backtest, and Optimizer output
  does not change.

## Runtime boundary

The public compatibility routes call the framework-neutral core:

- `/api/backtest` → `TWDPortfolioBacktestService`
- `/api/scan` → `TWDScanService`
- `/api/optimizer/exhaustive/prepare` → signed TWD price snapshot

The outer Vercel runtime remains Flask during the staged migration. Shared
calculation and data services live under `apps/api/app/`, allowing the later
FastAPI Portfolio v3 entrypoint to reuse the same valuation and return-component
contracts rather than fork them.
