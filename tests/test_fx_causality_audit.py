from __future__ import annotations

import pandas as pd
import pytest

from apps.api.app.data.fx_price_quality import reconcile_ohlc_levels
from apps.api.app.data.fx_provider import FXLevels, QuoteConvention
from apps.api.app.data.history_service import _fx_audit


def test_interpolated_fx_repair_is_marked_future_assisted() -> None:
    index = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
    frame = pd.DataFrame(
        {
            "Open": [100.0, 110.0, 121.0],
            "High": [101.0, 115.0, 122.0],
            "Low": [99.0, 105.0, 120.0],
            "Close": [100.0, 1000.0, 121.0],
        },
        index=index,
    )

    reconciliation = reconcile_ohlc_levels(frame)

    assert reconciliation.correction_count == 1
    assert reconciliation.future_assisted_count == 1
    assert bool(reconciliation.corrected.loc[pd.Timestamp("2024-01-02")]) is True
    assert bool(reconciliation.future_assisted.loc[pd.Timestamp("2024-01-02")]) is True
    assert reconciliation.levels.loc[pd.Timestamp("2024-01-02")] == pytest.approx(110.0)


def test_open_supported_terminal_repair_remains_causal() -> None:
    index = pd.to_datetime(["2024-01-01", "2024-01-02"])
    frame = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.0, 1000.0],
        },
        index=index,
    )

    reconciliation = reconcile_ohlc_levels(frame)

    assert reconciliation.correction_count == 1
    assert reconciliation.future_assisted_count == 0
    assert bool(reconciliation.future_assisted.iloc[-1]) is False
    assert reconciliation.levels.iloc[-1] == pytest.approx(101.0)


def test_fx_audit_exposes_non_causal_repair_count() -> None:
    levels = FXLevels(
        source_currency="USD",
        target_currency="TWD",
        levels=pd.Series(
            [31.0, 31.1],
            index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
            dtype=float,
        ),
        method="direct",
        tickers=("TWD=X",),
        correction_count=2,
        unresolved_count=0,
        material_transition_count=0,
        future_assisted_correction_count=1,
    )
    audit = _fx_audit(
        "USD",
        levels,
        QuoteConvention(
            raw_currency="USD",
            currency="USD",
            native_price_scale=1.0,
        ),
    )

    assert audit["correction_count"] == 2
    assert audit["future_assisted_correction_count"] == 1
    assert audit["non_causal_repair_present"] is True
