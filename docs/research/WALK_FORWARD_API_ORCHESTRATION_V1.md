# Walk-Forward API / Orchestration V1

Status: **Batch 4A-5 versioned server-orchestration contract.**

Contract versions:

- API: `walk-forward-api-2026-08-15.1`
- job: `walk-forward-job-2026-08-15.1`
- PIT client: `pit-universe-client-2026-08-15.1`
- Exhaustive HTTP placement: `exhaustive-authority-http-2026-08-15.1`

This contract turns the already-versioned Batch 4A-1 through 4A-4 boundaries into one request-scoped server workflow. It does **not** create a second PIT resolver, market-data authority, optimizer, portfolio simulator, metric engine, persistent ResearchRun store, or user-facing workspace.

## 1. Public surface

The v1 public research surface is:

- `POST /api/v1/research/walk-forward`
- `GET /api/v1/research/walk-forward/health`

The Cloudflare Worker is the same-origin edge entry point and proxies those exact routes to the Vercel backend. Unknown suffixes and wrong HTTP methods fail closed.

The POST request contains:

1. one or more explicit `periods` with Training, Decision and Evaluation dates;
2. a selector specification containing only:
   - PIT `universe`,
   - `benchmark`,
   - `holdingCount`;
3. an execution specification containing only:
   - `initialAmountTwd`,
   - inter-decision `transitionCostBps`.

Unversioned selector knobs such as public `rebalanceMode`, `bandRatio`, Training transaction cost or alternate score formulas are forbidden by the strict request schema.

## 2. Temporal processing order

For each period the server executes this order:

1. validate the explicit Walk-Forward period schedule;
2. resolve PIT membership for **exactly `decisionDate`** through the existing Worker/D1 Universe endpoint;
3. reject proxy/non-authoritative membership for public v1;
4. apply deterministic server admission limits before market-data/optimizer work;
5. fetch Training evidence for exact PIT members plus benchmark;
6. build the candidate Training `ResearchDataset` and Exhaustive authority `ResearchDataset` from the **same audited history batch**;
7. invoke the existing JavaScript Exhaustive numerical authority through the versioned HTTP placement;
8. create immutable `DecisionSnapshot` through the Batch 4A-2 selection boundary;
9. **only after the DecisionSnapshot exists**, fetch Evaluation/OOS data for the selected constituents;
10. validate the Evaluation dataset against the frozen Decision;
11. after all periods are frozen/evaluated, execute Batch 4A-4 as one continuous OOS ledger.

The primary causality invariant remains:

> `Training data <= Decision point < Evaluation/OOS data`

Evaluation data is not present in selector context and cannot retroactively change a decision hash.

## 3. PIT authority

Worker/D1 remains the sole historical-membership resolver.

Python `PITUniverseClient` consumes the existing endpoint:

`GET /api/v2/universes/{id}?asOf=YYYY-MM-DD`

The client validates and preserves the returned:

- universe id;
- requested/source/evidence dates;
- exact `fetchedAt`;
- version/checksum;
- ordered members;
- membership policy;
- authoritative/proxy truth;
- source label/URL.

It does not query D1 directly, replay archive policy, infer current constituents, or normalize a proxy observation into authoritative membership.

Public v1 rejects PIT observations where `membershipAuthoritative != true` or `source.isProxy == true`.

## 4. Training data authority and one-fetch rule

The Training market-data authority remains `TWDHistoryService` / `ResearchDatasetV1`.

For one period, exact PIT candidates and the benchmark are requested in one audited `histories_partial()` batch. Two deterministic dataset views are then built from that same batch:

- Selection candidate dataset: exact PIT candidates only;
- Exhaustive authority dataset: exact PIT candidates in the same order, followed by benchmark.

This is a reuse rule, not a new cache authority. It prevents duplicate downloads and ensures the candidate/benchmark view cannot silently diverge from the candidate Training evidence.

Every requested candidate must resolve or have an explicit `HistoryFailure`; existing Exhaustive policy still refuses silent candidate drops.

## 5. Public selector methodology lock

Batch 4A-5 exposes only the Exhaustive subset that can be interpreted consistently by the current OOS ledger:

- numerical/ranking authority: `public/exhaustive-optimizer-core.js`;
- equal weighting;
- `rebalanceMode = never`;
- Training transaction cost = `0`;
- execution delay provenance = `1` trading day;
- configured production risk-free rate remains the existing Exhaustive authority value;
- ranking/tie-break/non-finite semantics remain Batch 4A-3 authority semantics.

The Python orchestration layer does not implement CAGR, Sortino, MDD, beta, score, rebalance or ranking formulas.

This restriction is intentional. Public v1 must not optimize one trading policy in Training and execute a materially different policy in OOS merely because both runtimes can accept similarly named parameters.

## 6. Exhaustive production placement

The JavaScript authority is hosted as a dedicated Vercel Node function at:

`/api/internal/research/exhaustive-selection`

Python calls this function instead of assuming a `node` executable exists inside the Python serverless runtime.

Admission protections:

- POST only;
- request body <= 3 MiB;
- exact deployment-SHA binding when Vercel provides `VERCEL_GIT_COMMIT_SHA`;
- selection combination budget <= 500,000 per authority request;
- optional `WALK_FORWARD_INTERNAL_SECRET` or `VERCEL_AUTOMATION_BYPASS_SECRET` upgrades selection admission to secret + deployment binding;
- if no internal secret is configured, the endpoint remains in an explicitly reported `deployment-bound-bounded-fallback` mode rather than pretending cryptographic caller authentication exists.

The version probe is deliberately cheap and remains callable for deployment readiness verification. The expensive selection path is always bounded even in fallback mode.

This admission layer protects compute placement; it is not a substitute for PIT/data causality validation.

## 7. Synchronous job budgets

V1 is intentionally request-scoped and bounded:

- periods <= 24;
- PIT candidates <= 100;
- public holding count <= 20;
- Exhaustive combinations <= 500,000 per period;
- Exhaustive combinations <= 2,000,000 per job;
- public request body <= 128 KiB;
- edge/backend research rate limiting applies;
- Node authority has an explicit bounded runtime configuration.

If exact PIT membership contains more than 100 symbols, the server fails closed.

It must **not**:

- take the first 100;
- sort current constituents and truncate;
- use current fundamentals as a historical prefilter;
- silently drop candidates with missing history.

Safe large-universe narrowing requires a separately governed PIT-capable selection/filtering evidence source, expected in the later PIT-fundamentals roadmap.

## 8. OOS execution semantics

Batch 4A-4 remains the portfolio/metric authority.

Public 4A-5 v1 supports:

- one continuous TWD OOS ledger;
- no period-local NAV reset;
- no in-segment rebalance;
- optional transaction cost only when a later frozen Decision changes the target;
- reinvested-distribution ResearchDataset evidence;
- no external cashflows;
- no leverage/debt state;
- existing Portfolio v3 transaction-cost and metric calculations.

The API does not create another OOS simulator or score path.

## 9. Identity and reproducibility

A completed response includes:

- API/job contract versions;
- `asOfDate` and as-of policy;
- normalized request methodology;
- Training and authority dataset hashes;
- each immutable DecisionSnapshot and decision hash;
- each Evaluation dataset hash;
- continuous OOS contract/ledger/metrics;
- deterministic `jobHash` over the normalized request and versioned evidence identities.

`jobHash` is a reproducibility identity for the completed synchronous result. It is **not** a persisted ResearchRun id and does not imply server-side research memory.

Persistent research memory / rerunnable named runs belong to a later roadmap phase.

## 10. Deployment topology and readiness

Production topology:

`Browser / future 4A-6 UI -> Cloudflare same-origin Worker -> Vercel Python Walk-Forward API`

Python orchestration then uses:

- Worker/D1 Universe endpoint for PIT membership;
- existing market-data services for Training/Evaluation evidence;
- Vercel Node function for the existing JavaScript Exhaustive authority.

Production deployment must verify more than route existence. The Walk-Forward smoke waits until:

1. the Vercel Node authority reports the expected deployment SHA and versioned authority identity;
2. Worker-routed Walk-Forward health reports the same expected deployment SHA and API/job contract versions.

This closes the Cloudflare/Vercel concurrent-deployment race before the rollout is accepted.

## 11. Failure semantics

The service fails closed on at least:

- invalid/overlapping temporal schedule;
- incomplete requested historical period under the existing as-of policy;
- missing/noncausal/mismatched PIT response;
- proxy/non-authoritative PIT membership;
- unsupported candidate/universe size;
- excessive Exhaustive combinations;
- missing candidate/benchmark Training history;
- corporate-action evidence that existing Exhaustive policy rejects;
- authority version/dataset/result mismatch;
- Evaluation fetched/validated outside the frozen decision contract;
- unsupported OOS cashflow/leverage/distribution state;
- Vercel authority deployment mismatch;
- production readiness mismatch between Worker and Vercel.

No failure path is authorized to substitute current fundamentals, current membership, approximate portfolio mathematics or a second optimizer.

## 12. Explicit non-goals

Batch 4A-5 does not include:

- user-facing Walk-Forward UX/workspace — Batch 4A-6;
- automatic schedule generation or AI strategy design;
- PIT fundamentals / historical fundamental filtering;
- S&P 500-scale historical narrowing without PIT evidence;
- persistent ResearchRun storage or research memory;
- background/queue orchestration;
- distributed Exhaustive compute;
- new ranking/alpha/portfolio methodology;
- reactivation of frozen security/perimeter PR #147.

## 13. Required regressions

The implementation must keep regression evidence for:

- strict PIT payload/provenance parsing;
- proxy truth preservation and public rejection;
- PIT -> Training fetch -> selection -> Evaluation fetch ordering;
- exactly one shared Training fetch per period for candidates + benchmark;
- no silent >100 candidate truncation;
- strict public API schema excluding unversioned strategy knobs;
- health not consuming research quota;
- Node pre-parsed/raw body compatibility;
- server Exhaustive combination cap;
- optional internal-secret admission;
- same-origin Worker path/body/header behavior;
- request/body limits;
- production deployment-SHA readiness smoke;
- full repository CI and post-main production smoke before Batch 4A-5 closes.
