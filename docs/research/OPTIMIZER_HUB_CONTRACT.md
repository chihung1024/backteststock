# Optimizer Hub Contract

Status: **Current production Optimizer Hub contract: Dual Momentum + Allocation + bounded nested Parameter Optimization.**

This document replaces the former 4B-1, 4B-2, 4B-3 and capacity-evidence documents. Historical rollout gates remain in Git/PR/Actions. The current product semantics below are durable.

## 1. Product chain

```text
configured risky/defensive universe
→ Training ResearchDataset
→ Dual Momentum selection
→ Training-only allocation
→ optional bounded nested parameter optimization
→ full-Training winner refit
→ frozen DecisionSnapshot
→ outer Evaluation
→ continuous Portfolio v3 OOS ledger/costs/metrics
→ ResearchRun
```

The browser and AI may define a bounded request and explain backend evidence. They are not numerical result authorities.

## 2. Authority boundaries

Optimizer Hub reuses:

- configured-request membership identity from the backend research domain;
- `ResearchDataset` for audited TWD history;
- existing Dual Momentum signal implementation;
- existing Risk Mathematics for covariance/risk contribution;
- existing Portfolio v3 for OOS accounting and costs;
- existing Walk-Forward temporal firewall;
- existing ResearchRun persistence.

It must not create a second market-data downloader/cache, covariance definition, Portfolio engine, performance metric engine or browser-side accepted result.

## 3. Configured universe is not PIT

A user-configured risky/defensive universe is request provenance, not historical index-membership evidence.

The exact ordered canonical symbol set is hash-bound into configured research identity. No `sourceAsOf`, authority flag or other PIT field is fabricated.

A Decision uses one membership provenance model for that strategy: PIT or configured request, never a misleading mixture.

## 4. Dual Momentum signal

Signal authority is audited TWD adjusted total-return levels in the Training `ResearchDataset`.

For symbol `i`, Decision `t`, and lookback `L` calendar months:

```text
requested_start = t - L calendar months
baseline = first audited TWD level on/after requested_start
end      = last audited TWD level on/before t
momentum = end / baseline - 1
```

Current boundary policy requires the baseline/end observations to be close enough to their requested boundaries, finite, positive and ordered. Materially short history fails closed rather than silently shortening lookback.

Evaluation/OOS data is absent from signal calculation.

## 5. Selection

Risky assets first apply the explicit absolute threshold.

Passing risky assets are ranked by:

1. trailing TWD total return descending;
2. canonical symbol ascending as deterministic tie-break.

Up to `Top-K` passing risky assets are selected.

If no risky asset passes, configured defensive assets are ranked by the same Training-only signal and the result records an explicit defensive regime/fallback reason.

Risky and defensive sets must be non-empty as required by the current strategy and must be disjoint. Missing configured-member history is explicit and fails closed; the strategy does not quietly shrink the cross-section.

## 6. Monthly causal schedule

Configured Dual Momentum uses monthly decisions.

Core semantics:

- Training ends at Decision;
- Decision is after-close;
- Evaluation starts after Decision;
- Training covers the configured lookback;
- adjacent Decision months follow the versioned monthly schedule;
- new target weights apply only to subsequent Evaluation observations.

The browser may generate convenient schedules; backend validation remains authoritative.

## 7. Allocation methods

Current explicit methods are:

```text
equal
inverse_volatility
risk_parity_erc
```

A legacy request that omits the newer allocation field keeps its historical versioned replay semantics. Explicit allocation opts into the newer allocation identity.

### Equal

```text
w_i = 1 / n
```

For one selected asset, weight is `1.0`.

### Risk-data input

Inverse Volatility and ERC use only selected-asset `ResearchDataset.daily_returns_twd` from Training.

Current policy:

- complete-case rows across selected assets;
- no optimizer-private imputation;
- at least 60 finite complete-case daily observations for multi-asset risk allocation;
- covariance annualization 252;
- insufficient/invalid evidence fails closed;
- no silent Equal fallback.

### Covariance

Formal covariance reuses the existing Ledoit-Wolf Risk Mathematics authority. The optimizer does not implement an alternate hidden shrinkage estimator.

Risk numerical work uses canonical symbol order for reproducibility, then maps final weights back to frozen selected order.

### Inverse Volatility

```text
sigma_i = sqrt(Sigma_ii)
q_i = 1 / sigma_i
w_i = q_i / sum(q)
```

Variances must be finite and positive.

### ERC / Risk Parity

V1 means equal risk contribution with equal budgets.

The deterministic coordinate solver uses the versioned positive risk-budget objective and current implementation tolerance/iteration ceiling. Accepted weights are independently checked by the existing signed `risk_contributions()` authority; component-risk shares must satisfy the configured ERC residual tolerance.

No browser solver and no heuristic "risk parity" substitute are allowed.

## 8. Allocation evidence

Explicit risk allocations expose backend evidence sufficient to audit:

- method/version;
- selected symbols and frozen weights;
- input/complete-case counts;
- covariance method/annualization/diagnostics;
- portfolio volatility;
- signed component risk and risk-budget shares;
- ERC algorithm/iterations/residual when applicable.

Evidence is explanatory and part of deterministic decision identity. The UI displays it but does not recalculate it.

## 9. Parameter Optimization V1

Parameter optimization is opt-in. It tunes only:

```text
lookbackMonths
Top-K
absoluteThreshold
allocationMethod ∈ {equal, inverse_volatility, risk_parity_erc}
```

The configured universe, outer schedule, transaction-cost assumptions, market-data/FX method, covariance method, Portfolio accounting and metric formulas are fixed inputs, not hidden tuning dimensions.

## 10. Canonical search identity

Backend canonicalizes/deduplicates search dimensions before Cartesian enumeration.

Candidate identity is independent of user list ordering. Each normalized parameter tuple receives a deterministic canonical hash; the normalized search space/fold plan also receives deterministic identities.

No unbounded Cartesian search is permitted.

## 11. Nested temporal firewall

For each outer Decision:

```text
Outer Training
  → deterministic inner folds entirely inside Outer Training
  → evaluate parameter candidates
  → choose winner
  → refit winner on full Outer Training
  → freeze final outer Decision
Outer Evaluation
  → only after final Decision exists
```

Outer Evaluation is structurally unavailable to tuning for the same Decision.

Inner folds use completed calendar-month Evaluation buckets. Partial current outer months are not fabricated into completed inner OOS buckets; they may remain available for the final full-Training refit where causal.

Every candidate sees the identical inner schedule.

## 12. One audited parent dataset

One outer Training market-data batch produces one audited parent `ResearchDataset`.

Candidate/fold evaluation uses deterministic bounded child views of that parent:

- no per-candidate download;
- no interpolation or optimizer-private repair;
- parent membership/failure accounting is preserved;
- child views remain within parent/requested bounds;
- each view has deterministic identity.

## 13. Exact inner-OOS evaluation and winner policy

For each candidate:

```text
inner Training
→ existing Dual Momentum + Allocation
→ frozen inner Decision
→ inner Evaluation
→ existing continuous Walk-Forward OOS ledger
→ exact existing Portfolio metrics
```

Every required fold must complete for candidate eligibility. A candidate failure remains explicit; no silent shorter history, smaller symbol set, lower fold count or Equal fallback.

Accepted winner ordering is lexicographic:

1. higher exact continuous inner-OOS Sortino;
2. lower absolute Maximum Drawdown;
3. higher CAGR;
4. lower exact transaction costs;
5. lower canonical parameter hash.

Unavailable/non-finite accepted ranking metrics invalidate the candidate; they are not coerced to zero.

## 14. Winner refit and outer OOS

The tuning winner is a parameter set, not historical final weights.

The winner is rerun on the exact full Outer Training dataset to produce the final selection/allocation. That full-Training Decision is frozen before outer Evaluation data is loaded.

Outer OOS then uses the ordinary existing Walk-Forward/Portfolio v3 authorities. Outer performance never retroactively modifies the same-period search or winner.

## 15. Synchronous capacity

Current accepted limits are:

```text
MAX_PARAMETER_CANDIDATES = 48
MAX_INNER_FOLDS = 6
MAX_TUNING_EVALUATIONS_PER_JOB = 216
```

The global budget applies to candidate × inner-fold × outer-period planned work before expensive execution.

Empirical release evidence measured the real tuning authority on isolated CI runners. Representative results:

| Candidates | Folds | Candidate-fold evaluations | Tuning-only wall time |
| ---: | ---: | ---: | ---: |
| 12 | 3 | 36 | ~10.2 s |
| 24 | 6 | 144 | ~21.8 s |
| 48 | 3 | 144 | ~39.3 s |
| 48 | 6 | 288 | ~78.7 s |

The 288 case demonstrated technical completion but was intentionally not accepted as the synchronous product ceiling because the timing excluded live data access, winner refit and outer orchestration. The shipped global ceiling is 216.

Raise the ceiling only with new empirical capacity evidence; do not pre-emptively add queues/distributed workers.

## 16. ResearchRun and replay

D1 ResearchRun stores the exact normalized original request and backend-produced completed result.

- old manual requests are not silently upgraded;
- explicit optimization requests retain exact search/validation inputs;
- rerun replays the stored request rather than converting it to the previous winner;
- a new execution creates a new result identity while the source run remains immutable;
- browser-submitted authoritative candidate/winner results are forbidden.

## 17. UI contract

Optimizer Hub exposes manual and auto-optimized research in the same Walk-Forward workspace.

The UI may show:

- search-space editor and normalized candidate/work count;
- inner-fold timeline;
- objective policy;
- candidate statuses/failure reasons;
- winner parameters and deterministic tie-break explanation;
- candidate leaderboard;
- final outer OOS separately from inner tuning evidence;
- Research Library save/rerun.

It renders backend evidence and must not recompute accepted results.

## 18. Fail-closed shortcuts explicitly rejected

Do not:

- tune on outer OOS;
- call full-period historical optimization OOS evidence;
- let browser/AI submit authoritative scores;
- download market data per candidate;
- silently reduce symbols/dates/folds/search dimensions;
- vary costs solely to make a candidate look better;
- fall back from failed risk allocation to Equal;
- rank unavailable metrics as zero;
- invent an opaque universal AI score;
- create a second Decision, Portfolio, metric, covariance or market-data authority.

Tests and code are the final authority for exact version strings and numerical tolerances.
