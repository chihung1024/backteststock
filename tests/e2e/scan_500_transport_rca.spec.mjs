import { expect, test } from "@playwright/test";

const STORAGE_KEY = "backteststock-scan-job-v3";
const METRIC_VERSION = "2026-08-01.2";

async function fulfillJson(route, body, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function tickerAt(index) {
  return `T${String(index + 1).padStart(4, "0")}`;
}

function buildTickers(count = 500) {
  return Array.from({ length: count }, (_, index) => tickerAt(index));
}

function scanResultFor(ticker) {
  return {
    ticker,
    status: "ok",
    retryable: false,
    metric_definition_version: METRIC_VERSION,
    total_return: 0.1,
    cagr: 0.08,
    volatility: 0.2,
    mdd: -0.1,
    sharpe_ratio: 0.8,
    sortino_ratio: 1.1,
    beta: 1.0,
    alpha: 0.02,
    data_coverage: 1,
    trading_days: 252,
    data_start: "2025-01-02",
    data_end: "2025-12-31",
    note: null,
  };
}

async function installBaseRoutes(page) {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
}

async function startManualScan(page, tickers) {
  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.locator("#scan-tickers").fill(tickers.join(", "));
  await page.locator("#scan-start-period").fill("2025-01-01");
  await page.locator("#scan-end-period").fill("2025-12-31");
  await page.getByRole("button", { name: "開始集體回測" }).click();
}

test("persistent fourth-chunk 503 terminalizes only that chunk and does not block the fifth", async ({ page }) => {
  const tickers = buildTickers();
  const firstTickers = [];
  let fourthChunkRequests = 0;
  await installBaseRoutes(page);
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    const firstTicker = payload.tickers[0];
    firstTickers.push(firstTicker);
    if (firstTicker === tickerAt(300)) {
      fourthChunkRequests += 1;
      await fulfillJson(route, { error: "persistent upstream outage" }, 503);
      return;
    }
    await fulfillJson(route, payload.tickers.map((ticker) => scanResultFor(ticker)));
  });

  await startManualScan(page, tickers);

  await expect(page.locator("#scan-summary")).toContainText("成功標的400 / 500", { timeout: 30_000 });
  await expect(page.locator("#scan-summary")).toContainText("失敗標的100");
  await expect(page.locator("#scan-summary")).toContainText("未完成0");
  expect(fourthChunkRequests).toBe(4);
  expect(firstTickers.indexOf(tickerAt(400))).toBeGreaterThan(firstTickers.indexOf(tickerAt(300)));

  const job = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), STORAGE_KEY);
  expect(job.status).toBe("completed");
  expect(job.pending).toEqual([]);
  expect(job.results).toHaveLength(500);
  expect(job.results.filter((item) => item.error)).toHaveLength(100);
  expect(job.results.filter((item) => !item.error)).toHaveLength(400);
  expect(job.results.slice(300, 400).every((item) => item.error && item.retryable === false)).toBe(true);
  expect(job.results.slice(400).every((item) => !item.error)).toBe(true);
});

test("persistent failures in both final chunks reproduce 400 settled progress followed by only 300 successes", async ({ page }) => {
  const tickers = buildTickers();
  const failedChunkStarts = new Set([tickerAt(300), tickerAt(400)]);
  const requestStarts = [];
  await installBaseRoutes(page);
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    const firstTicker = payload.tickers[0];
    requestStarts.push(firstTicker);
    if (failedChunkStarts.has(firstTicker)) {
      await fulfillJson(route, { error: "persistent upstream outage" }, 503);
      return;
    }
    await fulfillJson(route, payload.tickers.map((ticker) => scanResultFor(ticker)));
  });

  await startManualScan(page, tickers);

  await expect(page.locator("#scan-progress-label")).toContainText(
    "正在取得第 401–500 檔；已完成 400 / 500 檔",
    { timeout: 30_000 },
  );

  await expect(page.locator("#scan-summary")).toContainText("成功標的300 / 500", { timeout: 30_000 });
  await expect(page.locator("#scan-summary")).toContainText("失敗標的200");
  await expect(page.locator("#scan-summary")).toContainText("未完成0");

  const job = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), STORAGE_KEY);
  expect(job.status).toBe("completed");
  expect(job.pending).toEqual([]);
  expect(job.results).toHaveLength(500);
  expect(job.results.filter((item) => item.error)).toHaveLength(200);
  expect(job.results.filter((item) => !item.error)).toHaveLength(300);
  expect(job.results.slice(0, 300).every((item) => !item.error)).toBe(true);
  expect(job.results.slice(300).every((item) => item.error && item.retryable === false)).toBe(true);

  expect(requestStarts.slice(0, 3)).toEqual([tickerAt(0), tickerAt(100), tickerAt(200)]);
  expect(requestStarts).toContain(tickerAt(300));
  expect(requestStarts).toContain(tickerAt(400));
});

test("fourth-chunk transport abort remains resumable within the same scan execution", async ({ page }) => {
  const tickers = buildTickers();
  const firstTickers = [];
  let transportAborts = 0;
  await installBaseRoutes(page);
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    const firstTicker = payload.tickers[0];
    firstTickers.push(firstTicker);
    if (firstTicker === tickerAt(300) && transportAborts < 2) {
      transportAborts += 1;
      await route.abort("timedout");
      return;
    }
    await fulfillJson(route, payload.tickers.map((ticker) => scanResultFor(ticker)));
  });

  await startManualScan(page, tickers);

  await expect(page.locator("#scan-summary")).toContainText("成功標的500 / 500", { timeout: 30_000 });
  expect(transportAborts).toBe(2);
  expect(firstTickers).toEqual([
    tickerAt(0),
    tickerAt(100),
    tickerAt(200),
    tickerAt(300),
    tickerAt(300),
    tickerAt(400),
    tickerAt(300),
  ]);

  const job = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), STORAGE_KEY);
  expect(job.status).toBe("completed");
  expect(job.pending).toEqual([]);
  expect(job.results).toHaveLength(500);
});
