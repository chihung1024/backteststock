# Optimizer Hub Allocation V1

Status: **Phase 4B-2 candidate contract.** It becomes production authority only after exact-head PR verification, independent review, merge, and post-main exact-SHA production gates pass.

## 1. Purpose

Phase 4B-2 adds an explicit Allocation / Weighting stage to the existing Optimizer Hub research chain:

```text
configured candidates
→ Training-only Selection / Signal
→ frozen selected constituents
→ Training-only Allocation / Weighting
→ DecisionSnapshot
→ Evaluation / continuous OOS Portfolio v3 ledger
→ metrics
→ ResearchRun
```

The feature answers a different question from Selection:

- Selection decides **which assets** are in the frozen Decision.
- Allocation decides **how much weight** each selected asset receives.

Allocation must not change candidate membership, Momentum ranking, absolute/relative filters, Decision timing, Evaluation inputs, Portfolio v3 accounting, metric formulas, or ResearchRun persistence authority.

## 2. Authority boundaries

Phase 4B-2 reuses existing authorities instead of creating parallel implementations:

| Concern | Authority |
| --- | --- |
| configured membership | `ConfiguredResearchUniverse` |
| Training TWD levels / returns | `ResearchDataset` |
| Dual Momentum selection | frozen Phase 4B-1 `DualMomentumSelectionEngine` |
| formal covariance | `docs/quant/RISK_MATHEMATICS_V1.md` / `ledoit_wolf_covariance()` |
| component risk / Euler decomposition | `risk_contributions()` |
| frozen target weights | `DecisionSnapshot.weights` |
| OOS transitions and costs | Portfolio v3 via existing Walk-Forward OOS ledger |
| OOS metrics | existing metric authority |
| durable completed research | D1 ResearchRun authority |

The browser may choose an allocation method and render returned evidence. It is not a covariance, ERC, Portfolio, or performance authority.

## 3. Versioned contracts

Allocation primitive contract:

```text
optimizer-hub-allocation-twd-2026-08-17.1
```

Dual Momentum + allocation selector contract:

```text
dual-momentum-allocation-selection-2026-08-17.1
```

Dual Momentum + allocation job contract:

```text
walk-forward-dual-momentum-allocation-job-2026-08-17.1
```

Selector policy:

```text
dual-momentum-configured-monthly-allocation-v1
```

Public Walk-Forward API contract when Phase 4B-2 is exposed:

```text
walk-forward-api-2026-08-17.3
```

## 4. Backward compatibility and replay

Backward compatibility is fail-safe and identity-preserving:

- a legacy Dual Momentum request that **omits** `allocationMethod` continues through the frozen Phase 4B-1 engine, selector policy, normalized request shape and job contract;
- the legacy request therefore does not acquire new allocation evidence merely because Phase 4B-2 exists;
- an explicit `allocationMethod` opts into Phase 4B-2 and therefore receives a new selector/job identity;
- explicit `allocationMethod="equal"` can produce the same numeric weights as legacy 4B-1 equal weighting, but it is intentionally a new versioned decision because the allocation stage and evidence are now explicit;
- ResearchRun rerun continues to replay the exact stored original request, so old saved runs remain reconstructable.

This boundary prevents a product upgrade from silently changing old `DecisionSnapshot` or `jobHash` identity.

## 5. Supported methods

V1 supports exactly three long-only, fully-invested methods:

```text
equal
inverse_volatility
risk_parity_erc
```

Out of scope for this contract:

- minimum variance;
- maximum diversification;
- HRP / HERC;
- leverage targeting;
- volatility targeting;
- custom risk budgets;
- long/short weights;
- weight caps/floors other than positivity implied by the current methods;
- parameter search or OOS-driven method selection.

Those require separately versioned later work.

## 6. Equal Weight

For `equal` and `n` selected assets:

```text
w_i = 1 / n
```

Equal Weight is data-independent. It does not require covariance or a minimum number of complete Training return observations.

A one-asset frozen selection always resolves to weight `1.0` under all three methods because there is no multi-asset allocation problem to solve.

## 7. Risk-data semantics

Inverse Volatility and ERC use only:

```text
ResearchDataset.daily_returns_twd
```

for the selected constituents and the current Training window.

Rules:

1. Evaluation/OOS returns are structurally unavailable to the allocation stage.
2. Values are interpreted as audited TWD daily returns under the existing ResearchDataset contract.
3. Non-finite values are treated as unavailable observations.
4. Multi-asset risk allocation uses **complete-case rows across all selected assets**.
5. Missing returns are not imputed inside the optimizer.
6. At least **60 finite complete-case daily observations** are required for a multi-asset risk-based allocation.
7. Formal daily covariance annualization is **252**.
8. Insufficient observations fail closed; the optimizer must not silently fall back to Equal Weight.

The 60-observation / 252-day boundary reuses the existing formal daily risk-analysis scale already used by the project rather than introducing an unrelated hidden threshold.

## 8. Formal covariance

For multi-asset Inverse Volatility and ERC, covariance is the existing Risk Mathematics formal estimator:

```text
Σ = ledoit_wolf_covariance(complete_case_training_returns, annualization=252)
```

Current authority method string:

```text
ledoit-wolf-mle-spherical-target
```

The optimizer does not implement an alternate shrinkage estimator. Formal covariance must pass the existing PSD diagnostic boundary. Non-PSD or non-finite formal covariance fails closed.

## 9. Canonical numerical ordering

Risk-based numerical work is performed in canonical symbol order, independent of request column ordering:

```text
canonical_symbols = sorted(selected_symbols)
```

Covariance construction and the ERC coordinate solver run in that canonical order. Final weights, component risks and risk-budget shares are then mapped back to the frozen selected-constituent order used by `DecisionSnapshot`.

This is a reproducibility rule, not a portfolio rule. It prevents tolerance-level coordinate-descent differences from making identical asset sets depend on request ordering.

## 10. Inverse Volatility

Given formal covariance `Σ`, asset volatility is:

```text
σ_i = sqrt(Σ_ii)
```

Raw inverse-volatility score:

```text
q_i = 1 / σ_i
```

Fully-invested weight:

```text
w_i = q_i / sum(q)
```

All diagonal variances must be finite and strictly positive. Invalid variances fail closed.

Correlation affects the formal covariance evidence but does not enter the Inverse Volatility weight formula beyond each diagonal variance. ERC is the method that explicitly solves for portfolio-level risk contribution equality.

## 11. Risk Parity / ERC

V1 Risk Parity means **Equal Risk Contribution (ERC)** with equal risk budgets:

```text
b_i = 1 / n
```

It is not an equal-volatility heuristic and is not a pairwise-risk label.

The positive risk-budget solution is obtained with deterministic canonical cyclic coordinate descent on the standard convex risk-budget objective:

```text
min_x  0.5 * x'Σx - Σ_i b_i log(x_i)
```

For coordinate `i`, with:

```text
c_i = (Σx)_i - Σ_ii x_i
```

the positive coordinate update is:

```text
x_i = (-c_i + sqrt(c_i^2 + 4 * Σ_ii * b_i)) / (2 * Σ_ii)
```

After each complete sweep, normalize:

```text
w = x / sum(x)
```

The solver is bounded by:

```text
tolerance = 1e-8
max_iterations = 10,000
```

Nonpositive variances, invalid discriminants, nonpositive coordinate updates, non-finite results or non-convergence fail closed.

## 12. ERC convergence authority

Solver convergence is not accepted from the optimizer's internal state alone. The resulting normalized weights are independently evaluated by the existing signed Risk Mathematics authority:

```text
portfolio_volatility, marginal_risk, component_risk = risk_contributions(w, Σ)
```

Risk-budget share is:

```text
share_i = component_risk_i / portfolio_volatility
```

For equal-budget ERC, acceptance requires:

```text
max_i |share_i - 1/n| <= 1e-8
```

This preserves the existing signed component-risk / Euler decomposition semantics instead of inventing a second risk-contribution definition inside the allocator.

## 13. Selection and allocation composition

The Phase 4B-1 selector remains frozen. Phase 4B-2 composition is additive:

```text
base_selection = DualMomentumSelectionEngine.select(training_context)
selected = base_selection.selected_constituents
allocation_returns = training_dataset.daily_returns_twd[selected]
allocation = allocate_weights_from_returns(allocation_returns, method)
SelectionResult(selected, allocation.weights, evidence)
```

Risk allocation cannot add a symbol that Selection did not choose and cannot remove a frozen selected symbol merely because its estimated weight is small.

## 14. Decision and causal identity

The final weights are frozen inside the same `DecisionSnapshot` that already binds:

- period / Decision timing;
- configured universe identity;
- Training dataset identity;
- selector contract and parameters;
- selected constituents;
- selection evidence;
- weights.

Evaluation data is loaded only after this Decision exists. Therefore OOS results cannot influence the risk model, ERC convergence or frozen weights for the same period.

## 15. Allocation evidence

Explicit Phase 4B-2 decisions expose backend-produced allocation evidence including:

- allocation contract version;
- Risk Mathematics contract version;
- method;
- selected symbols and frozen weights;
- input and complete-case observation counts;
- minimum required complete cases;
- daily frequency / TWD valuation currency;
- covariance method, annualization, shrinkage, PSD status, numerical rank and condition number when covariance is required;
- portfolio volatility when risk-based allocation is computed;
- signed component risk;
- risk-budget shares;
- ERC solver algorithm, iterations, residual, tolerance and iteration ceiling when applicable.

Evidence is explanatory and hash-bound through the configured DecisionSnapshot. The UI renders it but must not recompute it.

## 16. OOS execution

Allocation changes no downstream accounting authority. Frozen weights flow into the existing OOS ledger:

```text
DecisionSnapshot.weights
→ existing target-weight transition
→ Portfolio v3 turnover / transaction cost
→ continuous OOS equity
→ existing metrics
```

Changing allocation may legitimately change turnover and therefore transaction cost. Those costs remain calculated by Portfolio v3 rather than estimated inside the allocation module.

## 17. Required regression invariants

A Phase 4B-2 release must keep these checks green:

1. legacy Dual request without `allocationMethod` keeps the frozen 4B-1 normalized request shape and job contract;
2. old PIT / Exhaustive behavior remains unchanged and rejects `allocationMethod`;
3. Equal Weight is fully invested and data-independent;
4. Inverse Volatility exactly reuses the diagonal of formal Ledoit-Wolf covariance;
5. ERC equalizes existing signed component-risk shares within tolerance;
6. risk allocations are invariant to common return-unit scaling;
7. risk allocations are invariant to selected-column ordering through canonical numerical order;
8. missing-row complete-case behavior is explicit and insufficient samples fail closed;
9. Evaluation/OOS data remains absent from allocation input;
10. explicit allocation evidence and weights are frozen into DecisionSnapshot;
11. browser request/UX and displayed evidence match backend fields;
12. existing Portfolio/OOS/metric and ResearchRun authorities remain unchanged.

## 18. Rejected shortcuts

Do not:

- compute covariance or ERC in the browser;
- use Evaluation/OOS observations for Training weights;
- silently substitute Equal Weight after a risk allocation failure;
- use sample covariance as an alternate optimization authority when formal Ledoit-Wolf is required;
- use current/latest prices outside the Training dataset;
- impute missing selected-asset returns inside the allocator;
- change Phase 4B-1 selection to make ERC easier to solve;
- duplicate Portfolio transition-cost math;
- mutate old ResearchRun requests during rerun;
- weaken exact-SHA CI / production gates to ship this feature.

## 19. Future extension seam

Later allocation methods should implement the same narrow boundary:

```text
frozen selected constituents + Training-only ResearchDataset
→ versioned AllocationResult
→ SelectionResult weights/evidence
→ existing DecisionSnapshot / OOS authorities
```

Minimum Variance, Maximum Diversification, HRP, custom risk budgets and allocation-method parameter optimization are later versioned capabilities, not hidden extensions of this V1 contract.
