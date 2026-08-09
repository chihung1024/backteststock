# Deployment Runbook

## 1. Deploy the Python APIs to Vercel

Import `chihung1024/backteststock` into Vercel. `vercel.json` defines the current Python entrypoints, including legacy/compatibility Flask routes, Scanner/Screener, Exhaustive prepare, and the self-owned FastAPI Portfolio v3 entrypoint `api/portfolio_v3.py`.

Environment variables depend on the enabled features:

- `GIST_RAW_URL`: optional; used by selected screener/ticker-autocomplete compatibility paths.
- `RISK_FREE_RATE`: optional annual rate in decimal form for compatibility metric paths.
- `BACKTEST_FRED_API_KEY` or `FRED_API_KEY`: required only for FRED-dependent Portfolio analytics.

Verify both compatibility and Portfolio v3 health surfaces as applicable:

```text
GET https://<vercel-project>/api/health
GET https://<vercel-project>/api/v3/portfolio/health
```

Portfolio v3 health must return the service/contract/schema versions and the Vercel deployment SHA when available. Health responses must not expose environment variables.

## 2. Configure Cloudflare Worker

Create a Cloudflare API token using the **Edit Cloudflare Workers** custom permission policy. Restrict the token to only the account and zone used by this application.

In GitHub:

`Settings → Secrets and variables → Actions`

Create:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Do not paste token values into source files, issues, pull requests or chat messages.

The token must include Workers Scripts edit and D1 edit permissions. The deploy workflow resolves a database named `backteststock-universe`, creates it in APAC when absent, applies D1 migrations, and then deploys the Worker with the resolved UUID.

## 3. Configure the backend origin

The Cloudflare Worker reads the non-secret Vercel origin from `vars.BACKEND_ORIGIN` in `wrangler.jsonc`. Keep the value as the public HTTPS origin without `/api`.

Example:

```text
https://backteststock-api.vercel.app
```

For local development, copy `.dev.vars.example` to `.dev.vars` and point `BACKEND_ORIGIN` at the appropriate local Python process.

## 4. Deploy Cloudflare

After CI passes and the pull request is merged, the `Deploy Cloudflare Worker` workflow runs automatically for matching Worker, public-asset, migration, and deployment-script changes; it can also be started manually. It:

- resolves or creates `backteststock-universe`;
- applies `migrations/*.sql` remotely;
- publishes `public/` as Cloudflare Static Assets;
- publishes `worker/router.js` as the API entrypoint;
- keeps Portfolio v3 behind an explicit route allowlist;
- gives exhaustive prepare its separate larger request boundary;
- delegates remaining compatibility proxy/security handling to `worker/index.js`.

Then run `Update Universe Membership` once with `dry_run=false`. Confirm all configured sources are published in the uploaded `universe-update-report` artifact. The same workflow runs on its configured schedule.

## 5. Production smoke tests

Run after every relevant production deployment:

```text
GET /api/edge-health
GET /api/health
GET /api/v2/universes
POST /api/backtest with one 100% SPY portfolio
POST /api/scan with SPY and QQQ
POST /api/optimizer/exhaustive/prepare with a small fixed source pool
POST /api/v2/screener with one available Universe and limit null
GET /api/v3/portfolio/health
GET /api/v3/portfolio/assets/search?q=2330&limit=5
POST /api/v3/portfolio/preflight with a small mixed-market portfolio
POST /api/v3/portfolio/backtests with the same portfolio
```

The Portfolio production smoke must wait until `/api/v3/portfolio/health` reports the same deployment SHA as the GitHub commit being deployed before validating search/preflight/backtest behavior. This prevents a Cloudflare deployment from being accepted while Vercel is still serving an older backend deployment.

Confirm:

- Static page and `/portfolio/` load without unexpected third-party runtime dependencies.
- Browser API requests use the Cloudflare origin.
- `/api/debug` returns 404.
- Error responses do not contain stack traces or environment variables.
- Cloudflare and Vercel logs share the `x-request-id` response header where proxied.
- Universes show `available: true`, a source date, version, and non-zero member count.
- The Russell 2000 option visibly discloses that IWM holdings are a proxy.
- The screener response returns every passing candidate when `limit` is `null`.
- A browser scan of more than 100 mock candidates completes in bounded batches and paginates the final table.
- A simulated partial `/api/scan` response requeues only the missing ticker; a saved in-progress job resumes after reload without requesting completed tickers again.
- Exhaustive prepare reports `valuationCurrency: "TWD"`, a TWD valuation-contract version, and no silently omitted requested source ticker.
- Portfolio v3 preflight explicitly reports per-asset success/failure and does not silently alter requested membership.
- Portfolio v3 backtest returns contract/schema/reproducibility metadata, and its deployment SHA readiness check matches the GitHub deployment under test.

## 6. Release backup and merge governance

`.github/workflows/release-backups.yml` is the canonical generic pre/post merge backup gate. Runtime or quantitative-methodology PRs must use the `release-backup` label so the current `main` is backed up before merge and the merged SHA is backed up afterward.

Historical one-off PR backup workflows are not active governance mechanisms once superseded by the generic workflow; Git history and existing Releases preserve their evidence.

Before Portfolio Refinery Phase 0 starts, repository settings for `main` must enforce PR-only changes, required status checks, no force pushes, and no branch deletion. Source code cannot substitute for those repository-level controls.

## Rollback

- Cloudflare: roll back to the previous Worker deployment or disable the route/custom domain.
- Vercel: promote the previous verified deployment.
- D1 data: point `universe_current.version_id` back to a retained prior version if only constituent data needs rollback.
- PR-scoped rollback: restore the verified `backup-pre-pr<PR>-<SHA>` Release created by the generic release-backup gate.
- Do not revoke or remove an old runtime path until its replacement has passed CI, production smoke, and user-journey checks.
