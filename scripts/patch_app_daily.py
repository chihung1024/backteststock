from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "public/app.js"


def replace_once(content: str, old: str, new: str, label: str) -> str:
    count = content.count(old)
    if count != 1:
        raise SystemExit(f"app.js: {label} expected once, found {count}")
    return content.replace(old, new, 1)


def main() -> None:
    content = PATH.read_text(encoding="utf-8")

    content = replace_once(
        content,
        '''const currentMonth = new Date().toISOString().slice(0, 7);
const defaultState = {
  settings: {
    initialAmount: 10000,
    startPeriod: "2015-01",
    endPeriod: currentMonth,
    rebalancingPeriod: "annually",
    benchmark: "SPY",
  },''',
        '''function formatLocalDate(date) {
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
  if (/^\\d{4}-\\d{2}-\\d{2}$/.test(raw)) return raw;
  if (/^\\d{4}-\\d{2}$/.test(raw)) {
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
  },''',
        "rolling default",
    )

    content = replace_once(
        content,
        '''    if (parsed?.settings && Array.isArray(parsed?.portfolios) && parsed.portfolios.length) {
      return parsed;
    }''',
        '''    if (parsed?.settings && Array.isArray(parsed?.portfolios) && parsed.portfolios.length) {
      parsed.settings.startPeriod = normalizeSavedDate(
        parsed.settings.startPeriod,
        "start",
      );
      parsed.settings.endPeriod = normalizeSavedDate(
        parsed.settings.endPeriod,
        "end",
      );
      return parsed;
    }''',
        "saved-state migration",
    )

    content = replace_once(
        content,
        '''function parsePeriod(period) {
  const [year, month] = period.split("-").map(Number);
  if (!year || !month) throw new Error("請選擇有效的起訖月份。");
  return { year, month };
}''',
        '''function parseDateInput(value) {
  const raw = String(value || "").trim();
  if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(raw)) {
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
}''',
        "date parser",
    )

    content = replace_once(
        content,
        '  backtestWarning: document.querySelector("#backtest-warning"),',
        '  backtestWarning: document.querySelector("#backtest-warning"),\n'
        '  backtestTiming: document.querySelector("#backtest-timing"),',
        "timing DOM",
    )

    content = replace_once(
        content,
        '''          requested: response.headers.get("x-scan-requested"),
          resolved: response.headers.get("x-scan-resolved"),''',
        '''          requested: response.headers.get("x-scan-requested")
            || response.headers.get("x-backtest-requested"),
          resolved: response.headers.get("x-scan-resolved")
            || response.headers.get("x-backtest-resolved"),
          edgeCache: response.headers.get("x-edge-cache") || "",''',
        "response metadata",
    )

    content = replace_once(
        content,
        '''function initializeControls() {
  document.querySelector("#initial-amount").value = state.settings.initialAmount;
  document.querySelector("#start-period").value = state.settings.startPeriod;
  document.querySelector("#end-period").value = state.settings.endPeriod || currentMonth;
  document.querySelector("#rebalancing-period").value = state.settings.rebalancingPeriod;
  document.querySelector("#benchmark").value = state.settings.benchmark;
  document.querySelector("#scan-end-period").value = currentMonth;
}''',
        '''function initializeControls() {
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
}''',
        "control initialization",
    )

    content = replace_once(
        content,
        '''  const start = parsePeriod(state.settings.startPeriod);
  const end = parsePeriod(state.settings.endPeriod);
  const startValue = start.year * 12 + start.month;
  const endValue = end.year * 12 + end.month;
  if (startValue > endValue) throw new Error("結束月份必須晚於或等於起始月份。");''',
        '''  const start = parseDateInput(state.settings.startPeriod);
  const end = parseDateInput(state.settings.endPeriod);
  if (start.date > end.date) {
    throw new Error("結束日期必須晚於或等於起始日期。");
  }''',
        "backtest date validation",
    )

    payload_dates = '''    startYear: start.year,
    startMonth: start.month,
    endYear: end.year,
    endMonth: end.month,'''
    payload_dates_new = '''    startDate: start.value,
    endDate: end.value,
    startYear: start.year,
    startMonth: start.month,
    endYear: end.year,
    endMonth: end.month,'''
    if content.count(payload_dates) != 2:
        raise SystemExit(
            f"app.js: payload date anchors expected twice, found {content.count(payload_dates)}"
        )
    content = content.replace(payload_dates, payload_dates_new, 2)

    content = replace_once(
        content,
        '''  const start = parsePeriod(document.querySelector("#scan-start-period").value);
  const end = parsePeriod(document.querySelector("#scan-end-period").value);
  if (start.year * 12 + start.month > end.year * 12 + end.month) throw new Error("結束月份必須晚於或等於起始月份。");''',
        '''  const start = parseDateInput(document.querySelector("#scan-start-period").value);
  const end = parseDateInput(document.querySelector("#scan-end-period").value);
  if (start.date > end.date) {
    throw new Error("結束日期必須晚於或等於起始日期。");
  }''',
        "scan date validation",
    )

    content = replace_once(
        content,
        '''  showLoading("正在下載行情並計算投資組合…");
  try {''',
        '''  showLoading("正在下載行情並計算投資組合…");
  dom.backtestTiming.classList.add("hidden");
  const startedAt = performance.now();
  try {''',
        "backtest timer start",
    )

    content = replace_once(
        content,
        '''    if (latestBacktest.warning) setMessage(dom.backtestWarning, latestBacktest.warning);
    renderBacktestResults(latestBacktest);''',
        '''    if (latestBacktest.warning) setMessage(dom.backtestWarning, latestBacktest.warning);
    const elapsedSeconds = (performance.now() - startedAt) / 1000;
    const timing = parseServerTiming(latestBacktest.__responseMeta?.serverTiming);
    const phases = [];
    if (Number.isFinite(timing.market)) {
      phases.push(`行情下載與修復 ${(timing.market / 1000).toFixed(1)} 秒`);
    }
    if (Number.isFinite(timing.compute)) {
      phases.push(`投組與稽核計算 ${(timing.compute / 1000).toFixed(1)} 秒`);
    }
    const cacheText = latestBacktest.__responseMeta?.edgeCache === "HIT"
      ? "Edge 快取命中"
      : "即時計算";
    dom.backtestTiming.textContent = [
      `總等待 ${elapsedSeconds.toFixed(1)} 秒`,
      cacheText,
      ...phases,
    ].join("｜");
    dom.backtestTiming.classList.remove("hidden");
    renderBacktestResults(latestBacktest);''',
        "backtest timing display",
    )

    PATH.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
