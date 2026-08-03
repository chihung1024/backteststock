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
    data_coverage: 1,
    trading_days: 950,
    data_start: "2022-03-15",
    data_end: "2025-12-31",
  },
];

const history = Array.from({ length: 950 }, (_, index) => ({
  date: new Date(Date.UTC(2022, 0, 3 + index)).toISOString().slice(0, 10),
  value: 1_000_000 + index * 1000,
  return_index: 1 + index / 1000,
  drawdown: index % 100 === 0 ? -0.05 : 0,
  cumulative_income: index * 10,
}));

function fullPortfolioResult() {
  return {
    name: "績效列表已選標的等權組合",
    display_name: "績效列表已選標的等權組合 · AAA 50% · BBB 50%",
    metrics: {
      initial_balance: 1_000_000,
      final_balance: 1_950_000,
      net_profit: 950_000,
      total_return: 0.95,
      cagr: 0.17,
      volatility: 0.21,
      max_drawdown: -0.19,
      sharpe_ratio: 0.86,
      sortino_ratio: 1.31,
      beta: 1.02,
      alpha: 0.035,
      calmar_ratio: 0.89,
      var_95_daily: -0.023,
      cvar_95_daily: -0.034,
      positive_month_ratio: 0.62,
      transaction_costs: 0,
      borrowing_costs: 0,
      rebalance_count: 3,
    },
    series: history,
    annual_returns: { "2022": -0.1, "2023": 0.3, "2024": 0.2, "2025": 0.15 },
    monthly_returns: [{ year: 2025, month: 1, return: 0.04 }],
    income_by_year: { "2022": 5000, "2023": 9000, "2024": 11000, "2025": 12000 },
    target_allocation: { AAA: 0.5, BBB: 0.5 },
    final_allocation: { AAA: 0.52, BBB: 0.48 },
    factor_analysis: null,
    style_analysis: null,
    regime_analysis: null,
  };
}

test("integrates selected stocks and full portfolio results into one performance workspace", async ({ page }) => {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, ["AAA", "BBB", "SPY"]));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.route("**/api/scan", (route) => fulfillJson(route, scanRows));
  await page.route("**/api/portfolio-lab/backtests", async (route) => {
    const payload = route.request().postDataJSON();
    expect(payload.portfolios).toHaveLength(1);
    expect(payload.portfolios[0].assets.map((asset) => asset.symbol)).toEqual(["AAA", "BBB"]);
    expect(payload.portfolios[0].assets.reduce((sum, asset) => sum + asset.weight, 0)).toBeCloseTo(100, 6);
    await fulfillJson(route, {
      request_id: "integrated-request",
      generated_at: "2026-08-03T12:00:00Z",
      data_as_of: history.at(-1).date,
      effective_start: history[0].date,
      effective_end: history.at(-1).date,
      base_currency: "TWD",
      results: [fullPortfolioResult()],
      benchmark: null,
      assets: [],
      warnings: [],
    });
  });

  await page.goto("/");
  await expect(page.locator("#scanner-panel")).toBeVisible();
  await expect(page.getByRole("button", { name: "績效研究（個股掃描）" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#backtest-panel")).not.toBeVisible();

  await page.locator("#scan-tickers").fill("AAA, BBB");
  await page.locator("#scan-start-period").fill("2022-01-01");
  await page.locator("#scan-end-period").fill("2025-12-31");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  const headers = page.locator("#scan-table thead th");
  await expect(headers).toContainText([
    "股票代碼",
    "候選",
    "區間總報酬",
    "年化報酬率",
    "年化波動率",
    "最大回撤",
    "Sharpe",
    "Sortino",
    "Beta",
    "Alpha",
    "穩健分數",
    "成長分數",
    "回撤控制分數",
    "資料覆蓋率",
    "交易日",
    "資料區間",
  ]);

  const choices = page.locator('#scan-table input[data-optimizer-ticker]');
  await choices.nth(0).check();
  await choices.nth(1).check();

  const openBacktest = page.locator("#open-integrated-backtest");
  await expect(openBacktest).toHaveText("使用已選 2 檔建立投組回測");
  await openBacktest.click();

  const dialog = page.locator("#integrated-backtest-dialog");
  const lab = dialog.locator("#portfolio-lab");
  await expect(dialog).toHaveJSProperty("open", true);
  await expect(lab.getByRole("tab", { name: "資產配置" })).toHaveAttribute("class", /active/);
  const tickerInputs = lab.locator(".pl-ticker-search input");
  await expect(tickerInputs.nth(0)).toHaveValue("AAA");
  await expect(tickerInputs.nth(1)).toHaveValue("BBB");
  await expect(lab.locator(".pl-matrix tbody tr").nth(0).locator("td").nth(1).locator("input")).toHaveValue("50");
  await expect(lab.locator(".pl-matrix tbody tr").nth(1).locator("td").nth(1).locator("input")).toHaveValue("50");

  await lab.getByRole("button", { name: "執行完整回測" }).click();
  await expect(lab.locator("#pl-results")).toContainText("績效列表已選標的等權組合");
  await dialog.getByRole("button", { name: "關閉並返回績效列表" }).click();

  const portfolioRow = page.locator("#scan-table tbody tr.integrated-portfolio-row");
  await expect(portfolioRow).toHaveCount(1);
  await expect(portfolioRow).toContainText("投組｜績效列表已選標的等權組合");
  await expect(portfolioRow).toContainText("17.00%");
  await expect(portfolioRow).toContainText("95.00%");
  await expect(portfolioRow).toContainText("950");

  await page.getByRole("button", { name: "開始集體回測" }).click();
  await expect(portfolioRow).toHaveCount(0);
});


test("integrated backtest ignores a stale optimizer selection from another scan job", async ({ page }) => {
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
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));

  await page.goto("/");
  await expect(page.locator("#scanner-panel")).toBeVisible();
  await expect(page.locator("#open-integrated-backtest")).toBeDisabled();
});

test("integrated backtest rejects a saved ticker below the current coverage threshold", async ({ page }) => {
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
        {
          ticker: "AAA",
          status: "ok",
          retryable: false,
          trading_days: 1000,
          metric_definition_version: "2026-08-01.2",
        },
        {
          ticker: "LOW",
          status: "ok",
          retryable: false,
          trading_days: 800,
          metric_definition_version: "2026-08-01.2",
        },
      ],
    }));
    localStorage.setItem("backteststock-optimizer-manual-selection-v2", JSON.stringify({
      version: 2,
      sourceJobId: "current-scan",
      coverageThresholdPercent: 90,
      tickers: ["LOW"],
    }));
  });
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));

  await page.goto("/");
  await expect(page.locator("#scanner-panel")).toBeVisible();
  await expect(page.locator("#open-integrated-backtest")).toBeDisabled();
});
