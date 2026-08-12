"""Advanced analytics with explicit currency, sample and methodology metadata."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from apps.api.app.data.history_service import TWDAssetHistory
from apps.api.app.portfolio.api_models import RegimeType
from apps.api.app.portfolio.ledger import PortfolioLedger
from apps.api.app.portfolio.analytics_data import FRED_SOURCE, FRENCH_FACTOR_SOURCE

PORTFOLIO_ANALYTICS_CONTRACT_VERSION = "portfolio-analytics-twd-2026-08-12.1"
STYLE_PROXIES = {
    "large_value": "IWD",
    "large_growth": "IWF",
    "mid_value": "IWS",
    "mid_growth": "IWP",
    "small_value": "IWN",
    "small_growth": "IWO",
}
_FACTOR_COLUMNS = ("MKT_RF", "SMB", "HML", "RMW", "CMA", "MOM")


def factor_fx_regression(
    ledger: PortfolioLedger,
    histories: Mapping[str, TWDAssetHistory],
    factors: pd.DataFrame,
    *,
    comparison_window: tuple[pd.Timestamp, pd.Timestamp] | None = None,
) -> dict[str, Any]:
    """Regress monthly TWD portfolio returns on U.S. factors and FX covariates.

    This is deliberately not presented as a pure USD Fama-French regression.
    The dependent variable remains the Taiwan investor's TWD return, while
    quote-currency/TWD monthly returns are included separately as FX factors.

    When a multi-portfolio common window is active, callers must pass histories
    already bounded/reset to that exact daily interval. Official French factors
    are monthly full-period observations, so the first and last represented
    calendar months are conservatively excluded from the regression sample.
    """

    portfolio = _monthly_compounded(ledger.daily_returns).rename("portfolio_twd")
    factor_frame = factors.copy()
    factor_frame.index = _month_end_index(factor_frame.index)
    factor_frame.columns = [
        str(column).strip().replace("Mkt-RF", "MKT_RF")
        for column in factor_frame.columns
    ]
    factor_columns = [column for column in _FACTOR_COLUMNS if column in factor_frame]
    if not factor_columns:
        raise ValueError("factor dataset contains no supported factor columns")

    fx_columns: dict[str, pd.Series] = {}
    seen_currencies: set[str] = set()
    for symbol in ledger.symbols:
        history = histories[symbol]
        currency = history.quote_currency.upper()
        if currency == "TWD" or currency in seen_currencies:
            continue
        seen_currencies.add(currency)
        levels = history.fx_to_twd.astype(float).sort_index()
        monthly = levels.resample("ME").last().pct_change(fill_method=None)
        fx_columns[f"FX_{currency}_TWD"] = monthly

    independent = factor_frame[factor_columns].copy()
    for name, series in fx_columns.items():
        independent[name] = series
    joined = independent.join(portfolio, how="inner").replace(
        [np.inf, -np.inf], np.nan
    ).dropna()

    sample_policy = "full-overlap-months"
    excluded_boundary_months: list[str] = []
    if comparison_window is not None:
        start, end = (pd.Timestamp(value) for value in comparison_window)
        boundary_periods = {start.to_period("M"), end.to_period("M")}
        excluded_boundary_months = sorted(str(period) for period in boundary_periods)
        joined_periods = joined.index.to_period("M")
        joined = joined.loc[~joined_periods.isin(boundary_periods)]
        sample_policy = "exclude-common-window-boundary-months"

    predictor_columns = [column for column in joined if column != "portfolio_twd"]
    minimum = max(24, len(predictor_columns) * 3)
    if len(joined) < minimum:
        raise ValueError(
            f"factor and FX regression requires at least {minimum} overlapping months"
        )

    x = joined[predictor_columns].to_numpy(dtype=float)
    y = joined["portfolio_twd"].to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(x)), x])
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    predicted = design @ coefficients
    residual = y - predicted
    denominator = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - float(np.sum(residual**2) / denominator) if denominator else 0.0
    intercept = float(coefficients[0])
    annualized_alpha = (
        float((1.0 + intercept) ** 12 - 1.0) if intercept > -1.0 else -1.0
    )
    exposures = {
        name: float(value)
        for name, value in zip(predictor_columns, coefficients[1:], strict=True)
    }
    return {
        "contract_version": PORTFOLIO_ANALYTICS_CONTRACT_VERSION,
        "model": "U.S. Fama-French 5 Factor + Momentum with quote-currency FX covariates",
        "regression_currency": "TWD",
        "factor_source": FRENCH_FACTOR_SOURCE,
        "factor_source_currency": "USD",
        "sample_policy": sample_policy,
        "excluded_boundary_months": excluded_boundary_months,
        "observations": int(len(joined)),
        "start": joined.index[0].date().isoformat(),
        "end": joined.index[-1].date().isoformat(),
        "annualized_intercept": annualized_alpha,
        "r_squared": r_squared,
        "factor_betas": {
            name: exposures[name] for name in factor_columns if name in exposures
        },
        "fx_betas": {
            name: value for name, value in exposures.items() if name.startswith("FX_")
        },
        "limitations": [
            "The dependent return is TWD while the published equity factors are U.S. dollar factors.",
            "FX covariates separate measured currency exposure but do not make U.S. factors a global holdings model.",
            "Coefficients describe historical co-movement and are not forecasts.",
        ],
    }


def constrained_style_analysis(
    ledger: PortfolioLedger,
    style_histories: Mapping[str, TWDAssetHistory],
) -> dict[str, Any]:
    """Fit non-negative style weights constrained to sum exactly to one."""

    missing = [symbol for symbol in STYLE_PROXIES.values() if symbol not in style_histories]
    if missing:
        raise ValueError("missing style proxy histories: " + ", ".join(missing))
    portfolio = _monthly_compounded(ledger.daily_returns).rename("portfolio")
    proxies = pd.DataFrame(
        {
            style: _monthly_compounded(style_histories[symbol].daily_returns)
            for style, symbol in STYLE_PROXIES.items()
        }
    )
    joined = proxies.join(portfolio, how="inner").replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    if len(joined) < 24:
        raise ValueError("style analysis requires at least 24 overlapping months")

    columns = list(STYLE_PROXIES)
    x = joined[columns].to_numpy(dtype=float)
    y = joined["portfolio"].to_numpy(dtype=float)

    def objective(weights: np.ndarray) -> float:
        residual = y - x @ weights
        return float(np.dot(residual, residual))

    initial = np.full(len(columns), 1.0 / len(columns), dtype=float)
    result = minimize(
        objective,
        initial,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * len(columns),
        constraints=[{"type": "eq", "fun": lambda weights: float(weights.sum() - 1.0)}],
        options={"ftol": 1e-12, "maxiter": 2_000},
    )
    if not result.success:
        raise ValueError(f"constrained style regression failed: {result.message}")
    weights = np.clip(np.asarray(result.x, dtype=float), 0.0, 1.0)
    weights /= float(weights.sum())
    predicted = x @ weights
    denominator = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - float(np.sum((y - predicted) ** 2) / denominator) if denominator else 0.0
    return {
        "contract_version": PORTFOLIO_ANALYTICS_CONTRACT_VERSION,
        "model": "Constrained returns-based U.S. equity style proxy",
        "regression_currency": "TWD",
        "constraint": "weights >= 0 and sum(weights) = 1",
        "observations": int(len(joined)),
        "start": joined.index[0].date().isoformat(),
        "end": joined.index[-1].date().isoformat(),
        "r_squared": r_squared,
        "exposures": {
            name: float(value) for name, value in zip(columns, weights, strict=True)
        },
        "proxy_symbols": dict(STYLE_PROXIES),
        "limitations": [
            "ETF proxy regression is not a holdings-based style box.",
            "Results depend on the selected proxy set and historical sample.",
        ],
    }


def regime_analysis(
    ledger: PortfolioLedger,
    benchmark_returns: pd.Series,
    regime_type: RegimeType,
    *,
    cpi: pd.Series | None = None,
    real_gdp: pd.Series | None = None,
) -> dict[str, Any]:
    portfolio = _monthly_compounded(ledger.daily_returns).rename("portfolio")
    benchmark = _monthly_compounded(benchmark_returns).rename("benchmark")
    joined = pd.concat([portfolio, benchmark], axis=1).dropna()
    if len(joined) < 12:
        raise ValueError("regime analysis requires at least 12 overlapping months")

    thresholds: dict[str, float | int | str] = {}
    source = "portfolio benchmark"
    if regime_type == RegimeType.MARKET:
        benchmark_index = (1.0 + joined["benchmark"]).cumprod()
        moving_average = benchmark_index.rolling(10, min_periods=6).mean()
        labels = pd.Series(index=joined.index, dtype="object")
        valid = moving_average.notna()
        labels.loc[valid] = np.where(
            benchmark_index.loc[valid] >= moving_average.loc[valid],
            "Bull market",
            "Bear market",
        )
        thresholds = {"moving_average_months": 10, "minimum_months": 6}
    elif regime_type == RegimeType.VOLATILITY:
        volatility = joined["benchmark"].rolling(12, min_periods=6).std() * math.sqrt(12)
        threshold = _finite_median(volatility, "benchmark volatility")
        labels = pd.Series(index=joined.index, dtype="object")
        valid = volatility.notna()
        labels.loc[valid] = np.where(
            volatility.loc[valid] >= threshold,
            "High volatility",
            "Low volatility",
        )
        thresholds = {
            "rolling_months": 12,
            "annualized_volatility_median": threshold,
        }
    elif regime_type == RegimeType.INFLATION:
        inflation = _year_over_year(cpi, joined.index, "CPI")
        threshold = _finite_median(inflation, "year-over-year inflation")
        change = inflation.diff()
        valid = inflation.notna() & change.notna()
        direction = change >= 0.0
        labels = pd.Series(index=joined.index, dtype="object")
        labels.loc[valid] = np.select(
            [
                (inflation.loc[valid] >= threshold) & direction.loc[valid],
                (inflation.loc[valid] >= threshold) & ~direction.loc[valid],
                (inflation.loc[valid] < threshold) & direction.loc[valid],
            ],
            ["High and rising", "High and falling", "Low and rising"],
            default="Low and falling",
        )
        thresholds = {"sample_median_yoy_inflation": threshold}
        source = FRED_SOURCE
    elif regime_type == RegimeType.BUSINESS_CYCLE:
        inflation = _year_over_year(cpi, joined.index, "CPI")
        growth = _year_over_year(real_gdp, joined.index, "real GDP")
        inflation_threshold = _finite_median(inflation, "year-over-year inflation")
        growth_threshold = _finite_median(growth, "year-over-year real GDP growth")
        valid = growth.notna() & inflation.notna()
        labels = pd.Series(index=joined.index, dtype="object")
        labels.loc[valid] = np.select(
            [
                (growth.loc[valid] >= growth_threshold)
                & (inflation.loc[valid] < inflation_threshold),
                (growth.loc[valid] >= growth_threshold)
                & (inflation.loc[valid] >= inflation_threshold),
                (growth.loc[valid] < growth_threshold)
                & (inflation.loc[valid] >= inflation_threshold),
            ],
            ["Goldilocks", "Reflation", "Stagflation"],
            default="Slowdown",
        )
        thresholds = {
            "sample_median_yoy_real_gdp_growth": growth_threshold,
            "sample_median_yoy_inflation": inflation_threshold,
        }
        source = FRED_SOURCE
    else:
        return {
            "contract_version": PORTFOLIO_ANALYTICS_CONTRACT_VERSION,
            "type": "none",
            "regimes": [],
        }

    joined = joined.copy()
    joined["regime"] = labels
    rows: list[dict[str, Any]] = []
    for label, group in joined.dropna().groupby("regime", sort=False):
        returns = group["portfolio"]
        annualized = float((1.0 + returns).prod() ** (12.0 / len(returns)) - 1.0)
        rows.append(
            {
                "name": str(label),
                "months": int(len(group)),
                "annualized_return": annualized,
                "annualized_volatility": (
                    float(returns.std(ddof=1) * math.sqrt(12))
                    if len(returns) > 1
                    else None
                ),
                "best_month": float(returns.max()),
                "worst_month": float(returns.min()),
                "sample_warning": (
                    "fewer than 12 months" if len(group) < 12 else None
                ),
            }
        )
    return {
        "contract_version": PORTFOLIO_ANALYTICS_CONTRACT_VERSION,
        "type": regime_type.value,
        "source": source,
        "thresholds": thresholds,
        "observations": int(joined["regime"].notna().sum()),
        "regimes": rows,
        "limitations": [
            "Regimes are retrospective classifications, not forecasts.",
            "Months without the required rolling or year-over-year evidence remain unclassified.",
            "Sample-median thresholds adapt to the selected backtest period.",
            "Macroeconomic series are current revised data rather than vintage releases.",
        ],
    }


def inflation_adjusted_metrics(
    ledger: PortfolioLedger,
    cpi: pd.Series,
) -> dict[str, Any]:
    levels = ledger.return_index.astype(float).sort_index()
    monthly_cpi = _clean_macro_series(cpi, "CPI").resample("ME").last()
    daily_cpi = monthly_cpi.reindex(levels.index, method="ffill")
    usable = daily_cpi.notna()
    if usable.sum() < 2:
        raise ValueError("CPI does not cover the backtest period without backward fill")
    nominal = levels.loc[usable]
    daily_cpi = daily_cpi.loc[usable]
    inflation_index = daily_cpi / float(daily_cpi.iloc[0])
    real_index = nominal / inflation_index
    elapsed_years = max(
        (real_index.index[-1] - real_index.index[0]).days / 365.2425,
        1.0 / 365.2425,
    )
    return {
        "contract_version": PORTFOLIO_ANALYTICS_CONTRACT_VERSION,
        "source": FRED_SOURCE,
        "series": "CPIAUCSL",
        "currency_context": "TWD portfolio deflated by U.S. CPI",
        "start": real_index.index[0].date().isoformat(),
        "end": real_index.index[-1].date().isoformat(),
        "cumulative_inflation": float(inflation_index.iloc[-1] - 1.0),
        "real_total_return": float(real_index.iloc[-1] - 1.0),
        "real_cagr": (
            float(real_index.iloc[-1] ** (1.0 / elapsed_years) - 1.0)
            if real_index.iloc[-1] > 0.0
            else -1.0
        ),
        "limitations": [
            "U.S. CPI is not Taiwan CPI and may not represent the investor's actual consumption basket.",
            "Current revised CPI data are used; no vintage reconstruction is performed.",
        ],
    }


def _monthly_compounded(returns: pd.Series) -> pd.Series:
    values = pd.to_numeric(returns, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    values.index = pd.DatetimeIndex(pd.to_datetime(values.index)).tz_localize(None)
    return ((1.0 + values).resample("ME").prod() - 1.0).astype(float)


def _month_end_index(values: pd.Index) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(pd.to_datetime(values))
    if index.tz is not None:
        index = index.tz_localize(None)
    return index.to_period("M").to_timestamp("M")


def _clean_macro_series(values: pd.Series | None, label: str) -> pd.Series:
    if values is None:
        raise ValueError(f"{label} series is required")
    result = pd.to_numeric(values, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    result.index = pd.DatetimeIndex(pd.to_datetime(result.index)).tz_localize(None)
    result = result[~result.index.duplicated(keep="last")].sort_index().astype(float)
    if len(result) < 2:
        raise ValueError(f"{label} has fewer than two usable observations")
    return result


def _year_over_year(
    values: pd.Series | None,
    target_index: pd.DatetimeIndex,
    label: str,
) -> pd.Series:
    series = _clean_macro_series(values, label).resample("ME").last().ffill()
    yoy = series.pct_change(12, fill_method=None) * 100.0
    return yoy.reindex(target_index, method="ffill")


def _finite_median(values: pd.Series, label: str) -> float:
    finite = pd.to_numeric(values, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    if finite.empty:
        raise ValueError(f"{label} has no usable observations")
    return float(finite.median())
