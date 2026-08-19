from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from api.metrics import series_fingerprint
from apps.api.app.research.dataset import (
    ResearchDataset,
    _coverage_diagnostics,
    _dataset_hash,
    _matrix_returns,
    _weekly_last_actual,
)
from apps.api.app.research.dataset_views import slice_research_dataset


def _parent_dataset() -> ResearchDataset:
    index = pd.date_range("2024-01-02", periods=90, freq="B")
    qqq = pd.Series(100.0 * np.cumprod(np.full(len(index), 1.001)), index=index)
    bil = pd.Series(100.0 * np.cumprod(np.full(len(index), 1.0001)), index=index)
    bil.iloc[:15] = np.nan
    levels = pd.DataFrame({"QQQ": qqq, "BIL": bil}, index=index)
    requested = ("QQQ", "BIL")
    resolved = requested
    masks = {
        "QQQ": np.ones(len(index), dtype=bool),
        "BIL": np.asarray([False] * 15 + [True] * (len(index) - 15), dtype=bool),
    }
    coverage = _coverage_diagnostics(requested, resolved, {}, index, masks)
    daily_returns = _matrix_returns(levels)
    weekly_levels = _weekly_last_actual(levels)
    metadata = {
        symbol: {
            "symbol": symbol,
            "first_twd_date": index[0].date().isoformat(),
            "last_twd_date": index[-1].date().isoformat(),
            "fingerprints": {
                "aligned_twd_level": series_fingerprint(levels[symbol].dropna())
            },
        }
        for symbol in requested
    }
    dataset = ResearchDataset(
        requested_symbols=requested,
        resolved_symbols=resolved,
        failures={},
        requested_start=index[0].date(),
        requested_end=index[-1].date(),
        reference_calendar=index,
        availability_masks=masks,
        daily_levels_twd=levels,
        daily_returns_twd=daily_returns,
        weekly_levels_twd=weekly_levels,
        weekly_returns_twd=_matrix_returns(weekly_levels),
        native_returns={
            symbol: daily_returns[symbol].dropna().copy() for symbol in requested
        },
        fx_returns={
            symbol: pd.Series(0.0, index=daily_returns.index, name="return")
            for symbol in requested
        },
        coverage=coverage,
        asset_metadata=metadata,
        dataset_hash="",
    )
    dataset.dataset_hash = _dataset_hash(dataset)
    dataset.export_payload()
    return dataset


def test_bounded_view_has_own_identity_and_no_rows_outside_window() -> None:
    parent = _parent_dataset()
    original_hash = parent.dataset_hash
    start = parent.reference_calendar[30].date()
    end = parent.reference_calendar[60].date()

    child = slice_research_dataset(parent, start=start, end=end)

    assert child.requested_symbols == parent.requested_symbols
    assert child.resolved_symbols == parent.resolved_symbols
    assert child.requested_start == start
    assert child.requested_end == end
    assert child.effective_start == start
    assert child.effective_end == end
    assert child.dataset_hash != parent.dataset_hash
    assert parent.dataset_hash == original_hash
    assert child.daily_levels_twd.index.min().date() >= start
    assert child.daily_levels_twd.index.max().date() <= end
    assert child.asset_metadata["QQQ"]["parent_dataset_hash"] == parent.dataset_hash
    assert child.export_payload()["datasetHash"] == child.dataset_hash


def test_view_turns_no_availability_symbol_into_explicit_failure() -> None:
    parent = _parent_dataset()
    start = parent.reference_calendar[0].date()
    end = parent.reference_calendar[10].date()

    child = slice_research_dataset(parent, start=start, end=end)

    assert child.resolved_symbols == ("QQQ",)
    assert tuple(child.failures) == ("BIL",)
    assert child.failures["BIL"].stage == "slice_window"
    assert child.failures["BIL"].retryable is False
    assert child.coverage["BIL"]["status"] == "unavailable"


def test_view_rejects_dates_outside_parent_authority() -> None:
    parent = _parent_dataset()
    with pytest.raises(ValueError, match="inside the parent requested window"):
        slice_research_dataset(
            parent,
            start=date(2023, 12, 31),
            end=parent.requested_end,
        )


def test_same_window_slice_is_deterministic() -> None:
    parent = _parent_dataset()
    start = parent.reference_calendar[20].date()
    end = parent.reference_calendar[50].date()

    first = slice_research_dataset(parent, start=start, end=end)
    second = slice_research_dataset(parent, start=start, end=end)

    assert first.dataset_hash == second.dataset_hash
    assert first.export_payload() == second.export_payload()
