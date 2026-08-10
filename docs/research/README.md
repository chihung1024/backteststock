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
8. the active Phase contract/review plan when it exists on the working branch
9. corresponding implementation and tests

## Current main contract map

| Document | Authority |
| --- | --- |
| `RESEARCH_DATASET_V1.md` | reproducible research-data boundary: requested/resolved/failure membership, calendars, TWD/native/FX matrices, audits, fingerprints, dataset identity |
| `../quant/RISK_MATHEMATICS_V1.md` | pure covariance/correlation/risk mathematics |
| `REFINERY_API_V1.md` | public read-only Refinery request/resource/fail-closed API contract |
| `REFINERY_UI_V1.md` | Refinery workspace/presentation/persistence boundary |

Phase 5 clustering/redundancy methodology is currently under review in PR #65/#66 and is **not yet a `main` authority**. When accepted, its versioned contract must be added here in the same Batch that lands it.

## Semantic boundaries

### Dataset identity vs downstream analytical identity

`ResearchDataset.dataset_hash` represents the full reproducible dataset under its contract. A downstream primitive may require a narrower canonical identity for its exact effective sample; it must not silently repurpose the ResearchDataset hash.

### TWD risk vs native-currency diagnostics

TWD returns remain the Taiwanese-investor valuation/risk authority. Native-currency returns may support explicitly scoped diagnostics, but computability does not by itself prove economic/model applicability.

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
