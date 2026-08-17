# Optimizer Hub Parameter Optimization V1

Status: **Phase 4B-3 candidate contract.** This document defines the methodology boundary for implementation. It does not become production authority until code, tests, exact-head review, merge, and post-main production verification pass.

## 1. Purpose

Phase 4B-3 adds a bounded parameter-search stage to the existing Optimizer Hub without allowing the same outer Evaluation period to influence the parameters being evaluated on that outer period.

Existing production chain:

```text
configured universe
→ Dual Momentum Selection
→ explicit Allocation
→ DecisionSnapshot
→ outer Walk-Forward Evaluation
→ Portfolio v3 continuous OOS ledger
→ metrics
→ ResearchRun
```

Phase 4B-3 chain:

```text
configured universe
→ Outer Training
   → bounded nested temporal tuning inside Outer Training only
   → chosen parameter candidate
   → rerun chosen parameters on full Outer Training
→ frozen DecisionSnapshot
→ Outer Evaluation
→ existing Portfolio v3 continuous OOS ledger
→ metrics
→ ResearchRun
```

Parameter optimization is therefore a **Training-only model-selection problem**, not a second performance engine and not a license to reuse outer OOS evidence.

## 2. Authority boundaries

| Concern | Authority |
| --- | --- |
| configured membership | `ConfiguredResearchUniverse` |
| audited TWD history | `TWDHistoryService` / `ResearchDataset` |
| Dual Momentum signal | frozen 4B-1 engine |
| allocation methods | frozen 4B-2 engine |
| covariance / risk contribution | Risk Mathematics |
| inner and outer OOS accounting | existing Walk-Forward OOS + Portfolio v3 authority |
| performance metrics | existing metric authority |
| final decision identity | existing configured `DecisionSnapshot` seam |
| durable completed research | D1 ResearchRun |

The browser and AI may specify a search space and render backend evidence. They do not calculate authoritative candidate metrics or choose the winner locally.

## 3. Versioned identities

Candidate tuning contract:

```text
optimizer-hub-parameter-optimization-2026-08-18.1
```

Candidate job contract:

```text
walk-forward-dual-momentum-parameter-optimization-job-2026-08-18.1
```

Candidate selector policy:

```text
dual-momentum-nested-parameter-optimization-v1
```

Candidate objective policy:

```text
inner-oos-sortino-lexicographic-v1
```

These strings may change before the first production candidate only through an explicit contract update. Once released, later behavior changes require new versions.

## 4. Backward compatibility

Legacy replay is mandatory:

- Dual Momentum requests without optimization configuration continue through existing 4B-1 or 4B-2 paths unchanged.
- A legacy request that omits `allocationMethod` remains 4B-1 identity.
- A request with explicit fixed `allocationMethod` and no optimization remains 4B-2 identity.
- Only a request with explicit optimization configuration opts into 4B-3.
- ResearchRun rerun replays the exact stored request; old runs are never upgraded implicitly.

Phase 4B-3 must not change old normalized request payloads, `jobHash`, selector policy, decision hash, or allocation evidence merely because the new optimizer exists.

## 5. V1 tunable dimensions

V1 search space is intentionally narrow:

```text
lookbackMonths
Top-K
absoluteThreshold
allocationMethod
```

Allowed allocation values reuse 4B-2 exactly:

```text
equal
inverse_volatility
risk_parity_erc
```

V1 does not optimize:

- risky universe members;
- defensive universe members;
- outer period dates;
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

Recommended canonical tuple order:

```text
(lookbackMonths, topK, absoluteThreshold, allocationMethodOrder)
```

where allocation method order is versioned and deterministic.

Each candidate receives a SHA-256 canonical-JSON parameter identity. The whole normalized search space receives a separate `searchSpaceHash`.

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

## 8. Inner-fold policy

V1 uses a deterministic monthly temporal-validation policy compatible with the current Dual Momentum cadence.

The API exposes a bounded inner-validation configuration rather than arbitrary date arrays. Initial supported controls are expected to be:

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

The exact production default and maximum `foldCount` are set only after runtime-capacity benchmarking.

The newest valid folds are preferred so tuning evidence is relevant to the outer Decision while still remaining entirely pre-decision. Fold construction must be deterministic from the normalized request and outer period dates.

A candidate search is rejected when the outer Training interval cannot support every requested candidate's maximum lookback plus the requested inner fold schedule.

## 9. One download, many audited inner views

The tuner must not download market data separately for every candidate.

Required data flow:

```text
one Outer Training TWD history batch for configured members
→ audited outer ResearchDataset
→ deterministic bounded inner date slices/views
→ candidate evaluation
```

Implementation may add a tested slicing/view helper, but it must remain inside the existing TWD history / ResearchDataset authority and preserve explicit requested/resolved/failure semantics.

Do not add a second market-data cache, downloader, or optimizer-private price source.

A sliced inner view must have its own deterministic identity for its effective date interval and contents; it may not reuse the parent dataset hash while representing different rows.

## 10. Candidate execution

For each normalized parameter candidate and each inner fold:

1. build/derive the exact inner Training dataset;
2. run the existing Dual Momentum methodology with the candidate parameters;
3. if selected allocation is risk-based, reuse the existing 4B-2 allocation method and Risk Mathematics authority;
4. freeze the inner Decision;
5. build/derive the exact inner Evaluation dataset;
6. validate Evaluation only after the inner Decision exists;
7. run existing continuous OOS transition / Portfolio v3 ledger semantics;
8. preserve failures explicitly.

Candidate execution must not introduce proxy return, covariance, turnover, MDD, or Sortino formulas.

## 11. Continuous inner-OOS objective

Inner folds are evidence partitions, not independent portfolios.

A candidate is evaluated using one continuous inner-OOS ledger across its ordered inner folds, reusing the same no-reset semantics as outer Walk-Forward.

The accepted V1 primary objective is:

```text
maximize exact inner-OOS Sortino
```

The Sortino value comes from the existing authoritative metric context for the inner continuous OOS ledger.

Unavailable Sortino is not coerced to zero; the candidate is ineligible for winning.

## 12. Deterministic V1 ranking

Candidate eligibility first requires all required inner folds to complete successfully under the configured strategy and allocation contracts.

Among eligible candidates, deterministic ranking is:

1. higher exact inner-OOS Sortino;
2. lower absolute max drawdown;
3. higher exact CAGR;
4. lower exact transaction-cost / turnover evidence available from the existing OOS authority;
5. canonical parameter hash ascending.

This is a transparent lexicographic policy. It is intentionally not a hidden weighted composite score.

If no candidate is eligible, the outer period fails closed. It does not silently rerun the original manual parameters or Equal Weight.

## 13. Winner refit on full Outer Training

Inner tuning chooses a parameter tuple, not the final outer weights.

After a winner is selected:

```text
winner parameters
+ full Outer Training ResearchDataset
→ existing Dual Momentum engine
→ existing chosen allocation method
→ final outer selected constituents / weights
→ outer DecisionSnapshot
```

This mirrors standard model-selection/refit behavior: all information available up to the outer Decision may be used after the hyperparameters are frozen.

The final outer Decision is created before outer Evaluation history is requested or validated.

## 14. Tuning evidence

Backend-produced evidence must include at least:

```text
tuningContractVersion
objectivePolicyVersion
searchSpaceHash
innerFoldScheduleHash
candidateCount
plannedCandidateFoldEvaluations
candidate summaries
winnerParameterHash
winnerParameters
winnerRank
winner objective / tie-break metrics
trainingDatasetHash
```

Each candidate summary should expose enough evidence for debugging and explanation without serializing unnecessary full inner ledgers by default:

```text
parameterHash
parameters
status
failedFold / failureReason when applicable
completedFoldCount
innerOosMetricSummary
innerOosIdentity
```

Detailed inner evidence may be bounded or fetched separately later if response size requires it. A compact response must not discard the identities needed to reproduce it.

## 15. Decision identity

The selected tuning evidence and chosen parameters must be hash-bound before outer Evaluation.

Preferred composition is through the existing configured selection-evidence / DecisionSnapshot seam rather than creating a second decision object.

The final configured decision identity must therefore distinguish:

- manual 4B-1;
- explicit fixed allocation 4B-2;
- explicit nested parameter optimization 4B-3.

A numerically identical final weight vector from different tuning evidence is not the same research decision.

## 16. Job identity

The 4B-3 normalized job hash binds:

- outer period schedule;
- configured risky/defensive membership;
- normalized optimization search space;
- inner validation policy;
- objective policy version;
- execution / transaction-cost assumption;
- all existing versioned methodology identities.

Request list ordering that normalizes to the same canonical search space must not change job identity.

## 17. Capacity model

Current production already limits outer Walk-Forward periods and configured symbols. Parameter search adds another dimension and therefore requires an explicit candidate-fold budget.

Before a release candidate is Ready, benchmark at least:

```text
candidateCount
× innerFoldCount
× outerPeriodCount
× allocation method mix
× configured symbol count
```

Release must define and expose versioned hard limits for at least:

```text
MAX_PARAMETER_CANDIDATES
MAX_INNER_FOLDS
MAX_TUNING_EVALUATIONS_PER_JOB
```

The UI/API preflight shows normalized candidate count and planned tuning evaluations before execution.

Budget overflow fails closed before market-data work begins when possible.

Initial defaults must be materially below the measured safe ceiling. Do not infer a production limit from the theoretical method contract alone.

## 18. No premature asynchronous infrastructure

V1 remains synchronous if empirical benchmark evidence shows useful default searches fit the accepted production runtime envelope.

Only if measured product workloads fail that envelope should a later technical batch add durable asynchronous execution/cancellation/resume.

Do not add Redis, queues, distributed workers, or a second persistent result store merely because parameter search can be large.

## 19. API direction

The public request remains discriminated and backward-compatible.

Conceptual new shape:

```json
{
  "selector": {
    "strategy": "dual_momentum",
    "riskySymbols": ["QQQ", "SMH", "SPY"],
    "defensiveSymbols": ["BIL"],
    "optimization": {
      "method": "nested_grid_v1",
      "searchSpace": {
        "lookbackMonths": [6, 9, 12],
        "topK": [1, 2],
        "absoluteThreshold": [0.0],
        "allocationMethod": ["equal", "inverse_volatility", "risk_parity_erc"]
      },
      "innerValidation": {
        "foldCount": 4,
        "evaluationMonths": 1,
        "stepMonths": 1
      },
      "objective": "sortino"
    }
  }
}
```

Exact field names may be finalized during implementation, but these semantic rules are fixed:

- optimization is explicit opt-in;
- fixed manual strategy parameters and an optimization search space must not be ambiguous;
- unknown dimensions/methods fail closed;
- server canonicalizes and reports the effective search space;
- browser cannot submit completed candidate evidence.

## 20. UX direction

The existing Walk-Forward / Optimizer Hub workspace gains an explicit mode switch:

```text
Manual parameters | Auto optimize
```

V1 UX must show:

- normalized search dimensions;
- candidate count;
- planned tuning evaluations;
- inner-fold schedule;
- progress / cancellation semantics supported by the current execution model;
- winner parameters;
- exact objective and tie-break explanation;
- candidate leaderboard with explicit failed reasons;
- final outer OOS results separately labelled from inner tuning evidence;
- Research Library save/rerun through the existing authority.

The UI must visually distinguish **Tuning evidence** from **Outer OOS validation**.

## 21. ResearchRun semantics

No new persistence authority is introduced.

- saved run stores the original explicit optimization request;
- completed backend result is persisted by the existing ResearchRun path;
- rerun submits the exact original request;
- rerun creates a new run identity while reproducing deterministic job identity when external data/version authorities are unchanged;
- browser local state remains convenience only.

## 22. Required regression invariants

A 4B-3 release must prove:

1. legacy Exhaustive/PIT requests unchanged;
2. legacy Dual Momentum 4B-1 request identity unchanged;
3. explicit fixed-allocation 4B-2 request identity unchanged;
4. optimization request has separate versioned job/selector identity;
5. outer Evaluation is never read before winner parameters and final outer Decision are frozen;
6. every candidate for an outer period sees identical inner fold dates;
7. search-space request ordering does not change canonical candidates or winner;
8. duplicate parameter inputs do not duplicate budget or evaluations;
9. insufficient lookback/fold coverage fails closed;
10. risk-allocation failure remains explicit and never silently becomes Equal Weight;
11. accepted candidate metrics come from exact continuous inner OOS authority, not proxy metrics;
12. inner folds use no period-local NAV reset;
13. winner is refit on full Outer Training only after parameter selection;
14. tuning evidence is hash-bound into final configured Decision identity;
15. same normalized request and same underlying versioned data produces deterministic winner/job identity;
16. browser cannot fabricate authoritative candidate results;
17. ResearchRun save/load/rerun preserves exact optimization request;
18. capacity preflight fails before unbounded Cartesian work;
19. production exact-SHA gates remain fail closed.

## 23. Required tests

At minimum:

- temporal-boundary unit tests for inner fold construction;
- no-outer-OOS spy/fake-history tests;
- canonical search-space/hash tests;
- duplicate/reordered input invariance;
- ranking/tie-break fixtures;
- candidate failure propagation;
- continuous inner-OOS no-reset tests;
- legacy 4B-1 / 4B-2 golden identity regression;
- winner full-Training refit test;
- API validation and normalized request tests;
- UI request/evidence tests;
- ResearchRun exact-rerun tests;
- capacity guard tests;
- browser E2E for Manual ↔ Auto optimize;
- full existing CI/regression suite.

## 24. Open implementation decisions that must close before Ready

These are implementation parameters, not permission to change the causal contract:

1. exact maximum/default inner fold count;
2. exact maximum/default parameter candidate count;
3. exact total candidate-fold budget;
4. concrete audited inner-view/slicing helper placement;
5. response compaction threshold for candidate evidence;
6. progress granularity under the current synchronous API;
7. exact API field names / TypeScript discriminated union.

They must be resolved by code evidence, tests and capacity measurements before the PR moves to Ready.

## 25. Out of scope / rejected shortcuts

Do not include in 4B-3 V1:

- outer-OOS-driven parameter selection;
- current/latest data outside each outer Training window;
- tuning risky/defensive membership;
- Min-Variance / Max-Diversification / HRP / HERC;
- rebalance cadence optimization;
- custom risk budgets;
- arbitrary custom objective formulas;
- AI-generated executable strategy code;
- browser optimizer authority;
- per-candidate market-data downloads;
- proxy MDD/Sortino used as final candidate ranking;
- silent history/member/date truncation;
- silent failed-candidate fallback;
- alternate Portfolio/metric/covariance engine;
- unrelated PR #147/security/infrastructure work;
- CI or production-smoke weakening.

Those belong to later roadmap phases or remain rejected.

## 26. Later extension seam

After 4B-3 is production accepted, the same nested tuning authority may support separately versioned additions:

```text
4B-4 robust constraints / Pareto / stability
4B-5 additional allocation methods
4B-6 rebalance / execution tuning
4B-7 stable ensembles / regime-safe model selection
4C AI Research Autopilot
```

Later phases must reuse this causal nested-tuning seam rather than selecting parameters from the outer Evaluation results.