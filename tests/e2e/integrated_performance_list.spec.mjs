import { expect, test } from "@playwright/test";

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

const scanRows = [
  {
    ticker: "AAA",
    status: "ok",
    retryable: false,
    total_return: 1.2,
    cagr: 0.18,
    volatility: 0.24,
    mdd: -0.22,
    sharpe_ratio: 0.9,
    sortino_ratio: 1.4,
    beta: 1.1,
    alpha: 0.04,
    data_coverage: 1,
    trading_days: 1000,
    data_start: "2022-01-03",
    data_end: "2025-12-31",
    metric_definition_version: "2026-08-01.2",
  },
  {
    ticker: "BBB",
    status: "ok",
    retryable: false,
    total_return: 0.8,
    cagr: 0.15,
    volatility: 0.20,
    mdd: -0.18,
    sharpe_ratio: 0.8,
    sortino_ratio: 1.2,
    beta: 0.9,
    alpha: 0.03,
    data_coverage: 0.95,
    trading_days: 950,
    data_start: "2022-03-15",
    data_end: "2025-12-31",
    metric_definition_version: "2026-08-01.2",
  },
];

async function mockApis(page) {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, ["AAA", "BBB", "SPY"]));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.route("**/api/scan", (route) => fulfillJson(route, scanRows));
  await page.route("**/api/v3/portfolio/health", (route) => fulfillJson(route, {
    status: "ok",
    service: "backteststock-portfolio-v3",
  }));
  await page.route("**/api/v3/portfolio/assets/search**", (route) => fulfillJson(route, []));
}

test("scanner selection navigates to Portfolio and restores the source workspace on return", async ({ page }) => {
  await mockApis(page);
  await page.goto("/");

  await expect(page.locator("#scanner-panel")).toBeVisible();
  await expect(page.getByRole("button", { name: "績效研究（個股掃描）" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#integrated-backtest-dialog")).toHaveCount(0);

  await page.locator("#scan-tickers").fill("AAA, BBB");
  await page.locator("#scan-start-period").fill("2022-01-01");
  await page.locator("#scan-end-period").fill("2025-12-31");
  await page.locator("#scan-benchmark").fill("SPY");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  await page.locator("#scan-min-coverage").fill("90");
  await page.locator("#scan-min-coverage").blur();
  const choices = page.locator('#scan-table input[data-optimizer-ticker]');
  await expect(choices).toHaveCount(2);
  await choices.nth(0).check();
  await choices.nth(1).check();

  const openPortfolio = page.locator("#open-integrated-backtest");
  await expect(openPortfolio).toHaveText("使用已選 2 檔建立投組回測");
  await expect(openPortfolio).toHaveAttribute("href", "/portfolio/");
  await expect(openPortfolio).toHaveAttribute("aria-disabled", "false");
  await openPortfolio.click();

  await expect(page).toHaveURL(/\/portfolio\/\?handoff=[0-9a-f-]+$/u);
  await expect(page.getByRole("heading", { name: "投資組合研究工作區" })).toBeVisible();
  await expect(page.locator("#portfolio-handoff-banner")).toContainText("Scanner 選股已導入");
  await expect(page.locator("#portfolio-handoff-banner")).toContainText("2022-01-01 → 2025-12-31");
  await expect(page.locator("#portfolio-handoff-banner")).toContainText("Benchmark SPY");
  await expect(page.locator("#portfolio-handoff-banner")).toContainText("資料覆蓋率門檻 90%");

  const tickers = page.locator(".desktop-matrix .ticker-cell input");
  await expect(tickers).toHaveCount(2);
  await expect(tickers.nth(0)).toHaveValue("AAA");
  await expect(tickers.nth(1)).toHaveValue("BBB");
  const weights = page.locator(".desktop-matrix tbody .weight-input input");
  await expect(weights.nth(0)).toHaveValue("50");
  await expect(weights.nth(1)).toHaveValue("50");

  const handoff = await page.evaluate(() => JSON.parse(
    sessionStorage.getItem("backteststock-portfolio-handoff-v1"),
  ));
  expect(handoff.source).toBe("scanner");
  expect(handoff.sourceJobId).toBeTruthy();
  expect(handoff.selectedTickers).toEqual(["AAA", "BBB"]);
  expect(handoff.startDate).toBe("2022-01-01");
  expect(handoff.endDate).toBe("2025-12-31");
  expect(handoff.benchmark).toBe("SPY");
  expect(handoff.coverageThresholdPercent).toBe(90);

  await page.getByRole("link", { name: "返回績效列表" }).click();
  await expect(page).toHaveURL(/\/?\?tab=scanner(?:#scan-results)?$/u);
  await expect(page.locator("#scanner-panel")).toBeVisible();
  await expect(page.locator("#scan-results")).toBeVisible();
  await expect(page.locator("#scan-min-coverage")).toHaveValue("90");
  const restoredChoices = page.locator('#scan-table input[data-optimizer-ticker]');
  await expect(restoredChoices.nth(0)).toBeChecked();
  await expect(restoredChoices.nth(1)).toBeChecked();
  await expect(page.locator("#integrated-backtest-dialog")).toHaveCount(0);
});

test("Portfolio handoff rejects a stale selection from another scan job", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-scan-job-v3", JSON.stringify({
      version: 3,
      id: "current-scan",
      status: "completed",
      payload: {
        tickers: ["AAA"],
        benchmark: "SPY",
        startDate: "2022-01-01",
        endDate: "2025-12-31",
      },
      pending: [],
      results: [{
        ticker: "AAA",
        status: "ok",
        retryable: false,
        trading_days: 1000,
        metric_definition_version: "2026-08-01.2",
      }],
    }));
    localStorage.setItem("backteststock-optimizer-manual-selection-v2", JSON.stringify({
      version: 2,
      sourceJobId: "old-scan",
      coverageThresholdPercent: 90,
      tickers: ["AAA"],
    }));
  });
  await mockApis(page);
  await page.goto("/");

  const link = page.locator("#open-integrated-backtest");
  await expect(link).toHaveAttribute("aria-disabled", "true");
  await expect(link).toHaveText("建立投資組合回測");
});

test("Portfolio handoff rejects a ticker below the active coverage threshold", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-scan-job-v3", JSON.stringify({
      version: 3,
      id: "current-scan",
      status: "completed",
      payload: {
        tickers: ["AAA", "LOW"],
        benchmark: "SPY",
        startDate: "2022-01-01",
        endDate: "2025-12-31",
      },
      pending: [],
      results: [
        { ticker: "AAA", status: "ok", retryable: false, trading_days: 1000, metric_definition_version: "2026-08-01.2" },
        { ticker: "LOW", status: "ok", retryable: false, trading_days: 800, metric_definition_version: "2026-08-01.2" },
      ],
    }));
    localStorage.setItem("backteststock-optimizer-manual-selection-v2", JSON.stringify({
      version: 2,
      sourceJobId: "current-scan",
      coverageThresholdPercent: 90,
      tickers: ["LOW"],
    }));
  });
  await mockApis(page);
  await page.goto("/");

  const link = page.locator("#open-integrated-backtest");
  await expect(link).toHaveAttribute("aria-disabled", "true");
  await expect(link).toHaveText("建立投資組合回測");
});

test("Portfolio handoff enforces the twenty-asset workspace limit", async ({ page }) => {
  const rows = Array.from({ length: 21 }, (_, index) => ({
    ticker: `T${String(index + 1).padStart(2, "0")}`,
    status: "ok",
    retryable: false,
    trading_days: 1000,
    metric_definition_version: "2026-08-01.2",
  }));
  await page.addInitScript((items) => {
    localStorage.setItem("backteststock-scan-job-v3", JSON.stringify({
      version: 3,
      id: "current-scan",
      status: "completed",
      payload: {
        tickers: items.map((item) => item.ticker),
        benchmark: "SPY",
        startDate: "2022-01-01",
        endDate: "2025-12-31",
      },
      pending: [],
      results: items,
    }));
    localStorage.setItem("backteststock-optimizer-manual-selection-v2", JSON.stringify({
      version: 2,
      sourceJobId: "current-scan",
      coverageThresholdPercent: 90,
      tickers: items.map((item) => item.ticker),
    }));
  }, rows);
  await mockApis(page);
  await page.goto("/");

  const link = page.locator("#open-integrated-backtest");
  await expect(link).toHaveAttribute("aria-disabled", "true");
  await expect(link).toContainText("上限 20");
});
