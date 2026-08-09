"""Guarded correlation primitives for daily, structural, downside and stress views."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

TACTICAL_DAILY_WINDOW = 63
MEDIUM_DAILY_WINDOW = 252
STRUCTURAL_WEEKLY_WINDOW = 156
_VARIANCE_EPSILON = 1e-15


@dataclass(frozen=True, slots=True)
class CorrelationResult:
    status: str
    matrix: pd.DataFrame | None
    input_observations: int
    observations: int
    dropped_observations: int
    window: int | None
    condition: str
    threshold: float | None = None


@dataclass(frozen=True, slots=True)
class MultiHorizonCorrelation:
    tactical_daily: CorrelationResult
    medium_daily: CorrelationResult
    structural_weekly: CorrelationResult


def correlation_matrix(
    returns: pd.DataFrame,
    *,
    window: int | None = None,
    min_observations: int,
    condition: str = "unconditional",
) -> CorrelationResult:
    """Return complete-case Pearson correlation with explicit sample accounting."""

    frame = _numeric_frame(returns)
    if window is not None:
        if not isinstance(window, int) or window < 2:
            raise ValueError("correlation window must be an integer >= 2")
        frame = frame.tail(window)
    return _correlation_from_frame(
        frame,
        min_observations=min_observations,
        window=window,
        condition=condition,
        threshold=None,
    )


def multi_horizon_correlations(
    daily_returns: pd.DataFrame,
    weekly_returns: pd.DataFrame,
    *,
    tactical_min_observations: int,
    medium_min_observations: int,
    structural_min_observations: int,
    tactical_window: int = TACTICAL_DAILY_WINDOW,
    medium_window: int = MEDIUM_DAILY_WINDOW,
    structural_window: int = STRUCTURAL_WEEKLY_WINDOW,
) -> MultiHorizonCorrelation:
    """Return the approved tactical/medium/structural correlation views.

    Minimum-observation guards are caller policy and therefore explicit rather
    than hidden in the pure risk core.
    """

    return MultiHorizonCorrelation(
        tactical_daily=correlation_matrix(
            daily_returns,
            window=tactical_window,
            min_observations=tactical_min_observations,
            condition="tactical_daily",
        ),
        medium_daily=correlation_matrix(
            daily_returns,
            window=medium_window,
            min_observations=medium_min_observations,
            condition="medium_daily",
        ),
        structural_weekly=correlation_matrix(
            weekly_returns,
            window=structural_window,
            min_observations=structural_min_observations,
            condition="structural_weekly",
        ),
    )


def downside_correlation(
    returns: pd.DataFrame,
    benchmark_returns: pd.Series,
    *,
    min_observations: int,
) -> CorrelationResult:
    """Return asset correlation conditional on aligned benchmark return < 0."""

    frame, benchmark = _aligned_returns_and_benchmark(returns, benchmark_returns)
    selected = frame.loc[benchmark < 0.0]
    return _correlation_from_frame(
        selected,
        min_observations=min_observations,
        window=None,
        condition="benchmark_negative",
        threshold=0.0,
    )


def stress_correlation(
    returns: pd.DataFrame,
    benchmark_returns: pd.Series,
    *,
    quantile: float,
    min_observations: int,
) -> CorrelationResult:
    """Return correlation in the benchmark lower-tail quantile.

    The threshold is estimated only from aligned finite benchmark observations.
    The result becomes `insufficient_observations` rather than emitting a
    precise matrix when the selected tail sample is too small.
    """

    if not math.isfinite(quantile) or not 0.0 < quantile < 0.5:
        raise ValueError("stress quantile must be finite and between 0 and 0.5")
    frame, benchmark = _aligned_returns_and_benchmark(returns, benchmark_returns)
    threshold = float(benchmark.quantile(quantile))
    selected = frame.loc[benchmark <= threshold]
    return _correlation_from_frame(
        selected,
        min_observations=min_observations,
        window=None,
        condition=f"benchmark_lower_tail_q{quantile:.12g}",
        threshold=threshold,
    )


def _correlation_from_frame(
    frame: pd.DataFrame,
    *,
    min_observations: int,
    window: int | None,
    condition: str,
    threshold: float | None,
    input_observations: int | None = None,
) -> CorrelationResult:
    minimum = _minimum_observations(min_observations)
    original_count = len(frame) if input_observations is None else input_observations
    clean = frame.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    observations = len(clean)
    dropped = max(int(original_count - observations), 0)
    if observations < minimum:
        return CorrelationResult(
            status="insufficient_observations",
            matrix=None,
            input_observations=int(original_count),
            observations=observations,
            dropped_observations=dropped,
            window=window,
            condition=condition,
            threshold=threshold,
        )

    standard_deviation = clean.std(ddof=1)
    if bool((standard_deviation <= _VARIANCE_EPSILON).any()):
        return CorrelationResult(
            status="degenerate_variance",
            matrix=None,
            input_observations=int(original_count),
            observations=observations,
            dropped_observations=dropped,
            window=window,
            condition=condition,
            threshold=threshold,
        )

    matrix = clean.corr(method="pearson")
    if not np.isfinite(matrix.to_numpy(dtype=float)).all():
        return CorrelationResult(
            status="degenerate_variance",
            matrix=None,
            input_observations=int(original_count),
            observations=observations,
            dropped_observations=dropped,
            window=window,
            condition=condition,
            threshold=threshold,
        )
    return CorrelationResult(
        status="ok",
        matrix=matrix,
        input_observations=int(original_count),
        observations=observations,
        dropped_observations=dropped,
        window=window,
        condition=condition,
        threshold=threshold,
    )


def _numeric_frame(returns: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(returns, pd.DataFrame):
        raise TypeError("returns must be a pandas DataFrame")
    if returns.shape[1] < 1:
        raise ValueError("returns must contain at least one asset column")
    if not returns.columns.is_unique:
        raise ValueError("return columns must be unique")
    return returns.apply(pd.to_numeric, errors="coerce").astype(float)


def _aligned_returns_and_benchmark(
    returns: pd.DataFrame,
    benchmark_returns: pd.Series,
) -> tuple[pd.DataFrame, pd.Series]:
    frame = _numeric_frame(returns)
    if not isinstance(benchmark_returns, pd.Series):
        raise TypeError("benchmark_returns must be a pandas Series")
    benchmark = pd.to_numeric(benchmark_returns, errors="coerce").astype(float)

    benchmark_label = object()
    joined = pd.concat(
        [frame, benchmark.rename(benchmark_label)],
        axis=1,
        join="inner",
    )
    aligned_frame = joined[frame.columns].replace([np.inf, -np.inf], np.nan)
    aligned_benchmark = joined[benchmark_label].replace([np.inf, -np.inf], np.nan)
    finite_benchmark = aligned_benchmark.notna()
    return (
        aligned_frame.loc[finite_benchmark],
        aligned_benchmark.loc[finite_benchmark],
    )


def _minimum_observations(value: int) -> int:
    if not isinstance(value, int) or value < 2:
        raise ValueError("min_observations must be an integer >= 2")
    return value
