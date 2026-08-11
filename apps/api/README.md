# Unified API application core

`apps/api/app/` is the framework-neutral shared application core used by current production/research APIs. The repository intentionally contains compatibility Flask entrypoints and self-owned FastAPI domains; framework type is not the semantic authority boundary.

For live project status read root `to_do_update_list.md`; for document precedence read `docs/PROJECT_DOCUMENTATION_POLICY.md`.

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

Cloudflare Worker/static assets provide the browser-facing same-origin routing/guard boundary; they do not replace Python quantitative/data authorities.

## Shared authorities

### `app/data/`

Market-data, FX, TWD valuation and return-component authority.

```text
TWD adjusted close = native adjusted close × (TWD per native currency unit)
```

Existing audited calendar/forward-fill policies prohibit future-data backfill and keep native/FX/TWD components traceable.

### `app/portfolio/`

Portfolio v3 ledger, cash-flow/path-dependent analytics, contracts and orchestration. This domain is not a generic research container; Refinery must not absorb Portfolio ledger models for convenience.

### `app/research/`

Reproducible research-domain data/services including `ResearchDatasetV1` and shared research-data adapters. ResearchDataset consumes the audited TWD history authority; it is not a second candidate-price downloader. Dataset identity and downstream analytical/model identity are not automatically the same concept.

### `app/quant/`

Pure validated quantitative primitives such as covariance/correlation/effective-dimension mathematics. Rules:

- no HTTP/UI/storage side effects;
- no hidden stock-selection/sizing policy;
- deterministic/versioned inputs where semantics require it;
- reference/invariant/boundary tests appropriate to mathematical risk.

Phase 5 clustering/factor primitives remain work-in-progress until their reviewed branch is merged; documentation on `main` must not present them as already accepted production methodology.

### `app/refinery/`

Read-only Portfolio Refinery request/service/evidence composition. Current merged behavior combines ResearchDataset + Risk Mathematics while preserving:

- complete requested candidate membership or fail closed;
- candidate/benchmark sample isolation;
- explicit unavailable evidence;
- no hidden equal-weight portfolio;
- no KEEP/TRIM/REPLACE, sizing or OOS recommendation semantics before later validated phases.

## Current merged research flow

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
           +--> read-only risk/covariance/correlation diagnostics
           +--> Refinery workspace presentation
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

Active Phase-specific contracts/review plans belong on their working branch and become `main` authority only when accepted/merged.

## Extension rules

1. Do not add new Refinery logic to legacy `api/index.py` or `api/optimizer.py`.
2. Do not introduce a second ticker/FX/TWD calendar authority for convenience.
3. Quantitative semantic changes require contract/version/test review, not just code edits.
4. Preserve Portfolio ledger and Refinery research boundaries.
5. Do not convert unavailable data into zero or silently drop failed candidates.
6. Full-period historical research is not OOS evidence.
7. Update root `to_do_update_list.md` when active phase/batch/decision/root-cause state changes.
