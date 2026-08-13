import { expect, test } from "@playwright/test";

import { METRIC_DEFINITION_VERSION } from "../../public/scan-score-formulas.js";

const universes = [{
  id: "sp500",
  name: "S&P 500（IVV holdings）",
  source: { label: "iShares IVV holdings", url: "https://example.com/ivv", isProxy: true },
  available: true,
  version: "2026-08-13-sp500",
  sourceAsOf: "2026-08-13",
  memberCount: 504,
  warnings: [],
}];

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function successfulResult(ticker) {
  return {
    ticker,
    status: "ok",
    retryable: false,
    metric_definition_version: METRIC_DEFINITION_VERSION,
    total_return: 0.25,
    cagr: 0.25,
    volatility: 0.2,
    mdd: -0.1,
    sharpe_ratio: 1.1,
    sortino_ratio: 1.4,
    beta: 1,
    alpha: 0.02,
    data_coverage: 1,
    trading_days: 252,
    data_start: "2025-01-01",
    data_end: "2025-12-31",
  };
}

test("does not present zero-value scan results before the first batch settles", async ({ page }) => {
  let releaseFirstBatch;
  const firstBatchReleased = new Promise((resolve) => {
    releaseFirstBatch = resolve;
  });
  let firstScanRequest;
  const firstScanStarted = new Promise((resolve) => {
    firstScanRequest = resolve;
  });

  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: universes }));
  await page.route("**/api/scan", async (route) => {
    firstScanRequest();
    await firstBatchReleased;
    const payload = route.request().postDataJSON();
    await fulfillJson(route, payload.tickers.map(successfulResult));
  });

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.locator("#scan-tickers").fill("NVDA, MSFT");
  await page.locator("#scan-start-period").fill("2025-01-01");
  await page.locator("#scan-end-period").fill("2025-12-31");
  await page.getByRole("button", { name: "開始集體回測" }).click();
  await firstScanStarted;

  await expect(page.locator("#scan-results")).toBeVisible();
  await expect(page.locator("#scan-results-pending")).toBeVisible();
  await expect(page.locator("#scan-results-pending")).toContainText("等待第一批結果");
  await expect(page.locator("#scan-results-pending")).toContainText("2 檔、1 批");
  await expect(page.locator("#scan-summary")).not.toBeVisible();
  await expect(page.locator("#scan-table")).not.toBeVisible();
  await expect(page.locator("#scan-results")).toHaveAttribute("data-scan-state", "waiting-first-result");

  releaseFirstBatch();

  await expect(page.locator("#scan-results-pending")).toBeHidden();
  await expect(page.locator("#scan-summary")).toContainText("2 / 2");
  await expect(page.locator("#scan-table")).toContainText("NVDA");
  await expect(page.locator("#scan-results")).not.toHaveAttribute("data-scan-state", "waiting-first-result");
});

test("clears the execution plan when the selected filters return no candidates", async ({ page }) => {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: universes }));
  await page.route("**/api/v2/screener", (route) => fulfillJson(route, {
    universe: {
      id: "sp500",
      name: "S&P 500（IVV holdings）",
      version: "2026-08-13-sp500",
      sourceAsOf: "2026-08-13",
    },
    fundamentalsAsOf: "2026-08-13",
    funnel: {
      universeCount: 504,
      fundamentalsAvailable: 500,
      sectorMatches: 0,
      passedFilters: 0,
      selectedForScan: 0,
    },
    candidates: [],
    warnings: [],
  }));

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await expect(page.locator("#scan-execution-plan")).toBeVisible();

  await page.getByRole("button", { name: "篩選並建立回測清單" }).click();

  await expect(page.locator("#scan-tickers")).toHaveValue("");
  await expect(page.locator("#scan-execution-plan")).toBeHidden();
  await expect(page.locator("#scan-error")).toContainText("沒有符合目前條件的股票");
});
