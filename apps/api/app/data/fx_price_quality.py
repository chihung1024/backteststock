"""Vendor-neutral quality checks for direct and inverted FX OHLC bars."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

_BAR_TOLERANCE = 1.005
_TRANSIENT_SCALE_RATIO = 3.0
_TRANSIENT_BRIDGE_LIMIT = math.log(1.50)


@dataclass(slots=True)
class PriceLevelReconciliation:
    levels: pd.Series
    corrected: pd.Series
    unresolved: pd.Series
    future_assisted: pd.Series

    @property
    def correction_count(self) -> int:
        return int(self.corrected.sum())

    @property
    def unresolved_count(self) -> int:
        return int(self.unresolved.sum())

    @property
    def future_assisted_count(self) -> int:
        """Corrections that required a later trusted observation."""

        return int(self.future_assisted.sum())


def reconcile_ohlc_levels(
    frame: pd.DataFrame,
    *,
    invert: bool = False,
) -> PriceLevelReconciliation:
    """Return bar-consistent closing levels without symbol- or date-specific rules.

    A daily close must lie inside that day's low/high range.  When an upstream
    close is impossible but its OHLC bar remains coherent, reconstruct it by
    time-weighted log interpolation and constrain it to the observed bar.  A
    second pass repairs a reversible one-row scale pulse only when the bar gives
    independent support.  Valid, large price moves remain intact.

    Some historical repairs deliberately use a later trusted observation.  They
    remain useful for full-period data cleaning, but are marked in
    ``future_assisted`` so walk-forward/OOS consumers can exclude them rather
    than silently treating a non-causal repair as contemporaneously available.

    Inversion is applied to all OHLC fields before validation; high and low
    swap under a reciprocal quote.  That makes a direct and inverse FX quote
    economically equivalent before their quality scores are compared.
    """

    normalized = frame.copy()
    normalized.index = _naive_datetime_index(normalized.index)
    normalized = normalized.sort_index()
    normalized = normalized.loc[~normalized.index.duplicated(keep="last")]

    open_ = _numeric_column(normalized, "Open")
    high = _numeric_column(normalized, "High")
    low = _numeric_column(normalized, "Low")
    close = _numeric_column(normalized, "Close")

    if invert:
        original_high = high.copy()
        original_low = low.copy()
        open_ = _reciprocal(open_)
        close = _reciprocal(close)
        high = _reciprocal(original_low)
        low = _reciprocal(original_high)

    levels = close.copy()
    corrected = pd.Series(False, index=levels.index, dtype=bool)
    future_assisted = pd.Series(False, index=levels.index, dtype=bool)

    bar_valid = _valid_bar(open_, high, low)
    trusted = bar_valid & _inside_bar(levels, high, low)

    for position in range(len(levels)):
        if trusted.iloc[position] or not bar_valid.iloc[position]:
            continue
        replacement, used_future = _bar_supported_replacement(
            levels=levels,
            trusted=trusted,
            open_=open_,
            high=high,
            low=low,
            position=position,
        )
        if replacement is None:
            continue
        levels.iloc[position] = replacement
        corrected.iloc[position] = True
        future_assisted.iloc[position] = used_future
        trusted.iloc[position] = True

    # A vendor can emit a one-row temporary unit change inside a formally wide
    # bar.  Repair it only if a geometric bridge between its neighbours lies in
    # the bar, so a genuine large move is not silently changed.  Because this
    # bridge requires the following observation, it is non-causal by definition.
    for position in range(1, len(levels) - 1):
        if corrected.iloc[position] or not bar_valid.iloc[position]:
            continue
        previous = float(levels.iloc[position - 1])
        current = float(levels.iloc[position])
        following = float(levels.iloc[position + 1])
        if not all(_positive(value) for value in (previous, current, following)):
            continue

        entry = current / previous
        exit_ = following / current
        if math.log(entry) * math.log(exit_) >= 0.0:
            continue
        if min(abs(math.log(entry)), abs(math.log(exit_))) < math.log(
            _TRANSIENT_SCALE_RATIO
        ):
            continue
        if abs(math.log(following / previous)) > _TRANSIENT_BRIDGE_LIMIT:
            continue

        replacement = _time_weighted_geometric_level(
            index=levels.index,
            previous_position=position - 1,
            position=position,
            next_position=position + 1,
            previous=previous,
            following=following,
        )
        if replacement is None:
            continue
        lower = float(low.iloc[position])
        upper = float(high.iloc[position])
        if not _inside(replacement, lower, upper):
            continue
        levels.iloc[position] = min(max(replacement, lower), upper)
        corrected.iloc[position] = True
        future_assisted.iloc[position] = True
        trusted.iloc[position] = True

    unresolved = bar_valid & ~_inside_bar(levels, high, low)
    levels = levels.replace([np.inf, -np.inf], np.nan).dropna()
    levels = levels[levels > 0.0]
    corrected = corrected.reindex(levels.index, fill_value=False)
    unresolved = unresolved.reindex(levels.index, fill_value=False)
    future_assisted = future_assisted.reindex(levels.index, fill_value=False)
    return PriceLevelReconciliation(
        levels=levels.astype(float),
        corrected=corrected,
        unresolved=unresolved,
        future_assisted=future_assisted,
    )


def _bar_supported_replacement(
    *,
    levels: pd.Series,
    trusted: pd.Series,
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    position: int,
) -> tuple[float | None, bool]:
    previous_position = _nearest_trusted(trusted, position, step=-1)
    next_position = _nearest_trusted(trusted, position, step=1)
    replacement: float | None = None
    used_future = False
    if previous_position is not None and next_position is not None:
        replacement = _time_weighted_geometric_level(
            index=levels.index,
            previous_position=previous_position,
            position=position,
            next_position=next_position,
            previous=float(levels.iloc[previous_position]),
            following=float(levels.iloc[next_position]),
        )
        used_future = True
    elif _positive(float(open_.iloc[position])):
        replacement = float(open_.iloc[position])
    elif previous_position is not None:
        replacement = float(levels.iloc[previous_position])
    elif next_position is not None:
        replacement = float(levels.iloc[next_position])
        used_future = True

    if replacement is None or not _positive(replacement):
        return None, False
    lower = float(low.iloc[position])
    upper = float(high.iloc[position])
    if not _positive(lower) or not _positive(upper) or lower > upper:
        return None, False
    return min(max(replacement, lower), upper), used_future


def _time_weighted_geometric_level(
    *,
    index: pd.DatetimeIndex,
    previous_position: int,
    position: int,
    next_position: int,
    previous: float,
    following: float,
) -> float | None:
    if not _positive(previous) or not _positive(following):
        return None
    start = index[previous_position].value
    current = index[position].value
    end = index[next_position].value
    if end <= start:
        return math.sqrt(previous * following)
    weight = min(max((current - start) / (end - start), 0.0), 1.0)
    return math.exp((1.0 - weight) * math.log(previous) + weight * math.log(following))


def _nearest_trusted(trusted: pd.Series, position: int, *, step: int) -> int | None:
    current = position + step
    while 0 <= current < len(trusted):
        if bool(trusted.iloc[current]):
            return current
        current += step
    return None


def _valid_bar(open_: pd.Series, high: pd.Series, low: pd.Series) -> pd.Series:
    positive = (open_ > 0.0) & (high > 0.0) & (low > 0.0)
    return positive & (high >= low) & _inside_bar(open_, high, low)


def _inside_bar(values: pd.Series, high: pd.Series, low: pd.Series) -> pd.Series:
    return (values >= low / _BAR_TOLERANCE) & (values <= high * _BAR_TOLERANCE)


def _inside(value: float, low: float, high: float) -> bool:
    return bool(
        _positive(value)
        and _positive(low)
        and _positive(high)
        and low <= high
        and value >= low / _BAR_TOLERANCE
        and value <= high * _BAR_TOLERANCE
    )


def _numeric_column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name not in frame:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    values = frame[name]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, 0]
    return pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _reciprocal(values: pd.Series) -> pd.Series:
    return 1.0 / values.where(values > 0.0)


def _positive(value: float) -> bool:
    return bool(np.isfinite(value) and value > 0.0)


def _naive_datetime_index(index: pd.Index) -> pd.DatetimeIndex:
    result = pd.DatetimeIndex(pd.to_datetime(index))
    if result.tz is not None:
        result = result.tz_localize(None)
    return result
