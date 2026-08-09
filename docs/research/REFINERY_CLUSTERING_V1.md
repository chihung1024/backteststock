# Portfolio Refinery Clustering & Redundancy V1

Status: Phase 5 methodology contract. This phase adds deterministic hierarchical clustering and descriptive redundancy evidence on top of `ResearchDatasetV1`, `Risk Mathematics V1`, Refinery API V1 and Refinery UI V1. It does **not** recommend trades, select holdings, size positions, run marginal experiments, integrate Exhaustive, or make out-of-sample claims.

## Contract identity

```text
REFINERY_CLUSTERING_CONTRACT_VERSION = refinery-clustering-twd-2026-08-10.1
PRIMARY_CLUSTER_INPUT                 = structural synchronized weekly TWD returns
PRIMARY_LINKAGE                       = average
SENSITIVITY_LINKAGE                   = complete
PRIMARY_FLAT_CUT_DISTANCE             = 0.50
BOOTSTRAP_REPLICATES                  = 200
BOOTSTRAP_BLOCK_WEEKS                 = 4
STABILITY_WINDOWS_WEEKS               = 52, 104, 156
```

These are versioned research-consumer policies, not universal statistical constants. Any change to distance, linkage, cut, bootstrap, stability or verdict semantics requires an explicit contract version change and parity/regression review.

## 1. Authority boundaries

Phase 5 preserves the existing architecture:

- `TWDHistoryService` remains the market-data/FX authority.
- `ResearchDatasetV1` remains the requested/resolved membership, TWD calendar, daily/weekly return and reproducibility authority.
- `apps/api/app/quant/` owns pure clustering/factor mathematical primitives.
- `apps/api/app/refinery/` composes evidence and applies the versioned descriptive verdict policy.
- `api/refinery_v1.py` remains the self-owned public Refinery entrypoint.
- `apps/portfolio-web/` renders returned evidence only; browser code must not become a second clustering/redundancy calculation authority.
- Portfolio v3 Ledger/analytics remains independent; Refinery must not import Portfolio Ledger models as a generic research bag.

No new downloader is introduced for candidate prices or FX.

## 2. Membership and fail-closed semantics

Clustering/redundancy analysis is emitted only when Phase 3 candidate membership is complete and Phase 3 formal analysis is otherwise eligible.

If any requested candidate is unresolved:

- top-level Refinery status remains `incomplete`;
- clustering/redundancy output is unavailable/null;
- the resolved subset must **not** be silently clustered as if it were the requested universe.

If structural weekly evidence is unavailable or degenerate, the API may still return the existing Phase 4 risk diagnostics, but clustering/redundancy evidence must fail closed with an explicit status/reason.

## 3. Primary structural dependency input

The authoritative clustering input is the existing ResearchDataset synchronized **weekly TWD** return matrix, not the daily close matrix.

Reason:

- daily TWD returns remain authoritative for Taiwanese-investor NAV/risk;
- mixed-market daily closes are asynchronous across U.S./Taiwan/Japan/Europe;
- the existing `W-FRI period last actual TWD observation` policy is the structural dependency layer already frozen in ResearchDataset V1.

The primary structural view uses at most the latest 156 weekly observations and the existing complete-case semantics. Phase 5 must not invent a second weekly calendar.

Daily tactical/medium, downside and stress correlations remain corroborating evidence only.

## 4. Correlation distance

For a valid Pearson correlation matrix `rho`:

```text
d_ij = sqrt((1 - rho_ij) / 2)
```

Implementation rules:

1. reorder symbols into canonical lexicographic order before clustering so request-order permutations cannot change tie resolution merely by column position;
2. enforce a square symmetric finite matrix with unit diagonal;
3. clip only floating-point overshoot to `[-1, 1]` before distance conversion;
4. set diagonal distance to exactly zero;
5. reject materially non-symmetric/non-finite inputs rather than silently repairing them;
6. return symbols and results in explicit labelled form so later UI never infers ordering from raw matrix position.

This correlation distance is suitable for correlation-based hierarchical clustering. **Ward linkage is not the default and is not allowed in V1** because the project is not treating this transformed correlation distance as an ordinary Euclidean observation matrix for Ward variance minimization.

## 5. Hierarchical clustering

### Primary hierarchy

```text
linkage = average
```

Average linkage operates on the condensed correlation-distance matrix.

### Sensitivity hierarchy

```text
linkage = complete
```

Complete linkage is computed from the same structural matrix as a sensitivity diagnostic.

### Determinism

The implementation must canonicalize symbol order before constructing the condensed matrix. Flat cluster IDs are then canonicalized by sorted member sets; raw SciPy cluster numbers are never treated as stable public identifiers.

The response must include enough hierarchy evidence to render a dendrogram/tree without recomputing linkage in the browser:

- canonical symbol order;
- linkage method;
- merge rows / child references;
- merge distance;
- merged sample count;
- canonical flat memberships at the display cut.

## 6. Flat cluster display cut

Phase 5 V1 uses an explicit descriptive cut:

```text
PRIMARY_FLAT_CUT_DISTANCE = 0.50
```

For direct pairwise correlation this corresponds to `rho = 0.50`, but hierarchical cluster membership depends on linkage aggregation and therefore is not equivalent to saying every within-cluster pair has correlation >= 0.50.

The cut exists to make cluster/stability evidence inspectable and reproducible. It is **not** claimed to be statistically optimal and must be displayed as a versioned methodology parameter.

Average-linkage membership is primary descriptive grouping; complete-linkage membership at the same cut is sensitivity evidence.

## 7. Multi-window stability

Phase 5 computes structural clustering on these trailing weekly windows when available:

```text
52 weeks
104 weeks
156 weeks
```

Every window reuses the same ResearchDataset weekly return policy and complete-case rules. A window is available only when it meets the existing structural minimum-observation guard; unavailable windows remain explicit and are excluded from the denominator of agreement calculations.

For each asset pair, report:

- number of available windows;
- number of windows in which both assets share the same average-linkage flat cluster;
- `window_cocluster_agreement = same / available` when at least two windows are available;
- unavailable/null when fewer than two windows are available.

No missing window is counted as disagreement.

## 8. Bootstrap cluster stability

### Sampling policy

Use deterministic circular moving-block bootstrap on the primary structural weekly complete-case return frame:

```text
replicates   = 200
block length = 4 weeks
```

Rows are resampled jointly across every candidate so cross-sectional dependence is preserved. Blocks preserve short local time ordering better than iid row resampling.

### Deterministic seed

The bootstrap seed is derived from canonical SHA-256 material containing:

- candidate `dataset_hash`;
- `REFINERY_CLUSTERING_CONTRACT_VERSION`;
- primary linkage;
- flat-cut distance;
- bootstrap replicate count;
- bootstrap block length.

Repeated analysis of the same frozen dataset/contract must therefore produce identical bootstrap output.

### Bootstrap output

For every pair, report average-linkage co-cluster probability at the primary flat cut.

For every primary flat cluster with at least two members, report mean pairwise bootstrap co-cluster probability as descriptive cluster stability. Singleton stability is `not_applicable`, not `1.0`.

If a bootstrap replicate becomes degenerate, that replicate is explicitly counted as unusable. The response reports requested/usable replicate counts; it must not silently pretend 200 successful replicates were obtained.

## 9. Price-based redundancy evidence

For each unordered candidate pair, Phase 5 may expose these evidence fields:

- structural weekly correlation;
- medium daily correlation;
- downside correlation when benchmark-conditioned evidence is available;
- stress correlation when benchmark-conditioned evidence is available;
- same primary average-linkage cluster;
- same complete-linkage sensitivity cluster;
- multi-window co-cluster agreement;
- bootstrap co-cluster probability;
- observations/status for every underlying view.

Tactical 63D daily correlation may be displayed as context but is not a core redundancy verdict input because it is intentionally short-horizon.

## 10. Factor-implied relationship evidence

Factor evidence is secondary corroboration only. It must never override contradictory structural price evidence by itself.

### Scope

V1 may calculate factor evidence only for assets where:

- quote currency is USD;
- native-return history is available;
- at least 36 overlapping monthly observations exist with the official Kenneth French factor data.

Other assets receive an explicit unavailable scope status. This is deliberately labelled a **U.S.-factor co-movement diagnostic**, not a universal global factor model.

### Return/factor semantics

Use monthly compounded **native-currency** asset returns for this diagnostic so TWD FX translation is not folded into U.S. equity-factor beta estimates.

For eligible assets:

```text
asset excess return = native monthly return - RF
predictors           = MKT_RF, SMB, HML, RMW, CMA, MOM
```

Factor data must come from the existing official Kenneth French Data Library adapter after that adapter is moved/re-exported through a shared research/data authority. Refinery must not reverse-depend on Portfolio Ledger code.

### Factor-implied covariance/correlation

Let `beta_i` be an asset's factor-beta vector and `Sigma_F` the covariance matrix of aligned factor returns over the research sample:

```text
Cov_factor(i,j) = beta_i' Sigma_F beta_j
Corr_factor(i,j) = Cov_factor(i,j) /
                   sqrt(Cov_factor(i,i) * Cov_factor(j,j))
```

This is correlation of the **factor-implied systematic component**, not total asset-return correlation. Idiosyncratic residual variance is intentionally not presented as systematic overlap.

Per-asset output includes observations, beta vector and R-squared. Pairwise factor-implied correlation is considered a usable corroborator only when both assets have valid regressions; low R-squared remains visible and reduces confidence rather than being hidden.

No raw beta-vector cosine is used as the official factor-overlap evidence.

## 11. Economic-theme evidence

Phase 5 must not infer opaque economic themes from ticker names, current web prose or an unversioned LLM classification.

V1 permits theme evidence only when a deterministic traceable source exists with at least:

- source/provider;
- taxonomy/version;
- effective/retrieval date;
- per-symbol labels;
- confidence/provenance.

Until such a source is implemented, theme evidence is returned as:

```text
status = unavailable_no_traceable_theme_source
```

This explicit unavailable state satisfies the architecture requirement better than silently fabricating themes. Any later automatic theme source requires separate methodology/version review and remains read-only until Point-in-Time governance is available.

## 12. Redundancy verdict policy

Verdicts describe **historical exposure redundancy evidence** only:

```text
HIGH
MEDIUM
LOW
UNCERTAIN
```

There is no numeric 0–100 score.

### Core usable evidence

A pair needs valid structural correlation and bootstrap evidence to receive HIGH/MEDIUM/LOW. Otherwise verdict is `UNCERTAIN`.

### HIGH

All must hold:

- structural weekly correlation >= 0.80;
- same average-linkage cluster;
- same complete-linkage cluster;
- bootstrap co-cluster probability >= 0.75;
- multi-window co-cluster agreement is available and >= 2/3;
- medium daily correlation is available and >= 0.70.

### MEDIUM

All must hold:

- structural weekly correlation >= 0.65;
- same average-linkage cluster;
- bootstrap co-cluster probability >= 0.60;

and at least one available corroborator holds:

- medium daily correlation >= 0.60;
- downside correlation >= 0.65;
- stress correlation >= 0.65;
- factor-implied correlation >= 0.65 with both factor regressions valid;
- future traceable theme evidence explicitly shows shared theme.

Missing optional corroborators are not treated as zero.

### LOW

All must hold:

- structural weekly correlation <= 0.35;
- not in the same average-linkage cluster;
- bootstrap co-cluster probability <= 0.35.

### UNCERTAIN

Everything not satisfying HIGH/MEDIUM/LOW, including conflicting evidence, insufficient stability, or missing core evidence.

These thresholds are conservative descriptive policy. They are not estimates of probability that one asset should replace another.

## 13. Confidence and provenance

Verdict and confidence are separate concepts.

Every pair retains:

- structural/medium/downside/stress observation counts and statuses;
- available stability-window count;
- bootstrap requested/usable replicates;
- factor observation/R-squared evidence when applicable;
- theme provenance/status;
- dataset hash and methodology versions.

The UI may summarize confidence as `HIGH / MEDIUM / LOW` using an explicit versioned rule, but must always retain the underlying evidence and must not conflate confidence with redundancy verdict.

V1 initial confidence rule:

- HIGH: 3 stability windows available, >=190 usable bootstrap replicates, and all core correlation views used by the verdict have their configured minimum observations;
- MEDIUM: >=2 stability windows, >=160 usable bootstrap replicates, and structural/medium core views valid;
- LOW: otherwise.

## 14. Asset and cluster summaries

The API may produce convenience summaries from pair evidence:

### Cluster summary

- canonical cluster ID;
- sorted members;
- member count;
- mean/min/max structural correlation within cluster;
- mean bootstrap co-cluster stability when applicable;
- complete-linkage sensitivity agreement.

### Asset redundancy neighborhood

For each asset:

- HIGH pair peers;
- MEDIUM pair peers;
- LOW pair peers;
- UNCERTAIN pair peers;
- strongest evidence peers sorted deterministically by verdict class, bootstrap stability, absolute structural correlation and symbol.

This is **not** a stock rank or replace list. No asset receives a KEEP/TRIM/REPLACE label in Phase 5.

## 15. Public API extension

Phase 5 extends the existing successful Refinery `analyze` response rather than creating a second candidate-data fetch or a browser-side research engine.

Expected new top-level analysis sections:

```text
analysis.clustering
analysis.redundancy
analysis.factor_relationships
analysis.theme_relationships
```

Existing Phase 3/4 fields remain backward compatible.

Externally observable schema additions require a Refinery API schema-version bump while preserving `contract_version = refinery-v1` unless the request contract itself becomes incompatible.

No new request fields are required in V1 clustering. Existing candidate/date/benchmark/weights/EWMA/stress inputs remain authoritative.

## 16. Resource bounds

The existing candidate maximum remains 100.

Phase 5 adds explicit deterministic guards:

```text
MAX_CLUSTER_ASSETS      = 100
BOOTSTRAP_REPLICATES    = 200
BOOTSTRAP_BLOCK_WEEKS   = 4
MAX_PAIR_ROWS           = 4,950  # C(100,2)
```

The API may return all pair evidence for <=100 assets only if the existing 4 MiB canonical response guard still passes. If measured response size would exceed that bound, the endpoint fails closed; it must not silently truncate pair membership/evidence.

UI may render a deterministic subset/sorted table for performance while retaining the API evidence semantics.

## 17. UI semantics

Phase 5 adds read-only panels to the existing Refinery workspace:

1. `群聚結構` — average hierarchy/cluster groups, complete-linkage sensitivity and stability;
2. `重複曝險證據` — pair evidence/verdict/confidence table;
3. `因子關係` — eligible U.S.-factor diagnostics with explicit scope/limitations;
4. `主題關係` — provenance or explicit unavailable state.

UI rules:

- do not recompute clustering/verdicts in TypeScript;
- do not color HIGH as an automatic sell signal;
- always expose methodology version and key cut/bootstrap parameters;
- large pair tables use deterministic top-N presentation/filtering without changing API evidence;
- mobile must not mount an unbounded dendrogram/table that causes page overflow;
- existing Phase 4 risk/correlation diagnostics remain available and unchanged.

## 18. Required pure-math invariants and tests

At minimum:

1. correlation-distance matrix is symmetric, zero-diagonal and bounded `[0,1]`;
2. request/column permutation produces the same canonical hierarchy/memberships after relabelling;
3. perfect duplicates have zero distance and cluster together;
4. perfectly anticorrelated assets have distance 1;
5. identity correlation produces equal off-diagonal distance `sqrt(1/2)`;
6. average/complete linkage reference fixtures match SciPy on canonical condensed distances;
7. Ward is not accepted as a V1 method;
8. bootstrap output is deterministic for the same dataset hash/contract;
9. bootstrap row resampling is joint across assets;
10. unusable bootstrap replicates are counted rather than hidden;
11. multi-window missing evidence is excluded rather than counted as disagreement;
12. verdict rules are order independent and missing optional evidence never becomes numeric zero;
13. factor-implied covariance/correlation matches an independently computed matrix fixture;
14. non-USD/insufficient factor samples fail closed as unavailable;
15. theme evidence remains unavailable without a traceable source.

## 19. Required API/regression tests

Before merge:

1. incomplete candidate membership still blocks all formal clustering/redundancy analysis;
2. benchmark failure only removes downside/stress corroboration and does not fabricate it;
3. no-weight analysis remains valid for structural clustering; no equal weights are invented;
4. candidate permutation produces equivalent labelled clustering/redundancy evidence;
5. deterministic repeat requests over the same injected dataset produce identical output;
6. API schema/methodology versions expose the Phase 5 contract;
7. response-size/canonical-JSON guards still pass;
8. existing Phase 3/4 response fields remain unchanged for the same input dataset;
9. Worker route/security behavior remains unchanged unless separately required;
10. existing Portfolio, Scanner and Exhaustive regression suites remain unchanged.

## 20. Required browser gates

Add browser coverage for:

1. existing Portfolio workspace flow remains unchanged;
2. existing Phase 4 Refinery diagnosis flow remains unchanged;
3. cluster group/stability panel rendering;
4. average vs complete sensitivity evidence;
5. HIGH/MEDIUM/LOW/UNCERTAIN redundancy evidence rendering without recommendation labels;
6. factor available/unavailable scope states;
7. explicit unavailable theme-source state;
8. >20 and 100-candidate presentation guard;
9. 390px Refinery page remains usable without horizontal page overflow.

## 21. Explicit non-goals

Phase 5 does **not** implement:

- KEEP / TRIM / REPLACE;
- stock selection/ranking as an investment action;
- Remove-One / Add-One / Replace-One;
- position sizing, ERC, HRP or minimum-variance optimization;
- Exhaustive candidate selection;
- future-return alpha claims;
- OOS/walk-forward validation;
- point-in-time Universe/fundamentals;
- untraceable automatic economic-theme classification.

Those remain later phases.