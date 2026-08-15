import { expect, test } from "@playwright/test";

async function mockExposureApi(page) {
  let capturedRequest = null;

  await page.route("**/api/v3/portfolio/health", (route) =>
    route.fulfill({ json: { status: "ok", service: "backteststock-portfolio-v3" } }),
  );
  await page.route("**/api/v3/portfolio/assets/search**", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route("**/api/v3/portfolio/preflight", async (route) => {
    capturedRequest = route.request().postDataJSON();
    const portfolio = capturedRequest.portfolios[0];
    const symbol = portfolio.assets[0].symbol;
    await route.fulfill({
      json: {
        request_id: "exposure-preflight",
        generated_at: "2026-08-16T00:00:00Z",
        contract_version: "portfolio-v3",
        schema_version: "portfolio-v3-2026-08-15.1",
        base_currency: "TWD",
        requested_start: capturedRequest.start_date,
        requested_end: capturedRequest.end_date,
        effective_end: capturedRequest.end_date,
        assets: [
          {
            symbol,
            status: "ready",
            retryable: false,
            quote_currency: "USD",
            effective_start: capturedRequest.start_date,
            effective_end: capturedRequest.end_date,
            observations: 500,
            fingerprints: { adjusted_close_twd: "exposure-regression" },
          },
        ],
        portfolios: [
          {
            name: portfolio.name,
            status: "ready",
            symbols: [symbol],
            missing_symbols: [],
            effective_start: capturedRequest.start_date,
            effective_end: capturedRequest.end_date,
            observations: 500,
          },
        ],
        benchmark: null,
        analysis_dependencies: [],
        warnings: [],
      },
    });
  });

  return () => capturedRequest;
}

function desktopFirstTicker(page) {
  return page.locator(".allocation-matrix tbody tr").first().locator(".ticker-cell input");
}

function desktopFirstWeight(page) {
  return page.locator(".allocation-matrix tbody tr").first().locator("td").first().locator('input[type="number"]');
}

test("weight totals directly control cash and gross exposure without a 100 percent UI cap", async ({ page }) => {
  const requestSnapshot = await mockExposureApi(page);
  await page.goto("/portfolio/");

  await desktopFirstTicker(page).fill("VT");
  const weight = desktopFirstWeight(page);

  await weight.fill("50");
  await expect(page.getByText("50.0% · 現金 50.0%").first()).toBeVisible();
  await expect(page.getByText("每日重設總曝險；內部比例依再平衡設定").first()).toBeVisible();

  await weight.fill("150");
  await expect(page.getByText("150.0% · 1.50× · 融資 50.0%").first()).toBeVisible();

  await weight.fill("300");
  await expect(weight).toHaveValue("300");
  await expect(page.getByText("300.0% · 3.00× · 融資 200.0%").first()).toBeVisible();

  await weight.fill("150");
  const interest = page.getByLabel("借款年利率");
  const margin = page.getByLabel("維持保證金率");
  await expect(interest).toBeVisible();
  await expect(margin).toBeVisible();
  await interest.fill("5");

  const legacyDetails = page.locator("details").filter({ hasText: "舊版槓桿相容（僅 100% 權重投組）" });
  expect(await legacyDetails.evaluate((element) => element.open)).toBe(false);

  await page.getByRole("button", { name: "資料預檢" }).click();
  await expect(page.getByRole("heading", { name: "資料預檢" })).toBeVisible();

  const request = requestSnapshot();
  expect(request.portfolios[0].assets).toEqual([{ symbol: "VT", weight: 150 }]);
  expect(request.leverage.type).toBe("none");
  expect(request.leverage.annual_interest_rate_percent).toBe(5);
  expect(request.leverage.maintenance_margin_percent).toBe(25);

  await page.getByRole("button", { name: "縮放至 100%" }).first().click();
  await expect(page.getByText("100.0% · 全額投資").first()).toBeVisible();
  await expect(weight).toHaveValue("100");
});

test("legacy leverage is demoted but remains available for imported 100 percent models", async ({ page }) => {
  await mockExposureApi(page);
  await page.goto("/portfolio/");

  await expect(page.getByLabel("借款年利率")).toBeVisible();
  await expect(page.getByLabel("維持保證金率")).toBeVisible();

  const details = page.locator("details").filter({ hasText: "舊版槓桿相容（僅 100% 權重投組）" });
  expect(await details.evaluate((element) => element.open)).toBe(false);
  await details.locator("summary").click();
  await expect(page.getByLabel("舊版槓桿模式")).toBeVisible();
  await expect(page.getByText("新投組請直接用每組權重總和定義現金或槓桿曝險。" )).toBeVisible();
});

test("390px mobile editor keeps the same weight-defined exposure semantics", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockExposureApi(page);
  await page.goto("/portfolio/");

  await page.locator(".mobile-asset-row .ticker-cell input").first().fill("VT");
  const mobileWeight = page.locator(".mobile-asset-row .weight-input input").first();
  await mobileWeight.fill("150");

  const mobileCard = page.locator(".mobile-portfolio-card");
  await expect(mobileWeight).toHaveValue("150");
  await expect(mobileCard.getByText("150.0% · 1.50× · 融資 50.0%", { exact: true })).toBeVisible();
  await expect(mobileCard.getByText("每日重設總曝險；內部比例依再平衡設定", { exact: true })).toBeVisible();
});
