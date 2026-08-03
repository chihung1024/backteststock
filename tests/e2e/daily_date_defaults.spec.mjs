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

function rollingRange(now) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(today);
  end.setDate(end.getDate() - 1);
  const startYear = today.getFullYear() - 10;
  const maxDay = new Date(startYear, today.getMonth() + 1, 0).getDate();
  const start = new Date(
    startYear,
    today.getMonth(),
    Math.min(today.getDate(), maxDay),
  );
  return { startDate: formatLocalDate(start), endDate: formatLocalDate(end) };
}

async function routeStaticApis(page) {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
}

test("daily controls default to ten-years-ago same date through yesterday", async ({ page }) => {
  await routeStaticApis(page);
  await page.goto("/");

  const current = rollingRange(new Date());
  await expect(page.locator("#start-period")).toHaveAttribute("type", "date");
  await expect(page.locator("#end-period")).toHaveAttribute("type", "date");
  await expect(page.locator("#start-period")).toHaveValue(current.startDate);
  await expect(page.locator("#end-period")).toHaveValue(current.endDate);
  await expect(page.locator("#scan-start-period")).toHaveValue(current.startDate);
  await expect(page.locator("#scan-end-period")).toHaveValue(current.endDate);
});

test("a saved rolling default advances to the current day after refresh", async ({ page }) => {
  const now = new Date();
  const priorDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
  const prior = rollingRange(priorDay);
  const current = rollingRange(now);

  await page.addInitScript(({ priorRange }) => {
    localStorage.setItem("backteststock-state-v2", JSON.stringify({
      settings: {
        initialAmount: 10000,
        startPeriod: priorRange.startDate,
        endPeriod: priorRange.endDate,
        rebalancingPeriod: "annually",
        benchmark: "SPY",
      },
      portfolios: [{
        id: "portfolio-1",
        name: "測試投組",
        assets: [{ id: "asset-1", ticker: "SPY", weight: 100 }],
      }],
    }));
  }, { priorRange: prior });

  await routeStaticApis(page);
  await page.goto("/");
  await expect(page.locator("#start-period")).toHaveValue(current.startDate);
  await expect(page.locator("#end-period")).toHaveValue(current.endDate);
  await expect.poll(() => page.evaluate(() => {
    const state = JSON.parse(localStorage.getItem("backteststock-state-v2"));
    return [state.settings.startPeriod, state.settings.endPeriod];
  })).toEqual([current.startDate, current.endDate]);
});

test("an explicitly customized date range remains unchanged", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-state-v2", JSON.stringify({
      settings: {
        initialAmount: 10000,
        startPeriod: "2018-01-15",
        endPeriod: "2024-12-20",
        rebalancingPeriod: "annually",
        benchmark: "SPY",
      },
      portfolios: [{
        id: "portfolio-1",
        name: "測試投組",
        assets: [{ id: "asset-1", ticker: "SPY", weight: 100 }],
      }],
    }));
    localStorage.setItem("backteststock-backtest-date-mode-v1", "custom");
  });

  await routeStaticApis(page);
  await page.goto("/");
  await expect(page.locator("#start-period")).toHaveValue("2018-01-15");
  await expect(page.locator("#end-period")).toHaveValue("2024-12-20");
});
