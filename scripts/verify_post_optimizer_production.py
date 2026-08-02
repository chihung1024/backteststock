from __future__ import annotations

import base64
import gzip
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import requests

ORIGIN = "https://backteststock.chired.workers.dev"
MERGE_SHA = "1ed3c720551ce44c1ce18e6a5f1748eeaa49f1a6"
BACKUP_BRANCH = "release-backup/post-optimizer-manual-30-sortable-20260802T0355Z"
TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
    "META", "AVGO", "TSLA", "JPM", "WMT",
    "COST", "LLY", "XOM", "V", "MA",
    "HD", "NFLX", "ORCL", "AMD", "CSCO",
]
BENCHMARK = "SPY"
START_DATE = "2016-08-01"
END_DATE = "2026-07-31"
DIAGNOSTICS = Path("diagnostics")
USER_AGENT = "backteststock-post-merge-verification/3"


def write_json(name: str, value) -> None:
    DIAGNOSTICS.mkdir(exist_ok=True)
    (DIAGNOSTICS / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def post_json(path: str, payload: dict, timeout: int = 300):
    last = None
    for attempt in range(1, 5):
        started = time.perf_counter()
        response = requests.post(
            ORIGIN + path,
            json=payload,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
        elapsed = time.perf_counter() - started
        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text[:2000]}
        if response.status_code == 200:
            return body, elapsed, {key.lower(): value for key, value in response.headers.items()}
        last = (response.status_code, body, elapsed)
        if response.status_code not in (429, 500, 502, 503, 504):
            break
        time.sleep(5 * attempt)
    raise RuntimeError(f"{path} failed: {last}")


def get_text(path: str):
    response = requests.get(
        ORIGIN + path,
        timeout=60,
        allow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    if not response.content:
        raise AssertionError(f"empty production asset: {path}")
    return response


def page_and_prepare() -> None:
    DIAGNOSTICS.mkdir(exist_ok=True)
    home = get_text("/")
    optimizer_page = get_text("/optimizer.html")
    home_text = home.text
    optimizer_text = optimizer_page.text
    assert 'id="open-optimizer"' in home_text
    assert 'href="/optimizer.html"' in home_text
    for marker in (
        "五目標平衡搜尋（無單一主要目標）",
        "300 組（5×48 + 60）",
        "/optimizer.js?v=20260802.3",
        "/ui-enhancements.js?v=20260802.3",
        "/optimizer-ui-hardening.js?v=20260802.3",
    ):
        assert marker in optimizer_text, marker

    assets = {}
    asset_text = {}
    for name in (
        "optimizer.js",
        "optimizer-worker.js",
        "optimizer-balanced-worker.js",
        "ui-enhancements.js",
        "optimizer-ui-hardening.js",
        "optimizer.css",
    ):
        response = get_text(f"/{name}")
        assets[name] = {
            "finalUrl": response.url,
            "bytes": len(response.content),
            "sha256": hashlib.sha256(response.content).hexdigest(),
        }
        if name.endswith(".js"):
            asset_text[name] = response.text
    assert "const EXACT_OBJECTIVE_QUOTA = 48;" in asset_text["optimizer-balanced-worker.js"]
    assert "const EXACT_DIVERSITY_QUOTA = 60;" in asset_text["optimizer-balanced-worker.js"]
    assert "const BALANCED_WORKER_URL" in asset_text["optimizer-ui-hardening.js"]
    page_report = {
        "home": {
            "finalUrl": home.url,
            "bytes": len(home.content),
            "sha256": hashlib.sha256(home.content).hexdigest(),
        },
        "optimizer": {
            "requestedUrl": ORIGIN + "/optimizer.html",
            "finalUrl": optimizer_page.url,
            "bytes": len(optimizer_page.content),
            "sha256": hashlib.sha256(optimizer_page.content).hexdigest(),
        },
        "assets": assets,
    }
    write_json("production-page-report.json", page_report)

    calendar, calendar_seconds, calendar_headers = post_json(
        "/api/optimizer/calendar",
        {
            "startDate": START_DATE,
            "endDate": END_DATE,
            "benchmark": BENCHMARK,
            "trainingRatio": 0.70,
        },
    )
    total = calendar["trainingObservations"] + calendar["validationObservations"]
    assert calendar["trainingRatio"] == 0.70
    assert calendar["trainingObservations"] == math.floor(total * 0.70)
    assert calendar["benchmark"] == BENCHMARK
    assert calendar["benchmarkCorporateActionAudit"]["status"] == "verified_standard_actions"

    prepared, prepare_seconds, prepare_headers = post_json(
        "/api/optimizer/prepare",
        {
            "startDate": START_DATE,
            "endDate": END_DATE,
            "benchmark": BENCHMARK,
            "trainingRatio": 0.70,
            "trainingEnd": calendar["trainingEnd"],
            "candidateTickers": TICKERS,
            "candidateSelection": {
                "mode": "post_merge_production_verification",
                "rankingField": "sortino_ratio",
                "sourceTickerCount": len(TICKERS),
                "finalCandidateCount": 20,
            },
        },
    )
    envelope = prepared["snapshot"]
    raw = gzip.decompress(base64.b64decode(envelope["data"], validate=True))
    snapshot = json.loads(raw)
    assert snapshot["candidateTickers"] == TICKERS
    assert snapshot["benchmark"] == BENCHMARK
    assert snapshot["split"]["trainingObservations"] == calendar["trainingObservations"]
    assert snapshot["split"]["validationObservations"] == calendar["validationObservations"]
    assert snapshot["trainingRatio"] == 0.70
    assert len(snapshot["dates"]) == total
    assert envelope["datasetHash"] and envelope["signature"]
    assert envelope["signatureMode"].startswith("hmac-sha256")
    assert snapshot["dataSourceSettings"] == {
        "interval": "1d",
        "auto_adjust": False,
        "repair": True,
        "actions": True,
        "keepna": False,
    }
    required = [*TICKERS, BENCHMARK]
    statuses = prepared["summary"]["corporateActionStatus"]
    assert all(statuses[ticker] == "verified_standard_actions" for ticker in required)
    coverage = prepared["summary"]["dataCoverageAudit"]
    for ticker in required:
        assert coverage[ticker]["training"] >= 0.98, (ticker, coverage[ticker])
        assert coverage[ticker]["validation"] >= 0.98, (ticker, coverage[ticker])
    assert coverage["_global_complete_case"]["training"] >= 0.98
    assert coverage["_global_complete_case"]["validation"] >= 0.98
    assert len(snapshot["priceFingerprints"]) == 21

    report = {
        "calendarSeconds": calendar_seconds,
        "prepareSeconds": prepare_seconds,
        "requestedStart": START_DATE,
        "requestedEnd": END_DATE,
        "observations": total,
        "trainingObservations": calendar["trainingObservations"],
        "validationObservations": calendar["validationObservations"],
        "trainingStart": calendar["trainingStart"],
        "trainingEnd": calendar["trainingEnd"],
        "validationStart": calendar["validationStart"],
        "validationEnd": calendar["validationEnd"],
        "candidateCount": len(TICKERS),
        "benchmark": BENCHMARK,
        "compressedBytes": envelope["compressedBytes"],
        "uncompressedBytes": envelope["uncompressedBytes"],
        "datasetHash": envelope["datasetHash"],
        "signatureMode": envelope["signatureMode"],
        "optimizerAlgorithmVersion": snapshot["optimizerAlgorithmVersion"],
        "metricDefinitionVersion": snapshot["metricDefinitionVersion"],
        "marketDataContractVersion": snapshot["marketDataContractVersion"],
        "allCorporateActionsVerified": True,
        "strictCoverageVerified": True,
        "dataSourceSettings": snapshot["dataSourceSettings"],
        "calendarResponseVersion": calendar_headers.get("x-optimizer-algorithm-version"),
        "prepareResponseVersion": prepare_headers.get("x-optimizer-algorithm-version"),
    }
    (DIAGNOSTICS / "production-prepared.json").write_text(
        json.dumps(prepared, ensure_ascii=False), encoding="utf-8"
    )
    (DIAGNOSTICS / "production-snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False), encoding="utf-8"
    )
    write_json("production-prepare-report.json", report)
    print(json.dumps({"page": page_report, "prepare": report}, ensure_ascii=False, indent=2))


def exact_verify() -> None:
    prepared = json.loads((DIAGNOSTICS / "production-prepared.json").read_text())
    snapshot = json.loads((DIAGNOSTICS / "production-snapshot.json").read_text())
    search = json.loads((DIAGNOSTICS / "production-search-output.json").read_text())
    combinations = search["combinations"]
    settings = {"bandRatio": 0.20, "transactionCostBps": 0}

    payload, production_seconds, _headers = post_json(
        "/api/optimizer/verify",
        {
            "snapshot": prepared["snapshot"],
            "settings": settings,
            "combinations": combinations,
        },
    )
    results = payload["results"]
    metadata = payload["metadata"]
    assert len(results) == 300
    assert len({row["mask"] for row in results}) == 300
    assert metadata["verified_combinations"] == 300
    assert metadata["dataset_hash"] == prepared["snapshot"]["datasetHash"]
    assert math.isclose(metadata["rebalance_band_ratio"], 0.20, rel_tol=0, abs_tol=1e-15)
    assert math.isclose(metadata["trigger_lower_bound"], 0.08, rel_tol=0, abs_tol=1e-15)
    assert math.isclose(metadata["trigger_upper_bound"], 0.12, rel_tol=0, abs_tol=1e-15)
    assert metadata["execution_delay_trading_days"] == 1
    assert metadata["execution_price"] == "next_common_trading_day_adjusted_close"
    assert metadata["turnover_definition"] == "gross_notional_and_one_way"
    assert metadata["price_fingerprints"] == snapshot["priceFingerprints"]

    finite_keys = (
        "total_return", "cagr", "mdd", "volatility", "sharpe_ratio",
        "sortino_ratio", "beta", "alpha", "annualizedTurnoverOneWay",
        "transactionCost", "turnoverGross", "turnoverOneWay",
    )
    for row in results:
        assert len(row["tickers"]) == 10 and len(set(row["tickers"])) == 10
        for period in ("training", "validation"):
            metrics = row[period]
            for key in finite_keys:
                value = metrics[key]
                assert isinstance(value, (int, float)) and math.isfinite(value), (
                    row["combinationId"], period, key, value
                )
            assert isinstance(metrics["rebalanceCount"], int)
            assert metrics["rebalanceCount"] >= 0
            assert metrics["portfolioValueFingerprint"]

    repeat_payload, repeat_seconds, _headers = post_json(
        "/api/optimizer/verify",
        {
            "snapshot": prepared["snapshot"],
            "settings": settings,
            "combinations": [combinations[0]],
        },
    )
    repeat = repeat_payload["results"][0]
    first = results[0]
    for period in ("training", "validation"):
        assert repeat[period]["portfolioValueFingerprint"] == first[period]["portfolioValueFingerprint"]
    assert repeat["training"]["sortino_ratio"] == first["training"]["sortino_ratio"]
    assert repeat["validation"]["cagr"] == first["validation"]["cagr"]

    from api import optimizer

    def forbidden_download(*_args, **_kwargs):
        raise AssertionError("verify attempted a second market download")

    optimizer.app.config.update(TESTING=True)
    optimizer._download_common_prices = forbidden_download
    client = optimizer.app.test_client()
    local_started = time.perf_counter()
    local_response = client.post(
        "/api/optimizer/verify",
        json={
            "snapshot": prepared["snapshot"],
            "settings": settings,
            "combinations": combinations,
        },
    )
    local_seconds = time.perf_counter() - local_started
    assert local_response.status_code == 200, local_response.get_json()
    local_results = local_response.get_json()["results"]
    assert len(local_results) == 300
    production_by_id = {row["combinationId"]: row for row in results}
    for local_row in local_results:
        production_row = production_by_id[local_row["combinationId"]]
        for period in ("training", "validation"):
            assert local_row[period]["portfolioValueFingerprint"] == production_row[period]["portfolioValueFingerprint"]
            for key in (
                "sortino_ratio", "cagr", "mdd", "beta", "alpha",
                "annualizedTurnoverOneWay", "rebalanceCount",
            ):
                assert local_row[period][key] == production_row[period][key], (
                    local_row["combinationId"], period, key
                )

    report = {
        "productionExactSeconds": production_seconds,
        "repeatSeconds": repeat_seconds,
        "localSnapshotOnlySeconds": local_seconds,
        "resultCount": len(results),
        "uniqueMasks": len({row["mask"] for row in results}),
        "datasetHash": metadata["dataset_hash"],
        "sameSignedSnapshotUsed": True,
        "marketDownloadDuringVerify": False,
        "productionMatchesLocalSnapshotOnly": True,
        "deterministicExact": True,
        "allTrainingFinite": True,
        "allValidationFinite": True,
        "totalTrainingRebalances": sum(row["training"]["rebalanceCount"] for row in results),
        "totalValidationRebalances": sum(row["validation"]["rebalanceCount"] for row in results),
        "trainingFingerprintSample": first["training"]["portfolioValueFingerprint"],
        "validationFingerprintSample": first["validation"]["portfolioValueFingerprint"],
        "rebalanceBandRatio": metadata["rebalance_band_ratio"],
        "triggerLowerBound": metadata["trigger_lower_bound"],
        "triggerUpperBound": metadata["trigger_upper_bound"],
        "executionDelayTradingDays": metadata["execution_delay_trading_days"],
        "turnoverDefinition": metadata["turnover_definition"],
    }
    write_json("production-exact-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def summarize() -> None:
    summary = {
        "mergeSha": MERGE_SHA,
        "backupBranch": BACKUP_BRANCH,
        "productionOrigin": ORIGIN,
        "page": json.loads((DIAGNOSTICS / "production-page-report.json").read_text()),
        "prepare": json.loads((DIAGNOSTICS / "production-prepare-report.json").read_text()),
        "search": json.loads((DIAGNOSTICS / "production-search-report.json").read_text()),
        "exact": json.loads((DIAGNOSTICS / "production-exact-report.json").read_text()),
        "persistentDailyPriceDatabase": False,
    }
    write_json("post-optimizer-production-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    if os.environ.get("VERCEL_GIT_COMMIT_SHA") != MERGE_SHA:
        raise RuntimeError("verification signing key is not pinned to the production merge SHA")
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "prepare":
        page_and_prepare()
    elif command == "exact":
        exact_verify()
    elif command == "summary":
        summarize()
    else:
        raise SystemExit("usage: verify_post_optimizer_production.py prepare|exact|summary")


if __name__ == "__main__":
    main()
