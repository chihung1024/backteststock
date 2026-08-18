"""Audited date-window views derived from an existing ResearchDataset.

Phase 4B-3 uses one outer Training download and derives deterministic inner
Training/Evaluation datasets from it. This module slices only already-audited
ResearchDataset content; it never downloads, fills, or repairs market data.
"""

from __future__ import annotations

import copy
from datetime import date

import numpy as np
import pandas as pd

from api.metrics import series_fingerprint
from apps.api.app.data.history_service import HistoryFailure
from apps.api.app.research.dataset import (
    ResearchDataset,
    _coverage_diagnostics,
    _dataset_hash,
    _matrix_returns,
    _weekly_last_actual,
)

RESEARCH_DATASET_VIEW_POLICY = "research-dataset-bounded-date-view-2026-08-18.1"


def slice_research_dataset(
    parent: ResearchDataset,
    *,
    start: date,
    end: date,
) -> ResearchDataset:
    """Return a deterministic child dataset using only rows already in ``parent``.

    The child keeps the parent's requested symbol order and explicit failure
    accounting. A parent-resolved symbol with no audited availability inside the
    requested child window becomes an explicit non-retryable slice-window
    failure rather than being silently dropped.
    """

    parent.export_payload()
    if start > end:
        raise ValueError("research dataset view start must not be after end")
    if start < parent.requested_start or end > parent.requested_end:
        raise ValueError("research dataset view must stay inside the parent requested window")

    reference = pd.DatetimeIndex(parent.reference_calendar)
    reference_selector = (reference.date >= start) & (reference.date <= end)
    positions = np.flatnonzero(reference_selector)
    child_reference = reference[reference_selector]
    if child_reference.empty:
        raise ValueError("research dataset view contains no audited reference dates")

    requested = tuple(parent.requested_symbols)
    parent_resolved = set(parent.resolved_symbols)
    resolved: list[str] = []
    failures: dict[str, HistoryFailure] = {}
    masks: dict[str, np.ndarray] = {}

    for symbol in requested:
        if symbol in parent.failures:
            failures[symbol] = parent.failures[symbol]
            continue
        if symbol not in parent_resolved:
            raise ValueError("parent dataset membership accounting is incomplete")
        raw_mask = np.asarray(parent.availability_masks[symbol], dtype=bool)
        if len(raw_mask) != len(reference):
            raise ValueError(f"parent availability mask length mismatch: {symbol}")
        child_mask = raw_mask[positions].copy()
        if not bool(child_mask.any()):
            failures[symbol] = HistoryFailure(
                symbol=symbol,
                stage="slice_window",
                detail=(
                    "parent ResearchDataset has no audited availability inside "
                    f"{start.isoformat()}..{end.isoformat()}"
                ),
                retryable=False,
            )
            continue
        resolved.append(symbol)
        masks[symbol] = child_mask

    resolved_tuple = tuple(resolved)
    coverage = _coverage_diagnostics(
        requested,
        resolved_tuple,
        failures,
        child_reference,
        masks,
    )

    levels = parent.daily_levels_twd.reindex(child_reference)
    if resolved_tuple:
        levels = levels.loc[:, list(resolved_tuple)].copy()
    else:
        levels = pd.DataFrame(index=child_reference, dtype=float)
    daily_returns = _matrix_returns(levels)
    weekly_levels = _weekly_last_actual(levels)
    weekly_returns = _matrix_returns(weekly_levels)

    native_returns = {
        symbol: _slice_series(parent.native_returns.get(symbol), start=start, end=end)
        for symbol in resolved_tuple
    }
    fx_returns = {
        symbol: _slice_series(parent.fx_returns.get(symbol), start=start, end=end)
        for symbol in resolved_tuple
    }
    asset_metadata = {
        symbol: _child_asset_metadata(
            parent,
            symbol=symbol,
            levels=levels[symbol],
            start=start,
            end=end,
        )
        for symbol in resolved_tuple
    }

    child = ResearchDataset(
        requested_symbols=requested,
        resolved_symbols=resolved_tuple,
        failures=failures,
        requested_start=start,
        requested_end=end,
        reference_calendar=child_reference,
        availability_masks=masks,
        daily_levels_twd=levels,
        daily_returns_twd=daily_returns,
        weekly_levels_twd=weekly_levels,
        weekly_returns_twd=weekly_returns,
        native_returns=native_returns,
        fx_returns=fx_returns,
        coverage=coverage,
        asset_metadata=asset_metadata,
        dataset_hash="",
        contract_version=parent.contract_version,
    )
    child.dataset_hash = _dataset_hash(child)
    child.export_payload()
    if child.dataset_hash == parent.dataset_hash and (
        start != parent.requested_start or end != parent.requested_end
    ):
        raise ValueError("bounded research dataset view reused the parent identity")
    return child


def _slice_series(
    source: pd.Series | None,
    *,
    start: date,
    end: date,
) -> pd.Series:
    if source is None or source.empty:
        return pd.Series(dtype=float, name="return")
    index = pd.DatetimeIndex(pd.to_datetime(source.index))
    selector = (index.date >= start) & (index.date <= end)
    return source.loc[selector].copy()


def _child_asset_metadata(
    parent: ResearchDataset,
    *,
    symbol: str,
    levels: pd.Series,
    start: date,
    end: date,
) -> dict[str, object]:
    raw = parent.asset_metadata.get(symbol, {})
    metadata = copy.deepcopy(raw) if isinstance(raw, dict) else {}
    finite = pd.to_numeric(levels, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    metadata["research_dataset_view_policy"] = RESEARCH_DATASET_VIEW_POLICY
    metadata["parent_dataset_hash"] = parent.dataset_hash
    metadata["slice_requested_start"] = start.isoformat()
    metadata["slice_requested_end"] = end.isoformat()
    if not finite.empty:
        metadata["first_twd_date"] = finite.index[0].date().isoformat()
        metadata["last_twd_date"] = finite.index[-1].date().isoformat()
    fingerprints = metadata.get("fingerprints")
    if not isinstance(fingerprints, dict):
        fingerprints = {}
    else:
        fingerprints = copy.deepcopy(fingerprints)
    fingerprints["aligned_twd_level"] = (
        series_fingerprint(finite) if not finite.empty else None
    )
    metadata["fingerprints"] = fingerprints
    return metadata
