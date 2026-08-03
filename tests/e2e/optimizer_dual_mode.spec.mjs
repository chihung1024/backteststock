import { expect, test } from "@playwright/test";

test.setTimeout(90_000);

const tickers = ["T00", "T01", "T02", "T03", "T04"];

test("completed TWD scan source is carried directly into the exhaustive source pool", async ({ page }) => {
  await page.addInitScript(({ savedTickers }) => {
    localStorage.setItem("backteststock-scan-job-v3", JSON.stringify({
      version: 3,
      id: "scan-source-job",
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

  await page.goto("/optimizer.html", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "固定來源池全量精確回測" })).toBeVisible();
  const source = page.locator("#optimizer-source");
  await expect(source).toHaveValue(/T00/);
  await expect(source).toHaveValue(/T04/);
  await expect(source).not.toHaveAttribute("readonly", "");
  await page.locator("#optimizer-holding-count").fill("5");
  await expect(page.locator("#optimizer-combination-count")).toHaveText("1");
  await expect(page.locator("#optimizer-ranking-field")).toHaveCount(0);
  await expect(page.locator("#optimizer-training-ratio")).toHaveCount(0);
  await expect(page.locator("body")).toContainText("不切訓練期與樣本外期");
});

test("desktop exhaustive layout uses the wider maximum width", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto("/optimizer.html", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".site-header")).toHaveCSS("max-width", "1480px");
});
