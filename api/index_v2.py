"""Runtime API wrapper that enforces one deterministic metric implementation."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from api import index as legacy
from api import market_data
from api.corporate_actions import (
    CORPORATE_ACTION_POLICY_VERSION,
    RETURN_BASIS,
    audit_from_series,
)
from api.metrics import (
    METRIC_DEFINITION_VERSION,
    calculate_metrics,
    reproducibility_metadata,
    series_fingerprint,
)

logger = logging.getLogger(__name__)


def bulk_download_prices(tickers, start_date, end_date):
    """Fetch explicit Adj Close, raw Close, actions, and repair diagnostics."""
    return market_data.bulk_download_prices(
        tickers,
        start_date,
        end_date,
        timeout_seconds=legacy.MARKET_DATA_TIMEOUT_SECONDS,
        download_threads=legacy.MARKET_DATA_DOWNLOAD_THREADS,
    )


def download_data_reliably(tickers, start_date, end_date):
    return market_data.download_data_reliably(
        tickers,
        start_date,
        end_date,
        attempts=legacy.MARKET_DATA_ATTEMPTS,
        backoff_seconds=legacy.MARKET_DATA_BACKOFF_SECONDS,
        timeout_seconds=legacy.MARKET_DATA_TIMEOUT_SECONDS,
        download_threads=legacy.MARKET_DATA_DOWNLOAD_THREADS,
        batch_size=legacy.MARKET_DATA_BATCH_SIZE,
    )


def download_data_silently(tickers, start_date, end_date):
    prices, _failures = download_data_reliably(tickers, start_date, end_date)
    return prices


def _portfolio_action_status(audits: dict[str, dict]) -> str:
    statuses = {audit.get("status", "audit_not_recorded") for audit in audits.values()}
    if "review_required" in statuses:
        return "review_required"
    if statuses & {"adjusted_close_unverifiable", "insufficient_audit_history"}:
        return "audit_incomplete"
    if statuses and statuses == {"verified_standard_actions"}:
        return "verified_standard_actions"
    return "audit_not_recorded"


def run_simulation(
    portfolio_config,
    price_data,
    initial_amount,
    benchmark_history=None,
    corporate_action_audits=None,
):
    """Simulate weights using explicit adjusted total-return price series."""
    tickers = portfolio_config["tickers"]
    weights = np.asarray(portfolio_config["weights"], dtype=float) / 100.0
    df_prices = price_data[tickers].dropna().astype(float).copy()
    if len(df_prices) < 2:
        return None

    component_audits = {
        ticker: dict(
            (corporate_action_audits or {}).get(
                ticker, audit_from_series(price_data[ticker])
            )
        )
        for ticker in tickers
    }
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
        "return_basis": RETURN_BASIS,
        "corporate_action_policy_version": CORPORATE_ACTION_POLICY_VERSION,
        "corporate_action_status": _portfolio_action_status(component_audits),
        "component_corporate_action_audits": component_audits,
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


def _action_warning(audits: dict[str, dict]) -> str | None:
    review = sorted(
        ticker
        for ticker, audit in audits.items()
        if audit.get("status") == "review_required"
    )
    incomplete = sorted(
        ticker
        for ticker, audit in audits.items()
        if audit.get("status")
        in {"adjusted_close_unverifiable", "insufficient_audit_history"}
    )
    parts = []
    if review:
        parts.append("公司行為調整需人工覆核：" + ", ".join(review))
    if incomplete:
        parts.append("公司行為稽核資料不足：" + ", ".join(incomplete))
    return "；".join(parts) if parts else None


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
        action_audits = dict(
            prices_raw.attrs.get("corporate_action_audits", {})
        )
        for ticker in required_tickers:
            action_audits.setdefault(ticker, audit_from_series(prices_raw.get(ticker)))

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
        action_warning = _action_warning(action_audits)
        if action_warning:
            warning_parts.append(action_warning)
        if benchmark_ticker and benchmark_ticker.startswith("^"):
            warning_parts.append(
                "比較基準為價格指數；Yahoo Adjusted Close 通常不會補入指數成分股股利，"
                "需評估改用可投資 ETF 作為總報酬基準"
            )

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
            benchmark_audit = action_audits[benchmark_ticker]
            benchmark_result = {
                "name": benchmark_ticker,
                **benchmark_metrics,
                "beta": 1.0,
                "alpha": 0.0,
                "return_basis": RETURN_BASIS,
                "corporate_action_policy_version": CORPORATE_ACTION_POLICY_VERSION,
                "corporate_action_status": benchmark_audit.get(
                    "status", "audit_not_recorded"
                ),
                "corporate_action_audit": benchmark_audit,
                "portfolio_value_fingerprint": series_fingerprint(benchmark_history),
                "portfolioHistory": [
                    {"date": date.strftime("%Y-%m-%d"), "value": float(value)}
                    for date, value in benchmark_history["value"].items()
                ],
            }

        results = []
        for portfolio in portfolios:
            result = run_simulation(
                portfolio,
                common_prices,
                initial_amount,
                benchmark_history,
                corporate_action_audits=action_audits,
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
                "market_data_contract_version": market_data.MARKET_DATA_CONTRACT_VERSION,
                "corporate_action_audits": action_audits,
                "corporate_action_review_tickers": sorted(
                    ticker
                    for ticker, audit in action_audits.items()
                    if audit.get("status") == "review_required"
                ),
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


# All legacy endpoints remain available, but every production price hook and
# the backtest route are replaced before the WSGI app is exported.
legacy.bulk_download_prices = bulk_download_prices
legacy.download_data_reliably = download_data_reliably
legacy.download_data_silently = download_data_silently
legacy.calculate_metrics = calculate_metrics
legacy.run_simulation = run_simulation
legacy.app.view_functions["backtest_handler"] = backtest_handler
app = legacy.app


@app.after_request
def add_metric_version_header(response):
    response.headers.setdefault("X-Metric-Definition-Version", METRIC_DEFINITION_VERSION)
    return response
