# Portfolio Refinery Read-only API V1

Status: **Current read-only Refinery contract: Phase 3–5 baseline plus the opt-in Phase 6 marginal structural-experiment layer. Phase 6 remains candidate-validation work until its exact branch/CI/deployment gates pass.**

Corrected Phase 5 clustering/factor semantics are governed by `REFINERY_CLUSTERING_V1.md`; `PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md` records resolved M1–M4 findings and remaining release gates.

## Contract identity

```text
REFINERY_API_CONTRACT_VERSION = refinery-v1
REFINERY_API_SCHEMA_VERSION   = refinery-v1-2026-08-10.3
PHASE6_MARGINAL_CONTRACT_VERSION = refinery-phase6-marginal-v1-2026-08-13.1
```

Historical note: Phase 3 shipped `refinery-v1-2026-08-09.1`; the initial Phase 5 draft used `refinery-v1-2026-08-10.2`. Corrected M1–M4 public evidence semantics are versioned as `refinery-v1-2026-08-10.3`. The request contract remains `refinery-v1`.

`REFINERY_API_SCHEMA_VERSION` continues to identify the established Phase 3–5 envelope. When `experiment_plan` is absent, its serialized request/response semantics remain exactly that envelope. Phase 6 is an optional additive layer with its own public contract identity; changing its visible semantics requires a `PHASE6_MARGINAL_CONTRACT_VERSION` review rather than silently reusing the old layer.

Runtime boundary:

```text
Vercel entrypoint: api/refinery_v1.py
Edge prefix:       /api/v1/refinery/
Allowed routes:
  POST /api/v1/refinery/preflight
  POST /api/v1/refinery/analyze
```

Unknown Refinery paths fail closed with 404 and unsupported methods with 405. The Worker exposes no wildcard Refinery backend surface.

## 1. Request contract

Required:

- `contract_version = "refinery-v1"`
- `symbols`: 2–100 unique normalized candidate symbols
- `start_date`
- `end_date`

Optional:

- `benchmark`: one normalized symbol used for benchmark-conditioned downside/stress evidence
- `weights`: explicit candidate weights in percent; every candidate exactly once; total 100% within ±0.05 percentage point
- `experiment_plan`: one to twelve explicit operations, each exactly one of `remove_one`, `add_one`, or `replace_one`
- `ewma_decay`: covariance sensitivity parameter, default `0.94`, strictly between 0 and 1
- `stress_quantile`: lower-tail benchmark quantile, default `0.10`, allowed `[0.05, 0.25]`

`experiment_plan` is opt-in. Every operation is normalized through the established symbol authority; removals must be baseline candidates, additions must be external to the baseline, and normalized duplicate operations fail closed. The plan never expands into an implicit Cartesian set. A removal must retain at least two candidates.

Phase 5 introduced no request fields. Its clustering/redundancy/factor/theme evidence and the Phase 6 layer are derived from the same audited request/data boundary.

No equal-weight assumption is created when `weights` is omitted. Portfolio-specific volatility/MRC/RC/DR/weight-effective metrics remain unavailable while structural diagnostics can still be emitted.

Accepted weight totals within tolerance are proportionally normalized to exact unit sum for Phase 2 risk mathematics. Raw percentages, raw input total and normalization policy remain visible. This is numerical normalization, not sizing or optimization.

`start_date < end_date`; `end_date` may not be future; requested span is capped at 15 × 366 calendar days. Symbol normalization reuses `apps.api.app.data.history_service.normalize_symbol`.

## 2. Resource and abuse boundaries

```text
MAX_REQUEST_BYTES              = 512 KiB
API_TIMEOUT_MS                 = 240,000 ms at Worker
GENERAL_REQUESTS_PER_MINUTE    = 20 per backend instance/client key
ANALYZE_REQUESTS_PER_MINUTE    = 4 per backend instance/client key
MAX_RESPONSE_BYTES             = 4 MiB canonical JSON
MAX_CANDIDATE_SYMBOLS          = 100
MAX_EXPERIMENT_OPERATIONS       = 12
MAX_EXPERIMENT_UNION_SYMBOLS    = 24
MAX_HISTORY_CALENDAR_DAYS      = 15 × 366
```

Backend rate limiting remains a per-instance overload brake. The Worker adds
authenticated client identity plus Cloudflare Rate Limiting bindings, body
size enforcement, and fixed route/method allowlists before proxying. The edge
counters are distributed across isolates within a Cloudflare location but are
per-location and eventually consistent, not an accounting-grade global quota.
Protected production origin requests without the Worker service credential
fail closed.

Responses use `Cache-Control: no-store`. Authorization/cookie headers are not required and are not forwarded through the Refinery edge path. Backend/server/set-cookie disclosure is stripped at the edge.

Phase 5 pair evidence must still fit the same 4 MiB canonical-response guard. The API may not silently truncate requested candidate membership or pair evidence to fit the limit; oversize output fails closed.

Phase 6 applies both caps before expensive work. The union is the baseline candidates plus unique external Add/Replace symbols; benchmark membership is separate. The minimal V1 result also bounds per-operation pair-impact evidence to `2 × (24 - 1) = 46` pairs.

## 3. One market-data fetch, reproducible views

The Refinery performs one authoritative `TWDHistoryService.histories_partial()` call over baseline candidates, any Phase 6 external experiment symbols, and an optional distinct benchmark.

From that audited batch it constructs:

1. **candidate ResearchDataset** — candidate-only data used for covariance/correlation/risk/clustering/redundancy;
2. **benchmark ResearchDataset** — optional one-symbol reproducibility view for benchmark-conditioned diagnostics.
3. **experiment-union ResearchDataset** — only when `experiment_plan` is present; built from the already fetched union histories and used to freeze the Phase 6 samples.

Changing/adding a benchmark must not change the candidate complete-case calendar or candidate covariance/correlation/clustering sample. Phase 6 external symbols likewise do not change the Phase 3–5 baseline sample; they affect only the explicitly requested marginal layer.

The Refinery is not a market-data downloader. `TWDHistoryService` remains data/FX authority; `ResearchDatasetV1` remains alignment/membership/reproducibility authority.

## 4. Partial data and fail-closed analysis

`preflight` may return partial evidence with explicit per-symbol failures.

Resolved-symbol observation counts in a partial preflight are descriptive only and do not redefine requested membership.

If any requested **candidate** is unresolved:

- top-level status is `incomplete`;
- requested/resolved/failure evidence is returned;
- descriptive resolved-evidence counts may be returned;
- `analysis = null`;
- no Phase 2/5 formal analysis is computed on a silently reduced candidate set.

A failed optional benchmark does not invalidate candidate structural analysis. It makes benchmark-conditioned downside/stress evidence explicitly unavailable while preserving benchmark failure evidence.

If candidate membership is complete but required complete-case history is insufficient, status is `insufficient_data` and formal analysis is not emitted.

## 5. Versioned reliability policy

```text
MIN_DAILY_ANALYSIS_OBSERVATIONS = 60
TACTICAL_DAILY_WINDOW            = 63
TACTICAL_MIN_OBSERVATIONS        = 40
MEDIUM_DAILY_WINDOW              = 252
MEDIUM_MIN_OBSERVATIONS          = 120
STRUCTURAL_WEEKLY_WINDOW         = 156
STRUCTURAL_MIN_OBSERVATIONS      = 52
CONDITIONAL_MIN_OBSERVATIONS     = 20
DAILY_COVARIANCE_ANNUALIZATION   = 252
```

These are consumer policies, not universal statistical constants.

Phase 5 clustering has additional versioned methodology parameters (linkage, cut, stability windows, bootstrap policy, factor/theme evidence rules) defined in `REFINERY_CLUSTERING_V1.md`.

## 6. `preflight` response

`POST /api/v1/refinery/preflight` remains a readiness/reproducibility endpoint. Phase 5 does not turn preflight into a recommendation or hidden analysis call.

It includes:

- API contract/schema versions;
- ResearchDataset/Risk Mathematics versions;
- normalized candidate/benchmark/date/weight input state;
- raw weight total and normalization policy when supplied;
- candidate and optional benchmark dataset hashes;
- requested/resolved membership;
- per-symbol failures;
- effective dates;
- reference/common observation counts;
- coverage/audit/fingerprint evidence;
- analysis eligibility and explicit reasons.

When `experiment_plan` is present, it additionally carries `marginal_experiments` readiness only: union membership/failures, the frozen daily/weekly common-sample identities, eligibility/reasons and Phase 6 methodology. `preflight` never emits experiment snapshots, deltas or a preferred operation.

Statuses remain `ready`, `incomplete`, or `insufficient_data`.

## 7. `analyze` response — Phase 3/4 baseline

When candidate data are complete/sufficient, existing fields remain backward compatible.

### Reproducibility

- all preflight evidence;
- candidate/benchmark dataset identities;
- API/ResearchDataset/Risk Mathematics versions;
- covariance annualization, EWMA decay, stress quantile and observation guards.

### Covariance diagnostics

Daily candidate returns:

- Ledoit-Wolf annualized covariance as primary formal estimator;
- sample covariance as diagnostic;
- EWMA as sensitivity diagnostic;
- per-estimator observations/method/numerical diagnostics;
- shrinkage coefficient;
- pairwise estimator-dispersion diagnostics.

### Structural dimensions

- covariance entropy effective rank;
- covariance participation ratio;
- medium-correlation entropy effective rank;
- medium-correlation participation ratio.

These are structural diagnostics, not an exact count of independent economic bets.

### Portfolio risk — only with explicit weights

- normalized weights actually used;
- annualized variance/volatility;
- marginal risk contribution;
- signed component risk contribution;
- Diversification Ratio;
- weight-effective holdings;
- gross absolute-RC equivalent holdings.

Negative hedge RC remains signed.

### Correlation views

- tactical daily;
- medium daily;
- structural synchronized weekly;
- downside benchmark-negative;
- benchmark lower-tail stress.

Each carries explicit status, input/effective/dropped observations, condition/window/threshold and matrix only when available.

## 8. `analyze` response — Phase 5 additive sections

Schema `.3` adds these read-only sections under `analysis`:

```text
analysis.clustering
analysis.redundancy
analysis.factor_relationships
analysis.theme_relationships
```

### `analysis.clustering`

Carries server-authoritative labelled hierarchy/membership and stability evidence, including methodology version, primary/sensitivity linkage, display cut, multi-window evidence, bootstrap evidence and cluster summaries when available.

The API returns labelled data so the browser never infers semantics from raw matrix position or recomputes linkage.

### `analysis.redundancy`

Carries unordered pair evidence, descriptive verdict (`HIGH|MEDIUM|LOW|UNCERTAIN`), evidence confidence and the underlying price/stability/factor/theme corroborators/statuses.

No numeric magic score and no KEEP/TRIM/REPLACE action is introduced.

### `analysis.factor_relationships`

Carries explicitly scoped factor diagnostic evidence, source/sample/provenance, per-asset regression evidence and factor-implied relationship evidence when valid under the versioned Phase 5 methodology.

Corrected factor evidence uses boundary-month exclusion, one global common relationship sample, and explicit computability/model-scope/corroboration-eligibility states. Computable diagnostics remain visible, but factor evidence is fail-closed for verdict corroboration without traceable instrument-scope authority.

### `analysis.theme_relationships`

Carries traceable theme evidence only when a deterministic approved source exists. Current Phase 5 behavior may explicitly return `unavailable_no_traceable_theme_source`.

## 9. `analyze` response — Phase 6 optional marginal layer

When and only when `experiment_plan` is present, the response adds the top-level `marginal_experiments` object. The existing Phase 3–5 `analysis` stays the requested baseline analysis; Phase 6 must never replace it with a union or variant calculation.

The layer exposes:

- `status`, eligibility reasons and experiment-only membership failures, isolated from a valid baseline;
- `common_sample.experiment_union_dataset_hash` for full union provenance, separately from daily/weekly frozen effective-sample SHA-256 identities;
- one `experiment_baseline` and ordered `results`, all evaluated on the same frozen daily and weekly full-union complete-case matrices;
- each explicit operation, its resulting symbols, Ledoit-Wolf/effective-dimension/correlation/point-clustering snapshots, descriptive baseline/variant/delta fields, and changed-pair evidence;
- executable shared-pair invariance evidence with tolerance `1e-12`.

Variants select columns from the frozen matrices only; they never re-align or re-`dropna()` data per operation. Minimal V1 uses unweighted structural snapshots, does not infer allocations, and does not run the Phase 5 bootstrap/redundancy verdict per variant. Insufficient union data or experiment-only fetch failure makes this layer unavailable/incomplete while retaining the independently valid baseline response.

The layer is an in-sample historical structural diagnostic, not OOS validation, a ranking, a recommendation, selection, or sizing engine.

## 10. Methodology metadata

The response `methodology` object is the user/audit-visible bridge between schema and quantitative contracts. It must expose applicable contract versions and critical consumer policies.

Rules:

- API schema version, Phase 5 clustering methodology version and optional Phase 6 marginal contract version are separate identities;
- changing a quantitative methodology semantic does not silently reuse an old clustering version;
- adding externally visible Phase 3–5 envelope fields requires API schema-version review; changing the opt-in Phase 6 layer requires its own contract-version review;
- browser code may display methodology but must not redefine it.

## 11. Deterministic serialization

Successful/diagnostic payloads use canonical JSON semantics:

```text
UTF-8
sort_keys=True
separators=(",", ":")
allow_nan=False
```

NumPy/Pandas scalar values are normalized to JSON-safe primitives. Contract-approved unavailable analytical values are represented as `null`, not numeric zero.

Public API does not return raw daily price arrays or full ResearchDataset exports.

## 12. Error and security behavior

Validation errors are sanitized/stable. Unexpected exceptions are logged server-side and produce generic 500 responses without stack trace or environment leakage.

All Refinery responses include the established no-store/security headers, including:

- `Cache-Control: no-store`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `X-Refinery-API-Schema-Version`
- `X-Request-Id` when available

CORS remains limited to reviewed self-owned origins.

## 13. Explicit non-goals through Phase 6

The API does not implement:

- BUY / SELL / KEEP / TRIM / REPLACE;
- stock action ranking/selection;
- position sizing;
- HRP/ERC/minimum-variance optimization;
- Exhaustive candidate selection;
- OOS/walk-forward claims;
- Portfolio v3 ledger migration;
- untraceable economic-theme classification.

Phase 5 clustering/redundancy and Phase 6 marginal experiments are historical descriptive evidence only.

## 14. Validation gates

### Baseline Phase 3/4 invariants

- request normalization/uniqueness/date/weight/resource tests;
- one-fetch candidate/benchmark separation;
- candidate partial data blocks formal analysis;
- benchmark failure only disables conditional evidence;
- no hidden equal weights;
- traceable weight normalization;
- covariance/risk parity with Phase 2 primitives;
- deterministic serialization;
- request/response/security/rate/error guards;
- Worker route/header/method/body guards;
- existing Portfolio/Scanner/Exhaustive regressions.

### Phase 5 additive gates

Before Phase 5 merge:

- clustering/factor methodology contract and implementation versions align;
- corrected additive schema `.3` remains backward compatible for existing Phase 3/4 fields;
- incomplete membership still yields `analysis=null`;
- benchmark failure cannot fabricate downside/stress evidence;
- candidate permutation preserves equivalent labelled clustering evidence;
- response-size guard covers maximum pair output;
- factor unavailable/applicability states are explicit;
- theme unavailable state is explicit;
- server output, UI types and methodology fields agree;
- full CI/Vercel/backup/independent exact-head review pass;
- `to_do_update_list.md` records exact final evidence before merge and phase closeout.

### Phase 6 additive gates

- no-plan requests are exact Phase 3–5 parity;
- request validation rejects invalid shapes, normalized duplicates, invalid membership and both resource caps;
- one union market-history fetch is reused for baseline and marginal preparation;
- direct recomposition of each Remove-One/Add-One/Replace-One variant matches frozen-sample primitives and stable IDs;
- frozen daily/weekly sample identities remain distinct from union dataset provenance;
- failed experiment-only data and insufficient frozen samples fail only the marginal layer closed;
- shared retained-pair correlations remain invariant on the frozen sample;
- UI uses only the established preflight/analyze routes, preserves requested operation order and has no browser quantitative/ranking authority;
- source/type/build, focused and broad regression, browser E2E, candidate CI/Vercel/backup and independent exact-head review pass before merge.
