import { expect, test } from "@playwright/test";

const tickers = Array.from({ length: 31 }, (_, index) => `T${String(index).padStart(2, "0")}`);

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test("scan results allow a persistent manual 20-to-30-stock shortlist", async ({ page }) => {
  await page.addInitScript(({ savedTickers }) => {
    localStorage.setItem("backteststock-scan-job-v2", JSON.stringify({
      version: 2,
      id: "manual-source-job",
      status: "completed",
      createdAt: "2026-08-01T00:00:00.000Z",
      updatedAt: "2026-08-01T00:00:00.000Z",
      payload: {
        tickers: savedTickers,
        benchmark: "SPY",
        startDate: "2016-08-01",
        endDate: "2026-07-31",
        startYear: 2016,
        startMonth: 8,
        endYear: 2026,
        endMonth: 7,
      },
      pending: [],
      attempts: {},
      retryRound: 0,
      results: savedTickers.map((ticker, index) => ({
        ticker,
        status: "ok",
        retryable: false,
        total_return: 1 + index * 0.01,
        cagr: 0.20 + index * 0.001,
        volatility: 0.20,
        mdd: -0.25,
        sharpe_ratio: 1.1,
        sortino_ratio: 1.4 + index * 0.01,
        beta: 0.8 + index * 0.01,
        alpha: 0.03,
        data_coverage: 1,
        trading_days: 2500,
        data_start: "2016-08-01",
        data_end: "2026-07-31",
        corporate_action_status: "verified_standard_actions",
        metric_definition_version: "2026-08-01.2",
      })),
    }));
  }, { savedTickers: tickers });

  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "個股掃描" }).click();

  await expect(page.locator("#scan-table th[data-composite-metric='sortino_growth_beta_squared_mdd_score']"))
    .toContainText("優化分數");
  const checkboxes = page.locator("#scan-table input[data-optimizer-ticker]");
  await expect(checkboxes).toHaveCount(31);

  for (let index = 0; index < 20; index += 1) {
    await checkboxes.nth(index).check();
  }
  await expect(page.locator("#optimizer-manual-selection-status"))
    .toContainText("20 / 30");
  await expect(page.locator("#open-manual-optimizer")).not.toHaveClass(/disabled/);
  await expect(page.locator("#open-manual-optimizer")).toContainText("使用已選 20 檔");

  for (let index = 20; index < 30; index += 1) {
    await checkboxes.nth(index).check();
  }
  await expect(page.locator("#optimizer-manual-selection-status"))
    .toContainText("30 / 30");
  await expect(checkboxes.nth(30)).toBeDisabled();
  await expect(page.locator("#open-manual-optimizer")).toContainText("使用已選 30 檔");

  const saved = await page.evaluate(() => JSON.parse(
    localStorage.getItem("backteststock-optimizer-manual-selection-v1"),
  ));
  expect(saved.tickers).toHaveLength(30);
  expect(saved.sourceJobId).toBe("manual-source-job");
  expect(saved.minimumTickers).toBe(20);
  expect(saved.maximumTickers).toBe(30);
  expect(saved.finalCandidateCount).toBe(20);

  await page.goto("/optimizer.html?mode=manual", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#optimizer-candidate-mode")).toHaveValue("manual");
  await expect(page.locator("#optimizer-source-tickers")).toHaveAttribute("readonly", "");
  await expect(page.locator("#optimizer-ranking-field")).toBeEnabled();
  await expect(page.locator("#optimizer-source-status")).toContainText("手動候選短名單 30 檔");
  await expect(page.locator("#optimizer-source-status")).toContainText("取前 20 檔");
  await expect(page.locator("#optimizer-candidate-mode-note"))
    .toContainText("可能已參考原定樣本外期間");
  await expect(page.locator("#optimizer-candidate-mode-note"))
    .toContainText("訓練期資料取前 20 檔");
  await expect(page.locator("#optimizer-ranking-field option")).toContainText([
    "Sortino",
    "CAGR",
    "最低 |MDD|",
    "最低 |Beta|",
    "Alpha",
    "穩健分數",
    "成長分數",
    "回撤控制分數",
    "優化分數",
  ]);
});

test("manual selection excludes rows with materially short endpoint coverage", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-scan-job-v2", JSON.stringify({
      version: 2,
      id: "coverage-source-job",
      status: "completed",
      payload: {
        tickers: ["GOOD", "LATE"],
        benchmark: "SPY",
        startDate: "2016-08-01",
        endDate: "2026-07-31",
      },
      pending: [],
      attempts: {},
      retryRound: 0,
      results: [
        {
          ticker: "GOOD",
          status: "ok",
          retryable: false,
          data_coverage: 1,
          data_start: "2016-08-01",
          data_end: "2026-07-31",
          corporate_action_status: "verified_standard_actions",
        },
        {
          ticker: "LATE",
          status: "ok",
          retryable: false,
          data_coverage: 0.99,
          data_start: "2016-09-01",
          data_end: "2026-07-31",
          corporate_action_status: "verified_standard_actions",
        },
      ],
    }));
  });

  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "個股掃描" }).click();

  const late = page.locator("input[data-optimizer-ticker='LATE']");
  await expect(late).toBeDisabled();
  await expect(late).toHaveAttribute("title", /期初行情晚於回測起日/);
});

test("desktop layout uses the wider maximum width", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".site-header")).toHaveCSS("max-width", "1480px");
});
