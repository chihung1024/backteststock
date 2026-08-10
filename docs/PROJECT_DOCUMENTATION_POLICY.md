# Project Documentation Policy

Status: Repository documentation-governance contract.

Purpose: prevent stale handoff state, duplicated authorities, contradictory methodology text and phase-to-phase context loss. This file does not replace `AI_PROJECT_PLAYBOOK.md`; it defines how project documents divide responsibilities and how conflicts are resolved.

## 1. Documentation classes

### A. Engineering governance

**File:** `AI_PROJECT_PLAYBOOK.md`

Answers: how engineering work must be planned, investigated, implemented, tested, reviewed, committed, deployed and handed off.

Characteristics:

- highest repository engineering-process authority;
- intentionally stable;
- not a live status tracker;
- change only when governance itself changes.

### B. Product / architecture overview

**File:** `README.md`

Answers: what the system is, how major components fit together, how to run/test/deploy it, and where deeper documents live.

Characteristics:

- should remain useful to a new developer;
- must avoid volatile current-PR details;
- must not be treated as a project-progress ledger.

### C. Live execution / handoff state

**File:** `to_do_update_list.md`

Answers: what is stable, what is active now, why, what is blocked, what evidence exists, and exactly what the next Agent must do.

Required sections:

- Project Status
- Stable State
- Architecture Notes
- Master Plan
- Current Phase / Batch
- Change Log
- Decision Log
- Root Cause Log
- Known Issues
- Technical Debt
- Deferred / Rejected Candidates
- Risks
- Next Actions / Exact Resume Point

This file must be updated inside every implementation PR before a phase-ending merge and again in phase closeout.

### D. Versioned semantic contracts

Examples:

- `docs/quant/*.md`
- `docs/research/RESEARCH_DATASET_V1.md`
- `docs/research/REFINERY_API_V1.md`
- `docs/research/REFINERY_UI_V1.md`
- `docs/research/REFINERY_CLUSTERING_V1.md`

Answers: exact externally observable or quantitative semantics.

Rules:

- version identifiers must match code constants/tests where the contract is implemented;
- changes to methodology/schema semantics require explicit version review;
- do not silently rewrite history to make old versions appear to have always behaved like new versions;
- additive later-phase behavior should be documented as an extension while preserving the historical baseline contract.

### E. ADR / architecture decisions

**Location:** `docs/adr/`

Answers: what architectural decision was made, alternatives, rationale, trade-offs and reopen conditions.

Use an ADR when the decision is structural and likely to outlive one Phase.

### F. Review / convergence plans

Examples: `docs/research/PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md`.

Answers: what evidence reopened a decision, what must change before merge and what is deliberately deferred.

Rules:

- a review plan is not itself production methodology authority;
- once its amendments are accepted, the authoritative contract/code/tests must be updated together;
- resolved review plans remain useful as audit history and should be marked CLOSED rather than deleted.

## 2. Truth precedence by question type

There is no single universal precedence order; use the authority appropriate to the question.

### "What is running / open / green right now?"

1. Current GitHub/Vercel/Cloudflare remote state.
2. `to_do_update_list.md` snapshot.
3. README / historical phase prose.

If remote and roadmap conflict, remote state is the operational fact and the roadmap is stale until corrected.

### "What should this calculation/API mean?"

1. Accepted versioned contract / ADR.
2. Corresponding tests/reference fixtures.
3. Implementation.

If code and accepted contract disagree, do not silently declare code authoritative. Classify contract/code drift, determine which side is correct from evidence, then update version/code/tests together.

### "How should an Agent work?"

1. `AI_PROJECT_PLAYBOOK.md`.
2. Current Batch rules in `to_do_update_list.md`.
3. phase-specific review plan.

## 3. Freshness requirements

### Before starting work

Query and record, as applicable:

- latest `main` SHA;
- current branch/head SHA;
- open PR state and base/head;
- required checks;
- reviews / unresolved threads;
- active ruleset/protection state;
- latest release/backup/deployment state;
- current phase/batch in `to_do_update_list.md`.

A new conversation/session does not create a new project plan when repository state already contains one.

### During an implementation PR

Update the live roadmap when any of these materially changes:

- phase/batch state;
- root cause;
- locked decision;
- methodology/schema version;
- blocker;
- required verification evidence;
- next exact action.

Do not wait until closeout if the roadmap has already become materially false.

### Before merge

Perform a documentation integrity review:

1. README still describes the architecture accurately.
2. live roadmap matches remote PR/check/review state.
3. contract versions match code constants and public schema.
4. tests named as evidence actually exist and pass.
5. non-goals still match the Phase boundary.
6. deferred findings are recorded rather than lost.
7. exact rollback / recovery point is known.
8. exact next action is unambiguous.

## 4. Contract version discipline

Bump a methodology/schema contract when an externally observable semantic meaning changes, including examples such as:

- return/calendar policy;
- dataset identity/hash semantics;
- clustering distance/linkage/cut/stability/bootstrap semantics;
- seed identity that changes deterministic output;
- factor sample/alignment/applicability policy;
- verdict thresholds or evidence eligibility;
- API response schema with new externally observable fields.

Do not bump merely for prose clarification that does not change semantics.

A version bump is incomplete unless all applicable locations are aligned:

```text
contract document
<-> code constant
<-> tests / fixtures
<-> API methodology/schema output
<-> UI type/label if externally visible
<-> to_do_update_list decision/change log
```

## 5. Historical integrity

Do not erase prior phase history when reorganizing documentation.

Allowed:

- move detailed old execution records into a clearly labelled historical section;
- compress repeated prose while retaining PR/merge/backup/root-cause/decision evidence;
- add links to Git history for exhaustive detail.

Not allowed:

- replacing old failure history with only the final PASS state;
- removing a root-cause record because the bug is fixed;
- rewriting an old contract so the previous semantics can no longer be reconstructed;
- deleting deferred technical debt without a documented reject/resolve decision.

## 6. Documentation drift classification

Treat meaningful stale documentation as a real engineering defect.

### Symptom

A file states a phase, version, check, decision or behavior that is no longer true.

### Failure point

The consuming Agent/developer receives incorrect context.

### Root cause categories

- implementation advanced without documentation update;
- multiple files claim the same authority;
- version bump updated code but not docs;
- temporary workaround text became permanent;
- closeout state was not propagated.

### Prevention

- one live roadmap;
- one semantic authority per contract;
- explicit cross-links instead of duplicated long status prose;
- pre-merge documentation integrity review;
- post-main closeout.

## 7. Writing quality standard

Project documents should be:

- **specific**: exact file, version, SHA, status or condition when material;
- **scoped**: distinguish current Phase from future ideas;
- **evidence-based**: separate observed fact, inference and proposal;
- **fail-closed**: never convert unknown/unverified into PASS;
- **navigable**: clear headings, short tables, canonical links;
- **durable**: avoid volatile facts in README when they belong in the live roadmap;
- **actionable**: every blocker has a required resolution and owner Batch;
- **auditable**: decisions/root causes retain evidence and reopen conditions.

## 8. Research-document index

The canonical research-document map is `docs/research/README.md`. New research contracts or review plans must be added there in the same Batch that creates them.
