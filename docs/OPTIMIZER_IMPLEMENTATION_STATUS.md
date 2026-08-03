# Optimizer implementation status

Status: implemented in this merge branch; deployment and browser-capacity
validation remain pending.

## Active product contract

- One fixed user-supplied source pool; no pre-ranking, ticker substitution, or
  training-period candidate selection.
- One complete historical period; no training / out-of-sample split.
- Every asset and benchmark is converted to daily TWD adjusted-close levels
  before the browser receives the signed snapshot.
- Any source or benchmark data failure stops the exhaustive preflight with an
  explicit list; it never silently drops a ticker or shortens the period.
- `N` source tickers and configurable `K` holdings enumerate all `C(N,K)`
  portfolios with dynamic equal target weights `1/K`.
- Relative bands, monthly, quarterly, annual, and no-rebalance modes use the
  same exact browser simulation and configurable transaction cost / execution
  delay.

## Capacity and persistence

- The browser calculates up to **50,000,000** combinations.
- Up to **5,000,000** result rows are durably retained after all combinations
  have been calculated: 60% primary optimized-score leaders, 30% leaders from
  complementary metrics, and 10% deterministic diversity coverage.
- The first phase stores only bounded typed selection buffers; retained ranks
  are re-evaluated and stored compactly as `Uint32 rank + Float32[14] metrics`.
- Holdings are reconstructed from combinatorial rank, so they are not duplicated
  in every saved result row.
- Paused jobs persist checkpoints and compact chunks.  A pre-checkpoint browser
  close deliberately recomputes completed work rather than bias global ranks.
- The old 60-source-ticker cap is replaced by a 100-ticker platform boundary;
  the additional guards are `C(N,K) ≤ 50,000,000`, signed snapshot size, and
  the preflight resource estimate.

## Retired surface

The former `/api/optimizer/*` training / out-of-sample workflow is no longer
deployed or edge-routable.  `optimizer.html` uses only
`/api/optimizer/exhaustive/prepare`; legacy source files remain in the repository
temporarily as historical reference and are not part of the active build or
public route contract.

## Remaining release checks

- Run the real-browser IndexedDB resume and 5M-retention tests in an environment
  with Playwright Chromium installed.
- Measure 25/50/75/100-source preflight behavior on the target Vercel runtime.
- Deploy the branch only after confirming configured upstream Yahoo and FX
  request limits remain within the free hosting envelope.
