# Optimizer implementation status

This branch implements the agreed MVP end to end:

- strict training-only candidate selection from the source scan universe;
- 20-stock candidate pool and 10-stock equal-weight portfolios;
- relative ±20% weight bands with next-common-close execution;
- 184,756-combination proxy pass and 30,000 deep-search budget;
- deterministic multi-start, one-swap and limited two-swap search;
- 300 Python exact verifications with 70/30 training/out-of-sample split;
- transaction costs, turnover and rebalance event output;
- signed compressed data snapshot reused by search and verification;
- objective champions, exact-result table, Pareto chart and audit exports.

The optimizer does not create a persistent daily-price database and does not weaken Adjusted Close, repair or corporate-action audit requirements.

Final hardening guarantees exact unique budget contributions, explicit little-endian mask hashing, and a 3 MiB optimizer-only edge request ceiling compatible with the 2 MiB compressed snapshot ceiling.

The final implementation rejects silent out-of-sample truncation, treats null metrics as unavailable rather than zero, aggregates all three exact-verification batches to 300, and persists only compact summaries in localStorage while retaining full events in the audit JSON export.

## Dual-mode and daily-range hardening (2026-08-02)

- The scan endpoint accepts exact `YYYY-MM-DD` start and end dates while retaining legacy year/month request compatibility.
- The optimizer supports both strict automatic training-only candidate selection and a fixed manual 20-stock candidate mode.
- Manual scan-result selections persist across sorting and pagination, are capped at 20, and must contain exactly 20 eligible stocks before launch.
- The original three composite scores remain available, with an additional optimized score: `Sortino × sqrt((1 + CAGR) / ((1 + Beta)^2 × (1 + |MDD|)))`.
- Automatic date defaults roll forward daily from the same local calendar date ten years ago through yesterday, while explicitly customized ranges remain unchanged.
- Desktop content width is increased to 1480px.

## Exhaustive full-period refactor (2026-08-02)

The production page is reworked around the user's original fixed-universe research contract. The preceding MVP sections remain as implementation history; they no longer describe the primary page after this refactor.

- The source universe is fixed exactly as supplied; no training-period ranking or silent ticker substitution occurs.
- `N` source tickers and configurable `K` holdings produce all `C(N,K)` combinations.
- Every combination receives the same path-dependent exact simulation across the complete selected period.
- Equal target weights are dynamic at `1/K`.
- Rebalancing supports relative bands, monthly, quarterly, annually, or never, with configurable common-trading-day execution delay and transaction cost.
- Preflight validates strict full-period coverage and corporate actions, measures the current device, estimates runtime and storage, and requires explicit confirmation.
- Web Workers process deterministic chunks; IndexedDB preserves completed chunks for stop/resume.
- Full results support arbitrary metric sorting, filters, paging, CSV export, and on-demand event-detail reruns.
- The original four composite formulas remain available as exact-result columns.
- No persistent server-side daily-price database is introduced.
