# ResearchDatasetV1

Status: Phase 1 implementation contract. This layer is additive and does not switch any current production consumer.

## Purpose

`ResearchDatasetV1` is the reproducible data boundary between audited TWD market histories and later research engines such as Portfolio Refinery. It consolidates calendar, coverage, return-matrix, audit, fingerprint, and export/hash semantics that were previously assembled independently around the Exhaustive research path.

The dataset is **not** a portfolio strategy, selection model, covariance estimator, or validation engine.

## Source authority

The dataset consumes `PartialTWDHistories` produced by `TWDHistoryService`. It does not implement a second Yahoo/FX downloader.

Existing source authorities remain unchanged:

- `apps/api/app/data/history_service.py` — per-symbol partial-success history service;
- `apps/api/app/data/twd_valuation.py` — native × FX -> TWD valuation;
- `apps/api/app/data/return_components.py` — TWD price/distribution/total-return decomposition;
- `apps/api/app/backtest_service.py::align_twd_price_frame()` — current daily multi-asset union-calendar alignment used for Phase 1 parity;
- `api/metrics.py::series_fingerprint()` — current canonical level-series fingerprint.

## Contract identity

```text
RESEARCH_DATASET_CONTRACT_VERSION = research-dataset-twd-2026-08-09.1
RESEARCH_DATASET_HASH_ALGORITHM    = sha256-canonical-json-v1
RESEARCH_DAILY_RETURN_POLICY       = aligned-twd-level-pct-change-exclude-opening-v1
RESEARCH_WEEKLY_POLICY             = w-fri-period-last-actual-twd-observation-v1
```

## Membership semantics

The dataset preserves three distinct concepts:

1. `requested_symbols` — normalized/deduplicated order returned by `TWDHistoryService`;
2. `resolved_symbols` — successful histories in requested order;
3. `failures` — explicit per-symbol failure objects.

A partial dataset is valid research data, but `is_complete == false`. A consumer that requires every requested symbol must reject the partial dataset explicitly. It must not silently treat the resolved subset as the original requested universe.

## Date/calendar semantics

### Reference calendar

Union of the individual successful TWD valuation calendars before complete-case alignment. It is used to audit first/last availability and coverage.

### Daily TWD level matrix

Uses the existing `align_twd_price_frame()` policy:

- union the selected TWD valuation calendars;
- forward-fill only after a previously observed value;
- never backward-fill a pre-listing/pre-data opening;
- trim opening rows until all resolved assets have a usable value.

The requested start/end dates remain stored separately from the effective matrix start/end so any shortening is visible.

### Daily TWD returns

Arithmetic `pct_change(fill_method=None)` of the aligned daily TWD level matrix, excluding the synthetic opening row. The research return matrix therefore contains actual return observations only; it does not add an opening zero observation.

### Structural weekly matrix

Daily aligned TWD levels are grouped by `W-FRI` periods and the **last actual available research date** inside each period is retained. The timestamp is not relabelled to a future Friday.

This policy is specifically intended to avoid representing a Wednesday research cutoff as if a Friday observation already existed. Phase 2 may use the resulting weekly returns for structural cross-market correlation/clustering.

## Availability and coverage

For each resolved symbol, the availability mask matches the current Exhaustive audit convention: observations are available continuously from the first real TWD valuation date through the last real TWD valuation date on the union reference calendar. Cross-market non-trading days inside that interval are valid valuation dates and are not counted as missing quotes.

Per-symbol diagnostics include:

- overall reference-calendar coverage;
- missing day count;
- first available position;
- last available position.

The dataset also reports `_global_complete_case` diagnostics across resolved symbols.

This is intentionally separate from Scanner's user-facing coverage threshold and from Exhaustive's current 98% strict acceptance policy. `ResearchDatasetV1` reports evidence; the consumer decides the acceptance threshold.

## Native / FX / TWD separation

For every resolved asset the dataset retains:

- aligned TWD levels and returns;
- per-asset native return series;
- per-asset FX-to-TWD return series;
- quote-currency metadata;
- native, FX, original TWD, and aligned-TWD level fingerprints.

These components support later diagnostic decomposition without changing the rule that TWD returns are the Taiwanese investor-risk authority.

## Audits and reproducibility

Per-asset metadata carries:

- corporate-action audit;
- FX audit;
- return-component audit;
- quote currency / raw quote currency / native price scale;
- first/last TWD history date;
- fingerprints.

Dataset-level export also carries:

- market-data contract version;
- TWD valuation contract version;
- return-components contract version;
- corporate-action policy version;
- fingerprint algorithm;
- daily/weekly calendar policies;
- requested/effective dates;
- failures and coverage.

## Deterministic hash

`dataset_hash` is SHA-256 over a canonical JSON representation of the full exportable dataset excluding the hash field itself. Dictionary keys are sorted, separators are canonical, non-finite numeric values serialize as JSON `null`, and dates are ISO strings.

The hash is intended to answer: "Are these research matrices + metadata exactly the same dataset under the same contract?"

Changing a level, failure, audit, requested membership/order, coverage/calendar output, or contract metadata changes the hash.

## Export

`ResearchDataset.export_payload()` returns a JSON-safe object containing daily/weekly TWD matrices, native/FX returns, audits, coverage, availability masks, methodology versions, and `datasetHash`.

Phase 1 does not expose this export through a public API and does not define server persistence. Later phases may serialize/compress it for durable user research snapshots after size/security review.

## Exhaustive parity boundary

Current Exhaustive production preparation remains unchanged in Phase 1.

Parity tests must prove that, for the same complete histories:

- ResearchDataset daily TWD levels equal the current Exhaustive common TWD frame;
- reference calendar and availability coverage semantics agree;
- native/FX/aligned-TWD fingerprints agree with current preparation semantics;
- requested membership is never silently reduced.

Only after parity is accepted may a later PR migrate Exhaustive to consume `ResearchDatasetV1`. Phase 1 itself does not perform that migration.

## Explicit non-goals

- No covariance estimator.
- No correlation/clustering.
- No Portfolio Refinery API or UI.
- No stock selection/ranking.
- No sizing/HRP/risk-budget optimization.
- No OOS validation.
- No point-in-time Universe/fundamental reconstruction.
