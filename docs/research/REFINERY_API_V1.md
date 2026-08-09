# Portfolio Refinery Read-only API V1

Status: Phase 3 contract. This API exposes Phase 1 `ResearchDatasetV1` and Phase 2 `Risk Mathematics V1` for deterministic diagnosis only. It does not select, rank, size, recommend, cluster, or optimize securities.

## Contract identity

```text
REFINERY_API_CONTRACT_VERSION = refinery-v1
REFINERY_API_SCHEMA_VERSION   = refinery-v1-2026-08-09.1
```

Runtime boundary:

```text
Vercel entrypoint: api/refinery_v1.py
Edge prefix:       /api/v1/refinery/
Allowed routes:
  POST /api/v1/refinery/preflight
  POST /api/v1/refinery/analyze
```

No wildcard backend surface is exposed through the Worker. Unknown Refinery paths fail closed with 404 and wrong methods with 405.

## 1. Request contract

Required:

- `contract_version = "refinery-v1"`
- `symbols`: 2–100 unique normalized candidate symbols
- `start_date`
- `end_date`

Optional:

- `benchmark`: one normalized symbol used only for downside/stress conditioning
- `weights`: explicit candidate weights in percent; if supplied, every candidate must appear exactly once and total 100% within 0.05 percentage point
- `ewma_decay`: explicit covariance sensitivity policy, default `0.94`, finite and strictly between 0 and 1
- `stress_quantile`: benchmark lower-tail quantile, default `0.10`, allowed `[0.05, 0.25]`

No equal-weight assumption is made when `weights` is omitted. Portfolio-specific volatility/MRC/RC/DR/weight-effective metrics are then returned as unavailable, while structural covariance/correlation diagnostics may still be produced.

`end_date` may not be in the future. `start_date < end_date`. The requested span is capped at 15 × 366 calendar days as a Phase 3 resource budget, not as a claim about the statistically optimal history length.

Taiwan numeric shorthand and all symbol normalization reuse `apps.api.app.data.history_service.normalize_symbol`; the Refinery must not create a second ticker-normalization rule.

## 2. Resource and abuse boundaries

Phase 3 reuses the proven Portfolio v3 edge/runtime class rather than the Exhaustive snapshot exception:

```text
MAX_REQUEST_BYTES              = 512 KiB
API_TIMEOUT_MS                 = 240,000 ms at Worker
GENERAL_REQUESTS_PER_MINUTE    = 20 per backend instance/client key
ANALYZE_REQUESTS_PER_MINUTE    = 4 per backend instance/client key
MAX_RESPONSE_BYTES             = 4 MiB canonical JSON
MAX_CANDIDATE_SYMBOLS          = 100
MAX_HISTORY_CALENDAR_DAYS      = 15 × 366
```

The rate limiter is an in-process best-effort guard, not a globally distributed quota. The Worker additionally enforces request body size and a fixed route/method allowlist before proxying.

Responses are `Cache-Control: no-store`; authorization/cookie headers are not required by this API and the edge proxy must not forward them. Backend/server/set-cookie disclosure is stripped at the edge.

## 3. One market-data fetch, two reproducible views

The Refinery performs one authoritative `TWDHistoryService.histories_partial()` request for the union of candidate symbols plus an optional distinct benchmark.

From that one audited batch it constructs:

1. **candidate ResearchDataset** — contains candidate symbols only and is the sole source for candidate covariance/correlation/risk analysis;
2. **benchmark ResearchDataset** — one-symbol reproducibility view when a distinct benchmark is supplied.

This separation is mandatory. Adding or changing a benchmark must not alter the candidate complete-case calendar or candidate covariance/correlation sample.

The Refinery does not implement a downloader. `TWDHistoryService` remains the market-data authority and `build_research_dataset()` remains the research alignment/reproducibility authority.

## 4. Partial data and fail-closed analysis

`preflight` is diagnostic and may return a partial dataset with explicit per-symbol failures.

`analyze` must never silently remove a failed candidate and calculate a smaller portfolio/universe as if the request had succeeded.

If any **candidate** is unresolved:

- HTTP response remains a deterministic diagnostic response;
- top-level status is `incomplete`;
- requested/resolved/failure evidence is returned;
- `analysis` is `null`.

A failed optional benchmark does not invalidate candidate structural analysis. Instead, benchmark-conditioned downside/stress results are explicitly unavailable with the benchmark failure evidence retained.

If candidate membership is complete but complete-case observations are below the analysis minimum, status is `insufficient_data` and formal analysis is not emitted.

## 5. Versioned reliability policy

Phase 3 V1 uses these API-level reliability/resource policies:

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

These are versioned consumer policies, not universal statistical constants. Phase 2 mathematics keeps its own minimum-observation parameters explicit.

## 6. `preflight` response

`POST /api/v1/refinery/preflight` returns only request/data readiness and reproducibility evidence. It does not calculate a portfolio recommendation.

The response includes:

- API contract/schema versions;
- ResearchDataset and Risk Mathematics contract versions;
- normalized candidate symbols, benchmark, dates and explicit weight state;
- candidate dataset hash and optional benchmark dataset hash;
- requested/resolved membership;
- per-symbol failures with stage/detail/retryable;
- effective start/end;
- reference/common observation counts;
- coverage diagnostics;
- per-asset metadata/audit/fingerprints already carried by ResearchDataset;
- analysis eligibility and explicit reasons.

`preflight` may report `ready`, `incomplete`, or `insufficient_data`.

## 7. `analyze` response

When candidate data are complete and sufficient, `POST /api/v1/refinery/analyze` returns:

### Reproducibility

- all preflight evidence;
- candidate dataset hash;
- optional benchmark dataset hash;
- API/ResearchDataset/Risk Mathematics versions;
- explicit covariance annualization, EWMA decay, stress quantile and observation guards.

### Covariance diagnostics

Daily candidate returns only:

- Ledoit-Wolf annualized covariance as the primary formal risk estimator;
- sample covariance diagnostic estimator;
- EWMA sensitivity estimator;
- per-estimator observation count/method and numerical diagnostics;
- Ledoit-Wolf shrinkage coefficient;
- pairwise estimator-dispersion diagnostics.

The API does **not** return three full covariance matrices in V1. It returns diagnostics plus the primary risk results, reducing response size and avoiding presentation of sensitivity estimators as competing official weights.

### Structural dimensions

- covariance entropy effective rank;
- covariance participation ratio;
- medium-correlation entropy effective rank;
- medium-correlation participation ratio.

These remain structural diagnostics and are not labelled an exact number of independent economic bets.

### Portfolio risk, only when explicit weights were supplied

- annualized portfolio variance and volatility;
- marginal risk contribution;
- signed component risk contribution;
- Diversification Ratio;
- weight-effective holdings;
- gross absolute-RC equivalent holdings.

Signed hedge RC remains visible. The API does not transform negative RC into a positive allocation recommendation.

### Correlation views

The response may include ordered labelled matrices for:

- tactical daily;
- medium daily;
- structural synchronized weekly;
- downside benchmark-negative;
- benchmark lower-tail stress.

Each view includes status, input/effective/dropped observations, window/condition/threshold and matrix only when Phase 2 marks it available. Missing benchmark produces an explicit unavailable API state rather than an implicit SPY assumption.

## 8. Deterministic serialization

Successful and diagnostic Refinery payloads are serialized with canonical JSON semantics:

```text
UTF-8
sort_keys=True
separators=(",", ":")
allow_nan=False
```

NumPy/Pandas scalars are converted to JSON-safe primitive values and non-finite analytical values are represented as `null` only where the contract explicitly permits unavailable diagnostics. A response exceeding `MAX_RESPONSE_BYTES` fails closed rather than being silently truncated.

The API must never include raw daily price arrays or full ResearchDataset exports in the public response.

## 9. Error and security behavior

Backend validation errors are sanitized and stable. Unexpected exceptions are logged server-side and return a generic 500 response without stack traces/environment variables.

All Refinery responses include:

- `Cache-Control: no-store`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `X-Refinery-API-Schema-Version`
- `X-Request-Id` when available

CORS allowlist matches the self-owned Portfolio v3 origins unless separately reviewed.

## 10. Explicit non-goals

Phase 3 does not implement:

- BUY / SELL / KEEP / TRIM / REPLACE;
- stock ranking or selection;
- position sizing;
- HRP/ERC/minimum-variance portfolio optimization;
- clustering or redundancy verdicts;
- factor/economic-theme overlays;
- Leave-One-Out/Add-One/Replace-One;
- Exhaustive integration;
- historical alpha claims;
- OOS/walk-forward claims;
- Portfolio v3 ledger migration;
- UI changes.

Any of those belongs to a later approved phase.

## 11. Phase 3 validation gates

Before merge:

1. request normalization/uniqueness/date/weight/resource tests pass;
2. one-fetch candidate/benchmark separation is tested;
3. candidate partial data blocks formal analysis without silent deletion;
4. benchmark failure only disables conditional diagnostics;
5. no-weight request does not fabricate equal weights;
6. covariance/risk outputs match Phase 2 primitives on synthetic fixtures;
7. deterministic repeated requests over the same injected dataset produce identical payloads;
8. request and response size guards pass;
9. rate-limit/error/security-header tests pass;
10. Worker allowlist/wrong-method/oversize/header-sanitization tests pass;
11. Vercel route/deployment-contract tests pass;
12. existing Portfolio/Scanner/Exhaustive behavior remains unchanged;
13. full CI/Vercel/backup/independent diff review pass;
14. `to_do_update_list.md` records final evidence before merge and a doc-only closeout follows.
