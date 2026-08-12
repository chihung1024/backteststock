import { expect, test } from "@playwright/test";

test("ordinary optimizer route keeps the full scan source and ignores manual handoff mode", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-scan-job-v3", JSON.stringify({
      version: 3,
      id: "current-scan",
      status: "completed",
      payload: {
        tickers: ["AAA", "BBB", "CCC"],
        benchmark: "QQQ",
        startDate: "2025-01-01",
        endDate: "2025-12-31",
      },
      pending: [],
      results: [],
    }));
    localStorage.setItem("backteststock-optimizer-manual-selection-v2", JSON.stringify({
      version: 2,
      sourceJobId: "current-scan",
      selectionMode: "manual_fixed_source_pool",
      benchmark: "QQQ",
      startDate: "2025-01-01",
      endDate: "2025-12-31",
      coverageThresholdPercent: 90,
      valuationCurrency: "TWD",
      tickers: ["AAA", "BBB"],
    }));
  });

  await page.goto("/optimizer.html", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#optimizer-source")).toHaveValue("AAA, BBB, CCC");
  await expect(page.locator("#optimizer-benchmark")).toHaveValue("QQQ");
  await expect(page.locator("#optimizer-handoff-context")).toBeHidden();
});
