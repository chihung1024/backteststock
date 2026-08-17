# Optimizer Hub Dual Momentum V1

Status: **Phase 4B-1 production-accepted contract.** Product tree `8374bb17d3192c2e6adcfa06c7350d51e8651f2e` passed exact-head review, merge, post-main CI, Vercel/Cloudflare exact-SHA gates and production Walk-Forward verification on 2026-08-17.

Contract versions:

- configured research universe: `configured-research-universe-2026-08-17.1`
- configured decision: `walk-forward-configured-decision-2026-08-17.1`
- configured selection boundary: `walk-forward-configured-selection-2026-08-17.1`
- momentum signal: `momentum-twd-total-return-2026-08-17.1`
- Dual Momentum selector: `dual-momentum-selection-2026-08-17.1`
- Dual Momentum Walk-Forward job: `walk-forward-dual-momentum-job-2026-08-17.1`
- selector policy: `dual-momentum-configured-monthly-v1`

This document owns the additive Phase 4B-1 strategy contract. It does not replace the frozen PIT/Exhaustive contracts from Phase 4A.

## 1. Product objective

Phase 4B-1 delivers the first Optimizer Hub vertical slice:

```text
configured risky + defensive assets
  -> Training-only momentum evidence
  -> absolute filter
  -> relative ranking / Top-K
  -> defensive fallback
  -> frozen DecisionSnapshot
  -> existing Walk-Forward Evaluation
  -> existing Portfolio v3 continuous OOS ledger / costs
  -> existing authoritative metrics
  -> existing ResearchRun persistence / rerun
```

V1 deliberately fixes allocation to equal weight. Inverse volatility, ERC/Risk Parity, parameter optimization and advanced tactical allocation are separate later phases.

## 2. Authority boundaries

Phase 4B-1 must not create a second authority for any of the following:

- market data / TWD valuation: `ResearchDataset` remains authoritative;
- OOS execution / transaction costs: Portfolio v3 remains authoritative;
- portfolio metrics: the existing backend metrics remain authoritative;
- Walk-Forward temporal firewall: the existing Training -> frozen Decision -> Evaluation ordering remains authoritative;
- durable research memory: D1 ResearchRun remains authoritative;
- completed result: only backend-produced completed Walk-Forward results may be persisted.

The browser may edit parameters, generate a transparent monthly schedule, pre-validate inputs and render returned evidence. It must not recompute Momentum, portfolio paths, CAGR, Sortino, MDD or authoritative transaction costs.

## 3. Configured research universe provenance

Dual Momentum uses a fixed user-configured set of assets. Those symbols are not historical index-membership evidence and must never masquerade as PIT data.

`ConfiguredResearchUniverse` therefore binds:

```json
{
  "contractVersion": "configured-research-universe-2026-08-17.1",
  "provenanceType": "configured-request",
  "members": ["..."],
  "universeHash": "sha256(...)"
}
```

Rules:

1. members are canonical uppercase symbols;
2. membership is non-empty, unique and order-stable;
3. the exact ordered membership is part of immutable request/decision identity;
4. no `sourceAsOf`, `requestedAsOf`, authoritative-membership flag or other PIT field is fabricated;
5. a DecisionSnapshot has exactly one membership provenance: PIT or configured request, never both.

The existing PIT DecisionSnapshot payload/hash path remains unchanged for existing Exhaustive research.

## 4. Training-only signal authority

The Momentum signal authority is `ResearchDataset.daily_levels_twd`.

These levels are audited TWD adjusted total-return levels under the existing ResearchDataset contract. V1 does not fetch a second price series and does not calculate the signal from browser data.

For symbol `i`, Decision signal date `t` and lookback `L` calendar months:

```text
requested_start = t - L calendar months
baseline = first audited TWD level on or after requested_start
end      = last audited TWD level on or before t
M_i(t,L) = end / baseline - 1
```

Boundary policy:

- baseline must be no more than 7 calendar days after `requested_start`;
- end observation must be no more than 7 calendar days before `t`;
- baseline and end levels must be finite and strictly positive;
- baseline date must be strictly before end date;
- materially shorter history fails closed rather than silently shortening the lookback.

All signal dates and values are derived before Evaluation/OOS data is loaded. `SelectionContext` contains no Evaluation dataset.

## 5. Absolute Momentum

For configured threshold `h`:

```text
absolute_pass_i = M_i >= h
```

V1 exposes a numeric total-return threshold. The default is `0%`.

Cash hurdle, trend hurdle and other alternative absolute filters are not part of this contract and must be separately versioned before use.

## 6. Relative Momentum and deterministic Top-K

Risky assets are ranked by:

1. trailing total return descending;
2. canonical symbol ascending as deterministic tie-break.

Only risky assets passing the absolute hurdle participate in the risk-on Top-K selection.

If at least one risky asset passes:

```text
selected = first min(K, passing_risky_count) passing risky assets
regime   = risk_on
```

V1 request validation requires `1 <= K <= risky_universe_size`.

## 7. Defensive fallback

If no risky asset passes the absolute hurdle:

1. defensive assets are ranked by the same trailing total-return signal;
2. up to `min(K, defensive_count)` are selected;
3. the evidence records:
   - `regime = defensive`
   - `fallbackReason = no-risky-asset-cleared-absolute-threshold`.

V1 requires at least one defensive asset.

The risky and defensive symbol sets must be disjoint.

## 8. Allocation V1

Phase 4B-1 allocation is intentionally narrow:

```text
weight_j = 1 / selected_count
```

for every selected constituent.

This equal-weight result is emitted through the existing `SelectionResult(selected_constituents, weights)` boundary.

Inverse volatility and ERC/Risk Parity belong to Phase 4B-2 and must reuse the existing quant covariance/risk-contribution authorities rather than being embedded in Dual Momentum V1.

## 9. Missing-history failure semantics

Dual Momentum V1 does not silently drop a configured member and continue with a smaller universe.

Every configured risky and defensive member must have an explicit successful Training history outcome. If any configured member is unavailable, stale or materially shorter than the configured signal window, selection fails closed.

This prevents cross-sectional ranking from changing because a difficult-to-fetch or recently listed asset disappeared invisibly from the candidate set.

## 10. Monthly Walk-Forward policy

Dual Momentum V1 is monthly.

For every period:

- `training_end == decision_date`;
- decision timing remains `after_close`;
- `evaluation_start == decision_date + 1 calendar day`;
- one Evaluation slice spans at most 35 calendar days;
- `training_start` must cover the full configured Momentum lookback.

For adjacent periods:

- Decision months must be consecutive calendar months;
- previous `evaluation_end == current decision_date`;
- Evaluation windows do not overlap;
- the next Decision may use information from the prior OOS endpoint because that endpoint is known at the new after-close Decision time;
- the new frozen target only applies to subsequent Evaluation observations.

The browser helper may generate the recent monthly schedule for usability, but the server revalidates the same constraints and remains authoritative.

## 11. Decision evidence and identity

Configured DecisionSnapshot identity binds at least:

- configured universe payload/hash;
- Training ResearchDataset hash and effective window;
- selector contract/version/rule;
- selector parameters;
- eligible candidates;
- selected constituents;
- weights;
- Training-only selection evidence.

Momentum evidence includes:

- signal contract version;
- signal as-of date;
- lookback months;
- absolute threshold;
- boundary tolerance;
- signal authority;
- regime / fallback reason;
- risky and defensive rankings;
- baseline/end evidence dates and levels;
- trailing total returns;
- absolute-pass verdict for risky assets;
- selected symbols.

Any evidence change therefore changes configured Decision identity.

## 12. OOS execution and transaction costs

After the DecisionSnapshot is frozen, Phase 4B-1 uses the existing Evaluation and continuous OOS path unchanged.

The existing OOS authority owns:

- selected-constituent Evaluation history validation;
- inter-decision target transitions;
- traded notional;
- configured transition cost bps;
- state carry across periods;
- continuous equity / return index;
- authoritative metrics.

There is no Dual-Momentum-specific backtester or metric engine.

## 13. Public request contract

Existing Exhaustive requests remain backward compatible and do not need a `strategy` field.

Dual Momentum requests opt in explicitly:

```json
{
  "periods": ["..."],
  "selector": {
    "strategy": "dual_momentum",
    "riskySymbols": ["QQQ", "SMH", "SPY", "IWM", "VEA", "VWO"],
    "defensiveSymbols": ["BIL"],
    "lookbackMonths": 12,
    "topK": 3,
    "absoluteThreshold": 0
  },
  "execution": {
    "initialAmountTwd": 100000,
    "transitionCostBps": 5
  }
}
```

Dual Momentum must not include a PIT `universe` id. The configured symbol arrays are the exact membership authority for this strategy request.

## 14. ResearchRun persistence and rerun

No new persistence schema is introduced.

The existing ResearchRun authority already persists the complete normalized execution request and backend-produced completed result. For Dual Momentum:

- the exact configured selector request is stored in D1;
- browser-submitted completed results remain forbidden;
- rerun reloads the original stored request rather than rebuilding it from current UI defaults;
- the new backend execution creates a new immutable completed result/job identity;
- the original run/request remains unchanged.

## 15. UI contract

The Walk-Forward workspace becomes a strategy-aware Optimizer Hub entry point while remaining one workspace.

V1 UI requirements:

- user can choose legacy PIT + Exhaustive or Dual Momentum;
- old schema-v1 local workspace state migrates to Exhaustive without semantic change;
- Dual Momentum exposes risky assets, defensive assets, lookback, Top-K and absolute threshold;
- allocation is visibly fixed to equal weight in 4B-1;
- user can generate a recent six-month monthly schedule;
- normalized API request is visible before execution;
- configured universe provenance, signal regime and ranking evidence are visible after execution;
- Research Library save/load/rerun accepts the same Dual Momentum request/result without creating browser authority.

## 16. Explicit exclusions

Not in 4B-1:

- inverse-volatility allocation;
- ERC / Risk Parity;
- minimum variance;
- maximum diversification;
- HRP;
- parameter optimization/search;
- cash-hurdle proxy selection;
- trend-hurdle variants;
- weekly or quarterly rebalance;
- PAA/VAA/DAA/FAA/BAA/HAA;
- browser-side performance calculation;
- any change to the frozen PR #147 roadmap work.

## 17. Required verification before production authority

At minimum:

1. configured-universe identity determinism;
2. old PIT Decision golden hash unchanged;
3. Evaluation structurally absent from selection;
4. Momentum boundary / short-history fail-closed tests;
5. deterministic relative ranking / tie-break tests;
6. risk-on Top-K test;
7. defensive fallback test;
8. Dual job proves PIT resolver and Exhaustive authority are not invoked;
9. same OOS Portfolio v3 authority is used;
10. server monthly schedule validation;
11. API normalization and strategy-field validation;
12. TypeScript + production build;
13. existing Exhaustive workspace regression E2E;
14. Dual Momentum workspace/request/evidence E2E;
15. ResearchRun existing authority tests;
16. exact-head PR CI;
17. Vercel Preview validation;
18. independent review with zero BLOCKER findings;
19. post-merge Vercel + Cloudflare exact-SHA production gates and runtime smoke.

Until all applicable gates pass, Phase 4B-1 is not `CLOSED`.