"""External analysis-data adapters isolated from the portfolio calculation core."""

from __future__ import annotations

import os
import threading
from datetime import date

import pandas as pd
import requests
from cachetools import TTLCache

from apps.api.app.research.factor_data import (
    FRENCH_FACTOR_SOURCE,
    FrenchFactorProvider,
    parse_monthly_factor_text,
)

FRED_SOURCE = "Federal Reserve Economic Data (FRED)"
_FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


class FredProvider:
    """Load macro series with an explicit API key and bounded in-memory cache."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = 20.0,
        ttl_seconds: int = 21_600,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("BACKTEST_FRED_API_KEY")
            or os.getenv("FRED_API_KEY")
            or ""
        ).strip()
        self.timeout_seconds = timeout_seconds
        self._cache: TTLCache[tuple[str, date | None, date | None], pd.Series] = TTLCache(
            maxsize=16,
            ttl=ttl_seconds,
        )
        self._lock = threading.RLock()

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def series(
        self,
        series_id: str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.Series:
        if not self.api_key:
            raise ValueError("FRED API key is not configured")
        cache_key = (series_id, start, end)
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached.copy()
        params: dict[str, str] = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        if start is not None:
            params["observation_start"] = start.isoformat()
        if end is not None:
            params["observation_end"] = end.isoformat()
        response = requests.get(
            _FRED_URL,
            params=params,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        observations = response.json().get("observations", [])
        frame = pd.DataFrame(observations)
        if frame.empty:
            raise ValueError(f"FRED returned no observations for {series_id}")
        values = pd.to_numeric(frame["value"], errors="coerce")
        index = pd.to_datetime(frame["date"])
        result = pd.Series(values.to_numpy(), index=index, name=series_id).dropna()
        if result.empty:
            raise ValueError(f"FRED returned no numeric observations for {series_id}")
        result = result[~result.index.duplicated(keep="last")].sort_index().astype(float)
        with self._lock:
            self._cache[cache_key] = result
        return result.copy()


__all__ = [
    "FRENCH_FACTOR_SOURCE",
    "FRED_SOURCE",
    "FrenchFactorProvider",
    "FredProvider",
    "parse_monthly_factor_text",
]
