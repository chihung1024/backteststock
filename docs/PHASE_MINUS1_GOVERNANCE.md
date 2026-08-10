# Phase -1 — Governance & Architecture Hardening

Status: **HISTORICAL / CLOSED / PASS.**

This document preserves the Phase -1 architecture/governance hardening baseline and its original exit criteria. It is **not** the current engineering-governance authority and must not be used as live project status.

Current authorities:

- engineering governance: `AI_PROJECT_PLAYBOOK.md` (V3.0);
- durable product/runtime overview: `README.md` + `docs/adr/0001-runtime-and-quant-authority.md`;
- live Phase/Batch state: `to_do_update_list.md`;
- current remote checks/rulesets/deployments: query GitHub/Vercel/Cloudflare before acting.

Baseline main content for this historical phase: commit `35fe0e3f9c4ff5fc5f49b4abafeba3f5e6691a0c`.

## Objective

Harden repository governance and establish one architecture source of truth before Portfolio Refinery runtime or quantitative-model work began.

This phase was intentionally non-functional: it did not change portfolio calculations, scanner behavior, exhaustive-optimizer behavior, API responses, or production routing.

## Production architecture authority at Phase -1

The production surfaces recorded at the time were:

- Cloudflare Worker + static assets: browser entrypoint, static assets, D1 Universe access, request guards, and explicit API proxy routing.
- Vercel Python functions:
  - legacy/compatibility Flask surfaces under existing `/api/*` routes;
  - self-owned FastAPI Portfolio v3 at `api/portfolio_v3.py` for `/api/v3/portfolio/*`.
- Framework-neutral shared application core under `apps/api/app/`.
- Portfolio v3 React application under `apps/portfolio-web/`, published as `/portfolio/` static assets.
- D1 versioned Universe storage with last-good/current pointers.

Later phases added Refinery v1 and additional research/quant domains; use current README/ADR/implementation for current architecture rather than extending this historical snapshot.

## Runtime inventory recorded at the time

| Path | Historical classification | Notes |
| --- | --- | --- |
| `api/index.py` | legacy compatibility | Historical Flask implementation retained for compatibility. |
| `api/index_v2.py` | production compatibility | Deterministic legacy-compatible backtest API wrapper using shared TWD services. |
| `api/scan.py` | legacy compatibility | Retained legacy scan surface. |
| `api/scan_v2.py` | production | Scan path using shared TWD data. |
| `api/screener.py` | production | Universe/screener backend. |
| `api/optimizer.py` | legacy / compatibility | Existing optimizer implementation; new Refinery functionality was prohibited here. |
| `api/exhaustive_optimizer.py` | production research | Full-period exhaustive historical search/preparation path; research/exploration, not OOS validation. |
| `api/portfolio_v3.py` | production | Self-owned FastAPI Portfolio v3 entrypoint. |
| `apps/api/app/data/` | production shared core | TWD valuation, FX, return components, audited history services. |
| `apps/api/app/portfolio/` | production shared core | Portfolio v3 ledger, metrics, analytics, contracts and service layer. |
| `apps/portfolio-web/` | production | Standalone React/TypeScript Portfolio workspace. |
| `worker/router.js` | production | Explicit route allowlist/proxy. |

## Governance requirements recorded at Phase -1

The phase required PR-only changes to `main`, no force pushes/deletion, required CI/status checks, generic release backup for runtime changes, and a consistent merge policy. Repository-setting enforcement was intentionally separate from source code.

These requirements are historical evidence. Current merge/review/backup applicability is governed by V3.0 risk-proportional policy plus the actual current GitHub ruleset.

## Release-backup decision

`.github/workflows/release-backups.yml` became the canonical generic backup mechanism. Historical one-off PR backup workflows were retired from active source after the generic workflow was verified. Historical Releases and Git history preserve their evidence; one-off workflow files are not required in the current tree.

## Historical exit criteria

- architecture documentation matched deployed runtime at phase close;
- runtime inventory was explicit;
- obsolete one-off backup workflow files were removed;
- generic release-backup workflow remained active;
- existing runtime behavior was unchanged;
- main protection settings were confirmed before Phase 0.

## Historical non-goals

- no Portfolio Refinery API/UI;
- no covariance/correlation/clustering/selection/sizing implementation;
- no metric-formula refactor;
- no optimizer behavior change;
- no production-route change.
