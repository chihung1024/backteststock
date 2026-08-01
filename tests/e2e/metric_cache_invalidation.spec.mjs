import { expect, test } from "@playwright/test";

const STORAGE_KEY = "backteststock-scan-job-v2";
const SESSION_KEY = "backteststock-metric-cache-invalidated";
const METRIC_VERSION = "2026-08-01.2";

function scanPayload() {
  return {
    tickers: ["AAA"],
    benchmark: "SPY",
    startYear: 2024,
    startMonth: 1,
    endYear: 2024,
    endMonth: 12,
  };
}

test("stale saved scan results are automatically recalculated", async ({ page }) => {
  await page.goto("/");
  let scanRequests = 0;
  await page.route("**/api/scan", async (route) => {
    scanRequests += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          ticker: "AAA",
          status: "ok",
          retryable: false,
          metric_definition_version: METRIC_VERSION,
          total_return: 0.42,
          cagr: 0.42,
          volatility: 0.30,
          mdd: -0.20,
          sharpe_ratio: 1.40,
          sortino_ratio: 2.10,
          beta: 1.05,
          alpha: 0.08,
          data_coverage: 1,
          trading_days: 252,
          data_start: "2024-01-02",
          data_end: "2024-12-31",
        },
      ]),
    });
  });

  await page.evaluate(({ storageKey, payload }) => {
    localStorage.setItem(storageKey, JSON.stringify({
      version: 2,
      id: "legacy-metric-job",
      status: "completed",
      createdAt: "2025-01-01T00:00:00.000Z",
      updatedAt: "2025-01-01T00:00:00.000Z",
      payload,
      pending: [],
      attempts: {},
      retryRound: 0,
      results: [
        {
          ticker: "AAA",
          status: "ok",
          cagr: 0.25,
          sortino_ratio: 1.4,
          beta: 1.1,
          mdd: -0.3,
        },
      ],
    }));
  }, { storageKey: STORAGE_KEY, payload: scanPayload() });

  // The metric migration deliberately performs one nested reload. Schedule the
  // first navigation asynchronously so Playwright does not wait on the
  // intermediate document that is immediately replaced by the migration.
  await page.evaluate(() => {
    setTimeout(() => window.location.reload(), 0);
  });

  await expect.poll(async () => {
    try {
      return await page.evaluate(({ storageKey, metricVersion }) => {
        const raw = localStorage.getItem(storageKey);
        if (!raw) return null;
        const job = JSON.parse(raw);
        const result = job.results?.[0];
        return (
          job.status === "completed"
          && result?.metric_definition_version === metricVersion
          && result?.cagr === 0.42
        ) ? "recalculated" : null;
      }, { storageKey: STORAGE_KEY, metricVersion: METRIC_VERSION });
    } catch {
      // A navigation can destroy the current execution context between polls.
      return null;
    }
  }, { timeout: 30_000 }).toBe("recalculated");

  const recalculated = await page.evaluate(
    ({ storageKey }) => JSON.parse(localStorage.getItem(storageKey)),
    { storageKey: STORAGE_KEY },
  );
  expect(scanRequests).toBe(1);
  expect(recalculated.recalculationReason).toBe("metric_definition_changed");
  expect(recalculated.results[0].metric_definition_version).toBe(METRIC_VERSION);
  expect(recalculated.results[0].cagr).toBe(0.42);
  expect(recalculated.results[0].cagr).not.toBe(0.25);
  expect(await page.evaluate(
    ({ sessionKey }) => sessionStorage.getItem(sessionKey),
    { sessionKey: SESSION_KEY },
  )).toBe(METRIC_VERSION);
});

test("current metric-version scan results remain available without recalculation", async ({ page }) => {
  await page.goto("/");
  let scanRequests = 0;
  await page.route("**/api/scan", async (route) => {
    scanRequests += 1;
    await route.abort();
  });
  await page.evaluate(({ storageKey, metricVersion, payload }) => {
    localStorage.setItem(storageKey, JSON.stringify({
      version: 2,
      id: "current-metric-job",
      status: "completed",
      createdAt: "2026-07-31T00:00:00.000Z",
      updatedAt: "2026-07-31T00:00:00.000Z",
      payload,
      pending: [],
      attempts: {},
      retryRound: 0,
      results: [
        {
          ticker: "AAA",
          status: "ok",
          metric_definition_version: metricVersion,
          cagr: 0.25,
          sortino_ratio: 1.4,
          beta: 1.1,
          mdd: -0.3,
        },
      ],
    }));
  }, {
    storageKey: STORAGE_KEY,
    metricVersion: METRIC_VERSION,
    payload: scanPayload(),
  });

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(250);

  const savedJob = await page.evaluate(
    ({ storageKey }) => JSON.parse(localStorage.getItem(storageKey)),
    { storageKey: STORAGE_KEY },
  );
  expect(scanRequests).toBe(0);
  expect(savedJob.id).toBe("current-metric-job");
  expect(savedJob.results[0].metric_definition_version).toBe(METRIC_VERSION);
});
