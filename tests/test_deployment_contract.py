import importlib.util
import json
from pathlib import Path

from api import index_v2, scan_v2
from api.metrics import DATA_SOURCE_SETTINGS, METRIC_DEFINITION_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_metric_version_is_synchronized_across_runtime_browser_and_docs():
    browser_source = (ROOT / "public" / "scan-score-formulas.js").read_text(
        encoding="utf-8"
    )
    documentation = (ROOT / "docs" / "METRICS_REPRODUCIBILITY.md").read_text(
        encoding="utf-8"
    )

    assert (
        f'METRIC_DEFINITION_VERSION = "{METRIC_DEFINITION_VERSION}"'
        in browser_source
    )
    assert METRIC_DEFINITION_VERSION in documentation


def test_vercel_routes_use_deterministic_runtime_entrypoints():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    builds = {item["src"] for item in config["builds"]}
    routes = {item["src"]: item["dest"] for item in config["routes"]}

    assert "api/index_v2.py" in builds
    assert "api/scan_v2.py" in builds
    assert "api/optimizer.py" not in builds
    assert routes["/api/scan"] == "api/scan_v2.py"
    assert "/api/optimizer/(.*)" not in routes
    assert routes["/api/(.*)"] == "api/index_v2.py"


def test_wsgi_backtest_route_is_replaced_with_deterministic_handler():
    assert (
        index_v2.app.view_functions["backtest_handler"]
        is index_v2.backtest_handler
    )


def test_scan_and_backtest_share_identical_market_data_contract():
    assert scan_v2.DATA_SOURCE_SETTINGS is DATA_SOURCE_SETTINGS
    assert index_v2.DATA_SOURCE_SETTINGS is DATA_SOURCE_SETTINGS
    assert DATA_SOURCE_SETTINGS == {
        "interval": "1d",
        "auto_adjust": False,
        "repair": True,
        "actions": True,
        "keepna": False,
    }


def test_production_requirements_are_fully_pinned():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    package_lines = [
        line.strip()
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert package_lines
    assert all("==" in line for line in package_lines)
    assert "numpy==2.2.6" in package_lines
    assert "pandas==2.2.3" in package_lines
    assert "scipy==1.17.1" in package_lines
    assert "yfinance==1.5.2" in package_lines


def test_yfinance_price_repair_dependency_is_installed():
    assert DATA_SOURCE_SETTINGS["repair"] is True
    assert importlib.util.find_spec("scipy") is not None
