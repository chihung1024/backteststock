"""Full-period exhaustive portfolio optimizer snapshot endpoint."""

from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import json
import os
from typing import Any

import numpy as np
import pandas as pd
from flask import Blueprint, Flask, jsonify

from api import index as legacy
from api import market_data
from api.corporate_actions import CORPORATE_ACTION_POLICY_VERSION
from api.metrics import DATA_SOURCE_SETTINGS, METRIC_DEFINITION_VERSION, series_fingerprint
from apps.api.app.backtest_service import (
    TWD_PORTFOLIO_CALENDAR_POLICY,
    align_twd_price_frame,
)
from apps.api.app.data.history_service import TWDHistoryService, normalize_symbol
from apps.api.app.data.twd_valuation import (
    TWD_VALUATION_CONTRACT_VERSION,
    VALUATION_CURRENCY,
)

exhaustive_blueprint = Blueprint("exhaustive_optimizer", __name__)
app = Flask(__name__)

EXHAUSTIVE_OPTIMIZER_VERSION = "exhaustive-full-period-twd-2026-08-03.1"
EXHAUSTIVE_SNAPSHOT_FORMAT = "exhaustive-optimizer-snapshot-json-gzip-v1"
EXHAUSTIVE_REBALANCE_ENGINE = "browser-exact-dynamic-k-v1"
MIN_SOURCE_TICKERS = 2
MINIMUM_PERIOD_COVERAGE = 0.98
MAX_SNAPSHOT_COMPRESSED_BYTES = 5 * 1024 * 1024 // 2
MAX_SNAPSHOT_UNCOMPRESSED_BYTES = 24 * 1024 * 1024
twd_history_service = TWDHistoryService()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _signing_key() -> tuple[bytes, str]:
    secret = os.environ.get("OPTIMIZER_SIGNING_SECRET")
    if secret:
        return secret.encode("utf-8"), "hmac-sha256-secret"
    deployment_key = (
        os.environ.get("VERCEL_GIT_COMMIT_SHA")
        or os.environ.get("VERCEL_DEPLOYMENT_ID")
        or METRIC_DEFINITION_VERSION
    )
    derived = hashlib.sha256(
        f"backteststock-exhaustive-optimizer:{deployment_key}".encode("utf-8")
    ).digest()
    return derived, "hmac-sha256-deployment-key"


def _encode_exhaustive_snapshot(snapshot: dict) -> dict:
    raw = _canonical_json_bytes(snapshot)
    if len(raw) > MAX_SNAPSHOT_UNCOMPRESSED_BYTES:
        raise legacy.ValidationError("全量回測資料快照過大，請縮短期間或減少來源股票。")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    if len(compressed) > MAX_SNAPSHOT_COMPRESSED_BYTES:
        raise legacy.ValidationError("全量回測資料快照過大，請縮短期間或減少來源股票。")
    key, mode = _signing_key()
    signature = hmac.new(key, compressed, hashlib.sha256).hexdigest()
    return {
        "format": EXHAUSTIVE_SNAPSHOT_FORMAT,
        "encoding": "gzip+base64",
        "data": base64.b64encode(compressed).decode("ascii"),
        "compressedBytes": len(compressed),
        "uncompressedBytes": len(raw),
        "datasetHash": hashlib.sha256(raw).hexdigest(),
        "signature": signature,
        "signatureMode": mode,
    }


def _download_full_period_prices(
    tickers: list[str],
    start_text: str,
    end_text: str,
    benchmark: str,
):
    """Build a signed, full-period TWD snapshot from audited source histories."""

    start = pd.Timestamp(start_text).date()
    end = (pd.Timestamp(end_text) - pd.Timedelta(days=1)).date()
    histories = twd_history_service.histories_partial(
        tickers,
        start,
        end,
    )
    failed = [
        ticker
        for ticker in tickers
        if ticker not in histories.histories
    ]
    if failed:
        details = "; ".join(
            f"{ticker}: {histories.failures[ticker].stage} - "
            f"{histories.failures[ticker].detail}"
            for ticker in failed
            if ticker in histories.failures
        )
        raise legacy.DataSourceError(
            "行情資料尚未完整取得，不會靜默移除來源股票："
            + ", ".join(sorted(failed))
            + (f"；{details}" if details else "")
        )

    reference_index = pd.DatetimeIndex([])
    for ticker in tickers:
        reference_index = reference_index.union(
            histories.histories[ticker].adjusted_close_twd.index
        )
    reference_index = reference_index.sort_values().unique()
    if len(reference_index) < 60:
        raise legacy.ValidationError("比較基準交易日不足 60 日。")
    availability_masks = {
        ticker: _availability_mask(
            histories.histories[ticker].adjusted_close_twd,
            reference_index,
        )
        for ticker in tickers
    }
    common = align_twd_price_frame(histories.histories, tickers)
    if len(common) < 60:
        raise legacy.ValidationError("沒有足夠共同交易日建立全量回測快照。")
    audits = {
        ticker: histories.histories[ticker].corporate_action_audit or {}
        for ticker in tickers
    }
    common.attrs["reference_index"] = reference_index
    common.attrs["availability_masks"] = availability_masks
    common.attrs["fx_audits"] = {
        ticker: histories.histories[ticker].fx_audit for ticker in tickers
    }
    common.attrs["native_price_fingerprints"] = {
        ticker: series_fingerprint(histories.histories[ticker].native_adjusted_close)
        for ticker in tickers
    }
    common.attrs["fx_price_fingerprints"] = {
        ticker: series_fingerprint(histories.histories[ticker].fx_to_twd)
        for ticker in tickers
    }
    common.attrs["valuation_currency"] = VALUATION_CURRENCY
    common.attrs["twd_valuation_contract_version"] = TWD_VALUATION_CONTRACT_VERSION
    return common, audits


def _availability_mask(levels: pd.Series, reference_index: pd.DatetimeIndex) -> np.ndarray:
    """Mark each price as available after its first and before its last observation.

    Non-trading days in the global TWD union are deliberately not treated as a
    missing quote: their prior adjusted level is the valid valuation basis.  A
    late listing or early delisting remains visible to the strict full-period
    audit through the first/last true positions in this mask.
    """

    observed = pd.DatetimeIndex(levels.index).intersection(reference_index)
    mask = np.zeros(len(reference_index), dtype=bool)
    if observed.empty:
        return mask
    first = reference_index.get_indexer([observed[0]])[0]
    last = reference_index.get_indexer([observed[-1]])[0]
    if first >= 0 and last >= first:
        mask[first : last + 1] = True
    return mask


def _strict_full_period_coverage(
    common: pd.DataFrame,
    source_tickers: list[str],
    benchmark: str,
    minimum_coverage: float = MINIMUM_PERIOD_COVERAGE,
) -> dict:
    reference_index = pd.DatetimeIndex(common.attrs.get("reference_index", common.index))
    masks = common.attrs.get("availability_masks")
    required = [*source_tickers, benchmark]
    if not isinstance(masks, dict):
        masks = {
            ticker: np.ones(len(reference_index), dtype=bool)
            for ticker in required
        }

    diagnostics: dict[str, dict] = {}
    failures: list[str] = []
    for ticker in required:
        mask = np.asarray(
            masks.get(ticker, np.zeros(len(reference_index), dtype=bool)),
            dtype=bool,
        )
        if len(mask) != len(reference_index):
            raise legacy.ValidationError(f"行情覆蓋稽核長度不一致：{ticker}")
        coverage = float(mask.mean())
        missing = int((~mask).sum())
        first_position = int(np.argmax(mask)) if mask.any() else len(mask)
        last_position = int(len(mask) - 1 - np.argmax(mask[::-1])) if mask.any() else -1
        diagnostics[ticker] = {
            "overall": coverage,
            "missing_days": missing,
            "first_available_position": first_position,
            "last_available_position": last_position,
        }
        if coverage < minimum_coverage:
            failures.append(f"{ticker}(覆蓋 {coverage:.2%}，缺 {missing} 日)")
        if first_position > 5:
            failures.append(f"{ticker}(期初晚 {first_position} 個交易日)")
        if last_position < len(reference_index) - 6:
            gap = len(reference_index) - 1 - last_position
            failures.append(f"{ticker}(期末早 {gap} 個交易日)")

    common_mask = np.logical_and.reduce(
        [np.asarray(masks[ticker], dtype=bool) for ticker in required]
    )
    global_coverage = float(common_mask.mean())
    diagnostics["_global_complete_case"] = {
        "overall": global_coverage,
        "minimum_required": minimum_coverage,
        "reference_observations": len(reference_index),
        "common_observations": int(common_mask.sum()),
    }
    if global_coverage < minimum_coverage:
        failures.append(f"全體共同交易日覆蓋僅 {global_coverage:.2%}")

    common_positions = reference_index.get_indexer(common.index)
    if (
        len(common_positions) == 0
        or common_positions[0] < 0
        or common_positions[-1] < 0
        or common_positions[0] > 5
        or common_positions[-1] < len(reference_index) - 6
    ):
        failures.append("共同期間起訖與比較基準相差超過 5 個交易日")

    if failures:
        raise legacy.ValidationError(
            "全量回測不會靜默移除股票或縮短期間；行情覆蓋不足："
            + "；".join(dict.fromkeys(failures))
        )
    return diagnostics


def _error_response(message: str, status: int):
    return jsonify({"error": message, "retryable": status >= 500}), status


@exhaustive_blueprint.route("/api/optimizer/exhaustive/prepare", methods=["POST"])
def prepare_exhaustive_optimizer():
    try:
        data = legacy.require_json_object()
        start_date, end_exclusive = legacy.parse_period(data)
        raw_tickers = data.get("sourceTickers")
        if not isinstance(raw_tickers, list):
            raise legacy.ValidationError("來源股票必須為股票代碼列表。")
        source_tickers = legacy.deduplicate(
            normalize_symbol(legacy.normalize_ticker(value)) for value in raw_tickers
        )
        if len(source_tickers) < MIN_SOURCE_TICKERS:
            raise legacy.ValidationError(
                f"來源股票至少需要 {MIN_SOURCE_TICKERS} 檔不重複股票。"
            )
        benchmark = normalize_symbol(
            legacy.normalize_ticker(data.get("benchmark") or "SPY")
        )
        if benchmark in source_tickers:
            raise legacy.ValidationError("比較基準不可同時列入來源股票池。")

        required = [*source_tickers, benchmark]
        common, audits = _download_full_period_prices(
            required,
            start_date.strftime("%Y-%m-%d"),
            end_exclusive.strftime("%Y-%m-%d"),
            benchmark,
        )
        coverage = _strict_full_period_coverage(
            common,
            source_tickers,
            benchmark,
        )
        unverified = sorted(
            ticker
            for ticker in required
            if audits[ticker].get("status") != "verified_standard_actions"
        )
        if unverified:
            raise legacy.ValidationError(
                "下列標的未通過標準公司行為稽核，請自行移除或調整期間："
                + ", ".join(unverified)
            )

        snapshot = {
            "formatVersion": EXHAUSTIVE_SNAPSHOT_FORMAT,
            "optimizerMode": "exhaustive_full_period",
            "optimizerAlgorithmVersion": EXHAUSTIVE_OPTIMIZER_VERSION,
            "rebalanceEngineVersion": EXHAUSTIVE_REBALANCE_ENGINE,
            "metricDefinitionVersion": METRIC_DEFINITION_VERSION,
            "marketDataContractVersion": market_data.MARKET_DATA_CONTRACT_VERSION,
            "valuationCurrency": VALUATION_CURRENCY,
            "twdValuationContractVersion": TWD_VALUATION_CONTRACT_VERSION,
            "corporateActionPolicyVersion": CORPORATE_ACTION_POLICY_VERSION,
            "dataSourceSettings": dict(DATA_SOURCE_SETTINGS),
            "candidateTickers": source_tickers,
            "benchmark": benchmark,
            "dates": [date.strftime("%Y-%m-%d") for date in common.index],
            "prices": {
                ticker: [float(value) for value in common[ticker].to_numpy()]
                for ticker in required
            },
            "requestedStart": start_date.strftime("%Y-%m-%d"),
            "requestedEndInclusive": (
                end_exclusive - pd.Timedelta(days=1)
            ).strftime("%Y-%m-%d"),
            "actualStart": common.index[0].strftime("%Y-%m-%d"),
            "actualEnd": common.index[-1].strftime("%Y-%m-%d"),
            "commonCalendarPolicy": TWD_PORTFOLIO_CALENDAR_POLICY,
            "minimumPeriodCoverage": MINIMUM_PERIOD_COVERAGE,
            "dataCoverageAudit": coverage,
            "corporateActionAudits": audits,
            "fxAudits": dict(common.attrs.get("fx_audits", {})),
            "nativePriceFingerprints": dict(
                common.attrs.get("native_price_fingerprints", {})
            ),
            "fxPriceFingerprints": dict(
                common.attrs.get("fx_price_fingerprints", {})
            ),
            "priceFingerprints": {
                ticker: series_fingerprint(common[ticker]) for ticker in required
            },
            "supportedRebalanceModes": [
                "band",
                "monthly",
                "quarterly",
                "annually",
                "never",
            ],
            "persistentDailyPriceDatabase": False,
        }
        envelope = _encode_exhaustive_snapshot(snapshot)
        return jsonify(
            {
                "snapshot": envelope,
                "summary": {
                    "sourceTickers": source_tickers,
                    "sourceTickerCount": len(source_tickers),
                    "benchmark": benchmark,
                    "observations": len(common),
                    "actualStart": snapshot["actualStart"],
                    "actualEnd": snapshot["actualEnd"],
                    "priceFingerprints": snapshot["priceFingerprints"],
                    "nativePriceFingerprints": snapshot["nativePriceFingerprints"],
                    "fxPriceFingerprints": snapshot["fxPriceFingerprints"],
                    "corporateActionStatus": {
                        ticker: audits[ticker].get("status") for ticker in required
                    },
                    "dataCoverageAudit": coverage,
                    "optimizerAlgorithmVersion": EXHAUSTIVE_OPTIMIZER_VERSION,
                    "rebalanceEngineVersion": EXHAUSTIVE_REBALANCE_ENGINE,
                    "valuationCurrency": VALUATION_CURRENCY,
                    "twdValuationContractVersion": TWD_VALUATION_CONTRACT_VERSION,
                    "persistentDailyPriceDatabase": False,
                },
            }
        )
    except legacy.ValidationError as exc:
        return _error_response(str(exc), 400)
    except legacy.DataSourceError as exc:
        return _error_response(str(exc), 503)
    except Exception:
        app.logger.exception("Unexpected exhaustive optimizer prepare error")
        return _error_response("建立全量回測資料快照時發生錯誤。", 500)


app.register_blueprint(exhaustive_blueprint)


@app.after_request
def add_exhaustive_headers(response):
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Exhaustive-Optimizer-Version", EXHAUSTIVE_OPTIMIZER_VERSION)
    response.headers.setdefault("X-Valuation-Currency", VALUATION_CURRENCY)
    response.headers.setdefault(
        "X-TWD-Valuation-Contract-Version", TWD_VALUATION_CONTRACT_VERSION
    )
    return response
