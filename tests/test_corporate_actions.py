import pandas as pd
import pytest

from api.corporate_actions import (
    RETURN_BASIS,
    build_corporate_action_audit,
    extract_adjusted_close_prices,
    flattened_audit_fields,
)
from api.metrics import calculate_metrics


def _download_frame(
    *,
    raw_close,
    adjusted_close,
    dividends=None,
    splits=None,
    capital_gains=None,
    repaired=None,
    ticker="AAA",
):
    dates = pd.bdate_range("2024-01-02", periods=len(raw_close))
    values = {
        ("Close", ticker): raw_close,
        ("Adj Close", ticker): adjusted_close,
        ("Dividends", ticker): dividends or [0.0] * len(dates),
        ("Stock Splits", ticker): splits or [0.0] * len(dates),
        ("Capital Gains", ticker): capital_gains or [0.0] * len(dates),
        ("Repaired?", ticker): repaired or [False] * len(dates),
    }
    return pd.DataFrame(values, index=dates)


def test_explicit_adj_close_is_used_and_dividend_total_return_is_preserved():
    downloaded = _download_frame(
        raw_close=[100.0, 98.0, 100.0, 101.0],
        adjusted_close=[98.0, 98.0, 100.0, 101.0],
        dividends=[0.0, 2.0, 0.0, 0.0],
    )
    prices = extract_adjusted_close_prices(downloaded, ["AAA"])["AAA"]
    audit = prices.attrs["corporate_action_audit"]
    metrics = calculate_metrics(prices)

    assert prices.iloc[0] == 98.0
    assert prices.iloc[-1] == 101.0
    assert metrics["total_return"] == pytest.approx(101.0 / 98.0 - 1.0)
    assert metrics["total_return"] != pytest.approx(101.0 / 100.0 - 1.0)
    assert audit["return_basis"] == RETURN_BASIS
    assert audit["dividend_events"] == 1
    assert audit["distribution_adjustment_mismatches"] == 0
    assert audit["unexplained_adjustment_factor_changes"] == 0
    assert audit["status"] == "verified_standard_actions"


def test_standard_split_and_capital_gain_events_are_recorded():
    downloaded = _download_frame(
        raw_close=[50.0, 51.0, 52.0, 53.0],
        adjusted_close=[49.0, 49.98, 51.49, 53.0],
        splits=[0.0, 2.0, 0.0, 0.0],
        capital_gains=[0.0, 0.0, 0.0, 1.0],
        repaired=[False, True, False, True],
    )
    prices = extract_adjusted_close_prices(downloaded, ["AAA"])["AAA"]
    audit = prices.attrs["corporate_action_audit"]

    assert audit["stock_split_events"] == 1
    assert audit["capital_gain_events"] == 1
    assert audit["repaired_rows"] == 2


def test_unexplained_adjustment_factor_change_requires_review():
    dates = pd.bdate_range("2024-01-02", periods=4)
    audit = build_corporate_action_audit(
        ticker="AAA",
        raw_close=pd.Series([100.0, 100.0, 100.0, 100.0], index=dates),
        adjusted_close=pd.Series([90.0, 100.0, 100.0, 100.0], index=dates),
    )

    assert audit["status"] == "review_required"
    assert audit["unexplained_adjustment_factor_changes"] == 1
    assert audit["warning_dates"] == [dates[1].strftime("%Y-%m-%d")]


def test_split_like_unreported_adjusted_return_is_flagged_not_auto_rewritten():
    dates = pd.bdate_range("2024-01-02", periods=4)
    adjusted = pd.Series([100.0, 50.0, 51.0, 52.0], index=dates)
    audit = build_corporate_action_audit(
        ticker="AAA",
        raw_close=adjusted.copy(),
        adjusted_close=adjusted,
    )

    assert audit["status"] == "review_required"
    assert audit["split_like_unreported_changes"] == 1
    assert adjusted.iloc[1] == 50.0


def test_raw_close_is_never_substituted_when_adj_close_is_missing():
    dates = pd.bdate_range("2024-01-02", periods=3)
    downloaded = pd.DataFrame(
        {
            ("Close", "AAA"): [100.0, 101.0, 102.0],
            ("Dividends", "AAA"): [0.0, 0.0, 0.0],
            ("Stock Splits", "AAA"): [0.0, 0.0, 0.0],
        },
        index=dates,
    )

    assert extract_adjusted_close_prices(downloaded, ["AAA"]) == {}


def test_multi_symbol_download_extracts_each_explicit_adjusted_series():
    dates = pd.bdate_range("2024-01-02", periods=3)
    downloaded = pd.DataFrame(
        {
            ("Close", "AAA"): [100.0, 101.0, 102.0],
            ("Close", "BBB"): [50.0, 51.0, 52.0],
            ("Adj Close", "AAA"): [90.0, 91.0, 92.0],
            ("Adj Close", "BBB"): [45.0, 46.0, 47.0],
            ("Dividends", "AAA"): [0.0, 0.0, 0.0],
            ("Dividends", "BBB"): [0.0, 0.0, 0.0],
            ("Stock Splits", "AAA"): [0.0, 0.0, 0.0],
            ("Stock Splits", "BBB"): [0.0, 0.0, 0.0],
        },
        index=dates,
    )

    result = extract_adjusted_close_prices(downloaded, ["AAA", "BBB"])
    assert list(result) == ["AAA", "BBB"]
    assert result["AAA"].tolist() == [90.0, 91.0, 92.0]
    assert result["BBB"].tolist() == [45.0, 46.0, 47.0]


def test_flattened_audit_fields_are_csv_safe():
    dates = pd.bdate_range("2024-01-02", periods=3)
    audit = build_corporate_action_audit(
        ticker="AAA",
        raw_close=pd.Series([100.0, 100.0, 100.0], index=dates),
        adjusted_close=pd.Series([90.0, 100.0, 100.0], index=dates),
    )
    flat = flattened_audit_fields(audit)

    assert flat["corporate_action_status"] == "review_required"
    assert isinstance(flat["corporate_action_warning_dates"], str)
    assert flat["unexplained_adjustment_changes"] == 1
