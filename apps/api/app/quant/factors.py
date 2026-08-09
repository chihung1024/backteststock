"""Pure factor-exposure and factor-implied relationship diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

US_FACTOR_COLUMNS = ("MKT_RF", "SMB", "HML", "RMW", "CMA", "MOM")
RISK_FREE_COLUMN = "RF"
DEFAULT_FACTOR_MIN_MONTHS = 36
_VARIANCE_EPSILON = 1e-15


@dataclass(frozen=True, slots=True)
class FactorExposure:
    status: str
    observations: int
    start: str | None
    end: str | None
    intercept_monthly: float | None
    r_squared: float | None
    betas: dict[str, float] | None


@dataclass(frozen=True, slots=True)
class FactorImpliedRelationship:
    status: str
    symbols: tuple[str, ...]
    factor_observations: int
    covariance: pd.DataFrame | None
    correlation: pd.DataFrame | None


def fit_us_factor_exposure(
    native_daily_returns: pd.Series,
    factors: pd.DataFrame,
    *,
    min_observations: int = DEFAULT_FACTOR_MIN_MONTHS,
) -> FactorExposure:
    """Regress monthly native-currency excess return on U.S. factor returns."""

    if not isinstance(native_daily_returns, pd.Series):
        raise TypeError("native_daily_returns must be a pandas Series")
    if not isinstance(min_observations, int) or min_observations < 2:
        raise ValueError("min_observations must be an integer >= 2")

    monthly = _monthly_compounded(native_daily_returns).rename("asset_return")
    factor_frame = _factor_frame(factors)
    joined = factor_frame.join(monthly, how="inner").replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    observations = len(joined)
    start = joined.index[0].date().isoformat() if observations else None
    end = joined.index[-1].date().isoformat() if observations else None
    if observations < min_observations:
        return FactorExposure(
            status="insufficient_observations",
            observations=observations,
            start=start,
            end=end,
            intercept_monthly=None,
            r_squared=None,
            betas=None,
        )

    y = (
        joined["asset_return"].to_numpy(dtype=float)
        - joined[RISK_FREE_COLUMN].to_numpy(dtype=float)
    )
    denominator = float(np.sum((y - y.mean()) ** 2))
    if denominator <= _VARIANCE_EPSILON:
        return FactorExposure(
            status="degenerate_target",
            observations=observations,
            start=start,
            end=end,
            intercept_monthly=None,
            r_squared=None,
            betas=None,
        )

    x = joined[list(US_FACTOR_COLUMNS)].to_numpy(dtype=float)
    design = np.column_stack([np.ones(observations), x])
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    predicted = design @ coefficients
    residual = y - predicted
    r_squared = 1.0 - float(np.sum(residual**2) / denominator)
    return FactorExposure(
        status="ok",
        observations=observations,
        start=start,
        end=end,
        intercept_monthly=float(coefficients[0]),
        r_squared=r_squared,
        betas={
            name: float(value)
            for name, value in zip(
                US_FACTOR_COLUMNS,
                coefficients[1:],
                strict=True,
            )
        },
    )


def factor_implied_relationship(
    exposures: Mapping[str, FactorExposure],
    factors: pd.DataFrame,
) -> FactorImpliedRelationship:
    """Return systematic covariance/correlation implied by valid factor betas."""

    valid = {
        str(symbol): exposure
        for symbol, exposure in exposures.items()
        if exposure.status == "ok" and exposure.betas is not None
    }
    symbols = tuple(sorted(valid))
    factor_frame = _factor_frame(factors)
    if len(symbols) < 2:
        return FactorImpliedRelationship(
            status="insufficient_assets",
            symbols=symbols,
            factor_observations=len(factor_frame),
            covariance=None,
            correlation=None,
        )
    if len(factor_frame) < 2:
        return FactorImpliedRelationship(
            status="insufficient_factor_observations",
            symbols=symbols,
            factor_observations=len(factor_frame),
            covariance=None,
            correlation=None,
        )

    factor_values = factor_frame[list(US_FACTOR_COLUMNS)].to_numpy(dtype=float)
    factor_covariance = np.cov(factor_values, rowvar=False, ddof=1)
    beta_matrix = np.asarray(
        [
            [float(valid[symbol].betas[name]) for name in US_FACTOR_COLUMNS]
            for symbol in symbols
        ],
        dtype=float,
    )
    systematic_covariance = beta_matrix @ factor_covariance @ beta_matrix.T
    variances = np.diag(systematic_covariance)
    if (
        not np.isfinite(systematic_covariance).all()
        or bool((variances <= _VARIANCE_EPSILON).any())
    ):
        return FactorImpliedRelationship(
            status="degenerate_systematic_variance",
            symbols=symbols,
            factor_observations=len(factor_frame),
            covariance=None,
            correlation=None,
        )

    scale = np.sqrt(variances)
    correlation = systematic_covariance / np.outer(scale, scale)
    correlation = np.clip(correlation, -1.0, 1.0)
    np.fill_diagonal(correlation, 1.0)
    return FactorImpliedRelationship(
        status="ok",
        symbols=symbols,
        factor_observations=len(factor_frame),
        covariance=pd.DataFrame(
            systematic_covariance,
            index=symbols,
            columns=symbols,
        ),
        correlation=pd.DataFrame(correlation, index=symbols, columns=symbols),
    )


def _monthly_compounded(returns: pd.Series) -> pd.Series:
    values = pd.to_numeric(returns, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    if values.empty:
        return pd.Series(dtype=float, name="return")
    index = pd.DatetimeIndex(pd.to_datetime(values.index))
    if index.tz is not None:
        index = index.tz_convert(None)
    values = pd.Series(values.to_numpy(dtype=float), index=index, name="return")
    values = values[~values.index.duplicated(keep="last")].sort_index()
    return ((1.0 + values).resample("ME").prod() - 1.0).astype(float)


def _factor_frame(factors: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(factors, pd.DataFrame):
        raise TypeError("factors must be a pandas DataFrame")
    frame = factors.copy()
    frame.columns = [
        str(column).strip().replace("Mkt-RF", "MKT_RF")
        for column in frame.columns
    ]
    missing = [
        column
        for column in (*US_FACTOR_COLUMNS, RISK_FREE_COLUMN)
        if column not in frame.columns
    ]
    if missing:
        raise ValueError("factor dataset missing required columns: " + ", ".join(missing))
    index = pd.DatetimeIndex(pd.to_datetime(frame.index))
    if index.tz is not None:
        index = index.tz_convert(None)
    frame.index = index.to_period("M").to_timestamp("M")
    frame = frame[list((*US_FACTOR_COLUMNS, RISK_FREE_COLUMN))]
    frame = frame.apply(pd.to_numeric, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    return frame[~frame.index.duplicated(keep="last")].sort_index().astype(float)
