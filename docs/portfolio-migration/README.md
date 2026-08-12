# Portfolio migration provenance

Status: **HISTORICAL PROVENANCE ONLY — NOT LIVE PROJECT STATUS.**

This directory preserves only the migration evidence that still has unique value after Portfolio v3 became the self-owned production path in `backteststock`.

## Frozen source

Source repository: `chihung1024/backtest`

Frozen source commit:

`36eab9a380b69f0f3bd86c3906066f4f56e715bc`

Target production page: `/portfolio/`

The immutable source manifest, capability matrix, request/response fixtures, synthetic market data and parity scenarios are preserved under `tests/fixtures/portfolio_migration/` and verified by `tests/test_portfolio_migration_contract.py`.

## Remaining migration-semantic documents

- `PR2_LEDGER_METRICS.md` — migration-era Portfolio ledger / metric semantics that are still useful until a dedicated current ledger contract fully supersedes them.
- `PR3_PORTFOLIO_V3_API.md` — migration-era Portfolio v3 API semantics that are still useful until dedicated current API documentation fully supersedes them.

PR4–PR6 rollout/navigation/runtime-cutover narratives are no longer kept in the active documentation tree. Current behavior is authoritative in implementation, tests, README/contracts/ADR and deployment configuration; the removed narratives remain reconstructable from Git/PR history.

## Authority boundary

This directory does not override current code, versioned contracts, tests, ADRs or `to_do_update_list.md`. It exists only for frozen provenance and remaining unique migration semantics.

The historical PR7 idea to remove external legacy repositories/sites/projects is **not authorized by this document**. Any external-resource cleanup requires a fresh dependency audit and an explicit current functional batch.
