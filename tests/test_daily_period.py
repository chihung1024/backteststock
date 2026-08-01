import pandas as pd
import pytest

from api import index


def test_daily_period_is_inclusive_at_the_public_contract():
    start, end_exclusive = index.parse_period(
        {"startDate": "2025-08-01", "endDate": "2026-07-31"}
    )
    assert start == pd.Timestamp("2025-08-01")
    assert end_exclusive == pd.Timestamp("2026-08-01")


def test_daily_period_rejects_reversed_or_partial_dates():
    with pytest.raises(index.ValidationError):
        index.parse_period(
            {"startDate": "2026-07-31", "endDate": "2025-08-01"}
        )
    with pytest.raises(index.ValidationError):
        index.parse_period({"startDate": "2025-08-01"})


def test_legacy_month_period_remains_supported():
    start, end_exclusive = index.parse_period(
        {
            "startYear": 2025,
            "startMonth": 8,
            "endYear": 2026,
            "endMonth": 7,
        }
    )
    assert start == pd.Timestamp("2025-08-01")
    assert end_exclusive == pd.Timestamp("2026-08-01")
