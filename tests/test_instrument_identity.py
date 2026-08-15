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


def _downloaded_multi_history() -> pd.DataFrame:
    dates = pd.to_datetime(
        [
            "2018-01-02",
            "2023-06-22",
            "2023-06-23",
            "2024-02-01",
            "2024-02-02",
        ]
    )
    values: dict[tuple[str, str], list[float | bool]] = {}
    for symbol, closes in {
        "NEW_A": [10.0, 20.0, 20.5, 22.0, 22.5],
        "NEW_B": [30.0, 31.0, 31.5, 40.0, 40.5],
        "LONG": [50.0, 60.0, 60.5, 65.0, 65.5],
    }.items():
        values[("Adj Close", symbol)] = closes
        values[("Close", symbol)] = closes
        values[("Dividends", symbol)] = [0.0] * len(dates)
        values[("Stock Splits", symbol)] = [0.0] * len(dates)
        values[("Capital Gains", symbol)] = [0.0] * len(dates)
        values[("Repaired?", symbol)] = [False] * len(dates)
    frame = pd.DataFrame(values, index=dates)
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    return frame


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


def test_batch_guard_respects_distinct_lifecycles_and_preserves_long_history(
    monkeypatch,
) -> None:
    market_data.clear_price_cache()
    monkeypatch.setattr(
        market_data,
        "bulk_download_prices",
        lambda *_args, **_kwargs: _downloaded_multi_history(),
    )
    monkeypatch.setattr(
        market_data,
        "resolve_instrument_identities",
        lambda _symbols: {
            "NEW_A": InstrumentIdentity(
                symbol="NEW_A",
                status="verified",
                first_trade_date=date(2023, 6, 22),
            ),
            "NEW_B": InstrumentIdentity(
                symbol="NEW_B",
                status="verified",
                first_trade_date=date(2024, 2, 1),
            ),
            "LONG": InstrumentIdentity(
                symbol="LONG",
                status="verified",
                first_trade_date=date(2000, 1, 1),
            ),
        },
    )

    resolved, unresolved = market_data.download_prices_finitely(
        ["NEW_A", "NEW_B", "LONG"],
        "2018-01-01",
        "2024-02-03",
        attempts=1,
        backoff_seconds=(0.0,),
    )

    assert unresolved == []
    assert resolved["NEW_A"].index[0] == pd.Timestamp("2023-06-22")
    assert resolved["NEW_B"].index[0] == pd.Timestamp("2024-02-01")
    assert resolved["LONG"].index[0] == pd.Timestamp("2018-01-02")

    audit_a = resolved["NEW_A"].attrs["instrument_identity_audit"]
    audit_b = resolved["NEW_B"].attrs["instrument_identity_audit"]
    audit_long = resolved["LONG"].attrs["instrument_identity_audit"]
    assert audit_a["removed_pre_inception_rows"] == 1
    assert audit_b["removed_pre_inception_rows"] == 3
    assert audit_long["removed_pre_inception_rows"] == 0
    assert audit_long["status"] == "verified"
    assert audit_long["clipping_applied"] is False
    assert len(resolved["LONG"]) == 5


def test_unverified_metadata_fails_closed_instead_of_using_ticker_only_history(
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

    assert resolved == {}
    assert unresolved == ["VFLO"]


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
