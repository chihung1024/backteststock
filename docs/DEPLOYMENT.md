# Deployment Runbook

Status: **Current operational deployment/runbook contract.** Query live GitHub/Vercel/Cloudflare state before release; this file defines procedures, not cached status.

## 1. Topology

```text
Browser
→ Cloudflare Worker + static assets + D1
→ Vercel Python/Node functions
→ shared application/research authorities
```

`vercel.json`, `wrangler.jsonc`, `.github/workflows/` and runtime configuration are authoritative for exact routes/builds/deployment triggers.

## 2. Secrets and configuration

Never place secrets in repository files, PR bodies, screenshots, browser bundles or chat transcripts.

Cloudflare deployment credentials are stored as repository secrets. Feature-specific backend credentials belong in the owning runtime's secret/environment store.

`wrangler.jsonc` contains non-secret Worker configuration such as backend origin. Local development uses `.dev.vars` derived from `.dev.vars.example`; `.dev.vars` is not committed.

## 3. Vercel backend

Current reviewed entrypoints include compatibility APIs plus dedicated Exhaustive, Walk-Forward, Portfolio v3 and Refinery functions as configured in `vercel.json`.

Useful readiness surfaces include:

```text
GET /api/health
GET /api/v3/portfolio/health
GET /api/v1/research/walk-forward/health
POST /api/v1/refinery/preflight
```

Do not invent a new health route solely for deployment ceremony when an existing bounded contract smoke is sufficient.

## 4. Cloudflare Worker / D1

The Cloudflare deployment path owns:

- Worker routing and request guards;
- static asset publication;
- D1 migration application when configured;
- production route smoke tests.

Universe membership publishing is separately owned by `.github/workflows/update-universes.yml`.

A failed new Universe version does not justify overwriting the D1 last-good/current pointer.

## 5. Validation before release

Run validation proportional to the changed behavior.

The repository's broad integration baseline is represented by CI and may include:

```bash
python -m compileall -q api apps scripts
ruff check api apps scripts tests
python -m pytest -q
npm run check
npm run test:worker
npm run test:score
npm run check:portfolio
npm run test:e2e
npx wrangler d1 migrations apply backteststock-universe --local
npx wrangler deploy --dry-run
```

A docs-only change does not require invented production traffic; a runtime/quant/security/data change must receive the relevant targeted and integration verification.

Local success does not override a real failing remote check on the candidate being released.

## 6. Production smoke

Use only scopes touched by the release.

### Edge / compatibility / Universe

Representative routes:

```text
GET  /api/edge-health
GET  /api/health
GET  /api/v2/universes
POST /api/backtest
POST /api/scan
POST /api/optimizer/exhaustive/prepare
POST /api/v2/screener
```

### Portfolio v3

```text
GET  /api/v3/portfolio/health
GET  /api/v3/portfolio/assets/search?q=2330&limit=5
POST /api/v3/portfolio/preflight
POST /api/v3/portfolio/backtests
```

### Walk-Forward

Verify the public Worker route and, when the deployment contract depends on it, the expected backend revision/authority health before accepting the release.

### Refinery

Use a small valid `preflight` for readiness. Use bounded `analyze` only when changed behavior requires end-to-end analysis validation.

Validate that errors do not expose stack traces/secrets and that unavailable evidence remains unavailable rather than becoming zero/partial success.

## 7. Browser/security checks

When applicable verify:

- root and `/portfolio/` load;
- browser API calls remain same-origin through Cloudflare;
- debug/environment endpoints remain unavailable;
- errors do not leak stack traces/secrets;
- Universe/member metadata is coherent;
- Portfolio, Walk-Forward and Refinery preserve their versioned request/data/quant boundaries;
- no new direct foreign data origin appears in the browser.

## 8. Deployment economy

`vercel.json` currently disables automatic Git deployments for `internal-*` branches. That configuration is a simple resource control; do not build a second branch-governance system around it.

Avoid no-op commits or unrelated file changes solely to retrigger deployment. Prefer supported redeployment of the exact intended Git revision when a platform retry is required.

A hosting quota/rate-limit failure is not proof of an application defect, but it also does not turn an unverified revision into a verified one.

## 9. Rollback

Use the system that actually owns the failed state:

- **Source**: Git revert/restore to a known-good revision.
- **Vercel**: promote/redeploy the previous known-good deployment.
- **Cloudflare**: restore/promote the previous known-good Worker/static deployment.
- **D1 Universe**: move `universe_current.version_id` back to a retained known-good version when the defect is membership publication.
- **Data migration**: use the migration/data-specific recovery procedure appropriate to the actual schema/data change.

A GitHub Release/tag copy is not a substitute for D1 or deployment rollback and is not required for ordinary source recovery.

For a production regression, restore the last known good state first when impact warrants it, then perform RCA → minimum correct fix → verification → redeploy.
