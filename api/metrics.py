"""Deterministic performance metrics shared by scan and portfolio backtests."""

from __future__ import annotations

import hashlib
import importlib.metadata
import math
from collections.abc import Mapping

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
DAYS_PER_YEAR = 365.25
EPSILON = 1e-12
METRIC_DEFINITION_VERSION = "2026-08-01.1"
FINGERPRINT_ALGORITHM = "sha256-le-i8-f8-v1"
DATA_SOURCE_NAME = "Yahoo Finance via yfinance"
DATA_SOURCE_SETTINGS = {
    "interval": "1d",
    "auto_adjust": True,
    "repair": True,
    "actions": False,
    "keepna": False,
}


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def normalize_value_series(history, *, name: str = "value") -> pd.Series:
    """Return a positive, finite, unique, timezone-naive daily value series."""
    if history is None:
        return pd.Series(dtype=float, name=name)
    if isinstance(history, pd.DataFrame):
        if name in history.columns:
            raw = history[name]
        elif len(history.columns) == 1:
            raw = history.iloc[:, 0]
        else:
            raise ValueError(f"history must contain a {name!r} column")
    elif isinstance(history, pd.Series):
        raw = history
    else:
        raw = pd.Series(history)

    values = pd.to_numeric(raw, errors="coerce").astype(float)
    values = values.replace([np.inf, -np.inf], np.nan).dropna()
    values = values[values > 0]
    if values.empty:
        return pd.Series(dtype=float, name=name)

    index = pd.DatetimeIndex(pd.to_datetime(values.index))
    if index.tz is not None:
        index = index.tz_convert(None)
    values.index = index.normalize()
    values = values[~values.index.duplicated(keep="last")].sort_index()
    values.name = name
    return values


def align_value_series(asset_history, benchmark_history=None):
    asset = normalize_value_series(asset_history, name="asset")
    if benchmark_history is None:
        return asset, None

    benchmark = normalize_value_series(benchmark_history, name="benchmark")
    aligned = pd.concat([asset, benchmark], axis=1, join="inner").dropna()
    if aligned.empty:
        return pd.Series(dtype=float, name="asset"), pd.Series(
            dtype=float, name="benchmark"
        )
    return aligned["asset"], aligned["benchmark"]


def _canonical_float64(values) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if np.isnan(array).any():
        array = array.copy()
        array[np.isnan(array)] = np.nan
    return array.astype("<f8", copy=False)


def series_fingerprint(history) -> str | None:
    """Hash normalized dates and values as canonical little-endian records."""
    values = normalize_value_series(history)
    if values.empty:
        return None
    records = np.empty(
        len(values),
        dtype=np.dtype([("date", "<i8"), ("value", "<f8")], align=False),
    )
    records["date"] = np.asarray(values.index.asi8, dtype="<i8")
    records["value"] = _canonical_float64(values.to_numpy())
    digest = hashlib.sha256()
    digest.update(f"{FINGERPRINT_ALGORITHM}:series\0".encode("ascii"))
    digest.update(records.tobytes(order="C"))
    return digest.hexdigest()


def aligned_fingerprint(asset_history, benchmark_history) -> str | None:
    """Hash benchmark-calendar pairs without Python row iteration."""
    asset = normalize_value_series(asset_history, name="asset")
    benchmark = normalize_value_series(benchmark_history, name="benchmark")
    if benchmark.empty:
        return None
    aligned_asset = asset.reindex(benchmark.index)
    records = np.empty(
        len(benchmark),
        dtype=np.dtype(
            [("date", "<i8"), ("asset", "<f8"), ("benchmark", "<f8")],
            align=False,
        ),
    )
    records["date"] = np.asarray(benchmark.index.asi8, dtype="<i8")
    records["asset"] = _canonical_float64(aligned_asset.to_numpy())
    records["benchmark"] = _canonical_float64(benchmark.to_numpy())
    digest = hashlib.sha256()
    digest.update(f"{FINGERPRINT_ALGORITHM}:aligned\0".encode("ascii"))
    digest.update(records.tobytes(order="C"))
    return digest.hexdigest()

def benchmark_coverage(asset_history, benchmark_history) -> float:
    asset = normalize_value_series(asset_history, name="asset")
    benchmark = normalize_value_series(benchmark_history, name="benchmark")
    if benchmark.empty:
        return 0.0
    return min(float(len(asset.index.intersection(benchmark.index)) / len(benchmark)), 1.0)


def reproducibility_metadata(
    *,
    risk_free_rate: float,
    benchmark: str | None = None,
    extra: Mapping | None = None,
) -> dict:
    metadata = {
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "data_source": DATA_SOURCE_NAME,
        "data_source_version": package_version("yfinance"),
        "numpy_version": package_version("numpy"),
        "pandas_version": package_version("pandas"),
        "scipy_version": package_version("scipy"),
        "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
        "risk_free_rate": float(risk_free_rate),
        "trading_days_per_year": TRADING_DAYS_PER_YEAR,
        "data_source_settings": dict(DATA_SOURCE_SETTINGS),
    }
    if benchmark:
        metadata["benchmark"] = benchmark
    if extra:
        metadata.update(extra)
    return metadata


def _finite(value, default):
    return float(value) if value is not None and np.isfinite(value) else default


def _empty_result() -> dict:
    return {
        "total_return": 0.0,
        "cagr": 0.0,
        "mdd": 0.0,
        "volatility": 0.0,
        "sharpe_ratio": None,
        "sortino_ratio": None,
        "beta": None,
        "alpha": None,
        "metric_start": None,
        "metric_end": None,
        "metric_price_observations": 0,
        "metric_return_observations": 0,
        "metric_definition_version": METRIC_DEFINITION_VERSION,
    }


def calculate_metrics(asset_history, benchmark_history=None, risk_free_rate: float = 0.0):
    """Calculate all metrics from one common, date-aligned price/value sample.

    Sharpe and Sortino use arithmetic daily excess returns annualized by 252.
    Beta and Jensen alpha use the same paired daily-return observations.
    When a benchmark is supplied, every reported metric uses the common price dates.
    """
    if not math.isfinite(risk_free_rate) or risk_free_rate <= -1:
        raise ValueError("risk_free_rate must be finite and greater than -1")

    values, benchmark = align_value_series(asset_history, benchmark_history)
    result = _empty_result()
    if values.empty:
        return result

    result.update(
        {
            "metric_start": values.index[0].strftime("%Y-%m-%d"),
            "metric_end": values.index[-1].strftime("%Y-%m-%d"),
            "metric_price_observations": int(len(values)),
        }
    )
    if len(values) < 2 or values.iloc[0] <= EPSILON:
        return result

    total_return = float(values.iloc[-1] / values.iloc[0] - 1)
    elapsed_days = float((values.index[-1] - values.index[0]).days)
    years = elapsed_days / DAYS_PER_YEAR
    cagr = (
        float((values.iloc[-1] / values.iloc[0]) ** (1 / years) - 1)
        if years > 0
        else 0.0
    )
    drawdown = values / values.cummax() - 1
    mdd = float(drawdown.min())

    if benchmark is None:
        returns = values.pct_change(fill_method=None).dropna()
        benchmark_returns = None
    else:
        raw_asset = normalize_value_series(asset_history, name="asset")
        raw_benchmark = normalize_value_series(benchmark_history, name="benchmark")
        paired_prices = pd.concat(
            [raw_asset.reindex(raw_benchmark.index), raw_benchmark], axis=1
        )
        paired_returns = paired_prices.pct_change(fill_method=None).dropna()
        returns = paired_returns["asset"]
        benchmark_returns = paired_returns["benchmark"]

    result["metric_return_observations"] = int(len(returns))
    if len(returns) < 2:
        result.update(total_return=total_return, cagr=cagr, mdd=mdd)
        return result

    daily_risk_free = (1 + risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    excess_returns = returns - daily_risk_free
    annual_std = float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
    annualized_excess_return = float(excess_returns.mean() * TRADING_DAYS_PER_YEAR)
    sharpe = (
        annualized_excess_return / annual_std if annual_std > EPSILON else None
    )
    downside_daily = np.minimum(excess_returns.to_numpy(dtype=float), 0.0)
    downside_deviation = float(
        np.sqrt(np.mean(np.square(downside_daily)))
        * np.sqrt(TRADING_DAYS_PER_YEAR)
    )
    sortino = (
        annualized_excess_return / downside_deviation
        if downside_deviation > EPSILON
        else None
    )

    beta = None
    alpha = None
    if benchmark_returns is not None and len(benchmark_returns) == len(returns):
        benchmark_variance = float(benchmark_returns.var(ddof=1))
        if benchmark_variance > EPSILON:
            beta = float(returns.cov(benchmark_returns) / benchmark_variance)
            alpha = float(
                (
                    returns.mean()
                    - (
                        daily_risk_free
                        + beta * (benchmark_returns.mean() - daily_risk_free)
                    )
                )
                * TRADING_DAYS_PER_YEAR
            )

    result.update(
        {
            "total_return": _finite(total_return, 0.0),
            "cagr": _finite(cagr, 0.0),
            "mdd": _finite(mdd, 0.0),
            "volatility": _finite(annual_std, 0.0),
            "sharpe_ratio": _finite(sharpe, None),
            "sortino_ratio": _finite(sortino, None),
            "beta": _finite(beta, None),
            "alpha": _finite(alpha, None),
        }
    )
    return result
