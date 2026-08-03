# Deployment Runbook

## 1. Deploy the Python API to Vercel

1. Import `chihung1024/backteststock` into Vercel.
2. Vercel will use `vercel.json` and expose the Flask routes under `/api/*`.
3. Add environment variables:
   - `GIST_RAW_URL`: optional, required for the screener and ticker autocomplete.
   - `RISK_FREE_RATE`: optional annual rate in decimal form, such as `0.04`.
4. Verify:

```text
GET https://<vercel-project>/api/health
```

The response must contain only service status and must not expose environment variables.

## 2. Configure Cloudflare Worker

Create a Cloudflare API token using the **Edit Cloudflare Workers** custom permission policy. Restrict the token to only the account and zone used by this application.

In GitHub:

`Settings → Secrets and variables → Actions`

Create:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Do not paste token values into source files, issues, pull requests or chat messages.

The token must include Workers Scripts edit and D1 edit permissions. The deploy workflow resolves a
database named `backteststock-universe`, creates it in APAC when absent, applies D1 migrations, and then
deploys the Worker with the resolved UUID.

## 3. Configure the backend origin

The Cloudflare Worker reads the non-secret Vercel origin from
`vars.BACKEND_ORIGIN` in `wrangler.jsonc`. Keep the value as the public HTTPS
origin without `/api`.

Example value:

```text
https://backteststock-api.vercel.app
```

For local development, copy `.dev.vars.example` to `.dev.vars`.

## 4. Deploy Cloudflare

After CI passes and the pull request is merged, the `Deploy Cloudflare Worker`
workflow runs automatically for matching Worker, public-asset, migration, and
deployment-script changes; it can also be started manually. It:

- Resolves or creates `backteststock-universe`.
- Applies `migrations/*.sql` remotely.
- `public/` as Cloudflare Static Assets.
- `worker/router.js` as the API entrypoint: it gives the exhaustive-preflight
  route its larger signed-snapshot boundary, then delegates all other API
  proxy and security handling to `worker/index.js`.

Then run `Update Universe Membership` once with `dry_run=false`. Confirm all four sources are published
in the uploaded `universe-update-report` artifact. The same workflow runs every Monday and Thursday.

The GitHub `production` environment can be configured with required reviewers to prevent accidental deployment. After the first production deployment and smoke test succeed, the workflow may be changed to deploy automatically on `main`.

## 5. Smoke tests

Run after every production deployment:

```text
GET /api/edge-health
GET /api/health
GET /api/v2/universes
POST /api/backtest with one 100% SPY portfolio
POST /api/scan with SPY and QQQ
POST /api/optimizer/exhaustive/prepare with a small fixed source pool
POST /api/v2/screener with one available Universe and limit null
```

Confirm:

- Static page loads without third-party CDN requests.
- Browser API requests use the same Cloudflare origin.
- `/api/debug` returns 404.
- Error responses do not contain stack traces or environment variables.
- Cloudflare and Vercel logs share the `x-request-id` response header.
- All four Universes show `available: true`, a source date, version, and non-zero member count.
- The Russell 2000 option visibly discloses that IWM holdings are a proxy.
- The screener response returns every passing candidate when `limit` is `null`.
- A browser scan of more than 100 mock candidates completes in batches of at most 100 and paginates
  the final table.
- A simulated partial `/api/scan` response requeues only the missing ticker; a saved in-progress job
  resumes after reload without requesting completed tickers again.
- The exhaustive-preflight response summary reports `valuationCurrency: "TWD"`,
  a TWD valuation-contract version, and no silently omitted source ticker.

## Rollback

- Cloudflare: roll back to the previous Worker deployment or disable the route/custom domain.
- Vercel: promote the previous deployment.
- D1 data: point `universe_current.version_id` back to a retained prior version if only constituent data
  needs rollback.
- Full pre-stage rollback: restore GitHub Release tag `backup-2026-07-29-5e841f1`.
- Do not revoke the old backend until Cloudflare smoke tests and user journeys pass.
