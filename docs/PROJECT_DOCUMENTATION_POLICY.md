# Project Documentation Policy

Status: **Current documentation-governance contract**.

Purpose: keep repository documentation accurate, minimal, authoritative and useful to implementation. Documentation exists to support product correctness, reproducibility, operation, recovery and future handoff; it must not become a parallel project that competes with functional delivery.

This file does not replace `AI_PROJECT_PLAYBOOK.md`. The Playbook owns engineering governance and risk-proportional review. This policy owns documentation authority, quality, freshness, duplication, lifecycle and handoff hygiene.

> **Functional-first rule:** documentation and planning must help the project complete necessary functional work correctly. **Convergence means finish the necessary work first, remove or explicitly isolate material functional blockers, then stop unnecessary expansion. It does not mean stop early, accept a known major bug, or leave a defect that is likely to contaminate the next functional batch.**

---

## 1. Documentation authority map

### `AI_PROJECT_PLAYBOOK.md` — engineering governance

Owns planning, investigation, implementation, validation, review, Git/PR, deployment, rollback and handoff rules.

It is intentionally stable/frozen. Feature-specific lessons belong in contracts, ADRs, tests or the live handoff unless a documented Playbook reopen condition exists.

### `README.md` — durable product/architecture orientation

Owns:

- what the product does;
- major runtime components;
- how to develop, run, test and deploy;
- links to canonical deeper documents.

Do not use README as a live PR/check/deployment status page.

### `to_do_update_list.md` — live execution/handoff snapshot

Owns only the information needed to resume current work correctly:

- current functional goal;
- current stable production baseline;
- one Primary Active Batch;
- blocker, if any;
- still-relevant locked decisions;
- unresolved root causes / risks / technical debt;
- short next-functional roadmap;
- exact resume action.

It is **not** an append-only project diary. Detailed completed execution history belongs in Git/PR/Issue history unless unique evidence remains necessary for a future decision.

### Versioned contracts — semantic authority

Named API/data/quant/research/persistence/migration documents own accepted semantics. Applicable code constants, tests/fixtures, schema/methodology output and UI labels must agree with them.

### ADRs — durable structural decisions

Use ADRs only for durable, non-obvious architecture decisions whose rationale/trade-offs/reopen conditions are likely to matter again. Ordinary implementation detail belongs in code/tests.

### Runbooks — operational authority

Deployment, migration, rollback and recovery runbooks own executable procedures. Prefer verified commands, prerequisites, failure conditions and rollback steps over narrative prose.

### Historical documents

Keep only when they preserve unique audit/decision value. Historical material must be clearly non-current. If Git/PR/Issue history already preserves all useful evidence, remove or archive redundant active-tree prose.

---

## 2. Truth precedence

### Mutable operational state

For questions such as what is open, merged, green or deployed now:

1. current remote truth: GitHub / Vercel / Cloudflare / runtime;
2. `to_do_update_list.md` snapshot;
3. README / historical prose.

Important actions must re-query applicable remote truth instead of trusting a stale snapshot.

### Semantic meaning

For what an API/calculation/data contract should mean:

1. accepted versioned contract / ADR;
2. corresponding tests/reference fixtures;
3. implementation.

Contract/test/code drift is an engineering defect; do not silently choose one side.

### Agent execution

1. `AI_PROJECT_PLAYBOOK.md`;
2. current constraints in `to_do_update_list.md`;
3. accepted phase/feature contract where applicable.

---

## 3. Documentation quality standard

A document should satisfy the dimensions relevant to its class:

- **Accurate** — current claims reflect accepted semantics/current evidence, or are clearly historical/proposed.
- **Authoritative** — the reader can identify the canonical source and distinguish authority from supporting explanation.
- **Scoped** — one document does not absorb responsibilities already owned elsewhere.
- **Actionable** — live/runbook material states the next action, trigger, expected result or failure condition.
- **Verifiable** — important claims are traceable to code, tests, contracts, Issues/PRs, deployments or queryable remote state.
- **Durable** — stable docs avoid unnecessary volatile SHAs, PR/check numbers and temporary status.
- **Navigable** — link to canonical detail instead of copying large blocks.
- **Concise** — preserve the minimum information required for correctness and handoff.

More prose is not higher quality.

---

## 4. Freshness and lifecycle

Documents conceptually move through:

```text
PROPOSED -> CURRENT -> SUPERSEDED / HISTORICAL -> REMOVED
```

This is a lifecycle model, not a requirement to add status metadata to every file.

Do not leave obsolete material looking current, and do not maintain two CURRENT authorities for the same semantic question.

Update `to_do_update_list.md` only when a material handoff fact changes, including:

- Primary Active Batch / current functional goal;
- blocker or root-cause classification;
- still-relevant locked decision;
- methodology/schema/contract version affecting current work;
- production acceptance result;
- exact resume action;
- roadmap priority.

Do **not** update it for every commit, temporary hypothesis or intermediate CI run.

Before declaring a Phase/Issue/functional batch complete, reconcile applicable remote Issue/PR state, unresolved blocker reviews/threads, runtime verification, remaining actionable debt and next functional priority.

A remote item already closed/superseded must not remain listed as NEXT merely because the handoff snapshot is stale.

---

## 5. Live handoff compaction

Keep `to_do_update_list.md` small enough that a future Agent can understand the project state quickly.

Preferred structure:

```text
1. Current Functional Goal
2. Stable Production State
3. Primary Active Batch
4. Immediate Next Functional Batches
5. Locked Decisions Still Relevant
6. Open Root Causes / Risks / Technical Debt
7. Exact Resume Point
```

Compress completed phase detail when:

- the work is complete;
- no reopen condition applies;
- detailed evidence is reconstructable from Git/PR/Issue history;
- future work does not depend on the detail itself.

Never compact away an unresolved blocker, migration obligation, correctness limitation or deferred decision that still affects future work.

---

## 6. Duplication control

Default: **link, do not copy**.

Duplicate information only when local visibility is necessary for safe execution, the content is deliberately frozen/versioned, or automation validates the copies remain aligned.

Avoid duplicating:

- volatile PR/check/deployment state across README, TODO and phase docs;
- methodology formulas across prose files;
- the same roadmap in README, TODO and Issues;
- long Issue/PR histories inside live handoff;
- CI evidence already preserved remotely unless needed to justify an acceptance decision.

When duplication is necessary, identify the canonical authority.

---

## 7. Version discipline

Bump methodology/schema versions when externally observable meaning changes, including return/calendar policy, dataset/hash identity, quantitative methodology, factor sample/applicability, eligibility semantics, persistence interpretation or public response fields.

A semantic version change is incomplete until all applicable surfaces agree:

```text
canonical contract
<-> code constant
<-> tests / fixtures
<-> API methodology/schema output
<-> UI type/label
<-> live handoff when current execution depends on it
```

Do not bump versions for prose-only clarification with unchanged semantics.

---

## 8. Completion-before-convergence discipline

**Convergence is an exit discipline, not an early-stop rule.**

For a functional Batch, Phase or defect lane, first complete the work required to make the intended capability correct and safe. Only after that should scope be narrowed and optional improvement stop.

Before declaring the work converged / closed, verify as applicable:

1. the intended user-visible or system capability works through its relevant end-to-end path;
2. the demonstrated root cause is corrected rather than masked by a workaround;
3. regressions protecting the failure mode and adjacent high-risk behavior pass;
4. required runtime / production verification passes when deployment behavior matters;
5. newly discovered defects with material functional impact are either fixed in the current lane when they are necessary to safe completion, or explicitly isolated as a blocking next item with evidence;
6. no known unresolved defect is likely to invalidate the just-completed acceptance evidence or predictably break the immediately following functional work;
7. remaining findings are genuinely lower-priority enhancements, bounded debt or unrelated work, and are classified `NEXT / BACKLOG / REJECT` rather than silently abandoned.

Do **not** use “scope control”, “minimum change”, “functional-first” or “avoid over-engineering” as justification to knowingly leave a major correctness, reliability, data-integrity or workflow defect inside the capability being closed.

Conversely, once the above completion conditions are met, do not continue refactoring, documenting, redesigning or adding features merely because further improvement is possible.

The intended sequence is:

```text
Understand sufficiently
-> fix necessary root cause and coupled blockers
-> verify functional completeness
-> record remaining bounded debt
-> converge
-> move to the next functional goal
```

---

## 9. Functional-first roadmap documentation

Roadmaps describe **product/user capability outcomes**, not process activity.

Prefer items such as:

```text
Fix Scanner -> Optimizer handoff
Enable Remove/Add/Replace structural experiments
Verify the end-to-end research workflow
```

Do not make work NEXT merely because an old sequential roadmap says it comes next.

Promote future work to NEXT only when there is a concrete functional reason, such as:

- a current workflow is broken;
- a correctness/reliability defect blocks use;
- an existing capability lacks a necessary complementary function;
- measured evidence supports a material product benefit;
- an operational constraint blocks safe delivery;
- a newly discovered material defect would otherwise contaminate the next functional batch.

Otherwise keep it BACKLOG even if a prior plan listed it sequentially.

Planning/review/documentation activity is supporting work, not a product milestone by itself.

---

## 10. Documentation review and risk

Use the Playbook's existing risk classification and independent-review rules; do not create a second review system here.

Additional documentation-specific review questions for material changes:

1. Is this the correct canonical document for the claim/decision?
2. Does it contradict another CURRENT authority?
3. Does a semantic change require corresponding code/tests/schema/version changes?
4. Could the wording cause unsafe or incorrect implementation/operation?
5. Is the change adding process/document volume without reducing a real risk?
6. Are failure, rollback or reopen semantics explicit where consequences justify them?
7. Could a future Agent misread “converge / scope control / functional-first” as permission to close work with a known material functional defect?

For governance/contracts/runbooks, independent review should attempt to **falsify** the proposal rather than only proofread it.

Docs-only does not automatically mean low risk; risk follows the decision/behavior the document controls, as defined by the Playbook.

---

## 11. Documentation Definition of Done

A documentation change is complete when all applicable checks pass:

- correct authority/file chosen;
- claims verified against the appropriate source of truth;
- no unresolved contradiction with another current authority;
- unnecessary volatile detail removed;
- canonical links/references used where duplication is unnecessary;
- required semantic version alignment completed;
- superseded text removed, archived or marked historical;
- live handoff changed only when a material handoff fact changed;
- next action explicit for live/runbook material;
- material functional blockers are not hidden or compacted away in the name of convergence;
- risk-appropriate review completed.

Docs-only production smoke is normally unnecessary unless the document directly controls a production procedure that cannot be safely validated another way.

---

## 12. Documentation debt and cleanup

Documentation debt is actionable when it creates a real risk, for example:

- stale status can cause the wrong work to start;
- contradictory contracts can cause incorrect implementation;
- missing runbook information can cause deployment/recovery failure;
- duplicate authorities can drift;
- missing rationale makes a durable decision likely to be accidentally reversed;
- missing functional-blocker evidence can cause a future Batch to build on a known-bad foundation.

Classify findings with the normal `NOW / NEXT / BACKLOG / REJECT` system.

Do not create cleanup work solely for stylistic uniformity.

Allowed cleanup:

- compress completed phase detail;
- rely on Git history for obsolete rollout drafts;
- remove superseded documents when a current authority exists;
- retain historical files only when unique evidence remains useful.

Not allowed:

- delete unresolved technical debt without a resolve/reject decision;
- rewrite old contracts so prior semantics cannot be reconstructed;
- retain misleading stale status for perceived auditability;
- turn `to_do_update_list.md` into an append-only execution transcript;
- remove or downgrade a known material functional defect merely to make a phase appear converged.

---

## 13. Writing quality

Prefer direct statements, explicit status vocabulary, canonical links, exact failure/reopen conditions and deletion of obsolete prose.

Use tables only when they improve comparison. Use examples only when they clarify a contract or prevent likely misuse.

The target is:

> **minimum sufficient documentation with high decision value and low staleness risk, after necessary functional completeness has been achieved.**
