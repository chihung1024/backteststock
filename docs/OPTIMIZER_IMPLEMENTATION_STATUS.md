# Optimizer Implementation Status — Historical Snapshot

Status: **HISTORICAL / SUPERSEDED AS A LIVE STATUS DOCUMENT**.

This file preserves the Exhaustive optimizer implementation snapshot from the original rollout. Statements below about pending deployment/browser-capacity validation describe that historical stage and must **not** be used as the current project status.

For current state use:

1. root `to_do_update_list.md` for live phase/verification status;
2. `EXHAUSTIVE_OPTIMIZER_V3.md` for the current full-period Exhaustive product/research contract;
3. current code/tests/GitHub checks for operational truth.

## Historical active product contract captured by this snapshot

- One fixed user-supplied source pool; no pre-ranking, ticker substitution, or training-period candidate selection.
- One complete historical period; no training / out-of-sample split.
- Every asset and benchmark is converted to daily TWD adjusted-close levels before the browser receives the signed snapshot.
- Any source or benchmark data failure stops exhaustive preflight with an explicit list; it never silently drops a ticker or shortens the period.
- `N` source tickers and configurable `K` holdings enumerate all `C(N,K)` portfolios with dynamic equal target weights `1/K`.
- Relative bands, monthly, quarterly, annual, and no-rebalance modes use the same exact browser simulation and configurable transaction cost / execution delay.

These semantics remain historical-research semantics: full-period search results are not out-of-sample future-performance evidence.

## Capacity and persistence recorded at implementation time

- Browser calculation limit: **50,000,000** combinations.
- Durable retained result bound: up to **5,000,000** rows after all combinations are evaluated.
- Historical retention policy: 60% primary optimized-score leaders, 30% complementary-metric leaders, 10% deterministic diversity coverage.
- First phase stores bounded typed selection buffers; retained ranks are re-evaluated and stored compactly as `Uint32 rank + Float32[14] metrics`.
- Holdings are reconstructed from combinatorial rank rather than duplicated per saved row.
- Paused jobs persist checkpoints/compact chunks; a close before the first checkpoint recomputes work rather than biasing global ranks.
- Historical source-ticker boundary was raised from 60 to 100, additionally constrained by combination count, signed snapshot size and preflight resource estimates.

Any capacity value that affects current behavior must be verified against current code/tests rather than assumed from this snapshot.

## Retired surface

The former `/api/optimizer/*` training / out-of-sample workflow is retired from the active edge/public route contract. `optimizer.html` uses the full-period Exhaustive preparation path. Legacy source files may remain as historical references and are not automatically production authorities.

## Historical release checks

At the time this snapshot was written, the following checks were still listed as pending:

- real-browser IndexedDB resume / high-retention validation;
- 25/50/75/100-source preflight capacity checks on target runtime;
- deployment confirmation under hosting/request limits.

Those lines are retained here as **historical evidence of the rollout state**, not as current blockers. Later CI/release/deployment evidence is recorded in Git history and the live roadmap.

## Maintenance rule

Do not keep updating this file as a second project tracker. If Exhaustive semantics change, update the versioned Exhaustive contract and root live roadmap; preserve this snapshot for audit history.
