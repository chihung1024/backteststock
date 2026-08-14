# Scanner PIT Research Validity

## Purpose

This contract exposes the point-in-time Universe membership capability from Batch 3A in the normal Scanner workflow without implying that historical fundamentals already exist.

The default Scanner path remains the existing **current snapshot** workflow. PIT is an explicit opt-in research mode.

## Selection modes

### Current snapshot

- Uses the current versioned Universe snapshot.
- May apply the current fundamentals dataset, including sector, market-cap and valuation filters/sorting.
- Results can be used for current-universe retrospective research.
- Applying the selected list to an earlier performance period is **not** point-in-time historical selection and may contain survivorship/look-ahead bias.
- The UI and API surface this state as `current_snapshot_retrospective`.

### PIT historical membership

- Requires an explicit `selectionAsOf` date.
- Uses only a Universe observation whose `source_as_of` is on/before the research date and whose evidence had already been fetched by that date.
- Enforces the Batch 3A maximum observation age, archived membership integrity and checksum rules.
- Never substitutes current membership if historical evidence is unavailable.
- Does not call or apply the current fundamentals dataset.
- Sector, market-cap, P/E and market-cap/valuation sorting are disabled in the UI and are rejected by the API if supplied.
- `limit` remains available and PIT membership is ordered deterministically by ticker.
- When the generated PIT ticker list is handed to `/api/scan`, the performance interval must end on or before `selectionAsOf`. Prices after the selection date are future information relative to that research decision and therefore fail closed in the UI.

## Source authority vs temporal causality

A membership snapshot can be temporally causal without being an official historical index constituent list.

- `membershipCausal=true`: the evidence was available by the requested research date.
- `membershipAuthoritative=true`: the source is treated as authoritative membership evidence.
- `membershipAuthoritative=false`: the source is a proxy, such as ETF holdings. It may be used as causal research evidence but must not be presented as the official historical index membership.

The Scanner context must keep this distinction visible after the candidate list is handed to the performance scan.

Membership causality alone does not make a downstream performance calculation causal. For an ex-ante PIT research workflow, the end of the performance data window must also be no later than `selectionAsOf`.

## UI safety rules

1. Current snapshot is the default mode after page load.
2. PIT mode requires an explicit date and rejects future dates.
3. PIT mode disables current-fundamental controls instead of silently ignoring their meaning in the interface.
4. PIT funnel output displays historical fundamentals as **not applied**, never as zero observations.
5. A PIT API error is shown directly to the user. The browser must not retry by removing `selectionAsOf` or falling back to the current screener.
6. The research-validity context is associated with the exact generated ticker list. Manual changes to that list invalidate the stored screener context rather than attaching stale provenance.
7. The downstream `/api/scan` return/risk mathematics remain unchanged; this batch changes candidate provenance, causality guards and disclosure.
8. For an exact PIT-generated ticker list, normal scan submit and retry are blocked when the displayed performance end date is later than `selectionAsOf`; the UI explains that this would consume future price data.

## Deferred work

This contract does not fabricate or backfill historical fundamentals. Historical sector, fundamental and valuation selection may be added only after a same-time, provenance-preserving fundamentals dataset exists and can satisfy the same fail-closed research-validity standard.
