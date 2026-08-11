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

async function installQuotaFailureAfter300(page) {
  await page.addInitScript((storageKey) => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function patchedSetItem(key, value) {
      if (key === storageKey) {
        try {
          const parsed = JSON.parse(String(value));
          if (Array.isArray(parsed?.results) && parsed.results.length >= 400) {
            throw new DOMException("Synthetic quota exceeded after 300-result checkpoint", "QuotaExceededError");
          }
        } catch (error) {
          if (error?.name === "QuotaExceededError") throw error;
        }
      }
      return original.call(this, key, value);
    };
  }, STORAGE_KEY);
}

async function startManualScan(page, tickers) {
  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.locator("#scan-tickers").fill(tickers.join(", "));
  await page.locator("#scan-start-period").fill("2025-01-01");
  await page.locator("#scan-end-period").fill("2025-12-31");
  await page.getByRole("button", { name: "開始集體回測" }).click();
}

test("storage failure after 300 does not roll an uninterrupted in-memory scan backward", async ({ page }) => {
  const tickers = buildTickers();
  await installQuotaFailureAfter300(page);
  await installBaseRoutes(page);
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    await fulfillJson(route, payload.tickers.map((ticker) => scanResultFor(ticker)));
  });

  await startManualScan(page, tickers);

  await expect(page.locator("#scan-progress-label")).toContainText("完整取得 500 / 500 檔", { timeout: 30_000 });
  const activeText = await page.locator("#scan-progress-label").textContent();
  expect(activeText).toContain("500 / 500");

  const persisted = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), STORAGE_KEY);
  expect(persisted.results).toHaveLength(300);
  expect(persisted.status).toBe("running");
});

test("stale 300 checkpoint plus reload immediately auto-resumes instead of remaining visibly rolled back", async ({ page }) => {
  const tickers = buildTickers();
  let releaseFinalChunk;
  const finalChunkGate = new Promise((resolve) => {
    releaseFinalChunk = resolve;
  });

  await installQuotaFailureAfter300(page);
  await installBaseRoutes(page);
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    if (payload.tickers[0] === tickerAt(400)) {
      await finalChunkGate;
    }
    await fulfillJson(route, payload.tickers.map((ticker) => scanResultFor(ticker)));
  });

  await startManualScan(page, tickers);

  await expect(page.locator("#scan-progress-label")).toContainText(
    "正在取得第 401–500 檔；已完成 400 / 500 檔",
    { timeout: 30_000 },
  );

  const beforeReload = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), STORAGE_KEY);
  expect(beforeReload.results).toHaveLength(300);
  expect(beforeReload.status).toBe("running");

  await page.reload();

  await expect(page.locator("#scan-progress-label")).toContainText(
    "正在取得第 401–500 檔；已完成 400 / 500 檔",
    { timeout: 30_000 },
  );

  const stillPersisted = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), STORAGE_KEY);
  expect(stillPersisted.results).toHaveLength(300);
  expect(stillPersisted.status).toBe("running");

  releaseFinalChunk();
  await expect(page.locator("#scan-progress-label")).toContainText("完整取得 500 / 500 檔", { timeout: 30_000 });
});
