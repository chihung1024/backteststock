from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}")
    file_path.write_text(content.replace(old, new, 1), encoding="utf-8")


replace_once(
    "public/app.js",
    'const SCAN_RETRY_DELAYS_MS = [1_500, 5_000, 15_000, 30_000, 60_000];\n',
    'const SCAN_RETRY_DELAYS_MS = [1_500, 5_000, 15_000, 30_000, 60_000];\n'
    'const DEFAULT_LOOKBACK_YEARS = 10;\n',
)

replace_once(
    "public/app.js",
    '''function rollingYearRange(now = new Date()) {
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
''',
    '''function rollingDefaultRange(now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(today);
  end.setDate(end.getDate() - 1);
  const startYear = today.getFullYear() - DEFAULT_LOOKBACK_YEARS;
  const maxDay = new Date(startYear, today.getMonth() + 1, 0).getDate();
  const start = new Date(
    startYear,
    today.getMonth(),
    Math.min(today.getDate(), maxDay),
  );
  return {
    startDate: formatLocalDate(start),
    endDate: formatLocalDate(end),
  };
}

const defaultRange = rollingDefaultRange();
''',
)

replace_once(
    "public/app.js",
    '''function normalizeSavedDate(value, boundary) {
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
''',
    '''function isValidLocalIsoDate(value) {
  const raw = String(value || "").trim();
  if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(raw)) return false;
  const [year, month, day] = raw.split("-").map(Number);
  const parsed = new Date(year, month - 1, day);
  return parsed.getFullYear() === year
    && parsed.getMonth() === month - 1
    && parsed.getDate() === day;
}

function normalizeSavedDate(value, boundary) {
  const raw = String(value || "").trim();
  if (isValidLocalIsoDate(raw)) return raw;
  if (/^\\d{4}-\\d{2}$/.test(raw)) {
    if (boundary === "start") return `${raw}-01`;
    const [year, month] = raw.split("-").map(Number);
    const lastDay = new Date(year, month, 0).getDate();
    const migrated = `${raw}-${String(lastDay).padStart(2, "0")}`;
    return migrated > defaultRange.endDate ? defaultRange.endDate : migrated;
  }
  return boundary === "start" ? defaultRange.startDate : defaultRange.endDate;
}

function scanPayloadDate(payload, boundary) {
  const dateKey = boundary === "start" ? "startDate" : "endDate";
  const direct = String(payload?.[dateKey] || "").trim();
  if (isValidLocalIsoDate(direct)) return direct;

  const yearKey = boundary === "start" ? "startYear" : "endYear";
  const monthKey = boundary === "start" ? "startMonth" : "endMonth";
  const year = Number(payload?.[yearKey]);
  const month = Number(payload?.[monthKey]);
  if (Number.isInteger(year) && Number.isInteger(month) && month >= 1 && month <= 12) {
    const day = boundary === "start" ? 1 : new Date(year, month, 0).getDate();
    const candidate = [
      year,
      String(month).padStart(2, "0"),
      String(day).padStart(2, "0"),
    ].join("-");
    if (boundary === "end" && candidate > defaultRange.endDate) {
      return defaultRange.endDate;
    }
    return candidate;
  }
  return boundary === "start" ? defaultRange.startDate : defaultRange.endDate;
}

function normalizeScanPayloadDates(payload) {
  const startDate = scanPayloadDate(payload, "start");
  const endDate = scanPayloadDate(payload, "end");
  const [startYear, startMonth] = startDate.split("-").map(Number);
  const [endYear, endMonth] = endDate.split("-").map(Number);
  return {
    ...payload,
    startDate,
    endDate,
    startYear,
    startMonth,
    endYear,
    endMonth,
  };
}

const defaultState = {
''',
)

replace_once(
    "public/app.js",
    '''    ) {
      const allowed = new Set(job.payload.tickers);
''',
    '''    ) {
      job.payload = normalizeScanPayloadDates(job.payload);
      const allowed = new Set(job.payload.tickers);
''',
)

replace_once(
    "public/app.js",
    '''function restoreScanControls(payload) {
  document.querySelector("#scan-tickers").value = payload.tickers.join(", ");
  document.querySelector("#scan-start-period").value = `${payload.startYear}-${String(payload.startMonth).padStart(2, "0")}`;
  document.querySelector("#scan-end-period").value = `${payload.endYear}-${String(payload.endMonth).padStart(2, "0")}`;
  document.querySelector("#scan-benchmark").value = payload.benchmark;
}
''',
    '''function restoreScanControls(payload) {
  const normalized = normalizeScanPayloadDates(payload);
  document.querySelector("#scan-tickers").value = normalized.tickers.join(", ");
  document.querySelector("#scan-start-period").value = normalized.startDate;
  document.querySelector("#scan-end-period").value = normalized.endDate;
  document.querySelector("#scan-benchmark").value = normalized.benchmark;
}
''',
)

replace_once(
    "public/index.html",
    '<script type="module" src="/app.js?v=20260801.5"></script>',
    '<script type="module" src="/app.js?v=20260801.6"></script>',
)
replace_once(
    "public/index.html",
    '預設為今天 day 0 往前一個完整年度（起始日為一年前同日、結束日為昨天）；調整後股價包含拆股及股息效果。',
    '預設為今天 day 0 往前十個完整年度（起始日為十年前同日、結束日為昨天）；日期可自行調整，調整後股價包含拆股及股息效果。',
)
replace_once(
    "public/index.html",
    '優先每批 100 檔一次取得並逐檔驗收；只重排實際缺漏標的，並在此瀏覽器保存未完成進度。',
    '日期預設為今天 day 0 往前十個完整年度，可自行調整；優先每批 100 檔一次取得並逐檔驗收，只重排實際缺漏標的，並在此瀏覽器保存未完成進度。',
)

replace_once(
    "tests/e2e/daily_date_defaults.spec.mjs",
    'test("daily controls default to previous-year same date through yesterday", async ({ page }) => {',
    'test("daily controls default to ten-years-ago same date through yesterday", async ({ page }) => {',
)
replace_once(
    "tests/e2e/daily_date_defaults.spec.mjs",
    '''  const previousYear = today.getFullYear() - 1;
  const maxDay = new Date(previousYear, today.getMonth() + 1, 0).getDate();
  const start = new Date(
    previousYear,
''',
    '''  const startYear = today.getFullYear() - 10;
  const maxDay = new Date(startYear, today.getMonth() + 1, 0).getDate();
  const start = new Date(
    startYear,
''',
)

replace_once(
    "tests/e2e/app.spec.mjs",
    '''  await page.goto("/");
  await expect(page.locator("#scan-summary")).toContainText("3 / 3");
  expect(scanPayloads).toHaveLength(1);
  expect(scanPayloads[0].tickers).toEqual(["NVDA"]);
''',
    '''  await page.goto("/");
  await expect(page.locator("#scan-summary")).toContainText("3 / 3");
  await expect(page.locator("#scan-start-period")).toHaveValue("2025-01-01");
  await expect(page.locator("#scan-end-period")).toHaveValue("2025-12-31");
  expect(scanPayloads).toHaveLength(1);
  expect(scanPayloads[0].tickers).toEqual(["NVDA"]);
  expect(scanPayloads[0]).toMatchObject({
    startDate: "2025-01-01",
    endDate: "2025-12-31",
  });
''',
)

replace_once(
    "docs/DAILY_RANGE_AND_EDGE_CACHE.md",
    '''- 起始日期為今天往前一年的同月同日，且為包含端點。
- 例如在 2026-08-01 開啟網站時，預設為 2025-08-01 至 2026-07-31。
- 2 月 29 日往前一年遇到非閏年時，起始日期收斂至 2 月 28 日。
''',
    '''- 起始日期為今天往前十年的同月同日，且為包含端點。
- 例如在 2026-08-01 開啟網站時，預設為 2016-08-01 至 2026-07-31。
- 2 月 29 日往前十年遇到非閏年時，起始日期收斂至 2 月 28 日。
- 這只是新回測與新掃描的預設值；使用者可以自行修改起訖日期。
- 還原權值與再現性契約不因預設期間變更而調整。
''',
)
replace_once(
    "docs/DAILY_RANGE_AND_EDGE_CACHE.md",
    '''{
  "startDate": "2025-08-01",
  "endDate": "2026-07-31"
}
''',
    '''{
  "startDate": "2016-08-01",
  "endDate": "2026-07-31"
}
''',
)

print("Applied ten-year default and legacy date restoration patch")
