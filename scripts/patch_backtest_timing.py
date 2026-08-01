from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "api/index_v2.py"


def replace_once(content: str, old: str, new: str, label: str) -> str:
    count = content.count(old)
    if count != 1:
        raise SystemExit(f"api/index_v2.py: {label} expected once, found {count}")
    return content.replace(old, new, 1)


def main() -> None:
    content = PATH.read_text(encoding="utf-8")
    content = replace_once(
        content,
        "import logging\n",
        "import logging\nimport time\n",
        "time import",
    )
    content = replace_once(
        content,
        "def backtest_handler():\n    try:\n        data = legacy.require_json_object()",
        "def backtest_handler():\n    request_started = time.perf_counter()\n"
        "    try:\n        data = legacy.require_json_object()",
        "request timer",
    )
    content = replace_once(
        content,
        '''        prices_raw = download_data_silently(
            tuple(sorted(required_tickers)),
            start_date.strftime("%Y-%m-%d"),
            end_exclusive.strftime("%Y-%m-%d"),
        )
        action_audits = dict(
''',
        '''        market_started = time.perf_counter()
        prices_raw = download_data_silently(
            tuple(sorted(required_tickers)),
            start_date.strftime("%Y-%m-%d"),
            end_exclusive.strftime("%Y-%m-%d"),
        )
        market_ms = (time.perf_counter() - market_started) * 1000
        compute_started = time.perf_counter()
        action_audits = dict(
''',
        "market phase",
    )
    content = replace_once(
        content,
        '''        return legacy.jsonify(
            {
                "data": results,
                "benchmark": benchmark_result,
                "warning": "；".join(warning_parts) if warning_parts else None,
                "metadata": metadata,
            }
        )
''',
        '''        payload = {
            "data": results,
            "benchmark": benchmark_result,
            "warning": "；".join(warning_parts) if warning_parts else None,
            "metadata": metadata,
        }
        compute_ms = (time.perf_counter() - compute_started) * 1000
        serialize_started = time.perf_counter()
        response = legacy.jsonify(payload)
        serialize_ms = (time.perf_counter() - serialize_started) * 1000
        total_ms = (time.perf_counter() - request_started) * 1000
        timing = (
            f"market;dur={market_ms:.1f}, compute;dur={compute_ms:.1f}, "
            f"serialize;dur={serialize_ms:.1f}, total;dur={total_ms:.1f}"
        )
        response.headers["Server-Timing"] = timing
        response.headers["X-Backend-Server-Timing"] = timing
        response.headers["X-Backtest-Requested"] = str(len(required_tickers))
        response.headers["X-Backtest-Resolved"] = str(
            len(required_tickers) - len(failed_tickers)
        )
        return response
''',
        "timed response",
    )
    PATH.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
