import numpy as np
import pandas as pd
import pytest

from api import optimizer


@pytest.fixture()
def client():
    optimizer.app.config.update(TESTING=True)
    return optimizer.app.test_client()


def verified_audits(tickers):
    return {
        ticker: {
            "status": "verified_standard_actions",
            "warning_dates": [],
        }
        for ticker in tickers
    }


def synthetic_common(tickers, periods=100):
    dates = pd.bdate_range("2024-01-02", periods=periods)
    return pd.DataFrame(
        {
            ticker: np.linspace(100 + index, 120 + index, periods)
            for index, ticker in enumerate(tickers)
        },
        index=dates,
    )


def test_split_dates_uses_floor_common_trading_days():
    dates = pd.bdate_range("2024-01-02", periods=100)
    split = optimizer._split_dates(dates, 0.70)
    assert split["splitIndex"] == 70
    assert split["trainingObservations"] == 70
    assert split["validationObservations"] == 30
    assert split["trainingEnd"] == dates[69].strftime("%Y-%m-%d")
    assert split["validationStart"] == dates[70].strftime("%Y-%m-%d")


def test_snapshot_round_trip_is_deterministic_and_signed(monkeypatch):
    monkeypatch.setenv("OPTIMIZER_SIGNING_SECRET", "unit-test-secret")
    snapshot = {
        "formatVersion": optimizer.SNAPSHOT_FORMAT_VERSION,
        "candidateTickers": [f"T{index:02d}" for index in range(20)],
        "benchmark": "SPY",
        "dates": ["2024-01-02", "2024-01-03"],
        "prices": {},
    }
    first = optimizer._encode_snapshot(snapshot)
    second = optimizer._encode_snapshot(snapshot)
    assert first == second
    assert first["signatureMode"] == "hmac-sha256-secret"
    assert optimizer._decode_snapshot(first) == snapshot

    tampered = dict(first)
    tampered["signature"] = "0" * 64
    with pytest.raises(optimizer.legacy.ValidationError, match="簽章"):
        optimizer._decode_snapshot(tampered)


def test_relative_band_signal_executes_on_next_common_close():
    dates = pd.bdate_range("2024-01-02", periods=4)
    prices = np.full((4, 10), 100.0)
    prices[1:, 0] = 200.0
    result = optimizer._simulate_band(
        prices,
        dates,
        band_ratio=0.20,
        transaction_cost_bps=0,
    )
    assert result.rebalance_count == 1
    event = result.events[0]
    assert event["signalDate"] == dates[1].strftime("%Y-%m-%d")
    assert event["executionDate"] == dates[2].strftime("%Y-%m-%d")
    assert event["triggerIndexes"] == [0]
    assert event["transactionCost"] == 0


def test_initial_trade_cost_is_included():
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = np.full((3, 10), 100.0)
    result = optimizer._simulate_band(
        prices,
        dates,
        band_ratio=0.20,
        transaction_cost_bps=10,
    )
    assert result.initial_trade_cost > 0
    assert result.history.iloc[0, 0] < 10_000
    assert result.transaction_cost == pytest.approx(result.initial_trade_cost)


def test_prepare_and_verify_use_same_signed_snapshot(client, monkeypatch):
    monkeypatch.setenv("OPTIMIZER_SIGNING_SECRET", "endpoint-test-secret")
    candidates = [f"T{index:02d}" for index in range(20)]
    required = [*candidates, "SPY"]
    common = synthetic_common(required, periods=100)
    audits = verified_audits(required)

    monkeypatch.setattr(
        optimizer,
        "_download_common_prices",
        lambda tickers, _start, _end: (common[tickers], audits),
    )

    prepare_response = client.post(
        "/api/optimizer/prepare",
        json={
            "candidateTickers": candidates,
            "benchmark": "SPY",
            "startDate": "2024-01-02",
            "endDate": "2024-05-31",
            "trainingRatio": 0.70,
            "candidateSelection": {
                "mode": "strict_training_only",
                "rankingField": "sortino_ratio",
            },
        },
    )
    assert prepare_response.status_code == 200
    prepared = prepare_response.get_json()
    snapshot = optimizer._decode_snapshot(prepared["snapshot"])
    assert snapshot["candidateTickers"] == candidates
    assert snapshot["split"]["splitIndex"] == 70
    assert snapshot["candidateSelection"]["mode"] == "strict_training_only"

    verify_response = client.post(
        "/api/optimizer/verify",
        json={
            "snapshot": prepared["snapshot"],
            "settings": {
                "bandRatio": 0.20,
                "transactionCostBps": 0,
            },
            "combinations": [
                {
                    "combinationId": "one",
                    "mask": (1 << 10) - 1,
                    "tickers": candidates[:10],
                }
            ],
        },
    )
    assert verify_response.status_code == 200
    payload = verify_response.get_json()
    assert len(payload["results"]) == 1
    result = payload["results"][0]
    assert result["tickers"] == sorted(candidates[:10])
    assert result["training"]["metric_price_observations"] == 70
    assert result["validation"]["metric_price_observations"] == 30
    assert result["training"]["rebalanceCount"] >= 0
    assert payload["metadata"]["rebalance_engine_version"] == (
        optimizer.REBALANCE_ENGINE_VERSION
    )
