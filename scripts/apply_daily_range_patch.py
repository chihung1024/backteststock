from __future__ import annotations

import re
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise SystemExit(
            f"{path}: expected one replacement anchor, found {count}; anchor={old!r}"
        )
    write(path, content.replace(old, new, 1))


def replace_regex_once(path: str, pattern: str, replacement: str) -> None:
    content = read(path)
    updated, count = re.subn(
        pattern,
        lambda _match: replacement,
        content,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise SystemExit(f"{path}: regex replacement did not match exactly once")
    write(path, updated)


def patch_backend_period() -> None:
    replacement = textwrap.dedent(
        r'''
        def _parse_iso_date(value, label):
            raw = str(value or "").strip()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                raise ValidationError(f"{label}格式必須為 YYYY-MM-DD。")
            try:
                parsed = pd.Timestamp(raw)
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"{label}不是有效日期。") from exc
            if parsed.strftime("%Y-%m-%d") != raw:
                raise ValidationError(f"{label}不是有效日期。")
            return parsed.normalize()


        def parse_period(data):
            start_date_value = data.get("startDate")
            end_date_value = data.get("endDate")
            if start_date_value is not None or end_date_value is not None:
                if not start_date_value or not end_date_value:
                    raise ValidationError("起始日期與結束日期必須同時提供。")
                start_date = _parse_iso_date(start_date_value, "起始日期")
                end_inclusive = _parse_iso_date(end_date_value, "結束日期")
                current_date = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
                if start_date.year < MIN_YEAR:
                    raise ValidationError(f"起始日期不得早於 {MIN_YEAR}-01-01。")
                if end_inclusive > current_date:
                    raise ValidationError("結束日期不得晚於今天。")
                if start_date > end_inclusive:
                    raise ValidationError("結束日期必須晚於或等於起始日期。")
                return start_date, end_inclusive + pd.Timedelta(days=1)

            try:
                start_year = int(data["startYear"])
                start_month = int(data["startMonth"])
                end_year = int(data["endYear"])
                end_month = int(data["endMonth"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValidationError("請提供有效的起訖日期或起訖年月。") from exc

            current_year = pd.Timestamp.now(tz="UTC").year
            if not (
                MIN_YEAR <= start_year <= current_year
                and MIN_YEAR <= end_year <= current_year
            ):
                raise ValidationError(
                    f"年份必須介於 {MIN_YEAR} 與 {current_year} 之間。"
                )
            if not (1 <= start_month <= 12 and 1 <= end_month <= 12):
                raise ValidationError("月份必須介於 1 與 12 之間。")

            start_date = pd.Timestamp(start_year, start_month, 1)
            end_exclusive = (
                pd.Timestamp(end_year, end_month, 1) + pd.offsets.MonthBegin(1)
            )
            if start_date >= end_exclusive:
                raise ValidationError("結束年月必須晚於起始年月。")
            return start_date, end_exclusive


        def validate_initial_amount
        '''
    ).lstrip()
    replace_regex_once(
        "api/index.py",
        r"def parse_period\(data\):\n.*?\n\ndef validate_initial_amount",
        replacement,
    )


def patch_backtest_timing() -> None:
    replace_once("api/index_v2.py", "import logging\n", "import logging\nimport time\n")
    replace_once(
        "api/index_v2.py",
        "def backtest_handler():\n    try:\n        data = legacy.require_json_object()",
        "def backtest_handler():\n    request_started = time.perf_counter()\n    try:\n        data = legacy.require_json_object()",
    )
    replace_once(
        "api/index_v2.py",
        textwrap.dedent(
            '''
                    prices_raw = download_data_silently(
                        tuple(sorted(required_tickers)),
                        start_date.strftime("%Y-%m-%d"),
                        end_exclusive.strftime("%Y-%m-%d"),
                    )
                    action_audits = dict(
            '''
        ).lstrip("\n"),
        textwrap.dedent(
            '''
                    market_started = time.perf_counter()
                    prices_raw = download_data_silently(
                        tuple(sorted(required_tickers)),
                        start_date.strftime("%Y-%m-%d"),
                        end_exclusive.strftime("%Y-%m-%d"),
                    )
                    market_ms = (time.perf_counter() - market_started) * 1000
                    compute_started = time.perf_counter()
                    action_audits = dict(
            '''
        ).lstrip("\n"),
    )
    replace_once(
        "api/index_v2.py",
        textwrap.dedent(
            '''
                    return legacy.jsonify(
                        {
                            "data": results,
                            "benchmark": benchmark_result,
                            "warning": "；".join(warning_parts) if warning_parts else None,
                            "metadata": metadata,
                        }
                    )
            '''
        ).lstrip("\n"),
        textwrap.dedent(
            '''
                    payload = {
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
            '''
        ).lstrip("\n"),
    )


def patch_html() -> None:
    replace_once("public/index.html", "/app.js?v=20260801.4", "/app.js?v=20260801.5")
    replace_once(
        "public/index.html",
        '<span>起始月份</span>\n            <input id="start-period" type="month" value="2015-01">',
        '<span>起始日期</span>\n            <input id="start-period" type="date">',
    )
    replace_once(
        "public/index.html",
        '<span>結束月份</span>\n            <input id="end-period" type="month">',
        '<span>結束日期</span>\n            <input id="end-period" type="date">',
    )
    replace_once(
        "public/index.html",
        '<div id="backtest-warning" class="message warning hidden"></div>',
        '<div id="backtest-warning" class="message warning hidden"></div>\n'
        '        <div id="backtest-timing" class="result-context hidden"></div>',
    )
    replace_once(
        "public/index.html",
        '<span>起始月份</span>\n            <input id="scan-start-period" type="month" value="2019-01">',
        '<span>起始日期</span>\n            <input id="scan-start-period" type="date">',
    )
    replace_once(
        "public/index.html",
        '<span>結束月份</span>\n            <input id="scan-end-period" type="month">',
        '<span>結束日期</span>\n            <input id="scan-end-period" type="date">',
    )
    replace_once(
        "public/index.html",
        "調整後股價包含拆股及股息效果；未納入稅務、滑價與交易成本。",
        "預設為今天 day 0 往前一個完整年度（起始日為一年前同日、"
        "結束日為昨天）；調整後股價包含拆股及股息效果。",
    )


def patch_frontend() -> None:
    path = "public/app.js"
    content = read(path)
    old_default = textwrap.dedent(
        '''
        const currentMonth = new Date().toISOString().slice(0, 7);
        const defaultState = {
          settings: {
            initialAmount: 10000,
            startPeriod: "2015-01",
            endPeriod: currentMonth,
            rebalancingPeriod: "annually",
            benchmark: "SPY",
          },
        '''
    ).lstrip("\n")
    new_default = textwrap.dedent(
        '''
        function formatLocalDate(date) {
          const year = date.getFullYear();
          const month = String(date.getMonth() + 1).padStart(2, "0");
          const day = String(date.getDate()).padStart(2, "0");
          return `${year}-${month}-${day}`;
        }

        function rollingYearRange(now = new Date()) {
          const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
          const end = new Date(today);
          end.setDate(end.getDate() - 1);
          const previousYear = today.getFullYear() - 1;
          const maxDay = new Date(previousYear, today.getMonth() + 1, 0).getDate();
          const start = new Date(
            previousYear,
            today.getMonth(),
            Math.min(today.getDate(), maxDay),
          );
          return {
            startDate: formatLocalDate(start),
            endDate: formatLocalDate(end),
          };
        }

        const defaultRange = rollingYearRange();

        function normalizeSavedDate(value, boundary) {
          const raw = String(value || "").trim();
          if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;
          if (/^\d{4}-\d{2}$/.test(raw)) {
            if (boundary === "start") return `${raw}-01`;
            const [year, month] = raw.split("-").map(Number);
            const lastDay = new Date(year, month, 0).getDate();
            const migrated = `${raw}-${String(lastDay).padStart(2, "0")}`;
            return migrated > defaultRange.endDate ? defaultRange.endDate : migrated;
          }
          return boundary === "start" ? defaultRange.startDate : defaultRange.endDate;
        }

        const defaultState = {
          settings: {
            initialAmount: 10000,
            startPeriod: defaultRange.startDate,
            endPeriod: defaultRange.endDate,
            rebalancingPeriod: "annually",
            benchmark: "SPY",
          },
        '''
    ).lstrip("\n")
    if content.count(old_default) != 1:
        raise SystemExit("public/app.js: default state anchor not found")
    content = content.replace(old_default, new_default, 1)

    content = content.replace(
        textwrap.dedent(
            '''
                if (parsed?.settings && Array.isArray(parsed?.portfolios) && parsed.portfolios.length) {
                  return parsed;
                }
            '''
        ).lstrip("\n"),
        textwrap.dedent(
            '''
                if (parsed?.settings && Array.isArray(parsed?.portfolios) && parsed.portfolios.length) {
                  parsed.settings.startPeriod = normalizeSavedDate(
                    parsed.settings.startPeriod,
                    "start",
                  );
                  parsed.settings.endPeriod = normalizeSavedDate(
                    parsed.settings.endPeriod,
                    "end",
                  );
                  return parsed;
                }
            '''
        ).lstrip("\n"),
        1,
    )

    old_parse = textwrap.dedent(
        '''
        function parsePeriod(period) {
          const [year, month] = period.split("-").map(Number);
          if (!year || !month) throw new Error("請選擇有效的起訖月份。");
          return { year, month };
        }
        '''
    ).lstrip("\n")
    new_parse = textwrap.dedent(
        '''
        function parseDateInput(value) {
          const raw = String(value || "").trim();
          if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
            throw new Error("請選擇有效的起訖日期。");
          }
          const date = new Date(`${raw}T00:00:00`);
          if (Number.isNaN(date.getTime()) || formatLocalDate(date) !== raw) {
            throw new Error("請選擇有效的起訖日期。");
          }
          return {
            value: raw,
            date,
            year: date.getFullYear(),
            month: date.getMonth() + 1,
          };
        }
        '''
    ).lstrip("\n")
    if content.count(old_parse) != 1:
        raise SystemExit("public/app.js: parsePeriod anchor not found")
    content = content.replace(old_parse, new_parse, 1)

    content = content.replace(
        '  backtestWarning: document.querySelector("#backtest-warning"),',
        '  backtestWarning: document.querySelector("#backtest-warning"),\n'
        '  backtestTiming: document.querySelector("#backtest-timing"),',
        1,
    )
    content = content.replace(
        '          requested: response.headers.get("x-scan-requested"),\n'
        '          resolved: response.headers.get("x-scan-resolved"),',
        '          requested: response.headers.get("x-scan-requested")\n'
        '            || response.headers.get("x-backtest-requested"),\n'
        '          resolved: response.headers.get("x-scan-resolved")\n'
        '            || response.headers.get("x-backtest-resolved"),\n'
        '          edgeCache: response.headers.get("x-edge-cache") || "",',
        1,
    )

    old_initialize = textwrap.dedent(
        '''
        function initializeControls() {
          document.querySelector("#initial-amount").value = state.settings.initialAmount;
          document.querySelector("#start-period").value = state.settings.startPeriod;
          document.querySelector("#end-period").value = state.settings.endPeriod || currentMonth;
          document.querySelector("#rebalancing-period").value = state.settings.rebalancingPeriod;
          document.querySelector("#benchmark").value = state.settings.benchmark;
          document.querySelector("#scan-end-period").value = currentMonth;
        }
        '''
    ).lstrip("\n")
    new_initialize = textwrap.dedent(
        '''
        function initializeControls() {
          state.settings.startPeriod = normalizeSavedDate(
            state.settings.startPeriod,
            "start",
          );
          state.settings.endPeriod = normalizeSavedDate(
            state.settings.endPeriod,
            "end",
          );
          document.querySelector("#initial-amount").value = state.settings.initialAmount;
          document.querySelector("#start-period").value = state.settings.startPeriod;
          document.querySelector("#end-period").value = state.settings.endPeriod;
          document.querySelector("#rebalancing-period").value = state.settings.rebalancingPeriod;
          document.querySelector("#benchmark").value = state.settings.benchmark;
          document.querySelector("#scan-start-period").value = defaultRange.startDate;
          document.querySelector("#scan-end-period").value = defaultRange.endDate;
        }
        '''
    ).lstrip("\n")
    if content.count(old_initialize) != 1:
        raise SystemExit("public/app.js: initializeControls anchor not found")
    content = content.replace(old_initialize, new_initialize, 1)

    old_backtest_dates = textwrap.dedent(
        '''
          const start = parsePeriod(state.settings.startPeriod);
          const end = parsePeriod(state.settings.endPeriod);
          const startValue = start.year * 12 + start.month;
          const endValue = end.year * 12 + end.month;
          if (startValue > endValue) throw new Error("結束月份必須晚於或等於起始月份。");
        '''
    ).lstrip("\n")
    new_backtest_dates = textwrap.dedent(
        '''
          const start = parseDateInput(state.settings.startPeriod);
          const end = parseDateInput(state.settings.endPeriod);
          if (start.date > end.date) {
            throw new Error("結束日期必須晚於或等於起始日期。");
          }
        '''
    ).lstrip("\n")
    if content.count(old_backtest_dates) != 1:
        raise SystemExit("public/app.js: backtest date validation anchor not found")
    content = content.replace(old_backtest_dates, new_backtest_dates, 1)

    old_payload_dates = textwrap.dedent(
        '''
            startYear: start.year,
            startMonth: start.month,
            endYear: end.year,
            endMonth: end.month,
        '''
    ).lstrip("\n")
    new_payload_dates = textwrap.dedent(
        '''
            startDate: start.value,
            endDate: end.value,
            startYear: start.year,
            startMonth: start.month,
            endYear: end.year,
            endMonth: end.month,
        '''
    ).lstrip("\n")
    if content.count(old_payload_dates) != 2:
        raise SystemExit(
            "public/app.js: expected two backtest/scan payload date anchors"
        )
    content = content.replace(old_payload_dates, new_payload_dates, 2)

    old_scan_dates = textwrap.dedent(
        '''
          const start = parsePeriod(document.querySelector("#scan-start-period").value);
          const end = parsePeriod(document.querySelector("#scan-end-period").value);
          if (start.year * 12 + start.month > end.year * 12 + end.month) throw new Error("結束月份必須晚於或等於起始月份。");
        '''
    ).lstrip("\n")
    new_scan_dates = textwrap.dedent(
        '''
          const start = parseDateInput(document.querySelector("#scan-start-period").value);
          const end = parseDateInput(document.querySelector("#scan-end-period").value);
          if (start.date > end.date) {
            throw new Error("結束日期必須晚於或等於起始日期。");
          }
        '''
    ).lstrip("\n")
    if content.count(old_scan_dates) != 1:
        raise SystemExit("public/app.js: scan date validation anchor not found")
    content = content.replace(old_scan_dates, new_scan_dates, 1)

    content = content.replace(
        '  showLoading("正在下載行情並計算投資組合…");\n  try {',
        '  showLoading("正在下載行情並計算投資組合…");\n'
        '  dom.backtestTiming.classList.add("hidden");\n'
        '  const startedAt = performance.now();\n'
        '  try {',
        1,
    )
    content = content.replace(
        '    if (latestBacktest.warning) setMessage(dom.backtestWarning, latestBacktest.warning);\n'
        '    renderBacktestResults(latestBacktest);',
        '    if (latestBacktest.warning) setMessage(dom.backtestWarning, latestBacktest.warning);\n'
        '    const elapsedSeconds = (performance.now() - startedAt) / 1000;\n'
        '    const timing = parseServerTiming(latestBacktest.__responseMeta?.serverTiming);\n'
        '    const phases = [];\n'
        '    if (Number.isFinite(timing.market)) {\n'
        '      phases.push(`行情下載與修復 ${(timing.market / 1000).toFixed(1)} 秒`);\n'
        '    }\n'
        '    if (Number.isFinite(timing.compute)) {\n'
        '      phases.push(`投組與稽核計算 ${(timing.compute / 1000).toFixed(1)} 秒`);\n'
        '    }\n'
        '    const cacheText = latestBacktest.__responseMeta?.edgeCache === "HIT"\n'
        '      ? "Edge 快取命中"\n'
        '      : "即時計算";\n'
        '    dom.backtestTiming.textContent = [\n'
        '      `總等待 ${elapsedSeconds.toFixed(1)} 秒`,\n'
        '      cacheText,\n'
        '      ...phases,\n'
        '    ].join("｜");\n'
        '    dom.backtestTiming.classList.remove("hidden");\n'
        '    renderBacktestResults(latestBacktest);',
        1,
    )
    write(path, content)


def patch_worker() -> None:
    replace_once(
        "worker/index.js",
        "const API_TIMEOUT_MS = 240_000;",
        "const API_TIMEOUT_MS = 240_000;\n"
        'const EDGE_CACHE_VERSION = "2026-08-01.1";\n'
        "const EDGE_CACHE_TTL_SECONDS = 15 * 60;\n"
        'const EDGE_CACHEABLE_ROUTES = new Set(["/api/backtest", "/api/scan"]);',
    )
    marker = "\nasync function proxyBackend(request, env, requestId, requestBody) {"
    helpers = textwrap.dedent(
        '''

        function cacheBackend(env) {
          return env.API_CACHE || globalThis.caches?.default || null;
        }

        async function buildEdgeCacheKey(pathname, requestBody) {
          const digest = await crypto.subtle.digest("SHA-256", requestBody);
          const hash = [...new Uint8Array(digest)]
            .map((value) => value.toString(16).padStart(2, "0"))
            .join("");
          return new Request(
            `https://edge-cache.invalid/${EDGE_CACHE_VERSION}${pathname}/${hash}`,
          );
        }

        function withEdgeCacheStatus(response, status, requestId) {
          const headers = new Headers(response.headers);
          headers.set("x-edge-cache", status);
          headers.set("x-request-id", requestId);
          headers.set("cache-control", "no-store");
          return new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers,
          });
        }

        async function cacheSuccessfulResponse(cache, key, response) {
          if (!cache || response.status !== 200) return;
          const contentType = response.headers.get("content-type") || "";
          if (!contentType.includes("application/json")) return;
          const headers = new Headers(response.headers);
          headers.delete("x-request-id");
          headers.set("cache-control", `public, max-age=${EDGE_CACHE_TTL_SECONDS}`);
          const body = await response.clone().arrayBuffer();
          await cache.put(key, new Response(body, {
            status: response.status,
            statusText: response.statusText,
            headers,
          }));
        }
        '''
    )
    content = read("worker/index.js")
    if content.count(marker) != 1:
        raise SystemExit("worker/index.js: proxyBackend marker not found")
    content = content.replace(marker, helpers + marker, 1)
    old_proxy_return = textwrap.dedent(
        '''
          const requestBody = await readValidatedBody(request, requestId);
          if (requestBody instanceof Response) return requestBody;
          return proxyBackend(request, env, requestId, requestBody);
        '''
    ).lstrip("\n")
    new_proxy_return = textwrap.dedent(
        '''
          const requestBody = await readValidatedBody(request, requestId);
          if (requestBody instanceof Response) return requestBody;

          const cache = cacheBackend(env);
          const cacheEligible = (
            cache
            && EDGE_CACHEABLE_ROUTES.has(incomingUrl.pathname)
            && request.method === "POST"
            && requestBody instanceof ArrayBuffer
            && !request.headers.has("authorization")
            && !request.headers.has("cookie")
          );
          if (!cacheEligible) {
            return proxyBackend(request, env, requestId, requestBody);
          }

          const cacheKey = await buildEdgeCacheKey(incomingUrl.pathname, requestBody);
          const cached = await cache.match(cacheKey);
          if (cached) return withEdgeCacheStatus(cached, "HIT", requestId);

          const response = await proxyBackend(request, env, requestId, requestBody);
          await cacheSuccessfulResponse(cache, cacheKey, response);
          return withEdgeCacheStatus(response, "MISS", requestId);
        '''
    ).lstrip("\n")
    if content.count(old_proxy_return) != 1:
        raise SystemExit("worker/index.js: proxyApi return anchor not found")
    content = content.replace(old_proxy_return, new_proxy_return, 1)
    write("worker/index.js", content)


def patch_tests() -> None:
    replacements = {
        '.fill("2025-01")': '.fill("2025-01-01")',
        '.fill("2025-03")': '.fill("2025-03-31")',
        '.fill("2025-12")': '.fill("2025-12-31")',
        '.fill("2026-07")': '.fill("2026-07-31")',
    }
    for e2e_path in (ROOT / "tests/e2e").glob("*.mjs"):
        content = e2e_path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            content = content.replace(old, new)
        e2e_path.write_text(content, encoding="utf-8")

    write(
        "tests/test_daily_period.py",
        textwrap.dedent(
            '''
            import pandas as pd
            import pytest

            from api import index


            def test_daily_period_is_inclusive_at_the_public_contract():
                start, end_exclusive = index.parse_period(
                    {"startDate": "2025-08-01", "endDate": "2026-07-31"}
                )
                assert start == pd.Timestamp("2025-08-01")
                assert end_exclusive == pd.Timestamp("2026-08-01")


            def test_daily_period_rejects_reversed_or_partial_dates():
                with pytest.raises(index.ValidationError):
                    index.parse_period(
                        {"startDate": "2026-07-31", "endDate": "2025-08-01"}
                    )
                with pytest.raises(index.ValidationError):
                    index.parse_period({"startDate": "2025-08-01"})


            def test_legacy_month_period_remains_supported():
                start, end_exclusive = index.parse_period(
                    {
                        "startYear": 2025,
                        "startMonth": 8,
                        "endYear": 2026,
                        "endMonth": 7,
                    }
                )
                assert start == pd.Timestamp("2025-08-01")
                assert end_exclusive == pd.Timestamp("2026-08-01")
            '''
        ).lstrip(),
    )
    write(
        "tests/e2e/daily_date_defaults.spec.mjs",
        textwrap.dedent(
            '''
            import { expect, test } from "@playwright/test";

            async function fulfillJson(route, body) {
              await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify(body),
              });
            }

            function formatLocalDate(date) {
              return [
                date.getFullYear(),
                String(date.getMonth() + 1).padStart(2, "0"),
                String(date.getDate()).padStart(2, "0"),
              ].join("-");
            }

            test("daily controls default to previous-year same date through yesterday", async ({ page }) => {
              await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
              await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
              await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
              await page.goto("/");

              const today = new Date();
              const end = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
              const previousYear = today.getFullYear() - 1;
              const maxDay = new Date(previousYear, today.getMonth() + 1, 0).getDate();
              const start = new Date(
                previousYear,
                today.getMonth(),
                Math.min(today.getDate(), maxDay),
              );

              await expect(page.locator("#start-period")).toHaveAttribute("type", "date");
              await expect(page.locator("#end-period")).toHaveAttribute("type", "date");
              await expect(page.locator("#start-period")).toHaveValue(formatLocalDate(start));
              await expect(page.locator("#end-period")).toHaveValue(formatLocalDate(end));
              await expect(page.locator("#scan-start-period")).toHaveValue(formatLocalDate(start));
              await expect(page.locator("#scan-end-period")).toHaveValue(formatLocalDate(end));
            });
            '''
        ).lstrip(),
    )

    worker_test = read("tests/test_worker.mjs")
    worker_test += textwrap.dedent(
        '''

        test("identical backtest requests reuse the edge response cache", async () => {
          const originalFetch = globalThis.fetch;
          let backendCalls = 0;
          const stored = new Map();
          const cache = {
            async match(request) {
              return stored.get(request.url)?.clone() || null;
            },
            async put(request, response) {
              stored.set(request.url, response.clone());
            },
          };
          globalThis.fetch = async () => {
            backendCalls += 1;
            return new Response(
              JSON.stringify({ data: [], benchmark: null, metadata: {} }),
              {
                status: 200,
                headers: {
                  "content-type": "application/json",
                  "server-timing": "market;dur=100",
                },
              },
            );
          };

          try {
            const env = {
              BACKEND_ORIGIN: "https://backend.example",
              API_CACHE: cache,
            };
            const body = JSON.stringify({
              startDate: "2025-08-01",
              endDate: "2026-07-31",
              initialAmount: 10000,
              portfolios: [
                { name: "P", tickers: ["SPY"], weights: [100] },
              ],
            });
            const request = () => new Request(
              "https://example.com/api/backtest",
              {
                method: "POST",
                headers: { "content-type": "application/json" },
                body,
              },
            );
            const first = await worker.fetch(request(), env);
            const second = await worker.fetch(request(), env);
            assert.equal(first.headers.get("x-edge-cache"), "MISS");
            assert.equal(second.headers.get("x-edge-cache"), "HIT");
            assert.equal(backendCalls, 1);
            assert.deepEqual(
              await second.json(),
              { data: [], benchmark: null, metadata: {} },
            );
          } finally {
            globalThis.fetch = originalFetch;
          }
        });
        '''
    )
    write("tests/test_worker.mjs", worker_test)


def cleanup_temporary_files() -> None:
    for relative in (
        "scripts/apply_daily_range_patch.py",
        ".github/workflows/apply-daily-range-performance.yml",
        ".github/workflows/run-daily-range-patch-on-pr.yml",
        "diagnostics/daily-range-trigger.txt",
    ):
        path = ROOT / relative
        if path.exists():
            path.unlink()


def main() -> None:
    patch_backend_period()
    patch_backtest_timing()
    patch_html()
    patch_frontend()
    patch_worker()
    patch_tests()
    cleanup_temporary_files()


if __name__ == "__main__":
    main()
