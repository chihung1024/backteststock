# Optimizer Hub Parameter Optimization V1

Status: **Phase 4B-3 candidate contract.** It becomes production authority only after exact-head implementation verification, independent review, merge, and post-main exact-SHA production gates pass.

## 1. Purpose

Phase 4B-3 adds bounded, reproducible parameter optimization to the existing configured Dual Momentum + Allocation path without allowing the outer Walk-Forward Evaluation/OOS interval to influence parameter choice for the same outer Decision.

The target research chain is:

```text
configured universe
→ Outer Training ResearchDataset
→ deterministic inner temporal folds
→ bounded ParameterCandidate search
→ exact continuous inner-OOS evaluation
→ deterministic winner
→ winner refit on full Outer Training
→ frozen outer DecisionSnapshot
→ outer Evaluation
→ existing continuous Portfolio v3 OOS ledger
→ existing metrics
→ ResearchRun
```

This contract does not create a second market-data, covariance, Portfolio, metric, Walk-Forward, or persistence authority.

## 2. Authority boundaries

| Concern | Authority |
| --- | --- |
| configured membership | `ConfiguredResearchUniverse` |
| audited TWD history | `ResearchDataset` |
| Dual Momentum signal | existing 4B-1 Momentum implementation |
| Equal / Inverse Vol / ERC allocation | existing 4B-2 allocation implementation |
| covariance / risk decomposition | existing Risk Mathematics authority |
| inner/outer continuous OOS accounting | existing Walk-Forward OOS ledger + Portfolio v3 |
| exact performance metrics | existing Portfolio v3 metric authority |
| final outer Decision identity | existing configured `DecisionSnapshot` |
| durable completed research | existing D1 ResearchRun authority |

The optimizer may orchestrate these authorities, but it must not reimplement them privately. The browser or a future AI agent may define a bounded search request and render returned evidence. Neither may submit authoritative candidate results, calculate the accepted winner, or bypass backend validation.

## 3. Versioned identities

Parameter-optimization methodology:

```text
optimizer-hub-parameter-optimization-2026-08-18.1
```

Accepted inner objective policy:

```text
inner-oos-sortino-lexicographic-v1
```

Inner fold calendar policy:

```text
completed-calendar-month-buckets-v1
```

Configured selector policy:

```text
dual-momentum-nested-parameter-optimization-v1
```

Planned public job contract:

```text
walk-forward-dual-momentum-parameter-optimization-job-2026-08-18.1
```

Any externally observable methodology change requires explicit versioning rather than silent reinterpretation of an old ResearchRun.

## 4. Backward compatibility and replay

Phase 4B-3 is opt-in. Existing requests remain frozen:

- legacy Dual Momentum request without `allocationMethod` keeps 4B-1 request shape, selector policy and job contract;
- explicit 4B-2 allocation request keeps its existing request shape, allocation selector policy and job contract;
- PIT / Exhaustive behavior remains unchanged;
- ResearchRun rerun replays the exact stored request and therefore does not upgrade old runs into parameter optimization.

A 4B-3 request receives a separately versioned normalized selector/search identity. Do not add optional tuning fields to an old normalized request in a way that changes an existing `jobHash` or `DecisionSnapshot` identity.

Explicit optimization requests must persist their exact original search dimensions and inner validation policy. Rerun must recreate the same normalized search, not rewrite it into the winning manual parameter tuple.

## 5. V1 tunable dimensions

V1 automatically chooses only:

```text
lookbackMonths
Top-K
absoluteThreshold
allocationMethod ∈ {
  equal,
  inverse_volatility,
  risk_parity_erc
}
```

The following remain fixed inputs, not optimization dimensions:

- risky / defensive configured universe membership;
- outer Walk-Forward period schedule;
- initial amount;
- transaction-cost assumption;
- risk-free-rate context;
- covariance estimator;
- annualization policy;
- minimum complete-case requirement;
- market-data / FX method;
- execution-delay semantics;
- Portfolio v3 accounting;
- metric formulas.

These fixed assumptions remain visible in request/result evidence.

## 6. Search-space canonicalization

The backend owns canonical candidate enumeration.

Rules:

1. each search dimension is normalized and deduplicated before Cartesian enumeration;
2. `lookbackMonths` must satisfy the existing Dual Momentum range;
3. every `Top-K` must be valid for the fixed risky universe;
4. every threshold must be finite and canonicalize `-0.0` to `0.0`;
5. allocation method must be an existing supported 4B-2 method;
6. duplicate parameter tuples collapse before capacity accounting;
7. canonical candidate ordering is independent of request list ordering.

Canonical tuple order is:

```text
(lookbackMonths, topK, absoluteThreshold, allocationMethodOrder)
```

The allocation order is versioned and deterministic:

```text
equal
inverse_volatility
risk_parity_erc
```

Each candidate receives a SHA-256 canonical-JSON parameter identity. The normalized search space receives a separate `searchSpaceHash`; the candidate list plus inner validation policy and planned work receive a separate search-plan identity.

## 7. Outer / inner temporal firewall

For every existing outer Walk-Forward period:

```text
Outer Training start ... Outer Training end == Outer Decision
Outer Evaluation starts only after Outer Decision
```

Phase 4B-3 creates inner tuning folds **strictly inside the Outer Training interval**.

For each inner fold:

```text
Inner Training end == Inner Decision
Inner Evaluation starts after Inner Decision
Inner Evaluation end <= Outer Training end
```

No inner dataset may include an observation later than the outer Training end. Outer Evaluation is not passed to the tuning component and must be structurally unavailable before the final outer DecisionSnapshot is frozen.

The required orchestration order is:

```text
build/fetch Outer Training
→ tune only inside Outer Training
→ choose winner parameters
→ refit on full Outer Training
→ freeze outer DecisionSnapshot
→ only then fetch/validate Outer Evaluation
```

## 8. Inner-fold policy

V1 uses deterministic **completed calendar-month buckets** compatible with the current Dual Momentum monthly cadence.

The bounded inner-validation controls are:

```text
foldCount
evaluationMonths
stepMonths
```

Default V1 intent:

```text
evaluationMonths = 1
stepMonths = 1
```

`stepMonths` must be at least `evaluationMonths`, so accepted inner Evaluation windows do not overlap.

Fold construction rules:

1. Evaluation boundaries are calendar-month starts/ends, not arithmetic `DateOffset` intervals anchored to arbitrary month-end day numbers.
2. If the outer Decision / Training end is the final calendar day of its month, that completed month may be the newest inner Evaluation bucket.
3. If the outer Decision / Training end occurs before calendar month-end, the partial current month is **not** treated as a completed inner OOS bucket. The newest inner Evaluation therefore ends at the previous calendar month-end.
4. Any partial current-month observations remain part of the full Outer Training dataset and are used when the chosen winner is refit on full Outer Training before the outer Decision is frozen.
5. Inner folds are generated newest-first under the configured step, then stored chronologically and validated by the existing Walk-Forward non-overlap schedule authority.
6. Every candidate uses exactly the same inner fold schedule.
7. A request fails closed when Outer Training cannot support the maximum requested lookback plus all requested folds.

This policy prevents month-length artifacts such as inclusive `October 31..November 30` / `November 30..December 31` overlap and makes the inner schedule independent of whether neighboring months have 28, 29, 30 or 31 days.

The exact production default and maximum `foldCount` are set only after runtime-capacity benchmarking.

## 9. One download, many audited inner views

The tuner must not download market data separately for every candidate.

Required data flow:

```text
one Outer Training TWD history batch for configured members
→ audited outer ResearchDataset
→ deterministic bounded inner date slices/views
→ candidate evaluation
```

The bounded view helper remains inside the existing ResearchDataset authority:

- it reads only rows already present in the parent audited dataset;
- it does not download, fill, interpolate, or repair market history;
- it preserves requested membership and explicit failure accounting;
- a parent-resolved symbol with no audited availability inside a child interval becomes an explicit child-window failure rather than being silently dropped;
- a child view has its own deterministic ResearchDataset hash and binds the parent dataset identity in its evidence.

Do not add a second market-data cache, downloader, or optimizer-private price source.

## 10. Candidate execution

For one outer period and one `ParameterCandidate`:

```text
for each fixed inner fold:
    child Inner Training ResearchDataset
    → existing Dual Momentum + existing Allocation
    → frozen inner DecisionSnapshot
    → only then child Inner Evaluation ResearchDataset

all inner evaluations
→ existing continuous Walk-Forward OOS ledger
→ existing Portfolio v3 metrics
```

Important rules:

- candidate evaluation does not reset NAV per fold;
- transaction costs are computed by existing Portfolio v3 semantics;
- a candidate must complete every required fold to be eligible;
- candidate-specific missing history or allocation failure is an explicit candidate failure;
- failures do not authorize alternate data, silent symbol removal, Equal fallback, or shorter validation windows;
- all candidates see exactly the same outer Training data and inner schedule;
- runtime completion order cannot affect ranking order or identity.

## 11. Accepted objective policy

V1 deliberately uses a transparent lexicographic objective instead of creating another opaque composite score.

Eligible candidates are ranked by:

```text
1. higher exact continuous inner-OOS Sortino
2. lower abs(Max Drawdown)
3. higher CAGR
4. lower exact transaction costs
5. lexicographically lower canonical parameter hash
```

The primary objective is therefore:

```text
maximize Sortino
```

with deterministic tie-breaks rather than a hidden weighted score.

If an accepted ranking metric is unavailable or non-finite, that candidate is not silently assigned zero; it fails eligibility.

Proxy metrics may later be used only as clearly labelled search acceleration. Any candidate accepted as winner must be exact-revalidated by the authoritative path above.

## 12. Search-plan and resource budget

The system must fail closed before expensive candidate work when the normalized search exceeds the allowed budget.

At minimum the budget accounts for:

```text
candidateCount
innerFoldCount
outerPeriodCount
plannedTuningEvaluations = candidateCount × innerFoldCount × outerPeriodCount
```

Production caps such as:

```text
MAX_PARAMETER_CANDIDATES
MAX_INNER_FOLDS
MAX_TUNING_EVALUATIONS_PER_JOB
```

must be chosen from empirical runtime/capacity evidence before release. They are not guessed in the methodology contract.

Product defaults should remain materially below measured hard ceilings. Search count preflight must happen before market-data work whenever all required counts are available from the normalized request.

Unbounded Cartesian search is forbidden.

## 13. Tuning result identity and evidence

A completed inner tuning result binds at least:

```text
tuningContractVersion
objectivePolicyVersion
outerTrainingDatasetHash
searchSpaceHash / searchPlanHash
innerFoldScheduleHash
candidateParameterHashes
candidate status / failure evidence
candidate exact inner-OOS metric summaries
candidate inner-OOS identities
winnerParameterHash
winnerParameters
resultHash
```

Candidate evidence should include completed fold count, failed fold/reason when relevant, exact Sortino/MDD/CAGR/transaction costs for eligible candidates, inner Decision hashes and inner Evaluation dataset hashes.

Same normalized request + same audited data + same versioned methodology must produce the same ordering and winner identity.

Candidate ordering cannot depend on input list order or runtime completion order.

## 14. Winner refit on full Outer Training

The winner of inner tuning is a **parameter set**, not the final outer portfolio weights.

After the winner is selected:

```text
winner parameters
+ exact full Outer Training ResearchDataset
→ existing Dual Momentum + Allocation engine
→ final outer SelectionResult
→ configured DecisionSnapshot
```

The refit must use the exact `outerTrainingDatasetHash` that produced the tuning result. A tuning result cannot be applied to a different outer Training dataset.

The outer Decision binds:

- optimization contract identity;
- objective policy;
- tuning result hash;
- search plan hash;
- inner fold schedule hash;
- winner parameter hash and parameters;
- full tuning evidence;
- full-Outer-Training final selection and allocation evidence;
- final selected constituents and weights.

The existing `DecisionSnapshot` selector structure remains authoritative:

```text
selector: {
  contractVersion,
  rule,
  parameters
}
```

Phase 4B-3 must use that existing structure rather than creating a parallel top-level selector-parameters schema.

Only after this DecisionSnapshot exists may the ordinary outer Evaluation dataset be fetched/validated.

## 15. Outer OOS remains existing authority

Phase 4B-3 does not create a separate final performance engine.

```text
parameter-optimized outer DecisionSnapshot
→ existing Evaluation data load
→ existing continuous Walk-Forward OOS ledger
→ existing Portfolio v3 costs / metrics
→ ResearchRun
```

Outer OOS results may evaluate the frozen optimized methodology, but they cannot retroactively change its search space, inner fold ranking, winning parameters, selected holdings, or weights for that same outer period.

## 16. Public request / job identity

A public 4B-3 request must be explicitly discriminated from manual Dual Momentum.

Recommended semantic shape:

```text
selector: {
  strategy: "dual_momentum",
  riskySymbols,
  defensiveSymbols,
  parameterOptimization: {
    searchSpace: {
      lookbackMonths,
      topK,
      absoluteThreshold,
      allocationMethod
    },
    innerValidation: {
      foldCount,
      evaluationMonths,
      stepMonths
    }
  }
}
```

The exact API field shape may be refined during implementation, but these rules are fixed:

- omission of `parameterOptimization` remains existing manual behavior;
- an explicit optimization request receives a new job contract and selector policy;
- normalized search space, validation policy and fixed assumptions enter job identity;
- old job hashes must remain reconstructable;
- optimization and manual fixed parameter fields must not ambiguously compete for authority in the same request.

## 17. ResearchRun replay

Research Memory continues to persist the exact original execution request plus backend-produced completed result.

For a 4B-3 run:

- stored search dimensions remain immutable;
- stored inner validation policy remains immutable;
- rerun does not mutate the winner into a manual request;
- rerun creates normal ResearchRun lineage under the existing D1 authority;
- browser-submitted candidate rankings or winner evidence remain forbidden.

`jobHash` remains completed backend-result identity; durable `run_id` remains ResearchRun identity.

## 18. UX requirements

The intended Optimizer Hub UX exposes:

```text
Manual parameters | Auto optimize
```

Auto optimize should provide:

- explicit search-space controls;
- preflight candidate count and planned candidate-fold evaluations;
- inner-fold timeline;
- clear objective policy;
- progress / failure evidence;
- winner parameters and explanation;
- candidate leaderboard;
- final outer OOS result separated visually from inner tuning evidence;
- save/rerun through the existing Research Library.

The UI must not imply that inner search metrics are final OOS performance.

Recommended defaults must be narrow enough to be useful without encouraging enormous Cartesian searches. The browser should display the normalized candidate count before execution, but backend resource guards remain authoritative.

## 19. Required regression invariants

A 4B-3 release must prove:

1. legacy Exhaustive, 4B-1 and 4B-2 normalized request / job identity remain unchanged;
2. outer Evaluation is structurally absent from tuning inputs;
3. inner Evaluation windows are completed calendar-month buckets, deterministic, ordered, non-overlapping and entirely inside Outer Training;
4. a partial current outer month is excluded from inner OOS but retained for full-Outer-Training winner refit;
5. every candidate receives the exact same inner fold schedule;
6. normalized search identity is invariant to request dimension order and duplicate values;
7. no candidate causes a new market-data download;
8. inner child datasets contain no observations outside their requested parent-bounded interval;
9. candidate failure never silently truncates symbols/dates or falls back to another allocation;
10. accepted winner ranking uses exact continuous inner-OOS authoritative metrics;
11. unavailable primary metric is not coerced to zero;
12. deterministic tie-break ends in canonical parameter hash;
13. winner is rerun on exact full Outer Training before the outer Decision is frozen;
14. tuning result / winner evidence is hash-bound into the existing outer Decision selector/evidence structure;
15. only after final outer Decision exists is outer Evaluation loaded;
16. ResearchRun rerun replays the exact stored optimization request;
17. browser evidence matches backend results and does not recompute them;
18. capacity limits reject oversized work before expensive execution;
19. tampered tuning/winner identity fails closed;
20. a tuning result cannot be refit against a different outer Training dataset hash.

## 20. Rejected shortcuts

Do not:

- optimize directly against the final outer Evaluation interval;
- use a full-period historical winner as OOS evidence;
- let the browser or AI submit authoritative candidate scores;
- re-download Yahoo/FX data per candidate;
- silently reduce the search space because execution is slow;
- silently drop failed symbols or folds;
- change transaction-cost assumptions per candidate to improve scores;
- fall back from failed ERC/Inverse Vol to Equal;
- rank unavailable metrics as zero;
- create a new blended AI score without a versioned visible methodology;
- use a proxy winner without exact accepted-path validation;
- mutate legacy request identity;
- create a second Decision/selector payload authority;
- weaken existing CI, exact-SHA or production smoke gates.

## 21. Capacity / runtime expansion rule

Optimization does not automatically justify new infrastructure.

Required order:

```text
1. benchmark real candidate × fold × outer workloads
2. reuse audited outer datasets
3. deterministic in-process memoization only where identity-safe
4. bounded batch/cancellation/resume if required
5. asynchronous durable jobs only if measured synchronous workloads are insufficient
```

Do not introduce Redis, task queues or distributed workers before measured product evidence requires them.

## 22. Release gates

4B-3 is R2 by default because it changes quantitative methodology and public research behavior.

Before Ready / merge:

- targeted mathematical/causal tests pass;
- full relevant regression passes;
- legacy 4B-1/4B-2 identity regressions pass;
- public API/UI contract matches backend fields;
- browser E2E covers Auto Optimize request and authoritative evidence display;
- capacity benchmark establishes production caps/defaults;
- exact-head CI passes;
- independent exact-head methodology review is approved;
- rollback/recovery point exists.

After merge:

- main CI passes;
- Vercel production is READY on exact accepted SHA;
- Cloudflare deployment and applicable production smokes pass;
- Walk-Forward exact-SHA production verifier passes with the new API/job contract;
- runtime error/fatal scan shows no 4B-3 release defect.

4B-3 is not CLOSED before those post-main gates pass.

## 23. Future extensions

After 4B-3 is production accepted, later separately versioned work may add:

- Pareto / hard constraints / fold stability / parameter-plateau robustness;
- minimum variance / maximum diversification / custom risk budgets / HRP / HERC;
- rebalance / execution parameter tuning;
- robust parameter ensembles;
- causally defined regime-conditioned choice;
- AI Research Autopilot that compiles natural-language goals into bounded visible ExperimentSpecs.

None of those are hidden extensions of this V1 contract.