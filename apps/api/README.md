# Unified API application core

`apps/api/app/` is the framework-neutral shared application core used by the current production/research APIs. The repository intentionally contains both compatibility Flask entrypoints and self-owned FastAPI domains; framework type is not the semantic authority boundary.

For live project status, read root `to_do_update_list.md`. For document precedence, read `docs/PROJECT_DOCUMENTATION_POLICY.md`.

## Current runtime relationship

```text
Vercel Python Functions
├─ Flask compatibility / historical-product entrypoints
│  ├─ api/index_v2.py
│  ├─ api/scan_v2.py
│  ├─ api/screener.py
│  └─ api/exhaustive_optimizer.py
│
├─ FastAPI Portfolio v3
│  └─ api/portfolio_v3.py
│
└─ FastAPI Refinery v1
   └─ api/refinery_v1.py

All consume reviewed authorities under apps/api/app/.
```

Cloudflare Worker/static assets provide the browser-facing same-origin boundary and fixed API routing/guards. They do not replace the Python quantitative authority.

## Shared authorities

### `app/data/`

Market-data, FX, TWD valuation and return-component authority.

Core invariant:

```text
TWD adjusted close = native adjusted close × (TWD per native currency unit)
```

The existing audited calendar/forward-fill policies prohibit future-data backfill and keep native/FX/TWD components traceable.

### `app/portfolio/`

Portfolio v3 ledger, cash-flow/path-dependent analytics, contracts and orchestration.

This domain is not a generic research container. Refinery must not import Portfolio ledger models simply to reuse a convenient data shape.

### `app/research/`

Reproducible research-domain data/services, including `ResearchDatasetV1` and shared research-data adapters such as the Kenneth French factor provider.

Rules:

- ResearchDataset consumes the existing audited TWD history authority; it is not a second candidate-price downloader.
- Shared external research adapters must expose source/provenance and remain distinct from the primary market-price authority.
- Dataset identity and downstream analytical seed/model identity are not automatically the same concept.

### `app/quant/`

Pure validated quantitative primitives such as covariance/correlation, effective-dimension, clustering and factor relationship mathematics.

Rules:

- no HTTP/UI/storage side effects;
- no hidden stock selection/sizing policy;
- deterministic/versioned inputs where semantics require it;
- reference/invariant/metamorphic tests for mathematical behavior.

### `app/refinery/`

Read-only Portfolio Refinery request/service/evidence composition.

The Refinery may combine ResearchDataset + Risk Mathematics + versioned Phase 5 relationship evidence, but it must preserve:

- complete requested candidate membership or fail closed;
- candidate/benchmark sample isolation;
- explicit unavailable evidence;
- no hidden equal-weight portfolio;
- no KEEP/TRIM/REPLACE, sizing or OOS recommendation semantics before later validated phases.

## Current research flow

```text
TWDHistoryService
   |
   v
ResearchDatasetV1
   |
   +--> Risk Mathematics
   |       |
   |       v
   +--> Refinery service/API
           |
           +--> Phase 4 risk/correlation diagnostics
           +--> Phase 5 clustering/redundancy/factor/theme evidence
```

The browser consumes returned evidence; it does not become a second calculation authority.

## Contract references

- `docs/UNIFIED_TWD_CONTRACT.md`
- `docs/quant/METRIC_AUTHORITY.md`
- `docs/quant/RETURN_SEMANTICS.md`
- `docs/quant/RISK_MODEL_POLICY.md`
- `docs/quant/RISK_MATHEMATICS_V1.md`
- `docs/research/RESEARCH_DATASET_V1.md`
- `docs/research/REFINERY_API_V1.md`
- `docs/research/REFINERY_UI_V1.md`
- `docs/research/REFINERY_CLUSTERING_V1.md`
- `docs/research/PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md` while Phase 5 review is active

## Extension rules

1. Do not add new Refinery logic to legacy `api/index.py` or `api/optimizer.py`.
2. Do not introduce a second ticker/FX/TWD calendar authority for convenience.
3. Quantitative semantic changes require contract/version/test review, not just code edits.
4. Preserve Portfolio ledger and Refinery research boundaries.
5. Do not convert unavailable data into zero or silently drop failed candidates.
6. Full-period historical research is not OOS evidence.
7. Update root `to_do_update_list.md` when the active phase/batch/decision/root-cause state changes.
