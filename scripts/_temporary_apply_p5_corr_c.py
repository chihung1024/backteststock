from __future__ import annotations

import re
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one exact match, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_once(path: str, pattern: str, replacement: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, found {count}")
    file_path.write_text(updated, encoding="utf-8")


redundancy = "apps/api/app/refinery/redundancy.py"
replace_once(
    redundancy,
    "    factor_implied_correlation: float | None\n    shared_traceable_theme: bool | None",
    "    factor_implied_correlation: float | None\n    factor_corroboration_eligible: bool | None\n    shared_traceable_theme: bool | None",
)
replace_once(
    redundancy,
    '''        evidence.factor_implied_correlation is not None
        and evidence.factor_implied_correlation >= 0.65,''',
    '''        evidence.factor_corroboration_eligible is True
        and evidence.factor_implied_correlation is not None
        and evidence.factor_implied_correlation >= 0.65,''',
)

relationships = "apps/api/app/refinery/relationships.py"
replace_once(
    relationships,
    'THEME_UNAVAILABLE_STATUS = "unavailable_no_traceable_theme_source"',
    '''THEME_UNAVAILABLE_STATUS = "unavailable_no_traceable_theme_source"
FACTOR_MODEL_SCOPE = "U.S.-factor co-movement diagnostic"
FACTOR_CORROBORATION_UNAVAILABLE_REASON = (
    "unavailable_no_traceable_instrument_scope"
)''',
)

# Every asset evidence state exposes computability separately from applicability.
for marker in (
    '''                "status": "unavailable_non_usd_quote_currency",
                "quote_currency": quote_currency or None,
                "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,''',
    '''                "status": "unavailable_native_returns",
                "quote_currency": quote_currency,
                "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,''',
    '''                "status": "unavailable_factor_source",
                "quote_currency": "USD",
                "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,''',
):
    status_line, quote_line, policy_line = marker.split("\n")
    replacement = "\n".join(
        [
            status_line,
            quote_line,
            '                "factor_computable": False,',
            '                "factor_model_scope": FACTOR_MODEL_SCOPE,',
            '                "factor_corroboration_eligible": False,',
            '                "factor_corroboration_reason": FACTOR_CORROBORATION_UNAVAILABLE_REASON,',
            policy_line,
        ]
    )
    replace_once(relationships, marker, replacement)

replace_once(
    relationships,
    '''    base = {
        "source": FRENCH_FACTOR_SOURCE,
        "scope": "U.S.-factor co-movement diagnostic",
        "return_currency": "native_quote_currency",''',
    '''    base = {
        "source": FRENCH_FACTOR_SOURCE,
        "scope": FACTOR_MODEL_SCOPE,
        "factor_model_scope": FACTOR_MODEL_SCOPE,
        "factor_corroboration_policy": "fail_closed_without_traceable_instrument_scope_v1",
        "return_currency": "native_quote_currency",''',
)
replace_once(
    relationships,
    '''            "status": exposure.status,
            "quote_currency": "USD",
            "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,''',
    '''            "status": exposure.status,
            "quote_currency": "USD",
            "factor_computable": exposure.status == "ok" and exposure.betas is not None,
            "factor_model_scope": FACTOR_MODEL_SCOPE,
            "factor_corroboration_eligible": False,
            "factor_corroboration_reason": FACTOR_CORROBORATION_UNAVAILABLE_REASON,
            "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,''',
)
replace_once(
    relationships,
    '''        factor = factor_matrix.get(pair)
        window = window_lookup.get(pair, {})''',
    '''        factor = factor_matrix.get(pair)
        factor_corroboration_eligible, factor_corroboration_reason = (
            _factor_corroboration_pair_evidence(
                factor_payload,
                symbol_a,
                symbol_b,
                factor,
            )
        )
        window = window_lookup.get(pair, {})''',
)
replace_once(
    relationships,
    '''            factor_implied_correlation=factor,
            shared_traceable_theme=None,''',
    '''            factor_implied_correlation=factor,
            factor_corroboration_eligible=factor_corroboration_eligible,
            shared_traceable_theme=None,''',
)
replace_once(
    relationships,
    '''                "factor_implied_correlation": factor,
                "same_average_cluster": evidence.same_average_cluster,''',
    '''                "factor_implied_correlation": factor,
                "factor_corroboration_eligible": factor_corroboration_eligible,
                "factor_corroboration_reason": factor_corroboration_reason,
                "same_average_cluster": evidence.same_average_cluster,''',
)
replace_once(
    relationships,
    "\ndef _factor_matrix_lookup(payload: Mapping[str, Any]) -> dict[tuple[str, str], float]:",
    '''
def _factor_corroboration_pair_evidence(
    payload: Mapping[str, Any],
    symbol_a: str,
    symbol_b: str,
    factor_correlation: float | None,
) -> tuple[bool, str | None]:
    if factor_correlation is None:
        return False, "unavailable_factor_relationship"
    assets = payload.get("assets")
    if not isinstance(assets, Mapping):
        return False, FACTOR_CORROBORATION_UNAVAILABLE_REASON
    asset_a = assets.get(symbol_a)
    asset_b = assets.get(symbol_b)
    eligible = (
        isinstance(asset_a, Mapping)
        and isinstance(asset_b, Mapping)
        and asset_a.get("factor_corroboration_eligible") is True
        and asset_b.get("factor_corroboration_eligible") is True
    )
    if eligible:
        return True, None
    for asset in (asset_a, asset_b):
        if isinstance(asset, Mapping):
            reason = asset.get("factor_corroboration_reason")
            if isinstance(reason, str) and reason:
                return False, reason
    return False, FACTOR_CORROBORATION_UNAVAILABLE_REASON


def _factor_matrix_lookup(payload: Mapping[str, Any]) -> dict[tuple[str, str], float]:''',
)

# Types make diagnostic availability vs verdict eligibility explicit.
types = "apps/portfolio-web/src/refineryTypes.ts"
replace_once(
    types,
    "  factor_implied_correlation: number | null;\n  same_average_cluster: boolean;",
    "  factor_implied_correlation: number | null;\n  factor_corroboration_eligible: boolean;\n  factor_corroboration_reason: string | null;\n  same_average_cluster: boolean;",
)
replace_once(
    types,
    "  quote_currency: string | null;\n  monthly_return_policy: string;",
    "  quote_currency: string | null;\n  factor_computable: boolean;\n  factor_model_scope: string;\n  factor_corroboration_eligible: boolean;\n  factor_corroboration_reason: string | null;\n  monthly_return_policy: string;",
)
replace_once(
    types,
    "  scope: string;\n  return_currency: string;",
    "  scope: string;\n  factor_model_scope: string;\n  factor_corroboration_policy: string;\n  return_currency: string;",
)

# UI keeps the factor diagnostic visible while exposing verdict eligibility.
ui = "apps/portfolio-web/src/RefineryPhase5Results.tsx"
replace_once(
    ui,
    '''      <td>{formatNumber(pair.factor_implied_correlation, 2)}</td>
      <td>{yesNo(pair.same_average_cluster)}</td>''',
    '''      <td>{formatNumber(pair.factor_implied_correlation, 2)}</td>
      <td title={pair.factor_corroboration_reason ?? undefined}>{yesNo(pair.factor_corroboration_eligible)}</td>
      <td>{yesNo(pair.same_average_cluster)}</td>''',
)
replace_once(
    ui,
    '''<thead><tr><th>Pair</th><th>Verdict</th><th>Confidence</th><th>156W</th><th>252D</th><th>Downside</th><th>Stress</th><th>Factor</th><th>Avg cluster</th><th>Complete</th><th>Window</th><th>Bootstrap</th></tr></thead>''',
    '''<thead><tr><th>Pair</th><th>Verdict</th><th>Confidence</th><th>156W</th><th>252D</th><th>Downside</th><th>Stress</th><th>Factor diagnostic</th><th>Factor 可作 verdict</th><th>Avg cluster</th><th>Complete</th><th>Window</th><th>Bootstrap</th></tr></thead>''',
)
replace_once(
    ui,
    '''        <div><span>Return currency</span><strong>{factors.return_currency}</strong></div>
        <div><span>Minimum months</span><strong>{factors.minimum_monthly_observations}</strong></div>''',
    '''        <div><span>Return currency</span><strong>{factors.return_currency}</strong></div>
        <div><span>Model scope</span><strong>{factors.factor_model_scope}</strong></div>
        <div><span>Minimum months</span><strong>{factors.minimum_monthly_observations}</strong></div>''',
)
replace_once(
    ui,
    '''<thead><tr><th>代碼</th><th>Status</th><th>Quote CCY</th><th>Obs.</th><th>R²</th></tr></thead>''',
    '''<thead><tr><th>代碼</th><th>Status</th><th>Quote CCY</th><th>Computable</th><th>Verdict eligible</th><th>Obs.</th><th>R²</th></tr></thead>''',
)
replace_once(
    ui,
    '''                <td>{asset.quote_currency ?? "—"}</td>
                <td>{asset.observations}</td>''',
    '''                <td>{asset.quote_currency ?? "—"}</td>
                <td>{yesNo(asset.factor_computable)}</td>
                <td title={asset.factor_corroboration_reason ?? undefined}>{yesNo(asset.factor_corroboration_eligible)}</td>
                <td>{asset.observations}</td>''',
)
replace_once(
    ui,
    '''      <p className="refinery-method-note">Factor-implied correlation 表示系統性 factor component 的共動，不是總報酬相關，也不是全球通用因子模型。</p>''',
    '''      <p className="refinery-method-note">Factor-implied correlation 是 U.S.-factor co-movement diagnostic。沒有可追溯的 instrument/model applicability authority 時，診斷仍可顯示，但 factor_corroboration_eligible=false，不能升級 redundancy verdict。</p>''',
)

# Pure policy tests demonstrate that factor correlation alone has no verdict authority.
policy_test = "tests/test_redundancy_policy.py"
replace_once(
    policy_test,
    '        "factor_implied_correlation": None,\n        "shared_traceable_theme": None,',
    '        "factor_implied_correlation": None,\n        "factor_corroboration_eligible": False,\n        "shared_traceable_theme": None,',
)
regex_once(
    policy_test,
    r"    with_factor = _evidence\([\s\S]*?    assert redundancy_verdict\(with_factor\) == \"MEDIUM\"",
    '''    ineligible_factor = _evidence(
        structural_correlation=0.70,
        medium_correlation=None,
        factor_implied_correlation=0.70,
        factor_corroboration_eligible=False,
        same_average_cluster=True,
        bootstrap_probability=0.70,
    )
    assert redundancy_verdict(ineligible_factor) == "UNCERTAIN"

    eligible_factor = _evidence(
        structural_correlation=0.70,
        medium_correlation=None,
        factor_implied_correlation=0.70,
        factor_corroboration_eligible=True,
        same_average_cluster=True,
        bootstrap_probability=0.70,
    )
    assert redundancy_verdict(eligible_factor) == "MEDIUM"''',
)

# API integration test verifies diagnostics remain visible but fail closed for verdict use.
phase5_test = "tests/test_refinery_phase5.py"
replace_once(
    phase5_test,
    '''    assert factors["scope"] == "U.S.-factor co-movement diagnostic"
    assert factors["assets"]["AAA"]["status"] == "ok"
    assert factors["assets"]["BBB"]["status"] == "ok"
    assert factors["systematic_relationship"]["status"] == "ok"
    assert factors["systematic_relationship"]["matrix"]["symbols"] == ["AAA", "BBB"]''',
    '''    assert factors["scope"] == "U.S.-factor co-movement diagnostic"
    assert factors["factor_model_scope"] == "U.S.-factor co-movement diagnostic"
    assert factors["assets"]["AAA"]["status"] == "ok"
    assert factors["assets"]["BBB"]["status"] == "ok"
    assert factors["assets"]["AAA"]["factor_computable"] is True
    assert factors["assets"]["BBB"]["factor_computable"] is True
    assert factors["assets"]["AAA"]["factor_corroboration_eligible"] is False
    assert factors["assets"]["BBB"]["factor_corroboration_eligible"] is False
    assert factors["assets"]["AAA"]["factor_corroboration_reason"] == (
        "unavailable_no_traceable_instrument_scope"
    )
    assert factors["systematic_relationship"]["status"] == "ok"
    assert factors["systematic_relationship"]["matrix"]["symbols"] == ["AAA", "BBB"]
    pair = result["analysis"]["redundancy"]["pairs"][0]
    assert pair["factor_implied_correlation"] is not None
    assert pair["factor_corroboration_eligible"] is False
    assert pair["factor_corroboration_reason"] == (
        "unavailable_no_traceable_instrument_scope"
    )''',
)

print("P5-CORR-C precise patch applied successfully")
