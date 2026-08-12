# Research Documentation Index

Status: **Canonical navigation for BacktestStock research contracts.**

This index identifies which document owns which semantic boundary. Current execution status belongs in root `to_do_update_list.md`.

## Reading order

1. `../../AI_PROJECT_PLAYBOOK.md`
2. `../../to_do_update_list.md`
3. `../PROJECT_DOCUMENTATION_POLICY.md`
4. `RESEARCH_DATASET_V1.md`
5. `../quant/RISK_MATHEMATICS_V1.md`
6. `REFINERY_API_V1.md`
7. `REFINERY_UI_V1.md`
8. `REFINERY_CLUSTERING_V1.md`
9. corresponding implementation and tests

Closed implementation/convergence/production-acceptance narratives are reconstructed from Git/PR/Issue/Actions history when needed; they are not parallel contract authorities.

## Current main contract map

| Document | Authority |
| --- | --- |
| `RESEARCH_DATASET_V1.md` | reproducible research-data boundary: requested/resolved/failure membership, calendars, TWD/native/FX matrices, audits, fingerprints, dataset identity |
| `../quant/RISK_MATHEMATICS_V1.md` | pure covariance/correlation/risk mathematics |
| `REFINERY_API_V1.md` | public read-only Refinery request/resource/fail-closed API contract; request contract `refinery-v1`, current response schema `.3` |
| `REFINERY_UI_V1.md` | Refinery workspace/presentation/persistence boundary |
| `REFINERY_CLUSTERING_V1.md` | current Phase 5 clustering/redundancy methodology, bootstrap/factor/common-sample evidence and descriptive redundancy semantics; current clustering contract `.2` |

Phase 5 clustering/redundancy implementation is merged to production `main` and **is a current main authority**. Operational history is retained in GitHub PR/Issue/Actions evidence rather than a live-tree closeout plan.

## Semantic boundaries

### Dataset identity vs downstream analytical identity

`ResearchDataset.dataset_hash` represents the full reproducible dataset under its contract. A downstream primitive may require a narrower canonical identity for its exact effective sample; it must not silently repurpose the ResearchDataset hash.

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
