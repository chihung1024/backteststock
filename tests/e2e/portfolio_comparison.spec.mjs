import { expect, test } from "@playwright/test";

function resultItem(name, finalBalance) {
  return {
    name,
    display_name: `${name} · synthetic`,
    metrics: {
      initial_balance: 1_000_000,
      final_balance: finalBalance,
      contributions: 0,
      withdrawals: 0,
      net_contributions: 0,
      net_profit: finalBalance - 1_000_000,
      total_return: finalBalance / 1_000_000 - 1,
      cagr: 0.12,
      money_weighted_return: 0.12,
      xirr_status: "unique",
      volatility: 0.18,
      sharpe_ratio: 0.8,
      sortino_ratio: 1.1,
      max_drawdown: -0.2,
      calmar_ratio: 0.6,
      beta: 0.9,
      alpha: 0.01,
      benchmark_correlation: 0.85,
      transaction_costs: 0,
      borrowing_costs: 0,
      total_income: 0,
      rebalance_count: 2,
      observations: 688,
      start: "2023-12-15",
      end: "2026-08-10",
    },
    xirr: { status: "unique", value: 0.12, roots: [0.12], method: "test" },
    tail_risk: { method: "historical_simulation_daily", horizon: "daily", confidence: 0.95, var: -0.02, cvar: -0.03, observations: 687 },
    drawdown_events: [],
    annual_returns: [],
    monthly_returns: [],
    target_allocation: { TEST: 1 },
    final_allocation: { TEST: 1 },
    series: [
      { date: "2023-12-15", value: 1_000_000, return_index: 1, daily_return: 0, external_flow: 0, income: 0, cumulative_income: 0, cash: 0, debt: 0, gross_exposure: 1_000_000 },
      { date: "2026-08-10", value: finalBalance, return_index: finalBalance / 1_000_000, daily_return: 0.01, external_flow: 0, income: 0, cumulative_income: 0, cash: 0, debt: 0, gross_exposure: finalBalance },
    ],
    analytics: {},
    warnings: [],
    metadata: {},
    events: [],
  };
}

function preflightPayload() {
  return {
    request_id: "preflight-common-window",
    generated_at: "2026-08-11T00:00:00Z",
    contract_version: "portfolio-v3",
    schema_version: "portfolio-v3-2026-08-04.1",
    base_currency: "TWD",
    requested_start: "2016-08-10",
    requested_end: "2026-08-10",
    effective_end: "2026-08-10",
    assets: [],
    portfolios: [
      { name: "投資組合 1", status: "ready", symbols: ["GSIB"], missing_symbols: [], effective_start: "2023-12-15", effective_end: "2026-08-10", observations: 688 },
      { name: "投資組合 2", status: "ready", symbols: ["LVHI"], missing_symbols: [], effective_start: "2016-08-10", effective_end: "2026-08-10", observations: 2605 },
      { name: "投資組合 3", status: "ready", symbols: ["VLUE"], missing_symbols: [], effective_start: "2016-08-10", effective_end: "2026-08-10", observations: 2605 },
    ],
    benchmark: {
      symbol: "SPY",
      status: "ready",
      quote_currency: "USD",
      effective_start: "2016-08-10",
      effective_end: "2026-08-10",
      observations: 2605,
      fingerprints: {},
    },
    analysis_dependencies: [],
    warnings: [],
  };
}

function backtestPayload() {
  return {
    request_id: "backtest-common-window",
    generated_at: "2026-08-11T00:00:00Z",
    contract_version: "portfolio-v3",
    schema_version: "portfolio-v3-2026-08-04.1",
    base_currency: "TWD",
    requested_start: "2016-08-10",
    requested_end: "2026-08-10",
    effective_end: "2026-08-10",
    results: [
      resultItem("投資組合 1", 1_250_000),
      resultItem("投資組合 2", 1_310_000),
      resultItem("投資組合 3", 1_280_000),
    ],
    failures: [],
    assets: [],
    benchmark: resultItem("Benchmark · SPY", 1_290_000),
    warnings: ["multi-portfolio comparison recomputed from common window 2023-12-15 -> 2026-08-10 (common-runnable-portfolios-v1)"],
    timing: { market_ms: 1, compute_ms: 1, total_ms: 2 },
    reproducibility: {},
  };
}

async function mockPortfolioApi(page) {
  await page.route("**/api/v3/portfolio/health", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("**/api/v3/portfolio/preflight", (route) => route.fulfill({ json: preflightPayload() }));
  await page.route("**/api/v3/portfolio/backtests", (route) => route.fulfill({ json: backtestPayload() }));
  await page.route("**/api/v3/portfolio/assets/search**", (route) => route.fulfill({ json: [] }));
}

test("multi-portfolio results show one common period and all portfolios side by side", async ({ page }) => {
  await mockPortfolioApi(page);
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: "載入範例" }).click();
  await page.getByRole("button", { name: "資料預檢" }).click();
  await page.getByRole("button", { name: "執行回測" }).click();

  const comparison = page.getByRole("region", { name: "投資組合並排比較" });
  await expect(comparison).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "投資組合 1" })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "投資組合 2" })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: "投資組合 3" })).toBeVisible();
  await expect(page.getByText("共同比較期間：")).toBeVisible();
  await expect(comparison.getByText("2023-12-15 → 2026-08-10").first()).toBeVisible();
});

test("benchmark selection stays on the same common-window evidence", async ({ page }) => {
  await mockPortfolioApi(page);
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: "載入範例" }).click();
  await page.getByRole("button", { name: "資料預檢" }).click();
  await page.getByRole("button", { name: "執行回測" }).click();

  const selector = page.locator("label.compact-field select");
  await selector.selectOption({ label: "Benchmark · SPY · synthetic" });
  await expect(selector).toHaveValue("Benchmark · SPY");

  const comparison = page.getByRole("region", { name: "投資組合並排比較" });
  await expect(comparison.getByText("2023-12-15 → 2026-08-10").first()).toBeVisible();
  await expect(page.getByText("common-runnable-portfolios-v1", { exact: false })).toBeVisible();

  const tailRisk = page.locator("article.subcard").filter({ hasText: "尾端風險" });
  await expect(tailRisk.getByText("687", { exact: true })).toBeVisible();
});

test("390px comparison remains usable through horizontal table scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockPortfolioApi(page);
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: "載入範例" }).click();
  await page.getByRole("button", { name: "執行回測" }).click();

  const comparison = page.getByRole("region", { name: "投資組合並排比較" });
  await expect(comparison).toBeVisible();
  const overflowX = await comparison.evaluate((element) => getComputedStyle(element).overflowX);
  expect(["auto", "scroll"]).toContain(overflowX);
});
