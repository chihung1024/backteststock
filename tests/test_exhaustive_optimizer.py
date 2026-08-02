import base64
import gzip
import json

import numpy as np
import pandas as pd

from api import exhaustive_optimizer


def verified_audits(tickers):
    return {
        ticker: {"status": "verified_standard_actions", "warning_dates": []}
        for ticker in tickers
    }


def synthetic_common(tickers, periods=100):
    dates = pd.bdate_range("2024-01-02", periods=periods)
    frame = pd.DataFrame(
        {
            ticker: np.linspace(100 + index, 125 + index, periods)
            for index, ticker in enumerate(tickers)
        },
        index=dates,
    )
    frame.attrs["reference_index"] = dates
    frame.attrs["availability_masks"] = {
        ticker: np.ones(periods, dtype=bool) for ticker in tickers
    }
    return frame


def decode_unsigned(envelope):
    return json.loads(gzip.decompress(base64.b64decode(envelope["data"])))


def test_exhaustive_snapshot_is_deterministic_and_signed(monkeypatch):
    monkeypatch.setenv("OPTIMIZER_SIGNING_SECRET", "exhaustive-test-secret")
    snapshot = {
        "formatVersion": exhaustive_optimizer.EXHAUSTIVE_SNAPSHOT_FORMAT,
        "optimizerMode": "exhaustive_full_period",
        "candidateTickers": ["AAPL", "MSFT"],
    }
    first = exhaustive_optimizer._encode_exhaustive_snapshot(snapshot)
    second = exhaustive_optimizer._encode_exhaustive_snapshot(snapshot)
    assert first == second
    assert first["signatureMode"] == "hmac-sha256-secret"
    assert decode_unsigned(first) == snapshot


def test_full_period_coverage_rejects_late_ticker():
    source = ["AAPL", "MSFT", "LATE"]
    required = [*source, "SPY"]
    common = synthetic_common(required, periods=100)
    common.attrs["availability_masks"]["LATE"][:20] = False
    common = common.iloc[20:].copy()
    common.attrs["reference_index"] = pd.bdate_range("2024-01-02", periods=100)
    masks = {ticker: np.ones(100, dtype=bool) for ticker in required}
    masks["LATE"][:20] = False
    common.attrs["availability_masks"] = masks
    try:
        exhaustive_optimizer._strict_full_period_coverage(common, source, "SPY")
    except exhaustive_optimizer.legacy.ValidationError as exc:
        assert "不會靜默" in str(exc)
        assert "LATE" in str(exc)
    else:
        raise AssertionError("late ticker should fail strict coverage")


def test_prepare_exhaustive_accepts_variable_source_pool(monkeypatch):
    exhaustive_optimizer.app.config.update(TESTING=True)
    client = exhaustive_optimizer.app.test_client()
    source = [f"T{index:02d}" for index in range(25)]
    required = [*source, "SPY"]
    common = synthetic_common(required, periods=100)
    audits = verified_audits(required)
    monkeypatch.setattr(
        exhaustive_optimizer,
        "_download_full_period_prices",
        lambda tickers, _start, _end, _benchmark: (common[tickers], audits),
    )
    response = client.post(
        "/api/optimizer/exhaustive/prepare",
        json={
            "sourceTickers": source,
            "benchmark": "SPY",
            "startDate": "2024-01-02",
            "endDate": "2024-05-31",
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    snapshot = decode_unsigned(payload["snapshot"])
    assert snapshot["optimizerMode"] == "exhaustive_full_period"
    assert snapshot["candidateTickers"] == source
    assert "split" not in snapshot
    assert snapshot["persistentDailyPriceDatabase"] is False
    assert payload["summary"]["sourceTickerCount"] == 25
    assert payload["summary"]["observations"] == 100
