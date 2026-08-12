# BacktestStock Documentation Index

Status: **Canonical documentation navigation. Not a live project-status tracker.**

## Start here

| Need | Read |
| --- | --- |
| Engineering governance / AI workflow | `../AI_PROJECT_PLAYBOOK.md` |
| Product / architecture / run / test / deploy | `../README.md` |
| Current Phase / Batch / blocker / exact resume point | `../to_do_update_list.md` |
| Documentation authority / freshness / cleanup rules | `PROJECT_DOCUMENTATION_POLICY.md` |
| Research contract map | `research/README.md` |

## Current architecture / operations

- `adr/0001-runtime-and-quant-authority.md` — durable runtime/quant architecture decision.
- `UNIFIED_TWD_CONTRACT.md` — cross-market TWD valuation contract.
- `METRICS_REPRODUCIBILITY.md` — metric reproducibility/provenance rules.
- `DEPLOYMENT.md` — deployment/runtime environment procedures.
- `UNIVERSE_SCANNER_V2.md` — Scanner/Universe behavior and maintenance contract.
- `EXHAUSTIVE_OPTIMIZER_V3.md` — current exhaustive historical-search contract.

Current engineering governance is `../AI_PROJECT_PLAYBOOK.md`; current runtime architecture is README + ADR + implementation. Superseded phase-governance snapshots are reconstructed from Git history rather than kept in the active documentation tree.

## Quantitative contracts

Directory: `quant/`

- `METRIC_AUTHORITY.md`
- `RETURN_SEMANTICS.md`
- `RISK_MODEL_POLICY.md`
- `RISK_MATHEMATICS_V1.md`

These define mathematical/data semantics, not investment recommendations.

## Research / Portfolio Refinery

Directory: `research/`.

Use `research/README.md` for authority and reading order.

Current main contracts include:

- `research/RESEARCH_DATASET_V1.md`
- `research/REFINERY_API_V1.md`
- `research/REFINERY_UI_V1.md`
- `research/REFINERY_CLUSTERING_V1.md`

Phase 5 clustering/redundancy methodology is preserved by the current versioned contract, implementation and regression tests. Closed implementation/closeout narratives are reconstructed from Git/PR/Issue/Actions history instead of retained as parallel status documents.

## Historical documents

Historical documents stay in the active tree only when they retain unique audit or semantic value. Superseded rollout/status drafts that add no unique value are removed and remain recoverable from Git history.

`portfolio-migration/README.md` retains frozen source provenance required by the permanent migration contract test. `portfolio-migration/PR2_LEDGER_METRICS.md` and `portfolio-migration/PR3_PORTFOLIO_V3_API.md` are retained because they still carry migration-era ledger/API semantics not yet replaced by a dedicated current contract. PR4–PR6 rollout/cutover narratives are historical Git evidence, not active documentation.

## Maintenance rules

1. Identify the document's authority class before editing.
2. Keep volatile status only in `to_do_update_list.md`.
3. Keep semantic versions aligned with code/tests/public schema.
4. Remove stale redundant snapshots rather than accumulating warnings around them.
5. Preserve unresolved decisions/root causes; rely on Git history for obsolete drafts.
6. A merged contract may be authoritative while a post-main operational closeout is still pending; state those separately.
7. Update this index when canonical documents are added/removed or change authority class.
