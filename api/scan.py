import logging
import math
import os
import re
import threading
import time
from collections.abc import Iterable

import numpy as np
import pandas as pd
import yfinance as yf
from cachetools import TTLCache
from flask import Flask, jsonify, request

app = Flask(__name__)
logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252
DAYS_PER_YEAR = 365.25
EPSILON = 1e-9
MIN_YEAR = 1980
MAX_SCAN_TICKERS = 100
MARKET_DATA_ATTEMPTS = 3
MARKET_DATA_BACKOFF_SECONDS = (0.0, 1.5, 5.0)
MARKET_DATA_TIMEOUT_SECONDS = 12
MARKET_DATA_DOWNLOAD_THREADS = 16
TICKER_PATTERN = re.compile(r"^[A-Z0-9.^=_-]{1,20}$")

try:
    RISK_FREE_RATE = float(os.environ.get("RISK_FREE_RATE", "0"))
except ValueError:
    RISK_FREE_RATE = 0.0

_price_cache = TTLCache(maxsize=512, ttl=3600)
_price_cache_lock = threading.RLock()


class ValidationError(ValueError):
    """Raised when a scan request is invalid."""


@app.after_request
def add_headers(response):
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response


def normalize_ticker(value):
    ticker = str(value or "").strip().upper()
    if not TICKER_PATTERN.fullmatch(ticker):
        raise ValidationError(f"無效的股票代碼：{ticker or '(空白)'}")
    return ticker


def deduplicate(values: Iterable[str]):
    return list(dict.fromkeys(values))


def parse_period(data):
    try:
        start_year = int(data["startYear"])
        start_month = int(data["startMonth"])
        end_year = int(data["endYear"])
        end_month = int(data["endMonth"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("起訖年月格式不正確。") from exc

    current_year = pd.Timestamp.now(tz="UTC").year
    if not (
        MIN_YEAR <= start_year <= current_year
        and MIN_YEAR <= end_year <= current_year
    ):
        raise ValidationError(f"年份必須介於 {MIN_YEAR} 與 {current_year} 之間。")
    if not (1 <= start_month <= 12 and 1 <= end_month <= 12):
        raise ValidationError("月份必須介於 1 與 12 之間。")

    start_date = pd.Timestamp(start_year, start_month, 1)
    end_exclusive = pd.Timestamp(end_year, end_month, 1) + pd.offsets.MonthBegin(1)
    if start_date >= end_exclusive:
        raise ValidationError("結束年月必須晚於起始年月。")
    return start_date, end_exclusive


def normalize_price_series(raw_prices, ticker):
    if raw_prices is None:
        return None
    prices = pd.to_numeric(raw_prices, errors="coerce").dropna().astype(float)
    prices = prices[prices > 0]
    if prices.empty:
        return None

    index = pd.DatetimeIndex(pd.to_datetime(prices.index))
    if index.tz is not None:
        index = index.tz_convert(None)
    prices.index = index.normalize()
    prices = prices[~prices.index.duplicated(keep="last")].sort_index()
    prices.name = ticker
    return prices


def extract_close_prices(downloaded, tickers):
    if not isinstance(downloaded, pd.DataFrame) or downloaded.empty:
        return {}

    if isinstance(downloaded.columns, pd.MultiIndex):
        level_zero = downloaded.columns.get_level_values(0)
        level_one = downloaded.columns.get_level_values(1)
        if "Close" in level_zero:
            close_prices = downloaded.xs("Close", axis=1, level=0)
        elif "Close" in level_one:
            close_prices = downloaded.xs("Close", axis=1, level=1)
        else:
            return {}
    elif "Close" in downloaded.columns:
        close_prices = downloaded["Close"]
    else:
        return {}

    extracted = {}
    for ticker in tickers:
        raw_prices = None
        if isinstance(close_prices, pd.Series):
            if len(tickers) == 1:
                raw_prices = close_prices
        elif ticker in close_prices.columns:
            raw_prices = close_prices[ticker]
        prices = normalize_price_series(raw_prices, ticker)
        if prices is not None:
            extracted[ticker] = prices
    return extracted


def bulk_download_prices(tickers, start_date, end_date, *, use_threads=True):
    """Keep the original site's simple multi-symbol yfinance request shape."""
    thread_count = min(MARKET_DATA_DOWNLOAD_THREADS, max(len(tickers), 1))
    return yf.download(
        list(tickers),
        start=start_date,
        end=end_date,
        auto_adjust=True,
        progress=False,
        threads=thread_count if use_threads else False,
        timeout=MARKET_DATA_TIMEOUT_SECONDS,
        group_by="column",
        multi_level_index=True,
    )


def download_prices_finitely(tickers, start_date, end_date):
    """Resolve symbols in a few large requests and always stop after a finite budget."""
    requested = deduplicate(tickers)
    resolved = {}
    pending = []
    cache_keys = {ticker: (ticker, start_date, end_date) for ticker in requested}

    with _price_cache_lock:
        for ticker in requested:
            cached_prices = _price_cache.get(cache_keys[ticker])
            if cached_prices is None:
                pending.append(ticker)
            else:
                resolved[ticker] = cached_prices.copy()

    errors = []
    for attempt, delay in enumerate(MARKET_DATA_BACKOFF_SECONDS[:MARKET_DATA_ATTEMPTS], start=1):
        if not pending:
            break
        if delay:
            time.sleep(delay)

        current = list(pending)
        try:
            downloaded = bulk_download_prices(
                current,
                start_date,
                end_date,
                use_threads=attempt < MARKET_DATA_ATTEMPTS,
            )
            extracted = extract_close_prices(downloaded, current)
        except Exception as exc:
            logger.warning(
                "Market data request failed",
                extra={"attempt": attempt, "ticker_count": len(current)},
                exc_info=exc,
            )
            errors.append(exc)
            extracted = {}

        pending = []
        for ticker in current:
            prices = extracted.get(ticker)
            if prices is None:
                pending.append(ticker)
                continue
            resolved[ticker] = prices
            with _price_cache_lock:
                _price_cache[cache_keys[ticker]] = prices.copy()

    if pending:
        logger.warning(
            "Market data remained incomplete after finite retries",
            extra={
                "requested_count": len(requested),
                "resolved_count": len(resolved),
                "unresolved_count": len(pending),
                "error_count": len(errors),
            },
        )
    return resolved, pending


def calculate_metrics(values, benchmark_values=None):
    values = values.dropna().astype(float)
    empty = {
        "total_return": 0.0,
        "cagr": 0.0,
        "mdd": 0.0,
        "volatility": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "beta": None,
        "alpha": None,
    }
    if len(values) < 2 or values.iloc[0] <= EPSILON:
        return empty

    total_return = float(values.iloc[-1] / values.iloc[0] - 1)
    years = (values.index[-1] - values.index[0]).days / DAYS_PER_YEAR
    cagr = float((values.iloc[-1] / values.iloc[0]) ** (1 / years) - 1) if years > 0 else 0.0
    drawdown = values / values.cummax() - 1
    mdd = float(drawdown.min())
    returns = values.pct_change().dropna()
    if len(returns) < 2:
        return {**empty, "total_return": total_return, "cagr": cagr, "mdd": mdd}

    volatility = float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
    sharpe = float((cagr - RISK_FREE_RATE) / (volatility + EPSILON))
    daily_risk_free = (1 + RISK_FREE_RATE) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    downside = (returns - daily_risk_free).clip(upper=0)
    downside_deviation = float(np.sqrt((downside**2).mean()) * np.sqrt(TRADING_DAYS_PER_YEAR))
    sortino = float((cagr - RISK_FREE_RATE) / downside_deviation) if downside_deviation > EPSILON else 0.0

    beta = None
    alpha = None
    if benchmark_values is not None:
        benchmark = benchmark_values.dropna().astype(float)
        benchmark_returns = benchmark.pct_change().dropna()
        aligned = pd.concat([returns, benchmark_returns], axis=1, join="inner").dropna()
        if len(aligned) > 1:
            aligned.columns = ["asset", "benchmark"]
            benchmark_variance = float(aligned["benchmark"].var())
            if benchmark_variance > EPSILON:
                beta = float(aligned["asset"].cov(aligned["benchmark"]) / benchmark_variance)
                benchmark_years = (benchmark.index[-1] - benchmark.index[0]).days / DAYS_PER_YEAR
                benchmark_cagr = (
                    float((benchmark.iloc[-1] / benchmark.iloc[0]) ** (1 / benchmark_years) - 1)
                    if benchmark_years > 0 and benchmark.iloc[0] > EPSILON
                    else 0.0
                )
                alpha = float(cagr - (RISK_FREE_RATE + beta * (benchmark_cagr - RISK_FREE_RATE)))

    return {
        "total_return": total_return,
        "cagr": cagr,
        "mdd": mdd,
        "volatility": volatility,
        "sharpe_ratio": sharpe if math.isfinite(sharpe) else 0.0,
        "sortino_ratio": sortino if math.isfinite(sortino) else 0.0,
        "beta": beta if beta is None or math.isfinite(beta) else None,
        "alpha": alpha if alpha is None or math.isfinite(alpha) else None,
    }


def terminal_failure(ticker, message="行情資料無法取得（已完成有限次批次重試）。"):
    return {
        "ticker": ticker,
        "status": "failed",
        "retryable": False,
        "error_code": "market_data_unavailable",
        "error": message,
    }


@app.route("/api/scan", methods=["POST"])
def scan_handler():
    raw_tickers = []
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValidationError("請提供有效的 JSON 物件。")

        raw_tickers = data.get("tickers")
        if not isinstance(raw_tickers, list) or not raw_tickers:
            raise ValidationError("股票代碼列表不可為空。")
        tickers = deduplicate(normalize_ticker(ticker) for ticker in raw_tickers)
        if len(tickers) > MAX_SCAN_TICKERS:
            raise ValidationError(f"單次最多掃描 {MAX_SCAN_TICKERS} 檔標的。")
        if not data.get("benchmark"):
            raise ValidationError("請指定比較基準，以完整計算 Beta 與 Alpha。")

        benchmark_ticker = normalize_ticker(data["benchmark"])
        start_date, end_exclusive = parse_period(data)
        start_text = start_date.strftime("%Y-%m-%d")
        end_text = end_exclusive.strftime("%Y-%m-%d")
        resolved, unresolved = download_prices_finitely(
            deduplicate([*tickers, benchmark_ticker]),
            start_text,
            end_text,
        )
        unresolved_set = set(unresolved)
        benchmark_prices = resolved.get(benchmark_ticker)
        benchmark_available = (
            benchmark_ticker not in unresolved_set
            and benchmark_prices is not None
            and not benchmark_prices.empty
        )

        requested_business_days = max(
            len(pd.bdate_range(start_date, end_exclusive - pd.Timedelta(days=1))),
            1,
        )
        results = []
        for ticker in tickers:
            prices = resolved.get(ticker)
            if ticker in unresolved_set or prices is None or prices.empty:
                results.append(terminal_failure(ticker))
                continue

            notes = []
            if prices.index[0] > start_date + pd.offsets.BDay(5):
                notes.append(f"從 {prices.index[0].strftime('%Y-%m-%d')} 開始")
            if not benchmark_available:
                notes.append("比較基準行情無法取得，Beta／Alpha 暫不計算")

            metrics = calculate_metrics(
                prices,
                benchmark_prices if benchmark_available else None,
            )
            results.append(
                {
                    "ticker": ticker,
                    "status": "ok",
                    "retryable": False,
                    **metrics,
                    "data_start": prices.index[0].strftime("%Y-%m-%d"),
                    "data_end": prices.index[-1].strftime("%Y-%m-%d"),
                    "trading_days": len(prices),
                    "data_coverage": min(len(prices) / requested_business_days, 1.0),
                    "note": f"（{'；'.join(notes)}）" if notes else None,
                }
            )
        return jsonify(results)
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("Unexpected error in finite scan endpoint")
        safe_tickers = []
        if isinstance(raw_tickers, list):
            for raw in raw_tickers[:MAX_SCAN_TICKERS]:
                try:
                    safe_tickers.append(normalize_ticker(raw))
                except ValidationError:
                    continue
        if safe_tickers:
            return jsonify(
                [
                    terminal_failure(ticker, "回測服務發生未預期錯誤；本批已停止，不會無限重試。")
                    for ticker in deduplicate(safe_tickers)
                ]
            )
        return jsonify({"error": "伺服器發生未預期的錯誤。"}), 500
