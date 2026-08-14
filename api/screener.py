import logging
import math
import os
import re
from datetime import UTC, datetime

import requests
from cachetools import TTLCache, cached
from flask import Flask, jsonify, request

from api.request_guard import (
    MAX_REQUEST_BYTES,
    authorize_edge_request,
    request_body_failure,
)

app = Flask(__name__)
logger = logging.getLogger(__name__)
app.config.setdefault("MAX_CONTENT_LENGTH", MAX_REQUEST_BYTES)

TICKER_PATTERN = re.compile(r"^[A-Z0-9.^=_-]{1,20}$")
MAX_UNIVERSE_MEMBERS = 3_000
ALLOWED_SCREENER_SORTS = {
    "marketCap-desc",
    "marketCap-asc",
    "trailingPE-asc",
    "ticker-asc",
}
SCREENER_NUMERIC_FIELDS = {
    "marketCap",
    "trailingPE",
    "dividendYield",
    "returnOnEquity",
    "revenueGrowth",
    "earningsGrowth",
}
FILTER_LABELS = {
    "marketCap": "市值",
    "trailingPE": "本益比",
    "dividendYield": "殖利率",
    "returnOnEquity": "股東權益報酬率",
    "revenueGrowth": "營收成長率",
    "earningsGrowth": "獲利成長率",
}
NASDAQ_SECTOR_MAP = {
    "Technology": "Technology",
    "Telecommunications": "Communication Services",
    "Health Care": "Healthcare",
    "Consumer Discretionary": "Consumer Cyclical",
    "Consumer Staples": "Consumer Defensive",
    "Finance": "Financial Services",
    "Industrials": "Industrials",
    "Energy": "Energy",
    "Real Estate": "Real Estate",
    "Basic Materials": "Basic Materials",
    "Utilities": "Utilities",
}
NASDAQ_STOCK_SCREENER_URL = os.environ.get(
    "NASDAQ_STOCK_SCREENER_URL",
    "https://api.nasdaq.com/api/screener/stocks"
    "?tableonly=true&limit=10000&offset=0&download=true",
)
GIST_RAW_URL = os.environ.get("GIST_RAW_URL")
DATASET_CACHE = TTLCache(maxsize=8, ttl=900)


class ValidationError(ValueError):
    """Raised when a screener request is invalid."""


class DataSourceError(RuntimeError):
    """Raised when all configured screener sources fail."""


@app.after_request
def add_headers(response):
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response


def normalize_ticker(value):
    ticker = (
        str(value or "")
        .strip()
        .upper()
        .replace("/", "-")
        .replace(".", "-")
    )
    if not TICKER_PATTERN.fullmatch(ticker):
        raise ValidationError(f"無效的股票代碼：{ticker or '(空白)'}")
    return ticker


def optional_float(value):
    text = str(value or "").replace(",", "").replace("$", "").strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "-"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def clean_text(value):
    text = " ".join(str(value or "").split())
    return text or None


def normalize_sector(value):
    sector = clean_text(value)
    if not sector:
        return None
    return NASDAQ_SECTOR_MAP.get(sector, sector)


def request_headers():
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/market-activity/stocks/screener",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
    }


@cached(DATASET_CACHE)
def get_nasdaq_dataset():
    response = requests.get(
        NASDAQ_STOCK_SCREENER_URL,
        headers=request_headers(),
        timeout=(8, 35),
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) < 1_000:
        raise DataSourceError("Nasdaq 股票篩選資料回傳不完整。")

    records = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            ticker = normalize_ticker(row.get("symbol"))
        except ValidationError:
            continue
        record = {
            "ticker": ticker,
            "name": clean_text(row.get("name")),
            "companyName": clean_text(row.get("name")),
            "sector": normalize_sector(row.get("sector")),
            "industry": clean_text(row.get("industry")),
            "marketCap": optional_float(row.get("marketCap")),
        }
        records.append({key: value for key, value in record.items() if value is not None})

    if len(records) < 1_000:
        raise DataSourceError("Nasdaq 股票代碼正規化後數量異常。")
    return {
        "data": records,
        "asOf": clean_text(data.get("asOf")) or datetime.now(UTC).date().isoformat(),
        "warning": (
            "基本面廣覆蓋資料由 Nasdaq 官方股票篩選清單補足；該清單提供股票代碼、"
            "市值、產業與產業別，但不提供本益比、ROE 與成長率。設定缺少欄位的條件時，"
            "只有具備該欄位的補充資料可通過。"
        ),
        "source": "Nasdaq official stock screener",
    }


@cached(DATASET_CACHE)
def get_gist_dataset():
    if not GIST_RAW_URL:
        raise DataSourceError("GIST_RAW_URL 環境變數未設定。")
    response = requests.get(GIST_RAW_URL, timeout=(5, 15))
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, list):
        return {"data": payload, "asOf": None, "warning": None, "source": "Gist"}
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise DataSourceError("預處理股票資料格式不正確。")
    return {
        "data": payload["data"],
        "asOf": payload.get("asOf"),
        "warning": payload.get("warning"),
        "source": "Gist preprocessed fundamentals",
    }


def normalized_records(raw_records):
    records = {}
    for stock in raw_records:
        if not isinstance(stock, dict):
            continue
        try:
            ticker = normalize_ticker(stock.get("ticker"))
        except ValidationError:
            continue
        records[ticker] = {**stock, "ticker": ticker}
    return records


def merge_datasets(nasdaq_dataset, gist_dataset):
    merged = normalized_records(nasdaq_dataset.get("data", []))
    for ticker, stock in normalized_records(gist_dataset.get("data", [])).items():
        existing = merged.get(ticker, {"ticker": ticker})
        merged[ticker] = {
            **existing,
            **{key: value for key, value in stock.items() if value is not None},
        }

    warnings = []
    for dataset in (nasdaq_dataset, gist_dataset):
        warning = dataset.get("warning")
        if warning and str(warning) not in warnings:
            warnings.append(str(warning))
    return {
        "data": list(merged.values()),
        "asOf": gist_dataset.get("asOf") or nasdaq_dataset.get("asOf"),
        "warnings": warnings,
        "sources": [nasdaq_dataset.get("source"), gist_dataset.get("source")],
    }


@cached(DATASET_CACHE)
def get_comprehensive_dataset():
    errors = []
    nasdaq_dataset = None
    gist_dataset = None
    try:
        nasdaq_dataset = get_nasdaq_dataset()
    except (DataSourceError, requests.RequestException, ValueError, TypeError) as exc:
        errors.append(f"Nasdaq: {exc}")
    try:
        gist_dataset = get_gist_dataset()
    except (DataSourceError, requests.RequestException, ValueError, TypeError) as exc:
        errors.append(f"Gist: {exc}")

    if nasdaq_dataset and gist_dataset:
        return merge_datasets(nasdaq_dataset, gist_dataset)
    if nasdaq_dataset:
        return {
            "data": nasdaq_dataset["data"],
            "asOf": nasdaq_dataset.get("asOf"),
            "warnings": [nasdaq_dataset["warning"]] if nasdaq_dataset.get("warning") else [],
            "sources": [nasdaq_dataset.get("source")],
        }
    if gist_dataset:
        return {
            "data": gist_dataset["data"],
            "asOf": gist_dataset.get("asOf"),
            "warnings": [gist_dataset["warning"]] if gist_dataset.get("warning") else [],
            "sources": [gist_dataset.get("source")],
        }
    raise DataSourceError("所有基本面資料來源均不可用（" + "; ".join(errors) + "）。")


def require_json_object():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("請提供有效的 JSON 物件。")
    return data


def normalize_universe_snapshot(raw_snapshot):
    if not isinstance(raw_snapshot, dict):
        raise ValidationError("Universe 快照格式不正確。")
    universe_id = str(raw_snapshot.get("id") or "").strip().lower()
    version = str(raw_snapshot.get("version") or "").strip()
    raw_members = raw_snapshot.get("members")
    if not universe_id or not version or not isinstance(raw_members, list):
        raise ValidationError("Universe 快照缺少必要欄位。")
    if not raw_members or len(raw_members) > MAX_UNIVERSE_MEMBERS:
        raise ValidationError(
            f"Universe 成分股數量必須介於 1 與 {MAX_UNIVERSE_MEMBERS} 之間。"
        )

    members = []
    seen = set()
    for raw_member in raw_members:
        ticker = raw_member.get("ticker") if isinstance(raw_member, dict) else raw_member
        normalized = normalize_ticker(ticker)
        if normalized not in seen:
            members.append(normalized)
            seen.add(normalized)
    return {
        "id": universe_id,
        "name": str(raw_snapshot.get("name") or universe_id).strip()[:120],
        "version": version[:120],
        "sourceAsOf": raw_snapshot.get("sourceAsOf"),
        "fetchedAt": raw_snapshot.get("fetchedAt"),
        "proxyNote": raw_snapshot.get("proxyNote"),
        "members": members,
    }


def stock_matches_filters(stock, filters):
    for field, limits in filters.items():
        if field not in SCREENER_NUMERIC_FIELDS or not isinstance(limits, dict):
            continue
        value = optional_float(stock.get(field))
        if value is None:
            return False
        minimum = optional_float(limits.get("min")) if "min" in limits else None
        maximum = optional_float(limits.get("max")) if "max" in limits else None
        if minimum is not None and value < minimum:
            return False
        if maximum is not None and value > maximum:
            return False
    return True


def missing_filter_fields(stock, filters):
    return [
        field
        for field, limits in filters.items()
        if field in SCREENER_NUMERIC_FIELDS
        and isinstance(limits, dict)
        and optional_float(stock.get(field)) is None
    ]


def candidate_from_stock(stock, ticker):
    candidate = {"ticker": ticker}
    for field in (
        "name",
        "companyName",
        "sector",
        "industry",
        "marketCap",
        "trailingPE",
        "dividendYield",
        "returnOnEquity",
        "revenueGrowth",
        "earningsGrowth",
    ):
        value = stock.get(field)
        if value is not None:
            candidate[field] = value
    return candidate


def sort_screener_candidates(candidates, sort_name):
    def numeric_value(candidate, field, missing):
        value = optional_float(candidate.get(field))
        return value if value is not None else missing

    if sort_name == "marketCap-asc":
        return sorted(
            candidates,
            key=lambda item: (numeric_value(item, "marketCap", math.inf), item["ticker"]),
        )
    if sort_name == "trailingPE-asc":
        return sorted(
            candidates,
            key=lambda item: (numeric_value(item, "trailingPE", math.inf), item["ticker"]),
        )
    if sort_name == "ticker-asc":
        return sorted(candidates, key=lambda item: item["ticker"])
    return sorted(
        candidates,
        key=lambda item: (-numeric_value(item, "marketCap", -math.inf), item["ticker"]),
    )


def error_response(message, status):
    return jsonify({"error": message}), status


@app.before_request
def enforce_screener_request_guard():
    """Protect cached-but-expensive fundamentals reads at the origin."""

    if request.path not in {
        "/api/v2/screener",
        "/api/screener",
        "/api/all-tickers",
    }:
        return None

    identity = authorize_edge_request(
        request.headers,
        fallback_client_id=request.remote_addr or "unknown",
    )
    if not hasattr(identity, "client_id"):
        return error_response(identity.message, identity.status_code)

    body = None
    if request.method in {"POST", "PUT", "PATCH"}:
        body = request.get_data(cache=True, parse_form_data=False)
    failure = request_body_failure(
        request.headers,
        body,
        maximum_bytes=MAX_REQUEST_BYTES,
        message="Screener request body is too large.",
    )
    if failure:
        return error_response(failure.message, failure.status_code)
    return None


@app.route("/api/v2/screener", methods=["POST"])
def screener_v2_handler():
    try:
        data = require_json_object()
        snapshot = normalize_universe_snapshot(data.get("_universe"))
        sector = str(data.get("sector") or "any").strip()
        filters = data.get("filters") if isinstance(data.get("filters"), dict) else {}
        sort_name = str(data.get("sort") or "marketCap-desc")
        if sort_name not in ALLOWED_SCREENER_SORTS:
            raise ValidationError("不支援的排序方式。")

        raw_limit = data.get("limit")
        limit = None
        if raw_limit not in (None, ""):
            try:
                limit = int(raw_limit)
            except (TypeError, ValueError) as exc:
                raise ValidationError("回測檔數上限格式不正確。") from exc
            if limit < 1:
                raise ValidationError("回測檔數上限必須大於 0，留空則回測全部。")

        dataset = get_comprehensive_dataset()
        fundamentals = normalized_records(dataset["data"])
        candidates = []
        fundamentals_available = 0
        sector_matches = 0
        missing_by_field = {field: 0 for field in SCREENER_NUMERIC_FIELDS}

        for ticker in snapshot["members"]:
            stock = fundamentals.get(ticker)
            if stock is None:
                continue
            fundamentals_available += 1
            if sector != "any" and stock.get("sector") != sector:
                continue
            sector_matches += 1
            missing_fields = missing_filter_fields(stock, filters)
            if missing_fields:
                for field in missing_fields:
                    missing_by_field[field] += 1
                continue
            if not stock_matches_filters(stock, filters):
                continue
            candidates.append(candidate_from_stock(stock, ticker))

        candidates = sort_screener_candidates(candidates, sort_name)
        passed_filters = len(candidates)
        selected = candidates if limit is None else candidates[:limit]
        truncated = limit is not None and passed_filters > limit

        warnings = []
        if snapshot["proxyNote"]:
            warnings.append(snapshot["proxyNote"])
        warnings.extend(dataset.get("warnings") or [])
        missing_fundamentals = len(snapshot["members"]) - fundamentals_available
        if missing_fundamentals:
            warnings.append(
                f"{missing_fundamentals} 檔 Universe 成分股未在目前廣覆蓋資料中找到，未納入條件篩選。"
            )
        for field, count in missing_by_field.items():
            if count:
                warnings.append(
                    f"{count} 檔缺少{FILTER_LABELS.get(field, field)}欄位，無法驗證該條件，因此未納入。"
                )
        if truncated:
            warnings.append(
                f"共有 {passed_filters} 檔通過條件；依「{sort_name}」明確取前 {limit} 檔供回測。"
            )

        return jsonify(
            {
                "universe": {
                    key: snapshot[key]
                    for key in (
                        "id",
                        "name",
                        "version",
                        "sourceAsOf",
                        "fetchedAt",
                        "proxyNote",
                    )
                },
                "fundamentalsAsOf": dataset.get("asOf"),
                "fundamentalsSources": [source for source in dataset.get("sources", []) if source],
                "funnel": {
                    "universeCount": len(snapshot["members"]),
                    "fundamentalsAvailable": fundamentals_available,
                    "sectorMatches": sector_matches,
                    "passedFilters": passed_filters,
                    "selectedForScan": len(selected),
                },
                "candidates": selected,
                "truncated": truncated,
                "sort": sort_name,
                "limit": limit,
                "warnings": warnings,
            }
        )
    except ValidationError as exc:
        return error_response(str(exc), 400)
    except (DataSourceError, requests.RequestException) as exc:
        logger.error("V2 screener data source error: %s", exc)
        return error_response("篩選器基本面資料來源暫時無法取得。", 503)
    except Exception:
        logger.exception("Unexpected error in v2 screener endpoint")
        return error_response("篩選器發生未預期的錯誤。", 500)


@app.route("/api/screener", methods=["POST"])
def screener_handler():
    try:
        data = require_json_object()
        index_name = str(data.get("index") or "sp500")
        sector = str(data.get("sector") or "any")
        filters = data.get("filters") if isinstance(data.get("filters"), dict) else {}
        if "minMarketCap" in data and "marketCap" not in filters:
            filters = {**filters, "marketCap": {"min": data.get("minMarketCap", 0)}}

        dataset = get_comprehensive_dataset()
        membership_fields = {
            "sp500": "in_sp500",
            "nasdaq100": "in_nasdaq100",
            "russell3000": "in_russell3000",
        }
        membership_field = membership_fields.get(index_name)
        filtered = []
        for stock in dataset["data"]:
            if not isinstance(stock, dict):
                continue
            if membership_field and not stock.get(membership_field):
                continue
            if sector != "any" and stock.get("sector") != sector:
                continue
            if not stock_matches_filters(stock, filters):
                continue
            try:
                filtered.append(normalize_ticker(stock.get("ticker")))
            except ValidationError:
                continue
        return jsonify(sorted(set(filtered)))
    except ValidationError as exc:
        return error_response(str(exc), 400)
    except (DataSourceError, requests.RequestException):
        return error_response("篩選器資料來源暫時無法取得。", 503)
    except Exception:
        logger.exception("Unexpected error in legacy screener endpoint")
        return error_response("篩選器發生未預期的錯誤。", 500)


@app.route("/api/all-tickers", methods=["GET"])
def all_tickers_handler():
    try:
        dataset = get_comprehensive_dataset()
        tickers = []
        for stock in dataset["data"]:
            if not isinstance(stock, dict):
                continue
            try:
                tickers.append(normalize_ticker(stock.get("ticker")))
            except ValidationError:
                continue
        return jsonify(sorted(set(tickers)))
    except (DataSourceError, requests.RequestException):
        return error_response("股票清單資料來源暫時無法取得。", 503)
    except Exception:
        logger.exception("Unexpected error in all-tickers endpoint")
        return error_response("股票清單暫時無法取得。", 500)
