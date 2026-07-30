import { expect, test } from "@playwright/test";

const scoreKey = "sortino_alpha_beta_mdd_score";
const scoreLabel = "Sortino×Alpha/(1+Beta)/|MDD|";

const scanResults = [
  {
    ticker: "NVDA",
    status: "ok",
    retryable: false,
    total_return: 0.25,
    cagr: 0.25,
    volatility: 0.42,
    mdd: -0.1834,
    sharpe_ratio: 1.1,
    sortino_ratio: 1.437,
    beta: 1.527,
    alpha: 0.0837,
    data_coverage: 1,
    trading_days: 252,
    data_start: "2025-01-02",
    data_end: "2025-12-31",
    note: null,
  },
  {
    ticker: "MSFT",
    status: "ok",
    retryable: false,
    total_return: 0.30,
    cagr: 0.30,
    volatility: 0.24,
    mdd: -0.12,
    sharpe_ratio: 0.9,
    sortino_ratio: 1.2,
    beta: 1.05,
    alpha: 0.04,
    data_coverage: 1,
    trading_days: 252,
    data_start: "2025-01-02",
    data_end: "2025-12-31",
    note: null,
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
    trading_days: 252,
    data_start: "2025-01-02",
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

test("adds and sorts the requested composite score using raw scan metrics", async ({ page }) => {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, ["NVDA", "MSFT", "ZERO"]));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.route("**/api/scan", (route) => fulfillJson(route, scanResults));

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.locator("#scan-tickers").fill("NVDA, MSFT, ZERO");
  await page.locator("#scan-start-period").fill("2025-01");
  await page.locator("#scan-end-period").fill("2025-12");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  const scoreHeader = page.locator(`#scan-table th[data-composite-metric="${scoreKey}"]`);
  const tickerCells = page.locator("#scan-table tbody tr th:first-child");
  await expect(scoreHeader).toHaveText(scoreLabel);
  await expect(scoreHeader).toHaveClass(/sortable/);
  await expect(scoreHeader).toHaveAttribute("data-sort-key", scoreKey);

  const nvdaRow = page.locator("#scan-table tbody tr", { hasText: "NVDA" });
  const msftRow = page.locator("#scan-table tbody tr", { hasText: "MSFT" });
  const zeroRow = page.locator("#scan-table tbody tr", { hasText: "ZERO" });

  await expect(nvdaRow.locator(`td[data-composite-metric="${scoreKey}"]`)).toHaveText("0.2595");
  await expect(msftRow.locator(`td[data-composite-metric="${scoreKey}"]`)).toHaveText("0.1951");
  await expect(zeroRow.locator(`td[data-composite-metric="${scoreKey}"]`)).toHaveText("—");

  await expect(tickerCells).toHaveText(["MSFT", "NVDA", "ZERO"]);

  await scoreHeader.click();
  await expect(scoreHeader).toHaveText(`${scoreLabel} ▼`);
  await expect(scoreHeader).toHaveAttribute("aria-sort", "descending");
  await expect(tickerCells).toHaveText(["NVDA", "MSFT", "ZERO"]);

  await scoreHeader.click();
  await expect(scoreHeader).toHaveText(`${scoreLabel} ▲`);
  await expect(scoreHeader).toHaveAttribute("aria-sort", "ascending");
  await expect(tickerCells).toHaveText(["MSFT", "NVDA", "ZERO"]);
});
