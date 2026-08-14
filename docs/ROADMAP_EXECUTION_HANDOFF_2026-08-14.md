# Roadmap Execution Handoff — 2026-08-14

Status: **LOCAL CHECKPOINT — NOT COMMITTED, NOT PUSHED, NOT DEPLOYED**

This checkpoint was created because the active Codex session reported only 2%
weekly usage remaining. Do not treat the changes as release-ready until every
validation gate below has passed on the exact final head.

## 1. Exact working state

- Branch: `codex/roadmap-batch-0-1`
- Base commit: `c99916e7668a800e12d44b010becce43f51cd0d7`
- Base was equal to `origin/main` when this batch started.
- Worktree: intentionally dirty; about 33 tracked files changed plus new guard,
  Worker security, tests, generated Worker types and research-boundary docs.
- No commit, push, PR, GitHub write, secret write or production deployment was
  performed.
- Re-query `origin/main`, PRs, CI, Vercel and Cloudflare before resuming.

## 2. Completed implementation

### Batch 0 — research-use boundaries

- Added `docs/RESEARCH_USE_BOUNDARIES.md`.
- Added visible `Historical in-sample research`, `Current-universe
  constituents`, gross-return and not-investment-advice labels to Scanner,
  Exhaustive, Portfolio and Refinery source surfaces.
- Updated the relevant README and quant/API documents.
- Rebuilt tracked Portfolio assets under `public/portfolio/`.
- Added source-contract assertions.

### Batch 1 — perimeter and finite-resource controls

- Added `api/request_guard.py` and connected it to scan, backtest, exhaustive,
  screener, Portfolio and Refinery Vercel handlers.
- Production/Vercel requests default to fail closed when the edge secret is
  missing or invalid. An explicit `BACKTESTSTOCK_REQUIRE_EDGE_AUTH=false`
  exists only for the documented two-phase migration.
- Added a 512 KiB backend request ceiling and finite ticker/history/ticker-day
  budgets. Scan remains compatible with 101 tickers and has a finite 500
  ticker cap.
- Replaced trust in production `X-Forwarded-For` with an edge-authenticated,
  opaque client identifier. Existing process-local limiters remain only a
  per-instance overload brake.
- Added `worker/security.js`: it strips browser auth/cookie/spoofed identity,
  forwards the service credential, derives an HMAC-pseudonymous client key,
  and uses separate Cloudflare Rate Limiting bindings for general and
  expensive routes.
- Added required secret and rate-limit bindings to `wrangler.jsonc`, generated
  `worker-configuration.d.ts`, and added `wrangler types --check` to CI.
- Hardened scan caching with a 1 MiB maximum, Content-Length preflight,
  bounded streaming reads, early cancellation, query-aware keys, and
  fail-open cache read/write behavior.
- Unified proxy stripping of `authorization`, `cookie`, Cloudflare IP headers
  and client-supplied service identity.
- Updated the deployment runbook with secret provisioning and safe rollout.

## 3. Validation evidence already obtained

- Research-boundary worker: TypeScript and Vite build passed; Portfolio source
  contracts 5/5 passed; Playwright could not start because local Chromium was
  absent.
- Backend-perimeter worker before the final main-agent refinements: 24 focused
  tests passed, 43 affected endpoint tests passed, and compileall passed.
- Main-agent Worker integration after final refinements:
  - syntax checks for `worker/index.js`, `worker/router.js`, and
    `worker/security.js` passed;
  - focused/new Worker and route tests: 39/39 passed;
  - `wrangler types --check` passed;
  - `wrangler deploy --dry-run` passed with the rate-limit bindings visible.
- Cache-specific tests: 7/7 passed, including proof that an oversized stream is
  cancelled before its tail is consumed.

## 4. Mandatory validation still outstanding

The final Python changes that enforce a minimum 32-byte secret and support the
two-phase migration were made after the backend worker's test run. A full
dependency installation into an isolated `work/python-test-deps` directory
timed out; it did not modify repository files.

Run from repository root in a clean, fully provisioned environment:

```bash
python -m compileall -q api apps scripts
ruff check api apps scripts tests
python -m pytest -q
npm run check
npm run test:worker
npm run test:score
npm run check:portfolio
npm run types:check
node --test tests/test_portfolio_web_contract.mjs \
  tests/test_portfolio_route_bridge.mjs \
  tests/test_refinery_web_contract.mjs \
  tests/test_refinery_phase5_web_contract.mjs \
  tests/test_refinery_phase6_web_contract.mjs
npm run test:e2e
npx wrangler d1 migrations apply backteststock-universe --local
npx wrangler deploy --dry-run
git diff --check
```

Also confirm `git diff --exit-code -- package-lock.json public/portfolio` after
running the canonical Portfolio build. The generated asset rename from
`index-BVm8YPkD.js` to `index-MmpYQPEi.js` is expected only if a clean rebuild
reproduces it.

## 5. Release blocker: origin-auth rollout

Do **not** merge/deploy this batch before provisioning external secrets.

1. Generate one random value of at least 32 bytes; never commit it.
2. Configure it in Vercel as `BACKTESTSTOCK_EDGE_SECRET`.
3. Temporarily configure Vercel
   `BACKTESTSTOCK_REQUIRE_EDGE_AUTH=false` for migration.
4. Configure the same value in Cloudflare with:
   `npx wrangler secret put BACKTESTSTOCK_EDGE_SECRET`.
5. Deploy and verify Worker-routed calls carry authenticated identity.
6. Change Vercel `BACKTESTSTOCK_REQUIRE_EDGE_AUTH=true` and redeploy.
7. Verify Worker API calls succeed and direct-origin calls to protected routes
   return 403. `/api/health` remains the minimal public readiness surface.

Cloudflare Rate Limiting bindings are per-location and eventually consistent.
They are distributed edge protection, not a strong global accounting quota.
The first implementation uses a static bearer-style service credential over
TLS; a later hardening may use timestamped per-request HMAC signatures.

## 6. Review points before declaring Batch 1 complete

- Confirm all Vercel entrypoints that perform market-data or analysis work are
  covered by `authorize_edge_request`.
- Confirm no browser-controlled auth, cookie, XFF or service-identity header is
  forwarded to the origin.
- Confirm direct origin is rejected after enforcement and that Worker smoke
  covers scan, backtest, exhaustive, screener, Portfolio and Refinery.
- Decide whether 60 general and 12 expensive requests/minute/client/location
  are suitable for real Scanner chunking; tune only with measured evidence.
- Confirm 512 KiB backend ceiling is intentionally stricter than the old 3 MiB
  Exhaustive edge ceiling, or align the two contracts and tests.
- Check that soft elapsed-time failures do not discard useful completed work;
  they currently evaluate after synchronous service calls and are not hard
  cancellation.

## 7. Remaining roadmap

### Batch 2 — quant/date correctness

1. Charge Portfolio borrowing interest by actual elapsed calendar days between
   valuation timestamps; add weekend/holiday and leap-year tests.
2. Make `/api/backtest` transaction-cost semantics explicit in schema. Either
   implement cost/slippage/tax inputs or preserve gross-only behavior with an
   unambiguous machine-readable `return_net_of_costs=false` contract.
3. Reject future month endpoints and define an `as_of`/market-close rule so an
   incomplete current daily bar is not silently included.
4. Mark FX repairs that use future trusted observations as non-causal and let
   causal research modes exclude them.
5. Define common holding intervals for cross-market benchmark-relative
   returns; distinguish provider gaps from ordinary non-trading days in
   coverage masks.
6. Add convergence/error reporting to the Exhaustive post-cost fixed point and
   normalize timezone handling.
7. Fix the same-asset blur→rapid-refocus autocomplete timeout race and add the
   missing regression.

### Batch 3 — research validity

1. Extend Universe storage with effective-from/effective-to semantics and an
   explicit as-of lookup. Existing retained versions only provide history from
   collection onward; do not fabricate older membership.
2. Preserve delistings, ticker mappings, source-as-of, retrieved-at, provider
   version and immutable dataset hashes.
3. Fail closed when historical membership/fundamentals are unavailable instead
   of substituting the current Universe.
4. Add train/validation/test or rolling walk-forward selection to Exhaustive;
   retain full-period mode only under its current in-sample label.
5. Report trial count, stability and holdout degradation; add reproducible
   snapshot fixtures and leakage tests.

### Batch 4 — architecture, CI and governance

1. Create one route manifest that generates/checks `vercel.json` and both
   Worker routers; then retire duplicated legacy Flask paths incrementally.
2. Pin GitHub Actions to immutable SHAs; pin/hash the Universe updater's
   dependencies; add dependency audit, CodeQL/secret scanning and coverage
   thresholds.
3. Keep `wrangler types --check`; validate observability sampling and add
   rate-limit/cache/origin-auth metrics without logging secrets or raw IPs.
4. Separate production D1 provisioning from deployment and fail closed when
   the configured database ID is absent.
5. Automate handoff/current-SHA generation; establish release tags, LICENSE,
   SECURITY, CONTRIBUTING, CODEOWNERS and branch/ref retention policy.
6. Require a genuinely separate reviewer/account for high-risk changes.

## 8. Resume sequence for the next AI

1. Read this file, `docs/RESEARCH_USE_BOUNDARIES.md`, `docs/DEPLOYMENT.md`,
   `to_do_update_list.md`, and the repository instructions.
2. Re-query remote `main`; do not rebase/reset a dirty worktree without owner
   approval.
3. Inspect every unstaged/untracked file and preserve the generated Portfolio
   assets as one source/build unit.
4. Complete the mandatory validation list and repair regressions before adding
   more scope.
5. Obtain explicit authorization separately for commit, push and PR creation.
6. After Batch 0/1 is exact-head green and reviewed, proceed through Batches
   2→3→4 in order, updating this handoff after each completed gate.
