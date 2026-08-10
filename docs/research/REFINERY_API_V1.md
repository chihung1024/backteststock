# Portfolio Refinery Read-only API V1

Status: **Phase 3 baseline contract with Phase 5 additive analysis-schema extension**. The request contract remains `refinery-v1`; Phase 5 adds read-only clustering/redundancy/factor/theme evidence to successful `analyze` responses without changing the request shape or Portfolio v3 ledger semantics.

Current Phase 5 implementation is still under final review. Clustering/factor methodology is governed by `REFINERY_CLUSTERING_V1.md` plus the active `PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md`; this API document defines transport/schema/fail-closed semantics, not the statistical thresholds themselves.

## Contract identity

```text
REFINERY_API_CONTRACT_VERSION = refinery-v1
REFINERY_API_SCHEMA_VERSION   = refinery-v1-2026-08-10.2
```

Historical note: Phase 3 originally shipped schema `refinery-v1-2026-08-09.1`. The `.2` schema is an additive response extension on the Phase 5 branch; the request contract is unchanged.

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
- `ewma_decay`: covariance sensitivity parameter, default `0.94`, strictly between 0 and 1
- `stress_quantile`: lower-tail benchmark quantile, default `0.10`, allowed `[0.05, 0.25]`

Phase 5 introduces **no new request fields**. Clustering/redundancy/factor/theme evidence is derived from the same audited request/data boundary.

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
MAX_HISTORY_CALENDAR_DAYS      = 15 × 366
```

Backend rate limiting is best-effort/in-process, not a globally distributed quota. The Worker also enforces body size and fixed route/method allowlists before proxying.

Responses use `Cache-Control: no-store`. Authorization/cookie headers are not required and are not forwarded through the Refinery edge path. Backend/server/set-cookie disclosure is stripped at the edge.

Phase 5 pair evidence must still fit the same 4 MiB canonical-response guard. The API may not silently truncate requested candidate membership or pair evidence to fit the limit; oversize output fails closed.

## 3. One market-data fetch, reproducible views

The Refinery performs one authoritative `TWDHistoryService.histories_partial()` call over candidate symbols plus an optional distinct benchmark.

From that audited batch it constructs:

1. **candidate ResearchDataset** — candidate-only data used for covariance/correlation/risk/clustering/redundancy;
2. **benchmark ResearchDataset** — optional one-symbol reproducibility view for benchmark-conditioned diagnostics.

Changing/adding a benchmark must not change the candidate complete-case calendar or candidate covariance/correlation/clustering sample.

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

Schema `.2` may add these read-only sections under `analysis`:

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

The active Phase 5 review is tightening complete-month/common-sample/applicability semantics. Until those amendments are implemented and versioned, this section is **under final methodology review** and must not be interpreted beyond the current labelled evidence.

### `analysis.theme_relationships`

Carries traceable theme evidence only when a deterministic approved source exists. Current Phase 5 behavior may explicitly return `unavailable_no_traceable_theme_source`.

## 9. Methodology metadata

The response `methodology` object is the user/audit-visible bridge between schema and quantitative contracts. It must expose applicable contract versions and critical consumer policies.

Rules:

- API schema version and clustering methodology version are separate identities;
- changing a quantitative methodology semantic does not silently reuse an old clustering version;
- adding externally visible response fields requires API schema-version review;
- browser code may display methodology but must not redefine it.

## 10. Deterministic serialization

Successful/diagnostic payloads use canonical JSON semantics:

```text
UTF-8
sort_keys=True
separators=(",", ":")
allow_nan=False
```

NumPy/Pandas scalar values are normalized to JSON-safe primitives. Contract-approved unavailable analytical values are represented as `null`, not numeric zero.

Public API does not return raw daily price arrays or full ResearchDataset exports.

## 11. Error and security behavior

Validation errors are sanitized/stable. Unexpected exceptions are logged server-side and produce generic 500 responses without stack trace or environment leakage.

All Refinery responses include the established no-store/security headers, including:

- `Cache-Control: no-store`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `X-Refinery-API-Schema-Version`
- `X-Request-Id` when available

CORS remains limited to reviewed self-owned origins.

## 12. Explicit non-goals through Phase 5

The API does not implement:

- BUY / SELL / KEEP / TRIM / REPLACE;
- stock action ranking/selection;
- position sizing;
- HRP/ERC/minimum-variance optimization;
- Leave-One-Out/Add-One/Replace-One experiments;
- Exhaustive candidate selection;
- OOS/walk-forward claims;
- Portfolio v3 ledger migration;
- untraceable economic-theme classification.

Phase 5 clustering/redundancy is historical descriptive evidence only.

## 13. Validation gates

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
- additive schema `.2` remains backward compatible for existing Phase 3/4 fields;
- incomplete membership still yields `analysis=null`;
- benchmark failure cannot fabricate downside/stress evidence;
- candidate permutation preserves equivalent labelled clustering evidence;
- response-size guard covers maximum pair output;
- factor unavailable/applicability states are explicit;
- theme unavailable state is explicit;
- server output, UI types and methodology fields agree;
- full CI/Vercel/backup/independent exact-head review pass;
- `to_do_update_list.md` records exact final evidence before merge and phase closeout.
