"""Deterministic date-completeness policy for production research endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pandas as pd

AS_OF_POLICY = "last_complete_utc_calendar_day-v1"


class DatePolicyError(ValueError):
    """Raised when a requested research period can include incomplete future data."""


@dataclass(frozen=True, slots=True)
class CompletePeriod:
    start: pd.Timestamp
    end_exclusive: pd.Timestamp
    as_of_date: date
    as_of_policy: str = AS_OF_POLICY
    incomplete_current_bar_excluded: bool = True


def latest_complete_utc_date(now: datetime | None = None) -> date:
    """Return the latest date guaranteed to be a completed UTC calendar day."""

    resolved = now or datetime.now(timezone.utc)
    if resolved.tzinfo is None:
        resolved = resolved.replace(tzinfo=timezone.utc)
    else:
        resolved = resolved.astimezone(timezone.utc)
    return resolved.date() - timedelta(days=1)


def require_complete_period(
    start: pd.Timestamp,
    end_exclusive: pd.Timestamp,
    *,
    now: datetime | None = None,
) -> CompletePeriod:
    """Reject periods that extend beyond the last complete UTC calendar day.

    The public product uses daily bars across multiple exchanges.  Rather than
    guessing whether every relevant exchange has closed on the current date,
    production research excludes the current UTC calendar day entirely.  This
    makes the as-of boundary deterministic and prevents partial current-day bars
    or not-yet-complete future/current months from entering a backtest.
    """

    normalized_start = pd.Timestamp(start).tz_localize(None).normalize()
    normalized_end_exclusive = pd.Timestamp(end_exclusive).tz_localize(None).normalize()
    if normalized_start >= normalized_end_exclusive:
        raise DatePolicyError("結束日期必須晚於起始日期。")

    as_of = latest_complete_utc_date(now)
    requested_end = (normalized_end_exclusive - pd.Timedelta(days=1)).date()
    if requested_end > as_of:
        raise DatePolicyError(
            "結束日期不得晚於最後一個完整日 "
            f"{as_of.isoformat()}；今日尚可能包含未收盤或不完整日線。"
        )

    return CompletePeriod(
        start=normalized_start,
        end_exclusive=normalized_end_exclusive,
        as_of_date=as_of,
    )
