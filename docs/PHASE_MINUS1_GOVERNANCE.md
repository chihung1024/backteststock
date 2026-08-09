# Phase -1 — Governance & Architecture Hardening

Status: implementation baseline for the Portfolio Refinery program.

Baseline main content: commit `35fe0e3f9c4ff5fc5f49b4abafeba3f5e6691a0c` (the temporary documentation-only direct write was reverted before this branch was created).

## Objective

Harden repository governance and establish one current architecture source of truth before any Portfolio Refinery runtime or quantitative-model work begins.

This phase is intentionally non-functional: it must not change portfolio calculations, scanner behavior, exhaustive-optimizer behavior, API responses, or production routing.

## Production architecture authority

The current production surfaces are:

- Cloudflare Worker + static assets: browser entrypoint, static assets, D1 Universe access, request guards, and explicit API proxy routing.
- Vercel Python functions:
  - legacy/compatibility Flask surfaces under existing `/api/*` routes;
  - self-owned FastAPI Portfolio v3 at `api/portfolio_v3.py` for `/api/v3/portfolio/*`.
- Framework-neutral shared application core under `apps/api/app/`.
- Portfolio v3 React application under `apps/portfolio-web/`, published as `/portfolio/` static assets.
- D1 versioned Universe storage with last-good/current pointers.

`README.md`, `apps/api/README.md`, and `docs/DEPLOYMENT.md` are required to describe this current state and must not describe FastAPI as a future-only cutover.

## Runtime inventory

| Path | Classification | Notes |
| --- | --- | --- |
| `api/index.py` | legacy compatibility | Historical Flask implementation still imported by compatibility wrappers. Do not extend for new Portfolio Refinery work. |
| `api/index_v2.py` | production compatibility | Deterministic legacy-compatible backtest API wrapper using shared TWD services. |
| `api/scan.py` | legacy compatibility | Retained legacy scan surface. |
| `api/scan_v2.py` | production | Current scan path using shared TWD data. |
| `api/screener.py` | production | Universe/screener backend. |
| `api/optimizer.py` | legacy / compatibility | Existing optimizer implementation; no new Refinery functionality should be added here. |
| `api/exhaustive_optimizer.py` | production research | Full-period exhaustive historical search/preparation path. Treat as research/exploration, not out-of-sample validation. |
| `api/portfolio_v3.py` | production | Self-owned FastAPI Portfolio v3 entrypoint. |
| `apps/api/app/data/` | production shared core | TWD valuation, FX, return components, and audited history services. |
| `apps/api/app/portfolio/` | production shared core | Portfolio v3 ledger, metrics, analytics, contracts, and service layer. |
| `apps/portfolio-web/` | production | Standalone React/TypeScript Portfolio workspace. |
| `worker/router.js` | production | Explicit route allowlist/proxy for Portfolio v3 and exhaustive prepare. |

## Governance requirements

Before Phase 0 begins, GitHub repository settings for `main` must enforce:

1. Pull-request-only changes to `main`.
2. No force pushes.
3. No branch deletion.
4. Required CI/status checks for merge.
5. Runtime-changing PRs must use the generic `release-backup` gate.
6. Prefer one repository merge policy consistent with expected-head and backup verification; squash merge is the recommended policy.

Repository-settings enforcement is intentionally separate from source code. The current connector cannot modify branch-protection settings, so confirmation of these settings is an explicit Phase -1 exit gate rather than an implicit assumption.

## Release-backup policy

`.github/workflows/release-backups.yml` is the canonical generic backup mechanism.

Historical one-off PR backup workflows are retired from active source after the generic workflow is verified. Historical Releases and Git history remain immutable evidence; one-off workflow files are not required to preserve that history.

## Phase exit criteria

- Current architecture documentation matches deployed runtime.
- Runtime inventory is explicit.
- Obsolete one-off backup workflow files are removed.
- Generic release-backup workflow remains unchanged and active.
- Existing CI/runtime behavior is unchanged.
- `main` protection settings above are confirmed before Phase 0 starts.

## Explicit non-goals

- No Portfolio Refinery API.
- No Portfolio Refinery UI.
- No covariance, correlation, clustering, selection, or sizing implementation.
- No metric-formula refactor.
- No optimizer behavior change.
- No production-route change.
