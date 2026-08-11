"""Shared official factor-data adapters for research and Portfolio analytics."""

from __future__ import annotations

import io
import re
import threading
import zipfile

import pandas as pd
import requests
from cachetools import TTLCache

FRENCH_FACTOR_SOURCE = "Kenneth French Data Library"
_FRENCH_BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"


class FrenchFactorProvider:
    """Load official monthly U.S. five-factor and momentum observations."""

    def __init__(self, timeout_seconds: float = 20.0, ttl_seconds: int = 21_600) -> None:
        self.timeout_seconds = timeout_seconds
        self._cache: TTLCache[str, pd.DataFrame] = TTLCache(maxsize=2, ttl=ttl_seconds)
        self._lock = threading.RLock()

    def monthly_factors(self) -> pd.DataFrame:
        with self._lock:
            cached = self._cache.get("monthly")
            if cached is not None:
                return cached.copy()
        five = self._download_zip_csv("F-F_Research_Data_5_Factors_2x3_CSV.zip")
        momentum = self._download_zip_csv("F-F_Momentum_Factor_CSV.zip")
        momentum_column = next(
            (
                column
                for column in momentum.columns
                if str(column).strip().lower().startswith("mom")
            ),
            momentum.columns[0],
        )
        momentum = momentum[[momentum_column]].rename(columns={momentum_column: "MOM"})
        frame = five.join(momentum, how="inner")
        frame.columns = [
            str(column).strip().replace("Mkt-RF", "MKT_RF")
            for column in frame.columns
        ]
        frame = frame.apply(pd.to_numeric, errors="coerce").dropna(how="all") / 100.0
        with self._lock:
            self._cache["monthly"] = frame
        return frame.copy()

    def _download_zip_csv(self, filename: str) -> pd.DataFrame:
        response = requests.get(
            f"{_FRENCH_BASE_URL}/{filename}",
            timeout=self.timeout_seconds,
            allow_redirects=True,
        )
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            member = archive.namelist()[0]
            text = archive.read(member).decode("utf-8", errors="replace")
        return parse_monthly_factor_text(text)


def parse_monthly_factor_text(text: str) -> pd.DataFrame:
    """Parse the monthly block from official French Library CSV text."""

    rows: list[str] = []
    header: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if header is None and stripped.startswith(","):
            header = stripped
            continue
        if re.match(r"^\d{6},", stripped):
            rows.append(stripped)
        elif rows:
            break
    if header is None or not rows:
        raise ValueError("unexpected Kenneth French factor file format")
    frame = pd.read_csv(io.StringIO("date" + header + "\n" + "\n".join(rows)))
    frame["date"] = (
        pd.to_datetime(frame["date"].astype(str), format="%Y%m")
        + pd.offsets.MonthEnd(0)
    )
    return frame.set_index("date")
