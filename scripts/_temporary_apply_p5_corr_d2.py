from __future__ import annotations

import re
import subprocess
from pathlib import Path

OLD_CLUSTER = "refinery-clustering-twd-2026-08-10.1"
NEW_CLUSTER = "refinery-clustering-twd-2026-08-10.2"
OLD_SCHEMA = "refinery-v1-2026-08-10.2"
NEW_SCHEMA = "refinery-v1-2026-08-10.3"


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one exact match, found {count}: {old[:80]!r}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str, *, flags: int = re.DOTALL) -> None:
    text = read(path)
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, found {count}: {pattern[:100]!r}")
    write(path, updated)


def copy_from_review_branch(path: str) -> None:
    content = subprocess.check_output(
        ["git", "show", f"refs/remotes/origin/docs/phase5-convergence-plan:{path}"],
        text=True,
    )
    write(path, content)


subprocess.run(
    [
        "git", "fetch", "origin",
        "docs/phase5-convergence-plan:refs/remotes/origin/docs/phase5-convergence-plan",
    ],
    check=True,
)

for path in (
    "docs/research/REFINERY_CLUSTERING_V1.md",
    "docs/research/REFINERY_API_V1.md",
    "docs/research/REFINERY_UI_V1.md",
):
    copy_from_review_branch(path)

# Runtime identities.
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

# Name the already accepted M3 policy once and expose corrected consumer policies.
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

# Public response schema literals in code/tests follow .3. Request contract stays refinery-v1.
for root in (Path("apps"), Path("tests")):
    for file_path in root.rglob("*"):
        if file_path.is_file() and file_path.suffix in {".py", ".ts", ".tsx", ".mjs", ".js"}:
            text = file_path.read_text(encoding="utf-8")
            if OLD_SCHEMA in text:
                file_path.write_text(text.replace(OLD_SCHEMA, NEW_SCHEMA), encoding="utf-8")

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

# Promote clustering methodology baseline by section, not fragile sentence matching.
cluster_doc = "docs/research/REFINERY_CLUSTERING_V1.md"
text = read(cluster_doc).replace(OLD_CLUSTER, NEW_CLUSTER)
write(cluster_doc, text)
regex_once(
    cluster_doc,
    r"^Status:.*$",
    "Status: **Phase 5 corrected methodology contract / P5-CORR A–D implementation-aligned; final release gates pending.**",
    flags=re.MULTILINE,
)
regex_once(
    cluster_doc,
    r"## Review status and amendment gate\n[\s\S]*?(?=\n## Contract identity)",
    '''## Review status and correction outcome

The initial `.1` branch implementation was independently re-audited and four correctness gaps were resolved together in code, tests and contract:

1. M1 bootstrap effective-input identity;
2. M2 boundary-month factor alignment;
3. M3 factor computability vs verdict corroboration eligibility;
4. M4 one global common sample for the systematic factor relationship matrix.

The corrected methodology identity is `.2`. P5-CORR A/B/C each passed exact-head CI and focused independent review; D promotes the accepted semantics into versioned public evidence. Phase 5 is still not production-closed until security/final validation, required Vercel, final independent review and parent merge/closeout complete.
''',
)
text = read(cluster_doc).replace(
    "## Contract identity — initial Phase 5 baseline",
    "## Contract identity — corrected Phase 5 V1",
)
write(cluster_doc, text)
regex_once(
    cluster_doc,
    r"## 8\. Bootstrap cluster stability[^\n]*\n[\s\S]*?(?=\n## 9\. Price-based redundancy evidence)",
    '''## 8. Bootstrap cluster stability

### Sampling policy

Use deterministic circular moving-block bootstrap on the primary structural weekly return input:

```text
replicates   = 200
block length = 4 weeks
window       = 156 weeks
```

Rows are resampled jointly across candidate columns. Degenerate replicates are counted as unusable rather than hidden.

### Exact effective-input identity

The stochastic input is prepared by one shared pure path:

```text
numeric weekly returns
→ canonical sorted symbols
→ trailing bootstrap window
→ +/-inf to NaN
→ complete-case row drop
→ exact effective bootstrap sample
```

`bootstrap_input_fingerprint_sha256` hashes only the exact effective symbols, timestamps and numeric values. Rows older than the bootstrap window, and rows removed by complete-case preparation, do not change that identity.

`ResearchDataset.dataset_hash` remains the full audited research-dataset identity and is never replaced or repurposed for bootstrap seeding.

### Deterministic seed

Seed material includes:

- exact bootstrap input fingerprint;
- clustering contract version;
- primary linkage;
- flat-cut distance;
- bootstrap window;
- replicate count;
- block length.

The bootstrap primitive recomputes its effective-input fingerprint and fails closed if the caller supplies a mismatched identity.

### Output

- pairwise average-linkage co-cluster probability;
- requested/usable/unusable replicate counts;
- explicit bootstrap window/input fingerprint/seed evidence;
- cluster-level mean pairwise stability where applicable;
- singleton stability = `not_applicable`, not `1.0`.
''',
)
text = read(cluster_doc).replace("not a core verdict input in `.1`", "not a core verdict input in V1")
write(cluster_doc, text)
regex_once(
    cluster_doc,
    r"## 10\. Factor-implied relationship evidence[^\n]*\n[\s\S]*?(?=\n## 11\. Economic-theme evidence)",
    '''## 10. Factor-implied relationship evidence

Factor evidence is a **U.S.-factor co-movement diagnostic**. Diagnostic computability, model scope and redundancy-verdict corroboration eligibility are separate concepts.

### Data source and return semantics

Use official Kenneth French monthly U.S. five-factor plus momentum data through the shared research adapter. Asset regressions use native-currency returns so TWD FX translation is not folded into U.S.-factor beta estimates.

```text
asset excess return = native monthly return - RF
predictors           = MKT_RF, SMB, HML, RMW, CMA, MOM
```

### Boundary-month exclusion policy

Native daily returns are normalized and compounded by represented calendar month. The **first and last represented calendar periods are excluded** before factor regression because this repository does not own an exchange-calendar/instrument authority capable of proving those boundary holding periods complete.

```text
monthly_return_policy = boundary-month-exclusion-v1
minimum observations  = 36 after exclusion
```

No pre-window/backfilled return is fabricated to rescue a boundary month.

### Individual diagnostic evidence

USD quote currency plus sufficient native-return history may make the diagnostic mechanically computable. Per asset, the API separates:

- `factor_computable`;
- `factor_model_scope`;
- observations/effective start/end;
- beta vector and R-squared when available;
- `factor_corroboration_eligible` and explicit reason.

USD denomination alone is not instrument/model applicability authority.

### One global systematic relationship sample

Individual diagnostics may retain their own valid samples. One returned systematic relationship matrix uses one exact global common monthly intersection across every individually valid matrix member plus the factor frame.

On that same common frame the implementation:

1. refits every relationship beta;
2. computes `Sigma_F` from the exact same rows;
3. computes `B Sigma_F B'` and systematic correlation;
4. exposes common observations/start/end/fingerprint;
5. fails closed when the common sample is insufficient.

No pairwise-cell sample switching is permitted.

### Verdict corroboration eligibility

The repository currently lacks a traceable instrument-scope authority (instrument type/incorporation/market/ADR/ETF/fund taxonomy). Current Phase 5 therefore uses:

```text
factor_corroboration_policy   = fail_closed_without_traceable_instrument_scope_v1
factor_corroboration_eligible = false
reason                        = unavailable_no_traceable_instrument_scope
```

Computable betas/R²/systematic correlation remain visible, but factor evidence cannot upgrade a redundancy verdict while eligibility is false. A future traceable instrument authority requires separate methodology/version review.

### Systematic relationship formula

```text
Cov_factor(i,j)  = beta_i' Sigma_F beta_j
Corr_factor(i,j) = Cov_factor(i,j) /
                   sqrt(Cov_factor(i,i) * Cov_factor(j,j))
```

This describes factor-implied systematic co-movement, not total-return correlation. No raw beta-vector cosine is used as official factor-overlap evidence.
''',
)
text = read(cluster_doc)
text = text.replace("## 12. Redundancy verdict policy — initial `.1`", "## 12. Redundancy verdict policy")
text = text.replace(
    "- factor-implied correlation ≥0.65 when the final factor policy declares the evidence valid/eligible;",
    "- factor-implied correlation ≥0.65 **and** `factor_corroboration_eligible = true`;",
)
text = re.sub(
    r"\nThe `\.1` implementation currently treats valid factor regressions as a corroborator; M3 review must be resolved before merge so factor applicability is not inferred solely from USD quote currency\.\n",
    "\n",
    text,
)
text = text.replace(
    "bootstrap output is deterministic for the same dataset hash/contract",
    "bootstrap output is deterministic for the same exact effective-input fingerprint/methodology contract",
)
write(cluster_doc, text)

# API transport/schema contract promotion. Keep historical .2 only in one labelled note.
api_doc = "docs/research/REFINERY_API_V1.md"
regex_once(
    api_doc,
    r"^Status:.*$",
    "Status: **Phase 3 baseline contract with corrected Phase 5 additive analysis-schema extension. P5-CORR A–D implementation-aligned; final release gates pending.**",
    flags=re.MULTILINE,
)
regex_once(
    api_doc,
    r"Current Phase 5 implementation is still under final review\.[^\n]*",
    "Corrected Phase 5 clustering/factor semantics are governed by `REFINERY_CLUSTERING_V1.md`; `PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md` records resolved M1–M4 findings and remaining release gates.",
)
replace_once(
    api_doc,
    f"REFINERY_API_SCHEMA_VERSION   = {OLD_SCHEMA}",
    f"REFINERY_API_SCHEMA_VERSION   = {NEW_SCHEMA}",
)
regex_once(
    api_doc,
    r"Historical note: Phase 3 originally shipped schema[^\n]*",
    "Historical note: Phase 3 shipped `refinery-v1-2026-08-09.1`; the initial Phase 5 draft used `refinery-v1-2026-08-10.2`. Corrected M1–M4 public evidence semantics are versioned as `refinery-v1-2026-08-10.3`. The request contract remains `refinery-v1`.",
)
text = read(api_doc)
text = text.replace("Schema `.2` may add these read-only sections", "Schema `.3` adds these read-only sections")
text = text.replace(
    "The active Phase 5 review is tightening complete-month/common-sample/applicability semantics. Until those amendments are implemented and versioned, this section is **under final methodology review** and must not be interpreted beyond the current labelled evidence.",
    "Corrected factor evidence uses boundary-month exclusion, one global common relationship sample, and explicit computability/model-scope/corroboration-eligibility states. Computable diagnostics remain visible, but factor evidence is fail-closed for verdict corroboration without traceable instrument-scope authority.",
)
text = text.replace("additive schema `.2` remains backward compatible", "corrected additive schema `.3` remains backward compatible")
write(api_doc, text)

# UI contract promotion without changing persisted workspace schema.
ui_doc = "docs/research/REFINERY_UI_V1.md"
regex_once(
    ui_doc,
    r"^Status:.*$",
    "Status: **Phase 4 workspace/persistence baseline with corrected Phase 5 additive read-only results extension. P5-CORR A–D response semantics are implementation-aligned.**",
    flags=re.MULTILINE,
)
text = read(ui_doc)
text = text.replace(
    "Current Phase 5 factor semantics are under final methodology review. UI must distinguish **diagnostic availability** from any future/approved **verdict corroboration eligibility** if the API exposes separate states. It must not infer applicability from ticker or USD denomination itself.",
    "The API explicitly separates `factor_computable`, `factor_model_scope` and `factor_corroboration_eligible`. The UI keeps computable betas/R²/systematic correlation visible as diagnostics while separately showing whether factor evidence may affect a redundancy verdict. Current Phase 5 eligibility is fail-closed without traceable instrument-scope authority; the browser must not infer applicability from ticker or USD denomination.",
)
text = text.replace(
    "11. factor available/unavailable/scope presentation;",
    "11. factor computable/model-scope/verdict-eligibility presentation;",
)
write(ui_doc, text)

# Concise resolved review record becomes the D handoff authority.
review_plan = '''# Phase 5 Review & Convergence Plan

Status: **M1–M4 RESOLVED / P5-CORR A–D IMPLEMENTED; P5-SEC + P5-VAL + PARENT MERGE PENDING**.

Parent: PR #65 `feat: add Phase 5 clustering and redundancy diagnostics`.
Correctness convergence: Draft PR #71 `fix: converge Phase 5 correctness contracts`.
Historical docs child: PR #66. Its Phase5-specific evidence is preserved here; its general README/Deployment/TODO changes are superseded by the current main documentation-convergence path and are not wholesale merged.

## 1. Governance transition

The historical review plan was written under the old `Independent Third-Party Review` wording. Repository governance V3 uses an **Independent Review Gate** based on independent reasoning, relevant competence and exact-head evidence rather than a different GitHub identity. This transition does not waive correctness, security, required CI/Vercel or rollback gates.

P5-CORR A/B/C each received focused Same-AI Independent Review after exact-head validation. D and the final Phase 5 candidate require the same evidence discipline.

## 2. Corrected identities

```text
REFINERY_CLUSTERING_CONTRACT_VERSION = refinery-clustering-twd-2026-08-10.2
REFINERY_API_CONTRACT_VERSION        = refinery-v1
REFINERY_API_SCHEMA_VERSION          = refinery-v1-2026-08-10.3
```

No Refinery persisted workspace-storage schema bump is required because P5-CORR changes analytical evidence, not persisted request state.

## 3. M1 — bootstrap input identity — RESOLVED

Root cause: the draft hashed the entire weekly frame and repurposed `ResearchDataset.dataset_hash`, while bootstrap actually resampled a trailing-window complete-case sample.

Accepted implementation:
- shared effective sample preparation;
- fingerprint exact effective symbols/dates/values only;
- preserve ResearchDataset hash unchanged;
- primitive verifies fingerprint/sample identity;
- seed includes fingerprint + methodology version/linkage/cut/window/block/replicates;
- public evidence exposes bootstrap input fingerprint + window.

Evidence: P5-CORR-A Full CI #466 + Portfolio web CI #104 PASS; focused review PASS/BLOCKER=0.

## 4. M2 — boundary-month factor alignment — RESOLVED

Accepted V1 policy:
- normalize native daily returns;
- compound represented calendar months;
- exclude first and last represented periods;
- no exchange-calendar completeness claim;
- no fabricated pre-window return;
- require 36 observations after exclusion;
- policy `boundary-month-exclusion-v1`.

## 5. M4 — common systematic relationship sample — RESOLVED

Accepted implementation:
- individual diagnostics may keep individual valid samples;
- matrix membership begins with individually valid assets;
- one global common monthly intersection across all matrix members + factor frame;
- refit every relationship beta on that exact sample;
- compute `Sigma_F` from the same rows;
- no pairwise-cell sample switching;
- expose observations/start/end/common-sample fingerprint;
- insufficient common sample fails closed.

Evidence for M2+M4: P5-CORR-B Full CI #473 + Portfolio web CI #111 PASS; focused review PASS/BLOCKER=0.

## 6. M3 — factor computability vs verdict applicability — RESOLVED

Accepted implementation:
- separate `factor_computable`, `factor_model_scope`, `factor_corroboration_eligible`;
- model scope = `U.S.-factor co-movement diagnostic`;
- computable betas/R²/systematic correlation remain visible;
- policy = `fail_closed_without_traceable_instrument_scope_v1`;
- current eligibility false with `unavailable_no_traceable_instrument_scope`;
- factor correlation affects verdict only when eligibility is explicitly true and threshold is met;
- instrument master/regional factor routing remains BACKLOG.

Evidence: P5-CORR-C Full CI #479 + Portfolio web CI #117 PASS; focused review PASS/BLOCKER=0.

## 7. Accepted Phase 5 scope

- synchronized weekly TWD structural input;
- correlation distance `sqrt((1-rho)/2)`;
- average linkage primary, complete sensitivity;
- flat cut 0.50;
- 52/104/156-week stability;
- 200 × 4-week circular moving-block bootstrap;
- HIGH/MEDIUM/LOW/UNCERTAIN descriptive redundancy evidence;
- no numeric magic score;
- theme evidence unavailable without traceable provenance;
- browser is presentation only.

## 8. Explicit non-goals

- KEEP/TRIM/REPLACE;
- marginal Remove-One/Add-One/Replace-One experiments;
- sizing/HRP/ERC/min-var;
- Exhaustive selection integration;
- OOS/walk-forward claims;
- instrument/security master or regional factor routing;
- untraceable theme taxonomy.

## 9. Remaining gates

- [x] M1 implementation/tests/review;
- [x] M2 implementation/tests/review;
- [x] M4 implementation/tests/review;
- [x] M3 implementation/tests/review;
- [x] clustering `.2` / API response `.3` convergence in P5-CORR-D;
- [ ] P5-SEC `npm audit --json` evidence and reachability classification;
- [ ] final exact-head Python/Worker/score/Portfolio web/Playwright validation;
- [ ] required Vercel status green on final candidate;
- [ ] release-backup gate as applicable;
- [ ] V3 independent final exact-head review;
- [ ] preserve current main documentation authority during branch transition;
- [ ] expected-head parent merge and post-main deployment/smoke/backup closeout.

## 10. Exact resume point

After P5-CORR-D validation, execute **P5-SEC only**. Do not start Phase 6. New findings are NOW only if they block Phase 5 correctness/security/data integrity; otherwise classify NEXT/BACKLOG/REJECT.
'''
write("docs/research/PHASE5_REVIEW_AND_CONVERGENCE_PLAN.md", review_plan)

# Fail closed on stale unlabelled draft authority in the promoted clustering contract.
cluster_text = read(cluster_doc)
for forbidden in (
    "UNDER FINAL REVIEW",
    "Active review finding",
    "Review amendments required before merge",
    "initial `.1` baseline under review",
    "M3 review must be resolved before merge",
    "not considered implemented by this documentation change alone",
):
    if forbidden in cluster_text:
        raise RuntimeError(f"stale clustering-contract text remains after promotion: {forbidden}")

if NEW_CLUSTER not in cluster_text or OLD_CLUSTER in cluster_text:
    raise RuntimeError("clustering contract identity did not converge to .2")
if NEW_SCHEMA not in read(api_doc):
    raise RuntimeError("API schema identity did not converge to .3")
if 'REFINERY_API_CONTRACT_VERSION = refinery-v1' not in read(api_doc):
    raise RuntimeError("request contract was not preserved as refinery-v1")

print("P5-CORR-D structured promotion applied successfully")
