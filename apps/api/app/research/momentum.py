"""Training-only momentum primitives and the first Optimizer Hub strategy.

All signal values come from the authoritative ResearchDataset TWD total-return
levels available inside the Training window. Evaluation/OOS observations are not
part of the SelectionContext and therefore cannot influence these decisions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, ClassVar, Mapping

import numpy as np
import pandas as pd

from apps.api.app.research.selection import SelectionContext, SelectionResult

MOMENTUM_SIGNAL_CONTRACT_VERSION = "momentum-twd-total-return-2026-08-17.1"
DUAL_MOMENTUM_ENGINE_VERSION = "dual-momentum-selection-2026-08-17.1"
MOMENTUM_BOUNDARY_TOLERANCE_CALENDAR_DAYS = 7
DUAL_MOMENTUM_RULE = "absolute-filter-then-relative-top-k-with-defensive-fallback-v1"


@dataclass(frozen=True, slots=True)
class MomentumObservation:
    """One deterministic trailing total-return observation."""

    symbol: str
    lookback_months: int
    requested_start: date
    baseline_date: date
    end_date: date
    baseline_level: float
    end_level: float
    total_return: float

    def export_payload(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "lookbackMonths": self.lookback_months,
            "requestedStart": self.requested_start.isoformat(),
            "baselineDate": self.baseline_date.isoformat(),
            "endDate": self.end_date.isoformat(),
            "baselineLevelTwd": self.baseline_level,
            "endLevelTwd": self.end_level,
            "totalReturn": self.total_return,
        }


def trailing_total_return(
    levels: pd.Series,
    *,
    symbol: str,
    as_of: date,
    lookback_months: int,
    boundary_tolerance_days: int = MOMENTUM_BOUNDARY_TOLERANCE_CALENDAR_DAYS,
) -> MomentumObservation:
    """Return a calendar-month trailing return using only observations <= ``as_of``.

    The baseline is the first audited TWD level on or after the requested calendar
    lookback boundary. Both the baseline and end observation must lie within a
    small explicit calendar tolerance so recently listed or stale series cannot be
    silently compared on materially shorter windows.
    """

    canonical_symbol = str(symbol)
    if not canonical_symbol or canonical_symbol != canonical_symbol.strip().upper():
        raise ValueError("momentum symbol must already be canonical")
    if (
        not isinstance(lookback_months, int)
        or isinstance(lookback_months, bool)
        or not 1 <= lookback_months <= 60
    ):
        raise ValueError("lookback_months must be an integer between 1 and 60")
    if (
        not isinstance(boundary_tolerance_days, int)
        or isinstance(boundary_tolerance_days, bool)
        or not 0 <= boundary_tolerance_days <= 31
    ):
        raise ValueError("boundary_tolerance_days must be an integer between 0 and 31")
    if not isinstance(levels.index, pd.DatetimeIndex):
        raise TypeError("momentum levels require a DatetimeIndex")
    if levels.index.has_duplicates or not levels.index.is_monotonic_increasing:
        raise ValueError("momentum levels index must be unique and increasing")

    numeric = pd.to_numeric(levels, errors="coerce").astype(float)
    as_of_ts = pd.Timestamp(as_of)
    requested_start_ts = as_of_ts - pd.DateOffset(months=lookback_months)
    candidate = numeric.loc[
        (numeric.index >= requested_start_ts) & (numeric.index <= as_of_ts)
    ]
    if candidate.empty:
        raise ValueError(f"{canonical_symbol} has no observations inside the momentum window")
    values = candidate.to_numpy(dtype=float)
    if not np.isfinite(values).all() or bool((values <= 0.0).any()):
        raise ValueError(
            f"{canonical_symbol} momentum window requires finite positive TWD levels"
        )

    baseline_ts = candidate.index[0]
    end_ts = candidate.index[-1]
    baseline_date = baseline_ts.date()
    end_date = end_ts.date()
    requested_start = requested_start_ts.date()
    if baseline_date > requested_start + timedelta(days=boundary_tolerance_days):
        raise ValueError(
            f"{canonical_symbol} lacks a causal baseline near the requested momentum boundary"
        )
    if end_date < as_of - timedelta(days=boundary_tolerance_days):
        raise ValueError(f"{canonical_symbol} momentum evidence is stale at signal time")
    if baseline_ts >= end_ts:
        raise ValueError(f"{canonical_symbol} momentum window requires at least two dates")

    baseline_level = float(candidate.iloc[0])
    end_level = float(candidate.iloc[-1])
    total_return = end_level / baseline_level - 1.0
    if not math.isfinite(total_return):
        raise ValueError(f"{canonical_symbol} momentum return is non-finite")
    return MomentumObservation(
        symbol=canonical_symbol,
        lookback_months=lookback_months,
        requested_start=requested_start,
        baseline_date=baseline_date,
        end_date=end_date,
        baseline_level=baseline_level,
        end_level=end_level,
        total_return=0.0 if total_return == 0.0 else total_return,
    )


def passes_absolute_momentum(
    observation: MomentumObservation,
    *,
    threshold: float = 0.0,
) -> bool:
    """Apply a finite absolute-return hurdle to one momentum observation."""

    value = float(threshold)
    if not math.isfinite(value):
        raise ValueError("absolute momentum threshold must be finite")
    return observation.total_return >= value


def rank_relative_momentum(
    observations: tuple[MomentumObservation, ...],
) -> tuple[MomentumObservation, ...]:
    """Rank highest return first with canonical symbol as deterministic tie-break."""

    if not observations:
        raise ValueError("relative momentum ranking requires at least one observation")
    if len({item.symbol for item in observations}) != len(observations):
        raise ValueError("relative momentum observations must have unique symbols")
    return tuple(sorted(observations, key=lambda item: (-item.total_return, item.symbol)))


def top_k_momentum(
    observations: tuple[MomentumObservation, ...],
    *,
    k: int,
) -> tuple[MomentumObservation, ...]:
    """Return the deterministic top-K prefix of an already comparable observation set."""

    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError("momentum top_k must be a positive integer")
    ranked = rank_relative_momentum(observations)
    return ranked[: min(k, len(ranked))]


@dataclass(frozen=True, slots=True)
class DualMomentumSelectionEngine:
    """Absolute-filter risky assets, rank survivors, otherwise use defensive assets.

    Version 1 intentionally delivers one narrow allocation policy: equal weight.
    Risky assets that clear the absolute threshold are ranked by relative trailing
    total return and up to ``top_k`` are selected. If none clear the hurdle, up to
    ``top_k`` defensive assets are selected by the same relative momentum signal.
    """

    risky_symbols: tuple[str, ...]
    defensive_symbols: tuple[str, ...]
    lookback_months: int = 12
    top_k: int = 1
    absolute_threshold: float = 0.0
    boundary_tolerance_days: int = MOMENTUM_BOUNDARY_TOLERANCE_CALENDAR_DAYS

    contract_version: ClassVar[str] = DUAL_MOMENTUM_ENGINE_VERSION
    rule: ClassVar[str] = DUAL_MOMENTUM_RULE

    def __post_init__(self) -> None:
        risky = _canonical_symbol_tuple(self.risky_symbols, label="risky_symbols")
        defensive = _canonical_symbol_tuple(
            self.defensive_symbols, label="defensive_symbols"
        )
        if set(risky).intersection(defensive):
            raise ValueError("risky and defensive symbols must not overlap")
        if (
            not isinstance(self.lookback_months, int)
            or isinstance(self.lookback_months, bool)
            or not 1 <= self.lookback_months <= 60
        ):
            raise ValueError("lookback_months must be an integer between 1 and 60")
        if (
            not isinstance(self.top_k, int)
            or isinstance(self.top_k, bool)
            or self.top_k < 1
            or self.top_k > len(risky)
        ):
            raise ValueError("top_k must be between 1 and the risky universe size")
        threshold = float(self.absolute_threshold)
        if not math.isfinite(threshold):
            raise ValueError("absolute_threshold must be finite")
        if (
            not isinstance(self.boundary_tolerance_days, int)
            or isinstance(self.boundary_tolerance_days, bool)
            or not 0 <= self.boundary_tolerance_days <= 31
        ):
            raise ValueError("boundary_tolerance_days must be an integer between 0 and 31")
        object.__setattr__(self, "risky_symbols", risky)
        object.__setattr__(self, "defensive_symbols", defensive)
        object.__setattr__(self, "absolute_threshold", 0.0 if threshold == 0.0 else threshold)

    @property
    def parameters(self) -> Mapping[str, Any]:
        return {
            "riskySymbols": list(self.risky_symbols),
            "defensiveSymbols": list(self.defensive_symbols),
            "lookbackMonths": self.lookback_months,
            "topK": self.top_k,
            "absoluteThreshold": self.absolute_threshold,
            "boundaryToleranceCalendarDays": self.boundary_tolerance_days,
            "signalAuthority": "ResearchDataset.daily_levels_twd",
            "signalSemantics": "audited-TWD-adjusted-total-return-levels",
            "weighting": "equal",
            "rebalanceFrequency": "monthly",
        }

    def select(self, context: SelectionContext) -> SelectionResult:
        configured = context.configured_universe
        if configured is None or context.pit_universe is not None:
            raise ValueError("Dual Momentum v1 requires configured research universe provenance")
        expected_members = (*self.risky_symbols, *self.defensive_symbols)
        if configured.members != expected_members:
            raise ValueError(
                "configured universe members must exactly match risky then defensive symbols"
            )
        if context.unavailable_candidates:
            unavailable = ", ".join(item.symbol for item in context.unavailable_candidates)
            raise ValueError(
                "Dual Momentum v1 does not silently shorten signal history: " + unavailable
            )
        if context.eligible_candidates != expected_members:
            raise ValueError("Dual Momentum eligible membership differs from configured request")

        levels = context.training_dataset.daily_levels_twd
        as_of = context.period.training_end
        risky_observations = tuple(
            trailing_total_return(
                levels[symbol],
                symbol=symbol,
                as_of=as_of,
                lookback_months=self.lookback_months,
                boundary_tolerance_days=self.boundary_tolerance_days,
            )
            for symbol in self.risky_symbols
        )
        defensive_observations = tuple(
            trailing_total_return(
                levels[symbol],
                symbol=symbol,
                as_of=as_of,
                lookback_months=self.lookback_months,
                boundary_tolerance_days=self.boundary_tolerance_days,
            )
            for symbol in self.defensive_symbols
        )

        risky_ranked = rank_relative_momentum(risky_observations)
        defensive_ranked = rank_relative_momentum(defensive_observations)
        qualifying_risky = tuple(
            item
            for item in risky_ranked
            if passes_absolute_momentum(item, threshold=self.absolute_threshold)
        )
        if qualifying_risky:
            selected_observations = qualifying_risky[: self.top_k]
            regime = "risk_on"
            fallback_reason = None
        else:
            selected_observations = defensive_ranked[: min(self.top_k, len(defensive_ranked))]
            regime = "defensive"
            fallback_reason = "no-risky-asset-cleared-absolute-threshold"
        if not selected_observations:
            raise ValueError("Dual Momentum produced no selectable constituent")

        selected = tuple(item.symbol for item in selected_observations)
        weight = 1.0 / len(selected)
        evidence = {
            "contractVersion": MOMENTUM_SIGNAL_CONTRACT_VERSION,
            "signalAsOf": as_of.isoformat(),
            "lookbackMonths": self.lookback_months,
            "absoluteThreshold": self.absolute_threshold,
            "boundaryToleranceCalendarDays": self.boundary_tolerance_days,
            "signalAuthority": "ResearchDataset.daily_levels_twd",
            "regime": regime,
            "fallbackReason": fallback_reason,
            "riskyRanking": [
                {
                    **item.export_payload(),
                    "relativeRank": rank,
                    "absolutePass": passes_absolute_momentum(
                        item, threshold=self.absolute_threshold
                    ),
                }
                for rank, item in enumerate(risky_ranked, start=1)
            ],
            "defensiveRanking": [
                {**item.export_payload(), "relativeRank": rank}
                for rank, item in enumerate(defensive_ranked, start=1)
            ],
            "selected": list(selected),
        }
        return SelectionResult(
            selected_constituents=selected,
            weights=tuple(weight for _ in selected),
            evidence=evidence,
        )


def _canonical_symbol_tuple(values: tuple[str, ...], *, label: str) -> tuple[str, ...]:
    symbols = tuple(str(value) for value in values)
    if not symbols:
        raise ValueError(f"{label} requires at least one symbol")
    if any(not symbol or symbol != symbol.strip().upper() for symbol in symbols):
        raise ValueError(f"{label} must contain canonical symbols")
    if len(set(symbols)) != len(symbols):
        raise ValueError(f"{label} must contain unique symbols")
    return symbols