from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from apps.api.app.data.fx_provider import (
    FXDownloadError,
    YahooFXProvider,
    normalize_quote_convention,
)


def _frame(
    close: list[float],
    *,
    low: list[float] | None = None,
    high: list[float] | None = None,
    open_: list[float] | None = None,
) -> pd.DataFrame:
    index = pd.DatetimeIndex(["2025-01-02", "2025-01-03", "2025-01-06"])
    return pd.DataFrame(
        {
            "Open": close if open_ is None else open_,
            "High": close if high is None else high,
            "Low": close if low is None else low,
            "Close": close,
        },
        index=index,
    )


def test_fx_provider_repairs_an_impossible_direct_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corrupt = _frame(
        [29.254, 1.8015, 30.11],
        low=[29.387, 29.387, 29.40],
        high=[30.22, 30.08, 30.13],
        open_=[30.22, 30.07, 30.09],
    )
    monkeypatch.setattr(
        "apps.api.app.data.fx_provider.yf.download",
        lambda *_args, **_kwargs: corrupt.copy(),
    )

    result = YahooFXProvider().fx_to_twd("USD", date(2025, 1, 2), date(2025, 1, 6))

    repaired = result.levels.loc[pd.Timestamp("2025-01-03")]
    assert 29.387 <= repaired <= 30.08
    assert result.levels.pct_change(fill_method=None).abs().max() < 0.10


def test_fx_provider_prefers_the_cleanest_direct_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corrupt = _frame(
        [29.254, 1.8015, 30.11],
        low=[29.387, 29.387, 29.40],
        high=[30.22, 30.08, 30.13],
        open_=[30.22, 30.07, 30.09],
    )
    clean = _frame(
        [30.0, 30.1, 30.2],
        low=[29.9, 30.0, 30.1],
        high=[30.1, 30.2, 30.3],
    )

    def fake_download(ticker: str, **_kwargs: object) -> pd.DataFrame:
        return corrupt.copy() if ticker == "TWD=X" else clean.copy()

    monkeypatch.setattr("apps.api.app.data.fx_provider.yf.download", fake_download)

    result = YahooFXProvider().fx_to_twd("USD", date(2025, 1, 2), date(2025, 1, 6))

    assert result.tickers == ("USDTWD=X",)
    assert result.levels.equals(clean["Close"].astype(float))


def test_fx_provider_normalizes_inverse_ohlc_before_inversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inverse = _frame(
        [1 / 30.0, 1 / 30.1, 1 / 30.2],
        low=[1 / 30.1, 1 / 30.2, 1 / 30.3],
        high=[1 / 29.9, 1 / 30.0, 1 / 30.1],
    )

    def fake_download(ticker: str, **_kwargs: object) -> pd.DataFrame:
        return inverse.copy() if ticker == "TWDUSD=X" else pd.DataFrame()

    monkeypatch.setattr("apps.api.app.data.fx_provider.yf.download", fake_download)

    result = YahooFXProvider().fx_to_twd("USD", date(2025, 1, 2), date(2025, 1, 6))

    assert result.method == "inverse"
    assert result.levels.tolist() == pytest.approx([30.0, 30.1, 30.2])


def test_fx_provider_uses_usd_triangulation_when_direct_cross_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eur_usd = _frame([1.10, 1.11, 1.12], low=[1.09, 1.10, 1.11], high=[1.11, 1.12, 1.13])
    usd_twd = _frame([30.0, 30.1, 30.2], low=[29.9, 30.0, 30.1], high=[30.1, 30.2, 30.3])

    def fake_download(ticker: str, **_kwargs: object) -> pd.DataFrame:
        if ticker == "EURUSD=X":
            return eur_usd.copy()
        if ticker == "TWD=X":
            return usd_twd.copy()
        return pd.DataFrame()

    monkeypatch.setattr("apps.api.app.data.fx_provider.yf.download", fake_download)

    result = YahooFXProvider().fx_to_twd("EUR", date(2025, 1, 2), date(2025, 1, 6))

    assert result.method == "usd_triangulation"
    assert result.tickers == ("EURUSD=X", "TWD=X")
    assert result.levels.tolist() == pytest.approx([33.0, 33.411, 33.824])


def test_quote_currency_is_normalized_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class FakeFastInfo:
        currency = "GBp"

    class FakeTicker:
        fast_info = FakeFastInfo()

        def __init__(self, symbol: str) -> None:
            calls.append(symbol)

    monkeypatch.setattr("apps.api.app.data.fx_provider.yf.Ticker", FakeTicker)
    provider = YahooFXProvider()

    convention = provider.quote_convention("vod.l")
    assert convention.raw_currency == "GBp"
    assert convention.currency == "GBP"
    assert convention.native_price_scale == pytest.approx(0.01)
    assert provider.quote_currency("vod.l") == "GBP"
    assert provider.quote_currency("VOD.L") == "GBP"
    assert calls == ["VOD.L"]


@pytest.mark.parametrize(
    ("raw", "currency", "scale"),
    [
        ("GBP", "GBP", 1.0),
        ("GBp", "GBP", 0.01),
        ("GBX", "GBP", 0.01),
        ("ZAc", "ZAR", 0.01),
        ("ZAC", "ZAR", 0.01),
        ("ILA", "ILS", 0.01),
    ],
)
def test_quote_convention_distinguishes_minor_units(raw, currency, scale) -> None:
    convention = normalize_quote_convention(raw)

    assert convention.raw_currency == raw
    assert convention.currency == currency
    assert convention.native_price_scale == pytest.approx(scale)


def test_fx_provider_fails_closed_after_finite_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "apps.api.app.data.fx_provider.yf.download",
        lambda *_args, **_kwargs: pd.DataFrame(),
    )

    with pytest.raises(FXDownloadError, match="unable to obtain a verified USD/TWD"):
        YahooFXProvider().fx_to_twd("USD", date(2025, 1, 2), date(2025, 1, 6))


def test_fx_provider_uses_prior_opening_rate_but_excludes_download_lookahead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.to_datetime(
        ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]
    )
    frame = pd.DataFrame(
        {
            "Open": [29.9, 30.0, 30.1, 30.2, 30.3],
            "High": [30.0, 30.1, 30.2, 30.3, 30.4],
            "Low": [29.8, 29.9, 30.0, 30.1, 30.2],
            "Close": [29.9, 30.0, 30.1, 30.2, 30.3],
        },
        index=index,
    )
    monkeypatch.setattr(
        "apps.api.app.data.fx_provider.yf.download",
        lambda *_args, **_kwargs: frame.copy(),
    )

    result = YahooFXProvider().fx_to_twd("USD", date(2025, 1, 2), date(2025, 1, 6))

    assert result.levels.index.strftime("%Y-%m-%d").tolist() == [
        "2025-01-01",
        "2025-01-02",
        "2025-01-03",
        "2025-01-06",
    ]
