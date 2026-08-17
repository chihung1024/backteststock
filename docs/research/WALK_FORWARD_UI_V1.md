# Walk-Forward Research Workspace V1

Status: **Batch 4A-6 versioned user-facing UI contract.**

UI contract version: `walk-forward-ui-2026-08-17.1`

This contract exposes the already-versioned Walk-Forward 4A-1 through 4A-5 research workflow as a user-facing workspace inside the existing Portfolio web application. It does **not** create a second PIT resolver, selector, market-data service, Portfolio simulator, metric engine, benchmark engine, persistent ResearchRun store or AI strategy generator.

## 1. Product surface

The user-facing workspace is available from the `/portfolio/` application through the third workspace selector:

- Portfolio Backtest;
- Holding Refinery;
- Walk-Forward Research.

The Walk-Forward workspace is a full-page research surface, not a modal or hidden developer form.

V1 contains five user-visible capabilities:

1. research input and causal-period editing;
2. browser pre-validation and normalized request preview;
3. synchronous Walk-Forward execution with cancellation and explicit failure semantics;
4. continuous OOS result presentation using backend-authoritative ledger/metrics;
5. Decision / PIT / dataset provenance inspection and raw-result JSON export.

## 2. Authority boundary

The browser is an orchestration and presentation layer only.

It may:

- collect user inputs;
- normalize obvious symbol casing already required by the public request contract;
- reject structurally invalid or temporally impossible requests before network submission;
- display backend-returned metrics, series, hashes and provenance;
- format values for readability;
- persist the current workspace settings locally as a convenience.

It must not:

- resolve historical Universe membership;
- infer or substitute current constituents for PIT membership;
- silently truncate an oversized PIT Universe;
- download separate market history to fill server failures;
- rerun Exhaustive selection mathematics in the browser;
- recompute Portfolio performance, CAGR, Sortino, drawdown or transaction costs;
- fabricate a benchmark OOS series that is absent from the response;
- transform a failed research run into a partial success;
- treat browser validation as the final research authority.

Backend contracts remain authoritative for PIT evidence, market data, selection, continuous OOS ledger and metrics.

## 3. Request model

The workspace maps directly to `POST /api/v1/research/walk-forward`.

User-editable public V1 fields are limited to the existing 4A-5 contract:

- `selector.universe`;
- `selector.benchmark`;
- `selector.holdingCount`;
- `execution.initialAmountTwd`;
- `execution.transitionCostBps`;
- one or more explicit Training / Decision / Evaluation periods.

The UI must not expose unversioned methodology knobs such as alternate scoring formulas, Training transaction costs, public rebalance modes or AI-generated strategy parameters merely because a lower-level component could technically represent them.

## 4. Browser causal validation

Browser validation exists to prevent avoidable invalid submissions and improve UX. The backend repeats all authoritative checks.

V1 pre-validates at least:

- 1–24 periods;
- holding count 1–20;
- positive initial TWD amount within the public API bound;
- transition cost within the public API bound;
- canonical lowercase Universe id syntax;
- uppercase benchmark symbol presentation;
- valid ISO calendar dates;
- `trainingStart <= trainingEnd <= decisionDate < evaluationStart <= evaluationEnd`;
- Evaluation end no later than the last complete UTC calendar day;
- strictly increasing Decision dates;
- no overlapping Evaluation windows;
- a later Decision cannot precede the previous Evaluation end.

A request passing browser validation means only that it is structurally eligible to be submitted. It does not imply that PIT membership is authoritative, candidate count is <=100, market data is complete, Exhaustive combinations fit the server budget or the run will succeed.

## 5. Workspace settings persistence

The browser may persist the current Walk-Forward settings in local storage under a versioned workspace key.

This is **not** ResearchRun persistence.

Local settings persistence does not provide:

- immutable research identity;
- server-side storage;
- named runs;
- rerun history;
- comparison history;
- durable result storage;
- cross-device research memory;
- AI research memory.

Those capabilities belong to the later ResearchRun / research-memory phase.

## 6. Execution lifecycle

V1 executes the existing synchronous public Walk-Forward request.

The UI must:

- disable incompatible editing while a request is active;
- expose a clear active state rather than pretending the request is background work;
- allow cancellation through `AbortController`;
- invalidate an old result when research-defining settings change;
- ignore a late response from an aborted or superseded request;
- avoid automatic retry loops that would consume the public research rate limit;
- explain the current backend limit of at most two research POST requests per minute.

The UI does not create a queue or persistent background job abstraction over the synchronous API.

## 7. Failure semantics

The workspace translates common HTTP failure classes into user-readable context while preserving backend failure truth.

At minimum:

- `429`: research rate limit reached; do not silently retry;
- `422`: request/date/causality/resource admission failed;
- `409`: requested PIT evidence is unavailable or conflicts with causal requirements;
- `502`: an upstream PIT, market-data or Exhaustive authority dependency could not complete.

Unknown failures remain failures. The browser must not reinterpret them as empty data, zero return, shortened history or successful partial research.

## 8. Result presentation

V1 displays backend-authoritative continuous OOS evidence.

The primary result surface includes:

- final TWD balance;
- CAGR;
- Sortino ratio;
- maximum drawdown;
- transaction costs;
- observation count / effective period;
- continuous OOS equity curve from `oos.ledger.equity`;
- continuous OOS return-index curve from `oos.ledger.returnIndex`.

The browser may format those values but must not derive replacement performance series or recompute the metrics.

Evaluation periods remain evidence partitions. The UI must not visually or numerically imply that each period is an independently reset portfolio.

## 9. Benchmark boundary

The current Walk-Forward V1 response does not expose an independent continuous OOS benchmark series under the same OOS contract.

Therefore V1 UI explicitly states this limitation and does not:

- download benchmark history independently;
- stitch period-local benchmark series;
- reuse Training benchmark data as OOS evidence;
- show an apparent benchmark comparison unsupported by the response authority.

A benchmark curve may be added later only after a versioned backend contract exposes causally comparable continuous OOS benchmark evidence.

## 10. Decision and provenance presentation

For each frozen Decision, the workspace exposes enough returned evidence to understand the causal chain without modifying it:

- Training requested/effective dates;
- Decision date;
- Evaluation requested/effective dates;
- selected constituents and weights;
- PIT requested/source/evidence-availability dates;
- PIT authoritative/proxy truth;
- PIT version/checksum/membership policy/source;
- Training dataset hash;
- Exhaustive authority dataset hash;
- Decision hash;
- Evaluation dataset hash;
- combination count;
- selector contract identity.

The workspace also exposes Job/OOS contract identities and may export the exact returned JSON result for user-controlled archival.

Exporting JSON is not equivalent to creating a persisted ResearchRun.

## 11. Responsive UX

Desktop and mobile must expose the same research semantics.

At 390px viewport width:

- research inputs remain editable;
- run/cancel controls remain reachable;
- result metrics remain readable;
- chart width may scroll inside its bounded card when necessary;
- Decision provenance remains inspectable;
- the document must not develop page-level horizontal overflow.

Responsive layout differences must not hide causal warnings, change the request or omit failure state.

## 12. Verification requirements

The 4A-6 browser regression must cover at least:

- workspace navigation;
- request input preservation;
- causal validation preventing submission;
- normalized POST payload;
- backend metric values displayed without frontend recomputation;
- direct continuous OOS ledger series rendered as charts;
- explicit no-fabricated-benchmark boundary;
- Decision/provenance evidence presentation;
- rate-limit explanation with no retry loop;
- cancellation and late-response evidence invalidation;
- workspace-setting persistence;
- 390px settings + results with no page-level overflow;
- production asset build synchronization.

Full repository CI remains the final integration gate before merge.

## 13. Explicit non-goals

Batch 4A-6 does not include:

- persistent ResearchRun / research memory;
- server-side named run history;
- automated schedule generation;
- AI strategy generation or autonomous research planning;
- PIT fundamentals / historical fundamental narrowing;
- a new selector or scoring formula;
- a second Portfolio performance engine;
- background queues / distributed Walk-Forward execution;
- synthetic or browser-generated benchmark OOS evidence.

## 14. Next product boundary

After 4A-6 is production-verified, the next Phase A product milestone is ResearchRun / research memory: durable named runs, normalized request/result identity, reruns, comparisons and history that can later become AI research memory.
