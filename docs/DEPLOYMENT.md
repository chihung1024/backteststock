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

## 3. Configure the backend origin

The Cloudflare Worker needs a secret named `BACKEND_ORIGIN` containing the Vercel origin without `/api`:

```bash
npx --yes wrangler@4 secret put BACKEND_ORIGIN
```

Example value:

```text
https://backteststock-api.vercel.app
```

For local development, copy `.dev.vars.example` to `.dev.vars`.

## 4. Deploy Cloudflare

After CI passes and the pull request is merged, manually run the `Deploy Cloudflare Worker` workflow. It deploys:

- `public/` as Cloudflare Static Assets.
- `worker/index.js` as the API proxy and security layer.

The GitHub `production` environment can be configured with required reviewers to prevent accidental deployment. After the first production deployment and smoke test succeed, the workflow may be changed to deploy automatically on `main`.

## 5. Smoke tests

Run after every production deployment:

```text
GET /api/edge-health
GET /api/health
POST /api/backtest with one 100% SPY portfolio
POST /api/scan with SPY and QQQ
```

Confirm:

- Static page loads without third-party CDN requests.
- Browser API requests use the same Cloudflare origin.
- `/api/debug` returns 404.
- Error responses do not contain stack traces or environment variables.
- Cloudflare and Vercel logs share the `x-request-id` response header.

## Rollback

- Cloudflare: roll back to the previous Worker deployment or disable the route/custom domain.
- Vercel: promote the previous deployment.
- Do not revoke the old backend until Cloudflare smoke tests and user journeys pass.
