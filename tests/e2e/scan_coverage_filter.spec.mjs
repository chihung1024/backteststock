import { expect, test } from "@playwright/test";

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function scanRow(ticker, dataCoverage) {
  return {
    ticker,
    status: "ok",
    retryable: false,
    total_return: 0.2,
    cagr: 0.1,
    volatility: 0.2,
    mdd: -0.15,
    sharpe_ratio: 0.8,
    sortino_ratio: 1.1,
    beta: 1,
    alpha: 0.02,
    data_coverage: dataCoverage,
    trading_days: 252,
    data_start: "2025-01-02",
    data_end: "2025-12-31",
  };
}

test("defaults to 90% coverage and lets the user adjust the visible scan list", async ({ page }) => {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.route("**/api/scan", (route) => fulfillJson(route, [
    scanRow("FULL", 1),
    scanRow("AT90", 0.9),
    scanRow("LOW", 0.899),
    scanRow("MISSING", null),
  ]));

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.locator("#scan-tickers").fill("FULL, AT90, LOW, MISSING");
  await page.locator("#scan-start-period").fill("2025-01-01");
  await page.locator("#scan-end-period").fill("2025-12-31");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  const rows = page.locator("#scan-table tbody tr");
  await expect(page.locator("#scan-min-coverage")).toHaveValue("90");
  await expect(rows).toHaveCount(2);
  await expect(rows).toContainText(["FULL", "AT90"]);
  await expect(page.locator("#scan-coverage-filter-status")).toHaveText(
    "顯示 2 / 4 檔 · 門檻 ≥ 90% · 隱藏 2 檔",
  );
  await expect(page.locator("#scan-summary")).toContainText("符合覆蓋率門檻");
  await expect(page.locator("#scan-summary")).toContainText("2 / 4");

  await page.locator("#scan-min-coverage").fill("89.9");
  await expect(rows).toHaveCount(3);
  await expect(rows).toContainText(["FULL", "AT90", "LOW"]);
  await expect(page.locator("#scan-coverage-filter-status")).toHaveText(
    "顯示 3 / 4 檔 · 門檻 ≥ 89.9% · 隱藏 1 檔",
  );

  await page.locator("#scan-min-coverage").fill("0");
  await expect(rows).toHaveCount(3);
  await expect(rows).toContainText(["FULL", "AT90", "LOW"]);
  await expect(page.locator("#scan-coverage-filter-status")).toHaveText(
    "顯示 3 / 4 檔 · 門檻 ≥ 0% · 隱藏 1 檔",
  );
});
