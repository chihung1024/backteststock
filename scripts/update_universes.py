"""Fetch, validate, and optionally publish versioned Universe snapshots to D1."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TICKER_PATTERN = re.compile(r"^[A-Z0-9.^=_-]{1,20}$")
ISHARES_DATE_PATTERN = re.compile(r'Fund Holdings as of,"([^"]+)"')
DEFAULT_REPORT_PATH = Path("universe-update-report.json")
MEMBER_INSERT_CHUNK_SIZE = 12
MAX_RETAINED_VERSIONS = 12
INVESCO_QQQM_HOLDINGS_URL = (
    "https://dng-api.invesco.com/cache/v1/accounts/en_US/"
    "shareclasses/46138G649/holdings/fund"
    "?idType=cusip&productType=ETF"
)
DEFAULT_NASDAQ100_RELAY_URL = (
    "https://backteststock.chired.workers.dev/api/v2/sources/qqqm-holdings"
)

TICKER_ALIASES = {
    "BRKA": "BRK-A",
    "BRKB": "BRK-B",
    "BFA": "BF-A",
    "BFB": "BF-B",
}


class UniverseUpdateError(RuntimeError):
    """Raised when a source or D1 response fails a safety check."""


@dataclass(frozen=True)
class SourceEndpoint:
    source_label: str
    source_url: str
    adapter: str
    fetch_url: str | None = None
    is_proxy: bool = False
    proxy_note: str | None = None
    read_timeout_seconds: int = 30

    @property
    def request_url(self) -> str:
        return self.fetch_url or self.source_url


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    name: str
    source_label: str
    source_url: str
    adapter: str
    min_members: int
    max_members: int
    max_count_change_ratio: float
    max_membership_churn_ratio: float
    is_proxy: bool = False
    proxy_note: str | None = None
    read_timeout_seconds: int = 30
    fallbacks: tuple[SourceEndpoint, ...] = ()


@dataclass(frozen=True)
class Member:
    ticker: str
    source_ticker: str
    company_name: str | None = None
    sector: str | None = None
    weight: float | None = None
    market_value: float | None = None


@dataclass(frozen=True)
class Snapshot:
    source: SourceDefinition
    effective_source: SourceEndpoint
    source_as_of: str | None
    fetched_at: str
    checksum: str
    version: str
    members: tuple[Member, ...]


SOURCES = (
    SourceDefinition(
        id="sp500",
        name="S&P 500（IVV holdings）",
        source_label="iShares IVV holdings",
        source_url=os.environ.get(
            "UNIVERSE_SP500_URL",
            "https://www.ishares.com/us/products/239726/"
            "ishares-core-s-p-500-etf/latest-holdings.csv",
        ),
        adapter="ishares_csv",
        min_members=480,
        max_members=530,
        max_count_change_ratio=0.08,
        max_membership_churn_ratio=0.10,
        is_proxy=True,
        proxy_note=(
            "此清單是 IVV 公開持股代理池，可能包含現金、衍生品差異或與正式 "
            "S&P 500 授權名單存在短暫時差。"
        ),
    ),
    SourceDefinition(
        id="nasdaq100",
        name="NASDAQ-100",
        source_label="Nasdaq official API",
        source_url=os.environ.get(
            "UNIVERSE_NASDAQ100_URL",
            "https://api.nasdaq.com/api/quote/list-type/nasdaq100",
        ),
        adapter="nasdaq_json",
        min_members=95,
        max_members=110,
        max_count_change_ratio=0.12,
        max_membership_churn_ratio=0.15,
        read_timeout_seconds=12,
        fallbacks=(
            SourceEndpoint(
                source_label="Invesco QQQM holdings",
                source_url=os.environ.get(
                    "UNIVERSE_NASDAQ100_FALLBACK_URL",
                    INVESCO_QQQM_HOLDINGS_URL,
                ),
                adapter="invesco_json",
                is_proxy=True,
                proxy_note=(
                    "Nasdaq 官方 API 本次不可用，已使用追蹤 Nasdaq-100 的 "
                    "Invesco QQQM 公開持股代理池；可能存在追蹤誤差或調整時差。"
                ),
            ),
            SourceEndpoint(
                source_label="Invesco QQQM holdings via edge relay",
                source_url=INVESCO_QQQM_HOLDINGS_URL,
                fetch_url=os.environ.get(
                    "UNIVERSE_NASDAQ100_RELAY_URL",
                    DEFAULT_NASDAQ100_RELAY_URL,
                ),
                adapter="invesco_json",
                is_proxy=True,
                proxy_note=(
                    "Nasdaq 官方 API 與 Invesco 直連本次皆不可用，已透過固定目的地的 "
                    "Cloudflare edge relay 取得 Invesco QQQM 公開持股代理池；"
                    "可能存在追蹤誤差或調整時差。"
                ),
                read_timeout_seconds=20,
            ),
        ),
    ),
    SourceDefinition(
        id="soxx",
        name="SOXX holdings",
        source_label="iShares SOXX holdings",
        source_url=os.environ.get(
            "UNIVERSE_SOXX_URL",
            "https://www.ishares.com/us/products/239705/"
            "ishares-semiconductor-etf/latest-holdings.csv",
        ),
        adapter="ishares_csv",
        min_members=25,
        max_members=40,
        max_count_change_ratio=0.30,
        max_membership_churn_ratio=0.35,
    ),
    SourceDefinition(
        id="russell2000",
        name="Russell 2000（IWM holdings 代理）",
        source_label="iShares IWM holdings",
        source_url=os.environ.get(
            "UNIVERSE_RUSSELL2000_URL",
            "https://www.ishares.com/us/products/239710/"
            "ishares-russell-2000-etf/latest-holdings.csv",
        ),
        adapter="ishares_csv",
        min_members=1_750,
        max_members=2_100,
        max_count_change_ratio=0.10,
        max_membership_churn_ratio=0.15,
        is_proxy=True,
        proxy_note=(
            "此清單是 IWM 公開持股代理池，不是 FTSE Russell 授權的正式指數成分名單，"
            "可能有追蹤誤差與調整時差。"
        ),
    ),
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def request_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "Accept": "application/json,text/csv,text/plain;q=0.9,*/*;q=0.8",
            "User-Agent": (
                "Mozilla/5.0 (compatible; BacktestStockUniverseUpdater/1.0; "
                "+https://github.com/chihung1024/backteststock)"
            ),
        }
    )
    return session


def normalize_ticker(raw_value: Any) -> str:
    source = str(raw_value or "").strip().upper()
    if not source:
        raise UniverseUpdateError("empty ticker")
    normalized = TICKER_ALIASES.get(source, source.replace(".", "-"))
    if not TICKER_PATTERN.fullmatch(normalized):
        raise UniverseUpdateError(f"invalid ticker: {source}")
    return normalized


def optional_float(value: Any) -> float | None:
    text = str(value or "").replace(",", "").replace("%", "").strip()
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def iso_date(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    for pattern in ("%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return (
                datetime.strptime(raw_value.strip(), pattern)
                .replace(tzinfo=UTC)
                .date()
                .isoformat()
            )
        except ValueError:
            continue
    raise UniverseUpdateError(f"unsupported source date: {raw_value}")


def validate_source_date(source_id: str, source_as_of: str | None) -> None:
    if not source_as_of:
        raise UniverseUpdateError(f"{source_id}: source did not provide an as-of date")
    source_date = date.fromisoformat(source_as_of)
    age_days = (datetime.now(UTC).date() - source_date).days
    if age_days < -2:
        raise UniverseUpdateError(
            f"{source_id}: source date is unexpectedly in the future"
        )
    if age_days > 14:
        raise UniverseUpdateError(
            f"{source_id}: source data is stale ({age_days} days old)"
        )


def parse_ishares_csv(text: str) -> tuple[str | None, list[Member]]:
    match = ISHARES_DATE_PATTERN.search(text[:1_000])
    source_as_of = iso_date(match.group(1)) if match else None
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if row and row[0].strip() == "Ticker" and "Asset Class" in row
        ),
        None,
    )
    if header_index is None:
        raise UniverseUpdateError("iShares CSV header was not found")

    reader = csv.DictReader(
        io.StringIO(
            "\n".join(
                ",".join(csv_escape(value) for value in row)
                for row in rows[header_index:]
            )
        )
    )
    members = []
    for row in reader:
        if str(row.get("Asset Class") or "").strip() != "Equity":
            continue
        source_ticker = str(row.get("Ticker") or "").strip().upper()
        try:
            ticker = normalize_ticker(source_ticker)
        except UniverseUpdateError:
            continue
        members.append(
            Member(
                ticker=ticker,
                source_ticker=source_ticker,
                company_name=clean_text(row.get("Name")),
                sector=clean_text(row.get("Sector")),
                weight=optional_float(row.get("Weight (%)")),
                market_value=optional_float(row.get("Market Value")),
            )
        )
    return source_as_of, members


def csv_escape(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def parse_nasdaq_json(payload: dict[str, Any]) -> tuple[str | None, list[Member]]:
    if payload.get("status", {}).get("rCode") not in (None, 200):
        raise UniverseUpdateError(
            f"Nasdaq API returned status: {payload.get('status')}"
        )
    try:
        container = payload["data"]
        rows = container["data"]["rows"]
    except (KeyError, TypeError) as exc:
        raise UniverseUpdateError("Nasdaq JSON rows were not found") from exc
    if not isinstance(rows, list):
        raise UniverseUpdateError("Nasdaq JSON rows are not a list")

    source_as_of = iso_date(container.get("date"))
    members = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_ticker = str(row.get("symbol") or "").strip().upper()
        try:
            ticker = normalize_ticker(source_ticker)
        except UniverseUpdateError:
            continue
        members.append(
            Member(
                ticker=ticker,
                source_ticker=source_ticker,
                company_name=clean_text(row.get("companyName")),
                sector=clean_text(row.get("sector")),
                market_value=optional_float(row.get("marketCap")),
            )
        )
    return source_as_of, members


def parse_invesco_json(payload: dict[str, Any]) -> tuple[str | None, list[Member]]:
    rows = payload.get("holdings")
    if not isinstance(rows, list):
        raise UniverseUpdateError("Invesco JSON holdings were not found")

    source_as_of = iso_date(
        clean_text(payload.get("effectiveBusinessDate"))
        or clean_text(payload.get("effectiveDate"))
    )
    members = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("securityTypeCode") or "").strip().upper() not in {
            "ADR",
            "COM",
            "DRNY",
        }:
            continue
        source_ticker = str(row.get("ticker") or "").strip().upper()
        try:
            ticker = normalize_ticker(source_ticker)
        except UniverseUpdateError:
            continue
        members.append(
            Member(
                ticker=ticker,
                source_ticker=source_ticker,
                company_name=clean_text(row.get("issuerName")),
                weight=optional_float(row.get("percentageOfTotalNetAssets")),
                market_value=optional_float(row.get("marketValueBase")),
            )
        )
    return source_as_of, members


def deduplicate_members(members: list[Member]) -> tuple[Member, ...]:
    by_ticker: dict[str, Member] = {}
    for member in members:
        by_ticker.setdefault(member.ticker, member)
    return tuple(sorted(by_ticker.values(), key=lambda item: item.ticker))


def checksum_members(members: tuple[Member, ...]) -> str:
    content = "\n".join(member.ticker for member in members).encode()
    return hashlib.sha256(content).hexdigest()


def validate_snapshot(
    source: SourceDefinition,
    members: tuple[Member, ...],
    previous_member_count: int | None = None,
    previous_members: set[str] | None = None,
) -> None:
    member_count = len(members)
    if not source.min_members <= member_count <= source.max_members:
        raise UniverseUpdateError(
            f"{source.id}: member count {member_count} is outside "
            f"{source.min_members}..{source.max_members}"
        )
    if len({member.ticker for member in members}) != member_count:
        raise UniverseUpdateError(f"{source.id}: duplicate normalized tickers remain")
    if previous_member_count:
        change_ratio = abs(member_count - previous_member_count) / previous_member_count
        if change_ratio > source.max_count_change_ratio:
            raise UniverseUpdateError(
                f"{source.id}: member count changed {change_ratio:.1%}; "
                f"limit is {source.max_count_change_ratio:.1%}"
            )
    if previous_members:
        current_members = {member.ticker for member in members}
        retained_ratio = len(current_members & previous_members) / len(previous_members)
        churn_ratio = 1 - retained_ratio
        if churn_ratio > source.max_membership_churn_ratio:
            raise UniverseUpdateError(
                f"{source.id}: membership churn is {churn_ratio:.1%}; "
                f"limit is {source.max_membership_churn_ratio:.1%}"
            )


def fetch_snapshot(
    session: requests.Session,
    source: SourceDefinition,
    previous_member_count: int | None = None,
    previous_members: set[str] | None = None,
) -> Snapshot:
    endpoints = (
        SourceEndpoint(
            source_label=source.source_label,
            source_url=source.source_url,
            adapter=source.adapter,
            is_proxy=source.is_proxy,
            proxy_note=source.proxy_note,
            read_timeout_seconds=source.read_timeout_seconds,
        ),
        *source.fallbacks,
    )
    failures = []

    for endpoint in endpoints:
        try:
            response = session.get(
                endpoint.request_url,
                timeout=(10, endpoint.read_timeout_seconds),
            )
            response.raise_for_status()
            if endpoint.adapter == "ishares_csv":
                source_as_of, raw_members = parse_ishares_csv(response.text)
            elif endpoint.adapter == "nasdaq_json":
                source_as_of, raw_members = parse_nasdaq_json(response.json())
            elif endpoint.adapter == "invesco_json":
                source_as_of, raw_members = parse_invesco_json(response.json())
            else:
                raise UniverseUpdateError(
                    f"unsupported adapter: {endpoint.adapter}"
                )

            validate_source_date(source.id, source_as_of)
            members = deduplicate_members(raw_members)
            validate_snapshot(
                source,
                members,
                previous_member_count,
                previous_members,
            )
            checksum = checksum_members(members)
            fetched_at = utc_now()
            version_date = source_as_of or fetched_at[:10]
            return Snapshot(
                source=source,
                effective_source=endpoint,
                source_as_of=source_as_of,
                fetched_at=fetched_at,
                checksum=checksum,
                version=f"{version_date}-{checksum[:12]}",
                members=members,
            )
        except (
            UniverseUpdateError,
            requests.RequestException,
            ValueError,
            KeyError,
            IndexError,
            AttributeError,
            TypeError,
        ) as exc:
            failures.append(f"{endpoint.source_label}: {exc}")

    raise UniverseUpdateError(
        "all configured sources failed (" + "; ".join(failures) + ")"
    )


class D1Client:
    def __init__(self, account_id: str, database_id: str, api_token: str):
        self.endpoint = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{account_id}/d1/database/{database_id}/query"
        )
        self.session = request_session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            }
        )

    @classmethod
    def from_environment(cls) -> D1Client:
        values = {
            "CLOUDFLARE_ACCOUNT_ID": os.environ.get("CLOUDFLARE_ACCOUNT_ID"),
            "D1_DATABASE_ID": os.environ.get("D1_DATABASE_ID"),
            "CLOUDFLARE_API_TOKEN": os.environ.get("CLOUDFLARE_API_TOKEN"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise UniverseUpdateError(
                f"missing D1 environment values: {', '.join(missing)}"
            )
        return cls(
            str(values["CLOUDFLARE_ACCOUNT_ID"]),
            str(values["D1_DATABASE_ID"]),
            str(values["CLOUDFLARE_API_TOKEN"]),
        )

    def query(self, sql: str, params: list[Any] | None = None) -> dict[str, Any]:
        response = self.session.post(
            self.endpoint,
            json={"sql": sql, "params": params or []},
            timeout=(10, 45),
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise UniverseUpdateError(f"D1 API rejected query: {payload.get('errors')}")
        result = payload.get("result")
        if not isinstance(result, list) or not result:
            raise UniverseUpdateError("D1 API returned no query result")
        first = result[0]
        if first.get("success") is False:
            raise UniverseUpdateError(f"D1 query failed: {first}")
        return first

    def current_member_count(self, universe_id: str) -> int | None:
        result = self.query(
            """SELECT v.member_count
               FROM universe_current AS c
               JOIN universe_versions AS v ON v.id = c.version_id
               WHERE c.universe_id = ?1""",
            [universe_id],
        )
        rows = result.get("results") or []
        return int(rows[0]["member_count"]) if rows else None

    def current_members(self, universe_id: str) -> set[str]:
        result = self.query(
            """SELECT m.ticker
               FROM universe_current AS c
               JOIN universe_members AS m ON m.version_id = c.version_id
               WHERE c.universe_id = ?1""",
            [universe_id],
        )
        return {str(row["ticker"]) for row in result.get("results") or []}

    def publish(self, snapshot: Snapshot) -> str:
        source = snapshot.source
        effective_source = snapshot.effective_source
        version_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL, f"backteststock:{source.id}:{snapshot.version}"
            )
        )
        existing = self.query(
            """SELECT
                 v.checksum, v.member_count,
                 CASE WHEN c.version_id = v.id THEN 1 ELSE 0 END AS is_current
               FROM universe_versions AS v
               LEFT JOIN universe_current AS c ON c.universe_id = v.universe_id
               WHERE v.id = ?1""",
            [version_id],
        )
        existing_rows = existing.get("results") or []
        can_reuse_members = False
        if existing_rows:
            row = existing_rows[0]
            verified = self.query(
                "SELECT COUNT(*) AS member_count FROM universe_members WHERE version_id = ?1",
                [version_id],
            )
            verified_count = int(verified["results"][0]["member_count"])
            can_reuse_members = (
                row["checksum"] == snapshot.checksum
                and int(row["member_count"]) == len(snapshot.members)
                and verified_count == len(snapshot.members)
            )
            if not can_reuse_members and int(row["is_current"]):
                raise UniverseUpdateError(
                    f"{source.id}: refusing to rebuild the currently active version"
                )

        self.query(
            """INSERT INTO universe_versions (
                 id, universe_id, version, source_as_of, fetched_at, source_label,
                 source_url, is_proxy, checksum, member_count, status, warning
               ) VALUES (
                 ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, 'staging', ?11
               )
               ON CONFLICT(universe_id, version) DO UPDATE SET
                 fetched_at = excluded.fetched_at,
                 source_label = excluded.source_label,
                 source_url = excluded.source_url,
                 is_proxy = excluded.is_proxy,
                 checksum = excluded.checksum,
                 member_count = excluded.member_count,
                 warning = excluded.warning""",
            [
                version_id,
                source.id,
                snapshot.version,
                snapshot.source_as_of,
                snapshot.fetched_at,
                effective_source.source_label,
                effective_source.source_url,
                int(effective_source.is_proxy),
                snapshot.checksum,
                len(snapshot.members),
                effective_source.proxy_note,
            ],
        )

        if not can_reuse_members:
            self.query(
                "DELETE FROM universe_members WHERE version_id = ?1", [version_id]
            )
            for start in range(0, len(snapshot.members), MEMBER_INSERT_CHUNK_SIZE):
                chunk = snapshot.members[start : start + MEMBER_INSERT_CHUNK_SIZE]
                placeholders = []
                params: list[Any] = []
                for member in chunk:
                    offset = len(params)
                    placeholders.append(
                        f"(?{offset + 1}, ?{offset + 2}, ?{offset + 3}, "
                        f"?{offset + 4}, ?{offset + 5}, ?{offset + 6}, ?{offset + 7})"
                    )
                    params.extend(
                        [
                            version_id,
                            member.ticker,
                            member.source_ticker,
                            member.company_name,
                            member.sector,
                            member.weight,
                            member.market_value,
                        ]
                    )
                self.query(
                    """INSERT OR REPLACE INTO universe_members (
                         version_id, ticker, source_ticker, company_name, sector,
                         weight, market_value
                       ) VALUES """
                    + ", ".join(placeholders),
                    params,
                )

        verified = self.query(
            "SELECT COUNT(*) AS member_count FROM universe_members WHERE version_id = ?1",
            [version_id],
        )
        verified_count = int(verified["results"][0]["member_count"])
        if verified_count != len(snapshot.members):
            raise UniverseUpdateError(
                f"{source.id}: D1 verification expected {len(snapshot.members)}, got {verified_count}"
            )

        self.query(
            "UPDATE universe_versions SET status = 'active' WHERE id = ?1",
            [version_id],
        )
        self.query(
            """INSERT INTO universe_current (universe_id, version_id, promoted_at)
               VALUES (?1, ?2, ?3)
               ON CONFLICT(universe_id) DO UPDATE SET
                 version_id = excluded.version_id,
                 promoted_at = excluded.promoted_at""",
            [source.id, version_id, utc_now()],
        )
        self.query(
            """UPDATE universe_versions
               SET status = 'archived'
               WHERE universe_id = ?1 AND id != ?2 AND status = 'active'""",
            [source.id, version_id],
        )
        self.query(
            """DELETE FROM universe_versions
               WHERE universe_id = ?1
                 AND id != ?2
                 AND id NOT IN (
                   SELECT id FROM universe_versions
                   WHERE universe_id = ?1
                   ORDER BY fetched_at DESC
                   LIMIT ?3
                 )""",
            [source.id, version_id, MAX_RETAINED_VERSIONS],
        )
        return version_id


def snapshot_report(
    snapshot: Snapshot, published: bool, version_id: str | None
) -> dict[str, Any]:
    effective_source = snapshot.effective_source
    return {
        "id": snapshot.source.id,
        "name": snapshot.source.name,
        "source": effective_source.source_label,
        "sourceUrl": effective_source.source_url,
        "sourceAsOf": snapshot.source_as_of,
        "fetchedAt": snapshot.fetched_at,
        "version": snapshot.version,
        "checksum": snapshot.checksum,
        "memberCount": len(snapshot.members),
        "published": published,
        "versionId": version_id,
        "isProxy": effective_source.is_proxy,
        "proxyNote": effective_source.proxy_note,
        "fallbackUsed": effective_source.source_url != snapshot.source.source_url,
    }


def update_all(publish: bool) -> tuple[dict[str, Any], bool]:
    session = request_session()
    d1 = D1Client.from_environment() if publish else None
    report: dict[str, Any] = {
        "startedAt": utc_now(),
        "mode": "publish" if publish else "dry-run",
        "universes": [],
        "errors": [],
    }

    for source in SOURCES:
        try:
            previous_members = d1.current_members(source.id) if d1 else None
            previous_count = len(previous_members) if previous_members else None
            snapshot = fetch_snapshot(
                session,
                source,
                previous_member_count=previous_count,
                previous_members=previous_members,
            )
            version_id = d1.publish(snapshot) if d1 else None
            report["universes"].append(snapshot_report(snapshot, publish, version_id))
            print(
                f"{source.id}: validated {len(snapshot.members)} members "
                f"({snapshot.version}){' and published' if publish else ''}"
            )
        except (
            UniverseUpdateError,
            requests.RequestException,
            ValueError,
            KeyError,
            IndexError,
            AttributeError,
            TypeError,
        ) as exc:
            message = f"{source.id}: {exc}"
            report["errors"].append(message)
            print(message, file=sys.stderr)

    report["finishedAt"] = utc_now()
    report["success"] = not report["errors"] and len(report["universes"]) == len(
        SOURCES
    )
    return report, bool(report["success"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish validated snapshots to the configured Cloudflare D1 database.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help=f"JSON report path (default: {DEFAULT_REPORT_PATH}).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report, success = update_all(args.publish)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
