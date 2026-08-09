"""Reproducible research dataset built from audited TWD asset histories.

Phase 1 intentionally creates a framework-neutral data object without changing
any production Scanner, Portfolio, or Exhaustive consumer. The object preserves
requested membership and failures, makes calendar/coverage transformations
explicit, and provides deterministic export/hash semantics for later Portfolio
Refinery risk research.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from api.corporate_actions import CORPORATE_ACTION_POLICY_VERSION
from api.market_data import MARKET_DATA_CONTRACT_VERSION
from api.metrics import FINGERPRINT_ALGORITHM, series_fingerprint
from apps.api.app.backtest_service import (
    TWD_PORTFOLIO_CALENDAR_POLICY,
    align_twd_price_frame,
)
from apps.api.app.data.history_service import (
    HistoryFailure,
    PartialTWDHistories,
    TWDAssetHistory,
    TWDHistoryService,
)
from apps.api.app.data.return_components import RETURN_COMPONENTS_CONTRACT_VERSION
from apps.api.app.data.twd_valuation import (
    TWD_VALUATION_CONTRACT_VERSION,
    VALUATION_CURRENCY,
)

RESEARCH_DATASET_CONTRACT_VERSION = "research-dataset-twd-2026-08-09.1"
RESEARCH_DATASET_HASH_ALGORITHM = "sha256-canonical-json-v1"
RESEARCH_DAILY_RETURN_POLICY = "aligned-twd-level-pct-change-exclude-opening-v1"
RESEARCH_WEEKLY_POLICY = "w-fri-period-last-actual-twd-observation-v1"


@dataclass(slots=True)
class ResearchDataset:
    """One deterministic research view over a batch of audited TWD histories.

    A dataset may be partial: `requested_symbols` always preserves the normalized
    requested order, while `resolved_symbols` and `failures` make missing assets
    explicit. Consumers that require a complete universe must enforce that
    policy themselves instead of receiving a silently reduced dataset.
    """

    requested_symbols: tuple[str, ...]
    resolved_symbols: tuple[str, ...]
    failures: dict[str, HistoryFailure]
    requested_start: date
    requested_end: date
    reference_calendar: pd.DatetimeIndex
    availability_masks: dict[str, np.ndarray]
    daily_levels_twd: pd.DataFrame
    daily_returns_twd: pd.DataFrame
    weekly_levels_twd: pd.DataFrame
    weekly_returns_twd: pd.DataFrame
    native_returns: dict[str, pd.Series]
    fx_returns: dict[str, pd.Series]
    coverage: dict[str, dict[str, Any]]
    asset_metadata: dict[str, dict[str, Any]]
    dataset_hash: str
    contract_version: str = RESEARCH_DATASET_CONTRACT_VERSION

    @property
    def is_complete(self) -> bool:
        return not self.failures and self.requested_symbols == self.resolved_symbols

    @property
    def effective_start(self) -> date | None:
        if self.daily_levels_twd.empty:
            return None
        return self.daily_levels_twd.index[0].date()

    @property
    def effective_end(self) -> date | None:
        if self.daily_levels_twd.empty:
            return None
        return self.daily_levels_twd.index[-1].date()

    def export_payload(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot suitable for durable research export."""

        return _dataset_payload(self, include_hash=True)


class ResearchDatasetService:
    """Fetch audited histories once and turn them into `ResearchDatasetV1`."""

    def __init__(self, *, history_service: TWDHistoryService | None = None) -> None:
        self._history_service = history_service or TWDHistoryService()

    def build(
        self,
        symbols: Iterable[str],
        *,
        start: date,
        end: date,
    ) -> ResearchDataset:
        if start > end:
            raise ValueError("research dataset start must not be after end")
        histories = self._history_service.histories_partial(list(symbols), start, end)
        return build_research_dataset(histories, start=start, end=end)


def build_research_dataset(
    histories: PartialTWDHistories,
    *,
    start: date,
    end: date,
) -> ResearchDataset:
    """Build deterministic aligned daily/weekly research matrices.

    The daily TWD level matrix deliberately uses the existing
    `align_twd_price_frame()` semantics so Phase 1 can prove parity with current
    Exhaustive preparation before any production caller is migrated.
    """

    if start > end:
        raise ValueError("research dataset start must not be after end")
    if not isinstance(histories, PartialTWDHistories):
        raise TypeError("histories must be PartialTWDHistories")

    requested = tuple(histories.requested)
    resolved = tuple(symbol for symbol in requested if symbol in histories.histories)
    failures = {
        symbol: histories.failures[symbol]
        for symbol in requested
        if symbol in histories.failures
    }
    unaccounted = [
        symbol
        for symbol in requested
        if symbol not in histories.histories and symbol not in histories.failures
    ]
    if unaccounted:
        raise ValueError(
            "research histories contain requested symbols without an explicit "
            "success/failure outcome: " + ", ".join(unaccounted)
        )

    reference = _reference_calendar(histories.histories, resolved)
    masks = {
        symbol: _availability_mask(
            histories.histories[symbol].adjusted_close_twd,
            reference,
        )
        for symbol in resolved
    }
    coverage = _coverage_diagnostics(requested, resolved, failures, reference, masks)

    if resolved:
        daily_levels = align_twd_price_frame(histories.histories, resolved)
    else:
        daily_levels = pd.DataFrame(dtype=float)
    daily_returns = _matrix_returns(daily_levels)
    weekly_levels = _weekly_last_actual(daily_levels)
    weekly_returns = _matrix_returns(weekly_levels)

    native_returns = {
        symbol: _series_returns(histories.histories[symbol].native_adjusted_close)
        for symbol in resolved
    }
    fx_returns = {
        symbol: _series_returns(histories.histories[symbol].fx_to_twd)
        for symbol in resolved
    }
    asset_metadata = {
        symbol: _asset_metadata(
            histories.histories[symbol],
            daily_levels[symbol] if symbol in daily_levels.columns else None,
        )
        for symbol in resolved
    }

    dataset = ResearchDataset(
        requested_symbols=requested,
        resolved_symbols=resolved,
        failures=failures,
        requested_start=start,
        requested_end=end,
        reference_calendar=reference,
        availability_masks=masks,
        daily_levels_twd=daily_levels,
        daily_returns_twd=daily_returns,
        weekly_levels_twd=weekly_levels,
        weekly_returns_twd=weekly_returns,
        native_returns=native_returns,
        fx_returns=fx_returns,
        coverage=coverage,
        asset_metadata=asset_metadata,
        dataset_hash="",
    )
    dataset.dataset_hash = _dataset_hash(dataset)
    return dataset


def _reference_calendar(
    histories: Mapping[str, TWDAssetHistory], symbols: Iterable[str]
) -> pd.DatetimeIndex:
    calendar = pd.DatetimeIndex([])
    for symbol in symbols:
        calendar = calendar.union(histories[symbol].adjusted_close_twd.index)
    return calendar.sort_values().unique()


def _availability_mask(
    levels: pd.Series,
    reference_index: pd.DatetimeIndex,
) -> np.ndarray:
    """Match the current Exhaustive first/last-real-history availability rule."""

    observed = pd.DatetimeIndex(levels.index).intersection(reference_index)
    mask = np.zeros(len(reference_index), dtype=bool)
    if observed.empty:
        return mask
    first = reference_index.get_indexer([observed[0]])[0]
    last = reference_index.get_indexer([observed[-1]])[0]
    if first >= 0 and last >= first:
        mask[first : last + 1] = True
    return mask


def _coverage_diagnostics(
    requested: tuple[str, ...],
    resolved: tuple[str, ...],
    failures: Mapping[str, HistoryFailure],
    reference_index: pd.DatetimeIndex,
    masks: Mapping[str, np.ndarray],
) -> dict[str, dict[str, Any]]:
    diagnostics: dict[str, dict[str, Any]] = {}
    reference_count = len(reference_index)

    for symbol in requested:
        if symbol not in resolved:
            failure = failures[symbol]
            diagnostics[symbol] = {
                "status": "unavailable",
                "overall": 0.0,
                "missing_days": reference_count,
                "first_available_position": None,
                "last_available_position": None,
                "failure_stage": failure.stage,
            }
            continue
        mask = np.asarray(masks[symbol], dtype=bool)
        if len(mask) != reference_count:
            raise ValueError(f"availability mask length mismatch: {symbol}")
        diagnostics[symbol] = {
            "status": "available",
            "overall": float(mask.mean()) if reference_count else 0.0,
            "missing_days": int((~mask).sum()),
            "first_available_position": int(np.argmax(mask)) if mask.any() else None,
            "last_available_position": (
                int(reference_count - 1 - np.argmax(mask[::-1])) if mask.any() else None
            ),
        }

    if resolved and reference_count:
        common_mask = np.logical_and.reduce(
            [np.asarray(masks[symbol], dtype=bool) for symbol in resolved]
        )
        common_count = int(common_mask.sum())
        overall = float(common_mask.mean())
    else:
        common_count = 0
        overall = 0.0
    diagnostics["_global_complete_case"] = {
        "overall": overall,
        "reference_observations": reference_count,
        "common_observations": common_count,
        "resolved_symbols": len(resolved),
        "requested_symbols": len(requested),
    }
    return diagnostics


def _matrix_returns(levels: pd.DataFrame) -> pd.DataFrame:
    if levels.empty or len(levels) < 2:
        return pd.DataFrame(columns=levels.columns, dtype=float)
    returns = levels.pct_change(fill_method=None).iloc[1:]
    return returns.astype(float)


def _series_returns(levels: pd.Series) -> pd.Series:
    values = pd.to_numeric(levels, errors="coerce").astype(float)
    if len(values) < 2:
        return pd.Series(dtype=float, name="return")
    return values.pct_change(fill_method=None).iloc[1:].rename("return").astype(float)


def _weekly_last_actual(levels: pd.DataFrame) -> pd.DataFrame:
    """Use the last actual research date in each W-FRI period.

    We deliberately keep the source observation date rather than replacing it
    with a future Friday label. This prevents a mid-week research end date from
    being represented by a timestamp that had not occurred yet.
    """

    if levels.empty:
        return levels.copy()
    periods = levels.index.to_period("W-FRI")
    position_series = pd.Series(np.arange(len(levels)), index=levels.index)
    last_positions = position_series.groupby(periods).last().to_numpy(dtype=int)
    return levels.iloc[last_positions].copy()


def _asset_metadata(
    history: TWDAssetHistory,
    aligned_twd_levels: pd.Series | None,
) -> dict[str, Any]:
    return {
        "symbol": history.symbol,
        "quote_currency": history.quote_currency,
        "raw_quote_currency": history.raw_quote_currency,
        "native_price_scale": float(history.native_price_scale),
        "first_twd_date": history.adjusted_close_twd.index[0].date().isoformat(),
        "last_twd_date": history.adjusted_close_twd.index[-1].date().isoformat(),
        "corporate_action_audit": _json_safe(history.corporate_action_audit),
        "fx_audit": _json_safe(history.fx_audit),
        "return_component_audit": _json_safe(history.return_component_audit),
        "fingerprints": {
            "native_adjusted_close": series_fingerprint(history.native_adjusted_close),
            "fx_to_twd": series_fingerprint(history.fx_to_twd),
            "twd_adjusted_close": series_fingerprint(history.adjusted_close_twd),
            "aligned_twd_level": (
                series_fingerprint(aligned_twd_levels)
                if aligned_twd_levels is not None and not aligned_twd_levels.empty
                else None
            ),
        },
    }


def _dataset_hash(dataset: ResearchDataset) -> str:
    payload = _dataset_payload(dataset, include_hash=False)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dataset_payload(
    dataset: ResearchDataset,
    *,
    include_hash: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "formatVersion": RESEARCH_DATASET_CONTRACT_VERSION,
        "hashAlgorithm": RESEARCH_DATASET_HASH_ALGORITHM,
        "valuationCurrency": VALUATION_CURRENCY,
        "marketDataContractVersion": MARKET_DATA_CONTRACT_VERSION,
        "twdValuationContractVersion": TWD_VALUATION_CONTRACT_VERSION,
        "returnComponentsContractVersion": RETURN_COMPONENTS_CONTRACT_VERSION,
        "corporateActionPolicyVersion": CORPORATE_ACTION_POLICY_VERSION,
        "fingerprintAlgorithm": FINGERPRINT_ALGORITHM,
        "dailyCalendarPolicy": TWD_PORTFOLIO_CALENDAR_POLICY,
        "dailyReturnPolicy": RESEARCH_DAILY_RETURN_POLICY,
        "weeklyPolicy": RESEARCH_WEEKLY_POLICY,
        "requestedSymbols": list(dataset.requested_symbols),
        "resolvedSymbols": list(dataset.resolved_symbols),
        "failures": {
            symbol: {
                "stage": failure.stage,
                "detail": failure.detail,
                "retryable": bool(failure.retryable),
            }
            for symbol, failure in dataset.failures.items()
        },
        "requestedStart": dataset.requested_start.isoformat(),
        "requestedEndInclusive": dataset.requested_end.isoformat(),
        "effectiveStart": (
            dataset.effective_start.isoformat() if dataset.effective_start else None
        ),
        "effectiveEnd": (
            dataset.effective_end.isoformat() if dataset.effective_end else None
        ),
        "referenceDates": _date_strings(dataset.reference_calendar),
        "availabilityMasks": {
            symbol: [bool(value) for value in dataset.availability_masks[symbol]]
            for symbol in dataset.resolved_symbols
        },
        "dailyTwd": _frame_payload(dataset.daily_levels_twd),
        "dailyTwdReturns": _frame_payload(dataset.daily_returns_twd),
        "weeklyTwd": _frame_payload(dataset.weekly_levels_twd),
        "weeklyTwdReturns": _frame_payload(dataset.weekly_returns_twd),
        "nativeReturns": {
            symbol: _series_payload(dataset.native_returns[symbol])
            for symbol in dataset.resolved_symbols
        },
        "fxReturns": {
            symbol: _series_payload(dataset.fx_returns[symbol])
            for symbol in dataset.resolved_symbols
        },
        "coverage": _json_safe(dataset.coverage),
        "assets": _json_safe(dataset.asset_metadata),
    }
    if include_hash:
        payload["datasetHash"] = dataset.dataset_hash
    return payload


def _frame_payload(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "dates": _date_strings(frame.index),
        "columns": [str(column) for column in frame.columns],
        "values": [
            [_finite_float(value) for value in row]
            for row in frame.to_numpy(dtype=float)
        ],
    }


def _series_payload(series: pd.Series) -> dict[str, Any]:
    return {
        "dates": _date_strings(series.index),
        "values": [_finite_float(value) for value in series.to_numpy(dtype=float)],
    }


def _date_strings(index: Iterable[Any]) -> list[str]:
    return [pd.Timestamp(value).date().isoformat() for value in index]


def _finite_float(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, int):
        return value
    if isinstance(value, (float, np.floating)):
        return _finite_float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (date, pd.Timestamp)):
        return pd.Timestamp(value).date().isoformat()
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        return [_json_safe(item) for item in sorted(value, key=repr)]
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)
