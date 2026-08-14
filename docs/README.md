# BacktestStock Documentation Index

Status: **Canonical documentation navigation. Not a live project-status tracker.**

## Start here

| Need | Read |
| --- | --- |
| Engineering governance / AI workflow | `../AI_PROJECT_PLAYBOOK.md` |
| Product / architecture / run / test / deploy | `../README.md` |
| Current Phase / Batch / blocker / exact resume point | `../to_do_update_list.md` |
| 2026-08-14 ROADMAP-B01 historical recovery checkpoint | `ROADMAP_EXECUTION_HANDOFF_2026-08-14.md` |
| Documentation authority / freshness / cleanup rules | `PROJECT_DOCUMENTATION_POLICY.md` |
| Portfolio v3 ledger/API semantics | `PORTFOLIO_V3_CONTRACT.md` |
| Research contract map | `research/README.md` |
| Research-use boundaries / user-facing labels | `RESEARCH_USE_BOUNDARIES.md` |

## Current architecture / operations

- `adr/0001-runtime-and-quant-authority.md` — durable runtime/quant architecture decision.
- `UNIFIED_TWD_CONTRACT.md` — cross-market TWD valuation contract.
- `METRICS_REPRODUCIBILITY.md` — metric reproducibility/provenance rules.
- `RESEARCH_USE_BOUNDARIES.md` — required Historical in-sample, Current-universe, and compatibility Gross return wording.
- `PORTFOLIO_V3_CONTRACT.md` — current Portfolio v3 ledger/API/analytics/Edge semantic contract.
- `DEPLOYMENT.md` — deployment/runtime environment procedures.
- `UNIVERSE_SCANNER_V2.md` — Scanner/Universe behavior and maintenance contract.
- `EXHAUSTIVE_OPTIMIZER_V3.md` — current exhaustive historical-search contract.

Current engineering governance is `../AI_PROJECT_PLAYBOOK.md`; current runtime architecture is README + ADR + implementation. Superseded phase-governance and migration snapshots are reconstructed from Git history rather than kept in the active documentation tree.

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

Historical documents stay in the active tree only when they retain unique current audit or semantic value. Superseded migration fixtures, rollout/status drafts and self-referential migration checks are removed after their durable semantics are represented by current contracts and runtime-facing tests; Git history remains the historical evidence source.

## Maintenance rules

1. Identify the document's authority class before editing.
2. Keep volatile status only in `to_do_update_list.md`.
3. Keep semantic versions aligned with code/tests/public schema.
4. Remove stale redundant snapshots rather than accumulating warnings around them.
5. Preserve unresolved decisions/root causes; rely on Git history for obsolete drafts.
6. A merged contract may be authoritative while a post-main operational closeout is still pending; state those separately.
7. Update this index when canonical documents are added/removed or change authority class.
