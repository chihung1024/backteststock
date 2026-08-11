# Deployment Runbook

Status: **Current deployment/runbook contract.** Live check, ruleset and deployment state must be queried before release; this file defines procedure, not a cached status page.

## 1. Vercel Python APIs

`vercel.json` defines reviewed Python entrypoints including:

- legacy/compatibility Flask routes;
- Scanner / Screener;
- Exhaustive prepare;
- FastAPI Portfolio v3 — `api/portfolio_v3.py`;
- read-only FastAPI Refinery v1 — `api/refinery_v1.py`.

Environment variables depend on enabled features. Existing examples include `GIST_RAW_URL`, `RISK_FREE_RATE`, and FRED credentials used only by features that own them. Never add secrets to repository files, PR bodies, screenshots, browser bundles or chat transcripts.

### Readiness / smoke surfaces

Portfolio v3 exposes an explicit health route:

```text
GET https://<vercel-project>/api/health
GET https://<vercel-project>/api/v3/portfolio/health
```

Refinery v1 intentionally exposes reviewed POST operations rather than a fabricated health endpoint:

```text
POST https://<vercel-project>/api/v1/refinery/preflight
POST https://<vercel-project>/api/v1/refinery/analyze
```

Use a small valid `preflight` for Refinery readiness/contract smoke. Use bounded `analyze` only when the changed behavior requires end-to-end analysis validation.

## 2. Cloudflare Worker / D1

GitHub Actions deployment uses Cloudflare credentials stored only as repository secrets, including:

```text
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
```

The deployment workflow resolves `backteststock-universe`, applies D1 migrations, publishes Worker/static assets and uses the configured backend origin.

`wrangler.jsonc` stores non-secret `BACKEND_ORIGIN` as the Vercel HTTPS origin without `/api`. For local development, copy `.dev.vars.example` to `.dev.vars`; `.dev.vars` must not be committed.

## 3. Validation before merge/deploy

Validation scope follows `AI_PROJECT_PLAYBOOK.md` risk classification. A broad runtime/quant candidate normally includes:

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

Required GitHub checks are authoritative merge gates; local PASS is supplemental. Docs-only changes do not require invented production smoke, although repository CI may still run broad regression and provide useful evidence.

## 4. Cloudflare deployment

`Deploy Cloudflare Worker` runs automatically for its configured Worker/public/migration/deployment paths and can be manually dispatched when appropriate. Its current responsibilities include:

- resolve/create D1;
- apply migrations;
- publish `public/` static assets;
- publish Worker routing;
- keep Portfolio v3 behind explicit routes;
- keep Refinery v1 behind explicit POST-only routes;
- preserve the separate Exhaustive request boundary;
- execute configured production smoke tests.

Universe membership publishing is owned by `Update Universe Membership`; validate its report before relying on a newly published membership version.

## 5. Production smoke tests

Run only the scopes applicable to the deployment while preserving broad cross-domain checks for broad runtime releases.

### Edge / compatibility / Universe

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

Where deployment-SHA readiness is part of the Portfolio contract, wait until Vercel reports the expected deployment before accepting downstream Cloudflare smoke.

### Refinery v1

```text
POST /api/v1/refinery/preflight
POST /api/v1/refinery/analyze   # when analysis behavior changed
```

Validate requested candidate membership, fail-closed incomplete data, schema/methodology metadata, explicit unavailable evidence and absence of stack traces/secrets. Do not use a high-cardinality production analyze as a smoke test.

## 6. Browser / security checklist

As applicable, confirm:

- root and `/portfolio/` load;
- browser API calls remain same-origin through Cloudflare;
- `/api/debug` remains unavailable;
- errors do not expose stack traces/environment variables;
- request IDs remain traceable where proxied;
- Universe metadata/member counts are valid;
- Exhaustive prepare preserves requested sources and TWD contract metadata;
- Portfolio v3 preserves requested membership/reproducibility metadata;
- Refinery workspace remains isolated from Portfolio persistence/request models.

## 7. Release backup / merge governance

`.github/workflows/release-backups.yml` is the generic pre/post merge recovery mechanism when the V3 risk classification/Batch requires it.

Historical one-off backup/apply/diagnostic workflows are not current governance simply because GitHub retains old workflow registrations or run history. Current source-tree workflow authority is `.github/workflows/` on the candidate branch.

Before an important merge:

1. query actual current branch/ruleset/check state;
2. confirm required checks apply to the exact final head;
3. complete the review level required by V3 risk classification;
4. confirm recovery point where required;
5. merge only by an allowed non-bypass method;
6. verify post-main deployment/smoke only when applicable.

Do not encode volatile approval-count/strictness values here as permanent facts.

## 8. Hosting quota / Vercel deployment economy

A Vercel rate/quota failure is not proof of an application build defect, but it is also not permission to remove a required check. Classify external failures separately and require a genuine green required status when branch protection requires one.

Repository policy is defined in [`VERCEL_DEPLOYMENT_ECONOMY.md`](VERCEL_DEPLOYMENT_ECONOMY.md). The core operating model is:

```text
internal-<batch>    -> implementation / RCA / repeated GitHub CI; automatic Vercel deployment disabled
candidate-<batch>   -> converged merge candidate; Vercel Preview enabled
main                -> production deployment
```

`vercel.json` disables Git deployments for branch names matching `internal-*`; unspecified branches remain deployment-enabled. Do not open an `internal-*` branch as the final merge candidate because the required Vercel status is intentionally absent there.

For a normal Batch, target one final Preview deployment, plus at most one additional Preview after a real material blocker fix. This is an operational budget, not a substitute for risk-proportional validation.

When GitHub tooling would otherwise create one remote commit per file, prefer one atomic tree commit for a coherent multi-file change. Keep iterative/temporary commits on `internal-*` whenever possible.

Do not create empty commits, touch unrelated files, toggle governance, or bypass branch protection solely to retrigger Vercel after quota exhaustion. Freeze the exact candidate and wait for quota recovery or use a supported redeploy of the exact Git revision.

`ignoreCommand` may be evaluated later as a secondary optimization only after its effect on required status and quota accounting is verified end to end.

## 9. Rollback

- **Cloudflare**: restore/promote the previous verified Worker deployment or disable the affected route/domain as appropriate.
- **Vercel**: promote the previous verified deployment.
- **D1 membership**: point `universe_current.version_id` back to a retained prior good version when only membership data requires rollback.
- **Source**: revert/restore to the verified pre-change commit/release appropriate to the Batch risk.
- **Production regression**: restore Last Known Good first, then RCA → fix → validate → review → redeploy.
