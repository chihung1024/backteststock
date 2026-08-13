import { expect, test } from "@playwright/test";

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

function successRow(ticker) {
  return {
    ticker,
    status: "ok",
    retryable: false,
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
  };
}

function retryableFailure(ticker) {
  return {
    ticker,
    status: "failed",
    retryable: true,
    error_code: "twd_download_unavailable",
    error: "synthetic temporary upstream failure",
  };
}

async function installBaseRoutes(page) {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
}

test("scanner active ranges retain original ticker positions during retries", async ({ page }) => {
  const tickers = buildTickers();
  let releaseInitialLateBatch;
  const initialLateBatchGate = new Promise((resolve) => {
    releaseInitialLateBatch = resolve;
  });
  let markInitialLateBatchRequested;
  const initialLateBatchRequested = new Promise((resolve) => {
    markInitialLateBatchRequested = resolve;
  });
  let releaseRequeuedEarlyBatch;
  const requeuedEarlyBatchGate = new Promise((resolve) => {
    releaseRequeuedEarlyBatch = resolve;
  });
  let markRequeuedEarlyBatchRequested;
  const requeuedEarlyBatchRequested = new Promise((resolve) => {
    markRequeuedEarlyBatchRequested = resolve;
  });
  let earlyBatchRequestCount = 0;

  await installBaseRoutes(page);
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    const batchStart = payload.tickers[0];
    if (batchStart === tickerAt(400)) {
      markInitialLateBatchRequested();
      await initialLateBatchGate;
    }
    if (batchStart === tickerAt(300)) {
      earlyBatchRequestCount += 1;
      if (earlyBatchRequestCount === 2) {
        markRequeuedEarlyBatchRequested();
        await requeuedEarlyBatchGate;
      }
    }
    const rows = batchStart === tickerAt(300)
      ? payload.tickers.map(retryableFailure)
      : payload.tickers.map(successRow);
    await fulfillJson(route, rows);
  });

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.locator("#scan-tickers").fill(tickers.join(", "));
  await page.locator("#scan-start-period").fill("2025-01-01");
  await page.locator("#scan-end-period").fill("2025-12-31");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  // The first 401–500 request occurs while only 300 rows are settled. Its
  // range must come from immutable payload positions, not settled-result count.
  await initialLateBatchRequested;
  await expect(page.locator("#scan-progress-label")).toContainText(
    "正在取得第 401–500 檔；已結算 300 / 500 檔（成功 300、失敗 0）",
    { timeout: 30_000 },
  );
  releaseInitialLateBatch();

  // 301–400 is retried after 401–500 has already settled. It must not inherit
  // the later chunk's position from the settlement count.
  await requeuedEarlyBatchRequested;
  await expect(page.locator("#scan-progress-label")).toContainText(
    "正在取得第 301–400 檔；已結算 400 / 500 檔（成功 400、失敗 0）",
    { timeout: 30_000 },
  );
  releaseRequeuedEarlyBatch();

  await expect(page.locator("#scan-progress-label")).toContainText(
    "回測結束：已結算 500 / 500 檔（成功 400、失敗 100、未完成 0）",
    { timeout: 30_000 },
  );
  await expect(page.locator("#scan-summary")).toContainText("成功標的400 / 500");
  await expect(page.locator("#scan-summary")).toContainText("失敗標的100");
  await expect(page.locator("#scan-summary")).toContainText("未完成0");
  await expect(page.locator("#scan-progress-label")).not.toContainText("已完成 400 / 500");
});
