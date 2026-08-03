"""Framework-neutral individual-asset scans under the unified TWD contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from api.corporate_actions import flattened_audit_fields
from api.metrics import (
    METRIC_DEFINITION_VERSION,
    aligned_fingerprint,
    benchmark_coverage,
    calculate_metrics,
    reproducibility_metadata,
    series_fingerprint,
)
from apps.api.app.backtest_service import (
    TWD_PORTFOLIO_CALENDAR_POLICY,
    align_twd_price_frame,
)
from apps.api.app.data.history_service import (
    HistoryFailure,
    PartialTWDHistories,
    TWDHistoryService,
    normalize_symbol,
)
from apps.api.app.data.twd_valuation import (
    TWD_VALUATION_CONTRACT_VERSION,
    VALUATION_CURRENCY,
)

TWD_SCAN_CALENDAR_POLICY = TWD_PORTFOLIO_CALENDAR_POLICY


@dataclass(slots=True)
class TWDScanBatch:
    """One request's per-ticker outcomes plus the underlying TWD histories."""

    requested: tuple[str, ...]
    results: list[dict[str, Any]]
    benchmark_symbol: str | None
    benchmark_available: bool
    benchmark_failure: HistoryFailure | None
    histories: PartialTWDHistories


class TWDScanService:
    """Calculate each candidate in TWD without allowing peer failures to erase it."""

    def __init__(self, *, history_service: TWDHistoryService | None = None) -> None:
        self._history_service = history_service or TWDHistoryService()

    def run(
        self,
        tickers: Iterable[str],
        *,
        start: date,
        end: date,
        benchmark: str | None,
        risk_free_rate: float = 0.0,
    ) -> TWDScanBatch:
        candidate_symbols = _deduplicate_symbols(tickers)
        benchmark_symbol = normalize_symbol(benchmark) if benchmark else None
        requested = _deduplicate_symbols(
            ([benchmark_symbol] if benchmark_symbol else []) + list(candidate_symbols)
        )
        histories = self._history_service.histories_partial(list(requested), start, end)
        benchmark_history = (
            histories.histories.get(benchmark_symbol) if benchmark_symbol else None
        )
        benchmark_failure = (
            histories.failures.get(benchmark_symbol) if benchmark_symbol else None
        )

        results: list[dict[str, Any]] = []
        for ticker in candidate_symbols:
            history = histories.histories.get(ticker)
            if history is None:
                failure = histories.failures.get(ticker) or HistoryFailure(
                    symbol=ticker,
                    stage="download",
                    detail="requested TWD history was not returned",
                    retryable=True,
                )
                results.append(_failure_row(ticker, failure, benchmark_history is not None))
                continue

            try:
                if benchmark_history is not None and benchmark_symbol is not None:
                    pair = align_twd_price_frame(
                        histories.histories, [ticker, benchmark_symbol]
                    )
                    values = pair[ticker]
                    benchmark_values = pair[benchmark_symbol]
                else:
                    values = history.adjusted_close_twd
                    benchmark_values = None
                if len(values) < 2:
                    raise ValueError("fewer than two shared TWD valuation dates")
            except ValueError as exc:
                results.append(
                    _failure_row(
                        ticker,
                        HistoryFailure(
                            symbol=ticker,
                            stage="calendar",
                            detail=str(exc),
                            retryable=False,
                        ),
                        benchmark_history is not None,
                    )
                )
                continue

            results.append(
                _success_row(
                    ticker,
                    history,
                    values,
                    benchmark_values,
                    benchmark_symbol,
                    risk_free_rate,
                )
            )

        return TWDScanBatch(
            requested=requested,
            results=results,
            benchmark_symbol=benchmark_symbol,
            benchmark_available=benchmark_history is not None,
            benchmark_failure=benchmark_failure,
            histories=histories,
        )


def _success_row(
    ticker: str,
    history,
    values,
    benchmark_values,
    benchmark_symbol: str | None,
    risk_free_rate: float,
) -> dict[str, Any]:
    audit = history.corporate_action_audit or {}
    metrics = calculate_metrics(
        values, benchmark_values, risk_free_rate=risk_free_rate
    )
    asset_hash = series_fingerprint(values)
    native_hash = series_fingerprint(history.native_adjusted_close)
    fx_hash = series_fingerprint(history.fx_to_twd)
    paired_hash = (
        aligned_fingerprint(values, benchmark_values)
        if benchmark_values is not None
        else None
    )
    metadata = reproducibility_metadata(
        risk_free_rate=risk_free_rate,
        benchmark=benchmark_symbol,
        extra={
            "valuation_currency": VALUATION_CURRENCY,
            "twd_valuation_contract_version": TWD_VALUATION_CONTRACT_VERSION,
            "twd_scan_calendar_policy": TWD_SCAN_CALENDAR_POLICY,
            "quote_currency": history.quote_currency,
            "fx_audit": history.fx_audit,
            "corporate_action_audit": audit,
            "price_fingerprint": asset_hash,
            "native_price_fingerprint": native_hash,
            "fx_price_fingerprint": fx_hash,
            "aligned_price_fingerprint": paired_hash,
        },
    )
    notes = []
    audit_note = _audit_note(audit)
    if audit_note:
        notes.append(audit_note)
    if benchmark_values is None and benchmark_symbol:
        notes.append("比較基準 TWD 行情無法取得，Beta／Alpha 暫不計算")
    return {
        "ticker": ticker,
        "status": "ok",
        "retryable": False,
        **metrics,
        "data_start": metrics["metric_start"],
        "data_end": metrics["metric_end"],
        "trading_days": int(len(values)),
        "data_coverage": (
            benchmark_coverage(values, benchmark_values)
            if benchmark_values is not None
            else 0.0
        ),
        "benchmark_available": benchmark_values is not None,
        "valuation_currency": VALUATION_CURRENCY,
        "twd_valuation_contract_version": TWD_VALUATION_CONTRACT_VERSION,
        "calendar_policy": TWD_SCAN_CALENDAR_POLICY,
        "quote_currency": history.quote_currency,
        "fx_audit": history.fx_audit,
        "native_price_fingerprint": native_hash,
        "fx_price_fingerprint": fx_hash,
        "note": f"（{'；'.join(notes)}）" if notes else None,
        "return_basis": metadata["return_basis"],
        "corporate_action_policy_version": metadata["corporate_action_policy_version"],
        "corporate_action_audit": audit,
        **flattened_audit_fields(audit),
        "price_fingerprint": asset_hash,
        "aligned_price_fingerprint": paired_hash,
        "valuation_metadata": metadata,
        "reproducibility": _reproducibility_note(metadata, asset_hash, paired_hash),
    }


def _failure_row(
    ticker: str, failure: HistoryFailure, benchmark_available: bool
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "status": "failed",
        "retryable": failure.retryable,
        "error_code": f"twd_{failure.stage}_unavailable",
        "error": failure.detail,
        "benchmark_available": benchmark_available,
        "valuation_currency": VALUATION_CURRENCY,
        "twd_valuation_contract_version": TWD_VALUATION_CONTRACT_VERSION,
        "calendar_policy": TWD_SCAN_CALENDAR_POLICY,
        "metric_definition_version": METRIC_DEFINITION_VERSION,
    }


def _reproducibility_note(
    metadata: dict[str, Any], asset_hash: str | None, paired_hash: str | None
) -> str:
    settings = metadata["data_source_settings"]
    return ";".join(
        [
            f"metric={metadata['metric_definition_version']}",
            f"source=yfinance-{metadata['data_source_version']}",
            f"basis={metadata['return_basis']}",
            f"corp_actions={metadata['corporate_action_policy_version']}",
            f"adjust={str(settings['auto_adjust']).lower()}",
            f"actions={str(settings['actions']).lower()}",
            f"repair={str(settings['repair']).lower()}",
            f"rf={metadata['risk_free_rate']:.12g}",
            f"benchmark={metadata.get('benchmark', '')}",
            f"valuation={metadata['valuation_currency']}",
            f"twd_contract={metadata['twd_valuation_contract_version']}",
            f"asset_sha256={asset_hash or ''}",
            f"aligned_sha256={paired_hash or ''}",
        ]
    )


def _audit_note(audit: dict[str, Any]) -> str | None:
    status = audit.get("status")
    if status == "review_required":
        dates = audit.get("warning_dates") or []
        suffix = f"（{', '.join(dates[:3])}）" if dates else ""
        return f"公司行為調整需人工覆核{suffix}"
    if status in {"adjusted_close_unverifiable", "insufficient_audit_history"}:
        return "調整收盤價缺少足夠原始資料可供公司行為稽核"
    return None


def _deduplicate_symbols(symbols: Iterable[str | None]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in symbols:
        symbol = normalize_symbol(raw or "")
        if symbol and symbol not in seen:
            seen.add(symbol)
            result.append(symbol)
    return tuple(result)
