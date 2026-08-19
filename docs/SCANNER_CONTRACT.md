# Scanner / Universe Contract

Status: **Current Scanner / Universe product contract.**

This document owns the durable behavior of Universe publishing, current/PIT candidate selection, Scanner execution, date defaults and Edge caching. Historical phase names and rollout narratives belong in Git/PR history.

## 1. Authority boundaries

- `scripts/update_universes.py` owns source ingestion and publication validation.
- Cloudflare D1 owns versioned Universe membership and point-in-time observations.
- `worker/` owns same-origin routing, D1 reads and Edge cache admission.
- `api/scan_v2.py` + `apps/api/app/scan_service.py` own production scan execution.
- `apps/api/app/data/` owns market data, FX and TWD valuation.
- `api/metrics.py` owns simple-value Scanner metrics.
- Browser code owns request editing, progress/resume and presentation only.

A failure may not silently change requested symbols, requested dates, PIT provenance or quantitative methodology.

## 2. Universe sources

| Universe | Source | Expected size | Disclosure |
| --- | --- | ---: | --- |
| `sp500` | iShares IVV official holdings | 480–530 | ETF holdings proxy |
| `nasdaq100` | Nasdaq Global Index Watch; then Nasdaq API; then QQQM official holdings fallback | 95–110 | GIW is authoritative index evidence; QQQM fallback is proxy |
| `soxx` | iShares SOXX official holdings | 25–40 | ETF holdings |
| `russell2000` | iShares IWM official holdings | 1,750–2,100 | ETF holdings proxy |

Source URLs and optional environment overrides remain centralized in `scripts/update_universes.py`.

## 3. Publication and last-good semantics

Universe updates are publish-after-validation:

1. fetch and retry transient source errors;
2. normalize Yahoo-compatible symbols while preserving raw source symbols;
3. validate source date, ticker syntax, duplicates, count bounds and material membership changes;
4. write a staging version and all members;
5. read back and verify the stored member count;
6. atomically move `universe_current` only after the version is complete;
7. on failure, preserve the existing current/last-good version;
8. retain recent historical versions required by the current D1 policy; never delete the active version during cleanup.

The scheduled implementation is `.github/workflows/update-universes.yml`; its runtime behavior, not this prose, is authoritative for exact cron details.

D1 schema history lives in `migrations/`. `universe_versions`, `universe_members`, `universe_current` and PIT archive tables are data authorities, not browser state.

## 4. Public Universe and Screener APIs

`GET /api/v2/universes` returns enabled Universes with availability/source/version metadata.

`GET /api/v2/universes/:id` returns the complete current snapshot. Declared/stored member-count mismatch fails closed.

`POST /api/v2/screener` accepts a Universe id and user-visible filters/sort/limit. The Worker resolves the trusted D1 snapshot and must ignore client attempts to forge internal Universe metadata.

`limit` is optional. Omitting it means all candidates that pass explicit filters. Truncation occurs only when the user supplies a positive limit and the result exceeds it; the response must disclose truncation.

## 5. Current snapshot vs point-in-time mode

### Current snapshot

Current membership and current fundamentals may be used for present-universe retrospective research. Applying today's membership or fundamentals to an earlier date is not point-in-time selection and may contain survivorship/look-ahead bias.

### PIT historical membership

PIT mode requires explicit `selectionAsOf`.

A usable PIT observation must satisfy the current archive causality/integrity rules, including source/evidence availability no later than the research decision. The system must preserve whether membership is authoritative or a proxy.

PIT mode must not:

- substitute current membership when historical evidence is unavailable;
- apply current fundamentals as though they were historical;
- silently ignore unsupported sector/valuation filters;
- present proxy membership as official index membership.

For an ex-ante PIT Scanner flow, downstream performance data may not extend beyond `selectionAsOf`. Future prices relative to the selection decision are rejected rather than treated as causal evidence.

The generated PIT list and its provenance are one identity. Manual ticker edits invalidate the attached PIT context.

## 6. Scanner execution and recovery

The user-requested list is the work unit. Browser batching and backend download batching are implementation details, not semantic truncation.

Current behavior:

- large lists are processed in bounded batches without a user-level 100-symbol ceiling;
- unresolved tickers are retried without rerunning already successful tickers;
- asset market-data/currency/FX failures remain per-symbol failures;
- benchmark failure preserves successful asset results but makes benchmark-relative metrics unavailable;
- transient failures may be retried with bounded backoff;
- browser progress and pending work may be persisted locally for resume;
- completion means no pending work remains, with success/failure counts explicit;
- cancellation pauses work rather than relabeling pending symbols as final failures.

Missing or unavailable values are not converted to zero.

## 7. Date contract

For a new daily backtest/scan opened in the browser:

- end date defaults to yesterday, inclusive;
- start date defaults to the same calendar date ten years earlier;
- leap-day subtraction clamps to February 28 when necessary;
- users may edit both dates.

Public API uses inclusive `startDate` / `endDate`; backend converts the inclusive end to the market-data provider's exclusive end without changing user semantics.

Legacy period fields may remain accepted where runtime compatibility still requires them.

## 8. TWD, total return and coverage

All production Scanner performance uses the shared TWD valuation and metric contracts.

Data completeness is measured from observed TWD evidence, not from forward-filled metric calendars. Forward filling used by a metric alignment rule must not fabricate source-data coverage.

The browser may compute presentation-relative coverage across successful results, but that presentation value is not a new market-data authority.

## 9. Edge cache

Only eligible unauthenticated `/api/scan` POST responses may use the short-lived Edge response cache.

Cache identity includes the full request body. A response is cacheable only when it is a complete successful JSON result with consistent requested/resolved evidence.

Do not cache:

- non-200 responses;
- partial/incomplete scan results;
- requests carrying authorization/cookies;
- responses without complete resolution evidence.

`/api/backtest` is never served from the Scanner Edge response cache and must not emit a misleading `X-Edge-Cache` result.

## 10. Fail-closed and rollback

Never recover a Scanner/PIT failure by silently dropping symbols, shortening the requested period, substituting current membership, fabricating historical fundamentals, or converting unavailable metrics to zero.

Recovery authorities are the real systems:

- source code: Git revert/restore;
- Cloudflare: deployment rollback;
- D1 Universe: move `universe_current.version_id` to a retained known-good version;
- Vercel/backend: deployment rollback where applicable.

Tests and runtime contracts remain the final behavior authority when this document and code disagree.
