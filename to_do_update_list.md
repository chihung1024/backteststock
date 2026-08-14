# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff authority for volatile project state. Re-query mutable GitHub, CI, Vercel, Cloudflare and runtime state before important actions. Durable API/UI semantics belong in their contracts; closed execution detail remains recoverable from Git/PR/Issue/Actions history.

## Current Status

**ROADMAP-B01 — research-use boundaries + origin perimeter: ACTIVE DRAFT PR / IMPLEMENTATION VALIDATED / NOT MERGED / NOT DEPLOYED.**

- Stable production `main` remains [`c99916e7668a800e12d44b010becce43f51cd0d7`](https://github.com/chihung1024/backteststock/commit/c99916e7668a800e12d44b010becce43f51cd0d7) (PF-1I). ROADMAP-B01 is not part of production.
- Active candidate: [PR #147](https://github.com/chihung1024/backteststock/pull/147), branch `codex/roadmap-batch-0-1`, still Draft.
- Preserved recovery checkpoint commit: [`9ac88d1c79c7747329abd013a918c9c428e68874`](https://github.com/chihung1024/backteststock/commit/9ac88d1c79c7747329abd013a918c9c428e68874). Do not rewrite or discard this recovery point.
- Latest fully validated implementation head before this live-handoff reconciliation: [`0dc83c2e1090de4830d9e55616c2d174ffbb23de`](https://github.com/chihung1024/backteststock/commit/0dc83c2e1090de4830d9e55616c2d174ffbb23de).
- Exact-head candidate CI [#705](https://github.com/chihung1024/backteststock/actions/runs/31778607448) passed every repository gate at that implementation head: Python install/pip check, compile, Ruff, 287 pytest tests, JavaScript checks, Worker tests, generated Worker bindings, score tests, Portfolio TypeScript/build, Portfolio/Refinery source contracts, committed Portfolio asset verification, Chromium Playwright E2E, Vercel JSON validation, local D1 migrations and Wrangler deploy dry-run.
- Focused R3 self-review found and fixed two trust-boundary issues before the green candidate: misspelled/nonstandard required-policy values now fail closed rather than disabling edge protection, and browser-controlled forwarding/IP/service-identity headers are stripped before trusted backend headers are applied. Regression coverage was added.
- Portfolio production-asset validation was repaired without disabling the gate: runtime assets remain byte-strict; JavaScript source maps remain strict for file set, mappings, names and other semantic fields while package-manager install-layout paths are normalized and non-runtime embedded `sourcesContent` is excluded from equality after structural validation.
- [PR #146](https://github.com/chihung1024/backteststock/pull/146) was closed without merge as superseded by #147, preventing competing live-status documents.
- No ROADMAP-B01 production secret write, production merge or deployment has been performed.
- Any commit newer than the recorded green implementation head must obtain its own exact-head CI before the PR can be treated as release-ready. PR #147 is the authority for the current mutable head SHA.

### Remaining B01 release gates

1. Current PR #147 exact head must be fully green after the final documentation reconciliation.
2. Complete a genuinely independent review of the final high-risk diff. The current focused review is self-review and must not be labeled independent.
3. Provision one random `BACKTESTSTOCK_EDGE_SECRET` of at least 32 bytes in both Vercel and Cloudflare without committing or exposing the value.
4. Perform the documented two-phase origin-auth rollout: first run Vercel with `BACKTESTSTOCK_REQUIRE_EDGE_AUTH=false`, deploy/verify the Worker with the matching secret, then enable Vercel fail-closed enforcement.
5. Verify Worker-routed protected APIs succeed, direct protected Vercel-origin calls return 403, and `/api/health` remains public.
6. Only after those gates: mark #147 Ready, merge using the repository's approved method, then verify post-main CI, Vercel/Cloudflare deployment and production smokes before closing B01.

Historical local recovery details remain in [`docs/ROADMAP_EXECUTION_HANDOFF_2026-08-14.md`](docs/ROADMAP_EXECUTION_HANDOFF_2026-08-14.md). That file is a historical checkpoint, not the current live-status authority.

## Stable State

- Current verified production recovery baseline: `main` [`c99916e7668a800e12d44b010becce43f51cd0d7`](https://github.com/chihung1024/backteststock/commit/c99916e7668a800e12d44b010becce43f51cd0d7), PF-1I.
- Previous verified baseline: [`a7b28a06a5856233c6340be9a0c05de8d4be67cc`](https://github.com/chihung1024/backteststock/commit/a7b28a06a5856233c6340be9a0c05de8d4be67cc), PF-1H.
- PF-1I candidate CI #696, post-main CI #697, Vercel production and Cloudflare Deploy #70 passed; Cloudflare smoke covered Russell 2000, Portfolio v3 and Refinery v1.
- ROADMAP-B01 is a candidate only. Do not describe its security controls, research labels or resource limits as deployed until post-main production verification proves that state.
- Current production rollback remains a normal revert of PR #145; no B01 data/storage/schema migration is active in production.

## Architecture Notes

- Browser surfaces: Scanner/Universe, Exhaustive historical search, Portfolio v3 and Portfolio Refinery.
- Cloudflare Worker/static assets provide routing, D1 Universe access, cache, edge request policy and same-origin proxying.
- Vercel Python functions host compatibility routes plus Portfolio v3 and Refinery v1 API entrypoints.
- `apps/api/app/data/` is the shared market-data / FX / TWD valuation authority.
- `apps/api/app/portfolio/` owns path-dependent Portfolio ledger/analytics semantics.
- `apps/api/app/research/` owns reproducible ResearchDataset boundaries and must not become a second downloader.
- `apps/api/app/quant/` owns pure validated quantitative primitives.
- `apps/api/app/refinery/` is a read-only research/evidence domain and must not silently become a recommendation/sizing engine.
- TWD remains the canonical valuation currency across Scanner, Backtest, Portfolio and Exhaustive paths.

## Master Plan

### Batch 0 — Research-use boundaries — IMPLEMENTED IN PR #147

- Add visible historical in-sample, current-universe, gross-return and research/not-investment-advice boundaries to research surfaces.
- Keep current Universe membership clearly distinct from point-in-time historical membership.
- Update relevant contracts/source assertions without changing ranking or selection methodology.
- Canonical user-facing wording: [`docs/RESEARCH_USE_BOUNDARIES.md`](docs/RESEARCH_USE_BOUNDARIES.md).

### Batch 1 — Origin perimeter + finite-resource controls — IMPLEMENTED IN PR #147

- Worker-to-Vercel service authentication with fail-closed production enforcement.
- Browser credential/cookie/forwarding/IP/service-identity sanitation before origin forwarding.
- Finite backend request/ticker/history/ticker-day budgets and 512 KiB request ceiling.
- 500-ticker Scanner cap and bounded scan-cache response handling.
- Opaque edge client identity plus Cloudflare distributed rate-limit bindings.
- CI-generated Worker binding verification and deployment runbook.
- Two-phase rollout so production is never switched to fail-closed before both sides share the same secret.

### Batch 2 — Quant/date correctness — NEXT AFTER B01 CLOSEOUT

1. Charge Portfolio borrowing interest by actual elapsed calendar days; cover weekends, holidays and leap-year behavior.
2. Make legacy `/api/backtest` gross-vs-cost semantics machine-readable; either implement cost inputs or explicitly publish `return_net_of_costs=false`.
3. Reject future month endpoints and define a common `as_of` / market-close rule so incomplete current daily bars are not silently included.
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

1. Create one route manifest that generates/checks Vercel and Worker route definitions; retire duplicated legacy paths incrementally.
2. Pin GitHub Actions/dependencies appropriately and add dependency/security/coverage gates proportional to risk.
3. Preserve Wrangler type checks and add privacy-preserving rate-limit/cache/origin-auth observability.
4. Separate production D1 provisioning from deployment and fail closed when required database configuration is absent.
5. Automate handoff/current-SHA generation and formalize release/security/contribution/ownership artifacts where useful.
6. Require genuinely independent review for high-risk changes.

## Current Phase / Primary Active Batch

**Primary Active Batch: ROADMAP-B01 closeout only.**

Do not start Batch 2 implementation while #147 is still Draft, unreviewed by an independent reviewer, not safely rolled out, or not post-main verified. Newly discovered unrelated work goes to Backlog unless it is required to preserve B01 functional/security correctness.

## B01 Validation Record

Recorded exact-head green implementation candidate: `0dc83c2e1090de4830d9e55616c2d174ffbb23de`, CI #705.

Passed gates:

- Python dependency install and `pip check`.
- Python compile and Ruff.
- `pytest`: 287 passed.
- JavaScript syntax checks.
- Worker regression suite, including edge-auth/rate-limit/header-spoof coverage.
- Wrangler-generated Worker binding check.
- Score formula tests.
- Portfolio TypeScript check/build.
- Portfolio and Refinery source contracts.
- Canonical Portfolio runtime/source-map verification.
- Chromium Playwright browser E2E.
- Vercel configuration JSON validation.
- Local D1 migration apply.
- Cloudflare Wrangler deployment dry-run.

The above evidence applies to that exact SHA only. A newer PR head must be re-queried and validated before merge decisions.

## Decisions / Constraints

- Stable user functionality and UX outrank process expansion or cosmetic refactors.
- Debugging must address root cause; do not weaken gates merely to obtain green CI.
- Research labels are product correctness boundaries, not disclaimers used to excuse invalid research claims.
- Current Universe membership must never be presented as historical point-in-time membership.
- Full-period Exhaustive output remains explicitly historical/in-sample until Batch 3 adds OOS/walk-forward semantics.
- Direct-origin protection must fail closed in production after the controlled migration phase.
- `/api/health` intentionally remains public so deployment health can be verified without exposing protected analysis routes.
- Browser-controlled credentials, cookies and forwarding/client identity must not cross the Worker→origin trust boundary.
- Secrets must never be committed, logged, copied into handoff files or repeated in PR discussions.
- A self-review or same-account GitHub approval is not a genuinely independent review.
- Historical closeout narratives belong in Git/PR/Actions history; this file keeps only current state, unresolved root causes, risks and next actions.

## Root Causes / Findings Preserved for Later Batches

- Portfolio leverage interest currently accrues once per valuation row rather than by actual elapsed calendar days; Batch 2 must correct this with explicit calendar-day tests.
- Legacy year/month date parsing can accept a future month within the current year; Batch 2 must enforce a common `as_of`/completeness rule.
- FX level reconciliation can interpolate from a future trusted observation; retrospective repair is acceptable only when causality is explicit, and OOS-style research must be able to exclude future-assisted repairs.
- Legacy `/api/backtest` has no explicit transaction-cost/slippage/tax contract while Portfolio v3 does; gross/net semantics must be machine-readable.
- Exhaustive is intentionally a full-period historical optimizer today; high engineering reproducibility does not make it out-of-sample evidence.
- Universe version snapshots preserve source/checksum/version but do not provide historical effective-from/effective-to membership prior to collection.
- Cross-market union calendars can conflate provider gaps with legitimate exchange non-trading days; Batch 2 must make the distinction explicit.
- Vercel and Worker route declarations are duplicated; consolidate only after correctness/research-validity work, not during B01.

## Known Issues / Remaining Blockers

- B01 has not been independently reviewed by a separate reviewer.
- B01 production edge secret has not been provisioned or verified.
- B01 has not been merged or deployed; production remains c99916e.
- Sparse partial-calendar `data_coverage=0.5` behavior is repository-tested but still lacks a matching live provider-response verification.
- Historical research lacks complete point-in-time Universe history before collection began.
- Some future-assisted FX repair paths remain unsuitable for causal/OOS claims until Batch 2/3 boundaries are implemented.

## Technical Debt / Backlog

- Duplicate Worker/Vercel route declarations.
- Compatibility Flask paths to retire incrementally.
- Universe effective-interval, delisting and ticker-mapping provenance.
- Immutable GitHub Action pins, dependency/security audits, CodeQL/secret scanning and measured coverage thresholds.
- Privacy-preserving rate-limit/cache/origin-auth observability.
- Separate D1 provisioning from production deployment.
- Public sourcemap policy as a dedicated build/deployment decision rather than an incidental B01 change.

## Rejected for Current Batch

- Starting Batch 2 before B01 closeout.
- Unrelated feature work or large architectural refactors.
- Weakening CI, request protection or research contracts merely to simplify rollout.
- Arbitrary Cartesian experiment generation.
- Recommendation/ranking/sizing/OOS claims without the required validation contract.
- Persistence migration merely for convenience.
- Deleting active workflows/files as cleanup without a demonstrated current need.

## Risks

- **Security rollout:** mismatched/missing edge secrets can block valid traffic or leave direct origin exposed; use the two-phase runbook.
- **Resource contract:** limits must remain compatible with legitimate Scanner/Portfolio/Refinery workloads and be tuned from evidence, not arbitrary expansion.
- **Research validity:** current Universe or future-assisted data repair can create survivorship/look-ahead bias if labels/contracts are ignored.
- **Documentation drift:** GitHub/CI/deployment/runtime are mutable authorities; re-query them before action.
- **Review independence:** same-account approval must not be misreported as independent review.

## NOW / NEXT / BACKLOG / REJECT

### NOW

Keep `main c99916e` as the verified production recovery point. Finish ROADMAP-B01 on PR #147 only: final exact-head CI after documentation reconciliation → genuine independent review → controlled Vercel/Cloudflare secret rollout → production smoke → merge/post-main verification → B01 closeout.

### NEXT

After B01 is fully closed, execute Batch 2 quant/date correctness. Then Batch 3 research validity, then Batch 4 architecture/CI/governance, one primary implementation batch at a time.

### BACKLOG

Use the Technical Debt / Backlog section. Newly discovered useful but unrelated work stays there unless it is necessary to preserve the active batch's functional or security invariant.

### REJECT

Use the Rejected section. Do not reopen closed PF/UX batches unless their functional invariants demonstrably regress.

## Next Actions

1. Re-query PR #147 current head and its exact-head CI after this documentation update.
2. Complete focused final diff review and confirm no unresolved review threads.
3. Obtain a genuinely independent reviewer for the final R3 candidate; do not substitute self-approval.
4. Follow `docs/DEPLOYMENT.md` to provision the same >=32-byte edge secret in Vercel and Cloudflare using the compatibility-first two-phase sequence.
5. Verify protected Worker-routed calls succeed, protected direct-origin calls fail with 403, and `/api/health` remains public.
6. Mark #147 Ready and merge only after the required gates are satisfied.
7. Verify post-main CI, Vercel production, Cloudflare deployment and Scanner/Portfolio/Refinery smokes; then record B01 CLOSED.
8. Only then create the Batch 2 branch/work plan.

## Exact Resume Point

Production is still `main c99916e` (PF-1I). ROADMAP-B01 is preserved in Draft PR #147; recovery checkpoint `9ac88d1...` remains in history. Implementation head `0dc83c2e...` passed full CI #705 and focused self-review after the asset-verification, fail-closed policy-mode and forwarding-header hardening fixes. PR #146 is closed as superseded. Resume by re-querying #147's current mutable head/checks, then complete independent review and the two-phase secret rollout. Do not begin Batch 2 and do not describe B01 as deployed until post-main production verification is complete.
