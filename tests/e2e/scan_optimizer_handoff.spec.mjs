import { expect, test } from "@playwright/test";

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function scanRow(ticker, tradingDays) {
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
    data_coverage: 1,
    trading_days: tradingDays,
    data_start: "2025-01-02",
    data_end: "2025-12-31",
  };
}

test("manual scan choices become the exhaustive optimizer fixed source pool", async ({ page }) => {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.route("**/api/scan", (route) => fulfillJson(route, [
    scanRow("AAA", 252),
    scanRow("BBB", 230),
    scanRow("LOW", 224),
  ]));

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.locator("#scan-tickers").fill("AAA, BBB, LOW");
  await page.locator("#scan-start-period").fill("2025-01-01");
  await page.locator("#scan-end-period").fill("2025-12-31");
  await page.locator("#scan-benchmark").fill("QQQ");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  await expect(page.locator('input[data-optimizer-ticker="AAA"]')).toBeVisible();
  await expect(page.locator('input[data-optimizer-ticker="BBB"]')).toBeVisible();
  await expect(page.locator('input[data-optimizer-ticker="LOW"]')).toHaveCount(0);
  await page.locator('input[data-optimizer-ticker="AAA"]').check();
  await page.locator('input[data-optimizer-ticker="BBB"]').check();
  await expect(page.locator("#open-manual-optimizer")).toHaveAttribute("aria-disabled", "false");
  await expect(page.locator("#optimizer-manual-selection-status")).toContainText("手動候選 2 / 100");

  const handoff = await page.evaluate(() => JSON.parse(
    localStorage.getItem("backteststock-optimizer-manual-selection-v2"),
  ));
  expect(handoff).toMatchObject({
    version: 2,
    tickers: ["AAA", "BBB"],
    minimumTickers: 2,
    maximumTickers: 100,
    coverageThresholdPercent: 90,
    startDate: "2025-01-01",
    endDate: "2025-12-31",
    benchmark: "QQQ",
    valuationCurrency: "TWD",
  });

  await page.goto("/optimizer.html?mode=manual", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#optimizer-source")).toHaveValue("AAA, BBB");
  await expect(page.locator("#optimizer-start")).toHaveValue("2025-01-01");
  await expect(page.locator("#optimizer-end")).toHaveValue("2025-12-31");
  await expect(page.locator("#optimizer-benchmark")).toHaveValue("QQQ");
  await expect(page.locator("#optimizer-holding-count")).toHaveValue("2");
  await expect(page.locator("#optimizer-handoff-context")).toContainText("手動帶入 2 檔");
  await expect(page.locator("#optimizer-handoff-context")).toContainText("最低資料覆蓋率 ≥ 90%");
});

test("a restored legacy v3 scan keeps the exact manual selection when optimizer validates provenance", async ({ page }) => {
  await page.addInitScript(() => {
    const row = (ticker) => ({
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
      data_coverage: 1,
      trading_days: 252,
      data_start: "2025-01-02",
      data_end: "2025-12-31",
      twd_valuation_contract_version: "test-twd-v1",
    });
    localStorage.setItem("backteststock-scan-job-v3", JSON.stringify({
      version: 3,
      id: "legacy-restored-scan",
      status: "completed",
      payload: {
        tickers: ["AAA", "BBB"],
        benchmark: "QQQ",
        startYear: 2025,
        startMonth: 1,
        endYear: 2025,
        endMonth: 12,
      },
      pending: [],
      results: [row("AAA"), row("BBB")],
    }));
  });
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();

  await expect(page.locator('input[data-optimizer-ticker="AAA"]')).toBeVisible();
  await expect(page.locator('input[data-optimizer-ticker="BBB"]')).toBeVisible();
  await page.locator('input[data-optimizer-ticker="AAA"]').check();
  await page.locator('input[data-optimizer-ticker="BBB"]').check();

  const state = await page.evaluate(() => ({
    handoff: JSON.parse(localStorage.getItem("backteststock-optimizer-manual-selection-v2")),
    persistedScan: JSON.parse(localStorage.getItem("backteststock-scan-job-v3")),
  }));
  expect(state.handoff).toMatchObject({
    version: 2,
    sourceJobId: "legacy-restored-scan",
    tickers: ["AAA", "BBB"],
    coverageThresholdPercent: 90,
    startDate: "2025-01-01",
    endDate: "2025-12-31",
    benchmark: "QQQ",
    valuationCurrency: "TWD",
  });
  expect(state.persistedScan.payload.startDate).toBeUndefined();
  expect(state.persistedScan.payload.endDate).toBeUndefined();

  await page.goto("/optimizer.html?mode=manual", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#optimizer-source")).toHaveValue("AAA, BBB");
  await expect(page.locator("#optimizer-start")).toHaveValue("2025-01-01");
  await expect(page.locator("#optimizer-end")).toHaveValue("2025-12-31");
  await expect(page.locator("#optimizer-benchmark")).toHaveValue("QQQ");
  await expect(page.locator("#optimizer-holding-count")).toHaveValue("2");
  await expect(page.locator("#optimizer-handoff-context")).toContainText("手動帶入 2 檔");
});

test("a stale manual handoff fails closed instead of loading the whole scan list", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-scan-job-v3", JSON.stringify({
      version: 3,
      id: "current-scan",
      status: "completed",
      payload: {
        tickers: ["AAA", "BBB", "CCC"],
        benchmark: "SPY",
        startDate: "2025-01-01",
        endDate: "2025-12-31",
      },
      pending: [],
      results: [],
    }));
    localStorage.setItem("backteststock-optimizer-manual-selection-v2", JSON.stringify({
      version: 2,
      sourceJobId: "old-scan",
      tickers: ["AAA", "BBB"],
    }));
  });

  await page.goto("/optimizer.html?mode=manual", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#optimizer-source")).toHaveValue("");
  await expect(page.locator("#optimizer-handoff-context")).toContainText("來源股票未帶入");
});

test("a matching but invalid manual handoff cannot inject a ticker outside the scan", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-scan-job-v3", JSON.stringify({
      version: 3,
      id: "current-scan",
      status: "completed",
      payload: {
        tickers: ["AAA", "BBB", "CCC"],
        benchmark: "SPY",
        startDate: "2025-01-01",
        endDate: "2025-12-31",
      },
      pending: [],
      results: [
        { ticker: "AAA", status: "ok", retryable: false, trading_days: 252 },
        { ticker: "BBB", status: "ok", retryable: false, trading_days: 252 },
        { ticker: "CCC", status: "ok", retryable: false, trading_days: 252 },
      ],
    }));
    localStorage.setItem("backteststock-optimizer-manual-selection-v2", JSON.stringify({
      version: 2,
      sourceJobId: "current-scan",
      selectionMode: "manual_fixed_source_pool",
      benchmark: "SPY",
      startDate: "2025-01-01",
      endDate: "2025-12-31",
      coverageThresholdPercent: 90,
      valuationCurrency: "TWD",
      tickers: ["AAA", "OUTSIDE"],
    }));
  });

  await page.goto("/optimizer.html?mode=manual", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#optimizer-source")).toHaveValue("");
  await expect(page.locator("#optimizer-handoff-context")).toContainText("無法驗證");
});

test("a matching handoff cannot reintroduce a ticker below its saved coverage threshold", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-scan-job-v3", JSON.stringify({
      version: 3,
      id: "current-scan",
      status: "completed",
      payload: {
        tickers: ["AAA", "LOW"],
        benchmark: "SPY",
        startDate: "2025-01-01",
        endDate: "2025-12-31",
      },
      pending: [],
      results: [
        { ticker: "AAA", status: "ok", retryable: false, trading_days: 100 },
        { ticker: "LOW", status: "ok", retryable: false, trading_days: 89 },
      ],
    }));
    localStorage.setItem("backteststock-optimizer-manual-selection-v2", JSON.stringify({
      version: 2,
      sourceJobId: "current-scan",
      selectionMode: "manual_fixed_source_pool",
      benchmark: "SPY",
      startDate: "2025-01-01",
      endDate: "2025-12-31",
      coverageThresholdPercent: 90,
      valuationCurrency: "TWD",
      tickers: ["AAA", "LOW"],
    }));
  });

  await page.goto("/optimizer.html?mode=manual", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#optimizer-source")).toHaveValue("");
  await expect(page.locator("#optimizer-handoff-context")).toContainText("無法驗證");
});
