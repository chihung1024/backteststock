# Unified API application core

`apps/api/app/` is the framework-neutral shared application core used by the current production APIs. The repository is no longer waiting for a future FastAPI-only cutover: self-owned Portfolio v3 is already served by `api/portfolio_v3.py` as FastAPI, while legacy/compatibility Flask entrypoints remain for other existing routes.

## Current runtime relationship

```text
Vercel Python Functions
├─ Flask compatibility entrypoints
│  ├─ api/index_v2.py
│  ├─ api/scan_v2.py
│  ├─ api/screener.py
│  └─ api/exhaustive_optimizer.py
│
└─ FastAPI Portfolio v3
   └─ api/portfolio_v3.py

Both consume shared services under apps/api/app/.
```

The first cross-runtime invariant is implemented in `app/data/twd_valuation.py`:

```text
TWD adjusted close = native adjusted close × (TWD per native currency unit)
```

The valuation calendar is the union of the native market and FX market calendars. Native prices and FX rates may be carried forward only after a previously observed value; backward filling from a later quote is forbidden. This keeps FX-only days visible in TWD return paths and prevents future-data leakage.

## Shared authorities

- `app/data/`: TWD valuation, FX normalization, return components, audited history services.
- `app/portfolio/`: Portfolio v3 ledger, metrics, analytics, contracts, and orchestration.
- Existing Scanner and Exhaustive compatibility entrypoints reuse this shared data core where already migrated.

## Extension rule

New Portfolio Refinery work must not be added to legacy `api/index.py` or `api/optimizer.py`. Before new Refinery risk mathematics is introduced, the project must complete the metric-authority/parity phase described in `docs/PHASE_MINUS1_GOVERNANCE.md` and `docs/adr/0001-runtime-and-quant-authority.md`, so Scanner/legacy metrics, Portfolio v3 metrics, and Refinery do not diverge into independent formula authorities.
