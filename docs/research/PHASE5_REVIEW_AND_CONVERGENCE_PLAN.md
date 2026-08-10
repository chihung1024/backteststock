# Phase 5 Review & Convergence Plan

Status: **ACTIVE REVIEW PLAN / NOT PRODUCTION METHODOLOGY AUTHORITY**.

Parent work: PR #65 `feat: add Phase 5 clustering and redundancy diagnostics`.

Purpose: record the independent review findings that must be resolved before Phase 5 can be considered merge-ready. Accepted changes must be promoted into `REFINERY_CLUSTERING_V1.md`, code constants, tests, API methodology/schema output and the live roadmap together.

## 1. Baseline under review

- Production baseline: `main@db3e692e3e4ce1962d6953988464947b35d5ef82` (Phase 4 closeout).
- Parent PR: #65.
- Parent implementation head at review start: `0dd3c12b3097975bdcd4d36aeab5504987efbe29`.
- Phase 5 initial clustering contract: `refinery-clustering-twd-2026-08-10.1`.
- Refinery API request contract remains `refinery-v1`.
- Current additive API schema implemented on the Phase 5 branch: `refinery-v1-2026-08-10.2`.

The existing architecture and Phase 1–4 semantics are not being reopened by this review.

## 2. What remains accepted

The following Phase 5 design decisions remain supported and are not reopened without new evidence:

1. structural clustering input is synchronized weekly TWD returns;
2. distance is `sqrt((1-rho)/2)` over a validated correlation matrix;
3. average linkage is primary and complete linkage is sensitivity evidence;
4. Ward is not used as the V1 default on the precomputed correlation-distance path;
5. flat cut, stability windows and bootstrap parameters are explicit/versioned policies rather than claimed universal optima;
6. pair output is descriptive HIGH / MEDIUM / LOW / UNCERTAIN evidence, not a 0–100 score or trading action;
7. candidate membership remains fail-closed;
8. theme evidence remains explicitly unavailable without deterministic provenance;
9. browser code renders returned evidence and must not reimplement clustering/verdict math.

SciPy documentation supports average/complete linkage on condensed distance matrices and explicitly warns that Ward/centroid/median methods require Euclidean pairwise distances. The existing average/complete boundary is therefore retained.

## 3. Review Finding M1 — Bootstrap seed-data identity

### Existing contract text

The initial Phase 5 contract states that deterministic bootstrap seed material includes the candidate `dataset_hash`.

### Existing implementation

`Phase5RefineryService` constructs a canonical SHA-256 fingerprint from the structural weekly return frame after canonical column ordering and uses that identity for the bootstrap seed path.

### Why the difference exists

The full ResearchDataset hash intentionally captures broad reproducibility information, including requested membership/order and other metadata. Clustering evidence, however, is required to be invariant to a permutation of the same labelled candidate set and structural values.

Using one identity for both purposes conflates two questions:

- **ResearchDataset identity:** are the complete exported research data + metadata identical?
- **Clustering seed identity:** is the canonical structural input that drives the stochastic bootstrap identical?

### Proposed decision

Adopt a named **canonical structural bootstrap fingerprint** derived from:

- canonical sorted symbol order;
- structural weekly timestamps;
- structural weekly values with canonical non-finite handling;
- the relevant clustering methodology parameters/version included separately in seed material.

Do not mutate or semantically repurpose `ResearchDataset.dataset_hash`.

### Required changes

- rename the implementation boundary so a structural fingerprint is not masquerading as a dataset hash;
- update `REFINERY_CLUSTERING_V1.md` seed section;
- bump clustering methodology version because deterministic seed semantics are externally observable;
- preserve permutation-invariance tests;
- add a test showing ResearchDataset hash and structural bootstrap fingerprint intentionally answer different identity questions.

### Acceptance criteria

- same structural labelled data in different request order -> same bootstrap fingerprint / output;
- a structural value/date change -> different fingerprint/output seed;
- unrelated metadata that does not alter structural input does not silently change the clustering seed;
- API exposes the fingerprint with an unambiguous field name.

## 4. Review Finding M2 — Complete-month factor alignment

### Problem

Asset returns are converted to monthly observations by calendar-month compounding. For a research request that begins or ends mid-month, the first/last asset monthly observation can represent a partial month. Kenneth French monthly factor rows represent full calendar-month factor returns.

Regressing a partial-month asset return against a full-month factor return creates a period mismatch even though both are labelled with the same month-end timestamp.

### Proposed V1 policy

Use **complete overlapping calendar months only**.

A candidate month is eligible only when the asset daily return input covers the full intended asset trading interval for that calendar month within the research window. At minimum:

- drop a first month when the research start is after that asset's first required trading observation for the month;
- drop a last month when the research end occurs before the asset's final available trading observation for the month;
- retain explicit effective factor start/end and observation count.

The exact completeness implementation must be deterministic and independently testable; do not infer completeness from a month-end label alone.

### Required tests

- mid-month start drops first partial month;
- mid-month end drops last partial month;
- full-month boundaries retain the month;
- different holiday calendars do not fabricate missing returns as full coverage;
- insufficient complete months remains explicit unavailable evidence.

### Acceptance criteria

No OLS observation pairs an asset partial-month return with a full-month factor row.

## 5. Review Finding M3 — Factor computability vs applicability

### Source scope

The Kenneth French U.S. five-factor series is constructed from U.S. stock portfolios; its market factor covers eligible U.S.-incorporated NYSE/AMEX/NASDAQ firms and the characteristic factors are constructed from U.S. stock sorts. Momentum is likewise a U.S. stock factor in the U.S. library.

### Current implementation shortcut

Phase 5 currently treats USD quote currency + native return history + minimum observations as sufficient factor eligibility.

### Issue

USD denomination is sufficient to make the native-return regression mechanically easy to express, but does not classify the economic/instrument scope of every asset. Examples can include non-U.S. equities, ADRs, commodity/fixed-income/currency/crypto/leveraged products and other instruments.

A regression may still be mathematically computable and useful as a descriptive U.S.-factor loading diagnostic, but that is not the same as saying the model is an appropriate redundancy corroborator for every USD-denominated instrument.

### Proposed V1 policy

Split state into:

1. **factor_computable** — data prerequisites are satisfied;
2. **factor_model_scope** — what model/source is being applied;
3. **factor_corroboration_eligible** — whether Phase 5 verdict policy is allowed to use the factor value as corroborating evidence.

Until the repository has a traceable instrument taxonomy capable of establishing applicability, conservative V1 behavior is:

- allow the clearly labelled U.S.-factor diagnostic to be displayed when computable;
- preserve source/sample/R-squared/betas;
- do **not** let factor evidence upgrade a redundancy verdict solely because the quote currency is USD;
- keep future instrument taxonomy / regional factor routing in BACKLOG rather than expanding Phase 5.

### Acceptance criteria

- factor diagnostics cannot silently turn an otherwise UNCERTAIN pair into MEDIUM without an approved applicability rule;
- UI clearly distinguishes diagnostic availability from verdict corroboration eligibility;
- non-computable evidence stays unavailable, never zero.

## 6. Review Finding M4 — Common-sample factor relationship semantics

### Current risk

Each asset regression can be fitted on its own valid overlap window. The factor covariance matrix used for `B Sigma_F B'` can then be computed from a broader factor frame than one or more asset beta estimation windows.

The resulting matrix is deterministic, but its sample semantics are ambiguous.

### Proposed V1 policy

For the pair/matrix systematic relationship used by Phase 5, prefer one **common monthly observation set** shared by all assets included in that relationship matrix and the factor frame.

Alternative pairwise sample semantics would create different effective covariance samples for different cells and should not be introduced in V1 unless explicitly justified/versioned.

### Required changes

- determine the eligible common complete-month index;
- fit each included asset on that common factor/asset sample, or explicitly recompute relationship betas on the common relationship sample;
- compute factor covariance on the same index;
- expose factor relationship effective start/end/observations;
- assets not meeting the minimum on the common sample remain unavailable for the systematic relationship.

### Acceptance criteria

Every cell in one returned factor-implied relationship matrix has one unambiguous common factor sample.

## 7. Contract/version amendment proposal

If M1–M4 are accepted, the Phase 5 methodology contract should move from:

```text
refinery-clustering-twd-2026-08-10.1
```

to a new explicit version, suggested:

```text
refinery-clustering-twd-2026-08-10.2
```

The exact version string is frozen only in the implementation Batch when code/tests/docs are updated together.

The API request contract remains `refinery-v1`. The current Phase 5 branch already uses additive API schema `refinery-v1-2026-08-10.2`; if accepted methodology evidence fields change the public response shape again, evaluate whether another API schema bump is required.

## 8. Required implementation Batch sequence

### Batch P5-CORR-A — Seed identity

- explicit structural fingerprint primitive;
- no ResearchDataset hash repurposing;
- contract/code/test alignment.

### Batch P5-CORR-B — Factor calendar/sample policy

- complete-month alignment;
- common relationship sample;
- targeted reference/invariant tests.

### Batch P5-CORR-C — Factor applicability policy

- computable vs scope vs corroboration eligibility;
- conservative verdict behavior;
- UI/API evidence labels/types only as required.

Each sub-batch must remain independently testable and rollback-safe; if the implementation surface is small enough they may be one commit, but the logical verification gates remain separate.

## 9. Final validation gates

Before PR #65 leaves Draft / merges:

- [ ] clustering contract/code constants aligned;
- [ ] API schema doc/code aligned;
- [ ] complete-month factor tests pass;
- [ ] common-sample factor relationship tests pass;
- [ ] factor corroboration applicability test passes;
- [ ] bootstrap fingerprint/permutation invariants pass;
- [ ] existing Phase 1–4 fields remain regression-identical where required;
- [ ] Python full suite passes;
- [ ] Worker/Node suite passes;
- [ ] score suite passes;
- [ ] Portfolio web type/build/source-contract passes;
- [ ] Playwright full regression passes;
- [ ] Vercel required status passes on the final exact head;
- [ ] Release Backup Gate passes;
- [ ] dependency vulnerability triage completed or explicitly classified non-blocking with evidence;
- [ ] independent final exact-head review recorded;
- [ ] live roadmap updated before merge.

## 10. Explicit non-goals of this convergence

- regional factor-model implementation;
- instrument master;
- theme taxonomy/provider;
- change to average/complete linkage unless new evidence appears;
- changing current redundancy thresholds without separate evidence;
- marginal experiments;
- KEEP/TRIM/REPLACE;
- sizing;
- Exhaustive integration;
- OOS/walk-forward claims.

## 11. External methodological references

Primary/official references used for review:

- SciPy `scipy.cluster.hierarchy.linkage`, `average`, `complete`, `fcluster` documentation for condensed-distance hierarchical clustering and Euclidean requirements of Ward/centroid/median methods.
- Kenneth French Data Library, U.S. Fama/French 5 Factors (2x3) description.
- Kenneth French Data Library, U.S. Monthly Momentum Factor description.

These references support the scope/mechanics review; project-specific thresholds, windows and confidence/verdict policies remain BacktestStock versioned consumer decisions rather than claims of universal statistical optimality.
