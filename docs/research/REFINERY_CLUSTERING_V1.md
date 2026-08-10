# Portfolio Refinery Clustering & Redundancy V1

Status: **Phase 5 methodology baseline / UNDER FINAL REVIEW / NOT MERGE-APPROVED**.

This document defines the initial Phase 5 clustering/redundancy methodology implemented on PR #65. It adds deterministic hierarchical clustering and descriptive redundancy evidence on top of `ResearchDatasetV1`, `Risk Mathematics V1`, Refinery API V1 and Refinery UI V1. It does **not** recommend trades, select holdings, size positions, run marginal experiments, integrate Exhaustive, or make out-of-sample claims.

## Review status and amendment gate

The initial `.1` methodology is not yet the final merge authority. Independent review reopened four narrow correctness/contract questions:

1. bootstrap seed-data identity;
2. complete-month factor alignment;
3. factor computability vs applicability/corroboration;
4. common-sample factor-implied relationship semantics.

Details and acceptance criteria are recorded in [`PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md`](PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md).

Until those items are resolved in code + tests + contract together:

- PR #65 remains **NO-GO**;
- the `.1` text below is the auditable initial baseline, not a declaration that review findings are already implemented;
- accepted semantic changes require an explicit methodology-version review/bump;
- no future Agent should “fix the docs only” to make code and contract appear consistent.

## Contract identity — initial Phase 5 baseline

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

These are versioned research-consumer policies, not universal statistical constants. Any change to distance, linkage, cut, bootstrap identity/sampling, stability, factor evidence eligibility or verdict semantics requires explicit contract-version review and regression/parity evidence.

## 1. Authority boundaries

- `TWDHistoryService` remains market-data/FX authority.
- `ResearchDatasetV1` remains requested/resolved membership, TWD calendar, daily/weekly return and full dataset reproducibility authority.
- `apps/api/app/quant/` owns pure clustering/factor mathematical primitives.
- `apps/api/app/refinery/` composes evidence and applies versioned descriptive verdict policy.
- `api/refinery_v1.py` remains the public Refinery entrypoint.
- `apps/portfolio-web/` renders evidence only; it does not recompute clustering/redundancy/factor verdicts.
- Portfolio v3 ledger/analytics remains independent.

Candidate prices/FX are not re-downloaded by Phase 5. The Kenneth French factor adapter is a separate shared research-data source for the explicitly scoped factor diagnostic; it does not become a second candidate-price downloader.

## 2. Membership and fail-closed semantics

Formal clustering/redundancy is emitted only when candidate membership is complete and existing Refinery formal analysis is eligible.

If any requested candidate is unresolved:

- top-level Refinery status remains `incomplete`;
- `analysis = null` under the established API contract;
- the resolved subset is **not** silently clustered as a replacement universe.

If structural weekly evidence is unavailable/degenerate, existing Phase 4 risk diagnostics may still be returned where valid, but clustering/redundancy fails closed with explicit status/reason.

A benchmark failure affects only benchmark-conditioned downside/stress corroboration; it cannot change the candidate structural sample or fabricate a fallback benchmark.

## 3. Primary structural dependency input

The primary clustering input is the existing ResearchDataset synchronized **weekly TWD** return matrix.

Rationale:

- daily TWD returns remain authoritative for Taiwanese-investor NAV/risk;
- mixed-market daily closes are asynchronous;
- ResearchDataset already freezes the `W-FRI period last actual TWD observation` structural policy;
- Phase 5 must not invent a second weekly calendar.

The primary structural view uses at most the latest 156 weekly observations with existing complete-case semantics.

Tactical/medium daily, downside and stress correlations are distinct corroborating evidence, not interchangeable versions of one universal correlation matrix.

## 4. Correlation distance

For a valid Pearson correlation matrix `rho`:

```text
d_ij = sqrt((1 - rho_ij) / 2)
```

Implementation requirements:

1. canonical lexicographic symbol order before clustering;
2. square, symmetric, finite matrix with unit diagonal;
3. only floating-point overshoot is clipped to `[-1, 1]`;
4. diagonal distance exactly zero;
5. materially invalid inputs fail closed rather than being silently repaired;
6. all public results are explicitly labelled by symbol.

Ward is not a Phase 5 V1 default. Average/complete operate directly on the condensed distance representation; Ward/centroid/median impose Euclidean-distance requirements that this project does not assume for the precomputed correlation-distance workflow.

## 5. Hierarchical clustering

### Primary

```text
linkage = average
```

### Sensitivity

```text
linkage = complete
```

Both use the same structural correlation-distance matrix.

### Determinism

- canonicalize symbol order before condensed-distance construction;
- do not expose raw SciPy flat-cluster numbers as stable IDs;
- canonicalize public flat cluster IDs from sorted member sets;
- response includes enough labelled merge evidence for rendering without browser-side linkage.

Expected hierarchy evidence includes:

- canonical symbols;
- linkage method;
- merge child references;
- merge distance/count;
- canonical flat memberships at the display cut.

## 6. Flat display cut

```text
PRIMARY_FLAT_CUT_DISTANCE = 0.50
```

For a direct pair this maps to correlation 0.50, but hierarchical membership depends on linkage aggregation; it does not mean every within-cluster pair has correlation ≥0.50.

The cut is a reproducible descriptive policy, not a claim of statistical optimality.

## 7. Multi-window stability

Trailing structural windows when available:

```text
52 weeks
104 weeks
156 weeks
```

Each window reuses ResearchDataset weekly semantics and the structural minimum-observation guard.

For every unordered pair report:

- available windows;
- same-cluster windows under average linkage;
- `same / available` agreement when at least two windows are available;
- unavailable/null when fewer than two are available.

Unavailable windows are excluded from the denominator; they are not counted as disagreements.

## 8. Bootstrap cluster stability — initial `.1` baseline

### Sampling policy

Deterministic circular moving-block bootstrap over the primary structural weekly complete-case return frame:

```text
replicates   = 200
block length = 4 weeks
```

Rows are resampled jointly across candidate columns to preserve cross-sectional dependence. Degenerate replicates are counted as unusable rather than hidden.

### Initial `.1` seed contract

The original contract states seed material includes:

- candidate `dataset_hash`;
- clustering contract version;
- primary linkage;
- flat-cut distance;
- replicate count;
- block length.

### Active review finding

Current PR #65 implementation instead derives a canonical fingerprint from the structural weekly frame and feeds that identity into the bootstrap seed path to preserve request-order invariance. This is a real contract/implementation drift, not a wording-only issue.

The expected convergence is to define a dedicated **structural bootstrap fingerprint** without repurposing `ResearchDataset.dataset_hash`, but that amendment is not considered implemented by this documentation change alone. See Phase 5 convergence plan M1.

### Output

- pairwise average-linkage co-cluster probability;
- requested/usable/unusable replicate counts;
- cluster-level mean pairwise stability where applicable;
- singleton stability = `not_applicable`, not `1.0`.

## 9. Price-based redundancy evidence

For each unordered pair Phase 5 may expose:

- structural weekly correlation;
- medium daily correlation;
- downside correlation when benchmark-conditioned evidence is valid;
- stress correlation when valid;
- same average-linkage cluster;
- same complete-linkage cluster;
- multi-window co-cluster agreement;
- bootstrap co-cluster probability;
- observation/status evidence for underlying views.

Tactical 63D daily correlation may be displayed as context but is not a core verdict input in `.1`.

## 10. Factor-implied relationship evidence — initial `.1` baseline under review

Factor evidence is secondary corroboration only and cannot override contradictory structural evidence by itself.

### Data source / model scope

Phase 5 uses official Kenneth French monthly U.S. five-factor data plus U.S. momentum through the shared research adapter. Asset regressions use monthly compounded **native-currency** returns so TWD FX translation is not folded into the factor beta estimate.

```text
asset excess return = native monthly return - RF
predictors           = MKT_RF, SMB, HML, RMW, CMA, MOM
```

### Initial `.1` computability rule

The initial contract allowed factor calculation where:

- quote currency is USD;
- native-return history exists;
- at least 36 overlapping monthly observations exist.

This remains the auditable initial rule implemented on the branch, but it is **under review**.

### Review amendments required before merge

#### A. Complete-month alignment

Calendar-month labels alone are insufficient when a request begins/ends mid-month. A partial-month asset return must not be paired with a full-month Kenneth French factor observation. Phase 5 must freeze/test complete-month semantics before merge.

#### B. Computability vs applicability/corroboration

USD quotation proves denomination, not economic instrument/model applicability. The final V1 evidence contract must distinguish whether a factor diagnostic is mechanically computable from whether it is approved as redundancy-verdict corroboration.

Until a traceable applicability taxonomy exists, the conservative review proposal is to allow clearly labelled diagnostic output when computable but not let it upgrade a verdict merely because the instrument is USD-denominated.

#### C. Common relationship sample

Per-asset beta windows and the factor covariance sample must have one explicit relationship-sample policy. The preferred V1 convergence is a common complete-month sample for every asset included in one returned systematic relationship matrix.

### Factor-implied relationship formula

For valid betas and a frozen factor covariance sample:

```text
Cov_factor(i,j)  = beta_i' Sigma_F beta_j
Corr_factor(i,j) = Cov_factor(i,j) /
                   sqrt(Cov_factor(i,i) * Cov_factor(j,j))
```

This is correlation of factor-implied **systematic components**, not total-return correlation. Residual/idiosyncratic variance is not mislabelled as systematic overlap.

No raw beta-vector cosine is the official factor-overlap metric.

## 11. Economic-theme evidence

Phase 5 does not infer themes from ticker strings, unversioned current web prose or opaque LLM classification.

Usable theme evidence requires deterministic traceable provenance including, at minimum:

- source/provider;
- taxonomy/version;
- retrieval/effective date;
- per-symbol labels;
- confidence/provenance.

Until implemented:

```text
status = unavailable_no_traceable_theme_source
```

Missing theme evidence is not zero and cannot silently influence verdicts.

## 12. Redundancy verdict policy — initial `.1`

Verdicts describe **historical exposure redundancy evidence only**:

```text
HIGH
MEDIUM
LOW
UNCERTAIN
```

There is no numeric 0–100 score.

### Core evidence

Valid structural correlation and bootstrap evidence are required for HIGH/MEDIUM/LOW; otherwise verdict is `UNCERTAIN`.

### HIGH

All:

- structural correlation ≥0.80;
- same average-linkage cluster;
- same complete-linkage cluster;
- bootstrap co-cluster probability ≥0.75;
- window agreement available and ≥2/3;
- medium daily correlation available and ≥0.70.

### MEDIUM

All:

- structural correlation ≥0.65;
- same average-linkage cluster;
- bootstrap probability ≥0.60;

plus at least one **eligible available** corroborator:

- medium daily correlation ≥0.60;
- downside correlation ≥0.65;
- stress correlation ≥0.65;
- factor-implied correlation ≥0.65 when the final factor policy declares the evidence valid/eligible;
- future traceable shared-theme evidence.

The `.1` implementation currently treats valid factor regressions as a corroborator; M3 review must be resolved before merge so factor applicability is not inferred solely from USD quote currency.

### LOW

All:

- structural correlation ≤0.35;
- not same average-linkage cluster;
- bootstrap probability ≤0.35.

### UNCERTAIN

Everything else, including conflicting evidence, insufficient stability or missing core evidence.

These classes do not estimate replacement probability and do not imply a trade.

## 13. Confidence and provenance

Verdict and evidence confidence are separate.

Retain, where applicable:

- correlation statuses/sample counts;
- available stability-window count;
- bootstrap requested/usable replicates;
- factor sample/R-squared/scope evidence;
- theme provenance/status;
- dataset identity and clustering methodology version.

Initial `.1` confidence summary:

- HIGH: 3 stability windows, ≥190 usable bootstrap replicates, valid core correlation views;
- MEDIUM: ≥2 windows, ≥160 usable replicates, valid structural/medium views;
- LOW: otherwise.

Confidence is evidence completeness/stability, not a probability that a stock should be removed.

## 14. Asset / cluster summaries

Permitted convenience summaries:

### Cluster

- canonical cluster ID/members/count;
- min/mean/max within-cluster structural correlation;
- mean bootstrap pair stability when applicable;
- complete-linkage sensitivity agreement.

### Asset neighborhood

Pair peers may be grouped/sorted by descriptive verdict/evidence, but this is not a stock ranking or replacement list.

## 15. Public API extension

Phase 5 extends successful `refinery-v1` analyze responses with:

```text
analysis.clustering
analysis.redundancy
analysis.factor_relationships
analysis.theme_relationships
```

No second candidate-data fetch and no browser-side research engine is created.

Existing Phase 3/4 fields remain backward compatible. The API request contract remains `refinery-v1`; additive public response fields are governed by the Refinery API schema version.

## 16. Resource bounds

```text
MAX_CLUSTER_ASSETS      = 100
BOOTSTRAP_REPLICATES    = 200
BOOTSTRAP_BLOCK_WEEKS   = 4
MAX_PAIR_ROWS           = 4,950
```

All evidence must still satisfy the Refinery 4 MiB canonical response guard. Backend fails closed rather than silently dropping candidate/pair evidence. UI presentation may bound mounted DOM while preserving API semantics.

## 17. UI semantics

Phase 5 read-only panels:

1. `群聚結構`
2. `重複曝險證據`
3. `因子關係`
4. `主題關係`

Rules:

- no TypeScript recomputation of linkage/verdicts;
- no HIGH-as-sell presentation;
- expose methodology version/cut/bootstrap parameters;
- deterministic bounded presentation for large pair sets;
- no page-level mobile overflow;
- preserve existing Phase 4 diagnostics.

## 18. Required pure-math / methodology tests

Initial and convergence gates include:

1. correlation-distance symmetry/zero diagonal/[0,1] bound;
2. request/column permutation -> equivalent canonical hierarchy/evidence;
3. perfect duplicates distance zero / co-cluster;
4. perfect anticorrelation distance one;
5. identity correlation off-diagonal `sqrt(1/2)`;
6. average/complete fixtures match SciPy on canonical condensed distances;
7. Ward not accepted as V1 method;
8. bootstrap deterministic under the frozen structural seed identity;
9. bootstrap joint row resampling;
10. unusable replicates explicitly counted;
11. unavailable windows excluded from agreement denominator;
12. verdict order-independent; missing evidence never becomes zero;
13. factor-implied matrix matches independent fixture on the **same frozen sample**;
14. incomplete first/last factor months excluded under the final complete-month policy;
15. factor diagnostic availability separated from corroboration eligibility under the final scope policy;
16. insufficient/non-computable factor evidence fails closed;
17. theme evidence unavailable without traceable source.

## 19. Required API/regression gates

Before merge:

1. incomplete candidate membership blocks formal analysis;
2. benchmark failure only removes benchmark-conditioned corroboration;
3. no-weight analysis remains valid structurally without equal-weight fabrication;
4. candidate permutation produces equivalent labelled Phase 5 evidence;
5. deterministic repeat requests match under same frozen input/contract;
6. API schema/methodology versions match code/docs;
7. response-size/canonical JSON guards pass;
8. existing Phase 3/4 fields remain regression-compatible;
9. Worker security/routing behavior remains unchanged unless separately reviewed;
10. existing Portfolio/Scanner/Exhaustive tests pass;
11. M1–M4 convergence tests pass.

## 20. Required browser gates

- existing Portfolio flow unchanged;
- Phase 4 Refinery flow unchanged;
- cluster/stability/sensitivity panels;
- all four descriptive redundancy verdict classes without recommendation labels;
- factor diagnostic/scope/unavailable states;
- explicit unavailable theme state;
- >20 / 100-candidate bounded presentation;
- 390px no page-level horizontal overflow.

## 21. Merge gate

Phase 5 is not merge-ready until:

- M1–M4 are resolved and the accepted methodology version is frozen;
- code/constants/docs/tests/API/UI evidence align;
- full CI + focused web CI pass;
- Vercel required status is actually green on final exact head;
- backup gate passes;
- dependency vulnerability signal is triaged/classified;
- independent final exact-head review is recorded;
- `to_do_update_list.md` is current.

## 22. Explicit non-goals

Phase 5 does not implement:

- KEEP / TRIM / REPLACE;
- stock action ranking/selection;
- Remove-One / Add-One / Replace-One;
- position sizing / ERC / HRP / minimum variance;
- Exhaustive candidate selection;
- future-return alpha claims;
- OOS/walk-forward validation;
- point-in-time Universe/fundamental claims;
- untraceable automatic economic-theme classification.
