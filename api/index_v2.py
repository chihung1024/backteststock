"""Runtime API wrapper that enforces one deterministic metric implementation."""

from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd

from api import date_policy
from api import index as legacy
from api import market_data
from api.corporate_actions import (
    CORPORATE_ACTION_POLICY_VERSION,
    RETURN_BASIS,
    audit_from_series,
)
from api.metrics import (
    DATA_SOURCE_SETTINGS,
    METRIC_DEFINITION_VERSION,
    calculate_metrics,
    reproducibility_metadata,
    series_fingerprint,
)
from apps.api.app.backtest_service import (
    PortfolioFailure,
    PortfolioSpec,
    TWDPortfolioBacktestService,
    TWD_PORTFOLIO_CALENDAR_POLICY,
)
from apps.api.app.data.twd_valuation import (
    TWD_VALUATION_CONTRACT_VERSION,
    VALUATION_CURRENCY,
)

logger = logging.getLogger(__name__)
twd_backtest_service = TWDPortfolioBacktestService()
BACKTEST_RETURN_SEMANTICS = "gross_before_transaction_costs"
BACKTEST_COST_ASSUMPTIONS = {
    "transactionCostsIncluded": False,
    "transactionCostBps": None,
    "slippageIncluded": False,
    "taxesIncluded": False,
}
BACKTEST_GROSS_WARNING = "回測績效為 Gross，未計交易成本、滑價與稅負。"

if DATA_SOURCE_SETTINGS["auto_adjust"] or not DATA_SOURCE_SETTINGS["actions"]:
    raise RuntimeError(
        "Production backtest requires explicit Adj Close with corporate actions retained"
    )


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


def _serialize_twd_failure(failure: PortfolioFailure) -> dict:
    return {
        "name": failure.name,
        "stage": failure.stage,
        "detail": failure.detail,
        "symbols": list(failure.symbols),
        "retryable": failure.retryable,
    }


def _twd_failure_warning(failures: list[PortfolioFailure]) -> str | None:
    if not failures:
        return None
    items = [
        f"{failure.name}（{', '.join(failure.symbols)}：{failure.detail}）"
        for failure in failures
    ]
    return "以下投組未產生結果，但其他投組已保留：" + "；".join(items)


def _return_semantics_payload() -> dict:
    return {
        "basis": BACKTEST_RETURN_SEMANTICS,
        **BACKTEST_COST_ASSUMPTIONS,
    }


def backtest_handler():
    request_started = time.perf_counter()
    try:
        data = legacy.require_json_object()
        start_date, end_exclusive = legacy.parse_period(data)
        period = date_policy.require_complete_period(start_date, end_exclusive)
        start_date = period.start
        end_exclusive = period.end_exclusive
        initial_amount = legacy.validate_initial_amount(data.get("initialAmount"))
        default_period = data.get("rebalancingPeriod", "never")
        if default_period not in legacy.ALLOWED_REBALANCING_PERIODS:
            raise legacy.ValidationError("再平衡週期無效。")
        portfolios = legacy.validate_portfolios(data.get("portfolios"), default_period)
        benchmark_ticker = (
            legacy.normalize_ticker(data["benchmark"]) if data.get("benchmark") else None
        )
        specs = [
            PortfolioSpec(
                name=portfolio["name"],
                tickers=tuple(portfolio["tickers"]),
                weights=tuple(float(weight) / 100.0 for weight in portfolio["weights"]),
                rebalancing_period=portfolio["rebalancingPeriod"],
            )
            for portfolio in portfolios
        ]
        market_started = time.perf_counter()
        batch = twd_backtest_service.run(
            specs,
            start=start_date.date(),
            end=(end_exclusive - pd.Timedelta(days=1)).date(),
            initial_amount=initial_amount,
            benchmark=benchmark_ticker,
            risk_free_rate=legacy.RISK_FREE_RATE,
        )
        market_ms = (time.perf_counter() - market_started) * 1000
        compute_started = time.perf_counter()
        if not batch.results:
            details = "; ".join(
                f"{failure.name}: {failure.detail}" for failure in batch.failures
            )
            raise legacy.DataSourceError(
                "沒有可完成的 TWD 回測投組。" + (f" {details}" if details else "")
            )

        warning_parts = [BACKTEST_GROSS_WARNING]
        portfolio_failure_warning = _twd_failure_warning(batch.failures)
        if portfolio_failure_warning:
            warning_parts.append(portfolio_failure_warning)
        if benchmark_ticker and batch.benchmark is None:
            detail = (
                batch.benchmark_failure.detail
                if batch.benchmark_failure is not None
                else "比較基準未取得可用 TWD 歷史"
            )
            warning_parts.append(
                f"比較基準 {benchmark_ticker} 無法以 TWD 計價；"
                f"成功投組仍已計算，但 Beta／Alpha 暫不計算：{detail}"
            )
        action_audits = {
            ticker: history.corporate_action_audit or {}
            for ticker, history in batch.histories.histories.items()
        }
        action_warning = _action_warning(action_audits)
        if action_warning:
            warning_parts.append(action_warning)
        if benchmark_ticker and benchmark_ticker.startswith("^"):
            warning_parts.append(
                "比較基準為價格指數；Yahoo Adjusted Close 通常不會補入指數成分股股利，"
                "需評估改用可投資 ETF 作為總報酬基準"
            )

        metadata = reproducibility_metadata(
            risk_free_rate=legacy.RISK_FREE_RATE,
            benchmark=benchmark_ticker,
            extra={
                "requested_start": start_date.strftime("%Y-%m-%d"),
                "requested_end_exclusive": end_exclusive.strftime("%Y-%m-%d"),
                "as_of_date": period.as_of_date.isoformat(),
                "as_of_policy": period.as_of_policy,
                "incomplete_current_bar_excluded": (
                    period.incomplete_current_bar_excluded
                ),
                "valuation_currency": VALUATION_CURRENCY,
                "twd_valuation_contract_version": TWD_VALUATION_CONTRACT_VERSION,
                "calendar_policy": TWD_PORTFOLIO_CALENDAR_POLICY,
                "market_data_contract_version": market_data.MARKET_DATA_CONTRACT_VERSION,
                "return_semantics": BACKTEST_RETURN_SEMANTICS,
                "transaction_costs_included": False,
                "transaction_cost_bps": None,
                "slippage_included": False,
                "taxes_included": False,
                "requested_tickers": list(batch.requested),
                "resolved_tickers": list(batch.histories.histories),
                "corporate_action_audits": action_audits,
                "corporate_action_review_tickers": sorted(
                    ticker
                    for ticker, audit in action_audits.items()
                    if audit.get("status") == "review_required"
                ),
                "twd_price_fingerprints": {
                    ticker: series_fingerprint(history.adjusted_close_twd)
                    for ticker, history in batch.histories.histories.items()
                },
                "twd_history_failures": {
                    ticker: {
                        "stage": failure.stage,
                        "detail": failure.detail,
                        "retryable": failure.retryable,
                    }
                    for ticker, failure in batch.histories.failures.items()
                },
                "portfolio_effective_periods": {
                    result["name"]: {
                        "start": result.get("metric_start"),
                        "end": result.get("metric_end"),
                        "observations": result.get("metric_price_observations"),
                    }
                    for result in batch.results
                },
            },
        )
        payload = {
            "data": batch.results,
            "benchmark": batch.benchmark,
            "warning": "；".join(warning_parts),
            "failures": [_serialize_twd_failure(failure) for failure in batch.failures],
            "metadata": metadata,
            "returnSemantics": _return_semantics_payload(),
        }
        compute_ms = (time.perf_counter() - compute_started) * 1000
        serialize_started = time.perf_counter()
        response = legacy.jsonify(payload)
        serialize_ms = (time.perf_counter() - serialize_started) * 1000
        total_ms = (time.perf_counter() - request_started) * 1000
        timing = (
            f"market;dur={market_ms:.1f}, compute;dur={compute_ms:.1f}, "
            f"serialize;dur={serialize_ms:.1f}, total;dur={total_ms:.1f}"
        )
        response.headers["Server-Timing"] = timing
        response.headers["X-Backend-Server-Timing"] = timing
        response.headers["X-Backtest-Requested"] = str(len(batch.requested))
        response.headers["X-Backtest-Resolved"] = str(len(batch.histories.histories))
        response.headers["X-As-Of-Date"] = period.as_of_date.isoformat()
        response.headers["X-As-Of-Policy"] = period.as_of_policy
        return response
    except (legacy.ValidationError, date_policy.DatePolicyError) as exc:
        return legacy.error_response(str(exc), 400)
    except legacy.DataSourceError as exc:
        return legacy.error_response(str(exc), 503)
    except ValueError:
        logger.exception("Invalid deterministic metric configuration")
        return legacy.error_response("績效參數設定無效，未產生回測結果。", 500)
    except Exception:
        logger.exception("Unexpected error in deterministic backtest endpoint")
        return legacy.error_response("伺服器發生未預期的錯誤。", 500)


# Reuse the legacy Flask app and auxiliary routes, but replace only the
# production backtest route.  Do not mutate legacy market-data functions;
# unit tests and legacy endpoints retain their own isolated behavior.
legacy.app.view_functions["backtest_handler"] = backtest_handler
app = legacy.app


@app.after_request
def add_metric_version_header(response):
    response.headers.setdefault("X-Metric-Definition-Version", METRIC_DEFINITION_VERSION)
    response.headers.setdefault("X-Valuation-Currency", VALUATION_CURRENCY)
    response.headers.setdefault(
        "X-TWD-Valuation-Contract-Version", TWD_VALUATION_CONTRACT_VERSION
    )
    return response
