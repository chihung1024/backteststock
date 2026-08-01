from __future__ import annotations

import json
import time
from pathlib import Path

from api import optimizer


TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
    "META", "AVGO", "TSLA", "JPM", "WMT",
    "COST", "LLY", "XOM", "V", "MA",
    "HD", "NFLX", "ORCL", "AMD", "CSCO",
]
START_DATE = "2016-08-01"
END_DATE = "2026-07-31"
BENCHMARK = "SPY"


def post_json(client, path: str, payload: dict):
    started = time.perf_counter()
    response = client.post(path, json=payload)
    elapsed = time.perf_counter() - started
    body = response.get_json(silent=True)
    if response.status_code != 200:
        raise RuntimeError(
            f"{path} failed HTTP {response.status_code} after {elapsed:.3f}s: {body}"
        )
    return body, elapsed


def main():
    output_dir = Path("diagnostics")
    output_dir.mkdir(exist_ok=True)
    optimizer.app.config.update(TESTING=True)
    client = optimizer.app.test_client()

    calendar, calendar_seconds = post_json(
        client,
        "/api/optimizer/calendar",
        {
            "startDate": START_DATE,
            "endDate": END_DATE,
            "benchmark": BENCHMARK,
            "trainingRatio": 0.70,
        },
    )
    prepared, prepare_seconds = post_json(
        client,
        "/api/optimizer/prepare",
        {
            "startDate": START_DATE,
            "endDate": END_DATE,
            "benchmark": BENCHMARK,
            "trainingRatio": 0.70,
            "trainingEnd": calendar["trainingEnd"],
            "candidateTickers": TICKERS,
            "candidateSelection": {
                "mode": "strict_training_only_real_data_verification",
                "rankingField": "sortino_ratio",
                "sourceTickerCount": len(TICKERS),
                "candidateTickers": TICKERS,
            },
        },
    )
    snapshot = optimizer._decode_snapshot(prepared["snapshot"])
    report = {
        "calendarSeconds": calendar_seconds,
        "prepareSeconds": prepare_seconds,
        "candidateCount": len(snapshot["candidateTickers"]),
        "benchmark": snapshot["benchmark"],
        "observationCount": len(snapshot["dates"]),
        "trainingObservations": snapshot["split"]["trainingObservations"],
        "validationObservations": snapshot["split"]["validationObservations"],
        "trainingStart": snapshot["split"]["trainingStart"],
        "trainingEnd": snapshot["split"]["trainingEnd"],
        "validationStart": snapshot["split"]["validationStart"],
        "validationEnd": snapshot["split"]["validationEnd"],
        "compressedBytes": prepared["snapshot"]["compressedBytes"],
        "uncompressedBytes": prepared["snapshot"]["uncompressedBytes"],
        "base64Characters": len(prepared["snapshot"]["data"]),
        "datasetHash": prepared["snapshot"]["datasetHash"],
        "signatureMode": prepared["snapshot"]["signatureMode"],
        "metricDefinitionVersion": snapshot["metricDefinitionVersion"],
        "marketDataContractVersion": snapshot["marketDataContractVersion"],
        "corporateActionStatuses": {
            ticker: audit.get("status")
            for ticker, audit in snapshot["corporateActionAudits"].items()
        },
        "allCorporateActionsVerified": all(
            audit.get("status") == "verified_standard_actions"
            for audit in snapshot["corporateActionAudits"].values()
        ),
    }
    (output_dir / "optimizer-prepared.json").write_text(
        json.dumps(prepared, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "optimizer-prepare-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
