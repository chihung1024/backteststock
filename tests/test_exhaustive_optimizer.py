import base64
import gzip
import json

import numpy as np
import pandas as pd
import pytest

from api import exhaustive_optimizer
from apps.api.app.data.history_service import PartialTWDHistories, TWDAssetHistory
from apps.api.app.data.twd_valuation import TWDValuation


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


def twd_history(symbol, currency, native, fx, twd, dates):
    index = pd.DatetimeIndex(dates)
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency=currency,
        valuation=TWDValuation(
            source_currency=currency,
            native_adjusted_close=pd.Series(native, index=index, dtype=float),
            fx_to_twd=pd.Series(fx, index=index, dtype=float),
            adjusted_close_twd=pd.Series(twd, index=index, dtype=float),
            daily_returns=pd.Series(twd, index=index, dtype=float)
            .pct_change(fill_method=None)
            .fillna(0.0),
        ),
        corporate_action_audit={"status": "verified_standard_actions"},
        fx_audit={"method": "direct", "tickers": ["USDTWD=X"]},
    )


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


def test_exhaustive_snapshot_prices_are_twd_valuations(monkeypatch):
    dates = pd.bdate_range("2024-01-02", periods=65)
    fx = np.linspace(30.0, 31.0, len(dates))
    histories = {
        "AAA": twd_history(
            "AAA",
            "USD",
            np.full(len(dates), 100.0),
            fx,
            100.0 * fx,
            dates,
        ),
        "SPY": twd_history(
            "SPY",
            "USD",
            np.full(len(dates), 200.0),
            fx,
            200.0 * fx,
            dates,
        ),
    }

    class FakeHistoryService:
        def __init__(self):
            self.calls = []

        def histories_partial(self, tickers, start, end):
            self.calls.append((tickers, start, end))
            return PartialTWDHistories(
                requested=tuple(tickers), histories=histories, failures={}
            )

    fake = FakeHistoryService()
    monkeypatch.setattr(exhaustive_optimizer, "twd_history_service", fake)

    common, audits = exhaustive_optimizer._download_full_period_prices(
        ["AAA", "SPY"], "2024-01-02", "2024-04-01", "SPY"
    )

    assert fake.calls[0][1].isoformat() == "2024-01-02"
    assert fake.calls[0][2].isoformat() == "2024-03-31"
    assert common["AAA"].iloc[0] == pytest.approx(3000.0)
    assert common["AAA"].iloc[-1] == pytest.approx(3100.0)
    assert common.attrs["valuation_currency"] == "TWD"
    assert common.attrs["native_price_fingerprints"]["AAA"]
    assert common.attrs["fx_price_fingerprints"]["AAA"]
    assert audits["AAA"]["status"] == "verified_standard_actions"


def test_prepare_exhaustive_accepts_variable_source_pool(monkeypatch):
    exhaustive_optimizer.app.config.update(TESTING=True)
    client = exhaustive_optimizer.app.test_client()
    source = [f"T{index:03d}" for index in range(61)]
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
            "holdingCount": 1,
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
    assert snapshot["riskFreeRate"] == exhaustive_optimizer.legacy.RISK_FREE_RATE
    assert "split" not in snapshot
    assert snapshot["persistentDailyPriceDatabase"] is False
    assert payload["summary"]["sourceTickerCount"] == 61
    assert payload["summary"]["holdingCount"] == 1
    assert payload["summary"]["combinationCount"] == 61
    assert payload["summary"]["observations"] == 100
    assert snapshot["valuationCurrency"] == "TWD"
    assert snapshot["twdValuationContractVersion"]
    assert snapshot["nativePriceFingerprints"] == {}
    assert snapshot["fxPriceFingerprints"] == {}
    assert response.headers["X-Valuation-Currency"] == "TWD"
    assert response.headers["X-TWD-Valuation-Contract-Version"]


def test_prepare_exhaustive_rejects_more_than_50m_before_market_download(monkeypatch):
    exhaustive_optimizer.app.config.update(TESTING=True)
    client = exhaustive_optimizer.app.test_client()
    calls = []
    monkeypatch.setattr(
        exhaustive_optimizer,
        "_download_full_period_prices",
        lambda *_args: calls.append(_args),
    )
    source = [f"T{index:03d}" for index in range(30)]

    response = client.post(
        "/api/optimizer/exhaustive/prepare",
        json={
            "sourceTickers": source,
            "holdingCount": 15,
            "benchmark": "SPY",
            "startDate": "2024-01-02",
            "endDate": "2024-05-31",
        },
    )

    assert response.status_code == 400
    assert "50,000,000" in response.get_json()["error"]
    assert calls == []


def test_prepare_exhaustive_rejects_more_than_platform_source_limit(monkeypatch):
    exhaustive_optimizer.app.config.update(TESTING=True)
    client = exhaustive_optimizer.app.test_client()
    calls = []
    monkeypatch.setattr(
        exhaustive_optimizer,
        "_download_full_period_prices",
        lambda *_args: calls.append(_args),
    )

    response = client.post(
        "/api/optimizer/exhaustive/prepare",
        json={
            "sourceTickers": [f"T{index:03d}" for index in range(101)],
            "holdingCount": 1,
            "benchmark": "SPY",
            "startDate": "2024-01-02",
            "endDate": "2024-05-31",
        },
    )

    assert response.status_code == 400
    assert "100" in response.get_json()["error"]
    assert calls == []
