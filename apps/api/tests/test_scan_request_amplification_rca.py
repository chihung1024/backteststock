from __future__ import annotations

from datetime import date

import pandas as pd

from api import market_data
from apps.api.app.data.fx_provider import FXDownloadError, YahooFXProvider
from apps.api.app.data.history_service import PartialTWDHistories
from apps.api.app.scan_service import TWDScanService


def _symbols(start: int, count: int) -> list[str]:
    return [f"T{index:04d}" for index in range(start, start + count)]


class RecordingHistoryService:
    def __init__(self) -> None:
        self.requests: list[tuple[str, ...]] = []

    def histories_partial(self, symbols, _start, _end) -> PartialTWDHistories:
        requested = tuple(symbols)
        self.requests.append(requested)
        return PartialTWDHistories(requested=requested, histories={}, failures={})


def test_frontend_100_candidates_expand_to_101_history_symbols_with_benchmark() -> None:
    history_service = RecordingHistoryService()
    service = TWDScanService(history_service=history_service)
    candidates = _symbols(1, 100)

    batch = service.run(
        candidates,
        start=date(2025, 1, 2),
        end=date(2025, 1, 6),
        benchmark="SPY",
    )

    assert len(history_service.requests) == 1
    requested = history_service.requests[0]
    assert requested[0] == "SPY"
    assert requested[1:] == tuple(candidates)
    assert len(requested) == 101
    assert len(batch.results) == 100


def _install_successful_market_data_fakes(monkeypatch, batch_sizes: list[int]) -> None:
    def fake_bulk(tickers, *_args, **_kwargs):
        batch = list(tickers)
        batch_sizes.append(len(batch))
        return {"batch": batch}

    def fake_extract(downloaded, _batch):
        return {
            ticker: pd.Series(
                [100.0, 101.0],
                index=pd.to_datetime(["2025-01-02", "2025-01-03"]),
                dtype=float,
            )
            for ticker in downloaded["batch"]
        }

    monkeypatch.setattr(market_data, "bulk_download_prices", fake_bulk)
    monkeypatch.setattr(market_data, "extract_adjusted_close_prices", fake_extract)
    monkeypatch.setattr(market_data, "_attach_return_component_attrs", lambda *_args: None)


def test_market_data_101_symbols_split_into_100_plus_1_bulk_download(monkeypatch) -> None:
    market_data.clear_price_cache()
    batch_sizes: list[int] = []
    _install_successful_market_data_fakes(monkeypatch, batch_sizes)

    resolved, unresolved = market_data.download_prices_finitely(
        ["SPY", *_symbols(1, 100)],
        "2025-01-01",
        "2025-12-31",
    )

    assert unresolved == []
    assert len(resolved) == 101
    assert batch_sizes == [100, 1]


def test_five_frontend_batches_need_six_warm_or_ten_cold_bulk_downloads(monkeypatch) -> None:
    batch_sizes: list[int] = []
    _install_successful_market_data_fakes(monkeypatch, batch_sizes)
    frontend_batches = [_symbols(offset + 1, 100) for offset in range(0, 500, 100)]

    market_data.clear_price_cache()
    for candidates in frontend_batches:
        resolved, unresolved = market_data.download_prices_finitely(
            ["SPY", *candidates],
            "2025-01-01",
            "2025-12-31",
        )
        assert unresolved == []
        assert len(resolved) == 101
    warm_batch_sizes = list(batch_sizes)

    batch_sizes.clear()
    for candidates in frontend_batches:
        market_data.clear_price_cache()
        resolved, unresolved = market_data.download_prices_finitely(
            ["SPY", *candidates],
            "2025-01-01",
            "2025-12-31",
        )
        assert unresolved == []
        assert len(resolved) == 101
    cold_batch_sizes = list(batch_sizes)

    assert warm_batch_sizes == [100, 1, 100, 100, 100, 100]
    assert cold_batch_sizes == [100, 1] * 5


def test_unresolved_101_symbols_consume_three_rounds_of_100_plus_1(monkeypatch) -> None:
    market_data.clear_price_cache()
    batch_sizes: list[int] = []

    def fake_bulk(tickers, *_args, **_kwargs):
        batch = list(tickers)
        batch_sizes.append(len(batch))
        return {"batch": batch}

    monkeypatch.setattr(market_data, "bulk_download_prices", fake_bulk)
    monkeypatch.setattr(market_data, "extract_adjusted_close_prices", lambda *_args: {})
    monkeypatch.setattr(market_data, "_attach_return_component_attrs", lambda *_args: None)
    monkeypatch.setattr(market_data.time, "sleep", lambda _seconds: None)

    resolved, unresolved = market_data.download_prices_finitely(
        ["SPY", *_symbols(1, 100)],
        "2025-01-01",
        "2025-12-31",
    )

    assert resolved == {}
    assert len(unresolved) == 101
    assert batch_sizes == [100, 1] * 3


def test_500_unique_candidates_still_require_501_quote_metadata_calls_when_warm(monkeypatch) -> None:
    calls: list[str] = []

    class FakeFastInfo:
        currency = "USD"

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            calls.append(symbol)
            self.fast_info = FakeFastInfo()

    monkeypatch.setattr("apps.api.app.data.fx_provider.yf.Ticker", FakeTicker)
    provider = YahooFXProvider()
    frontend_batches = [_symbols(offset + 1, 100) for offset in range(0, 500, 100)]

    for candidates in frontend_batches:
        for symbol in ["SPY", *candidates]:
            assert provider.quote_convention(symbol).currency == "USD"

    assert len(calls) == 501
    assert calls.count("SPY") == 1
    assert len(set(calls)) == 501


def test_cold_provider_per_frontend_batch_repeats_benchmark_metadata(monkeypatch) -> None:
    calls: list[str] = []

    class FakeFastInfo:
        currency = "USD"

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            calls.append(symbol)
            self.fast_info = FakeFastInfo()

    monkeypatch.setattr("apps.api.app.data.fx_provider.yf.Ticker", FakeTicker)
    frontend_batches = [_symbols(offset + 1, 100) for offset in range(0, 500, 100)]

    for candidates in frontend_batches:
        provider = YahooFXProvider()
        for symbol in ["SPY", *candidates]:
            assert provider.quote_convention(symbol).currency == "USD"

    assert len(calls) == 505
    assert calls.count("SPY") == 5
    assert len(set(calls)) == 501


def test_quote_metadata_failures_retry_twice_per_symbol_and_are_not_cached(monkeypatch) -> None:
    calls: list[str] = []

    class FailingTicker:
        def __init__(self, symbol: str) -> None:
            calls.append(symbol)
            raise RuntimeError("synthetic Yahoo metadata throttle")

    monkeypatch.setattr("apps.api.app.data.fx_provider.yf.Ticker", FailingTicker)
    provider = YahooFXProvider()
    requested = ["SPY", *_symbols(1, 100)]

    for symbol in requested:
        try:
            provider.quote_convention(symbol)
        except FXDownloadError:
            pass
        else:  # pragma: no cover - diagnostic guard
            raise AssertionError("synthetic metadata failure should fail closed")

    assert len(calls) == 202
    assert all(calls.count(symbol) == 2 for symbol in requested)

    try:
        provider.quote_convention("SPY")
    except FXDownloadError:
        pass
    else:  # pragma: no cover - diagnostic guard
        raise AssertionError("synthetic metadata failure should remain unavailable")
    assert calls.count("SPY") == 4


def test_cold_usd_fx_resolution_probes_three_yahoo_candidates_then_caches(monkeypatch) -> None:
    calls: list[str] = []
    index = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    frame = pd.DataFrame(
        {
            "Open": [30.0, 30.1, 30.2],
            "High": [30.1, 30.2, 30.3],
            "Low": [29.9, 30.0, 30.1],
            "Close": [30.0, 30.1, 30.2],
        },
        index=index,
    )

    def fake_download(ticker: str, **_kwargs):
        calls.append(ticker)
        return frame.copy()

    monkeypatch.setattr("apps.api.app.data.fx_provider.yf.download", fake_download)
    provider = YahooFXProvider()

    first = provider.fx_to_twd("USD", date(2025, 1, 2), date(2025, 1, 6))
    second = provider.fx_to_twd("USD", date(2025, 1, 2), date(2025, 1, 6))

    assert first.levels.equals(second.levels)
    assert calls == ["TWD=X", "USDTWD=X", "TWDUSD=X"]
