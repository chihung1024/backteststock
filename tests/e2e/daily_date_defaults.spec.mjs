import { expect, test } from "@playwright/test";

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function formatLocalDate(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

test("daily controls default to previous-year same date through yesterday", async ({ page }) => {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.goto("/");

  const today = new Date();
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
  const previousYear = today.getFullYear() - 1;
  const maxDay = new Date(previousYear, today.getMonth() + 1, 0).getDate();
  const start = new Date(
    previousYear,
    today.getMonth(),
    Math.min(today.getDate(), maxDay),
  );

  await expect(page.locator("#start-period")).toHaveAttribute("type", "date");
  await expect(page.locator("#end-period")).toHaveAttribute("type", "date");
  await expect(page.locator("#start-period")).toHaveValue(formatLocalDate(start));
  await expect(page.locator("#end-period")).toHaveValue(formatLocalDate(end));
  await expect(page.locator("#scan-start-period")).toHaveValue(formatLocalDate(start));
  await expect(page.locator("#scan-end-period")).toHaveValue(formatLocalDate(end));
});
