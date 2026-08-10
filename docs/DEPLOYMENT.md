# Deployment Runbook

Status: Current deployment/runbook contract. Live deployment/check/ruleset state must still be queried before release; this file defines the expected procedure, not a cached status page.

## 1. Deploy Python APIs to Vercel

Import `chihung1024/backteststock` into Vercel. `vercel.json` defines the reviewed Python entrypoints, including:

- legacy/compatibility Flask routes;
- Scanner / Screener;
- Exhaustive prepare;
- self-owned FastAPI Portfolio v3 — `api/portfolio_v3.py`;
- read-only FastAPI Refinery v1 — `api/refinery_v1.py`.

Environment variables depend on enabled features:

- `GIST_RAW_URL`: optional; selected screener/ticker-autocomplete compatibility paths;
- `RISK_FREE_RATE`: optional annual rate in decimal form for compatibility metric paths;
- `BACKTEST_FRED_API_KEY` or `FRED_API_KEY`: only for FRED-dependent Portfolio analytics;
- other provider settings only when explicitly documented by the owning feature contract.

Never add secrets to repository files, issues, PR bodies, screenshots, browser bundles or chat transcripts.

### Vercel readiness surfaces

Portfolio v3 has an explicit health route:

```text
GET https://<vercel-project>/api/health
GET https://<vercel-project>/api/v3/portfolio/health
```

Portfolio v3 health must expose expected service/contract/schema/deployment identity without environment values.

Refinery v1 intentionally exposes only reviewed POST operations in production:

```text
POST https://<vercel-project>/api/v1/refinery/preflight
POST https://<vercel-project>/api/v1/refinery/analyze
```

Do **not** invent or depend on a Refinery health endpoint that the production contract does not provide. Use a small valid `preflight` as the Refinery readiness/contract smoke, then one bounded `analyze` only when the deployment change requires end-to-end analysis validation.

## 2. Configure Cloudflare Worker

Create a Cloudflare API token with only the account/zone permissions required by the existing deployment workflow. At minimum, current workflow responsibilities require Workers Scripts and D1 edit capabilities.

In GitHub:

```text
Settings -> Secrets and variables -> Actions
```

Configure the secrets used by the workflow, including:

```text
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
```

The deploy workflow resolves the `backteststock-universe` D1 database, applies migrations, publishes Worker/static assets and retains the configured backend origin.

## 3. Configure backend origin

Cloudflare Worker reads non-secret Vercel origin from `vars.BACKEND_ORIGIN` in `wrangler.jsonc`.

Use only the HTTPS origin, without `/api`, for example:

```text
https://backteststock-api.vercel.app
```

For local development, copy `.dev.vars.example` to `.dev.vars` and point `BACKEND_ORIGIN` to the local Python origin. `.dev.vars` must not be committed.

## 4. Validate before production deploy

Apply the validation scope required by the changed files. For a full runtime/quant PR the expected baseline includes:

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

Required GitHub checks and release-backup evidence are authoritative merge gates; local PASS is supplemental.

A docs-only PR may have zero runtime impact radius, but if repository CI runs the full suite, use that result as regression evidence rather than disabling it.

## 5. Deploy Cloudflare

After the relevant PR is merged and required checks pass, `Deploy Cloudflare Worker` runs automatically for configured Worker/public/migration/deployment-path changes and may also be started manually when appropriate.

Current responsibilities include:

- resolve/create `backteststock-universe`;
- apply `migrations/*.sql` remotely;
- publish `public/` static assets;
- publish `worker/router.js` as API entrypoint;
- keep Portfolio v3 behind an explicit allowlist;
- keep Refinery v1 behind an explicit POST-only allowlist;
- retain separate Exhaustive request boundary;
- delegate compatibility proxy/security behavior to reviewed Worker code.

When Universe data/schema changed, run/update the Universe workflow according to its contract and verify the produced report before moving current pointers.

## 6. Production smoke tests

Run after every relevant production deployment. Scope the smoke to changed domains but preserve core cross-domain regressions for broad runtime releases.

### Edge / compatibility / Universe

```text
GET  /api/edge-health
GET  /api/health
GET  /api/v2/universes
POST /api/backtest                         small known portfolio
POST /api/scan                             small known ticker set
POST /api/optimizer/exhaustive/prepare     small fixed source pool
POST /api/v2/screener                      one available Universe, bounded request
```

### Portfolio v3

```text
GET  /api/v3/portfolio/health
GET  /api/v3/portfolio/assets/search?q=2330&limit=5
POST /api/v3/portfolio/preflight           small mixed-market portfolio
POST /api/v3/portfolio/backtests           same validated portfolio
```

Portfolio smoke must wait until its health response identifies the Vercel deployment corresponding to the GitHub commit under test before the Cloudflare deployment is accepted. This prevents a Vercel/Cloudflare deployment race.

### Refinery v1

There is no production Refinery health route. Use:

```text
POST /api/v1/refinery/preflight
POST /api/v1/refinery/analyze   # only when end-to-end analysis behavior changed / requires verification
```

Use a small valid 2+ candidate request and a bounded historical interval. Validate:

- response contract remains `refinery-v1`;
- `X-Refinery-API-Schema-Version` matches the expected deployed schema;
- requested candidate membership is preserved;
- incomplete data fails closed rather than silently shrinking membership;
- no-weight request does not fabricate equal weights;
- benchmark failure, when intentionally exercised, disables only conditional evidence;
- Phase 5 fields/methodology version are present only when the merged contract actually includes them;
- theme/factor/unavailable evidence remains explicit rather than numeric fallback;
- no stack trace, environment or secret disclosure.

Do not use a high-cardinality production analyze as a smoke test; resource/capacity behavior belongs in controlled CI/performance validation.

## 7. Browser / security smoke checklist

Confirm, as applicable:

- root static page and `/portfolio/` load without unexpected third-party runtime dependencies;
- Scanner/Portfolio/Refinery browser API requests remain same-origin through Cloudflare;
- `/api/debug` remains unavailable;
- errors do not expose stack traces/environment variables;
- proxied response/request-id behavior remains traceable;
- Universe responses show valid available/source-date/version/member evidence;
- Russell 2000 proxy disclosure remains visible;
- screener `limit=null` semantics remain unchanged where required;
- large Scanner jobs retain bounded batching/resume behavior;
- Exhaustive prepare reports TWD valuation contract and no silent source omission;
- Portfolio v3 preserves requested membership and reproducibility metadata;
- Refinery workspace remains isolated from Portfolio storage/request models;
- Refinery large pair/correlation presentation remains bounded on desktop/mobile when Phase 5 is deployed.

## 8. Release backup and merge governance

`.github/workflows/release-backups.yml` is the generic pre/post merge recovery mechanism for runtime or quantitative-methodology PRs according to repository workflow/labels.

Historical one-off PR backup workflows are not current governance merely because their files/history still exist.

Before every important merge:

1. query the **actual current** GitHub default-branch ruleset;
2. confirm expected required checks apply to the exact final head;
3. complete the independent review required by `AI_PROJECT_PLAYBOOK.md` / live roadmap;
4. confirm recovery point / pre-merge backup where required;
5. merge only by allowed non-bypass method;
6. verify post-main checks/deployment/smoke before declaring the phase closed.

Do not encode changing approval-count/strictness values here as permanent fact. If the actual ruleset is weaker than the governance baseline, record the drift in `to_do_update_list.md` and address it in an explicit governance Batch rather than silently assuming protection exists.

## 9. Vercel / hosting quota failures

A Vercel check that fails because of deployment/build-rate quota is not evidence of an application build failure, but it is also **not permission to remove the required check**.

For a final merge head:

- classify quota/rate-limit evidence separately from code/build failure;
- avoid generating unnecessary preview deployments during high-commit churn;
- require an actual green Vercel status when repository protection requires it;
- change hosting plan/workflow policy only in a separately reviewed governance/deployment Batch.

## 10. Rollback

- **Cloudflare**: restore/promote the previous verified Worker deployment or disable the affected route/domain as appropriate.
- **Vercel**: promote the previous verified deployment.
- **D1 membership data**: point `universe_current.version_id` to a retained prior good version if only constituent data requires rollback.
- **PR-scoped source recovery**: restore/revert to the verified pre-merge release/checkpoint recorded by the release-backup workflow.
- **Phase regression**: prefer last known good production candidate first, then RCA/fix/verify/redeploy.

Never remove an old runtime path until its replacement has passed required CI, deployment verification, smoke and core user-journey checks.
