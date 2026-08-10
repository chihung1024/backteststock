"""Pure factor-exposure and factor-implied relationship diagnostics."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

US_FACTOR_COLUMNS = ("MKT_RF", "SMB", "HML", "RMW", "CMA", "MOM")
RISK_FREE_COLUMN = "RF"
DEFAULT_FACTOR_MIN_MONTHS = 36
FACTOR_MONTHLY_RETURN_POLICY = "boundary-month-exclusion-v1"
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
    observations: int
    start: str | None
    end: str | None
    sample_fingerprint_sha256: str | None
    covariance: pd.DataFrame | None
    correlation: pd.DataFrame | None


def boundary_safe_monthly_returns(native_daily_returns: pd.Series) -> pd.Series:
    """Compound only interior represented calendar months.

    The first represented month cannot prove a full holding-period month because
    the pre-window close is unavailable. The last represented month can also be
    partial. V1 therefore excludes both boundaries without pretending to own an
    exchange-specific complete-month calendar.
    """

    values = _normalized_daily_returns(native_daily_returns)
    if values.empty:
        return pd.Series(dtype=float, name="asset_return")
    periods = values.index.to_period("M")
    compounded = ((1.0 + values).groupby(periods).prod() - 1.0).astype(float)
    if len(compounded) <= 2:
        return pd.Series(dtype=float, name="asset_return")
    interior = compounded.iloc[1:-1].copy()
    interior.index = interior.index.to_timestamp("M")
    return interior.rename("asset_return")


def fit_us_factor_exposure(
    native_daily_returns: pd.Series,
    factors: pd.DataFrame,
    *,
    min_observations: int = DEFAULT_FACTOR_MIN_MONTHS,
) -> FactorExposure:
    """Regress boundary-safe monthly native excess return on U.S. factors."""

    if not isinstance(native_daily_returns, pd.Series):
        raise TypeError("native_daily_returns must be a pandas Series")
    if not isinstance(min_observations, int) or min_observations < 2:
        raise ValueError("min_observations must be an integer >= 2")
    monthly = boundary_safe_monthly_returns(native_daily_returns)
    return _fit_factor_exposure_from_monthly(
        monthly,
        _factor_frame(factors),
        min_observations=min_observations,
    )


def factor_implied_relationship(
    native_daily_returns: Mapping[str, pd.Series],
    factors: pd.DataFrame,
    *,
    min_observations: int = DEFAULT_FACTOR_MIN_MONTHS,
) -> FactorImpliedRelationship:
    """Refit all relationship betas and factor covariance on one common sample."""

    if not isinstance(native_daily_returns, Mapping):
        raise TypeError("native_daily_returns must be a mapping of symbol to Series")
    if not isinstance(min_observations, int) or min_observations < 2:
        raise ValueError("min_observations must be an integer >= 2")

    factor_frame = _factor_frame(factors)
    monthly_by_symbol: dict[str, pd.Series] = {}
    individual: dict[str, FactorExposure] = {}
    for raw_symbol, returns in native_daily_returns.items():
        symbol = str(raw_symbol)
        if symbol in monthly_by_symbol:
            raise ValueError("factor relationship symbols must remain unique after normalization")
        monthly = boundary_safe_monthly_returns(returns)
        monthly_by_symbol[symbol] = monthly
        individual[symbol] = _fit_factor_exposure_from_monthly(
            monthly,
            factor_frame,
            min_observations=min_observations,
        )

    symbols = tuple(
        sorted(
            symbol
            for symbol, exposure in individual.items()
            if exposure.status == "ok" and exposure.betas is not None
        )
    )
    if len(symbols) < 2:
        return _empty_relationship("insufficient_assets", symbols)

    common = factor_frame.copy()
    for symbol in symbols:
        common = common.join(
            monthly_by_symbol[symbol].rename(_asset_column(symbol)),
            how="inner",
        )
    common = common.replace([np.inf, -np.inf], np.nan).dropna()
    observations = len(common)
    start = common.index[0].date().isoformat() if observations else None
    end = common.index[-1].date().isoformat() if observations else None
    fingerprint = _frame_fingerprint(common) if observations else None
    if observations < min_observations:
        return FactorImpliedRelationship(
            status="insufficient_common_observations",
            symbols=symbols,
            observations=observations,
            start=start,
            end=end,
            sample_fingerprint_sha256=fingerprint,
            covariance=None,
            correlation=None,
        )

    relationship_betas: dict[str, dict[str, float]] = {}
    common_factors = common[list((*US_FACTOR_COLUMNS, RISK_FREE_COLUMN))]
    for symbol in symbols:
        refit = _fit_factor_exposure_from_monthly(
            common[_asset_column(symbol)].rename("asset_return"),
            common_factors,
            min_observations=min_observations,
        )
        if refit.status != "ok" or refit.betas is None:
            return FactorImpliedRelationship(
                status=f"common_refit_{refit.status}",
                symbols=symbols,
                observations=observations,
                start=start,
                end=end,
                sample_fingerprint_sha256=fingerprint,
                covariance=None,
                correlation=None,
            )
        relationship_betas[symbol] = refit.betas

    factor_values = common[list(US_FACTOR_COLUMNS)].to_numpy(dtype=float)
    factor_covariance = np.cov(factor_values, rowvar=False, ddof=1)
    beta_matrix = np.asarray(
        [
            [float(relationship_betas[symbol][name]) for name in US_FACTOR_COLUMNS]
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
            observations=observations,
            start=start,
            end=end,
            sample_fingerprint_sha256=fingerprint,
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
        observations=observations,
        start=start,
        end=end,
        sample_fingerprint_sha256=fingerprint,
        covariance=pd.DataFrame(
            systematic_covariance,
            index=symbols,
            columns=symbols,
        ),
        correlation=pd.DataFrame(correlation, index=symbols, columns=symbols),
    )


def _fit_factor_exposure_from_monthly(
    monthly: pd.Series,
    factor_frame: pd.DataFrame,
    *,
    min_observations: int,
) -> FactorExposure:
    joined = factor_frame.join(monthly.rename("asset_return"), how="inner").replace(
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


def _normalized_daily_returns(returns: pd.Series) -> pd.Series:
    if not isinstance(returns, pd.Series):
        raise TypeError("native_daily_returns must be a pandas Series")
    values = pd.to_numeric(returns, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    if values.empty:
        return pd.Series(dtype=float, name="return")
    index = pd.DatetimeIndex(pd.to_datetime(values.index))
    if index.tz is not None:
        index = index.tz_convert(None)
    values = pd.Series(values.to_numpy(dtype=float), index=index, name="return")
    return values[~values.index.duplicated(keep="last")].sort_index()


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


def _asset_column(symbol: str) -> str:
    return f"asset::{symbol}"


def _frame_fingerprint(frame: pd.DataFrame) -> str:
    payload = {
        "columns": [str(column) for column in frame.columns],
        "dates": [pd.Timestamp(value).isoformat() for value in frame.index],
        "values": frame.to_numpy(dtype=float).tolist(),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _empty_relationship(status: str, symbols: tuple[str, ...]) -> FactorImpliedRelationship:
    return FactorImpliedRelationship(
        status=status,
        symbols=symbols,
        observations=0,
        start=None,
        end=None,
        sample_fingerprint_sha256=None,
        covariance=None,
        correlation=None,
    )
