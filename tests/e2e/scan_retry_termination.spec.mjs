import { expect, test } from "@playwright/test";

const STORAGE_KEY = "backteststock-scan-job-v2";
const METRIC_VERSION = "2026-08-01.2";

async function fulfillJson(route, body, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test("repeated scan 503 responses terminate with explicit failures", async ({ page }) => {
  let scanRequests = 0;
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.route("**/api/scan", async (route) => {
    scanRequests += 1;
    await fulfillJson(route, { error: "temporary upstream outage", retryable: true }, 503);
  });

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.locator("#scan-tickers").fill("AAA");
  await page.locator("#scan-start-period").fill("2025-01-01");
  await page.locator("#scan-end-period").fill("2025-03-31");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  await expect(page.locator("#loading-overlay")).toHaveClass(/hidden/, { timeout: 30_000 });
  await expect(page.locator("#scan-summary")).toContainText("0 / 1");
  await expect(page.locator("#scan-summary")).toContainText("失敗標的");
  await expect(page.locator("#scan-table")).toContainText("已停止重試");

  const job = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), STORAGE_KEY);
  expect(scanRequests).toBe(4);
  expect(job.status).toBe("completed");
  expect(job.pending).toEqual([]);
  expect(job.results).toHaveLength(1);
  expect(job.results[0]).toMatchObject({
    ticker: "AAA",
    status: "failed",
    retryable: false,
    metric_definition_version: METRIC_VERSION,
  });
});
