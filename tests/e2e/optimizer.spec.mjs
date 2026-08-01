import { expect, test } from "@playwright/test";

const tickers = Array.from({ length: 20 }, (_, index) => `T${String(index).padStart(2, "0")}`);

function scanRow(ticker, index) {
  return {
    ticker,
    status: "ok",
    retryable: false,
    total_return: 0.5 + index * 0.01,
    cagr: 0.08 + index * 0.002,
    volatility: 0.2,
    mdd: -0.25 + index * 0.001,
    sharpe_ratio: 1,
    sortino_ratio: 1 + index * 0.05,
    beta: 0.9 + index * 0.005,
    alpha: 0.02 + index * 0.001,
    data_coverage: 1,
    corporate_action_status: "verified_standard_actions",
    metric_definition_version: "2026-08-01.2",
  };
}

function snapshotData() {
  const dates = [];
  const prices = {};
  const start = new Date("2024-01-02T00:00:00Z");
  for (let day = 0; day < 80; day += 1) {
    const date = new Date(start);
    date.setUTCDate(date.getUTCDate() + day);
    dates.push(date.toISOString().slice(0, 10));
  }
  for (let asset = 0; asset < 20; asset += 1) {
    prices[tickers[asset]] = dates.map((_, day) => 100 + asset + day * (0.1 + asset * 0.001));
  }
  prices.SPY = dates.map((_, day) => 100 + day * 0.12);
  return {
    optimizerAlgorithmVersion: "optimizer-test-v1",
    metricDefinitionVersion: "2026-08-01.2",
    candidateTickers: tickers,
    benchmark: "SPY",
    dates,
    prices,
    split: {
      splitIndex: 56,
      trainingStart: dates[0],
      trainingEnd: dates[55],
      validationStart: dates[56],
      validationEnd: dates.at(-1),
    },
  };
}

function exactResult(combination, index) {
  const metrics = {
    total_return: 0.2,
    cagr: 0.1 + index * 0.0001,
    mdd: -0.2,
    volatility: 0.18,
    sharpe_ratio: 1,
    sortino_ratio: 1.2 + index * 0.001,
    beta: 0.9,
    alpha: 0.03,
    annualizedTurnoverOneWay: 0.4,
    turnoverGross: 1000,
    turnoverOneWay: 0.2,
    transactionCost: 0,
    initialTradeCost: 0,
    rebalanceCount: 2,
    rebalanceEvents: [],
    unexecutedFinalSignal: null,
    portfolioValueFingerprint: `fingerprint-${index}`,
    metric_price_observations: 56,
  };
  return {
    combinationId: combination.combinationId,
    mask: combination.mask,
    tickers: combination.tickers,
    training: metrics,
    validation: {
      ...metrics,
      cagr: 0.07 + index * 0.00005,
      sortino_ratio: 0.9 + index * 0.0005,
      metric_price_observations: 24,
    },
  };
}

test("optimizer builds strict candidates and renders verified output", async ({ page }) => {
  await page.addInitScript(({ tickers: savedTickers }) => {
    localStorage.setItem("backteststock-scan-job-v2", JSON.stringify({
      id: "source-scan",
      version: 2,
      status: "completed",
      payload: {
        tickers: savedTickers,
        benchmark: "SPY",
        startDate: "2024-01-02",
        endDate: "2024-03-21",
      },
      pending: [],
      results: [],
    }));
  }, { tickers });

  await page.route("**/api/optimizer/calendar", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        trainingStart: "2024-01-02",
        trainingEnd: "2024-02-26",
        validationStart: "2024-02-27",
        validationEnd: "2024-03-21",
        trainingObservations: 56,
        validationObservations: 24,
        splitIndex: 56,
        benchmarkCorporateActionAudit: { status: "verified_standard_actions" },
      }),
    });
  });
  await page.route("**/api/scan", async (route) => {
    const payload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload.tickers.map((ticker) => scanRow(ticker, tickers.indexOf(ticker)))),
    });
  });
  await page.route("**/api/optimizer/prepare", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        snapshot: {
          format: "optimizer-snapshot-json-gzip-v1",
          encoding: "gzip+base64",
          data: "test",
          datasetHash: "dataset-hash",
          signature: "signature",
          signatureMode: "hmac-sha256-secret",
          compressedBytes: 100,
        },
        snapshotData: snapshotData(),
        summary: {
          candidateTickers: tickers,
          benchmark: "SPY",
          observations: 80,
          split: { splitIndex: 56 },
        },
      }),
    });
  });
  await page.route("**/api/optimizer/verify", async (route) => {
    const payload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        results: payload.combinations.map(exactResult),
        metadata: {
          optimizer_algorithm_version: "optimizer-test-v1",
          rebalance_engine_version: "relative-band-next-close-v1",
        },
      }),
    });
  });

  await page.goto("/optimizer.html");
  await expect(page.locator("#optimizer-source-status")).toContainText("20 檔");
  await page.locator("#optimizer-search-budget").fill("1000");
  await page.getByRole("button", { name: "建立候選池並執行最佳化" }).click();

  await expect(page.locator("#optimizer-candidate-panel")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("#optimizer-candidate-table tbody tr")).toHaveCount(20);
  await expect(page.locator("#optimizer-results")).toBeVisible({ timeout: 120_000 });
  await expect(page.locator("#optimizer-champions .optimizer-champion")).toHaveCount(5);
  await expect(page.locator("#optimizer-result-table tbody tr")).toHaveCount(300);
  await expect(page.locator("#optimizer-progress-label")).toContainText("全部完成");
  await expect(page.locator("#optimizer-reproducibility")).toContainText("dataset-hash");
  await expect(page.locator("#optimizer-reproducibility")).toContainText(
    '"verified_combinations": 300',
  );
});
