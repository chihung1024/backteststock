# Phase 5 Review & Convergence Plan

Status: **ACTIVE REVIEW PLAN / NOT PRODUCTION METHODOLOGY AUTHORITY**.

Parent work: PR #65 `feat: add Phase 5 clustering and redundancy diagnostics`.

Docs/governance child: PR #66 `docs: converge Phase 5 contracts and handoff state`.

Purpose: record the review findings that must be resolved before Phase 5 can be considered merge-ready and freeze an implementation-ready correction specification. Accepted changes must be promoted into `REFINERY_CLUSTERING_V1.md`, code constants, tests, API methodology/schema output, UI types/labels where externally visible, and the live roadmap together.

## 1. Baseline under review

- Production baseline: `main@db3e692e3e4ce1962d6953988464947b35d5ef82` (Phase 4 closeout).
- Parent PR: #65.
- Parent implementation head at review start: `0dd3c12b3097975bdcd4d36aeab5504987efbe29`.
- Phase 5 initial clustering contract: `refinery-clustering-twd-2026-08-10.1`.
- Refinery API request contract remains `refinery-v1`.
- Current additive API schema implemented on the Phase 5 branch: `refinery-v1-2026-08-10.2`.
- PR #66 final pre-review implementation is documentation-only; no production runtime correction is considered implemented by this plan.

The existing architecture and Phase 1–4 semantics are not being reopened.

## 2. Review-gate constraint

`AI_PROJECT_PLAYBOOK.md` requires an **Independent Third-Party Review** before an important PR merges. Current GitHub repository collaborator inventory contains only `chihung1024`; PR #66 has no submitted review. Therefore:

- self-review is evidence, not third-party approval;
- the playbook is not changed merely to bypass this gate;
- PR #66 remains unmerged until an actual independent reviewer/review mechanism exists;
- research/design work may continue in parallel, but P5-CORR production implementation does not supersede the open P5-DOC merge gate.

## 3. Decisions that remain accepted

The following Phase 5 design decisions remain supported and are not reopened without new evidence:

1. structural clustering input is synchronized weekly TWD returns;
2. distance is `sqrt((1-rho)/2)` over a validated correlation matrix;
3. average linkage is primary and complete linkage is sensitivity evidence;
4. Ward is not the V1 default on this precomputed correlation-distance path;
5. flat cut, stability windows and bootstrap parameters are explicit/versioned consumer policies rather than universal optima;
6. pair output is descriptive HIGH / MEDIUM / LOW / UNCERTAIN historical exposure evidence, not a 0–100 score or trading action;
7. candidate membership remains fail-closed;
8. theme evidence remains explicitly unavailable without deterministic provenance;
9. browser code renders returned evidence and must not reimplement clustering/verdict math.

## 4. M1 — Bootstrap seed-data identity

### Observed implementation

`Phase5RefineryService` currently:

1. computes `_structural_bootstrap_fingerprint(prepared.weekly_returns)`;
2. creates `replace(prepared.candidate_dataset, dataset_hash=canonical_seed_fingerprint)`;
3. passes that altered ResearchDataset into Phase 5 relationship composition;
4. `bootstrap_cluster_stability()` still names the input `dataset_hash` and includes it in the seed payload.

The service-level fingerprint canonicalizes symbol order, but hashes the **entire supplied weekly frame**. The actual bootstrap primitive then canonicalizes the frame again, truncates to the trailing structural window, replaces non-finite values, and drops incomplete rows before resampling.

### Root cause

Two distinct identities were conflated:

- **ResearchDataset identity** — full audited dataset/export identity;
- **bootstrap effective-input identity** — exact canonical rows/columns that the stochastic bootstrap actually resamples.

The current workaround avoids request-order instability but mutates `ResearchDataset.dataset_hash` semantics and allows data outside the effective bootstrap sample to change the seed.

### Frozen correction specification

Introduce one pure quant preparation path shared by fingerprinting and bootstrap execution.

Conceptually:

```text
prepare_bootstrap_sample(weekly_returns, window)
  -> numeric frame
  -> canonical sorted symbol columns
  -> trailing `window` rows
  -> +/-inf -> NaN
  -> complete-case row drop
  -> exact effective bootstrap sample

bootstrap_input_fingerprint(sample)
  -> SHA-256 of canonical symbols + exact dates + exact numeric values

bootstrap_seed
  = SHA-256(
      input_fingerprint,
      clustering_contract_version,
      primary_linkage,
      cut_distance,
      window,
      block_weeks,
      replicates
    )[:8]
```

Requirements:

- do not mutate or replace `ResearchDataset.dataset_hash`;
- rename the bootstrap primitive argument from `dataset_hash` to an unambiguous `input_fingerprint`/equivalent;
- both fingerprinting and bootstrap must consume the same prepared effective sample function so their semantics cannot drift;
- include `window` explicitly in seed methodology parameters;
- keep ResearchDataset hash in normal dataset/reproducibility evidence unchanged;
- API Phase 5 clustering evidence should expose an unambiguous field such as `bootstrap_input_fingerprint_sha256`; the draft-only `bootstrap_seed_fingerprint` name may be replaced before Phase 5 ships.

### Required tests

1. candidate/request permutation -> same effective fingerprint, seed and labelled bootstrap evidence;
2. change a value/date **inside** the effective sample -> fingerprint/seed changes;
3. add/change rows strictly older than trailing `window` -> fingerprint/seed/output unchanged;
4. change values only on a row that is excluded by complete-case preparation -> effective fingerprint unchanged;
5. ResearchDataset hash may answer a different identity question without being overwritten by clustering;
6. changing `window`, cut, linkage policy, block length, replicate count or contract version changes seed material as intended.

### Status

**BLOCKER / NOW.**

## 5. M2 — Boundary-safe monthly factor alignment

### Observed implementation

`fit_us_factor_exposure()` currently calls:

```text
((1 + daily_returns).resample("ME").prod() - 1)
```

and joins the resulting month-end labels directly to full-calendar-month Kenneth French rows.

ResearchDataset native returns are produced by `pct_change(...).iloc[1:]` inside the exact requested data window. Therefore the first return month cannot prove a full calendar-month holding-period return because the pre-window prior close is intentionally absent.

The last observed month can also be partial because of the requested end, listing/delisting/data availability, and this repository does not currently have an exchange-calendar authority that can prove otherwise for every instrument.

### Frozen conservative V1 policy

Do **not** pretend to infer exchange-specific month completeness from a month-end label.

For each asset's daily native-return series:

1. normalize timezone/index, numeric values and ordering;
2. identify calendar-month periods represented by the available return series;
3. exclude the **first and last represented calendar periods** from factor-regression eligibility;
4. compound only interior periods;
5. join those monthly asset returns to official factor rows;
6. require the existing minimum observation count after this exclusion.

This intentionally sacrifices at most two boundary observations per asset to obtain a deterministic fail-closed V1 rule without introducing an exchange-calendar/instrument-master dependency into Phase 5.

This is named a **boundary-month exclusion policy**, not a universal complete-month detector. Internal provider data quality remains governed by the existing market-data/audit contracts.

### Required evidence fields

Per asset retain:

- factor observations;
- effective start/end;
- regression R-squared/betas when available;
- explicit monthly-return policy identifier.

### Required tests

1. first represented month is excluded even when its month-end factor row exists;
2. last represented month is excluded;
3. interior months compound correctly from daily returns;
4. a mid-month requested start cannot create a valid same-month factor observation;
5. an early/partial terminal asset month cannot create a valid same-month factor observation;
6. insufficient post-exclusion months remains explicit unavailable evidence;
7. no backward/pre-window return is fabricated to rescue a boundary month.

### Status

**BLOCKER / NOW.**

## 6. M3 — Factor computability vs model applicability/corroboration

### Observed implementation

`_factor_payload()` currently treats:

```text
quote_currency == USD
+ native returns
+ minimum observations
```

as factor eligibility. `_redundancy_payload()` then inserts every available factor-implied correlation directly into `RedundancyEvidence`, where a value >= 0.65 can be the sole optional corroborator that upgrades a pair to MEDIUM.

ResearchDataset `asset_metadata` currently contains quote currency and audit/fingerprint fields, but no authoritative instrument type, incorporation/market scope, ADR/ETF/fund classification or approved factor-model applicability taxonomy.

### Frozen conservative V1 policy

Separate three concepts explicitly:

```text
factor_computable
factor_model_scope
factor_corroboration_eligible
```

For current Phase 5 V1:

- USD + native history may make the U.S.-factor regression **computable**;
- the model scope is explicitly `U.S.-factor co-movement diagnostic`;
- absent a traceable instrument-scope authority, `factor_corroboration_eligible = false`;
- diagnostic betas/R-squared/systematic correlation may still be displayed;
- factor evidence must **not** change HIGH/MEDIUM/LOW/UNCERTAIN verdicts while corroboration eligibility is false.

Do not solve this by building an instrument master inside Phase 5. Instrument taxonomy / regional factor routing remains BACKLOG.

### Minimal policy implementation

`RedundancyEvidence` should make factor eligibility explicit (for example `factor_corroboration_eligible: bool | None`) and the MEDIUM factor corroborator requires both:

```text
factor_corroboration_eligible is True
and factor_implied_correlation >= 0.65
```

The API may continue to expose the diagnostic `factor_implied_correlation` in the pair row, but must also expose eligibility/reason so UI and audit consumers can distinguish display evidence from verdict evidence.

Suggested explicit reason while no authority exists:

```text
unavailable_no_traceable_instrument_scope
```

### Required tests

1. an otherwise UNCERTAIN pair with factor correlation >= 0.65 remains UNCERTAIN when eligibility is false;
2. pure policy test proves factor can act as a corroborator only when eligibility is explicitly true;
3. USD diagnostic remains visible even when verdict eligibility is false;
4. non-USD/native-unavailable states remain unavailable, never numeric zero;
5. UI/source contract labels diagnostic availability separately from verdict eligibility.

### Status

**BLOCKER / NOW.**

## 7. M4 — Common-sample factor relationship semantics

### Observed implementation

Current code fits each asset exposure on its own factor/asset overlap, then `factor_implied_relationship()` computes `Sigma_F` over the broader factor frame passed to the relationship function. Consequently beta estimates and factor covariance can describe different observation universes.

### Frozen V1 relationship policy

Maintain two separate concepts:

1. **individual factor diagnostic** — each computable asset may report its own valid exposure sample;
2. **systematic relationship matrix** — one matrix must use one exact common monthly sample.

For the matrix:

1. prepare boundary-safe monthly returns for each factor-computable asset;
2. identify assets that individually satisfy minimum observations;
3. build one intersection of month indices across those valid assets and the factor frame;
4. require minimum observations on that global common set;
5. refit relationship betas for every matrix member on that same exact common set;
6. compute `Sigma_F` from the exact same common rows;
7. compute `B Sigma_F B'` and systematic correlation;
8. if the common set is insufficient, return relationship unavailable rather than silently switching to pairwise samples.

No pairwise-cell sample switching in V1. A single returned matrix has a single auditable observation universe.

### Required relationship evidence

`systematic_relationship` should expose at least:

- status;
- symbols;
- observations;
- effective start/end;
- common-sample fingerprint SHA-256;
- matrix when available.

Top-level provider `factor_sample` remains source/window evidence and must not be confused with the common relationship sample.

### Required tests

1. two assets with different individual histories are refit on the exact common index for the matrix;
2. `Sigma_F` uses exactly the same rows as relationship beta fitting;
3. matrix formula matches an independently computed fixture on the common set;
4. insufficient global common sample returns unavailable relationship;
5. no pair cell silently uses a different factor sample;
6. symbol/request permutation leaves labelled matrix and common-sample fingerprint equivalent.

### Status

**BLOCKER / NOW.**

## 8. Versioning decision for P5-CORR

The correction changes deterministic bootstrap seed identity, factor monthly-sample semantics, factor verdict eligibility and externally visible factor/relationship evidence. Therefore, if implemented as specified:

```text
REFINERY_CLUSTERING_CONTRACT_VERSION
  refinery-clustering-twd-2026-08-10.1
  -> refinery-clustering-twd-2026-08-10.2
```

The request contract remains:

```text
REFINERY_API_CONTRACT_VERSION = refinery-v1
```

Because the public Phase 5 response fields/semantics also change, the API schema should be bumped rather than keeping `.2`:

```text
REFINERY_API_SCHEMA_VERSION
  refinery-v1-2026-08-10.2
  -> refinery-v1-2026-08-10.3
```

No Refinery workspace persistence/storage schema bump is required unless the persisted input model changes; P5-CORR currently does not require that.

Version alignment is incomplete unless code constants, contract docs, tests, API methodology output, TypeScript response types/labels and live roadmap agree.

## 9. Minimal implementation surface

P5-CORR should normally touch only the following logical areas:

### Pure quant

- `apps/api/app/quant/clustering.py`
- `apps/api/app/quant/factors.py`
- `apps/api/app/quant/__init__.py` only for changed exports

### Refinery composition/policy

- `apps/api/app/refinery/phase5_service.py`
- `apps/api/app/refinery/relationships.py`
- `apps/api/app/refinery/redundancy.py`
- `apps/api/app/refinery/models.py` for API schema version

### UI contract only as externally required

- `apps/portfolio-web/src/refineryTypes.ts`
- Phase 5 results label/presentation files only if the new eligibility/sample evidence must be rendered

### Tests

- `tests/test_clustering.py`
- `tests/test_factor_relationships.py`
- `tests/test_redundancy_policy.py`
- `tests/test_refinery_phase5.py`
- Phase 5 web/source-contract/E2E tests only where visible response semantics change

### Documents

- `docs/research/REFINERY_CLUSTERING_V1.md`
- `docs/research/REFINERY_API_V1.md`
- `docs/research/REFINERY_UI_V1.md` only for visible semantics
- `to_do_update_list.md`
- this review plan marked RESOLVED/CLOSED after accepted implementation

Do not touch Scanner, Portfolio ledger, Exhaustive, D1 schema, market-data downloader authority or Phase 6 logic unless a new Critical finding proves it necessary.

## 10. Required implementation sequence

### P5-CORR-A — Seed identity

1. shared exact bootstrap-sample preparation;
2. effective-input fingerprint primitive;
3. no ResearchDataset hash repurposing;
4. seed parameter alignment including window;
5. targeted invariants.

### P5-CORR-B — Factor calendar + common-sample policy

1. boundary-month exclusion helper;
2. individual diagnostic sample evidence;
3. global common relationship sample;
4. refit relationship betas + `Sigma_F` on same rows;
5. matrix/sample fingerprint tests.

### P5-CORR-C — Factor applicability/verdict policy

1. computable/scope/corroboration-eligible evidence;
2. factor gated out of verdict unless eligibility explicitly true;
3. API/TypeScript/UI evidence labels;
4. policy regression tests.

### P5-CORR-D — Version/doc convergence

1. clustering contract `.2`;
2. API schema `.3`;
3. methodology output/type alignment;
4. live roadmap update;
5. no stale `.1/.2` claims except labelled historical notes.

Each sub-batch must remain independently testable and rollback-safe. They may be committed together only if the implementation diff remains one coherent correctness change; logical verification remains separated.

## 11. Final validation gates

Before PR #65 leaves Draft / merges:

- [ ] PR #66 independent third-party review completed and docs merged/preserved in parent history;
- [ ] clustering contract/code constants aligned at corrected version;
- [ ] API schema doc/code/types aligned;
- [ ] exact bootstrap-effective-input fingerprint invariants pass;
- [ ] irrelevant out-of-window weekly data does not change bootstrap seed/output;
- [ ] boundary-month factor tests pass;
- [ ] common-sample factor relationship tests pass;
- [ ] factor corroboration eligibility tests pass;
- [ ] existing Phase 1–4 fields remain regression-identical where required;
- [ ] Python full suite passes;
- [ ] Worker/Node suite passes;
- [ ] score suite passes;
- [ ] Portfolio web type/build/source-contract passes;
- [ ] Playwright full regression passes;
- [ ] Vercel required status passes on the final exact head;
- [ ] Release Backup Gate passes;
- [ ] dependency vulnerability triage completed or explicitly classified non-blocking with evidence;
- [ ] independent final exact-head review of PR #65 recorded;
- [ ] live roadmap updated before merge;
- [ ] expected-head squash merge only after all blockers are resolved.

## 12. Explicit non-goals

- regional factor-model implementation;
- instrument/security master;
- exchange-calendar platform;
- theme taxonomy/provider;
- change to average/complete linkage without new evidence;
- changing current redundancy thresholds except gating factor eligibility;
- marginal experiments;
- KEEP/TRIM/REPLACE;
- sizing;
- Exhaustive integration;
- OOS/walk-forward claims.

## 13. External methodological references

Primary/official references used for review:

- SciPy `scipy.cluster.hierarchy.linkage`, `average`, `complete`, `fcluster` documentation for condensed-distance hierarchical clustering and Euclidean requirements of Ward/centroid/median methods.
- Kenneth French Data Library, U.S. Fama/French 5 Factors (2x3) description.
- Kenneth French Data Library, U.S. Monthly Momentum Factor description.

These references support scope/mechanics only. BacktestStock windows, cut thresholds, bootstrap policy, confidence/verdict thresholds, conservative boundary-month exclusion and evidence-eligibility rules are versioned project consumer policies, not claims of universal statistical optimality.
