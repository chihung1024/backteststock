import { expect, test } from "@playwright/test";

const scoreKey = "sortino_alpha_mdd_score";
const scoreLabel = "Sortino×Alpha/|MDD|";

const scanResults = [
  {
    ticker: "NVDA",
    status: "ok",
    retryable: false,
    total_return: 5,
    cagr: 0.25,
    volatility: 0.42,
    mdd: -0.1834,
    sharpe_ratio: 1.1,
    sortino_ratio: 1.437,
    beta: 1.527,
    alpha: 0.0837,
    data_coverage: 1,
    trading_days: 2520,
    data_start: "2016-01-04",
    data_end: "2025-12-31",
    note: null,
  },
  {
    ticker: "MSFT",
    status: "ok",
    retryable: false,
    total_return: 8,
    cagr: 0.30,
    volatility: 0.24,
    mdd: -0.12,
    sharpe_ratio: 0.9,
    sortino_ratio: 1.2,
    beta: 1.05,
    alpha: 0.04,
    data_coverage: 1,
    trading_days: 2520,
    data_start: "2016-01-04",
    data_end: "2025-12-31",
    note: null,
  },
  {
    ticker: "QUALITY",
    status: "ok",
    retryable: false,
    total_return: 4,
    cagr: 0.20,
    volatility: 0.20,
    mdd: -0.15,
    sharpe_ratio: 1.5,
    sortino_ratio: 2.0,
    beta: 0.8,
    alpha: 0.06,
    data_coverage: 0.90,
    trading_days: 2268,
    data_start: "2017-01-03",
    data_end: "2025-12-31",
    note: null,
  },
  {
    ticker: "SHORT",
    status: "ok",
    retryable: false,
    total_return: 6.5,
    cagr: 1.3667,
    volatility: 0.539,
    mdd: -0.3829,
    sharpe_ratio: 2.54,
    sortino_ratio: 3.92,
    beta: 1.84,
    alpha: 1.0925,
    data_coverage: 0.2249,
    trading_days: 567,
    data_start: "2024-03-27",
    data_end: "2025-12-31",
    note: "（從 2024-03-27 開始）",
  },
  {
    ticker: "ZERO",
    status: "ok",
    retryable: false,
    total_return: 0,
    cagr: 0,
    volatility: 0,
    mdd: 0,
    sharpe_ratio: 0,
    sortino_ratio: 1,
    beta: 1,
    alpha: 0.02,
    data_coverage: 1,
    trading_days: 2520,
    data_start: "2016-01-04",
    data_end: "2025-12-31",
    note: null,
  },
];

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test("uses and sorts Sortino times Alpha divided by absolute MDD", async ({ page }) => {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, scanResults.map((item) => item.ticker)));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.route("**/api/scan", (route) => fulfillJson(route, scanResults));

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.locator("#scan-tickers").fill(scanResults.map((item) => item.ticker).join(", "));
  await page.locator("#scan-start-period").fill("2016-01");
  await page.locator("#scan-end-period").fill("2025-12");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  const scoreHeader = page.locator(`#scan-table th[data-composite-metric="${scoreKey}"]`);
  const tickerCells = page.locator("#scan-table tbody tr th:first-child");
  await expect(scoreHeader).toHaveText(scoreLabel);
  await expect(scoreHeader).toHaveClass(/sortable/);
  await expect(scoreHeader).toHaveAttribute("data-sort-key", scoreKey);
  await expect(page.locator('#scan-table th[data-composite-metric="ten_year_quality_score"]')).toHaveCount(0);
  await expect(page.locator('#scan-table th[data-composite-metric="sortino_alpha_beta_mdd_score"]')).toHaveCount(0);

  const nvdaRow = page.locator("#scan-table tbody tr", { hasText: "NVDA" });
  const msftRow = page.locator("#scan-table tbody tr", { hasText: "MSFT" });
  const qualityRow = page.locator("#scan-table tbody tr", { hasText: "QUALITY" });
  const shortRow = page.locator("#scan-table tbody tr", { hasText: "SHORT" });
  const zeroRow = page.locator("#scan-table tbody tr", { hasText: "ZERO" });

  await expect(nvdaRow.locator(`td[data-composite-metric="${scoreKey}"]`)).toHaveText("0.6558");
  await expect(msftRow.locator(`td[data-composite-metric="${scoreKey}"]`)).toHaveText("0.4000");
  await expect(qualityRow.locator(`td[data-composite-metric="${scoreKey}"]`)).toHaveText("0.8000");
  await expect(shortRow.locator(`td[data-composite-metric="${scoreKey}"]`)).toHaveText("11.1846");
  await expect(zeroRow.locator(`td[data-composite-metric="${scoreKey}"]`)).toHaveText("—");
  await expect(zeroRow.locator(`td[data-composite-metric="${scoreKey}"]`)).toHaveAttribute("title", /最大回撤為 0/);

  await expect(tickerCells).toHaveText([
    "SHORT （從 2024-03-27 開始）",
    "MSFT",
    "NVDA",
    "QUALITY",
    "ZERO",
  ]);

  await scoreHeader.click();
  await expect(scoreHeader).toHaveText(`${scoreLabel} ▼`);
  await expect(scoreHeader).toHaveAttribute("aria-sort", "descending");
  await expect(tickerCells).toHaveText([
    "SHORT （從 2024-03-27 開始）",
    "QUALITY",
    "NVDA",
    "MSFT",
    "ZERO",
  ]);

  await scoreHeader.click();
  await expect(scoreHeader).toHaveText(`${scoreLabel} ▲`);
  await expect(scoreHeader).toHaveAttribute("aria-sort", "ascending");
  await expect(tickerCells).toHaveText([
    "MSFT",
    "NVDA",
    "QUALITY",
    "SHORT （從 2024-03-27 開始）",
    "ZERO",
  ]);

  await page.getByRole("button", { name: "方法與限制" }).click();
  await expect(page.locator("#about-panel")).toContainText("Sortino × Alpha ÷ |最大回撤|");
  await expect(page.locator("#about-panel")).not.toContainText("十年品質分數");
  await expect(page.locator("#about-panel")).not.toContainText("Sortino × Alpha ÷ (1 + Beta)");
});
