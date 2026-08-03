"""Production scan endpoint using the shared deterministic metric engine."""

from __future__ import annotations

import logging
import time

import pandas as pd
from flask import Flask, jsonify, request

from api import index as date_contract
from api import market_data
from api import scan as legacy
from api.metrics import DATA_SOURCE_SETTINGS, METRIC_DEFINITION_VERSION
from apps.api.app.scan_service import TWDScanService, TWD_SCAN_CALENDAR_POLICY
from apps.api.app.data.twd_valuation import (
    TWD_VALUATION_CONTRACT_VERSION,
    VALUATION_CURRENCY,
)

app = Flask(__name__)
logger = logging.getLogger(__name__)
twd_scan_service = TWDScanService()

if DATA_SOURCE_SETTINGS["auto_adjust"] or not DATA_SOURCE_SETTINGS["actions"]:
    raise RuntimeError(
        "Production scan requires explicit Adj Close with corporate actions retained"
    )


def bulk_download_prices(tickers, start_date, end_date, *, use_threads=True):
    """Fetch raw/adjusted prices and actions under one explicit contract."""
    return market_data.bulk_download_prices(
        tickers,
        start_date,
        end_date,
        use_threads=use_threads,
        timeout_seconds=legacy.MARKET_DATA_TIMEOUT_SECONDS,
        download_threads=legacy.MARKET_DATA_DOWNLOAD_THREADS,
    )


def download_prices_finitely(tickers, start_date, end_date):
    """Resolve a large batch while retaining each symbol's action audit."""
    return market_data.download_prices_finitely(
        tickers,
        start_date,
        end_date,
        attempts=legacy.MARKET_DATA_ATTEMPTS,
        backoff_seconds=legacy.MARKET_DATA_BACKOFF_SECONDS,
        timeout_seconds=legacy.MARKET_DATA_TIMEOUT_SECONDS,
        download_threads=legacy.MARKET_DATA_DOWNLOAD_THREADS,
        batch_size=legacy.MAX_SCAN_TICKERS,
    )


@app.after_request
def add_headers(response):
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Metric-Definition-Version", METRIC_DEFINITION_VERSION)
    response.headers.setdefault("X-Valuation-Currency", VALUATION_CURRENCY)
    response.headers.setdefault(
        "X-TWD-Valuation-Contract-Version", TWD_VALUATION_CONTRACT_VERSION
    )
    return response


def error_response(message, status):
    return jsonify({"error": message, "retryable": status >= 500}), status


@app.route("/api/scan", methods=["POST"])
def scan_handler():
    request_started = time.perf_counter()
    raw_tickers = []
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise legacy.ValidationError("請提供有效的 JSON 物件。")

        raw_tickers = data.get("tickers")
        if not isinstance(raw_tickers, list) or not raw_tickers:
            raise legacy.ValidationError("股票代碼列表不可為空。")
        tickers = legacy.deduplicate(legacy.normalize_ticker(ticker) for ticker in raw_tickers)
        if not data.get("benchmark"):
            raise legacy.ValidationError("請指定比較基準，以完整計算 Beta 與 Alpha。")

        benchmark_ticker = legacy.normalize_ticker(data["benchmark"])
        start_date, end_exclusive = date_contract.parse_period(data)

        market_started = time.perf_counter()
        batch = twd_scan_service.run(
            tickers,
            start=start_date.date(),
            end=(end_exclusive - pd.Timedelta(days=1)).date(),
            benchmark=benchmark_ticker,
            risk_free_rate=legacy.RISK_FREE_RATE,
        )
        market_duration_ms = (time.perf_counter() - market_started) * 1000
        compute_started = time.perf_counter()
        results = batch.results
        compute_duration_ms = (time.perf_counter() - compute_started) * 1000
        serialize_started = time.perf_counter()
        response = jsonify(results)
        serialize_duration_ms = (time.perf_counter() - serialize_started) * 1000
        total_duration_ms = (time.perf_counter() - request_started) * 1000
        timing_header = ", ".join(
            [
                f"market;dur={market_duration_ms:.1f}",
                f"compute;dur={compute_duration_ms:.1f}",
                f"serialize;dur={serialize_duration_ms:.1f}",
                f"total;dur={total_duration_ms:.1f}",
            ]
        )
        response.headers["Server-Timing"] = timing_header
        response.headers["X-Backend-Server-Timing"] = timing_header
        response.headers["X-Scan-Requested"] = str(len(tickers))
        response.headers["X-Scan-Resolved"] = str(
            sum(1 for item in results if item.get("status") == "ok")
        )
        return response
    except (legacy.ValidationError, date_contract.ValidationError) as exc:
        return error_response(str(exc), 400)
    except ValueError as exc:
        logger.warning("Metric configuration rejected", exc_info=exc)
        return error_response("績效參數設定無效，未產生回測結果。", 500)
    except Exception:
        logger.exception("Unexpected error in deterministic scan endpoint")
        safe_tickers = []
        if isinstance(raw_tickers, list):
            for raw in raw_tickers:
                try:
                    safe_tickers.append(legacy.normalize_ticker(raw))
                except legacy.ValidationError:
                    continue
        if safe_tickers:
            return jsonify(
                [
                    {
                        **legacy.terminal_failure(
                            ticker,
                            "回測服務發生未預期錯誤；本批未產生任何推估數據。",
                        ),
                        "metric_definition_version": METRIC_DEFINITION_VERSION,
                        "valuation_currency": VALUATION_CURRENCY,
                        "twd_valuation_contract_version": (
                            TWD_VALUATION_CONTRACT_VERSION
                        ),
                        "calendar_policy": TWD_SCAN_CALENDAR_POLICY,
                    }
                    for ticker in legacy.deduplicate(safe_tickers)
                ]
            )
        return error_response("伺服器發生未預期的錯誤。", 500)
