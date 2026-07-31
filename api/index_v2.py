"""Runtime API wrapper that enforces one deterministic metric implementation."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import yfinance as yf

from api import index as legacy
from api.metrics import (
    DATA_SOURCE_SETTINGS,
    METRIC_DEFINITION_VERSION,
    calculate_metrics,
    reproducibility_metadata,
    series_fingerprint,
)

logger = logging.getLogger(__name__)


def bulk_download_prices(tickers, start_date, end_date):
    """Use the same adjusted/repaired daily-price contract as production scan."""
    return yf.download(
        list(tickers),
        start=start_date,
        end=end_date,
        interval=DATA_SOURCE_SETTINGS["interval"],
        auto_adjust=DATA_SOURCE_SETTINGS["auto_adjust"],
        actions=DATA_SOURCE_SETTINGS["actions"],
        repair=DATA_SOURCE_SETTINGS["repair"],
        keepna=DATA_SOURCE_SETTINGS["keepna"],
        progress=False,
        threads=min(legacy.MARKET_DATA_DOWNLOAD_THREADS, max(len(tickers), 1)),
        timeout=legacy.MARKET_DATA_TIMEOUT_SECONDS,
        group_by="column",
        multi_level_index=True,
    )


def run_simulation(portfolio_config, price_data, initial_amount, benchmark_history=None):
    """Simulate static weights with period rebalances effective at prior close."""
    tickers = portfolio_config["tickers"]
    weights = np.asarray(portfolio_config["weights"], dtype=float) / 100.0
    df_prices = price_data[tickers].dropna().astype(float).copy()
    if len(df_prices) < 2:
        return None

    portfolio_history = pd.Series(index=df_prices.index, dtype=float, name="value")
    rebalancing_dates = legacy.get_rebalancing_dates(
        df_prices, portfolio_config["rebalancingPeriod"]
    )
    shares = (initial_amount * weights) / df_prices.iloc[0]
    portfolio_history.iloc[0] = initial_amount

    for position in range(1, len(df_prices)):
        current_date = df_prices.index[position]
        if current_date in rebalancing_dates:
            previous_prices = df_prices.iloc[position - 1]
            previous_value = float((shares * previous_prices).sum())
            shares = (previous_value * weights) / previous_prices
        portfolio_history.iloc[position] = float(
            (shares * df_prices.iloc[position]).sum()
        )

    history_frame = portfolio_history.dropna().to_frame("value")
    metrics = calculate_metrics(
        history_frame,
        benchmark_history,
        risk_free_rate=legacy.RISK_FREE_RATE,
    )
    return {
        "name": portfolio_config["name"],
        **metrics,
        "portfolio_value_fingerprint": series_fingerprint(history_frame),
        "rebalancing_execution": "previous_close_before_period_start",
        "portfolioHistory": [
            {"date": date.strftime("%Y-%m-%d"), "value": float(value)}
            for date, value in history_frame["value"].items()
        ],
    }


def _common_calendar(prices_raw, tickers):
    missing = [
        ticker
        for ticker in tickers
        if ticker not in prices_raw.columns or prices_raw[ticker].dropna().empty
    ]
    if missing:
        raise legacy.DataSourceError(
            "行情資料尚未完整取得：" + ", ".join(missing)
        )
    common = prices_raw[tickers].dropna().astype(float).copy()
    if len(common) < 2:
        raise legacy.ValidationError("沒有足夠的共同交易日來進行可比較回測。")
    return common


def backtest_handler():
    try:
        data = legacy.require_json_object()
        start_date, end_exclusive = legacy.parse_period(data)
        initial_amount = legacy.validate_initial_amount(data.get("initialAmount"))
        default_period = data.get("rebalancingPeriod", "never")
        if default_period not in legacy.ALLOWED_REBALANCING_PERIODS:
            raise legacy.ValidationError("再平衡週期無效。")
        portfolios = legacy.validate_portfolios(data.get("portfolios"), default_period)
        benchmark_ticker = (
            legacy.normalize_ticker(data["benchmark"]) if data.get("benchmark") else None
        )

        portfolio_tickers = legacy.deduplicate(
            ticker for portfolio in portfolios for ticker in portfolio["tickers"]
        )
        required_tickers = legacy.deduplicate(
            portfolio_tickers + ([benchmark_ticker] if benchmark_ticker else [])
        )
        prices_raw = legacy.download_data_silently(
            tuple(sorted(required_tickers)),
            start_date.strftime("%Y-%m-%d"),
            end_exclusive.strftime("%Y-%m-%d"),
        )
        failed_tickers = [
            ticker
            for ticker in required_tickers
            if ticker not in prices_raw.columns
            or prices_raw[ticker].dropna().empty
        ]
        if failed_tickers:
            raise legacy.DataSourceError(
                "行情資料尚未完整取得，未建立部分資料回測："
                + ", ".join(failed_tickers)
            )

        common_prices = _common_calendar(prices_raw, required_tickers)
        effective_start = common_prices.index[0]
        effective_end = common_prices.index[-1]
        warning_parts = []
        if effective_start > start_date + pd.offsets.BDay(5):
            warning_parts.append(
                "為確保所有投組與比較基準使用完全相同期間，"
                f"有效起始日調整為 {effective_start:%Y-%m-%d}"
            )
        if effective_end < end_exclusive - pd.offsets.BDay(5):
            warning_parts.append(f"有效結束日為 {effective_end:%Y-%m-%d}")

        benchmark_history = None
        benchmark_result = None
        if benchmark_ticker:
            benchmark_history = legacy.normalized_benchmark_history(
                common_prices[benchmark_ticker], initial_amount
            )
            benchmark_metrics = calculate_metrics(
                benchmark_history,
                benchmark_history,
                risk_free_rate=legacy.RISK_FREE_RATE,
            )
            benchmark_result = {
                "name": benchmark_ticker,
                **benchmark_metrics,
                "beta": 1.0,
                "alpha": 0.0,
                "portfolio_value_fingerprint": series_fingerprint(benchmark_history),
                "portfolioHistory": [
                    {"date": date.strftime("%Y-%m-%d"), "value": float(value)}
                    for date, value in benchmark_history["value"].items()
                ],
            }

        results = []
        for portfolio in portfolios:
            result = run_simulation(
                portfolio, common_prices, initial_amount, benchmark_history
            )
            if result:
                results.append(result)
        if not results:
            raise legacy.ValidationError("沒有足夠的共同交易日來進行回測。")

        metadata = reproducibility_metadata(
            risk_free_rate=legacy.RISK_FREE_RATE,
            benchmark=benchmark_ticker,
            extra={
                "requested_start": start_date.strftime("%Y-%m-%d"),
                "requested_end_exclusive": end_exclusive.strftime("%Y-%m-%d"),
                "effective_start": effective_start.strftime("%Y-%m-%d"),
                "effective_end": effective_end.strftime("%Y-%m-%d"),
                "common_price_observations": int(len(common_prices)),
                "calendar_policy": "global_complete_case_across_all_assets_and_benchmark",
                "rebalancing_execution": "previous_close_before_period_start",
                "price_fingerprints": {
                    ticker: series_fingerprint(common_prices[ticker])
                    for ticker in required_tickers
                },
            },
        )
        return legacy.jsonify(
            {
                "data": results,
                "benchmark": benchmark_result,
                "warning": "；".join(warning_parts) if warning_parts else None,
                "metadata": metadata,
            }
        )
    except legacy.ValidationError as exc:
        return legacy.error_response(str(exc), 400)
    except legacy.DataSourceError as exc:
        return legacy.error_response(str(exc), 503)
    except ValueError:
        logger.exception("Invalid deterministic metric configuration")
        return legacy.error_response("績效參數設定無效，未產生回測結果。", 500)
    except Exception:
        logger.exception("Unexpected error in deterministic backtest endpoint")
        return legacy.error_response("伺服器發生未預期的錯誤。", 500)


# All legacy endpoints remain available, but the two shared computational hooks
# and the backtest route are replaced before the WSGI app is exported.
legacy.bulk_download_prices = bulk_download_prices
legacy.calculate_metrics = calculate_metrics
legacy.run_simulation = run_simulation
legacy.app.view_functions["backtest_handler"] = backtest_handler
app = legacy.app


@app.after_request
def add_metric_version_header(response):
    response.headers.setdefault("X-Metric-Definition-Version", METRIC_DEFINITION_VERSION)
    return response
