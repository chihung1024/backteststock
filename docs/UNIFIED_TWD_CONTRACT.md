# Unified TWD valuation contract

Status: **implemented and regression-tested; release identity is tracked by repository tags**.

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

## Current-instrument lifecycle boundary

A ticker string is not sufficient proof of instrument identity. Tickers can be
reused and an upstream vendor can stitch historical rows across an instrument
change. A real historical price for the same ticker text must therefore not be
assumed to belong to the instrument represented by that ticker today.

The shared Yahoo market-data boundary uses the versioned contract:

```text
INSTRUMENT_IDENTITY_CONTRACT_VERSION = yahoo-first-trade-date-2026-08-15.1
source = yahoo_history_metadata.firstTradeDate
```

Before TWD valuation, return decomposition, Scanner metrics, Portfolio ledger,
ResearchDataset construction, or Exhaustive preparation may consume a series:

- the current Yahoo instrument's `firstTradeDate` must be verified;
- every adjusted-close row before that date is removed;
- every time-indexed Raw Close, dividend, capital-gain, stock-split, and repair
  component is clipped to the same boundary;
- the corporate-action audit is rebuilt after clipping, so its event counts and
  warning dates refer only to the current instrument lifetime;
- the instrument-identity audit records the source, verified first-trade date,
  original/effective first dates, removed pre-inception row count, and whether
  clipping was required;
- if current-instrument metadata cannot be verified, the series fails closed as
  unresolved/retryable instead of producing research results from ticker-only
  history;
- if the requested window lies entirely before the current instrument's first
  trade date, no usable current-instrument history is returned.

This prevents the VFLO-class defect where a newly listed ETF can otherwise
appear to have years of pre-inception performance because an upstream ticker
history contains older rows. The market-data contract version includes the
instrument-identity contract, so caches created under the prior semantics are
not reused.

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