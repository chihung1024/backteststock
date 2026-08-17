# Research Documentation Index

Status: **Canonical navigation for BacktestStock research contracts.**

This index identifies which document owns which semantic boundary. Current execution status belongs in root `to_do_update_list.md`.

## Reading order

1. `../../AI_PROJECT_PLAYBOOK.md`
2. `../../to_do_update_list.md`
3. `../PROJECT_DOCUMENTATION_POLICY.md`
4. `RESEARCH_DATASET_V1.md`
5. `WALK_FORWARD_TEMPORAL_CONTRACT_V1.md`
6. `WALK_FORWARD_SELECTION_CORE_V1.md`
7. `WALK_FORWARD_EXHAUSTIVE_ADAPTER_V1.md`
8. `WALK_FORWARD_OOS_LEDGER_V1.md`
9. `WALK_FORWARD_API_ORCHESTRATION_V1.md`
10. `WALK_FORWARD_ADMISSION_V1.md`
11. `WALK_FORWARD_UI_V1.md`
12. `../quant/RISK_MATHEMATICS_V1.md`
13. `REFINERY_API_V1.md`
14. `REFINERY_UI_V1.md`
15. `REFINERY_CLUSTERING_V1.md`
16. corresponding implementation and tests

Closed implementation/convergence/production-acceptance narratives are reconstructed from Git/PR/Issue/Actions history when needed; they are not parallel contract authorities.

## Current main contract map

| Document | Authority |
| --- | --- |
| `RESEARCH_DATASET_V1.md` | reproducible research-data boundary: requested/resolved/failure membership, calendars, TWD/native/FX matrices, audits, fingerprints, dataset identity |
| `WALK_FORWARD_TEMPORAL_CONTRACT_V1.md` | Batch 4A-1 temporal causality firewall and immutable decision identity; not a public Walk-Forward API/UI |
| `WALK_FORWARD_SELECTION_CORE_V1.md` | Batch 4A-2 internal selector boundary: exact Training dataset, explicit PIT-member outcomes, SelectionEngine isolation from OOS data, post-decision Evaluation validation |
| `WALK_FORWARD_EXHAUSTIVE_ADAPTER_V1.md` | Batch 4A-3 internal adapter binding the existing JavaScript Exhaustive numerical/ranking authority to SelectionEngine with candidates+benchmark Training provenance and golden parity |
| `WALK_FORWARD_OOS_LEDGER_V1.md` | Batch 4A-4 internal continuous Evaluation/OOS ledger: state carry across frozen decisions, Portfolio v3 transition-cost authority, no period-local NAV reset, explicit gap/execution policies |
| `WALK_FORWARD_API_ORCHESTRATION_V1.md` | Batch 4A-5 request-scoped public server workflow: Worker/D1 PIT authority consumption, causal Training→Decision→Evaluation ordering, bounded JS Exhaustive production placement, same-origin edge route, job identity and production readiness semantics |
| `WALK_FORWARD_ADMISSION_V1.md` | Batch 4A-6.1 D1-derived executable-default guard: authoritative PIT/candidate/date/combination admission, explicit blocked reasons, browser migration boundary and production-smoke requirement; not final research authority |
| `WALK_FORWARD_UI_V1.md` | Batch 4A-6 user-facing workspace: request editing/pre-validation, synchronous execution/cancellation, authoritative OOS result presentation, provenance visibility and explicit no-fabricated-benchmark boundary |
| `../quant/RISK_MATHEMATICS_V1.md` | pure covariance/correlation/risk mathematics |
| `REFINERY_API_V1.md` | public read-only Refinery request/resource/fail-closed API contract; request contract `refinery-v1`, Phase 3–5 response schema `.3`, plus opt-in Phase 6 marginal contract `.1` |
| `REFINERY_UI_V1.md` | Refinery workspace/presentation/persistence boundary, including the non-persisted Phase 6 explicit-plan UI |
| `REFINERY_CLUSTERING_V1.md` | current Phase 5 clustering/redundancy methodology, bootstrap/factor/common-sample evidence and descriptive redundancy semantics; current clustering contract `.2` |

Phase 5 clustering/redundancy implementation is merged to production `main` and **is a current main authority**. Phase 6 is a separately versioned opt-in extension under candidate validation; its current execution state is recorded in `to_do_update_list.md`. Operational history is retained in GitHub PR/Issue/Actions evidence rather than a live-tree closeout plan.

## Semantic boundaries

### Dataset identity vs downstream analytical identity

`ResearchDataset.dataset_hash` represents the full reproducible dataset under its contract. A downstream primitive may require a narrower canonical identity for its exact effective sample; it must not silently repurpose the ResearchDataset hash.

### Walk-forward decision identity vs evaluation identity

A Walk-Forward `DecisionSnapshot` freezes the exact PIT evidence, training dataset identity, selector configuration, selected constituents and weights before OOS evaluation. Evaluation data may score that decision but must not mutate the same decision hash or retroactively become selection evidence.

### Selection input vs Evaluation/OOS input

A `SelectionEngine` receives the exact PIT-candidate Training `ResearchDataset` plus candidate accounting. Engine-specific causal Training evidence, such as the Exhaustive candidates+benchmark authority dataset, must remain inside the Training window, be explicitly hash-bound in selector parameters, and must not change eligible PIT membership. Evaluation/OOS datasets remain absent from selection and are validated only after a `DecisionSnapshot` exists.

### Existing Exhaustive authority vs Walk-Forward adapter

The Walk-Forward Exhaustive adapter does not own portfolio simulation or score mathematics. `public/exhaustive-optimizer-core.js` remains the numerical authority; the Python adapter owns only causal evidence validation, provenance binding and conversion of the authoritative winning combination into `SelectionResult`. Golden parity must fail rather than normalize an authority-version/result change in Python.

### Evaluation segments vs one investable OOS ledger

Walk-Forward Evaluation periods are evidence partitions, not independent portfolios. Batch 4A-4 carries actual ending OOS equity/allocation into the next frozen target, delegates inter-decision turnover/cost to Portfolio v3, and computes metrics once from one continuous ledger. Period-local NAV reset/average/stitch semantics are not a valid substitute. Evaluation-window gaps do not authorize hidden market observations: V1 carries the last audited state flat until the next validated OOS baseline.

### Walk-Forward admission vs final research authority

Batch 4A-6.1 derives an executable-default recommendation from the same D1 PIT archive and already-versioned synchronous capacity ceilings before the browser mounts a new/legacy-default workspace. Admission may block proxy membership, oversized candidate sets, impossible causal windows or excessive Exhaustive combinations, but it does not read market history, select securities or guarantee execution success. `POST /api/v1/research/walk-forward` remains the final fail-closed research authority.

### Walk-Forward API authority vs UI presentation

Batch 4A-6 exposes the existing request-scoped Walk-Forward API through the Portfolio web application. Browser validation is an early UX guard only; Worker/D1 PIT evidence, ResearchDataset, Exhaustive selection, continuous OOS ledger and Portfolio metrics remain server-side authorities. The UI may format returned evidence but must not recompute performance, substitute failed PIT/history evidence or fabricate a continuous benchmark series that the V1 response does not contain.

### Request-scoped orchestration vs persistent research memory

Batch 4A-5 may compose PIT evidence, Training datasets, immutable decisions and continuous OOS results into one deterministic `jobHash`, but that hash is not a persisted ResearchRun id. The API remains synchronous and request-scoped. Durable named runs, result storage, reruns, comparison history and AI research memory require a separately governed persistence contract later in the roadmap.

### PIT membership authority vs API orchestration

The Python Walk-Forward API does not own historical membership. Worker/D1 remains the PIT authority and Python consumes the versioned causal Universe response for exactly each Decision date. Large PIT universes must fail closed when synchronous Exhaustive bounds are exceeded; current fundamentals, current constituents and arbitrary truncation are not authorized substitutes.

### TWD risk vs native-currency diagnostics

TWD returns remain the Taiwanese-investor valuation/risk authority. Native-currency returns may support explicitly scoped diagnostics, but computability does not by itself prove economic/model applicability.

### Factor computability vs verdict applicability

Current Phase 5 policy separates `factor_computable`, `factor_model_scope` and `factor_corroboration_eligible`. U.S.-factor co-movement diagnostics may be displayed while verdict corroboration remains fail-closed without traceable instrument-scope authority.

### Diagnosis vs recommendation

Research diagnostics do not imply KEEP/TRIM/REPLACE, selection, sizing or forward-performance claims. Those require later validation/governance phases.

## Contract consistency checklist

Before a research PR merges:

- document status matches real Phase state;
- version strings match code/public schema;
- tests cover versioned semantics;
- UI types/labels match exposed fields;
- `to_do_update_list.md` records decisions and remaining risk;
- old semantics remain reconstructable from Git history;
- unresolved BLOCKER findings are zero.

After a merge, distinguish **contract authority** from any still-pending **post-main operational closeout** rather than leaving the contract index in a pre-merge state.
