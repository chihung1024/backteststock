# 50M full-computation / compact-retention optimizer

Status: **Current Exhaustive historical-search contract.** Operational deployment state must be verified from the current remote environment; this document defines the accepted calculation/storage semantics, not a cached rollout status.

## Scope

The exhaustive engine accepts up to **50,000,000** `C(N,K)` portfolios. Every accepted combination is evaluated with the same full-period, path-dependent simulation. The limit is a computation limit, not a pre-ranking or sampling limit.

The old 60-ticker source-list limit is removed. The platform accepts up to 100 source tickers per request, then also constrains the request by its actual `C(N,K)` count, signed snapshot size, and browser resource estimate.

This is a **full-period historical research/exploration** path. The same historical period is used for search and ranking; its winners are not out-of-sample evidence and must not be described as forward-performance validation.

## TWD valuation snapshot

Before browser computation, every source ticker and benchmark is converted to the shared daily TWD adjusted-close series. The signed snapshot records `valuationCurrency: "TWD"`, the TWD contract version, corporate-action audits, and FX-source audits. The browser refuses a non-TWD snapshot, so a saved native-currency job cannot be resumed or displayed as a TWD result.

The signed snapshot also carries the configured annual risk-free rate so Sortino and Alpha use the versioned metric context expected by the owning calculation contract.

## Why raw results are not persisted

Persisting all 50M portfolios with `K=10`, 14 `Float64` metrics, and packed holdings would require multiple gigabytes plus tens of thousands of IndexedDB writes. It also makes later sorting allocate hundreds of megabytes at once.

Raising the old numeric guard without changing this representation would make the browser fail before meaningful results are available.

## Retention policy

After all combinations have been evaluated, the default retains at most **5,000,000** distinct portfolios:

| Allocation | Purpose |
| --- | --- |
| 60% | Highest `optimized_score` portfolios. |
| 30% | Leaders in stable, growth, drawdown, Sortino, CAGR, and low-|MDD| views. |
| 10% | Deterministic rank-hash coverage sample for broader combination diversity. |

Overlaps are deduplicated. A rank-only primary reserve fills released places, so the final set reaches the configured maximum whenever enough portfolios exist. The allocation is transparent in code (`public/exhaustive-retention.js`) and may be changed only through an explicitly reviewed contract/policy change.

## Two bounded phases

1. Web Workers calculate all portfolios and stream only the score fields needed to choose retained ranks. Typed rank/score buffers keep memory bounded.
2. Selected ranks are evaluated again in parallel and saved in batches as `Uint32 rank + Float32[14] metrics + selection reason`. Holdings are derived from combinatorial rank on demand, not duplicated per row.

The calculation remains `Float64`; `Float32` is only the compact durable/display/sorting representation. A details view re-evaluates its selected portfolio with the exact simulation before displaying path-dependent events.

At the 5M retention maximum, the primary durable array payload is roughly 305 MB before browser storage overhead. Preflight surfaces storage and transient selection-buffer estimates before a large job starts.

## Resume semantics

Pausing a large calculation stores its rank/score checkpoint. If a browser is closed before that checkpoint exists, the completed range is deliberately recomputed on resume; retaining only later chunks would bias global rankings.

During the second materialization phase, selected ranks and completed compact chunks are persisted, so it can resume without recomputing the full combination set.

## Research boundary

Exhaustive V3 remains separate from future Portfolio Refinery selection/OOS governance. Any later integration must preserve a strict boundary between historical candidate search and independent walk-forward/out-of-sample validation.
