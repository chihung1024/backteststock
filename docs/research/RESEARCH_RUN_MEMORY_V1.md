# ResearchRun Memory V1

Status: **Current durable completed-research / rerun contract.**

ResearchRun persists successful backend-produced research without becoming a numerical authority.

## Identity model

Three identities remain distinct:

- `jobHash` — deterministic completed Walk-Forward result identity;
- `run_id` — one durable execution/history record;
- `library_id` — one capability-scoped research library.

A rerun may create a new `run_id` while reproducing the same `jobHash`.

## Authority boundary

D1 is durable ResearchRun authority. Browser localStorage is convenience state only.

Trusted creation path:

```text
browser submits run name + normal research request
→ existing backend authorities execute the request
→ only status=completed result with valid jobHash is accepted
→ Worker persists exact accepted request + exact backend result
```

The browser cannot upload an authoritative completed result, metric, decision hash or ledger and ask D1 to trust it.

ResearchRun does not recalculate, repair or normalize quantitative evidence.

## Capability-scoped library

The current public application uses a bearer capability rather than inventing a parallel account system.

A capability is cryptographically random, stored in D1 only as a hash, and authorizes one library. The raw capability is a credential and must not appear in logs.

Future account/auth integration may attach ownership to the existing library without changing `run_id`/`jobHash` semantics.

## Public API

Base path:

```text
/api/v1/research/runs
```

Supported behavior includes:

- create a completed named run;
- list bounded summaries for the authorized library;
- fetch one exact persisted request/result;
- rerun a source run using its stored execution request.

Rerun loads the immutable stored request. The browser cannot replace it with current UI defaults.

## Persistence

D1 stores library capability metadata and run records including applicable:

- `run_id` / `library_id`;
- optional `source_run_id`;
- user-facing name;
- authoritative `job_hash`;
- exact accepted execution request JSON;
- exact completed result JSON;
- result contract/decision metadata;
- timestamps.

There is no public global run listing or cross-library lookup by job hash.

## Failure semantics

A failed research execution does not create a partial durable run.

Fail closed on invalid/unknown capability, malformed request/name, D1 failure, non-completed/invalid backend result, payload bounds or insertion failure.

## Security invariants

- raw capabilities are never stored in D1 or logs;
- ResearchRun authorization is consumed at its owning edge boundary and not forwarded as a backend data-authority credential;
- cross-library run access does not reveal whether a foreign run exists;
- responses are no-store where the current runtime contract requires;
- browser-supplied result evidence is never persistence authority.

## Replay invariant

Existing stored requests remain reconstructable.

New methodology versions do not silently mutate an old stored request during rerun. Explicit optimization requests retain their search/validation inputs; rerun does not rewrite them to the historical winning manual tuple.

## Non-goals

ResearchRun is not:

- OAuth/account/ACL design;
- arbitrary result upload;
- mutable evidence;
- automatic strategy deployment;
- scheduled research;
- a second quantitative engine.

Tests and Worker/D1 implementation are authoritative for exact limits and endpoint details.
