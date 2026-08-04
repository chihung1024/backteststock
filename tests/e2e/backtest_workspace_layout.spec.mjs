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
  await page.route("**/api/v3/portfolio/health", (route) => fulfillJson(route, {
    status: "ok",
    service: "backteststock-portfolio-v3",
  }));
  await page.route("**/api/v3/portfolio/assets/search**", (route) => fulfillJson(route, [
    { symbol: "VT", name: "Vanguard Total World Stock ETF", currency: "USD" },
  ]));
}

test("main Portfolio entry uses normal full-page navigation instead of a dialog", async ({ page }) => {
  await mockShellApis(page);
  await page.goto("/");

  const entry = page.getByRole("link", { name: "投資組合回測" });
  await expect(entry).toHaveAttribute("href", "/portfolio/");
  await expect(page.locator("#scanner-panel")).toBeVisible();
  await expect(page.locator("#integrated-backtest-dialog")).toHaveCount(0);

  await entry.click();
  await expect(page).toHaveURL(/\/portfolio\/(?:\?handoff=[^#]+)?$/u);
  await expect(page.getByRole("heading", { name: "投資組合研究工作區" })).toBeVisible();
  await expect(page.locator("main#portfolio-main")).toBeVisible();
  await expect(page.locator("dialog")).toHaveCount(0);
  await expect(page.locator("iframe")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "返回個股研究" })).toBeVisible();
});

test("full-page Portfolio entry remains usable at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockShellApis(page);
  await page.goto("/");
  await page.getByRole("link", { name: "投資組合回測" }).click();

  await expect(page.getByRole("heading", { name: "投資組合研究工作區" })).toBeVisible();
  await expect(page.locator(".mobile-allocation")).toBeVisible();
  await expect(page.locator(".desktop-matrix")).toBeHidden();
  await expect(page.locator(".run-bar")).toBeVisible();
  const runButton = page.getByRole("button", { name: "執行回測" });
  await expect(runButton).toBeVisible();
  const box = await runButton.boundingBox();
  expect(box).not.toBeNull();
  expect(box.width).toBeGreaterThan(150);
  expect(box.width).toBeLessThanOrEqual(390);
});
