"""Production scan endpoint using the shared deterministic metric engine."""

from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, request

from api import scan as legacy
from api.metrics import (
    DATA_SOURCE_SETTINGS,
    METRIC_DEFINITION_VERSION,
    aligned_fingerprint,
    benchmark_coverage,
    calculate_metrics,
    reproducibility_metadata,
    series_fingerprint,
)

app = Flask(__name__)
logger = logging.getLogger(__name__)


def bulk_download_prices(tickers, start_date, end_date, *, use_threads=True):
    """Fetch one deterministic adjusted daily price shape for every API path."""
    thread_count = min(legacy.MARKET_DATA_DOWNLOAD_THREADS, max(len(tickers), 1))
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
        threads=thread_count if use_threads else False,
        timeout=legacy.MARKET_DATA_TIMEOUT_SECONDS,
        group_by="column",
        multi_level_index=True,
    )


# Reuse the established finite retry/cache implementation, but force identical
# download semantics to the portfolio endpoint.
legacy.bulk_download_prices = bulk_download_prices


@app.after_request
def add_headers(response):
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Metric-Definition-Version", METRIC_DEFINITION_VERSION)
    return response


def error_response(message, status):
    return jsonify({"error": message, "retryable": status >= 500}), status


def reproducibility_note(metadata: dict, asset_hash: str | None, paired_hash: str | None):
    settings = metadata["data_source_settings"]
    return ";".join(
        [
            f"metric={metadata['metric_definition_version']}",
            f"source=yfinance-{metadata['data_source_version']}",
            f"adjust={str(settings['auto_adjust']).lower()}",
            f"repair={str(settings['repair']).lower()}",
            f"rf={metadata['risk_free_rate']:.12g}",
            f"benchmark={metadata.get('benchmark', '')}",
            f"asset_sha256={asset_hash or ''}",
            f"aligned_sha256={paired_hash or ''}",
        ]
    )


@app.route("/api/scan", methods=["POST"])
def scan_handler():
    raw_tickers = []
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise legacy.ValidationError("請提供有效的 JSON 物件。")

        raw_tickers = data.get("tickers")
        if not isinstance(raw_tickers, list) or not raw_tickers:
            raise legacy.ValidationError("股票代碼列表不可為空。")
        tickers = legacy.deduplicate(legacy.normalize_ticker(ticker) for ticker in raw_tickers)
        if len(tickers) > legacy.MAX_SCAN_TICKERS:
            raise legacy.ValidationError(f"單次最多掃描 {legacy.MAX_SCAN_TICKERS} 檔標的。")
        if not data.get("benchmark"):
            raise legacy.ValidationError("請指定比較基準，以完整計算 Beta 與 Alpha。")

        benchmark_ticker = legacy.normalize_ticker(data["benchmark"])
        start_date, end_exclusive = legacy.parse_period(data)
        start_text = start_date.strftime("%Y-%m-%d")
        end_text = end_exclusive.strftime("%Y-%m-%d")
        resolved, unresolved = legacy.download_prices_finitely(
            legacy.deduplicate([*tickers, benchmark_ticker]),
            start_text,
            end_text,
        )
        unresolved_set = set(unresolved)
        benchmark_prices = resolved.get(benchmark_ticker)
        if (
            benchmark_ticker in unresolved_set
            or benchmark_prices is None
            or benchmark_prices.empty
        ):
            return error_response(
                "比較基準行情未完整取得；本批不產生可能失真的 Beta／Alpha，請稍後重試。",
                503,
            )

        shared_metadata = reproducibility_metadata(
            risk_free_rate=legacy.RISK_FREE_RATE,
            benchmark=benchmark_ticker,
            extra={
                "requested_start": start_text,
                "requested_end_exclusive": end_text,
                "benchmark_price_fingerprint": series_fingerprint(benchmark_prices),
            },
        )
        results = []
        for ticker in tickers:
            prices = resolved.get(ticker)
            if ticker in unresolved_set or prices is None or prices.empty:
                failure = legacy.terminal_failure(ticker)
                failure.update(
                    metric_definition_version=METRIC_DEFINITION_VERSION,
                    benchmark=benchmark_ticker,
                )
                results.append(failure)
                continue

            metrics = calculate_metrics(
                prices,
                benchmark_prices,
                risk_free_rate=legacy.RISK_FREE_RATE,
            )
            asset_hash = series_fingerprint(prices)
            paired_hash = aligned_fingerprint(prices, benchmark_prices)
            notes = []
            if prices.index[0] > start_date + pd.offsets.BDay(5):
                notes.append(f"從 {prices.index[0].strftime('%Y-%m-%d')} 開始")

            row_metadata = {
                **shared_metadata,
                "price_fingerprint": asset_hash,
                "aligned_price_fingerprint": paired_hash,
            }
            reproducibility = reproducibility_note(
                row_metadata, asset_hash, paired_hash
            )
            notes.append(f"再現資訊 {reproducibility}")
            results.append(
                {
                    "ticker": ticker,
                    "status": "ok",
                    "retryable": False,
                    **metrics,
                    "data_start": prices.index[0].strftime("%Y-%m-%d"),
                    "data_end": prices.index[-1].strftime("%Y-%m-%d"),
                    "trading_days": len(prices),
                    "data_coverage": benchmark_coverage(prices, benchmark_prices),
                    "note": f"（{'；'.join(notes)}）",
                    **row_metadata,
                    "reproducibility": reproducibility,
                }
            )
        return jsonify(results)
    except legacy.ValidationError as exc:
        return error_response(str(exc), 400)
    except ValueError as exc:
        logger.warning("Metric configuration rejected", exc_info=exc)
        return error_response("績效參數設定無效，未產生回測結果。", 500)
    except Exception:
        logger.exception("Unexpected error in deterministic scan endpoint")
        safe_tickers = []
        if isinstance(raw_tickers, list):
            for raw in raw_tickers[: legacy.MAX_SCAN_TICKERS]:
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
                    }
                    for ticker in legacy.deduplicate(safe_tickers)
                ]
            )
        return error_response("伺服器發生未預期的錯誤。", 500)
