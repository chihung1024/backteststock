# ResearchRun Memory V1

Status: **Batch 4A-7A internal contract candidate.**

Contract version: `research-run-memory-2026-08-17.1`

## Purpose

ResearchRun Memory turns a successfully completed Walk-Forward request into durable, recoverable research history without changing any quantitative authority.

The durable identities are intentionally distinct:

- `jobHash` remains the immutable identity of a completed Walk-Forward research result.
- `run_id` identifies one durable execution/history record. Re-running the same deterministic request may therefore create another `run_id` with the same `jobHash`.
- `library_id` identifies one capability-scoped research library.

Neither `run_id` nor `library_id` may replace `jobHash` in research-result identity or causal evidence.

## Authority boundary

D1 is the durable ResearchRun authority. Browser localStorage is never a durable run/result authority.

The browser is not allowed to submit a completed result for persistence. The trusted creation path is:

1. browser submits a run name plus a normal Walk-Forward request;
2. Worker invokes the existing public Walk-Forward execution path;
3. existing PIT / ResearchDataset / SelectionEngine / Exhaustive / OOS ledger / Portfolio metric authorities produce the result;
4. only a successful `status=completed` backend result may be persisted;
5. Worker stores the exact request that was accepted for that execution separately from the returned result JSON.

ResearchRun Memory must not recalculate, repair, normalize, invent or substitute research evidence.

## Capability-scoped library

The current public application has no account/session authority. V1 therefore uses a bearer capability rather than introducing a parallel OAuth/account system.

A library capability:

- is generated from 256 bits of cryptographically secure randomness;
- is returned only when a new library is first created;
- is stored by D1 only as a SHA-256 hash;
- authorizes access to exactly one `library_id`;
- may be exported/imported by the user for cross-device recovery;
- is treated by the browser as a credential, not as research data.

Future account authentication may attach ownership to an existing `library_id`; it must not require changing existing `run_id` or `jobHash` semantics.

No endpoint exists to create an empty durable library. A new library is created only as part of persisting a successfully completed first run.

## Public API

Base path:

`/api/v1/research/runs`

### POST `/api/v1/research/runs`

Body:

```json
{
  "name": "SOXX walk-forward baseline",
  "request": { "...": "normal Walk-Forward API request" }
}
```

If `Authorization: Bearer <library capability>` is supplied, the completed run is appended to that library. If no Authorization header is supplied, a new library is created only after successful execution and the response includes the one-time raw `libraryCapability`.

The body has no `result`, `jobHash`, `decisionHash`, metrics or ledger input fields. Such client-supplied fields are not persistence authority.

### GET `/api/v1/research/runs`

Requires the library bearer capability. Returns bounded run summaries newest first. It does not expose the raw capability.

### GET `/api/v1/research/runs/{run_id}`

Requires the library bearer capability and returns the exact persisted accepted request plus the completed result for that run.

A run in another library must not be distinguishable from a nonexistent run.

### POST `/api/v1/research/runs/{run_id}/rerun`

Requires the library bearer capability. The Worker loads `execution_request_json` from D1 and executes that stored request. The browser cannot replace the stored request in this operation.

A successful rerun creates a new `run_id`, stores `source_run_id`, and may legitimately reproduce the same `jobHash`.

## D1 persistence

`research_libraries` stores:

- `library_id`;
- hashed capability + hash contract version;
- creation and last-used timestamps.

`research_runs` stores:

- `run_id`;
- owning `library_id`;
- optional `source_run_id` for reruns;
- user-facing name;
- authoritative backend-produced `job_hash`;
- exact accepted `execution_request_json`;
- exact completed `result_json`;
- result contract version and decision count;
- creation timestamp.

V1 has no global public run listing and no cross-library lookup by `jobHash`.

## Failure semantics

Fail closed when:

- D1 is unavailable;
- the capability is malformed or unknown;
- request JSON/name is invalid or over bounds;
- Walk-Forward execution fails or does not return `completed` with a valid `jobHash`;
- the completed result exceeds the V1 persistence payload bound;
- durable insertion fails.

A failed Walk-Forward execution must not create an empty library or a partial durable run.

## Security invariants

- raw library capabilities are never written to D1 or logs;
- `Authorization` is consumed only at the ResearchRun edge and is never forwarded to the Vercel research backend;
- unknown-library and wrong-library run access return the same not-found semantics after authentication;
- client-supplied completed results are never accepted;
- response headers remain `no-store`;
- there is no cookie/session side authority in V1.

## Non-goals

V1 does not add:

- OAuth or user accounts;
- sharing/collaboration/ACLs;
- arbitrary result upload/import;
- mutable quantitative evidence;
- scheduled research;
- AI strategy generation;
- cross-run comparison UI;
- PIT fundamentals.

Those are later product batches and must consume ResearchRun truth rather than create a second persistence authority.
