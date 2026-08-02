import { expect, test } from "@playwright/test";

test.setTimeout(90_000);

const eligibleTickers = Array.from(
  { length: 31 },
  (_, index) => `T${String(index).padStart(2, "0")}`,
);
const tickers = [...eligibleTickers, "LATE"];

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test("scan shortlist is carried into the fixed exhaustive source pool", async ({ page }) => {
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
        data_coverage: ticker === "LATE" ? 0.99 : 1,
        trading_days: 2500,
        data_start: ticker === "LATE" ? "2016-09-01" : "2016-08-01",
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

  for (const ticker of eligibleTickers.slice(0, 30)) {
    await page.locator(`input[data-optimizer-ticker='${ticker}']`).check();
  }
  await expect(page.locator("#optimizer-manual-selection-status")).toContainText("30 / 30");
  await expect(page.locator("input[data-optimizer-ticker='T30']")).toBeDisabled();
  await expect(page.locator("input[data-optimizer-ticker='LATE']")).toBeDisabled();

  const saved = await page.evaluate(() => JSON.parse(
    localStorage.getItem("backteststock-optimizer-manual-selection-v1"),
  ));
  expect(saved.tickers).toHaveLength(30);
  expect(saved.sourceJobId).toBe("manual-source-job");

  await page.goto("/optimizer.html?mode=manual", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "固定來源池全量精確回測" })).toBeVisible();
  const source = page.locator("#optimizer-source");
  await expect(source).toHaveValue(/T00/);
  await expect(source).toHaveValue(/T29/);
  await expect(source).not.toHaveAttribute("readonly", "");
  await expect(page.locator("#optimizer-combination-count")).toHaveText("30,045,015");
  await expect(page.locator("#optimizer-ranking-field")).toHaveCount(0);
  await expect(page.locator("body")).toContainText("不自動換股或預先排名");
});

test("desktop exhaustive layout uses the wider maximum width", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto("/optimizer.html", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".site-header")).toHaveCSS("max-width", "1480px");
});
