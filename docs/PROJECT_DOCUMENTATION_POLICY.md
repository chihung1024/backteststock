# Project Documentation Policy

Status: **Current documentation-governance contract**.

Purpose: prevent stale handoff state, duplicated authorities, contradictory methodology text and phase-to-phase context loss. This file does not replace `AI_PROJECT_PLAYBOOK.md`; it defines how repository documents divide responsibilities and how conflicts are resolved.

## 1. Documentation classes

### Engineering governance

`AI_PROJECT_PLAYBOOK.md` owns engineering process: planning, investigation, implementation, validation, review, Git/PR, deployment and handoff. It is intentionally stable and frozen under V3.0 unless a documented Reopen Condition occurs.

### Product / architecture overview

`README.md` owns durable product, architecture, run/test/deploy orientation. It must avoid volatile PR/check details.

### Live execution / handoff state

`to_do_update_list.md` owns current stable state, active Phase/Batch, blockers, decisions, risks and exact next action. It is the repository's live handoff snapshot, not the source of truth for mutable remote state.

### Versioned semantic contracts

`docs/quant/`, `docs/research/` and other named contract documents own externally observable or quantitative semantics. Contract/version changes must align docs, code constants, tests/fixtures and public schema where applicable.

### ADRs

`docs/adr/` records structural decisions, rationale, trade-offs and reopen conditions.

### Historical records

Historical rollout/migration material may remain only when it still provides unique audit value. A historical file must not masquerade as live status or current contract. If Git history already preserves the evidence and the live file adds no unique operational/semantic value, remove it from the active tree.

## 2. Truth precedence

### What is running/open/green right now?

1. Current GitHub/Vercel/Cloudflare remote state.
2. `to_do_update_list.md` snapshot.
3. README / historical prose.

### What should a calculation/API mean?

1. Accepted versioned contract / ADR.
2. Corresponding tests/reference fixtures.
3. Implementation.

Contract/code drift is an engineering defect; do not silently choose one side without evidence.

### How should an Agent work?

1. `AI_PROJECT_PLAYBOOK.md`.
2. Current Batch constraints in `to_do_update_list.md`.
3. Phase-specific review plan/contract.

## 3. Freshness rules

Before important work, query current main/head, PR base/head/mergeability, required checks, reviews/threads, ruleset/protection and deployment/release state as applicable.

Update live handoff when Phase/Batch state, root cause, locked decision, methodology/schema version, blocker, verification evidence or exact next action materially changes.

Before merge, verify README architecture, live roadmap, contract versions, test evidence, non-goals, deferred findings, rollback/recovery and exact next action.

## 4. Version discipline

Bump methodology/schema versions when externally observable meaning changes, including return/calendar policy, dataset/hash identity, clustering/bootstrap semantics, factor sample/applicability, verdict eligibility or public response fields.

A version bump is incomplete unless applicable locations align:

```text
contract document
<-> code constant
<-> tests / fixtures
<-> API methodology/schema output
<-> UI type/label
<-> to_do_update_list.md
```

Do not bump for prose-only clarification with unchanged semantics.

## 5. Historical integrity and cleanup

Preserve meaningful root-cause/decision evidence, but do not keep redundant live files solely because they once existed.

Allowed:

- compress completed Phase detail into a historical summary;
- rely on Git history for obsolete rollout drafts;
- remove superseded documents when a current authority exists;
- keep a historical document only when it contains unique evidence still needed for audit or future decisions.

Not allowed:

- delete unresolved technical debt without resolve/reject decision;
- rewrite old contracts so prior semantics cannot be reconstructed;
- retain stale status text that can mislead future Agents simply for perceived auditability.

## 6. Writing quality

Documents should be specific, scoped, evidence-based, fail-closed, navigable, durable, actionable and auditable. Prefer canonical links over duplicated volatile status prose.
