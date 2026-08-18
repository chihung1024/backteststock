# Optimizer Hub Parameter Optimization V1

Status: **Phase 4B-3 candidate contract.** It becomes production authority only after exact-head implementation verification, independent review, merge, and post-main exact-SHA production gates pass.

## 1. Purpose

Phase 4B-3 adds bounded, reproducible parameter optimization to the existing configured Dual Momentum + Allocation path without allowing the outer Walk-Forward Evaluation/OOS interval to influence parameter choice for the same outer Decision.

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

The optimizer may orchestrate these authorities, but it must not reimplement them privately. Browser/AI may define a bounded search request and render returned evidence; neither may submit authoritative candidate results, calculate the accepted winner, or bypass backend validation.

## 3. Versioned identities

```text
parameter methodology: optimizer-hub-parameter-optimization-2026-08-18.1
inner objective:       inner-oos-sortino-lexicographic-v1
inner calendar:        completed-calendar-month-buckets-v1
selector policy:       dual-momentum-nested-parameter-optimization-v1
planned job contract:  walk-forward-dual-momentum-parameter-optimization-job-2026-08-18.1
```

Any externally observable methodology change requires explicit versioning rather than silent reinterpretation of an old ResearchRun.

## 4. Backward compatibility and replay

Phase 4B-3 is opt-in.

- Legacy Dual Momentum without `allocationMethod` keeps the frozen 4B-1 normalized request, selector policy, job contract and replay identity.
- Explicit 4B-2 allocation keeps its existing normalized request, allocation selector policy, job contract and replay identity.
- PIT / Exhaustive behavior remains unchanged.
- ResearchRun rerun replays the exact stored request; old runs are not upgraded into parameter optimization.
- A 4B-3 request receives a separately versioned normalized selector/search identity.
- Explicit optimization requests persist their exact original search dimensions and inner validation policy; rerun must not rewrite them into the winning manual parameter tuple.

Do not add optional tuning fields to an old normalized request in a way that changes an existing `jobHash` or `DecisionSnapshot` identity.

## 5. V1 tunable dimensions

V1 automatically chooses only:

```text
lookbackMonths
Top-K
absoluteThreshold
allocationMethod ∈ { equal, inverse_volatility, risk_parity_erc }
```

Fixed inputs, not optimization dimensions:

- risky / defensive configured universe membership;
- outer Walk-Forward schedule;
- initial amount;
- transaction-cost assumption;
- risk-free-rate context;
- covariance estimator / annualization / risk-data sufficiency methodology;
- market-data / FX method;
- execution-delay semantics;
- Portfolio v3 accounting;
- metric formulas.

## 6. Search-space canonicalization

Backend owns canonical candidate enumeration.

1. Normalize and deduplicate each dimension before Cartesian enumeration.
2. `lookbackMonths` obeys the existing Dual Momentum range.
3. Every `Top-K` must be valid for the fixed risky universe.
4. Thresholds must be finite; `-0.0` canonicalizes to `0.0`.
5. Allocation method must be one of the existing 4B-2 methods.
6. Duplicate parameter tuples collapse before capacity accounting.
7. Candidate order is independent of request-list ordering.

Canonical tuple ordering:

```text
(lookbackMonths, topK, absoluteThreshold, allocationMethodOrder)
```

Versioned allocation order:

```text
equal → inverse_volatility → risk_parity_erc
```

Each candidate receives a SHA-256 canonical-JSON `parameterHash`; the normalized search space receives `searchSpaceHash`; the candidate list + validation policy + planned work receive a separate search-plan identity.

## 7. Outer / inner temporal firewall

For each outer period:

```text
Outer Training end == Outer Decision
Outer Evaluation starts after Outer Decision
```

Inner tuning exists only inside Outer Training:

```text
Inner Training end == Inner Decision
Inner Evaluation starts after Inner Decision
Inner Evaluation end <= Outer Training end
```

Required orchestration order:

```text
fetch/build Outer Training once
→ tune only inside Outer Training
→ choose winner parameters
→ refit winner on full Outer Training
→ freeze outer DecisionSnapshot
→ only then fetch/validate Outer Evaluation
```

Outer Evaluation is structurally absent from the tuning component and cannot mutate the same outer Decision.

## 8. Inner-fold policy

V1 uses deterministic **completed calendar-month buckets** compatible with the current monthly Dual Momentum cadence.

Controls:

```text
foldCount
evaluationMonths
stepMonths
```

Default intent:

```text
evaluationMonths = 1
stepMonths = 1
```

`stepMonths >= evaluationMonths`; accepted inner Evaluation windows therefore do not overlap.

Rules:

1. Evaluation boundaries are calendar-month starts/ends, not arbitrary date-offset arithmetic.
2. If outer Training/Decision ends on calendar month-end, that completed month may be the newest inner Evaluation bucket.
3. If outer Training/Decision ends before calendar month-end, that partial month is excluded from inner OOS; the newest inner Evaluation ends at the previous calendar month-end.
4. Partial current-month observations remain in the full Outer Training dataset and participate in final winner refit.
5. Folds are generated deterministically, stored chronologically, and validated by the existing Walk-Forward non-overlap authority.
6. Every candidate sees the exact same schedule.
7. If Outer Training cannot support the maximum requested lookback plus all requested folds, the request fails closed.

This avoids inclusive month-length artifacts such as adjacent folds both containing November 30.

Production defaults use `foldCount = 3`; the V1 per-request fold ceiling is `6`.

## 9. One download, many audited views

Required flow:

```text
one Outer Training TWD history batch
→ one audited Outer Training ResearchDataset
→ deterministic parent-bounded child ResearchDataset views
→ all candidate evaluations
```

Child view rules:

- only parent-audited rows are used;
- no download, interpolation, filling or optimizer-private repair occurs;
- requested membership and explicit failure accounting are preserved;
- a parent-resolved symbol with zero audited availability in a child interval becomes an explicit child-window failure;
- child view gets its own deterministic ResearchDataset hash and binds parent identity.

No second downloader/cache/price authority is permitted.

## 10. Candidate execution

For each candidate and fixed inner fold:

```text
child Inner Training ResearchDataset
→ existing Dual Momentum + existing 4B-2 Allocation
→ frozen inner DecisionSnapshot
→ only then child Inner Evaluation ResearchDataset
```

All inner evaluations for that candidate feed:

```text
existing continuous Walk-Forward OOS ledger
→ existing Portfolio v3 metrics
```

Rules:

- no fold-local NAV reset;
- Portfolio v3 computes transaction costs;
- every required fold must complete for candidate eligibility;
- candidate-specific data/allocation failure is explicit;
- no silent symbol/fold truncation, alternate data, shorter windows, or Equal fallback;
- runtime completion order cannot affect accepted order or identity.

## 11. Accepted objective policy

V1 uses a transparent lexicographic objective, not another opaque composite score:

```text
1. higher exact continuous inner-OOS Sortino
2. lower abs(Max Drawdown)
3. higher CAGR
4. lower exact transaction costs
5. lexicographically lower canonical parameterHash
```

Unavailable/non-finite accepted ranking metrics make that candidate ineligible; they are never coerced to zero.

Proxy metrics may only be clearly labelled accelerators in later work. Any accepted winner must still be evaluated through the exact authoritative path.

## 12. Resource budget

Budget preflight must bound at least:

```text
candidateCount
innerFoldCount
outerPeriodCount
plannedTuningEvaluations = candidateCount × innerFoldCount × outerPeriodCount
```

V1 production limits are empirically bounded at:

```text
MAX_PARAMETER_CANDIDATES = 48
MAX_INNER_FOLDS = 6
MAX_TUNING_EVALUATIONS_PER_JOB = 216
```

Capacity evidence was collected on the exact 4B-3 quant/API tree with the audited `AAA/BBB/BND` synthetic integration regime and the real `run_inner_parameter_tuning` authority. Each case ran in an isolated GitHub-hosted runner job; timing below excludes dependency installation and measures tuning execution only.

| Candidates | Inner folds | Planned evaluations | Tuning wall time | Eligible |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 3 | 6 | 1.234 s | 2/2 |
| 12 | 3 | 36 | 10.165 s | 12/12 |
| 12 | 6 | 72 | 18.609 s | 12/12 |
| 24 | 3 | 72 | 20.076 s | 24/24 |
| 24 | 6 | 144 | 21.848 s | 24/24 |
| 48 | 3 | 144 | 39.293 s | 48/48 |
| 48 | 6 | 288 | 78.709 s | 48/48 |

The 288-evaluation case proves correctness/completability but is not accepted as the synchronous product ceiling: its ~78.7 s is tuning CPU alone and excludes live Training/Evaluation data access, winner refit and outer OOS orchestration. The global cap is therefore 216 while preserving the useful per-dimension ceilings of 48 candidates and 6 folds. The shipped default remains `12 candidates × 3 folds × 6 outer periods = 216` and therefore stays inside the final job ceiling.

Counts are request-derived and fail closed before market-data fetch. Unbounded Cartesian search is forbidden. Raising the 216 ceiling requires new empirical evidence and a separately reviewed release decision.

## 13. Tuning identity/evidence

A completed tuning result binds at least:

```text
objectivePolicyVersion
outerTrainingDatasetHash
searchSpaceHash / searchPlanHash
innerFoldScheduleHash
candidate parameter hashes
candidate status/failure evidence
candidate exact inner-OOS Sortino/MDD/CAGR/cost evidence
candidate inner Decision hashes
candidate inner Evaluation dataset hashes
winnerParameterHash
winnerParameters
resultHash
```

Same normalized request + same audited data + same methodology version must reproduce candidate order and winner identity.

## 14. Winner refit on full Outer Training

The tuning winner is a parameter set, not final weights.

```text
winner parameters
+ exact full Outer Training ResearchDataset
→ existing Dual Momentum + Allocation
→ final outer SelectionResult
→ existing configured DecisionSnapshot
```

Refit requires the same `outerTrainingDatasetHash` used by tuning. A result cannot be applied to another Training dataset.

The outer Decision binds optimization/objective identity, tuning/search/fold hashes, winner parameter identity, tuning evidence, and full-Outer-Training final selection/allocation evidence.

Existing Decision payload structure remains authoritative:

```text
selector: {
  contractVersion,
  rule,
  parameters
}
```

Do not create a second top-level selector-parameters schema.

## 15. Outer OOS remains existing authority

After the optimized outer Decision is frozen:

```text
existing outer Evaluation load
→ existing continuous Walk-Forward OOS ledger
→ existing Portfolio v3 costs / metrics
→ ResearchRun
```

Outer OOS evaluates the frozen methodology; it does not retroactively modify that period's search, winner, holdings or weights.

## 16. Public request / job identity

4B-3 must be explicitly discriminated from manual Dual Momentum. Intended semantic shape:

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

Rules:

- omission of `parameterOptimization` is existing manual behavior;
- explicit optimization receives a new job contract and selector policy;
- normalized search, validation and fixed assumptions enter job identity;
- manual fixed parameter fields and optimization search dimensions must not ambiguously compete for authority;
- old job hashes remain reconstructable.

## 17. ResearchRun

Existing D1 ResearchRun remains durable authority.

- exact original optimization request is stored;
- search/validation inputs are immutable on rerun;
- rerun creates new lineage through backend authority;
- it does not rewrite the request into the historical winner;
- browser-submitted candidate/winner evidence is forbidden;
- `jobHash` remains completed-result identity and `run_id` remains durable ResearchRun identity.

## 18. UX target

Optimizer Hub exposes:

```text
Manual parameters | Auto optimize
```

Auto Optimize should show:

- bounded search-space editor;
- normalized candidate count and planned candidate-fold evaluations;
- inner-fold timeline;
- visible objective policy;
- candidate progress/failure reasons;
- winner parameters/tie-break explanation;
- candidate leaderboard;
- final outer OOS clearly separated from inner tuning evidence;
- save/rerun through existing Research Library.

UI may format backend evidence but never recompute accepted results.

## 19. Required regressions

Release must prove:

1. legacy Exhaustive/4B-1/4B-2 normalized request and job identities remain unchanged;
2. outer Evaluation is absent from tuning inputs;
3. inner completed-month windows are deterministic, chronological, non-overlapping and inside Outer Training;
4. partial current outer month is excluded from inner OOS but retained for full Training refit;
5. every candidate sees the same inner schedule;
6. search identity is invariant to input dimension order/duplicates;
7. no candidate triggers a new market-data download;
8. child datasets stay inside parent/requested bounds;
9. failed candidates never silently change data/methodology;
10. accepted ranking uses exact continuous inner-OOS metrics;
11. unavailable primary metric is not zero;
12. canonical parameter hash is final deterministic tie-break;
13. winner is rerun on exact full Outer Training;
14. tuning/winner evidence is hash-bound into the existing outer Decision structure;
15. outer Evaluation loads only after final Decision exists;
16. ResearchRun rerun uses exact stored optimization request;
17. browser renders rather than recomputes authority evidence;
18. oversized search fails before expensive execution;
19. tampered tuning/winner identity fails closed;
20. a tuning result cannot be refit against a different outer Training hash.

## 20. Rejected shortcuts

Do not:

- tune on outer Evaluation;
- call full-period historical winners OOS evidence;
- let browser/AI submit authoritative scores;
- download market data per candidate;
- silently reduce search dimensions/folds/symbols/dates;
- vary cost assumptions to improve candidates;
- fall back from failed risk allocation to Equal;
- rank unavailable metrics as zero;
- invent an opaque AI score;
- accept a proxy winner without exact evaluation;
- mutate legacy request identity;
- create a second Decision/selector, Portfolio, metric, covariance or market-data authority;
- weaken CI/exact-SHA/production smoke gates.

## 21. Runtime expansion rule

```text
1. empirical benchmark
2. audited dataset reuse
3. identity-safe deterministic memoization where useful
4. bounded batch/cancellation/resume only if required
5. async durable jobs only if measured synchronous workloads are insufficient
```

No Redis/queue/distributed-worker expansion before measured product need.

The benchmark also exposed a separate execution-metadata boundary: long valid Walk-Forward `period_id` values could make the internal `PortfolioSpec` segment name exceed its 60-character validation limit. The OOS adapter now keeps full period identity in Decision/audit evidence and deterministically hash-compacts only the execution-only segment name when required; existing short names remain unchanged.

## 22. Release gates

4B-3 is expected R2 because it changes quantitative methodology and public research behavior.

Before Ready/merge:

- targeted mathematical/causal tests pass;
- full relevant regression passes;
- legacy identity regressions pass;
- API/UI contract matches backend evidence;
- browser E2E covers Auto Optimize;
- capacity benchmark establishes production caps/defaults;
- exact-head CI passes;
- independent exact-head methodology review approves;
- recovery point exists.

After merge:

- main CI success;
- Vercel production READY on exact accepted SHA;
- Cloudflare deploy/smokes success;
- Walk-Forward exact-SHA verifier recognizes new API/job contract;
- production runtime scan shows no 4B-3 defect.

4B-3 is not CLOSED before post-main gates pass.

## 23. Future extensions

Later separately versioned work may add Pareto/constraints/stability, MinVar/MaxDiv/custom risk budgets/HRP/HERC, execution tuning, robust ensembles, causal regime selection, and AI Research Autopilot. None is a hidden extension of 4B-3 V1.