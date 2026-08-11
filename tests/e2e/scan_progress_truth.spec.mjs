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

test("scanner distinguishes settled progress from successful results", async ({ page }) => {
  const tickers = buildTickers();
  const failedStarts = new Set([tickerAt(300), tickerAt(400)]);
  await installBaseRoutes(page);
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    const rows = failedStarts.has(payload.tickers[0])
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

  await expect(page.locator("#scan-progress-label")).toContainText(
    "正在取得第 401–500 檔；已結算 400 / 500 檔（成功 300、失敗 100）",
    { timeout: 30_000 },
  );

  await expect(page.locator("#scan-progress-label")).toContainText(
    "回測結束：已結算 500 / 500 檔（成功 300、失敗 200、未完成 0）",
    { timeout: 30_000 },
  );
  await expect(page.locator("#scan-summary")).toContainText("成功標的300 / 500");
  await expect(page.locator("#scan-summary")).toContainText("失敗標的200");
  await expect(page.locator("#scan-summary")).toContainText("未完成0");
  await expect(page.locator("#scan-progress-label")).not.toContainText("已完成 400 / 500");
});
