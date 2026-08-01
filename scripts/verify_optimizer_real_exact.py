from __future__ import annotations

import json
import math
import time
from pathlib import Path

from api import optimizer


def assert_finite_metrics(row: dict, period: str):
    metrics = row[period]
    for key in (
        "total_return",
        "cagr",
        "mdd",
        "volatility",
        "sharpe_ratio",
        "sortino_ratio",
        "beta",
        "alpha",
        "annualizedTurnoverOneWay",
        "transactionCost",
    ):
        value = metrics.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise AssertionError(f"non-finite {period}.{key}: {value}")


def main():
    output_dir = Path("diagnostics")
    prepared = json.loads(
        (output_dir / "optimizer-prepared.json").read_text(encoding="utf-8")
    )
    search = json.loads(
        (output_dir / "optimizer-search-output.json").read_text(encoding="utf-8")
    )
    combinations = search["combinations"]
    optimizer.app.config.update(TESTING=True)
    client = optimizer.app.test_client()

    def forbidden_download(*_args, **_kwargs):
        raise AssertionError("verify attempted to download market data")

    optimizer._download_common_prices = forbidden_download
    settings = {
        "bandRatio": 0.20,
        "transactionCostBps": 0,
        "targetWeight": 0.1,
        "executionDelayTradingDays": 1,
    }
    batch_reports = []
    results = []
    metadata = None
    started_all = time.perf_counter()
    for offset in range(0, len(combinations), 100):
        chunk = combinations[offset : offset + 100]
        started = time.perf_counter()
        response = client.post(
            "/api/optimizer/verify",
            json={
                "snapshot": prepared["snapshot"],
                "settings": settings,
                "combinations": chunk,
            },
        )
        elapsed = time.perf_counter() - started
        payload = response.get_json(silent=True)
        if response.status_code != 200:
            raise RuntimeError(
                f"verify batch HTTP {response.status_code} after {elapsed:.3f}s: {payload}"
            )
        results.extend(payload["results"])
        metadata = payload["metadata"]
        batch_reports.append(
            {
                "offset": offset,
                "requested": len(chunk),
                "returned": len(payload["results"]),
                "elapsedSeconds": elapsed,
            }
        )
    total_seconds = time.perf_counter() - started_all

    masks = [row["mask"] for row in results]
    if len(results) != 300 or len(set(masks)) != 300:
        raise AssertionError(
            f"expected 300 unique exact results, got {len(results)} / {len(set(masks))}"
        )
    for row in results:
        if len(row["tickers"]) != 10 or len(set(row["tickers"])) != 10:
            raise AssertionError("exact result does not contain 10 unique tickers")
        assert_finite_metrics(row, "training")
        assert_finite_metrics(row, "validation")

    first_combination = combinations[0]
    repeat_response = client.post(
        "/api/optimizer/verify",
        json={
            "snapshot": prepared["snapshot"],
            "settings": settings,
            "combinations": [first_combination],
        },
    )
    if repeat_response.status_code != 200:
        raise RuntimeError(f"repeat verify failed: {repeat_response.get_json()}")
    repeat = repeat_response.get_json()["results"][0]
    first = results[0]
    deterministic_exact = (
        first["training"]["portfolioValueFingerprint"]
        == repeat["training"]["portfolioValueFingerprint"]
        and first["validation"]["portfolioValueFingerprint"]
        == repeat["validation"]["portfolioValueFingerprint"]
        and first["training"]["sortino_ratio"]
        == repeat["training"]["sortino_ratio"]
        and first["validation"]["cagr"] == repeat["validation"]["cagr"]
    )
    if not deterministic_exact:
        raise AssertionError("exact verification was not deterministic")

    top_sortino = max(results, key=lambda row: row["training"]["sortino_ratio"])
    top_cagr = max(results, key=lambda row: row["training"]["cagr"])
    lowest_mdd = min(results, key=lambda row: abs(row["training"]["mdd"]))
    lowest_beta = min(results, key=lambda row: abs(row["training"]["beta"]))
    top_alpha = max(results, key=lambda row: row["training"]["alpha"])
    report = {
        "totalExactSeconds": total_seconds,
        "batchReports": batch_reports,
        "resultCount": len(results),
        "uniqueMasks": len(set(masks)),
        "marketDownloadDuringVerify": False,
        "deterministicExact": deterministic_exact,
        "allTrainingFinite": True,
        "allValidationFinite": True,
        "totalTrainingRebalances": sum(
            row["training"]["rebalanceCount"] for row in results
        ),
        "totalValidationRebalances": sum(
            row["validation"]["rebalanceCount"] for row in results
        ),
        "metadataDatasetHash": metadata.get("dataset_hash"),
        "metadataVerifiedCombinationsPerLastBatch": metadata.get(
            "verified_combinations"
        ),
        "champions": {
            "sortino": {
                "tickers": top_sortino["tickers"],
                "training": top_sortino["training"],
                "validation": top_sortino["validation"],
            },
            "cagr": {
                "tickers": top_cagr["tickers"],
                "training": top_cagr["training"],
                "validation": top_cagr["validation"],
            },
            "mdd": {
                "tickers": lowest_mdd["tickers"],
                "training": lowest_mdd["training"],
                "validation": lowest_mdd["validation"],
            },
            "beta": {
                "tickers": lowest_beta["tickers"],
                "training": lowest_beta["training"],
                "validation": lowest_beta["validation"],
            },
            "alpha": {
                "tickers": top_alpha["tickers"],
                "training": top_alpha["training"],
                "validation": top_alpha["validation"],
            },
        },
    }
    (output_dir / "optimizer-exact-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
