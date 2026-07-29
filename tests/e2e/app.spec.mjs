import { expect, test } from "@playwright/test";

const universes = [
  {
    id: "sp500",
    name: "S&P 500（IVV holdings）",
    source: { label: "iShares IVV holdings", url: "https://example.com/ivv", isProxy: true },
    available: true,
    version: "2026-07-27-sp500",
    sourceAsOf: "2026-07-27",
    memberCount: 504,
    warnings: [],
  },
  {
    id: "nasdaq100",
    name: "NASDAQ-100（自動備援）",
    source: { label: "Nasdaq Global Index Watch", url: "https://example.com/ndx", isProxy: false },
    available: true,
    version: "2026-07-29-nasdaq100",
    sourceAsOf: "2026-07-29",
    memberCount: 103,
    warnings: [],
  },
  {
    id: "soxx",
    name: "SOXX holdings",
    source: { label: "iShares SOXX holdings", url: "https://example.com/soxx", isProxy: false },
    available: true,
    version: "2026-07-27-soxx",
    sourceAsOf: "2026-07-27",
    memberCount: 30,
    warnings: [],
  },
  {
    id: "russell2000",
    name: "Russell 2000（IWM holdings 代理）",
    source: { label: "iShares IWM holdings", url: "https://example.com/iwm", isProxy: true },
    available: true,
    version: "2026-07-27-russell2000",
    sourceAsOf: "2026-07-27",
    memberCount: 1964,
    warnings: [],
  },
];

const scanResults = [
  {
    ticker: "NVDA",
    total_return: 0.25,
    cagr: 0.25,
    volatility: 0.42,
    mdd: -0.18,
    sharpe_ratio: 1.1,
    sortino_ratio: 1.4,
    beta: 1.5,
    alpha: 0.08,
    data_coverage: 1,
    trading_days: 252,
    data_start: "2025-01-02",
    data_end: "2025-12-31",
    note: null,
  },
  {
    ticker: "MSFT",
    total_return: 0.18,
    cagr: 0.18,
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
];

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test("initializes the UI and completes the Universe scanner flow", async ({ page }) => {
  const pageErrors = [];
  const consoleErrors = [];
  let screenerPayload;
  let scanPayload;

  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, ["AAPL", "MSFT", "NVDA"]));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: universes }));
  await page.route("**/api/v2/screener", async (route) => {
    screenerPayload = route.request().postDataJSON();
    await fulfillJson(route, {
      universe: {
        id: "nasdaq100",
        name: "NASDAQ-100（自動備援）",
        version: "2026-07-29-nasdaq100",
        sourceAsOf: "2026-07-29",
      },
      fundamentalsAsOf: "2026-07-29",
      funnel: {
        universeCount: 103,
        fundamentalsAvailable: 93,
        sectorMatches: 93,
        passedFilters: 2,
        selectedForScan: 2,
      },
      candidates: [
        { ticker: "NVDA", marketCap: 4_300_000_000_000, sector: "Technology", trailingPE: 57 },
        { ticker: "MSFT", marketCap: 3_700_000_000_000, sector: "Technology", trailingPE: 37 },
      ],
      truncated: false,
      warnings: [],
    });
  });
  await page.route("**/api/scan", async (route) => {
    scanPayload = route.request().postDataJSON();
    await fulfillJson(route, scanResults);
  });

  await page.goto("/");

  await expect(page.locator("#service-status")).toHaveText("服務正常");
  await expect(page.locator('input[list="ticker-options"]')).toHaveCount(4);
  await expect(page.locator("#portfolio-list .portfolio-card")).toHaveCount(2);

  await page.getByRole("button", { name: "個股掃描" }).click();
  await expect(page.getByRole("heading", { name: "個股績效掃描" })).toBeVisible();
  await expect(page.locator("#universe-status")).toHaveText("4 個股票池可用");

  await page.locator("#screener-index").selectOption("nasdaq100");
  await page.locator("#screener-limit").selectOption("25");
  await page.getByRole("button", { name: "篩選並建立回測清單" }).click();

  await expect(page.locator("#scan-tickers")).toHaveValue("NVDA, MSFT");
  await expect(page.locator("#screener-funnel")).toContainText("納入回測");
  expect(screenerPayload).toMatchObject({
    universe: "nasdaq100",
    sector: "any",
    limit: 25,
    sort: "marketCap-desc",
  });

  await page.locator("#scan-start-period").fill("2025-01");
  await page.locator("#scan-end-period").fill("2025-12");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  await expect(page.locator("#scan-results")).toBeVisible();
  await expect(page.locator("#scan-summary")).toContainText("2 / 2");
  await expect(page.locator("#scan-table")).toContainText("NVDA");
  await expect(page.locator("#scan-context")).toContainText("NASDAQ-100");
  expect(scanPayload).toMatchObject({
    tickers: ["NVDA", "MSFT"],
    benchmark: "SPY",
    startYear: 2025,
    startMonth: 1,
    endYear: 2025,
    endMonth: 12,
  });

  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
