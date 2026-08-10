from __future__ import annotations

import re
import subprocess
from pathlib import Path

OLD_CLUSTER = "refinery-clustering-twd-2026-08-10.1"
NEW_CLUSTER = "refinery-clustering-twd-2026-08-10.2"
OLD_SCHEMA = "refinery-v1-2026-08-10.2"
NEW_SCHEMA = "refinery-v1-2026-08-10.3"


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one exact match, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all(path: str, old: str, new: str) -> int:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count:
        file_path.write_text(text.replace(old, new), encoding="utf-8")
    return count


def regex_once(path: str, pattern: str, replacement: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, found {count}")
    file_path.write_text(updated, encoding="utf-8")


def copy_from_review_branch(path: str) -> None:
    content = subprocess.check_output(
        ["git", "show", f"refs/remotes/origin/docs/phase5-convergence-plan:{path}"],
        text=True,
    )
    Path(path).write_text(content, encoding="utf-8")


# Bring in only the Phase-5-specific reviewed documentation baseline from #66.
subprocess.run(
    [
        "git",
        "fetch",
        "origin",
        "docs/phase5-convergence-plan:refs/remotes/origin/docs/phase5-convergence-plan",
    ],
    check=True,
)
for document in (
    "docs/research/REFINERY_CLUSTERING_V1.md",
    "docs/research/REFINERY_API_V1.md",
    "docs/research/REFINERY_UI_V1.md",
):
    copy_from_review_branch(document)

# Runtime contract identities.
replace_once(
    "apps/api/app/quant/clustering.py",
    f'REFINERY_CLUSTERING_CONTRACT_VERSION = "{OLD_CLUSTER}"',
    f'REFINERY_CLUSTERING_CONTRACT_VERSION = "{NEW_CLUSTER}"',
)
replace_once(
    "apps/api/app/refinery/models.py",
    f'REFINERY_API_SCHEMA_VERSION = "{OLD_SCHEMA}"',
    f'REFINERY_API_SCHEMA_VERSION = "{NEW_SCHEMA}"',
)

# Give the already-implemented C policy one shared name and expose all corrected
# consumer policies through the audit-visible methodology payload.
relationships = "apps/api/app/refinery/relationships.py"
replace_once(
    relationships,
    '''FACTOR_CORROBORATION_UNAVAILABLE_REASON = (
    "unavailable_no_traceable_instrument_scope"
)''',
    '''FACTOR_CORROBORATION_UNAVAILABLE_REASON = (
    "unavailable_no_traceable_instrument_scope"
)
FACTOR_CORROBORATION_POLICY = "fail_closed_without_traceable_instrument_scope_v1"''',
)
replace_once(
    relationships,
    '"factor_corroboration_policy": "fail_closed_without_traceable_instrument_scope_v1",',
    '"factor_corroboration_policy": FACTOR_CORROBORATION_POLICY,',
)

phase5 = "apps/api/app/refinery/phase5_service.py"
replace_once(
    phase5,
    "    DEFAULT_FACTOR_MIN_MONTHS,\n    PRIMARY_CLUSTER_LINKAGE,",
    "    DEFAULT_FACTOR_MIN_MONTHS,\n    FACTOR_MONTHLY_RETURN_POLICY,\n    PRIMARY_CLUSTER_LINKAGE,",
)
replace_once(
    phase5,
    "from .relationships import THEME_UNAVAILABLE_STATUS, build_phase5_relationships",
    '''from .relationships import (
    FACTOR_CORROBORATION_POLICY,
    FACTOR_MODEL_SCOPE,
    THEME_UNAVAILABLE_STATUS,
    build_phase5_relationships,
)''',
)
replace_once(
    phase5,
    '''                "clustering_bootstrap_block_weeks": BOOTSTRAP_BLOCK_WEEKS,
                "clustering_bootstrap_seed_source": (
                    "effective_structural_weekly_sample_fingerprint_sha256"
                ),
                "factor_source": FRENCH_FACTOR_SOURCE,
                "factor_scope": "U.S.-factor co-movement diagnostic",
                "factor_minimum_monthly_observations": DEFAULT_FACTOR_MIN_MONTHS,''',
    '''                "clustering_bootstrap_block_weeks": BOOTSTRAP_BLOCK_WEEKS,
                "clustering_bootstrap_window_weeks": PRIMARY_STRUCTURAL_WINDOW_WEEKS,
                "clustering_bootstrap_seed_source": (
                    "effective_structural_weekly_sample_fingerprint_sha256"
                ),
                "factor_source": FRENCH_FACTOR_SOURCE,
                "factor_scope": FACTOR_MODEL_SCOPE,
                "factor_monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,
                "factor_relationship_sample_policy": "global_common_monthly_sample_v1",
                "factor_corroboration_policy": FACTOR_CORROBORATION_POLICY,
                "factor_minimum_monthly_observations": DEFAULT_FACTOR_MIN_MONTHS,''',
)

# Test/runtime literals follow the final public response schema. Historical prose
# is handled separately below and may retain labelled draft-version references.
for root in (Path("tests"), Path("apps")):
    for file_path in root.rglob("*"):
        if file_path.is_file() and file_path.suffix in {".py", ".ts", ".tsx", ".mjs", ".js"}:
            text = file_path.read_text(encoding="utf-8")
            if OLD_SCHEMA in text:
                file_path.write_text(text.replace(OLD_SCHEMA, NEW_SCHEMA), encoding="utf-8")

# Add explicit version/methodology evidence to an existing end-to-end service fixture.
phase5_test = "tests/test_refinery_phase5.py"
replace_once(
    phase5_test,
    '''    assert result["status"] == "ok"
    assert analysis["clustering"]["status"] == "ok"''',
    f'''    assert result["status"] == "ok"
    assert result["schema_version"] == "{NEW_SCHEMA}"
    assert result["contract_version"] == "refinery-v1"
    assert result["methodology"]["clustering_contract_version"] == "{NEW_CLUSTER}"
    assert result["methodology"]["clustering_bootstrap_window_weeks"] == 156
    assert result["methodology"]["factor_monthly_return_policy"] == "boundary-month-exclusion-v1"
    assert result["methodology"]["factor_relationship_sample_policy"] == "global_common_monthly_sample_v1"
    assert result["methodology"]["factor_corroboration_policy"] == "fail_closed_without_traceable_instrument_scope_v1"
    assert analysis["clustering"]["status"] == "ok"''',
)

# Clustering methodology contract: promote the reviewed baseline to corrected .2.
cluster_doc = "docs/research/REFINERY_CLUSTERING_V1.md"
replace_all(cluster_doc, OLD_CLUSTER, NEW_CLUSTER)
replace_once(
    cluster_doc,
    "Status: Phase 5 methodology contract. This phase adds deterministic hierarchical clustering and descriptive redundancy evidence on top of `ResearchDatasetV1`, `Risk Mathematics V1`, Refinery API V1 and Refinery UI V1.",
    "Status: **Phase 5 corrected methodology contract / P5-CORR A–D accepted implementation target.** This phase adds deterministic hierarchical clustering and descriptive redundancy evidence on top of `ResearchDatasetV1`, `Risk Mathematics V1`, Refinery API V1 and Refinery UI V1.",
)
regex_once(
    cluster_doc,
    r"### Deterministic seed\n\n[\s\S]*?\n### Bootstrap output",
    '''### Deterministic effective-input identity and seed

The bootstrap data identity is **not** `ResearchDataset.dataset_hash`. The exact stochastic input is prepared once by the shared quant path:

```text
numeric weekly returns
→ canonical sorted symbols
→ trailing bootstrap window (156 weeks by current policy)
→ +/-inf to NaN
→ complete-case row drop
→ exact effective bootstrap sample
```

`bootstrap_input_fingerprint_sha256` hashes only canonical symbols, exact timestamps and exact numeric values in that effective sample. Rows outside the structural window or rows removed by complete-case preparation do not change that fingerprint.

The deterministic seed hashes:

- exact bootstrap input fingerprint;
- `REFINERY_CLUSTERING_CONTRACT_VERSION`;
- primary linkage;
- flat-cut distance;
- bootstrap window;
- replicate count;
- block length.

The bootstrap primitive recomputes the effective fingerprint and fails closed if a caller supplies a fingerprint for a different sample. `ResearchDataset.dataset_hash` remains the independent full research-dataset identity and is never overwritten for bootstrap purposes.

### Bootstrap output''',
)
regex_once(
    cluster_doc,
    r"## 10\. Factor-implied relationship evidence\n[\s\S]*?\n## 11\. Economic-theme evidence",
    '''## 10. Factor-implied relationship evidence

Factor evidence is a **U.S.-factor co-movement diagnostic**. Computability, model scope and verdict corroboration eligibility are separate concepts.

### Boundary-month exclusion policy

Native daily returns are normalized and compounded by represented calendar month. The first and last represented calendar periods are excluded before factor regression because the repository does not have an exchange-calendar/instrument authority that can prove those boundary holding periods are complete. No pre-window return is fabricated to rescue the first month.

The current policy identifier is:

```text
boundary-month-exclusion-v1
```

A regression requires at least 36 observations **after** this exclusion.

### Individual diagnostics

USD quote currency plus sufficient native-return history can make the diagnostic mechanically computable. Per-asset evidence explicitly exposes:

- `factor_computable`;
- `factor_model_scope`;
- observations/effective start/end;
- intercept, beta vector and R-squared when available;
- `factor_corroboration_eligible` and reason.

USD denomination alone is **not** proof that this U.S. factor model is economically applicable to an instrument.

### One global relationship sample

Individual diagnostics may use their own valid samples. One returned systematic relationship matrix, however, uses exactly one global common monthly index across every individually valid matrix member and the factor frame.

On that exact common sample the implementation:

1. refits every relationship beta;
2. computes `Sigma_F` from the same factor rows;
3. computes `B Sigma_F B'` and systematic correlation;
4. exposes observations, effective start/end and common-sample fingerprint;
5. fails closed when the global common sample has fewer than the required observations.

No pairwise-cell sample switching is permitted in V1.

### Corroboration eligibility

The repository currently lacks a traceable instrument-scope authority (instrument type/incorporation/market/ADR/ETF/fund taxonomy) that can justify applying this model as verdict evidence. Therefore current Phase 5 uses:

```text
factor_corroboration_policy = fail_closed_without_traceable_instrument_scope_v1
factor_corroboration_eligible = false
reason = unavailable_no_traceable_instrument_scope
```

Diagnostic betas/R-squared/systematic correlation remain visible when computable, but factor evidence cannot upgrade a redundancy verdict while eligibility is false. A future traceable instrument authority may enable eligibility through a separately reviewed contract; Phase 5 does not build that authority.

## 11. Economic-theme evidence''',
)
replace_once(
    cluster_doc,
    "- factor-implied correlation >= 0.65 with both factor regressions valid;",
    "- factor-implied correlation >= 0.65 **and** `factor_corroboration_eligible = true`;",
)
replace_once(
    cluster_doc,
    "8. bootstrap output is deterministic for the same dataset hash/contract;",
    "8. bootstrap output is deterministic for the same exact effective-input fingerprint/methodology contract;",
)

# API contract: keep request v1, promote corrected response schema to .3.
api_doc = "docs/research/REFINERY_API_V1.md"
replace_once(
    api_doc,
    "Status: **Phase 3 baseline contract with Phase 5 additive analysis-schema extension**.",
    "Status: **Phase 3 baseline contract with corrected Phase 5 additive analysis-schema extension.** P5-CORR A–D semantics are now implementation-aligned; Phase 5 still awaits security/final validation and parent merge.",
)
replace_once(
    api_doc,
    "Current Phase 5 implementation is still under final review. Clustering/factor methodology is governed by `REFINERY_CLUSTERING_V1.md` plus the active `PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md`; this API document defines transport/schema/fail-closed semantics, not the statistical thresholds themselves.",
    "Corrected Phase 5 clustering/factor semantics are governed by `REFINERY_CLUSTERING_V1.md`; `PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md` records the resolved M1–M4 review and remaining release gates. This API document defines transport/schema/fail-closed semantics, not universal statistical optimality.",
)
replace_once(api_doc, f"REFINERY_API_SCHEMA_VERSION   = {OLD_SCHEMA}", f"REFINERY_API_SCHEMA_VERSION   = {NEW_SCHEMA}")
replace_once(
    api_doc,
    "Historical note: Phase 3 originally shipped schema `refinery-v1-2026-08-09.1`. The `.2` schema is an additive response extension on the Phase 5 branch; the request contract is unchanged.",
    "Historical note: Phase 3 shipped `refinery-v1-2026-08-09.1`; the initial Phase 5 draft used `refinery-v1-2026-08-10.2`. Corrected M1–M4 public evidence semantics are versioned as `refinery-v1-2026-08-10.3`. The request contract remains unchanged.",
)
replace_once(api_doc, "Schema `.2` may add these read-only sections under `analysis`:", "Schema `.3` adds these read-only sections under `analysis`:")
replace_once(
    api_doc,
    "The active Phase 5 review is tightening complete-month/common-sample/applicability semantics. Until those amendments are implemented and versioned, this section is **under final methodology review** and must not be interpreted beyond the current labelled evidence.",
    "Corrected factor evidence uses boundary-month exclusion, one global common relationship sample, and explicit computability/model-scope/corroboration-eligibility states. Computable diagnostics remain visible, but factor evidence is fail-closed for verdict corroboration without traceable instrument-scope authority.",
)
replace_once(api_doc, "additive schema `.2` remains backward compatible", "corrected additive schema `.3` remains backward compatible")

# UI contract: promote from review wording to the now-explicit server states.
ui_doc = "docs/research/REFINERY_UI_V1.md"
replace_once(
    ui_doc,
    "Status: **Phase 4 workspace/persistence baseline with Phase 5 additive read-only results extension**.",
    "Status: **Phase 4 workspace/persistence baseline with corrected Phase 5 additive read-only results extension.** P5-CORR A–D response semantics are reflected without changing persisted workspace schema.",
)
replace_once(
    ui_doc,
    "Current Phase 5 factor semantics are under final methodology review. UI must distinguish **diagnostic availability** from any future/approved **verdict corroboration eligibility** if the API exposes separate states. It must not infer applicability from ticker or USD denomination itself.",
    "The API now explicitly separates `factor_computable`, `factor_model_scope` and `factor_corroboration_eligible`. The UI must keep computable betas/R²/systematic correlation visible as diagnostics while separately showing whether factor evidence may affect a redundancy verdict. Current Phase 5 eligibility is fail-closed without traceable instrument-scope authority; the browser must not infer applicability from ticker or USD denomination.",
)
replace_once(
    ui_doc,
    "11. factor available/unavailable/scope presentation;",
    "11. factor computable/model-scope/verdict-eligibility presentation;",
)

# Replace the stale review-plan gate text with one concise resolved correction record.
review_plan = '''# Phase 5 Review & Convergence Plan

Status: **M1–M4 RESOLVED / P5-CORR A–D IMPLEMENTED; P5-SEC + P5-VAL + PARENT MERGE PENDING**.

Parent: PR #65 `feat: add Phase 5 clustering and redundancy diagnostics`.
Correctness convergence: Draft PR #71 `fix: converge Phase 5 correctness contracts`.
Historical docs child: PR #66. Its Phase5-specific evidence was preserved here; its general README/Deployment/TODO changes are superseded by the current main documentation-convergence path and are not wholesale merged.

## 1. Governance transition

The historical review plan was created under the old `Independent Third-Party Review` wording. Repository governance V3 now uses an **Independent Review Gate** based on independent reasoning, relevant competence and exact-head evidence rather than a different GitHub identity. This change does not waive correctness, security, required CI/Vercel or rollback gates.

P5-CORR A/B/C each received focused Same-AI Independent Review after exact-head validation. Final PR #65/#71 still requires an independent exact-head review after D/security/final validation converge.

## 2. Corrected contract identities

```text
REFINERY_CLUSTERING_CONTRACT_VERSION = refinery-clustering-twd-2026-08-10.2
REFINERY_API_CONTRACT_VERSION        = refinery-v1
REFINERY_API_SCHEMA_VERSION          = refinery-v1-2026-08-10.3
```

No Refinery persisted workspace-storage schema bump is required because P5-CORR changes analytical evidence, not persisted request state.

## 3. M1 — bootstrap input identity — RESOLVED

Root cause: the initial implementation hashed the entire weekly frame and repurposed `ResearchDataset.dataset_hash`, while bootstrap actually resampled a trailing-window complete-case sample.

Accepted implementation:

- one shared `prepare_bootstrap_sample()` path: numeric → sorted symbols → trailing window → non-finite→NaN → complete-case;
- fingerprint exact effective symbols/dates/values only;
- preserve `ResearchDataset.dataset_hash` unchanged;
- bootstrap verifies caller fingerprint matches the effective sample;
- seed includes fingerprint + clustering version + linkage + cut + window + block length + replicates;
- public evidence uses `bootstrap_input_fingerprint_sha256` plus explicit bootstrap window.

Evidence: P5-CORR-A exact-head Full CI #466 and Portfolio web CI #104 PASS; focused review PASS / BLOCKER=0.

## 4. M2 — boundary-month factor alignment — RESOLVED

Root cause: resampling all represented months could compare a partial first/last asset-return month with a full-calendar Kenneth French factor row.

Accepted V1 policy:

- normalize native daily returns;
- compound by represented calendar month;
- exclude first and last represented periods;
- no exchange-calendar completeness claim;
- no fabricated pre-window return;
- require 36 observations after exclusion;
- policy identifier `boundary-month-exclusion-v1`.

## 5. M4 — one common systematic relationship sample — RESOLVED

Root cause: initial individual betas could be fit on different samples while `Sigma_F` came from a broader factor frame.

Accepted implementation:

- individual diagnostics may retain individual valid samples;
- matrix membership begins with individually valid assets;
- one global common monthly intersection across all matrix members + factor frame;
- refit every relationship beta on that exact common frame;
- compute `Sigma_F` from those same rows;
- no pairwise-cell sample switching;
- expose observations/start/end/common-sample fingerprint;
- insufficient common sample fails closed.

Evidence for M2+M4: P5-CORR-B exact-head Full CI #473 and Portfolio web CI #111 PASS; focused review PASS / BLOCKER=0.

## 6. M3 — factor computability vs verdict applicability — RESOLVED

Root cause: USD denomination plus valid regression made factor-implied correlation eligible to act as a MEDIUM corroborator without traceable instrument/model applicability authority.

Accepted implementation:

- separate `factor_computable`, `factor_model_scope`, `factor_corroboration_eligible`;
- model scope = `U.S.-factor co-movement diagnostic`;
- computable betas/R²/systematic correlation remain visible;
- current corroboration policy = `fail_closed_without_traceable_instrument_scope_v1`;
- current eligibility = false with `unavailable_no_traceable_instrument_scope`;
- factor correlation can affect verdict only when eligibility is explicitly true and threshold is met;
- instrument master/regional factor routing remains BACKLOG.

Evidence: P5-CORR-C exact-head Full CI #479 and Portfolio web CI #117 PASS; focused review PASS / BLOCKER=0.

## 7. Scope that remains accepted

- structural clustering input: synchronized weekly TWD returns;
- correlation distance `sqrt((1-rho)/2)`;
- average linkage primary; complete linkage sensitivity;
- flat cut 0.50;
- stability windows 52/104/156 weeks;
- 200 × 4-week circular moving-block bootstrap;
- HIGH/MEDIUM/LOW/UNCERTAIN descriptive redundancy evidence;
- no numeric magic score;
- theme evidence unavailable without traceable provenance;
- browser is presentation only.

## 8. Explicit non-goals through Phase 5

- KEEP/TRIM/REPLACE;
- Remove-One/Add-One/Replace-One marginal experiments;
- position sizing / HRP / ERC / min variance;
- Exhaustive selection integration;
- OOS/walk-forward claims;
- instrument/security master or regional factor routing;
- untraceable theme taxonomy.

## 9. Remaining gates

P5-CORR is not equivalent to Phase 5 closure. Before parent merge:

- [x] M1 exact bootstrap-effective-input identity implemented/tested/reviewed;
- [x] M2 boundary-month exclusion implemented/tested/reviewed;
- [x] M4 global common relationship sample implemented/tested/reviewed;
- [x] M3 computability/applicability/verdict gate implemented/tested/reviewed;
- [x] clustering contract promoted to `.2` and API response schema to `.3` in P5-CORR-D;
- [ ] P5-SEC dependency vulnerability triage with `npm audit --json` evidence;
- [ ] exact final Python/Worker/score/Portfolio web/Playwright validation;
- [ ] required Vercel status green on the final exact candidate;
- [ ] release-backup gate as applicable;
- [ ] V3 independent final exact-head review;
- [ ] preserve current main documentation authority during branch transition;
- [ ] expected-head squash merge into parent, then parent #65 into main only after all parent gates;
- [ ] post-main deployment/smoke/backup closeout.

## 10. Exact resume point

After P5-CORR-D validation, execute **P5-SEC** only. Do not start Phase 6. Any new observation is NOW only if it blocks Phase 5 correctness/security/data integrity; otherwise classify NEXT/BACKLOG/REJECT.
'''
Path("docs/research/PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md").write_text(review_plan, encoding="utf-8")

print("P5-CORR-D convergence patch applied successfully")
