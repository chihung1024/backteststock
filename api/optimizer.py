"""Deterministic candidate-pool portfolio optimizer endpoints."""

from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import json
import math
import os
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request

from api import index as legacy
from api import market_data
from api.corporate_actions import CORPORATE_ACTION_POLICY_VERSION, audit_from_series
from api.metrics import (
    DATA_SOURCE_SETTINGS,
    METRIC_DEFINITION_VERSION,
    calculate_metrics,
    reproducibility_metadata,
    series_fingerprint,
)

app = Flask(__name__)

OPTIMIZER_ALGORITHM_VERSION = "optimizer-mvp-2026-08-01.1"
REBALANCE_ENGINE_VERSION = "relative-band-next-close-v1"
SNAPSHOT_FORMAT_VERSION = "optimizer-snapshot-json-gzip-v1"
DEFAULT_TRAINING_RATIO = 0.70
CANDIDATE_COUNT = 20
HOLDING_COUNT = 10
MAX_VERIFY_COMBINATIONS = 300
MAX_SNAPSHOT_COMPRESSED_BYTES = 2 * 1024 * 1024
MAX_SNAPSHOT_UNCOMPRESSED_BYTES = 12 * 1024 * 1024


@app.after_request
def add_headers(response):
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault(
        "X-Metric-Definition-Version", METRIC_DEFINITION_VERSION
    )
    response.headers.setdefault(
        "X-Optimizer-Algorithm-Version", OPTIMIZER_ALGORITHM_VERSION
    )
    return response


def error_response(message: str, status: int):
    return jsonify({"error": message, "retryable": status >= 500}), status


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
        f"backteststock-optimizer:{deployment_key}".encode("utf-8")
    ).digest()
    return derived, "hmac-sha256-deployment-key"


def _sign_payload(payload: bytes) -> tuple[str, str]:
    key, mode = _signing_key()
    return hmac.new(key, payload, hashlib.sha256).hexdigest(), mode


def _encode_snapshot(snapshot: dict) -> dict:
    raw = _canonical_json_bytes(snapshot)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    if len(compressed) > MAX_SNAPSHOT_COMPRESSED_BYTES:
        raise legacy.ValidationError("最佳化資料快照過大，請縮短期間或候選池。")
    signature, mode = _sign_payload(compressed)
    return {
        "format": SNAPSHOT_FORMAT_VERSION,
        "encoding": "gzip+base64",
        "data": base64.b64encode(compressed).decode("ascii"),
        "compressedBytes": len(compressed),
        "uncompressedBytes": len(raw),
        "datasetHash": hashlib.sha256(raw).hexdigest(),
        "signature": signature,
        "signatureMode": mode,
    }


def _decode_snapshot(envelope: dict) -> dict:
    if not isinstance(envelope, dict):
        raise legacy.ValidationError("缺少最佳化資料快照。")
    if envelope.get("format") != SNAPSHOT_FORMAT_VERSION:
        raise legacy.ValidationError("最佳化資料快照版本不相容。")
    if envelope.get("encoding") != "gzip+base64":
        raise legacy.ValidationError("最佳化資料快照編碼不相容。")
    try:
        compressed = base64.b64decode(envelope["data"], validate=True)
    except (KeyError, ValueError) as exc:
        raise legacy.ValidationError("最佳化資料快照內容無效。") from exc
    if len(compressed) > MAX_SNAPSHOT_COMPRESSED_BYTES:
        raise legacy.ValidationError("最佳化資料快照超過允許大小。")
    expected_signature, _mode = _sign_payload(compressed)
    if not hmac.compare_digest(
        str(envelope.get("signature") or ""), expected_signature
    ):
        raise legacy.ValidationError("最佳化資料快照簽章驗證失敗。")
    try:
        raw = gzip.decompress(compressed)
    except (OSError, EOFError) as exc:
        raise legacy.ValidationError("最佳化資料快照無法解壓縮。") from exc
    if len(raw) > MAX_SNAPSHOT_UNCOMPRESSED_BYTES:
        raise legacy.ValidationError("最佳化資料快照解壓縮後過大。")
    if hashlib.sha256(raw).hexdigest() != envelope.get("datasetHash"):
        raise legacy.ValidationError("最佳化資料快照雜湊不一致。")
    try:
        snapshot = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise legacy.ValidationError("最佳化資料快照不是有效 JSON。") from exc
    if not isinstance(snapshot, dict):
        raise legacy.ValidationError("最佳化資料快照結構無效。")
    return snapshot


def _parse_ratio(value, *, label: str, default: float) -> float:
    try:
        numeric = float(default if value is None else value)
    except (TypeError, ValueError) as exc:
        raise legacy.ValidationError(f"{label}格式不正確。") from exc
    if not math.isfinite(numeric) or not 0 < numeric < 1:
        raise legacy.ValidationError(f"{label}必須介於 0 與 1 之間。")
    return numeric


def _split_dates(index: pd.DatetimeIndex, training_ratio: float) -> dict:
    if len(index) < 60:
        raise legacy.ValidationError("共同交易日不足 60 日，無法切分訓練與樣本外期間。")
    split_index = int(math.floor(len(index) * training_ratio))
    split_index = min(max(split_index, 30), len(index) - 20)
    return {
        "trainingStart": index[0].strftime("%Y-%m-%d"),
        "trainingEnd": index[split_index - 1].strftime("%Y-%m-%d"),
        "validationStart": index[split_index].strftime("%Y-%m-%d"),
        "validationEnd": index[-1].strftime("%Y-%m-%d"),
        "trainingObservations": split_index,
        "validationObservations": len(index) - split_index,
        "splitIndex": split_index,
        "splitRule": "floor(common_trading_days*training_ratio)",
    }


def _download_common_prices(tickers: list[str], start_text: str, end_text: str):
    prices, failures = market_data.download_data_reliably(
        tickers,
        start_text,
        end_text,
        attempts=legacy.MARKET_DATA_ATTEMPTS,
        backoff_seconds=legacy.MARKET_DATA_BACKOFF_SECONDS,
        timeout_seconds=legacy.MARKET_DATA_TIMEOUT_SECONDS,
        download_threads=legacy.MARKET_DATA_DOWNLOAD_THREADS,
        batch_size=legacy.MARKET_DATA_BATCH_SIZE,
    )
    failed = [
        ticker
        for ticker in tickers
        if ticker in failures
        or ticker not in prices.columns
        or prices[ticker].dropna().empty
    ]
    if failed:
        raise legacy.DataSourceError(
            "行情資料尚未完整取得：" + ", ".join(sorted(failed))
        )
    common = prices[tickers].dropna().astype(float)
    if len(common) < 60:
        raise legacy.ValidationError("沒有足夠共同交易日建立最佳化資料。")
    audits = dict(prices.attrs.get("corporate_action_audits", {}))
    for ticker in tickers:
        audits.setdefault(ticker, audit_from_series(prices[ticker]))
    return common, audits


@app.route("/api/optimizer/calendar", methods=["POST"])
def optimizer_calendar():
    try:
        data = legacy.require_json_object()
        start_date, end_exclusive = legacy.parse_period(data)
        benchmark = legacy.normalize_ticker(data.get("benchmark") or "SPY")
        ratio = _parse_ratio(
            data.get("trainingRatio"),
            label="訓練期比例",
            default=DEFAULT_TRAINING_RATIO,
        )
        common, audits = _download_common_prices(
            [benchmark],
            start_date.strftime("%Y-%m-%d"),
            end_exclusive.strftime("%Y-%m-%d"),
        )
        split = _split_dates(common.index, ratio)
        return jsonify(
            {
                **split,
                "benchmark": benchmark,
                "benchmarkFingerprint": series_fingerprint(common[benchmark]),
                "benchmarkCorporateActionAudit": audits[benchmark],
                "trainingRatio": ratio,
                "requestedStart": start_date.strftime("%Y-%m-%d"),
                "requestedEndInclusive": (
                    end_exclusive - pd.Timedelta(days=1)
                ).strftime("%Y-%m-%d"),
                "optimizerAlgorithmVersion": OPTIMIZER_ALGORITHM_VERSION,
                "metricDefinitionVersion": METRIC_DEFINITION_VERSION,
            }
        )
    except legacy.ValidationError as exc:
        return error_response(str(exc), 400)
    except legacy.DataSourceError as exc:
        return error_response(str(exc), 503)
    except Exception:
        app.logger.exception("Unexpected optimizer calendar error")
        return error_response("建立訓練與樣本外期間時發生錯誤。", 500)


@app.route("/api/optimizer/prepare", methods=["POST"])
def optimizer_prepare():
    try:
        data = legacy.require_json_object()
        start_date, end_exclusive = legacy.parse_period(data)
        raw_candidates = data.get("candidateTickers")
        if not isinstance(raw_candidates, list):
            raise legacy.ValidationError("候選池必須為股票代碼列表。")
        candidates = legacy.deduplicate(
            legacy.normalize_ticker(value) for value in raw_candidates
        )
        if len(candidates) != CANDIDATE_COUNT:
            raise legacy.ValidationError(
                f"候選池必須正好包含 {CANDIDATE_COUNT} 檔不重複股票。"
            )
        benchmark = legacy.normalize_ticker(data.get("benchmark") or "SPY")
        if benchmark in candidates:
            raise legacy.ValidationError("比較基準不可同時作為候選股。")
        ratio = _parse_ratio(
            data.get("trainingRatio"),
            label="訓練期比例",
            default=DEFAULT_TRAINING_RATIO,
        )
        requested_training_end = data.get("trainingEnd")
        required = [*candidates, benchmark]
        common, audits = _download_common_prices(
            required,
            start_date.strftime("%Y-%m-%d"),
            end_exclusive.strftime("%Y-%m-%d"),
        )
        if requested_training_end:
            training_end = legacy._parse_iso_date(
                requested_training_end, "訓練期結束日期"
            )
            training_count = int((common.index <= training_end).sum())
            if training_count < 30 or len(common) - training_count < 20:
                raise legacy.ValidationError(
                    "指定訓練期切割後，訓練或樣本外共同交易日不足。"
                )
            split = {
                "trainingStart": common.index[0].strftime("%Y-%m-%d"),
                "trainingEnd": common.index[training_count - 1].strftime("%Y-%m-%d"),
                "validationStart": common.index[training_count].strftime("%Y-%m-%d"),
                "validationEnd": common.index[-1].strftime("%Y-%m-%d"),
                "trainingObservations": training_count,
                "validationObservations": len(common) - training_count,
                "splitIndex": training_count,
                "splitRule": "explicit_training_end_on_common_calendar",
            }
        else:
            split = _split_dates(common.index, ratio)

        review = sorted(
            ticker
            for ticker in required
            if audits[ticker].get("status") != "verified_standard_actions"
        )
        if review:
            raise legacy.ValidationError(
                "下列標的未通過標準公司行為稽核，不能進入嚴格最佳化："
                + ", ".join(review)
            )

        snapshot = {
            "formatVersion": SNAPSHOT_FORMAT_VERSION,
            "optimizerAlgorithmVersion": OPTIMIZER_ALGORITHM_VERSION,
            "metricDefinitionVersion": METRIC_DEFINITION_VERSION,
            "marketDataContractVersion": market_data.MARKET_DATA_CONTRACT_VERSION,
            "corporateActionPolicyVersion": CORPORATE_ACTION_POLICY_VERSION,
            "dataSourceSettings": dict(DATA_SOURCE_SETTINGS),
            "candidateTickers": candidates,
            "benchmark": benchmark,
            "dates": [date.strftime("%Y-%m-%d") for date in common.index],
            "prices": {
                ticker: [float(value) for value in common[ticker].to_numpy()]
                for ticker in required
            },
            "split": split,
            "trainingRatio": ratio,
            "corporateActionAudits": audits,
            "priceFingerprints": {
                ticker: series_fingerprint(common[ticker]) for ticker in required
            },
            "requestedStart": start_date.strftime("%Y-%m-%d"),
            "requestedEndInclusive": (
                end_exclusive - pd.Timedelta(days=1)
            ).strftime("%Y-%m-%d"),
            "commonCalendarPolicy": "global_complete_case_candidates_and_benchmark",
            "candidateSelection": data.get("candidateSelection") or {},
        }
        envelope = _encode_snapshot(snapshot)
        return jsonify(
            {
                "snapshot": envelope,
                "summary": {
                    "candidateTickers": candidates,
                    "benchmark": benchmark,
                    "observations": len(common),
                    "split": split,
                    "priceFingerprints": snapshot["priceFingerprints"],
                    "corporateActionStatus": {
                        ticker: audits[ticker].get("status") for ticker in required
                    },
                    "optimizerAlgorithmVersion": OPTIMIZER_ALGORITHM_VERSION,
                    "rebalanceEngineVersion": REBALANCE_ENGINE_VERSION,
                },
            }
        )
    except legacy.ValidationError as exc:
        return error_response(str(exc), 400)
    except legacy.DataSourceError as exc:
        return error_response(str(exc), 503)
    except Exception:
        app.logger.exception("Unexpected optimizer prepare error")
        return error_response("建立最佳化資料快照時發生錯誤。", 500)


@dataclass
class SimulationResult:
    history: pd.DataFrame
    turnover_gross: float
    turnover_one_way: float
    annualized_turnover_one_way: float
    transaction_cost: float
    rebalance_count: int
    events: list[dict]
    pending_signal: dict | None
    initial_trade_cost: float


def _post_cost_target_nav(
    pre_values: np.ndarray,
    cash: float,
    weights: np.ndarray,
    cost_rate: float,
) -> tuple[float, float, float]:
    pre_nav = float(pre_values.sum() + cash)
    if pre_nav <= 0:
        raise legacy.ValidationError("投組淨值小於或等於 0，無法再平衡。")
    target_nav = pre_nav
    for _ in range(40):
        target_values = target_nav * weights
        gross = float(np.abs(target_values - pre_values).sum())
        updated = pre_nav - gross * cost_rate
        if updated <= 0:
            raise legacy.ValidationError("交易成本使投組淨值歸零。")
        if abs(updated - target_nav) <= 1e-10 * max(pre_nav, 1.0):
            target_nav = updated
            break
        target_nav = updated
    target_values = target_nav * weights
    gross = float(np.abs(target_values - pre_values).sum())
    cost = gross * cost_rate
    return target_nav, gross, cost


def _simulate_band(
    prices: np.ndarray,
    dates: pd.DatetimeIndex,
    *,
    band_ratio: float,
    transaction_cost_bps: float,
    initial_amount: float = 10_000.0,
) -> SimulationResult:
    if prices.ndim != 2 or prices.shape[1] != HOLDING_COUNT:
        raise legacy.ValidationError(
            f"精確複驗投組必須包含 {HOLDING_COUNT} 檔股票。"
        )
    if prices.shape[0] != len(dates) or len(dates) < 2:
        raise legacy.ValidationError("精確複驗期間資料不足。")
    if not np.isfinite(prices).all() or np.any(prices <= 0):
        raise legacy.ValidationError("精確複驗價格包含無效值。")

    weights = np.full(HOLDING_COUNT, 1.0 / HOLDING_COUNT, dtype=float)
    lower = weights * (1.0 - band_ratio)
    upper = weights * (1.0 + band_ratio)
    cost_rate = transaction_cost_bps / 10_000.0
    shares = np.zeros(HOLDING_COUNT, dtype=float)
    cash = float(initial_amount)
    values = np.empty(len(dates), dtype=float)
    events: list[dict] = []
    pending: dict | None = None
    total_gross = 0.0
    total_cost = 0.0

    initial_pre_values = np.zeros(HOLDING_COUNT, dtype=float)
    target_nav, gross, initial_cost = _post_cost_target_nav(
        initial_pre_values, cash, weights, cost_rate
    )
    shares = (target_nav * weights) / prices[0]
    cash = target_nav - float((shares * prices[0]).sum())
    values[0] = target_nav
    total_gross += gross
    total_cost += initial_cost

    for position in range(1, len(dates)):
        current_prices = prices[position]
        pre_values = shares * current_prices
        pre_nav = float(pre_values.sum() + cash)
        executed = False

        if pending is not None:
            target_nav, gross, cost = _post_cost_target_nav(
                pre_values, cash, weights, cost_rate
            )
            shares = (target_nav * weights) / current_prices
            cash = target_nav - float((shares * current_prices).sum())
            values[position] = target_nav
            total_gross += gross
            total_cost += cost
            events.append(
                {
                    "signalDate": pending["signalDate"],
                    "executionDate": dates[position].strftime("%Y-%m-%d"),
                    "triggerIndexes": pending["triggerIndexes"],
                    "grossTradedNotional": gross,
                    "oneWayTurnover": gross / (2 * pre_nav) if pre_nav > 0 else 0.0,
                    "transactionCost": cost,
                    "preTradeNav": pre_nav,
                    "postTradeNav": target_nav,
                }
            )
            pending = None
            executed = True
        else:
            values[position] = pre_nav

        if not executed:
            current_weights = pre_values / pre_nav
            trigger_indexes = np.flatnonzero(
                (current_weights < lower) | (current_weights > upper)
            )
            if trigger_indexes.size:
                pending = {
                    "signalDate": dates[position].strftime("%Y-%m-%d"),
                    "triggerIndexes": [int(value) for value in trigger_indexes],
                    "weights": [float(value) for value in current_weights],
                }

    elapsed_years = max(
        float((dates[-1] - dates[0]).days) / 365.25,
        1 / 365.25,
    )
    rebalance_gross = max(total_gross - initial_amount + initial_cost, 0.0)
    average_nav = float(np.mean(values))
    one_way = rebalance_gross / (2 * average_nav) if average_nav > 0 else 0.0
    return SimulationResult(
        history=pd.DataFrame({"value": values}, index=dates),
        turnover_gross=rebalance_gross,
        turnover_one_way=one_way,
        annualized_turnover_one_way=one_way / elapsed_years,
        transaction_cost=total_cost,
        rebalance_count=len(events),
        events=events,
        pending_signal=pending,
        initial_trade_cost=initial_cost,
    )


def _validate_snapshot_structure(snapshot: dict):
    tickers = snapshot.get("candidateTickers")
    benchmark = snapshot.get("benchmark")
    dates = snapshot.get("dates")
    prices = snapshot.get("prices")
    split = snapshot.get("split")
    if not isinstance(tickers, list) or len(tickers) != CANDIDATE_COUNT:
        raise legacy.ValidationError("快照候選池數量不正確。")
    if not isinstance(benchmark, str) or not benchmark:
        raise legacy.ValidationError("快照比較基準遺失。")
    if not isinstance(dates, list) or len(dates) < 60:
        raise legacy.ValidationError("快照日期序列不足。")
    if not isinstance(prices, dict):
        raise legacy.ValidationError("快照價格矩陣遺失。")
    for ticker in [*tickers, benchmark]:
        values = prices.get(ticker)
        if not isinstance(values, list) or len(values) != len(dates):
            raise legacy.ValidationError(f"快照價格長度不一致：{ticker}")
    if not isinstance(split, dict):
        raise legacy.ValidationError("快照期間切割資訊遺失。")
    if snapshot.get("metricDefinitionVersion") != METRIC_DEFINITION_VERSION:
        raise legacy.ValidationError("快照績效公式版本已過期。")
    if (
        snapshot.get("marketDataContractVersion")
        != market_data.MARKET_DATA_CONTRACT_VERSION
    ):
        raise legacy.ValidationError("快照行情資料契約版本已過期。")


def _segment_result(
    candidate_prices: np.ndarray,
    benchmark_prices: np.ndarray,
    dates: pd.DatetimeIndex,
    *,
    band_ratio: float,
    transaction_cost_bps: float,
    ticker_names: list[str],
) -> dict:
    simulation = _simulate_band(
        candidate_prices,
        dates,
        band_ratio=band_ratio,
        transaction_cost_bps=transaction_cost_bps,
    )
    benchmark_history = pd.DataFrame(
        {"value": benchmark_prices / benchmark_prices[0] * 10_000.0},
        index=dates,
    )
    metrics = calculate_metrics(
        simulation.history,
        benchmark_history,
        risk_free_rate=legacy.RISK_FREE_RATE,
    )
    events = []
    for event in simulation.events:
        trigger_indexes = event.get("triggerIndexes", [])
        events.append(
            {
                key: value
                for key, value in event.items()
                if key != "triggerIndexes"
            }
            | {
                "triggerTickers": [
                    ticker_names[index] for index in trigger_indexes
                ],
            }
        )
    pending = simulation.pending_signal
    if pending:
        trigger_indexes = pending.get("triggerIndexes", [])
        pending = {
            key: value
            for key, value in pending.items()
            if key != "triggerIndexes"
        } | {
            "triggerTickers": [
                ticker_names[index] for index in trigger_indexes
            ],
        }
    return {
        **metrics,
        "turnoverGross": simulation.turnover_gross,
        "turnoverOneWay": simulation.turnover_one_way,
        "annualizedTurnoverOneWay": simulation.annualized_turnover_one_way,
        "transactionCost": simulation.transaction_cost,
        "initialTradeCost": simulation.initial_trade_cost,
        "rebalanceCount": simulation.rebalance_count,
        "rebalanceEvents": events,
        "unexecutedFinalSignal": pending,
        "portfolioValueFingerprint": series_fingerprint(simulation.history),
    }


@app.route("/api/optimizer/verify", methods=["POST"])
def optimizer_verify():
    try:
        data = legacy.require_json_object()
        snapshot = _decode_snapshot(data.get("snapshot"))
        _validate_snapshot_structure(snapshot)

        raw_combinations = data.get("combinations")
        if not isinstance(raw_combinations, list) or not raw_combinations:
            raise legacy.ValidationError("至少需要一組待複驗投組。")
        if len(raw_combinations) > MAX_VERIFY_COMBINATIONS:
            raise legacy.ValidationError(
                f"單次最多精確複驗 {MAX_VERIFY_COMBINATIONS} 組投組。"
            )

        settings = data.get("settings") or {}
        band_ratio = _parse_ratio(
            settings.get("bandRatio"),
            label="權重偏移比例",
            default=0.20,
        )
        try:
            transaction_cost_bps = float(settings.get("transactionCostBps", 0))
        except (TypeError, ValueError) as exc:
            raise legacy.ValidationError("交易成本格式不正確。") from exc
        if (
            not math.isfinite(transaction_cost_bps)
            or transaction_cost_bps < 0
            or transaction_cost_bps > 1_000
        ):
            raise legacy.ValidationError("交易成本必須介於 0 與 1,000 bps。")

        candidate_tickers = snapshot["candidateTickers"]
        ticker_set = set(candidate_tickers)
        dates = pd.DatetimeIndex(pd.to_datetime(snapshot["dates"]))
        split_index = int(snapshot["split"]["splitIndex"])
        if not 1 < split_index < len(dates) - 1:
            raise legacy.ValidationError("快照切割索引無效。")
        all_candidate_prices = np.column_stack(
            [
                np.asarray(snapshot["prices"][ticker], dtype=float)
                for ticker in candidate_tickers
            ]
        )
        benchmark_prices = np.asarray(
            snapshot["prices"][snapshot["benchmark"]], dtype=float
        )
        index_by_ticker = {
            ticker: index for index, ticker in enumerate(candidate_tickers)
        }

        seen = set()
        results = []
        for raw in raw_combinations:
            if not isinstance(raw, dict):
                raise legacy.ValidationError("待複驗投組格式不正確。")
            tickers = [
                legacy.normalize_ticker(value) for value in raw.get("tickers", [])
            ]
            if (
                len(tickers) != HOLDING_COUNT
                or len(set(tickers)) != HOLDING_COUNT
                or not set(tickers).issubset(ticker_set)
            ):
                raise legacy.ValidationError(
                    f"每組投組必須由候選池中的 {HOLDING_COUNT} 檔不重複股票組成。"
                )
            canonical = tuple(sorted(tickers))
            if canonical in seen:
                continue
            seen.add(canonical)
            ordered = list(canonical)
            columns = [index_by_ticker[ticker] for ticker in ordered]
            selected = all_candidate_prices[:, columns]

            training = _segment_result(
                selected[:split_index],
                benchmark_prices[:split_index],
                dates[:split_index],
                band_ratio=band_ratio,
                transaction_cost_bps=transaction_cost_bps,
                ticker_names=ordered,
            )
            validation = _segment_result(
                selected[split_index:],
                benchmark_prices[split_index:],
                dates[split_index:],
                band_ratio=band_ratio,
                transaction_cost_bps=transaction_cost_bps,
                ticker_names=ordered,
            )
            results.append(
                {
                    "combinationId": str(raw.get("combinationId") or ""),
                    "mask": int(raw.get("mask") or 0),
                    "tickers": ordered,
                    "training": training,
                    "validation": validation,
                }
            )

        metadata = reproducibility_metadata(
            risk_free_rate=legacy.RISK_FREE_RATE,
            benchmark=snapshot["benchmark"],
            extra={
                "optimizer_algorithm_version": OPTIMIZER_ALGORITHM_VERSION,
                "rebalance_engine_version": REBALANCE_ENGINE_VERSION,
                "snapshot_format_version": SNAPSHOT_FORMAT_VERSION,
                "dataset_hash": data["snapshot"]["datasetHash"],
                "candidate_pool_hash": hashlib.sha256(
                    "\n".join(candidate_tickers).encode("utf-8")
                ).hexdigest(),
                "training_split": snapshot["split"],
                "target_weights": [0.1] * HOLDING_COUNT,
                "rebalance_band_mode": "relative_to_target_weight",
                "rebalance_band_ratio": band_ratio,
                "trigger_lower_bound": 0.1 * (1 - band_ratio),
                "trigger_upper_bound": 0.1 * (1 + band_ratio),
                "execution_delay_trading_days": 1,
                "execution_price": "next_common_trading_day_adjusted_close",
                "transaction_cost_bps": transaction_cost_bps,
                "initial_trade_cost_policy": "included",
                "turnover_definition": "gross_notional_and_one_way",
                "verified_combinations": len(results),
                "candidate_selection": snapshot.get("candidateSelection") or {},
                "price_fingerprints": snapshot["priceFingerprints"],
            },
        )
        return jsonify({"results": results, "metadata": metadata})
    except legacy.ValidationError as exc:
        return error_response(str(exc), 400)
    except Exception:
        app.logger.exception("Unexpected optimizer verification error")
        return error_response("精確複驗時發生錯誤。", 500)
