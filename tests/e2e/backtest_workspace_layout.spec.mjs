import { expect, test } from "@playwright/test";

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockShellApis(page) {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, ["QQQ", "SOXX", "VTI", "BND", "SPY"]));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.route("**/api/portfolio-lab/assets/search**", (route) => fulfillJson(route, [
    { symbol: "VT", name: "Vanguard Total World Stock ETF", currency: "USD" },
  ]));
}

function portfolioResult(name, multiplier = 1) {
  return {
    name,
    display_name: `${name} · QQQ 60% · SOXX 40%`,
    metrics: {
      initial_balance: 1000000,
      final_balance: 2000000 * multiplier,
      net_profit: 1000000 * multiplier,
      total_return: 1 * multiplier,
      cagr: 0.12 * multiplier,
      money_weighted_return: 0.115 * multiplier,
      volatility: 0.22,
      sharpe_ratio: 0.8,
      sortino_ratio: 1.1,
      max_drawdown: -0.32,
      calmar_ratio: 0.38,
      var_95_daily: -0.025,
      cvar_95_daily: -0.036,
      positive_month_ratio: 0.63,
      transaction_costs: 1200,
      borrowing_costs: 0,
      rebalance_count: 9,
      beta: 1.05,
      alpha: 0.02,
      benchmark_correlation: 0.91,
    },
    series: [
      { date: "2020-01-02", value: 1000000, return_index: 1, drawdown: 0, cumulative_income: 0 },
      { date: "2021-01-04", value: 1300000, return_index: 1.3, drawdown: -0.05, cumulative_income: 12000 },
      { date: "2022-01-03", value: 1100000, return_index: 1.1, drawdown: -0.22, cumulative_income: 26000 },
      { date: "2023-01-03", value: 2000000 * multiplier, return_index: 2 * multiplier, drawdown: 0, cumulative_income: 42000 },
    ],
    annual_returns: { "2020": 0.18, "2021": 0.24, "2022": -0.19, "2023": 0.31 },
    monthly_returns: [
      { year: 2023, month: 1, return: 0.04 },
      { year: 2023, month: 2, return: -0.02 },
    ],
    income_by_year: { "2020": 6000, "2021": 12000, "2022": 11000, "2023": 13000 },
    target_allocation: { QQQ: 0.6, SOXX: 0.4 },
    final_allocation: { QQQ: 0.64, SOXX: 0.36 },
    factor_analysis: { model: "Fama-French 5 Factor + Momentum", annualized_alpha: 0.02, betas: { MKT_RF: 1.03 } },
    style_analysis: { model: "Returns-based U.S. equity style proxy", exposures: { large_growth: 0.72 } },
    regime_analysis: { type: "market", regimes: [{ name: "Bull market", months: 20, annualized_return: 0.18 }] },
  };
}

function backtestResponse() {
  return {
    request_id: "request-1",
    generated_at: "2026-08-03T12:00:00Z",
    data_as_of: "2023-01-03",
    effective_start: "2020-01-02",
    effective_end: "2023-01-03",
    base_currency: "TWD",
    results: [portfolioResult("投組 1"), portfolioResult("投組 2", 0.9)],
    benchmark: {
      ...portfolioResult("Benchmark · SPY", 0.75),
      display_name: "Benchmark · SPY",
      factor_analysis: null,
      style_analysis: null,
      regime_analysis: null,
    },
    assets: [],
    warnings: ["Common start moved because of asset inception dates"],
  };
}

async function openPortfolioLab(page) {
  await page.goto("/");
  await page.getByRole("button", { name: "投資組合回測" }).click();
  const dialog = page.locator("#integrated-backtest-dialog");
  const lab = dialog.locator("#portfolio-lab");
  await expect(dialog).toHaveJSProperty("open", true);
  await expect(lab).toBeVisible();
  return { dialog, lab };
}

test("portfolio lab ports the original functional design and result dashboard", async ({ page }) => {
  await mockShellApis(page);
  let submittedPayload;
  await page.route("**/api/portfolio-lab/backtests", async (route) => {
    submittedPayload = route.request().postDataJSON();
    await fulfillJson(route, backtestResponse());
  });

  const { dialog, lab } = await openPortfolioLab(page);
  await expect(lab).toContainText("投資組合回測實驗室");
  await expect(lab.getByRole("tab", { name: "回測設定" })).toBeVisible();
  await expect(lab.getByText("定期現金流", { exact: true })).toBeVisible();
  await expect(lab.getByText("再平衡", { exact: true })).toBeVisible();
  await expect(lab.getByText("槓桿與保證金", { exact: true })).toBeVisible();
  await expect(lab.getByText("進階分析", { exact: true })).toBeVisible();

  await lab.getByLabel("現金流方式").selectOption("fixed");
  await expect(lab.getByLabel("金額／比例")).toBeVisible();
  await lab.getByLabel("金額／比例").fill("5000");
  await lab.getByLabel("槓桿方式").selectOption("fixed_ratio");
  const leverageRatio = lab.getByRole("spinbutton", { name: "槓桿倍數", exact: true });
  await expect(leverageRatio).toBeVisible();
  await leverageRatio.fill("1.5");
  await lab.getByText("報酬式風格分析", { exact: true }).click();
  await lab.getByText("Fama–French 因子回歸", { exact: true }).click();
  await lab.getByLabel("市場環境分析").selectOption("market");

  await lab.getByRole("tab", { name: "資產配置" }).click();
  await expect(lab.locator(".pl-matrix tbody tr")).toHaveCount(7);
  await expect(lab.locator(".pl-matrix thead th")).toHaveCount(7);
  await expect(lab.locator(".pl-total-row td.complete")).toHaveCount(2);
  await expect(lab.getByRole("button", { name: /新增資產/ })).toBeVisible();

  await lab.locator(".pl-ticker-search input").nth(2).fill("VT");
  await expect(lab.getByRole("button", { name: /VT Vanguard Total World Stock ETF/ })).toBeVisible();

  await lab.getByRole("button", { name: "執行完整回測" }).click();
  await expect.poll(() => submittedPayload).toBeTruthy();
  expect(submittedPayload.cashflow).toMatchObject({ type: "fixed", amount: 5000, frequency: "monthly" });
  expect(submittedPayload.leverage).toMatchObject({ type: "fixed_ratio", ratio: 1.5 });
  expect(submittedPayload.analytics).toMatchObject({ style_analysis: true, factor_regression: true, regime: "market" });
  expect(submittedPayload.portfolios).toHaveLength(2);

  await expect(lab.locator("#pl-results")).toBeVisible();
  await expect(lab.getByText("完整回測結果", { exact: true })).toBeVisible();
  await expect(lab.locator(".pl-summary")).toHaveCount(3);
  await expect(lab.getByText("XIRR", { exact: true })).toBeVisible();
  await expect(lab.getByText("CVaR 95%（日）", { exact: true })).toBeVisible();

  await lab.getByRole("tab", { name: "資產成長" }).click();
  await expect(lab.locator("canvas.pl-chart")).toBeVisible();
  await lab.getByRole("tab", { name: "年度報酬" }).click();
  await expect(lab.getByText("2023", { exact: true }).first()).toBeVisible();
  await lab.getByRole("tab", { name: "月報酬熱圖" }).click();
  await expect(lab.locator(".pl-heatmap")).toBeVisible();
  await expect(lab.locator('.pl-heatmap td[data-heat="0.04"]')).toHaveCSS("background-color", /rgba?\(/);
  await lab.getByRole("tab", { name: "配置", exact: true }).click();
  await expect(lab.locator(".pl-allocation-card")).toHaveCount(2);
  await lab.getByRole("tab", { name: "分析", exact: true }).click();
  await expect(lab.getByText("Fama–French", { exact: true }).first()).toBeVisible();

  await dialog.getByRole("button", { name: "關閉並返回績效列表" }).click();
  await expect(dialog).toHaveJSProperty("open", false);
});

test("portfolio lab remains usable at mobile width with two default portfolios", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockShellApis(page);
  const { dialog, lab } = await openPortfolioLab(page);

  const dialogBox = await dialog.boundingBox();
  expect(dialogBox).not.toBeNull();
  expect(dialogBox.width).toBeLessThanOrEqual(390);

  await lab.getByRole("tab", { name: "資產配置" }).click();
  await expect(lab.locator(".pl-matrix thead th")).toHaveCount(4);
  await expect(lab.locator(".pl-total-row td.complete")).toHaveCount(2);
  const runButton = lab.getByRole("button", { name: "執行完整回測" });
  await expect(runButton).toBeVisible();
  const buttonBox = await runButton.boundingBox();
  expect(buttonBox).not.toBeNull();
  expect(buttonBox.width).toBeGreaterThan(300);
  expect(buttonBox.width).toBeLessThanOrEqual(dialogBox.width);
});
