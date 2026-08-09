# ADR 0001 — Runtime and Quantitative Authority Boundaries

- Status: Accepted for Phase -1
- Date: 2026-08-09
- Scope: architecture authority only; no runtime behavior change

## Context

The repository completed the self-owned Portfolio v3 cutover while retaining compatibility Flask routes for scanner, screener, legacy backtest, and exhaustive research workflows. Documentation still described FastAPI as future work, and the planned Portfolio Refinery would otherwise risk adding a third independent quantitative implementation.

## Decision

1. `api/portfolio_v3.py` is the production FastAPI Portfolio v3 entrypoint.
2. `api/index_v2.py`, `api/scan_v2.py`, `api/screener.py`, and `api/exhaustive_optimizer.py` remain production compatibility/research entrypoints until separately retired.
3. `apps/api/app/data/` is the shared TWD market-data and valuation authority.
4. `apps/api/app/portfolio/` is the Portfolio v3 ledger and portfolio-analysis authority.
5. New Portfolio Refinery work must not be added to legacy `api/index.py` or `api/optimizer.py`.
6. Before Refinery risk mathematics is implemented, Phase 0 must define and test canonical shared quantitative primitives so Scanner/legacy metrics, Portfolio v3 metrics, and Refinery do not become three independent formula authorities.
7. The full-period exhaustive optimizer is classified as historical research/exploration. It is not an out-of-sample validation engine and must not be used directly as a production recommendation gate.

## Consequences

- Phase -1 updates documentation only and retires obsolete one-off workflow files.
- Phase 0 will freeze metric semantics and parity before refactoring implementation.
- Portfolio Refinery remains blocked from runtime implementation until Phase -1 and Phase 0 exit gates pass.
- Existing compatibility routes are not removed by this ADR.

## Rejected alternatives

- Treat all current Python entrypoints as equivalent production authorities: rejected because responsibilities differ and this would perpetuate ambiguity.
- Put Refinery formulas directly into `portfolio/analytics.py`: rejected because it would mix portfolio analytics, structural risk research, and selection logic in one module.
- Reuse full-period exhaustive results as future-selection evidence: rejected because the same data are used for search and evaluation, creating selection and multiple-testing bias.
