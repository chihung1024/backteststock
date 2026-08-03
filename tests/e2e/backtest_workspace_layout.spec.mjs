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
}

test("backtest opens as an original-inspired research workspace", async ({ page }) => {
  await mockShellApis(page);
  await page.goto("/");

  await page.getByRole("button", { name: "投資組合回測" }).click();

  const dialog = page.locator("#integrated-backtest-dialog");
  await expect(dialog).toHaveJSProperty("open", true);
  await expect(dialog).toHaveClass(/backtest-workspace-dialog/);
  await expect(dialog.locator(".backtest-workspace-appbar")).toBeVisible();
  await expect(dialog.locator(".backtest-workspace-hero")).toContainText("投資組合回測與風險比較");
  await expect(dialog.locator(".backtest-workspace-fact")).toHaveCount(3);
  await expect(dialog.locator(".backtest-settings-heading")).toContainText("01");
  await expect(dialog.locator(".backtest-settings-heading")).toContainText("回測基本設定");
  await expect(dialog.locator(".backtest-assets-heading")).toContainText("02");
  await expect(dialog.locator(".backtest-assets-heading")).toContainText("投資組合與資產配置");
  await expect(dialog.locator("#portfolio-list .portfolio-card")).toHaveCount(2);
  await expect(dialog.locator("#add-portfolio")).toHaveText("＋ 新增投資組合");
  await expect(dialog.locator(".backtest-run-bar #run-backtest")).toBeVisible();
  await expect(page.locator("body")).toHaveClass(/backtest-workspace-open/);

  await dialog.getByRole("button", { name: "關閉投資組合回測並返回績效列表" }).click();
  await expect(dialog).toHaveJSProperty("open", false);
  await expect(page.locator("body")).not.toHaveClass(/backtest-workspace-open/);
});

test("backtest workspace remains usable at mobile width", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockShellApis(page);
  await page.goto("/");
  await page.getByRole("button", { name: "投資組合回測" }).click();

  const dialog = page.locator("#integrated-backtest-dialog");
  await expect(dialog).toHaveJSProperty("open", true);
  const dialogBox = await dialog.boundingBox();
  expect(dialogBox).not.toBeNull();
  expect(dialogBox.width).toBeLessThanOrEqual(390);
  await expect(dialog.locator("#initial-amount")).toBeVisible();
  await expect(dialog.locator("#portfolio-list .portfolio-card").first()).toBeVisible();
  const runButton = dialog.locator("#run-backtest");
  await expect(runButton).toBeVisible();
  const buttonBox = await runButton.boundingBox();
  expect(buttonBox).not.toBeNull();
  expect(buttonBox.width).toBeGreaterThan(300);
  expect(buttonBox.width).toBeLessThanOrEqual(dialogBox.width);
});
