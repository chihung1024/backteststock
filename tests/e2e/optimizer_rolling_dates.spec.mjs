import { expect, test } from "@playwright/test";

function localRange(now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(today);
  end.setDate(end.getDate() - 1);
  const year = today.getFullYear() - 10;
  const maxDay = new Date(year, today.getMonth() + 1, 0).getDate();
  const start = new Date(year, today.getMonth(), Math.min(today.getDate(), maxDay));
  const format = (date) => [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
  return { startDate: format(start), endDate: format(end) };
}

test("optimizer advances a prior rolling default after refresh", async ({ page }) => {
  const current = localRange();
  const previousNow = new Date();
  previousNow.setDate(previousNow.getDate() - 1);
  const previous = localRange(previousNow);
  await page.addInitScript(({ prior }) => {
    localStorage.setItem("backteststock-scan-job-v2", JSON.stringify({
      version: 2,
      id: "prior-day-job",
      payload: {
        tickers: Array.from({ length: 20 }, (_, index) => `T${index}`),
        benchmark: "SPY",
        startDate: prior.startDate,
        endDate: prior.endDate,
      },
      results: [],
      pending: [],
      attempts: {},
      retryRound: 0,
    }));
  }, { prior: previous });

  await page.goto("/optimizer.html", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#optimizer-start-date")).toHaveValue(current.startDate);
  await expect(page.locator("#optimizer-end-date")).toHaveValue(current.endDate);
  await expect(page.locator("#optimizer-reset-rolling-dates")).toBeVisible();
});

test("optimizer preserves an explicitly custom range", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-optimizer-date-mode-v1", "custom");
    localStorage.setItem(
      "backteststock-optimizer-custom-range-v1",
      JSON.stringify({ startDate: "2018-01-15", endDate: "2025-12-20" }),
    );
  });

  await page.goto("/optimizer.html", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#optimizer-start-date")).toHaveValue("2018-01-15");
  await expect(page.locator("#optimizer-end-date")).toHaveValue("2025-12-20");
});

test("optimizer exposes balanced search and sortable verification contract", async ({ page }) => {
  await page.goto("/optimizer.html", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".optimizer-balanced-search-control input"))
    .toHaveValue("五目標平衡搜尋（無單一主要目標）");
  await expect(page.locator('label:has-text("精確複驗") input'))
    .toHaveValue("300 組（5×48 + 60）");
  await expect(page.locator("#optimizer-primary-objective")).toBeHidden();
  await expect(page.locator("#optimizer-search-budget")).toHaveAttribute("min", "6000");
});
