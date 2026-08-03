from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from apps.api.app.portfolio.analytics import (
    STYLE_PROXIES,
    constrained_style_analysis,
    factor_fx_regression,
    inflation_adjusted_metrics,
    regime_analysis,
)
from apps.api.app.portfolio.api_models import RegimeType


def test_factor_regression_separates_equity_factors_and_fx_exposure() -> None:
    rng = np.random.default_rng(42)
    index = pd.date_range("2020-01-31", periods=48, freq="ME")
    factors = pd.DataFrame(
        {
            "MKT_RF": rng.normal(0.006, 0.03, len(index)),
            "SMB": rng.normal(0.001, 0.015, len(index)),
            "HML": rng.normal(0.001, 0.015, len(index)),
            "RMW": rng.normal(0.001, 0.01, len(index)),
            "CMA": rng.normal(0.001, 0.01, len(index)),
            "MOM": rng.normal(0.002, 0.02, len(index)),
            "RF": np.full(len(index), 0.001),
        },
        index=index,
    )
    fx_returns = pd.Series(rng.normal(0.0, 0.01, len(index)), index=index)
    portfolio_returns = (
        0.002
        + 1.1 * factors["MKT_RF"]
        + 0.25 * factors["SMB"]
        - 0.15 * factors["HML"]
        + 0.4 * fx_returns
    )
    ledger = SimpleNamespace(
        name="Global",
        symbols=("SPY",),
        daily_returns=portfolio_returns,
    )
    history = SimpleNamespace(
        quote_currency="USD",
        fx_to_twd=(1.0 + fx_returns).cumprod(),
    )

    result = factor_fx_regression(ledger, {"SPY": history}, factors)

    assert result["regression_currency"] == "TWD"
    assert result["factor_source_currency"] == "USD"
    assert result["factor_betas"]["MKT_RF"] == pytest.approx(1.1, abs=1e-6)
    assert result["factor_betas"]["SMB"] == pytest.approx(0.25, abs=1e-6)
    assert result["fx_betas"]["FX_USD_TWD"] == pytest.approx(0.4, abs=1e-6)
    assert result["r_squared"] == pytest.approx(1.0, abs=1e-10)
    assert result["limitations"]


def test_style_analysis_uses_true_nonnegative_sum_to_one_constraints() -> None:
    rng = np.random.default_rng(7)
    index = pd.date_range("2019-01-31", periods=60, freq="ME")
    proxy_returns = {
        style: pd.Series(rng.normal(0.006, 0.025, len(index)), index=index)
        for style in STYLE_PROXIES
    }
    expected = {
        "large_value": 0.35,
        "large_growth": 0.25,
        "mid_value": 0.15,
        "mid_growth": 0.10,
        "small_value": 0.10,
        "small_growth": 0.05,
    }
    portfolio = sum(expected[name] * proxy_returns[name] for name in STYLE_PROXIES)
    ledger = SimpleNamespace(name="Style", daily_returns=portfolio)
    histories = {
        symbol: SimpleNamespace(daily_returns=proxy_returns[style])
        for style, symbol in STYLE_PROXIES.items()
    }

    result = constrained_style_analysis(ledger, histories)

    assert result["constraint"] == "weights >= 0 and sum(weights) = 1"
    assert sum(result["exposures"].values()) == pytest.approx(1.0, abs=1e-10)
    assert all(value >= 0.0 for value in result["exposures"].values())
    for name, value in expected.items():
        assert result["exposures"][name] == pytest.approx(value, abs=2e-4)
    assert result["r_squared"] == pytest.approx(1.0, abs=1e-8)


def test_market_and_macro_regimes_publish_thresholds_samples_and_limitations() -> None:
    index = pd.date_range("2018-01-31", periods=72, freq="ME")
    benchmark = pd.Series(
        np.where(np.arange(len(index)) < 36, 0.012, -0.004),
        index=index,
    )
    portfolio = pd.Series(0.8 * benchmark + 0.002, index=index)
    ledger = SimpleNamespace(name="Regime", daily_returns=portfolio)
    macro_index = pd.date_range("2016-07-31", periods=len(index) + 18, freq="ME")
    cpi = pd.Series(np.linspace(100.0, 125.0, len(macro_index)), index=macro_index)
    gdp = pd.Series(np.linspace(18_000.0, 24_000.0, len(macro_index)), index=macro_index)

    market = regime_analysis(ledger, benchmark, RegimeType.MARKET)
    inflation = regime_analysis(
        ledger,
        benchmark,
        RegimeType.INFLATION,
        cpi=cpi,
    )
    cycle = regime_analysis(
        ledger,
        benchmark,
        RegimeType.BUSINESS_CYCLE,
        cpi=cpi,
        real_gdp=gdp,
    )

    assert market["thresholds"]["moving_average_months"] == 10
    assert market["regimes"]
    assert inflation["source"].startswith("Federal Reserve")
    assert "sample_median_yoy_inflation" in inflation["thresholds"]
    assert cycle["regimes"]
    assert all("months" in row for row in cycle["regimes"])
    assert cycle["limitations"]


def test_macro_regimes_do_not_assign_labels_before_yoy_evidence_exists() -> None:
    index = pd.date_range("2020-01-31", periods=36, freq="ME")
    benchmark = pd.Series(np.linspace(0.002, 0.012, len(index)), index=index)
    portfolio = pd.Series(0.7 * benchmark + 0.001, index=index)
    ledger = SimpleNamespace(name="Macro evidence", daily_returns=portfolio)
    cpi = pd.Series(np.linspace(100.0, 115.0, len(index)), index=index)
    gdp = pd.Series(np.linspace(20_000.0, 23_000.0, len(index)), index=index)

    inflation = regime_analysis(
        ledger,
        benchmark,
        RegimeType.INFLATION,
        cpi=cpi,
    )
    cycle = regime_analysis(
        ledger,
        benchmark,
        RegimeType.BUSINESS_CYCLE,
        cpi=cpi,
        real_gdp=gdp,
    )

    # YoY needs 12 prior months; inflation direction needs one additional month.
    assert inflation["observations"] == 23
    assert cycle["observations"] == 24
    assert sum(row["months"] for row in inflation["regimes"]) == 23
    assert sum(row["months"] for row in cycle["regimes"]) == 24
    assert any("remain unclassified" in item for item in cycle["limitations"])


def test_inflation_adjustment_has_explicit_twd_us_cpi_limitation() -> None:
    index = pd.date_range("2020-01-31", periods=36, freq="ME")
    return_index = pd.Series((1.01 ** np.arange(len(index))), index=index)
    ledger = SimpleNamespace(return_index=return_index)
    cpi = pd.Series(
        np.linspace(100.0, 112.0, 48),
        index=pd.date_range("2019-01-31", periods=48, freq="ME"),
    )

    result = inflation_adjusted_metrics(ledger, cpi)

    assert result["series"] == "CPIAUCSL"
    assert result["currency_context"] == "TWD portfolio deflated by U.S. CPI"
    assert result["real_total_return"] < float(return_index.iloc[-1] - 1.0)
    assert result["limitations"]