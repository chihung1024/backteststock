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
12. `RESEARCH_RUN_MEMORY_V1.md`
13. `OPTIMIZER_HUB_DUAL_MOMENTUM_V1.md`
14. `OPTIMIZER_HUB_ALLOCATION_V1.md`
15. `../quant/RISK_MATHEMATICS_V1.md`
16. `REFINERY_API_V1.md`
17. `REFINERY_UI_V1.md`
18. `REFINERY_CLUSTERING_V1.md`
19. corresponding implementation and tests

Closed implementation/convergence/production-acceptance narratives are reconstructed from Git/PR/Issue/Actions history when needed; they are not parallel contract authorities.

## Current main / candidate contract map

| Document | Authority |
| --- | --- |
| `RESEARCH_DATASET_V1.md` | reproducible research-data boundary: requested/resolved/failure membership, calendars, TWD/native/FX matrices, audits, fingerprints, dataset identity |
| `WALK_FORWARD_TEMPORAL_CONTRACT_V1.md` | Batch 4A-1 temporal causality firewall and immutable PIT decision identity; not a public Walk-Forward API/UI |
| `WALK_FORWARD_SELECTION_CORE_V1.md` | Batch 4A-2 internal selector boundary: exact Training dataset, explicit PIT-member outcomes, SelectionEngine isolation from OOS data, post-decision Evaluation validation |
| `WALK_FORWARD_EXHAUSTIVE_ADAPTER_V1.md` | Batch 4A-3 internal adapter binding the existing JavaScript Exhaustive numerical/ranking authority to SelectionEngine with candidates+benchmark Training provenance and golden parity |
| `WALK_FORWARD_OOS_LEDGER_V1.md` | Batch 4A-4 internal continuous Evaluation/OOS ledger: state carry across frozen decisions, Portfolio v3 transition-cost authority, no period-local NAV reset, explicit gap/execution policies |
| `WALK_FORWARD_API_ORCHESTRATION_V1.md` | Batch 4A-5 request-scoped public server workflow: Worker/D1 PIT authority consumption, causal Training→Decision→Evaluation ordering, bounded JS Exhaustive production placement, same-origin edge route, job identity and production readiness semantics |
| `WALK_FORWARD_ADMISSION_V1.md` | Batch 4A-6.1 D1-derived executable-default guard: authoritative PIT/candidate/date/combination admission, explicit blocked reasons, browser migration boundary and production-smoke requirement; not final research authority |
| `WALK_FORWARD_UI_V1.md` | Batch 4A-6 user-facing workspace: request editing/pre-validation, synchronous execution/cancellation, authoritative OOS result presentation, provenance visibility and explicit no-fabricated-benchmark boundary |
| `RESEARCH_RUN_MEMORY_V1.md` | Batch 4A-7 durable D1 ResearchRun authority: immutable original request, backend-produced completed result, run/job identity separation, capability-based library access and rerun semantics |
| `OPTIMIZER_HUB_DUAL_MOMENTUM_V1.md` | Phase 4B-1 production-accepted configured strategy contract: configured-request universe provenance, Training-only TWD Momentum, absolute/relative/Top-K selection, defensive fallback, monthly schedule and reuse of existing OOS/ResearchRun authorities |
| `OPTIMIZER_HUB_ALLOCATION_V1.md` | Phase 4B-2 candidate Allocation/Weighting contract: explicit Equal / Inverse Volatility / Risk Parity-ERC, Training-only TWD returns, formal Ledoit-Wolf covariance, signed component-risk convergence and legacy 4B-1 replay compatibility |
| `../quant/RISK_MATHEMATICS_V1.md` | pure covariance/correlation/risk mathematics |
| `REFINERY_API_V1.md` | public read-only Refinery request/resource/fail-closed API contract; request contract `refinery-v1`, Phase 3–5 response schema `.3`, plus opt-in Phase 6 marginal contract `.1` |
| `REFINERY_UI_V1.md` | Refinery workspace/presentation/persistence boundary, including the non-persisted Phase 6 explicit-plan UI |
| `REFINERY_CLUSTERING_V1.md` | current Phase 5 clustering/redundancy methodology, bootstrap/factor/common-sample evidence and descriptive redundancy semantics; current clustering contract `.2` |

Phase 4A-7 ResearchRun memory and Phase 4B-1 Dual Momentum are merged and production accepted. `OPTIMIZER_HUB_ALLOCATION_V1.md` is the Phase 4B-2 candidate authority until its PR/preview/review/merge/post-main production gates pass. Operational state is recorded in `to_do_update_list.md`.

## Semantic boundaries

### Dataset identity vs downstream analytical identity

`ResearchDataset.dataset_hash` represents the full reproducible dataset under its contract. A downstream primitive may require a narrower canonical identity for its exact effective sample; it must not silently repurpose the ResearchDataset hash.

### Walk-forward decision identity vs evaluation identity

A Walk-Forward `DecisionSnapshot` freezes the exact membership provenance, training dataset identity, selector configuration, selected constituents and weights before OOS evaluation. Existing Exhaustive decisions use exact PIT evidence. Phase 4B configured-strategy decisions use separately versioned request-defined membership evidence and must never fabricate PIT provenance. Evaluation data may score a frozen decision but must not mutate the same decision hash or retroactively become selection evidence.

### Selection input vs Evaluation/OOS input

A `SelectionEngine` receives one exact Training `ResearchDataset` plus immutable membership provenance and candidate accounting. Existing Exhaustive research uses PIT membership; configured strategy research may use an explicitly hash-bound request universe under its own contract. Engine-specific causal Training evidence must remain inside the Training window. Evaluation/OOS datasets remain absent from selection and are validated only after a `DecisionSnapshot` exists.

### Existing Exhaustive authority vs Walk-Forward adapter

The Walk-Forward Exhaustive adapter does not own portfolio simulation or score mathematics. `public/exhaustive-optimizer-core.js` remains the numerical authority; the Python adapter owns only causal evidence validation, provenance binding and conversion of the authoritative winning combination into `SelectionResult`. Golden parity must fail rather than normalize an authority-version/result change in Python.

### Configured strategy provenance vs PIT membership

A user-defined strategy universe is not historical index-membership evidence. Phase 4B configured strategies therefore bind canonical ordered symbols directly into a separately versioned configured-request identity. They do not add synthetic `sourceAsOf`, authority flags or other PIT fields. Existing PIT payload/hash semantics remain reconstructable and regression-protected.

### Evaluation segments vs one investable OOS ledger

Walk-Forward Evaluation periods are evidence partitions, not independent portfolios. Batch 4A-4 carries actual ending OOS equity/allocation into the next frozen target, delegates inter-decision turnover/cost to Portfolio v3, and computes metrics once from one continuous ledger. Period-local NAV reset/average/stitch semantics are not a valid substitute. Evaluation-window gaps do not authorize hidden market observations: V1 carries the last audited state flat until the next validated OOS baseline.

### Walk-Forward admission vs final research authority

Batch 4A-6.1 derives an executable-default recommendation for the PIT/Exhaustive path from the same D1 PIT archive and already-versioned synchronous capacity ceilings before the browser mounts a new/legacy-default workspace. Admission does not authorize configured-strategy membership and does not read market history, select securities or guarantee execution success. `POST /api/v1/research/walk-forward` remains the final fail-closed research authority.

### Walk-Forward API authority vs UI presentation

The Portfolio web application exposes the request-scoped Walk-Forward authority. Browser validation is an early UX guard only. Worker/D1 PIT evidence where applicable, configured-request identity where applicable, ResearchDataset, selection, continuous OOS ledger and Portfolio metrics remain backend authorities. The UI may format returned evidence but must not recompute signals/performance, substitute failed history evidence or fabricate benchmark series.

### Request-scoped orchestration vs persistent research memory

Walk-Forward execution composes Training evidence, immutable decisions and continuous OOS results into deterministic backend-produced job identity. Batch 4A-7 separately persists named completed ResearchRuns in D1. `jobHash` remains completed-result identity; `run_id` remains durable ResearchRun identity. Rerun reuses the immutable stored original request and creates a new run/result rather than mutating the source run. Browser-submitted completed results are not authoritative.

### PIT membership authority vs API orchestration

For PIT-based research, Python does not own historical membership. Worker/D1 remains the PIT authority and Python consumes the versioned causal Universe response for exactly each Decision date. Large PIT universes must fail closed when synchronous Exhaustive bounds are exceeded; current fundamentals, current constituents and arbitrary truncation are not authorized substitutes.

### TWD risk vs native-currency diagnostics

TWD returns remain the Taiwanese-investor valuation/risk authority. Native-currency returns may support explicitly scoped diagnostics, but computability does not by itself prove economic/model applicability.

### Factor computability vs verdict applicability

Current Phase 5 policy separates `factor_computable`, `factor_model_scope` and `factor_corroboration_eligible`. U.S.-factor co-movement diagnostics may be displayed while verdict corroboration remains fail-closed without traceable instrument-scope authority.

### Diagnosis vs recommendation

Research diagnostics do not imply KEEP/TRIM/REPLACE, selection, sizing or forward-performance claims. Those require explicitly versioned strategy/allocation/validation governance.

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
