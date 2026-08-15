# Walk-Forward Continuous OOS Ledger V1

Status: **Batch 4A-4 internal research contract.**

Contract version: `walk-forward-oos-ledger-2026-08-15.1`

This contract owns the first continuous investable Evaluation/OOS ledger across frozen Walk-Forward decisions. It does not own selection, PIT membership, market-data acquisition, FX conversion, public API orchestration, or UI.

## 1. Goal

A Walk-Forward study is not one investable history if every Evaluation period starts from a fresh NAV and period-local returns are later averaged or stitched. Batch 4A-4 therefore requires one continuous TWD equity path whose capital state and target-transition costs carry across decisions.

Required causal chain:

```text
PIT + Training
    -> SelectionEngine
    -> immutable DecisionSnapshot
    -> validated Evaluation ResearchDataset
    -> Portfolio v3 segment execution
    -> inter-decision target transition
    -> one continuous OOS PortfolioLedger
    -> existing Portfolio metric report
```

The primary invariant is:

> A later Evaluation period starts from the prior period's actual ending OOS equity/allocation state after all already-authoritative Portfolio v3 path effects. It never starts from a newly normalized NAV.

## 2. Authorities reused, not replaced

### 2.1 Decision authority

`DecisionSnapshot` remains the immutable decision identity from Batch 4A-1/4A-2. Its hash is revalidated before OOS execution.

### 2.2 Evaluation-data authority

Each OOS input remains a `ResearchDataset` and must pass `validate_evaluation_dataset()` against its frozen decision. Batch 4A-4 does not widen the requested Evaluation window or fetch hidden pre/post-window observations.

### 2.3 Portfolio path authority

Within every Evaluation segment, `apps/api/app/portfolio/ledger.py::simulate_portfolio_ledger()` remains the Portfolio v3 path-dependent execution authority.

Inter-decision turnover and transaction cost delegate to the same Portfolio v3 `_rebalance()` implementation. Batch 4A-4 does not reproduce that formula in a research-specific calculator.

### 2.4 Metric authority

The final continuous `PortfolioLedger` is scored by existing `compute_metric_report()`. CAGR, Sortino, drawdown, XIRR and related metrics are therefore computed once from the continuous ledger, never aggregated from period-local metric reports.

## 3. Execution timing

Decision timing remains `after_close` from the temporal contract.

V1 execution policy:

`target-at-first-effective-oos-close-v1`

For each Evaluation segment:

1. the first effective TWD level is the execution/baseline close;
2. the frozen target is present at that baseline;
3. the first attributed market return is the next effective valuation interval;
4. for every later decision, the target transition is charged at the next segment's first effective OOS valuation before that segment's first attributed market return.

This preserves the existing `ResearchDataset` level/return convention: the first level is a baseline and `daily_returns_twd` begins after it.

## 4. Evaluation gaps

V1 gap policy:

`carry-last-audited-state-flat-no-invented-return-v1`

`validate_period_schedule()` allows non-overlapping Evaluation windows with calendar gaps. Batch 4A-4 does not fabricate price observations or hidden returns for those gaps.

Therefore:

- the prior segment's final audited equity/allocation is carried forward unchanged;
- no OOS row is invented for an unobserved gap date;
- the next target transition uses that carried state at the next segment's first effective valuation;
- CAGR still uses actual elapsed calendar time through the existing metric authority.

This is intentionally fail-safe. A later orchestration layer may provide a separately versioned continuous execution-history contract if the product chooses to model exposure between Evaluation windows, but 4A-4 does not silently infer it.

## 5. Transaction-cost continuity

At an inter-decision boundary, turnover uses the prior segment's actual ending allocation and gross exposure, not the prior target weights.

Example with no leverage/cash:

```text
ending equity = 110
ending allocation = 100% AAA
next target = 100% BBB
transaction_cost_bps = 100

traded notional = sell 110 AAA + buy 110 BBB = 220
cost = 220 * 100 / 10,000 = 2.2
next segment starting equity = 107.8
```

The transition cost is represented as a real negative daily strategy return on the next segment's baseline date. The continuous `return_index` therefore does not hide the turnover cost.

If the next target is already identical to the actual prior ending allocation, traded notional may be zero. If the target is unchanged but weights drifted, the decision boundary may still generate turnover because the portfolio is restored to the frozen target.

## 6. One continuous return index

The final ledger must satisfy, under the supported V1 state:

```text
equity[t] == initial_amount * continuous_return_index[t]
```

within numerical tolerance for every retained OOS observation.

Period-local `return_index` values are execution internals only. They are never exported as independent NAV histories and then averaged or concatenated without state transfer.

A golden parity regression is required: when the frozen target is unchanged across a split and no gap return is present, the split Walk-Forward result must match one ordinary Portfolio v3 ledger over the equivalent TWD level path.

## 7. V1 ResearchDataset state boundary

`ResearchDataset` exposes adjusted/total-return TWD levels. It does not expose the full separate price/distribution component history needed to reconstruct cash distributions after the fact.

Therefore V1 requires:

- `reinvest_distributions=True`;
- `cashflow.type=none`;
- `leverage.type=none`.

Unsupported configurations fail closed.

This is not a claim that Portfolio v3 cannot model those features. Portfolio v3 already can. It is a statement that 4A-4 will not reconstruct state that the current ResearchDataset evidence does not prove.

Periodic/threshold rebalancing inside an Evaluation segment remains available because that calculation is performed by the existing Portfolio v3 ledger against the segment's frozen target.

Return-component policy:

`research-total-return-reinvested-v1`

Separate cash-income attribution is intentionally unavailable in this mode; OOS total return already includes reinvested distributions.

## 8. Period audit

Every OOS segment records at least:

- `period_id`;
- `decision_hash`;
- Evaluation `dataset_hash`;
- requested Evaluation start/end;
- effective valuation start/end;
- exact selected constituents and weights;
- transition traded notional;
- transition transaction cost.

Every transition event records the previous and next decision hashes plus execution/gap policy identifiers.

This allows later ResearchRun persistence to bind an OOS ledger to exact decisions and exact Evaluation evidence without changing those underlying identities.

## 9. Failure semantics

Batch 4A-4 fails rather than silently normalizing when:

- no Evaluation segments are supplied;
- the decision schedule is invalid or overlaps;
- a decision hash no longer validates;
- an Evaluation dataset does not match its decision/window;
- a selected symbol is absent from OOS TWD levels;
- a selected segment has fewer than two effective valuation dates;
- selected TWD levels are non-finite/non-positive;
- unsupported distribution/cashflow/leverage state is requested;
- an inter-decision transition depletes equity;
- combined OOS dates duplicate/go backward;
- continuous equity and continuous return-index identity diverge.

## 10. Non-goals

Batch 4A-4 does **not** add:

- a public Walk-Forward API or job system;
- PIT resolver changes;
- new universe/fundamental selection logic;
- a second Exhaustive implementation;
- a new downloader, FX source or TWD valuation path;
- benchmark/alpha orchestration across OOS gaps;
- non-reinvested distribution accounting from ResearchDataset;
- external cashflow or leverage state across decisions;
- persistence/ResearchRun memory;
- user-facing Walk-Forward controls or charts;
- AI Autopilot.

Those remain later, separately versioned work.

## 11. Required regressions before merge

At minimum:

1. disjoint target transition proves full sell+buy notional and transaction cost;
2. global equity/return index does not reset at a later period;
3. unchanged-target split has golden parity with the existing single-window Portfolio v3 authority;
4. gap dates are not fabricated;
5. decision/Evaluation hashes remain bound in period audit and transition provenance;
6. unsupported non-reinvested distribution/cashflow/leverage state fails closed;
7. existing Portfolio v3, Walk-Forward temporal/selection, Exhaustive, Worker, browser and deployment-config regressions remain green.

## 12. Roadmap placement

```text
4A-1 Temporal Contract / Causality Firewall      DONE
4A-2 Selection Core                              DONE
4A-3 Existing Exhaustive adapter / golden parity DONE
4A-4 Continuous OOS Portfolio ledger             THIS CONTRACT
4A-5 PIT/API/job orchestration                    NEXT
4A-6 User-facing Walk-Forward UX
```
