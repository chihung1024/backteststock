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

function scanResultFor(ticker, position = 0) {
  return {
    ticker,
    status: "ok",
    retryable: false,
    metric_definition_version: METRIC_VERSION,
    total_return: 0.1 + position / 100_000,
    cagr: 0.08 + position / 100_000,
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

test("500-symbol happy path crosses five bounded 100-symbol chunks", async ({ page }) => {
  const tickers = buildTickers();
  const payloads = [];
  await installBaseRoutes(page);
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    payloads.push(payload);
    await fulfillJson(
      route,
      payload.tickers.map((ticker, index) => scanResultFor(ticker, payloads.length * 100 + index)),
    );
  });

  await startManualScan(page, tickers);

  await expect(page.locator("#scan-summary")).toContainText("500 / 500", { timeout: 30_000 });
  expect(payloads.map((payload) => payload.tickers.length)).toEqual([100, 100, 100, 100, 100]);
  expect(payloads.flatMap((payload) => payload.tickers)).toEqual(tickers);

  const job = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), STORAGE_KEY);
  expect(job.status).toBe("completed");
  expect(job.pending).toEqual([]);
  expect(job.results).toHaveLength(500);
});

test("fourth chunk request-level 503 is requeued and fifth chunk still executes", async ({ page }) => {
  const tickers = buildTickers();
  const firstTickers = [];
  let fourthChunkFailures = 0;
  await installBaseRoutes(page);
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    const firstTicker = payload.tickers[0];
    firstTickers.push(firstTicker);

    if (firstTicker === tickerAt(300) && fourthChunkFailures < 2) {
      fourthChunkFailures += 1;
      await fulfillJson(route, { error: "temporary upstream outage" }, 503);
      return;
    }

    await fulfillJson(route, payload.tickers.map((ticker) => scanResultFor(ticker)));
  });

  await startManualScan(page, tickers);

  await expect(page.locator("#scan-summary")).toContainText("500 / 500", { timeout: 30_000 });
  expect(fourthChunkFailures).toBe(2);
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

test("running 300-of-500 persisted job auto-resumes only the remaining 200", async ({ page }) => {
  const tickers = buildTickers();
  const settled = tickers.slice(0, 300).map((ticker) => scanResultFor(ticker));
  const pending = tickers.slice(300);
  const requested = [];
  const savedJob = {
    version: 3,
    id: "saved-500-running",
    status: "running",
    createdAt: "2026-08-11T00:00:00.000Z",
    updatedAt: "2026-08-11T00:05:00.000Z",
    payload: {
      tickers,
      benchmark: "SPY",
      startDate: "2025-01-01",
      endDate: "2025-12-31",
      startYear: 2025,
      startMonth: 1,
      endYear: 2025,
      endMonth: 12,
    },
    screenerContext: null,
    pending,
    results: settled,
    attempts: {},
    retryRound: 0,
  };

  await page.addInitScript(({ key, job }) => {
    localStorage.setItem(key, JSON.stringify(job));
  }, { key: STORAGE_KEY, job: savedJob });
  await installBaseRoutes(page);
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    requested.push(...payload.tickers);
    await fulfillJson(route, payload.tickers.map((ticker) => scanResultFor(ticker)));
  });

  await page.goto("/");

  await expect(page.locator("#scan-summary")).toContainText("500 / 500", { timeout: 30_000 });
  expect(requested).toEqual(pending);
  expect(requested).not.toContain(tickerAt(299));

  const job = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), STORAGE_KEY);
  expect(job.status).toBe("completed");
  expect(job.pending).toEqual([]);
  expect(job.results).toHaveLength(500);
});

test("paused 300-of-500 persisted job does not auto-resume and remains explicitly resumable", async ({ page }) => {
  const tickers = buildTickers();
  const settled = tickers.slice(0, 300).map((ticker) => scanResultFor(ticker));
  const pending = tickers.slice(300);
  let scanRequests = 0;
  const savedJob = {
    version: 3,
    id: "saved-500-paused",
    status: "paused",
    createdAt: "2026-08-11T00:00:00.000Z",
    updatedAt: "2026-08-11T00:05:00.000Z",
    payload: {
      tickers,
      benchmark: "SPY",
      startDate: "2025-01-01",
      endDate: "2025-12-31",
      startYear: 2025,
      startMonth: 1,
      endYear: 2025,
      endMonth: 12,
    },
    screenerContext: null,
    pending,
    results: settled,
    attempts: {},
    retryRound: 0,
  };

  await page.addInitScript(({ key, job }) => {
    localStorage.setItem(key, JSON.stringify(job));
  }, { key: STORAGE_KEY, job: savedJob });
  await installBaseRoutes(page);
  await page.route("**/api/scan", async (route) => {
    scanRequests += 1;
    await fulfillJson(route, []);
  });

  await page.goto("/");
  await expect(page.locator("#scan-progress-label")).toContainText("已還原 300 / 500 檔，未完成 200 檔");
  await expect(page.locator("#retry-scan")).toBeVisible();
  await page.waitForTimeout(500);
  expect(scanRequests).toBe(0);

  const job = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), STORAGE_KEY);
  expect(job.status).toBe("paused");
  expect(job.results).toHaveLength(300);
  expect(job.pending).toHaveLength(200);
});
