from __future__ import annotations

from datetime import date

import pandas as pd

from api import market_data
from api.instrument_identity import (
    InstrumentIdentity,
    apply_instrument_lifecycle_guard,
    parse_first_trade_date,
)


def _downloaded_history() -> pd.DataFrame:
    dates = pd.to_datetime(["2016-01-04", "2023-06-22", "2023-06-23"])
    columns = pd.MultiIndex.from_tuples(
        [
            ("Adj Close", "VFLO"),
            ("Close", "VFLO"),
            ("Dividends", "VFLO"),
            ("Stock Splits", "VFLO"),
            ("Capital Gains", "VFLO"),
            ("Repaired?", "VFLO"),
        ]
    )
    return pd.DataFrame(
        [
            [10.0, 10.0, 0.25, 0.0, 0.0, False],
            [24.8, 24.8, 0.0, 0.0, 0.0, False],
            [25.0, 25.0, 0.0, 0.0, 0.0, False],
        ],
        index=dates,
        columns=columns,
    )


def test_parse_first_trade_date_accepts_yahoo_epoch_and_iso() -> None:
    expected = date(2023, 6, 22)
    epoch_seconds = pd.Timestamp("2023-06-22T13:30:00Z").timestamp()
    assert parse_first_trade_date(epoch_seconds) == expected
    assert parse_first_trade_date(epoch_seconds * 1000) == expected
    assert parse_first_trade_date("2023-06-22") == expected
    assert parse_first_trade_date(None) is None
    assert parse_first_trade_date("not-a-date") is None


def test_guard_clips_price_and_all_time_indexed_components() -> None:
    adjusted = pd.Series(
        [10.0, 24.8, 25.0],
        index=pd.to_datetime(["2016-01-04", "2023-06-22", "2023-06-23"]),
        name="VFLO",
    )
    adjusted.attrs["raw_close"] = adjusted.rename("raw_close").copy()
    adjusted.attrs["dividends"] = pd.Series(
        [0.25, 0.0, 0.0], index=adjusted.index, name="dividends"
    )
    identity = InstrumentIdentity(
        symbol="VFLO", status="verified", first_trade_date=date(2023, 6, 22)
    )

    guarded = apply_instrument_lifecycle_guard(adjusted, identity)

    assert guarded.index[0] == pd.Timestamp("2023-06-22")
    assert guarded.attrs["raw_close"].index[0] == pd.Timestamp("2023-06-22")
    assert guarded.attrs["dividends"].index[0] == pd.Timestamp("2023-06-22")
    audit = guarded.attrs["instrument_identity_audit"]
    assert audit["status"] == "verified_clipped"
    assert audit["first_trade_date"] == "2023-06-22"
    assert audit["original_first_date"] == "2016-01-04"
    assert audit["effective_first_date"] == "2023-06-22"
    assert audit["removed_pre_inception_rows"] == 1
    assert audit["clipping_applied"] is True


def test_market_data_never_exposes_pre_inception_ticker_reuse(monkeypatch) -> None:
    market_data.clear_price_cache()
    monkeypatch.setattr(
        market_data,
        "bulk_download_prices",
        lambda *_args, **_kwargs: _downloaded_history(),
    )
    monkeypatch.setattr(
        market_data,
        "resolve_instrument_identities",
        lambda _symbols: {
            "VFLO": InstrumentIdentity(
                symbol="VFLO",
                status="verified",
                first_trade_date=date(2023, 6, 22),
            )
        },
    )

    resolved, unresolved = market_data.download_prices_finitely(
        ["VFLO"],
        "2016-01-01",
        "2023-06-24",
        attempts=1,
        backoff_seconds=(0.0,),
    )

    assert unresolved == []
    vflo = resolved["VFLO"]
    assert vflo.index.tolist() == [
        pd.Timestamp("2023-06-22"),
        pd.Timestamp("2023-06-23"),
    ]
    assert vflo.attrs["raw_close"].index[0] == pd.Timestamp("2023-06-22")
    assert vflo.attrs["dividends"].index[0] == pd.Timestamp("2023-06-22")
    corporate = vflo.attrs["corporate_action_audit"]
    assert corporate["dividend_events"] == 0
    assert corporate["instrument_identity"]["status"] == "verified_clipped"
    assert corporate["instrument_identity"]["removed_pre_inception_rows"] == 1

    frame, failures = market_data.download_data_reliably(
        ["VFLO"],
        "2016-01-01",
        "2023-06-24",
        attempts=1,
        backoff_seconds=(0.0,),
    )
    assert failures == {}
    assert frame["VFLO"].dropna().index[0] == pd.Timestamp("2023-06-22")
    assert (
        frame.attrs["instrument_identity_audits"]["VFLO"]["first_trade_date"]
        == "2023-06-22"
    )


def test_unverified_metadata_is_explicit_and_does_not_invent_a_boundary(
    monkeypatch,
) -> None:
    market_data.clear_price_cache()
    monkeypatch.setattr(
        market_data,
        "bulk_download_prices",
        lambda *_args, **_kwargs: _downloaded_history(),
    )
    monkeypatch.setattr(
        market_data,
        "resolve_instrument_identities",
        lambda _symbols: {
            "VFLO": InstrumentIdentity(
                symbol="VFLO",
                status="unverified_metadata",
                first_trade_date=None,
                detail="metadata unavailable",
            )
        },
    )

    resolved, unresolved = market_data.download_prices_finitely(
        ["VFLO"],
        "2016-01-01",
        "2023-06-24",
        attempts=1,
        backoff_seconds=(0.0,),
    )

    assert unresolved == []
    assert resolved["VFLO"].index[0] == pd.Timestamp("2016-01-04")
    audit = resolved["VFLO"].attrs["instrument_identity_audit"]
    assert audit["status"] == "unverified_metadata"
    assert audit["first_trade_date"] is None
    assert audit["clipping_applied"] is False


def test_entirely_pre_inception_window_returns_no_usable_current_instrument(
    monkeypatch,
) -> None:
    market_data.clear_price_cache()
    old_only = _downloaded_history().iloc[[0]].copy()
    monkeypatch.setattr(
        market_data,
        "bulk_download_prices",
        lambda *_args, **_kwargs: old_only,
    )
    monkeypatch.setattr(
        market_data,
        "resolve_instrument_identities",
        lambda _symbols: {
            "VFLO": InstrumentIdentity(
                symbol="VFLO",
                status="verified",
                first_trade_date=date(2023, 6, 22),
            )
        },
    )

    resolved, unresolved = market_data.download_prices_finitely(
        ["VFLO"],
        "2016-01-01",
        "2017-01-01",
        attempts=1,
        backoff_seconds=(0.0,),
    )

    assert resolved == {}
    assert unresolved == ["VFLO"]
