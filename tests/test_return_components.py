from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from api.corporate_actions import extract_adjusted_close_prices
from api.market_data import (
    MARKET_DATA_CONTRACT_VERSION,
    RETURN_COMPONENT_SOURCE_VERSION,
    _attach_return_component_attrs,
)
from apps.api.app.data.fx_provider import FXLevels, normalize_quote_convention
from apps.api.app.data.history_service import (
    TWDAssetHistory,
    TWDHistoryService,
    _scale_native_prices,
)
from apps.api.app.data.return_components import (
    RETURN_COMPONENTS_CONTRACT_VERSION,
    native_components_from_adjusted_close,
    total_only_components,
    value_components_in_twd,
)
from apps.api.app.data.twd_valuation import value_adjusted_close_in_twd

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "return_components"
    / "synthetic_market_data.csv"
)


def _fixture_series(
    prefix: str = "AAA",
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    frame = pd.read_csv(FIXTURE, parse_dates=["date"]).set_index("date")
    adjusted = frame[f"{prefix}_adjusted_close"].rename(prefix)
    raw = frame[f"{prefix}_native_close"].rename("raw_close")
    distribution = frame[f"{prefix}_distribution"].rename("dividends")
    fx = frame[f"{prefix}_fx_to_twd"].rename("fx_to_twd")
    adjusted.attrs = {
        "raw_close": raw,
        "dividends": distribution,
        "capital_gains": pd.Series(0.0, index=frame.index),
        "corporate_action_audit": {"status": "verified_standard_actions"},
    }
    return adjusted, raw, distribution, fx


class _FixtureFXProvider:
    def __init__(self, fx: pd.Series) -> None:
        self.fx = fx

    def quote_convention(self, _symbol: str):
        return normalize_quote_convention("USD")

    def fx_to_twd(self, currency: str, _start: date, _end: date) -> FXLevels:
        return FXLevels(
            source_currency=currency,
            target_currency="TWD",
            levels=self.fx,
            method="direct",
            tickers=(f"{currency}TWD=X",),
            correction_count=0,
            unresolved_count=0,
            material_transition_count=0,
        )


def test_native_components_preserve_identity_across_split_like_raw_jump() -> None:
    adjusted, raw, _, _ = _fixture_series()
    components = native_components_from_adjusted_close(adjusted)

    np.testing.assert_allclose(
        components.total_returns,
        components.price_returns + components.distribution_returns,
        rtol=0.0,
        atol=1e-12,
    )
    split_date = pd.Timestamp("2024-01-05")
    assert raw.pct_change(fill_method=None).loc[split_date] < -0.45
    assert components.price_returns.loc[split_date] > 0.0
    assert components.distribution_returns.loc[split_date] == 0.0
    assert components.audit["raw_total_mismatch_rows"] >= 1
    assert components.audit["contract_version"] == RETURN_COMPONENTS_CONTRACT_VERSION
    assert (components.distribution_returns >= 0.0).all()


def test_twd_components_match_adjusted_level_times_fx_without_backward_fill() -> None:
    adjusted, _, _, fx = _fixture_series()
    native = native_components_from_adjusted_close(adjusted)
    fx = fx.loc[fx.index >= pd.Timestamp("2024-01-03")]
    fx.loc[pd.Timestamp("2024-01-06")] = 31.35
    fx = fx.sort_index()

    components = value_components_in_twd(
        native,
        source_currency="USD",
        fx_to_twd=fx,
    )

    union = adjusted.index.union(fx.index).sort_values().unique()
    expected = adjusted.reindex(union).ffill() * fx.reindex(union).ffill()
    expected = expected.dropna()
    expected = expected / expected.iloc[0]

    assert components.first_date == pd.Timestamp("2024-01-03")
    np.testing.assert_allclose(
        components.total_return_index,
        expected,
        rtol=0.0,
        atol=1e-12,
    )
    fx_only_date = pd.Timestamp("2024-01-06")
    assert fx_only_date in components.total_returns.index
    assert components.distribution_returns.loc[fx_only_date] == 0.0
    assert components.total_returns.loc[fx_only_date] != 0.0
    assert components.audit["calendar_policy"].endswith("no_backward_fill")


def test_distribution_cash_and_reinvestment_are_equal_on_payment_date() -> None:
    index = pd.to_datetime(["2024-01-02", "2024-01-03"])
    adjusted = pd.Series([100.0, 102.0], index=index, name="TEST")
    adjusted.attrs = {
        "raw_close": pd.Series([100.0, 101.0], index=index),
        "dividends": pd.Series([0.0, 1.0], index=index),
        "capital_gains": pd.Series([0.0, 0.0], index=index),
    }
    native = native_components_from_adjusted_close(adjusted)
    twd = value_components_in_twd(native, source_currency="TWD")

    opening = 100.0
    reinvested = opening * (1.0 + twd.total_returns.iloc[1])
    retained_asset = opening * (1.0 + twd.price_returns.iloc[1])
    retained_cash = opening * twd.distribution_returns.iloc[1]
    assert np.isclose(reinvested, retained_asset + retained_cash)
    assert np.isclose(reinvested, 102.0)


def test_total_only_fallback_is_backward_compatible() -> None:
    index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    adjusted_twd = pd.Series([100.0, 101.0, 99.0], index=index)
    components = total_only_components(adjusted_twd, source_currency="USD")

    np.testing.assert_allclose(components.price_returns, components.total_returns)
    assert not components.distribution_returns.any()
    assert components.audit["status"] == "total_return_only"


def test_market_data_retains_clean_component_inputs_in_series_attrs() -> None:
    index = pd.to_datetime(["2024-01-02", "2024-01-03"])
    columns = pd.MultiIndex.from_product(
        [
            ["Adj Close", "Close", "Dividends", "Capital Gains", "Stock Splits"],
            ["AAA"],
        ]
    )
    downloaded = pd.DataFrame(
        [[100.0, 100.0, 0.0, 0.0, 0.0], [102.0, 101.0, 1.0, 0.0, 0.0]],
        index=index,
        columns=columns,
    )
    extracted = extract_adjusted_close_prices(downloaded, ["AAA"])
    _attach_return_component_attrs(downloaded, ["AAA"], extracted)
    attrs = extracted["AAA"].attrs

    assert attrs["return_component_source_version"] == RETURN_COMPONENT_SOURCE_VERSION
    np.testing.assert_allclose(attrs["raw_close"], [100.0, 101.0])
    np.testing.assert_allclose(attrs["dividends"], [0.0, 1.0])
    np.testing.assert_allclose(attrs["capital_gains"], [0.0, 0.0])
    assert "components" in MARKET_DATA_CONTRACT_VERSION


def test_minor_unit_scaling_applies_to_prices_and_cash_but_not_split_ratios() -> None:
    index = pd.to_datetime(["2024-01-02", "2024-01-03"])
    adjusted = pd.Series([1000.0, 1020.0], index=index)
    adjusted.attrs = {
        "raw_close": pd.Series([1000.0, 1010.0], index=index),
        "dividends": pd.Series([0.0, 10.0], index=index),
        "capital_gains": pd.Series([0.0, 5.0], index=index),
        "stock_splits": pd.Series([0.0, 2.0], index=index),
    }
    scaled = _scale_native_prices(adjusted, 0.01)

    np.testing.assert_allclose(scaled, [10.0, 10.2])
    np.testing.assert_allclose(scaled.attrs["raw_close"], [10.0, 10.1])
    np.testing.assert_allclose(scaled.attrs["dividends"], [0.0, 0.1])
    np.testing.assert_allclose(scaled.attrs["capital_gains"], [0.0, 0.05])
    np.testing.assert_allclose(scaled.attrs["stock_splits"], [0.0, 2.0])


def test_twd_asset_history_exposes_components_without_changing_daily_returns() -> None:
    adjusted, _, _, fx = _fixture_series()
    native = native_components_from_adjusted_close(adjusted)
    valuation = value_adjusted_close_in_twd(
        adjusted,
        source_currency="USD",
        fx_to_twd=fx,
    )
    components = value_components_in_twd(
        native,
        source_currency="USD",
        fx_to_twd=fx,
    )
    history = TWDAssetHistory(
        symbol="AAA",
        quote_currency="USD",
        valuation=valuation,
        corporate_action_audit=None,
        return_components=components,
    )

    np.testing.assert_allclose(history.daily_returns, components.total_returns)
    np.testing.assert_allclose(
        history.daily_returns,
        history.price_returns + history.distribution_returns,
        atol=1e-12,
    )
    assert history.return_component_audit["contract_version"] == (
        RETURN_COMPONENTS_CONTRACT_VERSION
    )


def test_history_service_builds_components_and_preserves_partial_success(
    monkeypatch,
) -> None:
    adjusted, _, _, fx = _fixture_series()
    monkeypatch.setattr(
        "apps.api.app.data.history_service.download_prices_finitely",
        lambda *_args: ({"AAA": adjusted}, ["BAD"]),
    )
    service = TWDHistoryService(fx_provider=_FixtureFXProvider(fx))

    result = service.histories_partial(
        ["AAA", "BAD"],
        date(2024, 1, 2),
        date(2024, 1, 11),
    )

    assert set(result.histories) == {"AAA"}
    assert result.failures["BAD"].stage == "download"
    history = result.histories["AAA"]
    assert history.return_components is not None
    assert history.return_component_audit["status"].startswith("verified")
    assert history.distribution_returns.gt(0.0).sum() == 2
    np.testing.assert_allclose(
        history.daily_returns,
        history.price_returns + history.distribution_returns,
        atol=1e-12,
    )


def test_twd_asset_history_legacy_positional_construction_is_unchanged() -> None:
    index = pd.to_datetime(["2024-01-02", "2024-01-03"])
    valuation = value_adjusted_close_in_twd(
        pd.Series([100.0, 101.0], index=index),
        source_currency="TWD",
    )
    history = TWDAssetHistory(
        "AAA",
        "TWD",
        valuation,
        None,
        {"method": "identity"},
        "TWD",
        1.0,
    )

    assert history.fx_audit == {"method": "identity"}
    assert history.raw_quote_currency == "TWD"
    assert history.native_price_scale == 1.0
    assert history.return_components is None
