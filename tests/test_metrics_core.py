import math

import numpy as np
import pandas as pd
import pytest

from api.metrics import (
    FINGERPRINT_ALGORITHM,
    METRIC_DEFINITION_VERSION,
    aligned_fingerprint,
    benchmark_coverage,
    calculate_metrics,
    reproducibility_metadata,
    series_fingerprint,
)


def history(values, dates=None):
    if dates is None:
        dates = pd.bdate_range("2024-01-02", periods=len(values))
    return pd.Series(values, index=pd.DatetimeIndex(dates), name="value")


def test_exact_total_return_cagr_mdd_and_risk_metrics():
    values = history([100.0, 110.0, 99.0, 118.8])
    metrics = calculate_metrics(values, risk_free_rate=0.0)
    returns = values.pct_change(fill_method=None).dropna()
    expected_vol = returns.std(ddof=1) * math.sqrt(252)
    expected_sharpe = returns.mean() * 252 / expected_vol
    downside = np.minimum(returns.to_numpy(), 0.0)
    expected_downside = np.sqrt(np.mean(downside**2)) * math.sqrt(252)
    expected_sortino = returns.mean() * 252 / expected_downside

    assert metrics["total_return"] == pytest.approx(0.188)
    assert metrics["mdd"] == pytest.approx(-0.10)
    assert metrics["volatility"] == pytest.approx(expected_vol)
    assert metrics["sharpe_ratio"] == pytest.approx(expected_sharpe)
    assert metrics["sortino_ratio"] == pytest.approx(expected_sortino)
    assert metrics["metric_definition_version"] == METRIC_DEFINITION_VERSION
    assert metrics["metric_price_observations"] == 4
    assert metrics["metric_return_observations"] == 3


def test_self_benchmark_beta_one_alpha_zero():
    values = history([100, 102, 101, 105, 104, 108])
    metrics = calculate_metrics(values, values)
    assert metrics["beta"] == pytest.approx(1.0, abs=1e-12)
    assert metrics["alpha"] == pytest.approx(0.0, abs=1e-12)


def test_prices_are_aligned_before_returns_to_avoid_mismatched_intervals():
    dates = pd.bdate_range("2024-01-02", periods=6)
    asset = history([100, 102, 106, 108, 111], dates[[0, 1, 3, 4, 5]])
    benchmark = history([100, 101, 103, 105, 106, 109], dates)
    metrics = calculate_metrics(asset, benchmark)

    paired = pd.DataFrame(
        {
            "asset": asset.reindex(dates),
            "benchmark": benchmark,
        }
    )
    expected_returns = paired.pct_change(fill_method=None).dropna()
    expected_beta = (
        expected_returns["asset"].cov(expected_returns["benchmark"])
        / expected_returns["benchmark"].var(ddof=1)
    )

    assert metrics["metric_price_observations"] == 5
    assert metrics["metric_return_observations"] == 3
    assert metrics["beta"] == pytest.approx(expected_beta)


def test_short_history_uses_same_period_for_asset_and_benchmark():
    benchmark_dates = pd.bdate_range("2020-01-02", periods=12)
    benchmark = history(np.linspace(100, 120, 12), benchmark_dates)
    asset_dates = benchmark_dates[-6:]
    asset = history(np.linspace(50, 65, 6), asset_dates)
    metrics = calculate_metrics(asset, benchmark)

    assert metrics["metric_start"] == asset_dates[0].strftime("%Y-%m-%d")
    assert metrics["metric_end"] == asset_dates[-1].strftime("%Y-%m-%d")
    assert metrics["metric_price_observations"] == 6


def test_coverage_uses_actual_benchmark_trading_dates():
    benchmark_dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-05", "2024-01-08"])
    asset_dates = benchmark_dates[[0, 2, 3]]
    benchmark = history([100, 101, 102, 103], benchmark_dates)
    asset = history([50, 51, 52], asset_dates)
    assert benchmark_coverage(asset, benchmark) == pytest.approx(0.75)


def test_fingerprints_are_stable_and_change_with_data():
    values = history([100, 101, 102])
    same = history([100, 101, 102])
    changed = history([100, 101, 103])
    assert series_fingerprint(values) == series_fingerprint(same)
    assert series_fingerprint(values) != series_fingerprint(changed)
    assert aligned_fingerprint(values, same) != aligned_fingerprint(values, changed)


def test_invalid_risk_free_rate_rejected():
    with pytest.raises(ValueError):
        calculate_metrics(history([100, 101, 102]), risk_free_rate=-1.0)


def test_zero_risk_denominator_is_reported_as_undefined_not_zero():
    constant = history([100, 100, 100, 100])
    metrics = calculate_metrics(constant)
    assert metrics["volatility"] == 0.0
    assert metrics["sharpe_ratio"] is None
    assert metrics["sortino_ratio"] is None


def test_reproducibility_metadata_includes_price_repair_runtime():
    metadata = reproducibility_metadata(risk_free_rate=0.0, benchmark="SPY")
    assert metadata["data_source_settings"]["repair"] is True
    assert metadata["scipy_version"] == "1.17.1"
    assert metadata["fingerprint_algorithm"] == FINGERPRINT_ALGORITHM
