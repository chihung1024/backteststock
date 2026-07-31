import { expect, test } from "@playwright/test";

const formulas = {
  original: {
    key: "sortino_alpha_mdd_score",
    label: "Sortino×Alpha/|MDD|",
  },
  recommended: {
    key: "alpha_sqrt_sortino_mdd_score",
    label: "建議分數",
  },
  percentile: {
    key: "percentile_composite_score",
    label: "百分位分數",
  },
};

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

function formulaHeader(page, formula) {
  return page.locator(`#scan-table th[data-composite-metric="${formula.key}"]`);
}

function formulaCell(row, formula) {
  return row.locator(`td[data-composite-metric="${formula.key}"]`);
}

test("compares and sorts three scan score formulas", async ({ page }) => {
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

  const originalHeader = formulaHeader(page, formulas.original);
  const recommendedHeader = formulaHeader(page, formulas.recommended);
  const percentileHeader = formulaHeader(page, formulas.percentile);
  const tickerCells = page.locator("#scan-table tbody tr th:first-child");

  await expect(originalHeader).toHaveText(formulas.original.label);
  await expect(recommendedHeader).toHaveText(formulas.recommended.label);
  await expect(percentileHeader).toHaveText(formulas.percentile.label);
  for (const formula of Object.values(formulas)) {
    await expect(formulaHeader(page, formula)).toHaveClass(/sortable/);
    await expect(formulaHeader(page, formula)).toHaveAttribute("data-sort-key", formula.key);
  }
  await expect(page.locator('#scan-table th[data-composite-metric="ten_year_quality_score"]')).toHaveCount(0);
  await expect(page.locator('#scan-table th[data-composite-metric="sortino_alpha_beta_mdd_score"]')).toHaveCount(0);
  await expect(page.locator("#score-formula-comparison")).toContainText("每格顯示「名次 · 分數」");

  const nvdaRow = page.locator("#scan-table tbody tr", { hasText: "NVDA" });
  const msftRow = page.locator("#scan-table tbody tr", { hasText: "MSFT" });
  const qualityRow = page.locator("#scan-table tbody tr", { hasText: "QUALITY" });
  const shortRow = page.locator("#scan-table tbody tr", { hasText: "SHORT" });
  const zeroRow = page.locator("#scan-table tbody tr", { hasText: "ZERO" });

  await expect(formulaCell(nvdaRow, formulas.original)).toHaveText("#3 · 0.6558");
  await expect(formulaCell(msftRow, formulas.original)).toHaveText("#4 · 0.4000");
  await expect(formulaCell(qualityRow, formulas.original)).toHaveText("#2 · 0.8000");
  await expect(formulaCell(shortRow, formulas.original)).toHaveText("#1 · 11.1846");

  await expect(formulaCell(nvdaRow, formulas.recommended)).toHaveText("#2 · 0.2343");
  await expect(formulaCell(msftRow, formulas.recommended)).toHaveText("#4 · 0.1265");
  await expect(formulaCell(qualityRow, formulas.recommended)).toHaveText("#3 · 0.2191");
  await expect(formulaCell(shortRow, formulas.recommended)).toHaveText("#1 · 3.4956");

  await expect(formulaCell(nvdaRow, formulas.percentile)).toHaveText("#2 · 50.00");
  await expect(formulaCell(msftRow, formulas.percentile)).toHaveText("#4 · 20.00");
  await expect(formulaCell(qualityRow, formulas.percentile)).toHaveText("#2 · 50.00");
  await expect(formulaCell(shortRow, formulas.percentile)).toHaveText("#1 · 80.00");

  for (const formula of Object.values(formulas)) {
    await expect(formulaCell(zeroRow, formula)).toHaveText("—");
    await expect(formulaCell(zeroRow, formula)).toHaveAttribute("title", /最大回撤為 0/);
  }

  await expect(tickerCells).toHaveText([
    "SHORT （從 2024-03-27 開始）",
    "MSFT",
    "NVDA",
    "QUALITY",
    "ZERO",
  ]);

  await originalHeader.click();
  await expect(originalHeader).toHaveText(`${formulas.original.label} ▼`);
  await expect(originalHeader).toHaveAttribute("aria-sort", "descending");
  await expect(tickerCells).toHaveText([
    "SHORT （從 2024-03-27 開始）",
    "QUALITY",
    "NVDA",
    "MSFT",
    "ZERO",
  ]);

  await originalHeader.click();
  await expect(originalHeader).toHaveText(`${formulas.original.label} ▲`);
  await expect(originalHeader).toHaveAttribute("aria-sort", "ascending");
  await expect(tickerCells).toHaveText([
    "MSFT",
    "NVDA",
    "QUALITY",
    "SHORT （從 2024-03-27 開始）",
    "ZERO",
  ]);

  await percentileHeader.click();
  await expect(percentileHeader).toHaveText(`${formulas.percentile.label} ▼`);
  await expect(percentileHeader).toHaveAttribute("aria-sort", "descending");
  await expect(tickerCells).toHaveText([
    "SHORT （從 2024-03-27 開始）",
    "NVDA",
    "QUALITY",
    "MSFT",
    "ZERO",
  ]);

  await page.getByRole("button", { name: "方法與限制" }).click();
  await expect(page.locator("#about-panel")).toContainText("Sortino × Alpha ÷ |最大回撤|");
  await expect(page.locator("#about-panel")).toContainText("Alpha × √(Sortino ÷ |最大回撤|)");
  await expect(page.locator("#about-panel")).toContainText("50% Alpha、30% Sortino、20% 低回撤");
  await expect(page.locator("#about-panel")).not.toContainText("十年品質分數");
  await expect(page.locator("#about-panel")).not.toContainText("Sortino × Alpha ÷ (1 + Beta)");
});
