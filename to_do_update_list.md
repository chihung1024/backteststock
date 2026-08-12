# BacktestStock — Live Project Status & Handoff

> Repository-internal live handoff snapshot. Mutable GitHub / Vercel / Cloudflare / runtime state must be re-queried before important actions. Durable architecture belongs in README/contracts/ADRs; completed execution detail is reconstructable from Git/PR/Issue history.

## 1. Current Functional Goal

**Next functional goal: Issue #78 — restore Scanner selected-tickers → Optimizer manual handoff.**

The repository has completed the prior P0 Portfolio common-window correctness lane. Do not reopen #79 or #80 without new evidence.

### Completion-before-convergence rule

**Convergence is an exit discipline, not an early-stop rule.**

For every functional batch:

1. complete the necessary root-cause fix;
2. fix coupled material blockers required for safe acceptance;
3. run relevant regression and end-to-end verification;
4. perform production/runtime verification when behavior depends on deployment;
5. do not leave a known material defect that invalidates acceptance or predictably contaminates the next dependent functional batch;
6. only then classify remaining work as NEXT / BACKLOG / REJECT and stop unnecessary expansion.

`scope control`, `minimum change`, `functional-first` and `avoid over-engineering` are not permission to close work with a known major correctness, reliability, data-integrity or workflow defect.

---

## 2. Stable Production State

Repository: `chihung1024/backteststock`.

Last **functionally production-verified** runtime baseline:

`aba00c70215c451954487096b4d0b88fa50d48b0`

Important closed foundations:

- Phase -1 through 4: governance, TWD/quant authority, ResearchDataset, Refinery API/UI — CLOSED/PASS.
- Phase 5 / #65 + #75 + #94: clustering/redundancy + hardened production acceptance — CLOSED/PASS/PRODUCTION VERIFIED.
- #83 + #84 + #80: scanner retry/cache/progress/reliability acceptance — CLOSED/PASS.
- #90: Vercel Deployment Economy — CLOSED/PASS/VERIFIED.
- #79 + PR #98: Portfolio multi-runnable common-window authority — CLOSED/PASS/PRODUCTION VERIFIED.

### #79 final production evidence

Merged PR #98 → `main@aba00c70215c451954487096b4d0b88fa50d48b0`.

Post-main:

- Full CI #596 PASS;
- genuine Vercel production deployment SUCCESS;
- production contract verification against `backteststock.chired.workers.dev` served exact merged SHA;
- raw history starts intentionally differed: SPY `2019-01-02`, QQQM `2020-10-13`;
- effective common window: `2020-10-13 -> 2021-03-31`;
- requested portfolios: 122 observations each;
- benchmark: 122 observations on same metrics/series interval;
- benchmark tail-risk: 121 observations;
- `common-runnable-portfolios-v1` warning present;
- final-balance / total-return identity PASS.

Evidence-only PR #100 was closed without merge after the production check. Internal #97 was also closed without merge after #98 completed.

Cloudflare was not redeployed for #98 because changed paths did not match its production deploy trigger; the existing Worker proxies the Vercel backend.

---

## 3. Primary Active Batch — #78 Scanner → Optimizer Handoff

Issue #78: user-selected Scanner rows do not reliably auto-populate the Optimizer when the source scan job was restored from an older persisted `backteststock-scan-job-v3` shape.

Priority: **HIGH user-visible workflow regression / implementation-ready.**

Initial risk: **R1**, unless implementation changes persisted schema/version or broader optimizer semantics.

### Root Cause

Historical `scan-job-v3` records can use legacy month fields:

```text
startYear / startMonth
endYear / endMonth
```

Scanner restoration in `public/app.js` normalizes them to canonical:

```text
startDate / endDate
```

The manual handoff is then written from this normalized in-memory Scanner job.

Optimizer startup in `public/exhaustive-optimizer.js`, however, reads the raw persisted scan job and validates provenance without applying the same normalization authority.

Result:

```text
Scanner / manual handoff: canonical dates
Optimizer source job:     legacy/raw dates
              ↓
strict provenance comparison fails
              ↓
selected tickers are not loaded
```

This is a **cross-page migration-authority split**, not an optimizer-math defect.

### Required correction

Use **one shared pure scan-job payload normalization authority** for Scanner restoration and Optimizer manual-handoff validation.

Required behavior:

- optimizer normalizes raw persisted scan job before provenance comparison;
- legacy and current-format scan jobs resolve to the same canonical date interpretation;
- exact selected tickers populate in manual mode;
- canonical start/end and benchmark populate;
- provenance remains fail-closed for sourceJobId, ticker membership, coverage threshold, benchmark, valuation currency and source eligibility;
- ordinary Optimizer mode remains unchanged;
- optimizer quantitative formulas/engine remain unchanged.

Do not:

- bypass `validatedManualHandoff()`;
- ignore sourceJobId;
- fall back to the full scan pool when manual validation fails;
- weaken membership/coverage/provenance checks;
- solve only in obsolete `public/optimizer.js`;
- redesign persistence unless new evidence requires it.

### Mandatory verification

1. legacy `scan-job-v3` migration boundary: restore Scanner → select rows → open `/optimizer.html?mode=manual` → exact selected tickers + canonical dates + benchmark;
2. fresh current-format handoff still works;
3. stale sourceJobId fails closed;
4. ticker outside source scan fails closed;
5. below-threshold ticker fails closed;
6. ordinary optimizer mode retains current behavior;
7. shared normalizer parity: any payload Scanner accepts as resumable/restored must receive the same canonical date/provenance interpretation before Optimizer validation;
8. relevant browser/E2E workflow passes end to end.

### Exit gate

Do not close #78 merely because the selected list appears once. Before convergence, independently check for migration/provenance regressions that could break restored jobs or contaminate the next Refinery/Phase 6 workflow.

---

## 4. Immediate Next Functional Batches

### F1 — #78 Scanner → Optimizer handoff

**PRIMARY NEXT / implementation-ready.** Restore the promised user workflow with shared normalization authority.

### F2 — Phase 6 / #77 Remove-One / Add-One / Replace-One MVP

**NEXT AFTER #78 is safely complete.** Issue #77 is the frozen/saturated specification; do not restart broad planning.

Minimal functional objective:

- explicit Remove-One / Add-One / Replace-One operations;
- one authoritative union market-data fetch;
- one frozen global experiment common sample;
- experiment baseline and variants use identical effective samples;
- deterministic structural deltas using existing quant primitives;
- localized fail-closed behavior for experiment-only data failure;
- no hidden weighting, ranking, sizing or recommendation score;
- usable Refinery UI for submitting and reading the three operations.

Before starting, re-check that no material #78 defect would break Scanner/Optimizer inputs or provenance used by downstream workflow.

### F3 — Core workflow integration

After Phase 6 MVP, validate the actual user journey rather than automatically starting another methodology phase:

```text
Scanner
-> selected tickers
-> Optimizer
-> candidate portfolio
-> Portfolio backtest
-> Refinery structural analysis / marginal experiments
```

Fix material cross-module handoff/correctness defects discovered by this journey before adding dependent capabilities.

### Phase 7+

**CONDITIONAL BACKLOG, not automatic sequence.**

Promote only when a concrete functional need/evidence justifies it. Examples may include OOS/walk-forward validation, selection, sizing, Exhaustive integration or point-in-time data, but completion of the previous numbered phase alone is not sufficient reason.

---

## 5. Locked Decisions Still Relevant

### D-01 — Governance V3 frozen

`AI_PROJECT_PLAYBOOK.md` is the engineering governance authority. Do not rewrite it for feature-specific lessons without a documented reopen condition.

### D-02 — Documentation quality

`docs/PROJECT_DOCUMENTATION_POLICY.md` owns documentation authority/freshness/lifecycle/duplication/handoff quality.

Documentation exists to prevent project memory loss and distortion, not to become a parallel project.

### D-03 — Completion before convergence

Fix necessary root cause + coupled material blockers + acceptance evidence first; converge only after no known material defect remains that invalidates acceptance or predictably contaminates dependent next work.

### D-04 — One Primary Active Batch

Keep one core implementation lane. Supporting review/research/docs may run only when they do not create a competing implementation stream.

### D-05 — Deployment Economy

`internal-*` branches suppress automatic Vercel Preview. Promote a converged implementation to deliberate `candidate-*` only when genuine deployment evidence is required. Keep `main` production deployment enabled.

### D-06 — Phase-close freshness

Before CLOSED/PASS, reconcile applicable remote open PRs, unresolved blocker reviews/threads, deployment/runtime evidence and remaining material debt. Every explicit blocker must be MERGED, SUPERSEDED WITH EVIDENCE, or still OPEN.

### D-07 — Quant/data authority

- `TWDHistoryService`: audited market history / TWD valuation authority.
- `apps/api/app/portfolio/`: Portfolio ledger/metrics/comparison/analytics composition.
- `apps/api/app/research/` + `apps/api/app/refinery/`: ResearchDataset / Refinery evidence composition.
- `apps/api/app/quant/`: pure validated quantitative primitives.
- browser: presentation/workflow only; no second quantitative authority.

---

## 6. Open Root Causes / Risks / Technical Debt

### Open root cause

**RC-78 / R1:** Scanner normalizes legacy persisted scan-job dates while Optimizer validates the raw persisted job. Fix with shared pure normalization authority; preserve strict provenance.

### Functional risks to watch

- A UI-only #78 patch could hide the migration split while restored jobs remain broken.
- Weakening provenance to make manual mode populate could silently load the wrong source universe.
- Phase 6 must not begin on top of an unresolved #78 input/handoff defect.
- Phase 6 common-sample work must not silently change existing Phase 3–5 baseline semantics.
- New feature work must not introduce browser-side quantitative formulas parallel to backend authority.
- Phase closure must not hide a known material blocker simply to keep the roadmap moving.

### Technical debt — BACKLOG unless promoted by evidence

- **Scanner presentation-only residual from #80:** on a retry-requeued chunk, displayed batch range is inferred from `resultMap.size + 1`; an actual 401–500 request can therefore temporarily be labelled 301–400. Confirmed closure evidence says this does **not** change scan execution, settled/success/failure counts or resume semantics. Keep BACKLOG unless new evidence raises functional severity.
- Yahoo request amplification / metadata fan-out and scanner diagnostics hardening;
- instrument/security master and regional factor routing;
- traceable theme provider/taxonomy;
- distributed Refinery rate limiting;
- Cloudflare timeout-vs-retry-budget formal alignment;
- GitHub Actions immutable-SHA pinning review;
- historical Actions registry cleanup where supported;
- single-portfolio + shorter-benchmark strict-comparison policy separate from completed #79;
- point-in-time Universe/fundamentals for a future PIT phase.

Deferred until evidence requires them:

- Phase 6 variant-level full Phase 5 bootstrap;
- persistent experiment plans;
- automatic selection/ranking/sizing;
- OOS claims from in-sample evidence.

Rejected approaches remain:

- branch/Vercel bypass;
- no-op deployment trigger commits;
- scanner chunk-size workaround instead of orchestration RCA;
- hand-merging generated bundles;
- magic scores / hidden recommendation or sizing logic;
- broad Portfolio rewrite without evidence.

---

## 7. Exact Resume Point

After this documentation-convergence change is accepted:

1. re-query current `main`, Issue #78 and open PR state;
2. create a clean `internal-*` branch from exact current main for #78;
3. inspect existing Scanner date normalization and all Optimizer/manual-handoff consumers before modifying code;
4. first add a deterministic regression reproducing the legacy-v3 restored-job boundary that current tests miss;
5. extract/reuse the smallest shared pure scan-job payload normalizer;
6. apply it to both Scanner restoration and Optimizer provenance validation;
7. preserve strict validation; do not add fallback-to-full-scan behavior;
8. run focused unit/browser tests plus relevant broad CI;
9. independently falsify migration/provenance behavior and inspect for any material defect that would contaminate downstream work;
10. if clean, promote/merge/deploy with risk-proportional gates and verify the user-visible handoff;
11. close #78 only after completion-before-convergence conditions are satisfied;
12. then begin only Phase 6 MVP scope from Issue #77.

**Primary Functional Batch after this handoff lands = #78 Scanner → Optimizer manual handoff.**
