from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from apps.api.app.data.history_service import (
    HistoryFailure,
    PartialTWDHistories,
    TWDAssetHistory,
)
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.scan_service import TWDScanService


def _history(
    symbol: str,
    currency: str,
    native: list[float],
    fx: list[float],
    twd: list[float],
) -> TWDAssetHistory:
    index = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    valuation = TWDValuation(
        source_currency=currency,
        native_adjusted_close=pd.Series(native, index=index, dtype=float),
        fx_to_twd=pd.Series(fx, index=index, dtype=float),
        adjusted_close_twd=pd.Series(twd, index=index, dtype=float),
        daily_returns=pd.Series(twd, index=index, dtype=float)
        .pct_change(fill_method=None)
        .fillna(0.0),
    )
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency=currency,
        valuation=valuation,
        corporate_action_audit={"status": "verified_standard_actions"},
        fx_audit={"method": "direct", "tickers": ["USDTWD=X"]},
    )


class FakeHistoryService:
    def __init__(self, histories, failures=None) -> None:
        self.histories = histories
        self.failures = failures or {}

    def histories_partial(self, symbols, _start, _end) -> PartialTWDHistories:
        requested = tuple(symbols)
        return PartialTWDHistories(
            requested=requested,
            histories={symbol: self.histories[symbol] for symbol in requested if symbol in self.histories},
            failures={symbol: self.failures[symbol] for symbol in requested if symbol in self.failures},
        )


def test_scan_uses_twd_levels_not_native_currency_returns() -> None:
    asset = _history(
        "ASSET", "USD", [100.0, 100.0, 100.0], [30.0, 31.0, 32.0], [3000.0, 3100.0, 3200.0]
    )
    benchmark = _history(
        "SPY", "USD", [200.0, 200.0, 200.0], [30.0, 31.0, 32.0], [6000.0, 6200.0, 6400.0]
    )
    service = TWDScanService(
        history_service=FakeHistoryService({"ASSET": asset, "SPY": benchmark})
    )

    batch = service.run(
        ["asset"],
        start=date(2025, 1, 2),
        end=date(2025, 1, 6),
        benchmark="SPY",
    )

    row = batch.results[0]
    assert row["status"] == "ok"
    assert row["valuation_currency"] == "TWD"
    assert row["total_return"] == pytest.approx(3200.0 / 3000.0 - 1.0)
    assert row["beta"] == pytest.approx(1.0)
    assert row["data_coverage"] == pytest.approx(1.0)
    assert row["fx_audit"]["method"] == "direct"
    assert row["native_price_fingerprint"]
    assert row["fx_price_fingerprint"]
    assert row["valuation_metadata"]["native_price_fingerprint"] == row[
        "native_price_fingerprint"
    ]
    assert "valuation=TWD" in row["reproducibility"]


def test_scan_preserves_asset_result_when_benchmark_or_peer_fails() -> None:
    good = _history(
        "GOOD", "TWD", [100.0, 101.0, 102.0], [1.0, 1.0, 1.0], [100.0, 101.0, 102.0]
    )
    service = TWDScanService(
        history_service=FakeHistoryService(
            {"GOOD": good},
            {
                "BAD": HistoryFailure("BAD", "download", "Yahoo unavailable", True),
                "SPY": HistoryFailure("SPY", "fx", "USD/TWD unavailable", True),
            },
        )
    )

    batch = service.run(
        ["GOOD", "BAD"],
        start=date(2025, 1, 2),
        end=date(2025, 1, 6),
        benchmark="SPY",
    )

    good_row, bad_row = batch.results
    assert batch.benchmark_available is False
    assert good_row["status"] == "ok"
    assert good_row["beta"] is None
    assert "Beta／Alpha 暫不計算" in good_row["note"]
    assert bad_row == {
        "ticker": "BAD",
        "status": "failed",
        "retryable": True,
        "error_code": "twd_download_unavailable",
        "error": "Yahoo unavailable",
        "benchmark_available": False,
        "valuation_currency": "TWD",
        "twd_valuation_contract_version": "twd-adjusted-close-union-calendar-2026-08-03.1",
        "calendar_policy": "union_twd_valuation_calendar_forward_fill_after_observation_complete_case-v1",
        "metric_definition_version": good_row["metric_definition_version"],
    }
