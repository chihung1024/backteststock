# Portfolio Refinery Contract

Status: **Current production read-only Refinery contract, including clustering/redundancy diagnostics and opt-in marginal structural experiments.**

This document consolidates the former API, clustering and UI phase documents. Refinery remains a diagnostic/research domain, not a stock-action recommendation or portfolio-construction authority.

## 1. Public surface and authority boundary

Runtime:

```text
POST /api/v1/refinery/preflight
POST /api/v1/refinery/analyze
```

Current implementation constants include:

```text
REFINERY_API_CONTRACT_VERSION = refinery-v1
REFINERY_API_SCHEMA_VERSION = refinery-v1-2026-08-10.3
PHASE6_MARGINAL_CONTRACT_VERSION = refinery-phase6-marginal-v1-2026-08-13.1
```

Authorities:

- market data / FX / TWD valuation: shared `TWDHistoryService`;
- reproducible aligned evidence: `ResearchDataset`;
- pure covariance/correlation/risk/clustering math: `apps/api/app/quant/`;
- evidence composition and descriptive policy: `apps/api/app/refinery/`;
- public HTTP contract: `api/refinery_v1.py`;
- browser: request editing and rendering only.

Portfolio v3 remains a separate path-dependent ledger domain. Refinery does not become another Portfolio engine.

## 2. Request and resource boundaries

Base request requires:

- `contract_version = "refinery-v1"`;
- 2–100 unique candidate symbols;
- start/end dates.

Optional inputs include benchmark, explicit candidate weights, EWMA decay, stress quantile and an explicit marginal `experiment_plan`.

Current resource constants in code include:

```text
MAX_CANDIDATE_SYMBOLS = 100
MAX_EXPERIMENT_OPERATIONS = 12
MAX_EXPERIMENT_UNION_SYMBOLS = 24
MAX_HISTORY_CALENDAR_DAYS = 15 * 366
MAX_REQUEST_BYTES = 512 KiB
MAX_RESPONSE_BYTES = 4 MiB
GENERAL_REQUESTS_PER_MINUTE = 20
ANALYZE_REQUESTS_PER_MINUTE = 4
```

The code is authoritative for exact bounds.

No hidden Equal Weight is created when weights are omitted. Portfolio-specific risk contribution metrics remain unavailable without explicit weights.

## 3. One market-data fetch and reproducible views

One authoritative history request covers the baseline candidates, optional distinct benchmark and any explicitly requested external experiment symbols.

From that audited history batch Refinery may derive:

- candidate ResearchDataset;
- optional benchmark ResearchDataset;
- optional experiment-union ResearchDataset.

These are views of one audited data authority, not independent downloaders.

Changing benchmark or experiment-only symbols must not silently change the baseline candidate sample.

## 4. Fail-closed membership/data semantics

If any requested candidate is unresolved:

- top-level state is incomplete;
- explicit failure evidence remains visible;
- formal candidate analysis is not run on a silently reduced subset.

If complete-case evidence is insufficient, formal analysis is unavailable rather than numerically fabricated.

A failed optional benchmark may disable benchmark-conditioned diagnostics without invalidating otherwise valid candidate structural analysis.

Unavailable analytical values are `null`/explicit unavailable states, not zero.

## 5. Current reliability policy

Current code uses the following consumer bounds:

```text
MIN_DAILY_ANALYSIS_OBSERVATIONS = 60
TACTICAL_MIN_OBSERVATIONS = 40
MEDIUM_MIN_OBSERVATIONS = 120
STRUCTURAL_MIN_OBSERVATIONS = 52
CONDITIONAL_MIN_OBSERVATIONS = 20
DAILY_COVARIANCE_ANNUALIZATION = 252
```

These are versioned product policies, not universal statistical constants.

## 6. Baseline risk/correlation evidence

When eligible, Refinery may expose:

- reproducibility and dataset identities;
- Ledoit-Wolf formal covariance;
- sample/EWMA sensitivity diagnostics;
- covariance/correlation effective dimensions;
- signed risk-contribution evidence when explicit weights exist;
- Diversification Ratio when applicable;
- tactical, medium, structural, downside and stress correlation views.

The browser displays returned evidence but does not recalculate the matrices or portfolio metrics.

## 7. Structural clustering

Primary structural input is synchronized weekly TWD returns from the existing `ResearchDataset`.

Correlation distance:

```text
d_ij = sqrt((1 - rho_ij) / 2)
```

Current methodology:

```text
primary linkage = average
sensitivity linkage = complete
flat display cut = 0.50
stability windows = 52 / 104 / 156 weeks
bootstrap replicates = 200
bootstrap block = 4 weeks
```

Symbols are canonicalized before numerical clustering. Public cluster identity must be deterministic from member sets rather than unstable library-generated labels.

Invalid correlation inputs fail closed rather than being silently repaired beyond floating-point clipping.

## 8. Stability and bootstrap identity

Multi-window stability reports available same-cluster evidence; unavailable windows are excluded rather than counted as disagreement.

Bootstrap uses joint moving-block resampling of the exact prepared weekly sample. Its deterministic seed/fingerprint binds the effective symbols, timestamps, values and methodology parameters.

`ResearchDataset.dataset_hash` remains the full dataset identity and is not repurposed as a bootstrap input fingerprint.

Unusable bootstrap replicates are explicitly counted.

## 9. Factor relationship evidence

Factor evidence is a scoped diagnostic, not automatically a valid redundancy corroborator.

Current design separates:

- `factor_computable`;
- model scope;
- `factor_corroboration_eligible`.

The factor adapter uses traceable Kenneth French monthly data and native-currency asset returns. Boundary months that cannot be proven complete are excluded. Returned systematic relationship evidence uses one exact global common monthly sample rather than switching samples pair by pair.

Without traceable instrument-scope authority, factor evidence remains visible as a diagnostic but fails closed for redundancy-verdict corroboration.

Theme evidence likewise remains unavailable unless deterministic traceable taxonomy/provenance exists; ticker-string or opaque LLM classification is not authority.

## 10. Descriptive redundancy verdict

Pair verdicts are:

```text
HIGH
MEDIUM
LOW
UNCERTAIN
```

They describe historical exposure redundancy evidence only.

There is no 0–100 magic score and no implicit KEEP/TRIM/REPLACE action.

Current high/medium/low policy combines structural correlation, cluster membership, stability/bootstrap and eligible corroborators under versioned thresholds. Missing core evidence produces `UNCERTAIN`, not a made-up numeric score.

Confidence describes evidence completeness/stability, not a probability that a holding should be removed.

## 11. Explicit marginal experiments

The optional experiment plan accepts only explicit:

```text
remove_one
add_one
replace_one
```

operations.

Rules:

- at most the code-defined operation/union bounds;
- never generate an implicit Cartesian experiment set;
- reuse one already-fetched union history;
- freeze common daily/weekly samples across baseline and variants;
- each variant selects columns from the frozen sample rather than realigning independently;
- experiment-layer failure does not destroy an independently valid baseline response;
- output is descriptive baseline/variant/delta evidence only.

The layer does not rank experiments, choose a winner, infer allocation, recommend a trade or make an OOS claim.

## 12. Deterministic serialization and security

Successful/diagnostic payloads use deterministic JSON semantics and do not emit NaN as valid numeric evidence.

Refinery responses are `no-store`, carry the established security headers and stable request-id/schema metadata. Errors are sanitized; unexpected exceptions are logged server-side without exposing stack traces/environment variables.

The Worker exposes only reviewed same-origin routes/methods; browser code does not call foreign market/factor/theme origins directly.

## 13. UI and persistence boundary

Refinery state persists independently from Portfolio state. Switching workspace changes workflow/presentation but does not copy a Portfolio into Refinery or vice versa.

The UI may:

- edit candidate/date/benchmark/weights and supported advanced parameters;
- collect explicit page-scoped marginal operations;
- preflight and analyze;
- show data confidence, matrices, clustering, pair evidence, factor/theme states and marginal deltas;
- use bounded/scrollable presentation for large matrices/tables.

It must not:

- calculate clustering or redundancy verdicts;
- create a recommendation from HIGH/MEDIUM/LOW;
- rank marginal experiments into a purported winner;
- run a browser covariance/Portfolio/selection engine;
- convert unavailable evidence to zero;
- create hidden cross-workspace state.

Large-result rendering guards are presentation-only and must not change server evidence semantics.

## 14. Explicit non-goals

Refinery does not currently own:

- BUY / SELL / KEEP / TRIM / REPLACE recommendations;
- stock action ranking/selection;
- position sizing;
- HRP/ERC/minimum-variance optimizer output for the user;
- Exhaustive candidate selection;
- causal OOS/Walk-Forward performance claims;
- untraceable automatic theme classification.

A future transition from diagnosis to recommendation requires its own causally validated methodology, not a UI reinterpretation of current descriptive evidence.

## 15. Verification invariant

Keep regression coverage for:

- complete requested membership or explicit failure;
- no hidden equal weight;
- benchmark isolation;
- covariance/risk parity with shared quant authorities;
- clustering determinism and bootstrap identity;
- factor common-sample/applicability semantics;
- explicit unavailable theme evidence;
- deterministic serialization and response/resource guards;
- UI rendering without browser quantitative authority;
- explicit experiment operation/order/sample invariance;
- baseline parity when no experiment plan is supplied.

Code/tests supersede stale prose if drift is discovered.
