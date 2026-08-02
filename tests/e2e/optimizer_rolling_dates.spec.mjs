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

test("exhaustive optimizer always advances automatic dates to today-minus-one", async ({ page }) => {
  const current = localRange();
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-exhaustive-date-mode-v1", "automatic");
  });
  await page.goto("/optimizer.html", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#optimizer-start")).toHaveValue(current.startDate);
  await expect(page.locator("#optimizer-end")).toHaveValue(current.endDate);
  await expect(page.locator("#optimizer-reset-dates")).toBeVisible();
});

test("exhaustive optimizer preserves an explicitly custom range", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-exhaustive-date-mode-v1", "custom");
    localStorage.setItem(
      "backteststock-exhaustive-custom-range-v1",
      JSON.stringify({ startDate: "2018-01-15", endDate: "2025-12-20" }),
    );
  });
  await page.goto("/optimizer.html", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#optimizer-start")).toHaveValue("2018-01-15");
  await expect(page.locator("#optimizer-end")).toHaveValue("2025-12-20");

  await page.locator("#optimizer-reset-dates").click();
  const current = localRange();
  await expect(page.locator("#optimizer-start")).toHaveValue(current.startDate);
  await expect(page.locator("#optimizer-end")).toHaveValue(current.endDate);
});

test("optimizer exposes full-period exhaustive contract instead of training split", async ({ page }) => {
  await page.goto("/optimizer.html", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "固定來源池全量精確回測" })).toBeVisible();
  await expect(page.locator("body")).toContainText("完整枚舉 C(N,K)");
  await expect(page.locator("#optimizer-holding-count")).toHaveValue("10");
  await expect(page.locator("#optimizer-rebalance-mode")).toHaveValue("band");
  await expect(page.locator("#optimizer-worker-count")).toBeVisible();
  await expect(page.locator("#optimizer-preflight-button")).toContainText("預檢、測速並估算");
  await expect(page.locator("#optimizer-training-ratio")).toHaveCount(0);
  await expect(page.locator("#optimizer-search-budget")).toHaveCount(0);
});
