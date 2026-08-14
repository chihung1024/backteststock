import { expect, test } from "@playwright/test";

async function fulfillJson(route, body, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

const universes = [
  {
    id: "nasdaq100",
    name: "NASDAQ-100（自動備援）",
    source: { label: "Nasdaq Global Index Watch", url: "https://example.com/ndx", isProxy: false },
    available: true,
    version: "2026-08-14-ndx",
    sourceAsOf: "2026-08-14",
    memberCount: 101,
    warnings: [],
  },
];

function scanResult(ticker) {
  return {
    ticker,
    status: "ok",
    retryable: false,
    total_return: 0.1,
    cagr: 0.09,
    volatility: 0.2,
    mdd: -0.1,
    sharpe_ratio: 0.8,
    sortino_ratio: 1.1,
    beta: 1,
    alpha: 0.02,
    data_coverage: 1,
    trading_days: 252,
    data_start: "2025-01-02",
    data_end: "2025-12-31",
  };
}

test("exposes PIT membership mode without applying current fundamentals", async ({ page }) => {
  let screenerPayload;

  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, ["AAPL", "MSFT", "NVDA"]));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: universes }));
  await page.route("**/api/v2/screener", async (route) => {
    screenerPayload = route.request().postDataJSON();
    await fulfillJson(route, {
      universe: {
        id: "nasdaq100",
        name: "NASDAQ-100（自動備援）",
        version: "2026-08-14-ndx",
        sourceAsOf: "2026-08-14",
        fetchedAt: "2026-08-14T06:20:00Z",
        evidenceAvailableAsOf: "2026-08-14",
        requestedAsOf: "2026-08-14",
      },
      fundamentalsAsOf: null,
      fundamentalsSources: [],
      funnel: {
        universeCount: 3,
        fundamentalsAvailable: null,
        sectorMatches: null,
        passedFilters: 3,
        selectedForScan: 3,
      },
      candidates: [
        { ticker: "AAPL" },
        { ticker: "MSFT" },
        { ticker: "NVDA" },
      ],
      truncated: false,
      sort: "ticker-asc",
      limit: null,
      warnings: [
        "歷史 PIT 模式只使用所選日期當時已取得的成分股快照；沒有套用目前 fundamentals。",
      ],
      researchValidity: {
        selectionMode: "point_in_time_membership_only",
        requestedAsOf: "2026-08-14",
        membershipObservationAsOf: "2026-08-14",
        membershipEvidenceAvailableAsOf: "2026-08-14",
        membershipPointInTime: true,
        membershipCausal: true,
        membershipAuthoritative: true,
        membershipSourceType: "authoritative",
        fundamentalsPointInTime: false,
        fundamentalsApplied: false,
        historicalSelectionSafe: true,
      },
    });
  });
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    await fulfillJson(route, payload.tickers.map(scanResult));
  });

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();

  await expect(page.locator("#screener-selection-mode")).toHaveValue("current");
  await expect(page.locator("#screener-selection-as-of")).toBeDisabled();
  await page.locator("#screener-selection-mode").selectOption("pit");

  await expect(page.locator("#screener-selection-as-of")).toBeEnabled();
  await expect(page.locator("#screener-sector")).toBeDisabled();
  await expect(page.locator("#screener-market-cap")).toBeDisabled();
  await expect(page.locator("#screener-pe")).toBeDisabled();
  await expect(page.locator("#screener-sort")).toBeDisabled();
  await expect(page.locator("#screener-limit")).toBeEnabled();
  await expect(page.locator("#screener-mode-note")).toContainText("目前基本面不會套用");

  await page.locator("#screener-selection-as-of").fill("2026-08-14");
  await page.getByRole("button", { name: "建立 PIT 成分股回測清單" }).click();

  expect(screenerPayload).toEqual({
    universe: "nasdaq100",
    selectionAsOf: "2026-08-14",
    sector: "any",
    filters: {},
    limit: null,
    sort: "ticker-asc",
  });
  await expect(page.locator("#scan-tickers")).toHaveValue("AAPL, MSFT, NVDA");
  await expect(page.locator("#screener-funnel")).toContainText("歷史基本面");
  await expect(page.locator("#screener-funnel")).toContainText("未套用");
  await expect(page.locator("#screener-warning")).toContainText("沒有套用目前 fundamentals");

  await page.locator("#scan-start-period").fill("2025-01-01");
  await page.locator("#scan-end-period").fill("2025-12-31");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  await expect(page.locator("#scan-results")).toBeVisible();
  await expect(page.locator("#scan-summary")).toContainText("3 / 3");
  await expect(page.locator("#scan-context")).toContainText("模式：PIT 歷史成分股");
  await expect(page.locator("#scan-context")).toContainText("選股基準日：2026-08-14");
  await expect(page.locator("#scan-context")).toContainText("基本面：未套用");
  await expect(page.locator("#scan-context")).toContainText("membership 因果性：已驗證");

  await page.locator("#screener-selection-mode").selectOption("current");
  await expect(page.locator("#screener-selection-as-of")).toBeDisabled();
  await expect(page.locator("#screener-sector")).toBeEnabled();
  await expect(page.locator("#screener-market-cap")).toBeEnabled();
  await expect(page.locator("#screener-pe")).toBeEnabled();
  await expect(page.locator("#screener-sort")).toBeEnabled();
});

test("shows fail-closed PIT evidence errors without falling back to current selection", async ({ page }) => {
  let requestCount = 0;
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: universes }));
  await page.route("**/api/v2/screener", async (route) => {
    requestCount += 1;
    await fulfillJson(route, {
      error: "所選日期之前沒有可驗證且當時已取得的歷史 Universe 快照；已停止使用目前成分股替代。",
    }, 409);
  });

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.locator("#screener-selection-mode").selectOption("pit");
  await page.locator("#screener-selection-as-of").fill("2026-08-01");
  await page.getByRole("button", { name: "建立 PIT 成分股回測清單" }).click();

  await expect(page.locator("#scan-error")).toContainText("已停止使用目前成分股替代");
  expect(requestCount).toBe(1);
  await expect(page.locator("#scan-tickers")).toHaveValue("AAPL, MSFT, NVDA, AMZN, GOOGL");
});
