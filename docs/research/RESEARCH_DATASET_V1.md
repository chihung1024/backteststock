# ResearchDataset V1

Status: **Current reproducible research-data boundary.**

`ResearchDataset` is the deterministic bridge between audited TWD market histories and research engines. It owns membership accounting, requested/effective date boundaries, aligned daily/weekly matrices, audit/fingerprint evidence and dataset identity. It is not a strategy, selector, covariance model, Portfolio engine or downloader.

## Source authority

Input is `PartialTWDHistories` from `TWDHistoryService`.

The dataset does not re-download Yahoo/FX data. TWD valuation, instrument lifecycle, return components and source audits remain owned by `apps/api/app/data/` and the shared TWD contract.

Current identity/policy constants live in `apps/api/app/research/dataset.py`.

## Membership

Every requested symbol has exactly one outcome:

```text
resolved history
or
explicit HistoryFailure
```

A partial dataset is valid evidence but `is_complete == false`. Consumers that require full membership must reject it; they may not silently redefine the requested universe as the resolved subset.

Requested order is preserved after canonical normalization/deduplication at the owning data-service boundary.

## Requested-window isolation

All retained native/FX/TWD observations must stay within the dataset's requested inclusive interval.

A caller that owns a wider parent history must create an explicit bounded view; `ResearchDataset` does not silently accept future/pre-window rows and trust downstream code to ignore them.

Requested dates and effective dates are separate evidence.

## Daily matrix

Daily TWD levels use the existing multi-asset alignment policy:

- union the usable TWD valuation calendars;
- forward-fill only after a real prior observation;
- never backward-fill before inception/first evidence;
- trim opening rows until the selected resolved set has valid aligned levels.

Daily returns are arithmetic `pct_change(fill_method=None)` of aligned TWD levels and exclude the synthetic opening row.

## Weekly structural matrix

Weekly structural evidence groups daily aligned TWD levels by `W-FRI` period and retains the last actual available research date in each period.

The timestamp is not relabelled to a future Friday. This prevents a partial week ending Wednesday from being represented as evidence available Friday.

## Availability / coverage

Availability and coverage describe source evidence, not forward-filled convenience rows.

A consumer may use aligned levels for valid cross-market valuation, but it must not claim that forward-filled dates were fresh source observations.

## Reproducibility identity

Dataset export/hash binds material evidence such as:

- contract/policy versions;
- requested/resolved/failure membership;
- requested/effective ranges;
- daily/weekly matrices;
- native/FX/TWD audit/fingerprint evidence;
- applicable source/valuation identities.

Identity is deterministic canonical JSON + SHA-256 under the implementation contract.

The dataset hash means “same complete ResearchDataset evidence,” not “same downstream model sample.” A downstream primitive may need its own narrower effective-sample identity and must not repurpose the dataset hash.

## Parent-bounded views

Nested research such as parameter tuning may create deterministic child views from one audited parent dataset when methodology permits.

Child views:

- use only parent evidence;
- do not download, interpolate or privately repair data;
- remain inside parent/requested bounds;
- preserve requested membership/outcome accounting;
- receive their own deterministic identity and parent provenance.

## Fail-closed semantics

Reject or expose explicit failure rather than:

- silently dropping requested members;
- using rows outside the requested window;
- replacing unavailable data with zero;
- backfilling from future observations;
- changing calendar/coverage policy without versioning;
- using the dataset hash as a generic identity for unrelated downstream samples.

Tests and code are authoritative for exact serialization fields and policy constants.
