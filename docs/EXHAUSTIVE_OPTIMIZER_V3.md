# 50M full-computation / compact-retention optimizer

Status: implemented in the merge branch; not yet deployed to production.

## Scope

The exhaustive engine accepts up to **50,000,000** `C(N,K)` portfolios. Every
accepted combination is evaluated with the same full-period, path-dependent
simulation. The limit is a computation limit, not a pre-ranking or sampling
limit.

The old 60-ticker source-list limit is removed. The deployed platform accepts
up to 100 source tickers per request, then also constrains the request by its
actual `C(N,K)` count, signed snapshot size, and browser resource estimate.

## TWD valuation snapshot

Before browser computation, every source ticker and benchmark is converted to
the shared daily TWD adjusted-close series.  The signed snapshot records
`valuationCurrency: "TWD"`, the TWD contract version, corporate-action audits,
and FX-source audits.  The browser refuses a non-TWD snapshot, so a saved native
currency job cannot be resumed or displayed as a TWD result.
The signed snapshot also carries the configured annual risk-free rate so
Sortino and Alpha use the same definition as the scanner and portfolio API.

## Why raw results are not persisted

Persisting all 50M portfolios with `K=10`, 14 `Float64` metrics, and packed
holdings would require multiple gigabytes plus tens of thousands of IndexedDB
writes. It also makes later sorting allocate hundreds of megabytes at once.
Raising the old numeric guard without changing this representation would make
the browser fail before meaningful results are available.

## Retention policy

After all combinations have been evaluated, the default retains at most
**5,000,000** distinct portfolios:

| Allocation | Purpose |
| --- | --- |
| 60% | Highest `optimized_score` portfolios. |
| 30% | Leaders in stable, growth, drawdown, Sortino, CAGR, and low-|MDD| views. |
| 10% | Deterministic rank-hash coverage sample for broader combination diversity. |

Overlaps are deduplicated. A rank-only primary reserve fills released places,
so the final set reaches the configured maximum whenever enough portfolios
exist. The allocation is transparent in code (`public/exhaustive-retention.js`)
and may be made configurable later without changing the calculation contract.

## Two bounded phases

1. Web Workers calculate all portfolios and stream only the score fields needed
   to choose retained ranks. Typed rank/score buffers keep memory bounded.
2. The selected ranks are evaluated again in parallel and saved in batches as
   `Uint32 rank + Float32[14] metrics + selection reason`. Holdings are derived
   from the combinatorial rank on demand, not stored per row.

The calculation remains `Float64`; `Float32` is only the compact, display and
sorting representation. A details view re-evaluates its selected portfolio
with the exact simulation before displaying path-dependent events.

At the 5M retention maximum, the primary durable array payload is roughly
305 MB before browser storage overhead. The preflight surfaces this estimate
and the transient selection-buffer estimate before a user starts a large job.

## Resume semantics

Pausing a large calculation stores its rank/score checkpoint. If a browser is
closed before that checkpoint exists, the completed range is deliberately
recomputed on resume; retaining only later chunks would bias global rankings.
During the second materialization phase, the selected ranks and completed compact
chunks are persisted, so it can resume without recomputing the full 50M set.
