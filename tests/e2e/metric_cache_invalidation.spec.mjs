import { expect, test } from "@playwright/test";

const STORAGE_KEY = "backteststock-scan-job-v2";
const SESSION_KEY = "backteststock-metric-cache-invalidated";
const METRIC_VERSION = "2026-07-31.1";

test("stale saved scan results are removed before they can remain active", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(({ storageKey }) => {
    localStorage.setItem(storageKey, JSON.stringify({
      id: "legacy-metric-job",
      status: "completed",
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
  }, { storageKey: STORAGE_KEY });

  await page.reload({ waitUntil: "domcontentloaded" });

  await expect.poll(() => page.evaluate(
    ({ storageKey }) => localStorage.getItem(storageKey),
    { storageKey: STORAGE_KEY },
  )).toBeNull();
  await expect.poll(() => page.evaluate(
    ({ sessionKey }) => sessionStorage.getItem(sessionKey),
    { sessionKey: SESSION_KEY },
  )).toBe(METRIC_VERSION);
});

test("current metric-version scan results remain available", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(({ storageKey, metricVersion }) => {
    localStorage.setItem(storageKey, JSON.stringify({
      id: "current-metric-job",
      status: "completed",
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
  }, { storageKey: STORAGE_KEY, metricVersion: METRIC_VERSION });

  await page.reload({ waitUntil: "domcontentloaded" });

  const savedJob = await page.evaluate(
    ({ storageKey }) => JSON.parse(localStorage.getItem(storageKey)),
    { storageKey: STORAGE_KEY },
  );
  expect(savedJob.id).toBe("current-metric-job");
  expect(savedJob.results[0].metric_definition_version).toBe(METRIC_VERSION);
});
