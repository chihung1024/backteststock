from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import time
from pathlib import Path

import requests

ORIGIN = os.environ.get("ORIGIN", "https://backteststock.chired.workers.dev")
DIAG = Path("diagnostics")
DIAG.mkdir(exist_ok=True)

payload = {
    "sourceTickers": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
        "AVGO", "JPM", "WMT", "XOM", "COST",
    ],
    "benchmark": "SPY",
    "startDate": "2016-08-02",
    "endDate": "2026-08-01",
}
started = time.perf_counter()
response = requests.post(
    f"{ORIGIN}/api/optimizer/exhaustive/prepare",
    json=payload,
    timeout=260,
)
elapsed = time.perf_counter() - started
response.raise_for_status()
body = response.json()
envelope = body["snapshot"]
compressed = base64.b64decode(envelope["data"])
raw = gzip.decompress(compressed)
snapshot = json.loads(raw)
assert envelope["format"] == "exhaustive-optimizer-snapshot-json-gzip-v1"
assert envelope["encoding"] == "gzip+base64"
assert len(envelope["signature"]) == 64
assert envelope["datasetHash"] == hashlib.sha256(raw).hexdigest()
assert snapshot["optimizerMode"] == "exhaustive_full_period"
assert snapshot["candidateTickers"] == payload["sourceTickers"]
assert snapshot["benchmark"] == "SPY"
assert "split" not in snapshot
assert snapshot["persistentDailyPriceDatabase"] is False
assert len(snapshot["dates"]) >= 2400
assert snapshot["actualStart"] <= "2016-08-09"
assert snapshot["actualEnd"] >= "2026-07-27"
assert set(snapshot["supportedRebalanceModes"]) == {
    "band", "monthly", "quarterly", "annually", "never"
}
settings = snapshot["dataSourceSettings"]
assert settings.get("auto_adjust") is False
assert settings.get("actions") is True
assert settings.get("repair") is True
for ticker in [*payload["sourceTickers"], "SPY"]:
    assert snapshot["corporateActionAudits"][ticker]["status"] == "verified_standard_actions"
    assert len(snapshot["prices"][ticker]) == len(snapshot["dates"])
assert body["summary"]["persistentDailyPriceDatabase"] is False
(DIAG / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
(DIAG / "prepare.json").write_text(json.dumps({
    "elapsed_seconds": elapsed,
    "http_status": response.status_code,
    "compressed_bytes": envelope["compressedBytes"],
    "uncompressed_bytes": envelope["uncompressedBytes"],
    "dataset_hash": envelope["datasetHash"],
    "signature_mode": envelope["signatureMode"],
    "observations": len(snapshot["dates"]),
    "actual_start": snapshot["actualStart"],
    "actual_end": snapshot["actualEnd"],
}, indent=2), encoding="utf-8")
print(json.dumps({
    "prepare_seconds": round(elapsed, 3),
    "observations": len(snapshot["dates"]),
    "dataset_hash": envelope["datasetHash"],
}, ensure_ascii=False))
