# Walk-Forward Exhaustive Adapter V1

Status: **Batch 4A-3 internal research adapter; not yet a public Walk-Forward API/UI.**

## Purpose

Batch 4A-3 places the existing Exhaustive numerical authority behind the Batch 4A-2 `SelectionEngine` boundary without porting or duplicating its portfolio simulation, metrics, score formulas, rebalance mathematics, or combination ranking in Python.

The authority remains:

```text
public/exhaustive-optimizer-core.js
```

The causal path is:

```text
PIT candidate Training ResearchDataset
        +
Training-only Exhaustive authority ResearchDataset
(candidates + benchmark)
        ↓
ExhaustiveSelectionEngine
        ↓
Node bridge → existing exhaustive-optimizer-core.js
        ↓
winning exact combination
        ↓
SelectionResult → immutable DecisionSnapshot
```

No Evaluation/OOS observation is an input to the adapter or the JavaScript authority.

## Contract identity

```text
WALK_FORWARD_EXHAUSTIVE_ADAPTER_VERSION
= walk-forward-exhaustive-adapter-2026-08-15.1
```

The adapter records the runtime-reported JavaScript `EXHAUSTIVE_ENGINE_VERSION` and bridge version in `DecisionSnapshot.selector_parameters` before selection executes.

## One numerical authority

Python owns only orchestration and fail-closed validation. It does **not** implement:

- combination simulation;
- equal-weight portfolio NAV mathematics;
- periodic/band rebalance mathematics;
- transaction-cost fixed point;
- Sortino, CAGR, MDD, volatility, beta or alpha formulas;
- stable/growth/drawdown/optimized score formulas;
- the authoritative winner metric calculation.

`scripts/exhaustive_selection_authority.mjs` imports the existing `public/exhaustive-optimizer-core.js` and enumerates exact combinations through that implementation.

The default winner contract remains the current Exhaustive UI contract:

```text
field     = optimized_score
direction = descending
nonfinite = negative infinity
tie-break = smaller combination rank
```

The tie-break matches the existing Exhaustive sort/retention behavior. No ticker-symbol alphabetical tie-break is introduced.

## Candidate Training evidence vs benchmark evidence

Batch 4A-2 remains unchanged: `SelectionContext.training_dataset` requests exactly the PIT member sequence, and those resolved members are the only eligible constituents.

Exhaustive additionally requires a benchmark for beta/alpha and therefore optimized score. The adapter receives one engine-specific `authority_dataset` containing:

```text
exact PIT candidate order + benchmark
```

for the exact same Training window.

The benchmark is not inserted into PIT membership and can never become an eligible constituent.

Before execution the adapter requires:

1. no unavailable PIT candidate, matching the existing Exhaustive fail-closed policy;
2. the authority dataset requested/resolved sequence is exactly candidates followed by benchmark;
3. both datasets request the same Training start/end;
4. authority effective observations remain within Training and at/before Decision;
5. every candidate has identical raw native/FX/TWD history fingerprints and audit metadata across the PIT candidate dataset and authority dataset;
6. the existing Exhaustive 2–100 source-ticker and 50,000,000-combination ceilings hold;
7. the existing minimum-observation and `_strict_full_period_coverage()` policy holds;
8. every candidate and benchmark has `verified_standard_actions` corporate-action status;
9. TWD authority levels are finite and positive.

The authority dataset hash is snapshotted in selector parameters and revalidated after JavaScript execution. A result that reports another dataset hash, authority version, bridge version, ranking contract, combination count or invalid constituent/weight set is rejected.

## Why two ResearchDataset artifacts are acceptable

This does not create a second market-data authority. Both artifacts use the same versioned `ResearchDataset`/TWD valuation boundary.

The candidate-only dataset preserves PIT eligibility semantics. The candidates+benchmark authority dataset preserves the exact common-calendar semantics already used by the production Exhaustive prepare endpoint.

Existing regression `test_research_dataset_matches_current_exhaustive_preparation` proves that a ResearchDataset built from candidates+benchmark produces the same TWD aligned frame, reference calendar, availability masks, coverage evidence and source fingerprints as the current Exhaustive preparation path.

The adapter additionally compares raw candidate history identities across the two artifacts so an independently changed candidate series cannot enter the JavaScript authority under the candidate Training hash.

## Golden parity evidence

Batch 4A-3 requires all of the following:

1. existing `test_quant_authority_exhaustive.mjs` continues to prove `simulateExactPortfolio()` against the canonical shared quant fixture;
2. `test_exhaustive_selection_authority.mjs` compares the new bridge winner against direct calls to the same current Exhaustive core for every combination in a deterministic fixture;
3. the bridge regression freezes non-finite-score handling and smaller-rank tie-break;
4. Python adapter tests prove runtime JS authority identity and authority dataset identity are included in the frozen decision;
5. an end-to-end Python → Node → existing JS authority → `SelectionResult` → `DecisionSnapshot` regression runs in CI;
6. existing repository Exhaustive, ResearchDataset and Walk-Forward tests remain green.

A future change to the existing Exhaustive core is allowed to change results only through its own reviewed/versioned authority change. The adapter must not normalize such a change back to an older Python result.

## Execution placement

`NodeExhaustiveAuthorityRunner` is an internal Batch 4A-3 runner used to establish an executable cross-language adapter and CI parity.

Batch 4A-3 does **not** assert that Node is available inside the production Python/Vercel runtime, and it adds no public route that depends on this runner. Production placement, job orchestration and PIT API wiring remain Batch 4A-5 decisions.

This separation prevents infrastructure convenience from forcing a second Python quant engine.

## Failure semantics

The adapter fails closed rather than silently changing the experiment:

- unavailable PIT member → reject;
- benchmark in candidate universe → reject;
- candidate-history drift between Training artifacts → reject;
- insufficient/late/early full-period coverage → reject;
- unverified corporate action → reject;
- authority dataset mutation → reject;
- JS authority/bridge version drift during execution → reject;
- result bound to another dataset → reject;
- wrong ranking contract or combination count → reject;
- invalid winner symbols/weights → reject.

No fallback ranking methodology is permitted.

## Non-goals

Batch 4A-3 does not implement:

- a new optimization objective;
- a Python copy of Exhaustive mathematics;
- retention/storage redesign for 50M production jobs;
- continuous OOS Portfolio ledger;
- inter-period turnover/cost accounting;
- public Walk-Forward API/PIT orchestration;
- user-facing Walk-Forward controls;
- PIT fundamentals;
- ResearchRun persistence or AI Autopilot.

## Batch sequence

```text
4A-1 Temporal causality + DecisionSnapshot       DONE
4A-2 SelectionEngine + physical train/OOS split DONE
4A-3 Existing Exhaustive adapter + golden parity THIS CONTRACT
4A-4 Continuous OOS Portfolio ledger            NEXT
4A-5 PIT/API orchestration
4A-6 User-facing Walk-Forward UX
```
