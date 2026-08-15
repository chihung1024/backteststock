# Walk-Forward Selection Core V1

Status: **Batch 4A-2 selection-boundary contract; internal research infrastructure, not yet a public Walk-Forward API/UI.**

## Purpose

Batch 4A-2 turns the Batch 4A-1 temporal firewall into an executable selection boundary without creating a second market-data, optimizer, Portfolio, or metrics authority.

The required causal order is:

```text
PIT membership at Decision
        +
exact Training ResearchDataset
        ↓
SelectionEngine
        ↓
immutable DecisionSnapshot
        ↓
Evaluation/OOS ResearchDataset
```

Evaluation/OOS observations are structurally unavailable to `SelectionEngine`.

## Contract identity

```text
WALK_FORWARD_SELECTION_CONTRACT_VERSION
= walk-forward-selection-2026-08-15.1
```

The contract is additive to:

- `RESEARCH_DATASET_V1.md`;
- `WALK_FORWARD_TEMPORAL_CONTRACT_V1.md`.

Batch 4A-1 remains the authority for period causality and immutable decision identity. Batch 4A-2 owns only the selector/orchestration boundary.

## Exact training dataset

`build_selection_context()` accepts exactly one `ResearchDataset` representing the requested Training window.

Required invariants:

1. `training_dataset.requested_start == period.training_start`;
2. `training_dataset.requested_end == period.training_end`;
3. requested training symbols exactly equal the PIT member sequence;
4. every PIT member has one explicit outcome:
   - resolved history, therefore eligible; or
   - `HistoryFailure`, therefore unavailable;
5. no member may be both resolved and failed;
6. the stored `ResearchDataset.dataset_hash` must still match exported content;
7. effective observations remain inside the Training window and at/before Decision.

The core does not silently drop a PIT member, substitute current membership, normalize provenance-sensitive symbols, or widen the Training window.

## SelectionContext

`SelectionContext` contains:

- `WalkForwardPeriod`;
- exact `ResolvedPITUniverse`;
- the exact Training `ResearchDataset`;
- deterministic eligible candidates;
- explicit unavailable-candidate failure evidence.

It intentionally does **not** contain:

- Evaluation/OOS `ResearchDataset`;
- future prices or returns;
- future fundamentals;
- Portfolio evaluation results.

A selector may know the scheduled Evaluation date boundaries through `WalkForwardPeriod`; date boundaries are not future observations.

## SelectionEngine

`SelectionEngine` is a framework-neutral protocol:

```text
contract_version
rule
parameters
select(SelectionContext) -> SelectionResult
```

Selector identity and parameters are snapshotted **before** `select()` executes. If an engine mutates its own configuration during execution, the frozen decision still records the configuration presented at invocation.

The Training dataset hash is captured before execution and revalidated after execution. If a selector mutates Training dataset content or identity, selection fails closed.

## SelectionResult

A selector returns only:

- selected constituents;
- weights.

The existing Batch 4A-1 `create_decision_snapshot()` remains the authority that validates and freezes:

- canonical symbols;
- selected ⊆ eligible ⊆ PIT membership;
- finite positive weights;
- weights summing to one;
- selector parameters;
- Training dataset identity;
- full decision hash.

Batch 4A-2 does not weaken or duplicate those checks.

## Configured equal-weight reference engine

`ConfiguredEqualWeightSelectionEngine` exists only to verify the orchestration contract.

It:

- makes no ranking or alpha claim;
- reads no market-price series;
- selects an explicitly configured subset;
- uses equal weights;
- fails if a configured symbol is unavailable.

It is not the production selection strategy. Batch 4A-3 will place the existing Exhaustive optimizer/ranking authority behind `SelectionEngine` and prove golden parity rather than reproducing those formulas here.

## Evaluation/OOS boundary

`validate_evaluation_dataset()` may be called only with an already-created `DecisionSnapshot`.

It validates:

1. requested Evaluation start/end exactly match the period;
2. Evaluation dataset identity is internally consistent;
3. effective observations remain inside the Evaluation window;
4. every selected constituent was requested and resolved for evaluation.

Additional symbols such as a benchmark may be present. Evaluation data may score the frozen decision but cannot change its constituents, weights, selector identity, Training hash, PIT evidence, or `decision_hash`.

## Required future-data mutation property

Regression tests must construct the same Training/PIT decision against materially different OOS paths, including extreme future moves, such as approximately:

- `+5000%`;
- `-99%`.

The following must remain identical:

- selected constituents;
- weights;
- decision hash.

The OOS dataset hashes should differ, proving that future observations changed while the frozen selection did not.

## Failure semantics

Training-history incompleteness is explicit rather than silently filtered.

For every PIT member:

```text
resolved history → eligible candidate
HistoryFailure   → unavailable candidate with stage/detail/retryable
```

A later adapter may choose a stricter policy and reject any unavailable candidate, but it must do so explicitly. The core itself preserves the complete accounting so failure policy is auditable.

## Non-goals

Batch 4A-2 does not implement:

- Exhaustive optimizer parity;
- new ranking/alpha methodology;
- Refinery-driven selection;
- PIT fundamentals;
- continuous OOS Portfolio ledger;
- turnover/transaction costs between decisions;
- public Walk-Forward API/UI;
- ResearchRun persistence.

Those remain later batches.

## Batch sequence

```text
4A-1 Temporal causality + DecisionSnapshot       DONE
4A-2 SelectionEngine + physical train/OOS split  THIS CONTRACT
4A-3 Existing Exhaustive adapter + golden parity NEXT
4A-4 Continuous OOS Portfolio ledger
4A-5 PIT/API orchestration
4A-6 User-facing Walk-Forward UX
```
