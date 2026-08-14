# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff authority for volatile project state. Re-query GitHub, CI, Vercel, Cloudflare and runtime state before important actions. Durable semantics remain in current contracts; closed execution detail remains recoverable from Git/PR/Issue/Actions history.

## Project Status

**ROADMAP-B01 — research-use boundaries + origin perimeter: LOCAL CHECKPOINT / NOT COMMITTED / NOT PUSHED / NOT DEPLOYED.**

- Local implementation branch: `codex/roadmap-batch-0-1`.
- Exact base: `c99916e7668a800e12d44b010becce43f51cd0d7`, which was `origin/main` when the local batch started.
- The local worktree is intentionally dirty and contains Batch 0 research-boundary work plus most Batch 1 origin-auth, resource-limit, rate-limit and bounded-cache work.
- Focused Worker integration tests passed 39/39; Wrangler types and deploy dry-run passed. Full final Python/CI/browser validation is still outstanding.
- No commit, push, PR, secret write or production deployment was performed for ROADMAP-B01.
- Authoritative detailed checkpoint and resume procedure: [`docs/ROADMAP_EXECUTION_HANDOFF_2026-08-14.md`](docs/ROADMAP_EXECUTION_HANDOFF_2026-08-14.md).
- **Do not merge/deploy ROADMAP-B01 until its external Vercel/Cloudflare edge secret is provisioned and the documented two-phase rollout is verified.**

## Stable State

- Current verified functional recovery baseline: `main` [`c99916e7668a800e12d44b010becce43f51cd0d7`](https://github.com/chihung1024/backteststock/commit/c99916e7668a800e12d44b010becce43f51cd0d7), PF-1I.
- Previous verified functional baseline: [`a7b28a06a5856233c6340be9a0c05de8d4be67cc`](https://github.com/chihung1024/backteststock/commit/a7b28a06a5856233c6340be9a0c05de8d4be67cc), PF-1H.
- PF-1I candidate CI #696, exact-head review, post-main CI #697, Vercel production status and Cloudflare Deploy #70 passed. Cloudflare smoke covered Russell 2000, Portfolio v3 and Refinery v1.
- ROADMAP-B01 is **not** part of this stable baseline; it exists only in the preserved local dirty worktree.
- Rollback for the current deployed functional head is a normal revert of PR #145; no data/storage/schema migration is involved.

## Architecture Notes

- Browser surfaces: Scanner/Universe, Exhaustive historical search, Portfolio v3 and Portfolio Refinery.
- Cloudflare Worker/static assets provide routing, D1 Universe access, request guards, cache and same-origin proxying.
- Vercel Python functions host compatibility routes plus Portfolio v3 and Refinery v1 API entrypoints.
- `apps/api/app/data/` is the shared market-data / FX / TWD valuation authority.
- `apps/api/app/portfolio/` owns path-dependent Portfolio ledger/analytics semantics.
- `apps/api/app/research/` owns reproducible ResearchDataset boundaries; it must not become a second downloader.
- `apps/api/app/quant/` owns pure validated quantitative primitives.
- `apps/api/app/refinery/` is a read-only research/evidence domain and must not silently become a recommendation/sizing engine.
- TWD remains the canonical valuation currency across Scanner, Backtest, Portfolio and Exhaustive paths.

## Master Plan

### Batch 0 — Research-use boundaries — LOCAL IMPLEMENTED / FINAL GATES PENDING

- Add visible historical in-sample, current-universe, gross-return and non-investment-advice boundaries to research surfaces.
- Keep current Universe membership clearly distinct from point-in-time historical membership.
- Update relevant contracts and source assertions without changing ranking/selection methodology.

### Batch 1 — Origin perimeter + finite-resource controls — LOCAL IMPLEMENTED / FINAL GATES PENDING

- Protect analysis origins with Worker-to-Vercel service authentication.
- Strip browser-controlled credentials, cookies and spoofed service/client identity before origin forwarding.
- Add finite backend request/ticker/history/ticker-day budgets and bounded scan cache reads/writes.
- Use distributed Cloudflare rate limiting as overload protection while retaining process-local brakes only as per-instance safeguards.
- Roll out in two phases so production is never switched to fail-closed before both sides share the same secret.

### Batch 2 — Quant/date correctness — NEXT AFTER B01 CLOSEOUT

1. Charge Portfolio borrowing interest by actual elapsed calendar days; cover weekends/holidays/leap years.
2. Make legacy `/api/backtest` gross-vs-cost semantics machine-readable; either implement cost inputs or explicitly publish `return_net_of_costs=false`.
3. Reject future month endpoints and define an `as_of` / market-close rule so incomplete current daily bars are not silently included.
4. Mark FX repairs using future trusted observations as non-causal and allow causal research modes to exclude them.
5. Define common holding intervals for cross-market benchmark-relative returns and distinguish provider gaps from ordinary non-trading days.
6. Add convergence/error reporting to Exhaustive post-cost fixed-point logic and normalize timezone handling.
7. Resolve the same-asset blur → rapid-refocus autocomplete timeout race with regression coverage.

### Batch 3 — Research validity

1. Add effective-from/effective-to Universe semantics and explicit as-of lookup for history collected from now onward; never fabricate older membership.
2. Preserve delistings, ticker mappings, source-as-of, retrieved-at, provider version and immutable dataset hashes.
3. Fail closed when required historical membership/fundamentals are unavailable instead of substituting the current Universe.
4. Add train/validation/test or rolling walk-forward selection to Exhaustive; retain full-period mode only under explicit in-sample labeling.
5. Report trial count, stability and holdout degradation; add snapshot/leakage regressions.

### Batch 4 — Architecture / CI / governance

1. Create one route manifest that generates/checks Vercel and Worker routing definitions; retire duplicated legacy Flask paths incrementally.
2. Pin GitHub Actions/dependencies appropriately and add dependency/security/coverage gates proportional to risk.
3. Preserve Wrangler type checks and add rate-limit/cache/origin-auth observability without logging secrets or raw IPs.
4. Separate production D1 provisioning from deployment and fail closed when required database configuration is absent.
5. Automate handoff/current-SHA generation and formalize release/security/contribution/ownership artifacts where useful.
6. Require genuinely independent review for high-risk changes.

## Current Phase / Batch

Primary Active Batch: **ROADMAP-B01** only.

- Objective: finish and validate the already-implemented research-boundary + origin-perimeter checkpoint without adding unrelated scope.
- In scope: exact files already present in the dirty worktree, mandatory validation, regression fixes required by those changes, edge-secret rollout preparation and documentation consistency.
- Out of scope: new product features, arbitrary refactors, recommendation/sizing/OOS claims, unrelated Technical Debt, or starting Batch 2 before B01 is stable.
- Allowed investigation: only evidence needed to validate B01, isolate regressions, confirm routing/auth coverage, request/resource budgets and deployment contracts.
- Expansion trigger: Critical security/data-integrity/production issue, direct root-cause dependency, or evidence that B01 cannot safely ship without a narrowly related change.
- Risk: origin authentication and secret handling are security-boundary work; treat final implementation as high risk and reclassify from the exact final diff before merge.

## Validation Status

Already obtained on the local checkpoint:

- Research-boundary worker TypeScript/Vite build passed; Portfolio source contracts 5/5 passed; local Chromium was unavailable.
- Backend perimeter focused run: 24 tests + 43 affected endpoint tests + compileall passed before final Python refinements.
- Final Worker integration checks: syntax passed; focused/new Worker/route tests 39/39 passed; `wrangler types --check` passed; `wrangler deploy --dry-run` passed.
- Cache-specific tests 7/7 passed, including early cancellation of oversized streams.

Still mandatory on the exact final head:

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

Also rebuild Portfolio canonically and confirm `git diff --exit-code -- package-lock.json public/portfolio`; generated asset changes are acceptable only when a clean rebuild reproduces them.

## Release / Deployment Blocker

Before B01 merge/deployment:

1. Generate one random secret of at least 32 bytes; never commit it.
2. Configure Vercel `BACKTESTSTOCK_EDGE_SECRET` and temporarily set `BACKTESTSTOCK_REQUIRE_EDGE_AUTH=false` for migration.
3. Configure the same value as Cloudflare `BACKTESTSTOCK_EDGE_SECRET`.
4. Deploy/verify Worker-routed requests carry authenticated identity.
5. Switch Vercel `BACKTESTSTOCK_REQUIRE_EDGE_AUTH=true`, redeploy, then verify protected direct-origin calls return 403 while Worker-routed calls succeed.
6. Keep `/api/health` as the minimal public readiness surface.

Cloudflare rate limiting is distributed per location and eventually consistent; it is overload protection, not a strong global accounting quota.

## Change Log — Functional Stable History

- PF-1I — Portfolio autocomplete focus-transition guard — PR #145 / `c99916e` — deployed and post-main verified.
- PF-1H — Portfolio stale-request busy cleanup — PR #143 / `a7b28a0` — deployed and post-main verified.
- PF-1G — Portfolio autocomplete late-response guard — PR #141 / `dac6e6c` — deployed and post-main verified.
- PF-1F — Refinery stale-evidence invalidation — PR #139 / `a4c4312` — deployed and post-main verified.
- PF-1E — Portfolio stale-evidence invalidation — PR #137 / `2dda223` — deployed and post-main verified.
- PF-1D — Scanner edge-cache namespace invalidation — PR #135 / `f8c08ca` — deployed and post-main verified.
- PF-1C — TWD Scanner raw-calendar coverage audit — PR #133 / `47ca2ea` — deployed and repository-verified; sparse `0.5` production case remains unverified.
- PF-1B — Scanner → Portfolio legacy-date handoff — PR #131 / `3a93afe` — deployed and post-main verified.
- PF-1A — Scanner → Portfolio → Optimizer provenance preservation — PR #129 / `15a5f44` — deployed and post-main verified.
- UX-1B — Scanner destination capacity clarity — PR #127 / `21a7e5f` — deployed and post-main verified.
- UX-1A — Scanner execution clarity / pending-first-result behavior — PR #125 / `4598ecf` — deployed and post-main verified.

Full closed-batch narratives before this live-status convergence remain permanently recoverable from the immutable pre-checkpoint file at [`c99916e:to_do_update_list.md`](https://github.com/chihung1024/backteststock/blob/c99916e7668a800e12d44b010becce43f51cd0d7/to_do_update_list.md) and the linked PR/Actions history.

## Decision Log

- TWD is the single valuation authority for cross-market research outputs.
- Exhaustive remains full-period historical search; it is not OOS evidence.
- Current Universe membership must not be presented as historical point-in-time membership.
- ResearchDataset reports evidence and explicit partial membership; consumers decide acceptance thresholds and must fail closed when completeness is required.
- Portfolio ledger remains a separate path-dependent domain even when sharing TWD data/quant primitives.
- Stable functionality takes priority over cleanup/refactor; no unrelated changes enter B01.
- `main c99916e` remains the recovery baseline until B01 is exact-head green, reviewed and deliberately rolled out.
- B01 origin authentication uses a two-phase rollout specifically to avoid locking out legitimate Worker traffic during secret migration.

## Root Cause Log

- PF-1I: delayed blur from an older asset input could clear a newer input's active autocomplete state; fixed by asset-scoped deferred cleanup.
- PF-1H: stale request `finally` blocks could clear the busy state of a newer Portfolio request; fixed by request-version/controller identity guards.
- PF-1G: autocomplete responses/busy state lacked request identity; fixed by monotonic request-version guards.
- PF-1F: Refinery late responses could repopulate evidence for an obsolete model/plan; fixed by request-version invalidation.
- PF-1E: Portfolio model replacement/edit cleared visible evidence but did not fully invalidate in-flight work; fixed by abort + versioned evidence invalidation.
- PF-1D: PF-1C backend correction could be hidden by an old edge-cache namespace; fixed by namespace invalidation and regression coverage.
- PF-1C: Scanner coverage audit was computed after forward-fill, overstating raw observation coverage; fixed by auditing raw calendars before metric alignment.
- PF-1B: Portfolio route bridge read legacy scan jobs without the Scanner's date normalization; fixed by applying the shared date contract.
- PF-1A: Portfolio round-trip replaced rich Optimizer handoff provenance with an incomplete record; fixed by preserving validated manual-selection metadata.

## Known Issues

- Sparse partial-calendar `data_coverage=0.5` behavior is repository-tested but still NOT VERIFIED against a matching live production provider response.
- ROADMAP-B01 final Python/full CI/browser validation remains outstanding.
- ROADMAP-B01 cannot safely merge/deploy before matching Vercel/Cloudflare edge secret provisioning and rollout verification.
- The local `codex/roadmap-batch-0-1` worktree is intentionally dirty; do not reset/clean/rebase it blindly.
- Legacy month-based date input can currently describe a future/incomplete month; Batch 2 must define explicit `as_of` behavior.
- Portfolio borrowing interest currently needs calendar-day accrual verification/fix for multi-day valuation gaps.
- Historical research still lacks complete point-in-time Universe history before collection began; survivorship/look-ahead claims must remain constrained.
- Some FX repair logic can use a future trusted observation during interpolation; causal research must identify/exclude those repairs before OOS-style use.

## Technical Debt

- Duplicate route declarations across Vercel and Worker routers; consolidate only in Batch 4 after B01/B2/B3 correctness work.
- Compatibility Flask paths remain and should be retired incrementally, not via one large rewrite.
- Universe storage needs effective interval / delisting / ticker-mapping provenance for point-in-time research.
- CI/security governance can be tightened with immutable action pins, dependency auditing, CodeQL/secret scanning and measured coverage thresholds.
- Observability for rate limit/cache/origin auth needs privacy-preserving metrics.

## Deferred / Backlog

- Distributed Refinery rate limiting beyond B01's perimeter controls.
- Instrument/security master and regional factor routing.
- Traceable theme provider/taxonomy.
- Public sourcemap policy as a dedicated build/deployment decision.
- Exception-taxonomy hardening only when a reproducible invariant failure exists.

## Rejected for Current / Next Functional Batch

- Arbitrary Cartesian experiment generation.
- Recommendation, ranking, selection, sizing, optimization or OOS claims without the required validation contract.
- Changing Phase 5/6 methodology without a separately reviewed contract.
- Persistence migration merely for convenience.
- Deleting active workflows/files or mixing unrelated cleanup into a functional release.
- Starting Batch 2 implementation while B01 remains unvalidated/unreviewed.

## Risks

- **Security rollout risk:** mismatched/missing edge secrets can block valid traffic or leave direct origin exposed. Use the documented two-phase rollout and verify both paths.
- **Dirty-worktree risk:** unknown/local changes can be lost by reset/clean/rebase. Preserve and inspect before any branch synchronization.
- **Research-validity risk:** current Universe or future-assisted data repair can create survivorship/look-ahead bias if labels/contracts are ignored.
- **Resource-contract risk:** request ceilings/rate limits must be tuned from measured Scanner behavior, not arbitrary assumptions.
- **Documentation-drift risk:** mutable remote/CI/deployment state is higher authority than this snapshot; re-query before action.

## NOW / NEXT / BACKLOG / REJECT

### NOW

Preserve `main c99916e` as the verified functional recovery point. Resume only ROADMAP-B01 from the existing local dirty worktree: re-query remote truth, inspect/preserve every local change, complete the mandatory validation list, repair only directly related regressions, provision the required edge secret, and complete the safe two-phase rollout gates. Do not treat B01 as release-ready or deployed yet.

### NEXT

After B01 is exact-head green, independently reviewed and safely rolled out, execute Batch 2 (quant/date correctness), then Batch 3 (research validity), then Batch 4 (architecture/CI/governance), one primary implementation batch at a time.

### BACKLOG

Use the Deferred / Backlog section above. Newly discovered useful-but-unrelated work stays there unless it meets the documented expansion trigger.

### REJECT

Use the Rejected section above. Do not reopen closed PF/UX batches unless their functional invariants regress.

## Next Actions

1. Read `AI_PROJECT_PLAYBOOK.md`, root `README.md`, this file, `docs/ROADMAP_EXECUTION_HANDOFF_2026-08-14.md`, `docs/DEPLOYMENT.md` and applicable contracts.
2. Re-query current `main`, PRs, checks, Vercel and Cloudflare before touching the preserved local B01 worktree.
3. Inspect every unstaged/untracked local B01 file; preserve generated Portfolio assets with their source/build unit.
4. Run every mandatory validation gate and fix only B01-related regressions.
5. Reclassify final risk from the exact diff; obtain required review/authorization before commit/push/PR/merge/deploy.
6. Provision and verify origin-auth secrets using the two-phase rollout before enforcing fail-closed origin access.
7. Update this handoff after each completed gate and keep one primary active batch.

## Exact Resume Point

PF-1I is closed at `main c99916e`; candidate CI #696, exact-head review, post-main CI #697, Vercel production status and Cloudflare Deploy #70 passed. ROADMAP-B01 then began locally from that exact head and remains an uncommitted, unpushed, undeployed dirty-worktree checkpoint. Resume from [`docs/ROADMAP_EXECUTION_HANDOFF_2026-08-14.md`](docs/ROADMAP_EXECUTION_HANDOFF_2026-08-14.md), preserve the dirty worktree, re-query mutable remote truth, run every mandatory validation gate, and do not start Batch 2 until B01 reaches a stable reviewed checkpoint.
