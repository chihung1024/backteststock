import { expect, test } from "@playwright/test";

const universes = [
  {
    id: "sp500",
    name: "S&P 500（IVV holdings）",
    source: { label: "iShares IVV holdings", url: "https://example.com/ivv", isProxy: true },
    available: true,
    version: "2026-07-27-sp500",
    sourceAsOf: "2026-07-27",
    memberCount: 504,
    warnings: [],
  },
  {
    id: "nasdaq100",
    name: "NASDAQ-100（自動備援）",
    source: { label: "Nasdaq Global Index Watch", url: "https://example.com/ndx", isProxy: false },
    available: true,
    version: "2026-07-29-nasdaq100",
    sourceAsOf: "2026-07-29",
    memberCount: 103,
    warnings: [],
  },
  {
    id: "soxx",
    name: "SOXX holdings",
    source: { label: "iShares SOXX holdings", url: "https://example.com/soxx", isProxy: false },
    available: true,
    version: "2026-07-27-soxx",
    sourceAsOf: "2026-07-27",
    memberCount: 30,
    warnings: [],
  },
  {
    id: "russell2000",
    name: "Russell 2000（IWM holdings 代理）",
    source: { label: "iShares IWM holdings", url: "https://example.com/iwm", isProxy: true },
    available: true,
    version: "2026-07-27-russell2000",
    sourceAsOf: "2026-07-27",
    memberCount: 1964,
    warnings: [],
  },
];

const scanResults = [
  {
    ticker: "NVDA",
    status: "ok",
    retryable: false,
    total_return: 0.25,
    cagr: 0.25,
    volatility: 0.42,
    mdd: -0.18,
    sharpe_ratio: 1.1,
    sortino_ratio: 1.4,
    beta: 1.5,
    alpha: 0.08,
    data_coverage: 1,
    trading_days: 252,
    data_start: "2025-01-02",
    data_end: "2025-12-31",
    note: null,
  },
  {
    ticker: "MSFT",
    status: "ok",
    retryable: false,
    total_return: 0.18,
    cagr: 0.18,
    volatility: 0.24,
    mdd: -0.12,
    sharpe_ratio: 0.9,
    sortino_ratio: 1.2,
    beta: 1.05,
    alpha: 0.04,
    data_coverage: 1,
    trading_days: 252,
    data_start: "2025-01-02",
    data_end: "2025-12-31",
    note: null,
  },
];

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function scanResultFor(ticker, position = 0) {
  return {
    ticker,
    status: "ok",
    retryable: false,
    total_return: 0.1 + position / 10_000,
    cagr: 0.08 + position / 10_000,
    volatility: 0.2,
    mdd: -0.1,
    sharpe_ratio: 0.8,
    sortino_ratio: 1.1,
    beta: 1.0,
    alpha: 0.02,
    data_coverage: 1,
    trading_days: 252,
    data_start: "2025-01-02",
    data_end: "2025-12-31",
    note: null,
  };
}

test("initializes the UI and completes the Universe scanner flow", async ({ page }) => {
  const pageErrors = [];
  const consoleErrors = [];
  let screenerPayload;
  const scanPayloads = [];

  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, ["AAPL", "MSFT", "NVDA"]));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: universes }));
  await page.route("**/api/v2/screener", async (route) => {
    screenerPayload = route.request().postDataJSON();
    await fulfillJson(route, {
      universe: {
        id: "nasdaq100",
        name: "NASDAQ-100（自動備援）",
        version: "2026-07-29-nasdaq100",
        sourceAsOf: "2026-07-29",
      },
      fundamentalsAsOf: "2026-07-29",
      funnel: {
        universeCount: 103,
        fundamentalsAvailable: 93,
        sectorMatches: 93,
        passedFilters: 2,
        selectedForScan: 2,
      },
      candidates: [
        { ticker: "NVDA", marketCap: 4_300_000_000_000, sector: "Technology", trailingPE: 57 },
        { ticker: "MSFT", marketCap: 3_700_000_000_000, sector: "Technology", trailingPE: 37 },
      ],
      truncated: false,
      warnings: [],
    });
  });
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    scanPayloads.push(payload);
    if (scanPayloads.length === 1) {
      await fulfillJson(route, [
        {
          ticker: "NVDA",
          status: "pending",
          retryable: true,
          error_code: "market_data_temporarily_unavailable",
        },
        scanResults[1],
      ]);
      return;
    }
    await fulfillJson(route, [scanResults[0]]);
  });

  await page.goto("/");

  await expect(page.locator("#service-status")).toHaveText("服務正常");
  await expect(page.locator('input[list="ticker-options"]')).toHaveCount(4);
  await expect(page.locator("#portfolio-list .portfolio-card")).toHaveCount(2);

  await page.getByRole("button", { name: "個股掃描" }).click();
  await expect(page.getByRole("heading", { name: "個股績效掃描" })).toBeVisible();
  await expect(page.locator("#universe-status")).toHaveText("4 個股票池可用");

  await page.locator("#screener-index").selectOption("nasdaq100");
  await page.getByRole("button", { name: "篩選並建立回測清單" }).click();

  await expect(page.locator("#scan-tickers")).toHaveValue("NVDA, MSFT");
  await expect(page.locator("#screener-funnel")).toContainText("納入回測");
  expect(screenerPayload).toMatchObject({
    universe: "nasdaq100",
    sector: "any",
    limit: null,
    sort: "marketCap-desc",
  });

  await page.locator("#scan-start-period").fill("2025-01");
  await page.locator("#scan-end-period").fill("2025-12");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  await expect(page.locator("#scan-results")).toBeVisible();
  await expect(page.locator("#scan-summary")).toContainText("2 / 2");
  await expect(page.locator("#scan-table")).toContainText("NVDA");
  await expect(page.locator("#scan-context")).toContainText("NASDAQ-100");
  expect(scanPayloads[0]).toMatchObject({
    tickers: ["NVDA", "MSFT"],
    benchmark: "SPY",
    startYear: 2025,
    startMonth: 1,
    endYear: 2025,
    endMonth: 12,
  });
  expect(scanPayloads[1].tickers).toEqual(["NVDA"]);

  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test("defaults to every filtered candidate and paginates more than 100 results", async ({ page }) => {
  const candidates = Array.from({ length: 125 }, (_, index) => ({
    ticker: `T${String(index + 1).padStart(4, "0")}`,
    marketCap: 500_000_000_000 - index,
    sector: "Technology",
    trailingPE: 20,
  }));
  const scanPayloads = [];
  let screenerPayload;

  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, candidates.map((item) => item.ticker)));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: universes }));
  await page.route("**/api/v2/screener", async (route) => {
    screenerPayload = route.request().postDataJSON();
    await fulfillJson(route, {
      universe: {
        id: "sp500",
        name: "S&P 500（IVV holdings）",
        version: "2026-07-27-sp500",
        sourceAsOf: "2026-07-27",
      },
      fundamentalsAsOf: "2026-07-29",
      funnel: {
        universeCount: 504,
        fundamentalsAvailable: 482,
        sectorMatches: 482,
        passedFilters: candidates.length,
        selectedForScan: candidates.length,
      },
      candidates,
      truncated: false,
      limit: null,
      warnings: [],
    });
  });
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    scanPayloads.push(payload);
    await fulfillJson(
      route,
      payload.tickers.map((ticker, index) => scanResultFor(ticker, scanPayloads.length * 10 + index)),
    );
  });

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.getByRole("button", { name: "篩選並建立回測清單" }).click();

  expect(screenerPayload.limit).toBeNull();
  await expect(page.locator("#scan-tickers")).toHaveValue(/T0125/);
  await page.locator("#scan-start-period").fill("2025-01");
  await page.locator("#scan-end-period").fill("2025-12");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  await expect(page.locator("#scan-summary")).toContainText("125 / 125");
  expect(scanPayloads.map((payload) => payload.tickers.length)).toEqual([100, 25]);
  expect(Math.max(...scanPayloads.map((payload) => payload.tickers.length))).toBeLessThanOrEqual(100);
  expect(scanPayloads.flatMap((payload) => payload.tickers)).toEqual(candidates.map((item) => item.ticker));
  await expect(page.locator("#scan-pagination")).toBeVisible();
  await expect(page.locator("#scan-page-status")).toHaveText("第 1 / 2 頁");
  await page.getByRole("button", { name: "下一頁" }).click();
  await expect(page.locator("#scan-page-status")).toHaveText("第 2 / 2 頁");
});

test("accepts more than 100 manually entered tickers", async ({ page }) => {
  const tickers = Array.from({ length: 101 }, (_, index) => `M${String(index + 1).padStart(4, "0")}`);
  const scanPayloads = [];

  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: universes }));
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    scanPayloads.push(payload);
    await fulfillJson(route, payload.tickers.map((ticker) => scanResultFor(ticker)));
  });

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.locator("#scan-tickers").fill(tickers.join(", "));
  await page.locator("#scan-start-period").fill("2025-01");
  await page.locator("#scan-end-period").fill("2025-12");
  await page.getByRole("button", { name: "開始集體回測" }).click();

  await expect(page.locator("#scan-summary")).toContainText("101 / 101");
  expect(scanPayloads.map((payload) => payload.tickers.length)).toEqual([100, 1]);
  expect(scanPayloads.flatMap((payload) => payload.tickers)).toEqual(tickers);
  expect(Math.max(...scanPayloads.map((payload) => payload.tickers.length))).toBeLessThanOrEqual(100);
});

test("restores a saved scan and requests only unfinished tickers", async ({ page }) => {
  const scanPayloads = [];
  const savedJob = {
    version: 2,
    id: "saved-scan",
    status: "running",
    createdAt: "2026-07-30T00:00:00.000Z",
    updatedAt: "2026-07-30T00:01:00.000Z",
    payload: {
      tickers: ["AAPL", "MSFT", "NVDA"],
      benchmark: "SPY",
      startYear: 2025,
      startMonth: 1,
      endYear: 2025,
      endMonth: 12,
    },
    screenerContext: null,
    pending: ["NVDA"],
    results: [scanResultFor("AAPL"), scanResultFor("MSFT")],
    attempts: { NVDA: 1 },
    retryRound: 0,
  };

  await page.addInitScript((job) => {
    localStorage.setItem("backteststock-scan-job-v2", JSON.stringify(job));
  }, savedJob);
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: universes }));
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    scanPayloads.push(payload);
    await fulfillJson(route, [scanResultFor("NVDA")]);
  });

  await page.goto("/");
  await expect(page.locator("#scan-summary")).toContainText("3 / 3");
  expect(scanPayloads).toHaveLength(1);
  expect(scanPayloads[0].tickers).toEqual(["NVDA"]);
  await expect.poll(
    () => page.evaluate(() => {
      const saved = JSON.parse(localStorage.getItem("backteststock-scan-job-v2"));
      return { status: saved?.status, results: saved?.results?.length };
    }),
  ).toEqual({ status: "completed", results: 3 });
});
