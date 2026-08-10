# Research Documentation Index

Status: Canonical navigation/index for BacktestStock research contracts.

This index tells a developer or Agent **which document owns which semantic boundary**. It is not a live project-status tracker; current execution status belongs in root `to_do_update_list.md`.

## 1. Reading order

For current Portfolio Refinery work, read in this order:

1. `../../AI_PROJECT_PLAYBOOK.md`
2. `../../to_do_update_list.md`
3. `../PROJECT_DOCUMENTATION_POLICY.md`
4. `RESEARCH_DATASET_V1.md`
5. `../quant/RISK_MATHEMATICS_V1.md`
6. `REFINERY_API_V1.md`
7. `REFINERY_UI_V1.md`
8. `REFINERY_CLUSTERING_V1.md`
9. current Phase review/convergence plan when one exists
10. implementation and tests corresponding to the active contract

## 2. Contract map

| Document | Authority | Current role |
| --- | --- | --- |
| `RESEARCH_DATASET_V1.md` | reproducible research data boundary | requested/resolved/failure membership, calendars, TWD/native/FX matrices, audits, fingerprints, deterministic dataset hash |
| `../quant/RISK_MATHEMATICS_V1.md` | pure risk mathematics | covariance, correlation, effective dimensions, portfolio risk decomposition |
| `REFINERY_API_V1.md` | public read-only Refinery API | request/resource/fail-closed semantics and additive analysis response schema |
| `REFINERY_UI_V1.md` | Refinery workspace/presentation contract | workspace isolation, persistence, API boundary, rendering/performance/accessibility rules |
| `REFINERY_CLUSTERING_V1.md` | Phase 5 clustering/redundancy methodology | correlation distance, linkage, stability, redundancy evidence, factor/theme evidence |
| `PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md` | active review plan, not production authority | methodology/code/doc drift found during Phase 5 review and exact amendments required before merge |

## 3. Phase progression

```text
Phase 1  ResearchDatasetV1
  |
Phase 2  Risk Mathematics
  |
Phase 3  Refinery API
  |
Phase 4  Refinery UI
  |
Phase 5  Clustering & Redundancy
  |
Phase 6  Marginal Experiments
  |
Phase 7  Walk-Forward / Research Validity
  |
Phase 8  Selection Policy
  |
Phase 9  Sizing
  |
Phase 10 Validated Exhaustive Integration
  |
Phase 11 Point-in-Time Universe / Alpha / Economic Factors
```

Later phases may consume earlier evidence, but must not silently redefine earlier authorities.

## 4. Semantic boundaries that must remain distinct

### Dataset identity vs analytical seed identity

`ResearchDataset.dataset_hash` answers whether the full reproducible dataset export is identical under its contract. A downstream stochastic/deterministic research primitive may need a narrower canonical identity if its output must be invariant to metadata/order that is intentionally part of the dataset identity. Such a decision must be versioned and documented; one hash must not be silently repurposed to mean both things.

### TWD risk vs native-currency factor diagnostic

- TWD returns remain the primary Taiwanese-investor valuation/risk authority.
- Native-currency returns may be used for explicitly scoped factor diagnostics so FX translation is not confused with factor loading.
- Factor evidence is secondary and its sample/applicability rules must remain explicit.

### Structural dependence vs tactical dependence

- structural clustering uses synchronized weekly TWD returns;
- medium/tactical daily views remain separate evidence;
- downside/stress views depend on benchmark-conditioned observations;
- these are not collapsed into one universal correlation concept.

### Diagnosis vs recommendation

Through Phase 6, evidence is descriptive/historical. KEEP/TRIM/REPLACE, selection and sizing require later validation gates and must not be inferred from a HIGH redundancy label alone.

## 5. Contract/version consistency checklist

Before a research PR merges:

- [ ] document status reflects the real Phase state;
- [ ] version string in docs matches code constant;
- [ ] public API methodology/schema exposes the intended version;
- [ ] tests cover the versioned semantics;
- [ ] UI types/labels match the response shape if exposed;
- [ ] `to_do_update_list.md` records the decision and evidence;
- [ ] old semantics remain reconstructable from Git history / prior version text;
- [ ] active review plan has no unresolved BLOCKER.

## 6. Phase 5 current review state

`REFINERY_CLUSTERING_V1.md` remains the Phase 5 methodology document, but the current implementation is **not merge-approved** while `PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md` has unresolved methodology amendments concerning:

1. bootstrap seed-data identity;
2. complete-month factor alignment;
3. factor computability vs applicability/corroboration;
4. common-sample factor-implied relationship semantics.

The review plan must not be mistaken for a second implementation contract. Accepted amendments are promoted into the clustering contract/code/tests together.
