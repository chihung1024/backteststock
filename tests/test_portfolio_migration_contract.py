from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "portfolio_migration"
DOC = ROOT / "docs" / "portfolio-migration" / "README.md"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def load_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_frozen_source_manifest_is_complete_and_immutable() -> None:
    manifest = load_json("source_manifest.json")
    assert manifest["schema_version"] == 1
    assert manifest["source_repository"] == "chihung1024/backtest"
    assert manifest["target_repository"] == "chihung1024/backteststock"
    assert manifest["target_page"] == "/portfolio/"
    assert manifest["source_version"] == "0.6.6"
    assert SHA40.fullmatch(manifest["source_commit"])

    expected_files = {
        "frontend/src/App.tsx",
        "backend/app/models.py",
        "backend/app/service.py",
        "backend/app/engine/backtest.py",
        "backend/app/engine/metrics.py",
        "backend/app/engine/analytics.py",
    }
    assert set(manifest["files"]) == expected_files
    assert all(SHA40.fullmatch(value) for value in manifest["files"].values())
    assert len(set(manifest["files"].values())) == len(expected_files)

    documentation = DOC.read_text(encoding="utf-8")
    assert manifest["source_commit"] in documentation
    assert "`/portfolio/`" in documentation


def test_capability_matrix_has_unique_traceable_requirements() -> None:
    matrix = load_json("capability_matrix.json")
    capabilities = matrix["capabilities"]
    ids = [item["id"] for item in capabilities]
    assert len(capabilities) >= 30
    assert len(ids) == len(set(ids))
    assert {item["phase"] for item in capabilities} == set(range(1, 8))
    assert all(item["status"] in matrix["statuses"] for item in capabilities)
    assert all(item["acceptance"].strip() for item in capabilities)
    assert all(item["required"] is True for item in capabilities)

    by_id = {item["id"]: item for item in capabilities}
    assert by_id["market.twd_daily"]["status"] == "implemented"
    assert by_id["metrics.xirr"]["status"] == "improved"
    assert by_id["dependency.remove_old_api"]["phase"] == 6
    assert by_id["retirement.delete_source"]["phase"] == 7


def test_legacy_request_fixture_exercises_full_feature_surface() -> None:
    request = load_json("legacy_request.json")
    assert request["base_currency"] == "TWD"
    assert date.fromisoformat(request["start_date"]) < date.fromisoformat(request["end_date"])
    assert 1 <= len(request["portfolios"]) <= 5
    for portfolio in request["portfolios"]:
        symbols = [asset["symbol"] for asset in portfolio["assets"]]
        assert len(symbols) == len(set(symbols))
        assert 1 <= len(symbols) <= 20
        assert abs(sum(asset["weight"] for asset in portfolio["assets"]) - 100.0) <= 0.05

    assert request["cashflow"]["type"] != "none"
    assert request["rebalancing"]["threshold_percent"] is not None
    assert request["transaction_cost_bps"] > 0
    assert request["leverage"]["type"] != "none"
    assert request["reinvest_dividends"] is False
    assert request["analytics"]["style_analysis"] is True
    assert request["analytics"]["factor_regression"] is True
    assert request["analytics"]["inflation_adjusted"] is True


def test_response_contract_preserves_legacy_and_v3_fields() -> None:
    contract = load_json("legacy_response_shape.json")
    assert {"results", "assets", "warnings"} <= set(contract["top_level_required"])
    assert {"metrics", "series", "target_allocation", "final_allocation"} <= set(
        contract["portfolio_result_required"]
    )
    assert {"cagr", "money_weighted_return", "max_drawdown", "calmar_ratio"} <= set(
        contract["legacy_metric_keys"]
    )
    assert {
        "metric_definition_version",
        "valuation_contract_version",
        "xirr_status",
        "data_audit",
    } <= set(contract["target_v3_additions"])


def test_synthetic_market_data_contains_required_edge_cases() -> None:
    with (FIXTURES / "synthetic_market_data.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) >= 8
    dates = [date.fromisoformat(row["date"]) for row in rows]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates))

    numeric_columns = [column for column in rows[0] if column != "date"]
    for row in rows:
        for column in numeric_columns:
            value = float(row[column])
            if "distribution" not in column:
                assert value > 0
            else:
                assert value >= 0

    assert any(float(row["AAA_distribution"]) > 0 for row in rows)
    assert any(float(row["BBB_distribution"]) > 0 for row in rows)
    assert len({float(row["AAA_fx_to_twd"]) for row in rows}) > 1

    raw_ratio = float(rows[3]["AAA_native_close"]) / float(rows[2]["AAA_native_close"])
    adjusted_ratio = float(rows[3]["AAA_adjusted_close"]) / float(
        rows[2]["AAA_adjusted_close"]
    )
    assert raw_ratio < 0.75  # split-like raw price discontinuity
    assert adjusted_ratio > 0.95  # adjusted history remains economically continuous


def test_scenarios_cover_data_ledger_and_failure_isolation() -> None:
    payload = load_json("scenarios.json")
    assert payload["fixture"] == "synthetic_market_data.csv"
    scenarios = payload["scenarios"]
    ids = {scenario["id"] for scenario in scenarios}
    assert len(ids) == len(scenarios)
    assert {scenario["phase"] for scenario in scenarios} >= {1, 2, 3}
    assert {
        "single_asset_total_return",
        "distribution_retained_as_cash",
        "monthly_contribution_with_cost",
        "fixed_ratio_leverage_margin_event",
        "benchmark_failure_is_non_destructive",
    } <= ids
    assertions = {
        assertion
        for scenario in scenarios
        for assertion in scenario.get("assertions", [])
    }
    assert {
        "no_look_ahead",
        "no_adjusted_close_double_count",
        "external_flow_excluded_from_twr",
        "margin_call_is_event_not_api_error",
        "portfolio_result_is_retained",
    } <= assertions
