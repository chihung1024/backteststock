from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from api import exhaustive_optimizer
from api.metrics import series_fingerprint
from apps.api.app.data.history_service import (
    HistoryFailure,
    PartialTWDHistories,
    TWDAssetHistory,
)
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.research.dataset import (
    RESEARCH_DATASET_CONTRACT_VERSION,
    RESEARCH_WEEKLY_POLICY,
    ResearchDatasetService,
    build_research_dataset,
)


def _history(
    symbol: str,
    dates: pd.DatetimeIndex,
    *,
    currency: str = "USD",
    native_start: float = 100.0,
    native_step: float = 1.0,
    fx_start: float = 30.0,
    fx_step: float = 0.1,
) -> TWDAssetHistory:
    native = pd.Series(
        native_start + native_step * np.arange(len(dates), dtype=float),
        index=dates,
        dtype=float,
    )
    if currency == "TWD":
        fx = pd.Series(1.0, index=dates, dtype=float)
    else:
        fx = pd.Series(
            fx_start + fx_step * np.arange(len(dates), dtype=float),
            index=dates,
            dtype=float,
        )
    twd = native * fx
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency=currency,
        valuation=TWDValuation(
            source_currency=currency,
            native_adjusted_close=native.rename("native_adjusted_close"),
            fx_to_twd=fx.rename("fx_to_twd"),
            adjusted_close_twd=twd.rename("adjusted_close_twd"),
            daily_returns=twd.pct_change(fill_method=None)
            .fillna(0.0)
            .rename("daily_return"),
        ),
        corporate_action_audit={
            "status": "verified_standard_actions",
            "warning_dates": [],
        },
        fx_audit={
            "method": "identity" if currency == "TWD" else "direct",
            "tickers": [] if currency == "TWD" else [f"{currency}TWD=X"],
        },
        raw_quote_currency=currency,
        native_price_scale=1.0,
    )


def _partial(
    requested: tuple[str, ...],
    histories: dict[str, TWDAssetHistory],
    failures: dict[str, HistoryFailure] | None = None,
) -> PartialTWDHistories:
    return PartialTWDHistories(
        requested=requested,
        histories=histories,
        failures=failures or {},
    )


def test_research_dataset_preserves_membership_coverage_and_actual_week_dates():
    aaa_dates = pd.bdate_range("2024-01-02", periods=6)  # through Jan 9
    bbb_dates = pd.bdate_range("2024-01-03", periods=6)  # through Jan 10
    histories = {
        "AAA": _history("AAA", aaa_dates),
        "BBB": _history("BBB", bbb_dates, native_start=150.0),
    }
    partial = _partial(
        ("AAA", "BBB", "FAIL"),
        histories,
        {
            "FAIL": HistoryFailure(
                symbol="FAIL",
                stage="download",
                detail="synthetic missing history",
                retryable=True,
            )
        },
    )

    dataset = build_research_dataset(
        partial,
        start=date(2024, 1, 2),
        end=date(2024, 1, 10),
    )

    assert dataset.contract_version == RESEARCH_DATASET_CONTRACT_VERSION
    assert dataset.requested_symbols == ("AAA", "BBB", "FAIL")
    assert dataset.resolved_symbols == ("AAA", "BBB")
    assert not dataset.is_complete
    assert dataset.failures["FAIL"].stage == "download"
    assert dataset.requested_start == date(2024, 1, 2)
    assert dataset.requested_end == date(2024, 1, 10)
    assert dataset.effective_start == date(2024, 1, 3)
    assert dataset.effective_end == date(2024, 1, 10)

    # The aligned matrix may carry AAA forward on Jan 10, but the reference
    # availability audit still exposes that AAA's real history ended earlier.
    assert dataset.coverage["AAA"]["last_available_position"] < len(
        dataset.reference_calendar
    ) - 1
    assert dataset.coverage["BBB"]["first_available_position"] > 0
    assert dataset.coverage["FAIL"]["status"] == "unavailable"
    assert dataset.coverage["_global_complete_case"]["requested_symbols"] == 3
    assert dataset.coverage["_global_complete_case"]["resolved_symbols"] == 2

    assert not dataset.daily_levels_twd.isna().any().any()
    assert list(dataset.daily_returns_twd.index) == list(dataset.daily_levels_twd.index[1:])

    # Jan 10 is a Wednesday. The second weekly observation must stay Jan 10,
    # not be relabelled to the future Friday Jan 12.
    assert list(dataset.weekly_levels_twd.index.strftime("%Y-%m-%d")) == [
        "2024-01-05",
        "2024-01-10",
    ]
    assert RESEARCH_WEEKLY_POLICY == "w-fri-period-last-actual-twd-observation-v1"

    payload = dataset.export_payload()
    assert payload["datasetHash"] == dataset.dataset_hash
    assert payload["requestedSymbols"] == ["AAA", "BBB", "FAIL"]
    assert payload["failures"]["FAIL"]["detail"] == "synthetic missing history"
    json.dumps(payload, allow_nan=False)


def test_research_dataset_hash_is_deterministic_and_data_sensitive():
    dates = pd.bdate_range("2024-01-02", periods=10)
    first_histories = {
        "AAA": _history("AAA", dates),
        "BBB": _history("BBB", dates, native_start=200.0),
    }
    first = build_research_dataset(
        _partial(("AAA", "BBB"), first_histories),
        start=date(2024, 1, 2),
        end=date(2024, 1, 15),
    )
    second = build_research_dataset(
        _partial(("AAA", "BBB"), first_histories),
        start=date(2024, 1, 2),
        end=date(2024, 1, 15),
    )
    assert first.dataset_hash == second.dataset_hash

    changed_histories = dict(first_histories)
    changed_histories["AAA"] = _history("AAA", dates, native_step=1.1)
    third = build_research_dataset(
        _partial(("AAA", "BBB"), changed_histories),
        start=date(2024, 1, 2),
        end=date(2024, 1, 15),
    )
    assert third.dataset_hash != first.dataset_hash


def test_research_dataset_export_rejects_mutated_content_with_stale_hash():
    dates = pd.bdate_range("2024-01-02", periods=5)
    dataset = build_research_dataset(
        _partial(("AAA",), {"AAA": _history("AAA", dates)}),
        start=date(2024, 1, 2),
        end=date(2024, 1, 8),
    )
    original_hash = dataset.dataset_hash

    dataset.daily_levels_twd.iloc[-1, 0] *= 1.01

    assert dataset.dataset_hash == original_hash
    with pytest.raises(ValueError, match="content changed after hash creation"):
        dataset.export_payload()


def test_research_dataset_rejects_unaccounted_requested_symbol():
    dates = pd.bdate_range("2024-01-02", periods=5)
    partial = PartialTWDHistories(
        requested=("AAA", "MISSING"),
        histories={"AAA": _history("AAA", dates)},
        failures={},
    )

    with pytest.raises(ValueError, match="explicit success/failure"):
        build_research_dataset(
            partial,
            start=date(2024, 1, 2),
            end=date(2024, 1, 8),
        )


def test_research_dataset_rejects_conflicting_success_and_failure_outcomes():
    dates = pd.bdate_range("2024-01-02", periods=5)
    partial = PartialTWDHistories(
        requested=("AAA",),
        histories={"AAA": _history("AAA", dates)},
        failures={
            "AAA": HistoryFailure(
                symbol="AAA",
                stage="download",
                detail="synthetic conflicting outcome",
                retryable=True,
            )
        },
    )

    with pytest.raises(ValueError, match="both success and failure outcomes"):
        build_research_dataset(
            partial,
            start=date(2024, 1, 2),
            end=date(2024, 1, 8),
        )


def test_research_dataset_rejects_history_outside_requested_window():
    dates = pd.bdate_range("2024-01-02", periods=6)  # includes Jan 9
    partial = _partial(("AAA",), {"AAA": _history("AAA", dates)})

    with pytest.raises(ValueError, match="outside requested inclusive window"):
        build_research_dataset(
            partial,
            start=date(2024, 1, 2),
            end=date(2024, 1, 8),
        )


def test_research_dataset_service_fetches_once_and_keeps_history_outcomes():
    dates = pd.bdate_range("2024-01-02", periods=5)
    partial = _partial(("AAA",), {"AAA": _history("AAA", dates)})

    class FakeHistoryService:
        def __init__(self):
            self.calls = []

        def histories_partial(self, symbols, start, end):
            self.calls.append((list(symbols), start, end))
            return partial

    fake = FakeHistoryService()
    service = ResearchDatasetService(history_service=fake)
    dataset = service.build(
        ["AAA"],
        start=date(2024, 1, 2),
        end=date(2024, 1, 8),
    )

    assert fake.calls == [(["AAA"], date(2024, 1, 2), date(2024, 1, 8))]
    assert dataset.is_complete
    assert dataset.resolved_symbols == ("AAA",)


def test_research_dataset_matches_current_exhaustive_preparation(monkeypatch):
    dates = pd.bdate_range("2024-01-02", periods=64)  # through Mar 29
    required = ("AAA", "BBB", "SPY")
    histories = {
        "AAA": _history("AAA", dates, native_start=100.0),
        "BBB": _history("BBB", dates, native_start=200.0, fx_start=31.0),
        "SPY": _history("SPY", dates, native_start=300.0, fx_start=32.0),
    }
    partial = _partial(required, histories)

    class FakeHistoryService:
        def histories_partial(self, tickers, start, end):
            assert tuple(tickers) == required
            assert start == date(2024, 1, 2)
            assert end == date(2024, 3, 31)
            return partial

    monkeypatch.setattr(
        exhaustive_optimizer,
        "twd_history_service",
        FakeHistoryService(),
    )
    common, audits = exhaustive_optimizer._download_full_period_prices(
        list(required),
        "2024-01-02",
        "2024-04-01",
        "SPY",
    )
    exhaustive_coverage = exhaustive_optimizer._strict_full_period_coverage(
        common,
        ["AAA", "BBB"],
        "SPY",
    )

    dataset = build_research_dataset(
        partial,
        start=date(2024, 1, 2),
        end=date(2024, 3, 31),
    )

    pd.testing.assert_frame_equal(dataset.daily_levels_twd, common)
    assert dataset.reference_calendar.equals(common.attrs["reference_index"])
    for symbol in required:
        assert np.array_equal(
            dataset.availability_masks[symbol],
            common.attrs["availability_masks"][symbol],
        )
        assert dataset.coverage[symbol]["overall"] == pytest.approx(
            exhaustive_coverage[symbol]["overall"]
        )
        assert dataset.coverage[symbol]["missing_days"] == exhaustive_coverage[symbol][
            "missing_days"
        ]
        assert dataset.asset_metadata[symbol]["corporate_action_audit"] == audits[symbol]
        assert dataset.asset_metadata[symbol]["fingerprints"]["native_adjusted_close"] == (
            common.attrs["native_price_fingerprints"][symbol]
        )
        assert dataset.asset_metadata[symbol]["fingerprints"]["fx_to_twd"] == (
            common.attrs["fx_price_fingerprints"][symbol]
        )
        assert dataset.asset_metadata[symbol]["fingerprints"]["aligned_twd_level"] == (
            series_fingerprint(common[symbol])
        )

    assert dataset.coverage["_global_complete_case"]["overall"] == pytest.approx(
        exhaustive_coverage["_global_complete_case"]["overall"]
    )
    assert dataset.coverage["_global_complete_case"]["reference_observations"] == (
        exhaustive_coverage["_global_complete_case"]["reference_observations"]
    )
    assert dataset.coverage["_global_complete_case"]["common_observations"] == (
        exhaustive_coverage["_global_complete_case"]["common_observations"]
    )
