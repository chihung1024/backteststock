# BacktestStock Documentation Index

`docs/` contains durable technical knowledge that cannot be derived cheaply from code/tests/runtime alone. It is not a second governance or project-history system.

Active work begins with:

```text
AGENTS.md → to_do_update_list.md → relevant code/contracts → current Git/PR/CI/runtime truth
```

## Product / operational contracts

- `../README.md` — product architecture, local setup and top-level usage.
- `SCANNER_CONTRACT.md` — Universe publication, current/PIT Scanner behavior, date/cache semantics.
- `EXHAUSTIVE_OPTIMIZER_V3.md` — full-period Exhaustive historical-search contract.
- `PORTFOLIO_V3_CONTRACT.md` — Portfolio v3 ledger/API/analytics contract.
- `UNIFIED_TWD_CONTRACT.md` — cross-market TWD valuation and return-component boundary.
- `DEPLOYMENT.md` — deploy, smoke, secrets and rollback runbook.

## Quantitative contracts

- `quant/METRIC_AUTHORITY.md` — metric authority map, formulas, corporate-action/reproducibility semantics.
- `quant/RETURN_SEMANTICS.md` — return semantics.
- `quant/RISK_MODEL_POLICY.md` — risk-model policy.
- `quant/RISK_MATHEMATICS_V1.md` — covariance/correlation/risk mathematics.

## Research contracts

- `research/RESEARCH_DATASET_V1.md` — reproducible audited research-data boundary.
- `research/WALK_FORWARD_CONTRACT.md` — temporal firewall, selection, continuous OOS, API/admission/UI.
- `research/OPTIMIZER_HUB_CONTRACT.md` — configured Dual Momentum, allocation and bounded nested tuning.
- `research/REFINERY_CONTRACT.md` — read-only diagnostics, clustering/redundancy and marginal experiments.
- `research/RESEARCH_RUN_MEMORY_V1.md` — durable completed research / rerun authority.

## Architecture decisions

- `adr/0001-runtime-and-quant-authority.md` — durable runtime/quant authority split.

## Documentation rule

Prefer updating the existing contract that owns a semantic boundary.

Create a new durable document only for a genuinely independent long-lived contract, architecture decision, reusable runbook or material RCA that cannot be expressed clearly in an existing authority.

Do not preserve phase-by-phase rollout diaries, transient CI investigations, closed plans or stale status copies in the live tree. Git/PR/Actions already preserve that history.

If prose conflicts with code/tests/current runtime, investigate the drift; do not use stale prose to override current system truth.
