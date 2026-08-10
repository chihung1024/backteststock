# BacktestStock Documentation Index

Status: Canonical navigation for repository documentation. **Not a live project-status tracker.** Current Phase/Batch/PR/check state belongs in root `to_do_update_list.md`.

## 1. Start here

| Need | Read |
| --- | --- |
| Engineering rules / AI workflow | `../AI_PROJECT_PLAYBOOK.md` |
| Product / architecture / local run | `../README.md` |
| Current project status / exact resume point | `../to_do_update_list.md` |
| Documentation authority / freshness / version rules | `PROJECT_DOCUMENTATION_POLICY.md` |
| Current research contract map | `research/README.md` |

## 2. Current architecture / governance

- `PHASE_MINUS1_GOVERNANCE.md` — governance/architecture hardening baseline and historical Phase -1 record.
- `adr/0001-runtime-and-quant-authority.md` — runtime/quant authority architectural decision.
- `UNIFIED_TWD_CONTRACT.md` — cross-market TWD valuation contract.
- `METRICS_REPRODUCIBILITY.md` — metric reproducibility/provenance rules.
- `DEPLOYMENT.md` — deployment/runtime environment procedures.
- `PROJECT_DOCUMENTATION_POLICY.md` — documentation governance and staleness prevention.

## 3. Quantitative contracts

Directory: `quant/`

- `METRIC_AUTHORITY.md`
- `RETURN_SEMANTICS.md`
- `RISK_MODEL_POLICY.md`
- `RISK_MATHEMATICS_V1.md`

These documents define mathematical/data semantics. They are not user-facing strategy recommendations.

## 4. Research / Portfolio Refinery

Directory: `research/`

Use `research/README.md` for the canonical reading order and authority map.

Current principal contracts:

- `research/RESEARCH_DATASET_V1.md`
- `research/REFINERY_API_V1.md`
- `research/REFINERY_UI_V1.md`
- `research/REFINERY_CLUSTERING_V1.md`

Active review/convergence documents are clearly labelled as review plans and do not silently replace accepted methodology contracts.

## 5. Scanner / Exhaustive

Current/product-contract documents include:

- `UNIVERSE_SCANNER_V2.md`
- `EXHAUSTIVE_OPTIMIZER_V3.md`

Historical or superseded design/status snapshots may also remain in `docs/` for auditability, including:

- `EXHAUSTIVE_OPTIMIZER_V2.md`
- `PORTFOLIO_OPTIMIZER_MVP.md`
- `OPTIMIZER_IMPLEMENTATION_STATUS.md`

**Do not use a historical snapshot as live project state.** Verify the current implementation/route/test contract and root `to_do_update_list.md` before changing production behavior.

## 6. Portfolio migration / production history

Directory: `portfolio-migration/`

These files preserve migration/cutover evidence and should be read as historical/operational records unless the live roadmap explicitly names one as an active contract.

## 7. Documentation maintenance rules

When adding or changing a document:

1. identify its authority class in `PROJECT_DOCUMENTATION_POLICY.md`;
2. avoid duplicating volatile live status outside `to_do_update_list.md`;
3. add a clear Status line when the document is historical, versioned, active-review, superseded or current;
4. preserve old root-cause/decision evidence instead of rewriting history;
5. update this index or the research index when a new canonical document is introduced;
6. verify links, version strings and code/test references before merge.
