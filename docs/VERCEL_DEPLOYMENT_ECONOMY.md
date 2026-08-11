# Vercel Deployment Economy

Status: **Current operational policy.** This document controls how AI-assisted development uses Vercel Preview deployments without weakening required deployment validation.

## 1. Purpose

Vercel Git integration deploys branch pushes by default. In an AI-assisted repository, many small remote commits, diagnostic commits, temporary workflow commits and generated-asset sync commits can consume Preview deployment quota without adding production confidence.

The policy is therefore:

> **Iterate freely in CI; deploy only deliberate candidates.**

This is a deployment-economy control, not a reduction in merge quality. A required Vercel check must still be genuinely green on the final merge candidate whenever branch protection requires it.

## 2. Branch topology

### `internal-*`

Use for implementation iterations, RCA, temporary diagnostics, generated-asset synchronization, dependency/security evidence collection and review fixes before a Vercel candidate exists.

`vercel.json` disables automatic Vercel deployment for `internal-*` branches.

Rules:

- do not treat an `internal-*` branch as a merge candidate;
- GitHub CI / focused CI remain the primary iteration feedback;
- temporary workflow/write capability must be removed before promotion;
- branch may contain multiple auditable commits when that improves RCA/history;
- do not require a Vercel status on an internal validation branch.

### `candidate-*`

Use only after the internal Batch has converged to a coherent candidate.

Rules:

- Vercel deployment remains enabled;
- no temporary workflow or diagnostic helper may remain;
- final diff/scope/risk must already be known;
- the candidate receives the required Vercel Preview and exact-head merge gates;
- source changes after candidate promotion are allowed only for a real blocker; such a fix creates a new exact candidate and requires applicable revalidation.

### `main`

`main` remains the production branch. Merge/push to `main` may create the production Vercel deployment and must follow normal post-main verification.

## 3. Candidate promotion

Because Vercel deploys on Git pushes, creating a branch name alone is not sufficient evidence that a Preview deployment will exist.

Preferred promotion flow:

```text
main / known base
↓
internal-<batch>
↓
implement + CI + RCA + cleanup
↓
internal candidate PASS
↓
candidate-<batch>
↓
one deliberate candidate push / promotion commit
↓
Vercel Preview + exact-head gates
↓
review / backup / merge
↓
main production deploy
```

A tree-identical promotion commit is permitted only when it is the deliberate transition from a Vercel-disabled `internal-*` branch to a Vercel-enabled `candidate-*` branch and the commit records that promotion boundary. It must not be used as a quota retry or to manufacture a green status.

If the repository tooling can produce the candidate as one meaningful source commit instead, prefer that over a tree-identical promotion commit.

## 4. Deployment budget

Normal target per Batch:

- internal iterations: **0 Vercel deployments**;
- first final candidate: **1 Preview deployment**;
- material blocker fix after candidate review: normally **at most 1 additional Preview**;
- merge to `main`: **1 production deployment**.

This is an operating target, not a numeric correctness gate. Exceed it only when additional deployment evidence prevents a concrete failure mode.

## 5. Remote commit economy

When the available GitHub tooling would otherwise create one remote commit per file, prefer one atomic tree commit for a coherent multi-file change:

```text
create blobs
→ create one tree
→ create one commit
→ fast-forward branch ref
```

Do not split a coherent Batch into multiple deploy-enabled commits merely because the connector exposes file-by-file mutation APIs.

Multiple commits remain valid when they materially improve rollback, RCA or auditability; keep them on `internal-*` until candidate promotion whenever possible.

## 6. Forbidden quota workarounds

Do not:

- create empty/no-op commits only to retrigger Vercel;
- change unrelated files to obtain another Preview;
- remove or bypass the required Vercel check because quota is exhausted;
- force-push protected history to reduce deployment count;
- deploy an unrelated local file tree and treat it as the Git candidate's required status;
- repeatedly toggle Draft/Ready as a deployment retry mechanism.

A platform quota failure is classified as an external CI/deployment failure, not an application defect.

## 7. Quota exhaustion procedure

When Vercel reports a rate/deployment quota failure:

1. freeze the exact candidate SHA;
2. finish all non-Vercel evidence that can be completed safely;
3. do not create a retry-only commit;
4. wait for quota recovery or use a supported exact-Git-SHA redeploy path;
5. re-query the required status on the same candidate;
6. merge only after the required Vercel context is genuinely successful.

If manual intervention is required, use Vercel's deployment UI to create/redeploy the exact Git commit or branch candidate; verify the deployment metadata matches the expected SHA before accepting it.

## 8. `ignoreCommand`

Path-based Vercel ignored-build logic may be evaluated later as a second-layer optimization, but it is not the primary control here. Do not rely on it until its interaction with this repository's required GitHub Vercel status and quota accounting is verified end to end.

## 9. Validation of this policy

A change to this policy or `git.deploymentEnabled` is deployment-governance relevant and should be treated as R2 when it changes which branches deploy or which deployment evidence is required.

Before merging a policy change:

- validate `vercel.json` syntax/configuration;
- prove `internal-*` does not create an automatic Vercel Preview;
- prove the promoted `candidate-*` path does create the required Preview;
- confirm `main` production deployment remains enabled;
- confirm branch protection still requires genuine deployment evidence where intended.

## 10. Reopen condition

Revisit this policy only if there is evidence of one of the following:

- internal branches still consume avoidable Vercel deployment quota;
- candidate branches cannot obtain the required status;
- a Vercel product/configuration change invalidates the branch rules;
- the repository moves to an explicit GitHub-Actions-controlled Vercel deployment model;
- the current deployment budget materially blocks safe delivery.
