# Fixed-universe exhaustive portfolio backtest

## Research contract

The exhaustive optimizer treats the supplied source tickers as a fixed research universe. It does not rank, replace, or silently remove tickers before combination generation. For `N` source tickers and `K` holdings, the browser enumerates every `C(N,K)` portfolio and runs the same full-period path-dependent simulation for each one.

This is a full-period historical ranking tool. It intentionally does not split observations into training and out-of-sample periods. Results should therefore be interpreted as retrospective rankings and remain subject to data-mining and selection bias.

## Exact simulation

Every combination uses:

- equal target weights of `1/K`;
- one signed Adjusted Close snapshot shared by all workers;
- configurable relative weight-band, monthly, quarterly, annual, or no-rebalance policy;
- configurable execution delay in common trading days;
- transaction costs at initial construction and each rebalance;
- path-dependent shares, cash, turnover, costs, and drawdown;
- total return, CAGR, MDD, volatility, Sortino, Beta, Alpha, annualized one-way turnover, rebalance count, transaction cost, and all four composite scores.

No proxy score, heuristic search budget, training-period candidate ranking, or 300-portfolio verification sample is used in this mode.

## Preflight and execution

Before execution the application:

1. validates every source ticker, corporate-action audit, full-period coverage, and common-calendar endpoints;
2. computes the exact combination count;
3. downloads one signed snapshot;
4. runs a small exact calibration sample on the user's device;
5. estimates time, result size, and worker memory;
6. waits for explicit confirmation.

The browser then processes deterministic lexicographic combination ranges in Web Workers. Completed chunks and compact result arrays are saved in IndexedDB. A user may stop the job, preserve completed chunks, and resume later. Daily prices are not stored in a persistent server-side database.

## Scale guardrails

The current safety limit is 5,000,000 exact combinations per job and 60 source tickers. Results are stored as packed combination indexes and Float64 metric arrays. Event histories are generated on demand for a selected portfolio rather than persisted for every combination.
