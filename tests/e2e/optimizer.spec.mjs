import { gzipSync } from "node:zlib";
import { expect, test } from "@playwright/test";

const tickers = ["T00", "T01", "T02", "T03", "T04"];

function buildSnapshot() {
  const dates = [];
  const prices = {};
  const start = new Date("2024-01-02T00:00:00Z");
  for (let day = 0; day < 80; day += 1) {
    const date = new Date(start);
    date.setUTCDate(date.getUTCDate() + day);
    dates.push(date.toISOString().slice(0, 10));
  }
  for (let asset = 0; asset < tickers.length; asset += 1) {
    prices[tickers[asset]] = dates.map((_, day) => (
      100 + asset * 2 + day * (0.08 + asset * 0.01) + Math.sin(day / 5 + asset)
    ));
  }
  prices.SPY = dates.map((_, day) => 100 + day * 0.09 + Math.sin(day / 7));
  return {
    formatVersion: "exhaustive-optimizer-snapshot-json-gzip-v1",
    optimizerMode: "exhaustive_full_period",
    optimizerAlgorithmVersion: "exhaustive-test-v1",
    valuationCurrency: "TWD",
    candidateTickers: tickers,
    benchmark: "SPY",
    dates,
    prices,
    requestedStart: dates[0],
    requestedEndInclusive: dates.at(-1),
  };
}

function envelope(snapshot) {
  const compressed = gzipSync(Buffer.from(JSON.stringify(snapshot)));
  return {
    format: "exhaustive-optimizer-snapshot-json-gzip-v1",
    encoding: "gzip+base64",
    data: compressed.toString("base64"),
    compressedBytes: compressed.length,
    uncompressedBytes: JSON.stringify(snapshot).length,
    datasetHash: "e2e-exhaustive-dataset",
    signature: "e2e-signature",
    signatureMode: "hmac-sha256-secret",
  };
}

test("exhaustive optimizer preflights, confirms and evaluates every N choose K combination", async ({ page }) => {
  await page.addInitScript(({ savedTickers }) => {
    indexedDB.deleteDatabase("backteststock-exhaustive-optimizer-v1");
    localStorage.setItem("backteststock-scan-job-v3", JSON.stringify({
      id: "exhaustive-source",
      version: 3,
      status: "completed",
      payload: { tickers: savedTickers, benchmark: "SPY" },
      results: [],
      pending: [],
    }));
  }, { savedTickers: tickers });

  const snapshot = buildSnapshot();
  await page.route("**/api/optimizer/exhaustive/prepare", async (route) => {
    const payload = route.request().postDataJSON();
    expect(payload.sourceTickers).toEqual(tickers);
    expect(payload.holdingCount).toBe(2);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        snapshot: envelope(snapshot),
        summary: {
          sourceTickers: tickers,
          sourceTickerCount: tickers.length,
          benchmark: "SPY",
          observations: snapshot.dates.length,
          actualStart: snapshot.dates[0],
          actualEnd: snapshot.dates.at(-1),
          valuationCurrency: "TWD",
          persistentDailyPriceDatabase: false,
        },
      }),
    });
  });

  await page.goto("/optimizer.html", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#optimizer-source")).toHaveValue(/T00/);
  await page.locator("#optimizer-holding-count").fill("2");
  await expect(page.locator("#optimizer-combination-count")).toHaveText("10");
  await page.locator("#optimizer-worker-count").fill("2");
  await page.getByRole("button", { name: "預檢、測速並估算" }).click();

  await expect(page.locator("#optimizer-confirmation")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("#optimizer-confirmation-summary")).toContainText("10 組");
  await expect(page.locator("#optimizer-confirmation-summary")).toContainText("本機單 Worker");

  await page.getByRole("button", { name: "確認開始全量精確回測" }).click();
  await expect(page.locator("#optimizer-result-panel")).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("#optimizer-result-body tr")).toHaveCount(10);
  await expect(page.locator("#optimizer-result-summary")).toContainText("完整結果 10 組");
  await expect(page.locator("#optimizer-result-summary")).toContainText("篩選後 10 組");

  await page.locator("#optimizer-sort-field").selectOption("cagr");
  await page.locator("#optimizer-sort-direction").selectOption("desc");
  await page.getByRole("button", { name: "套用排序與篩選" }).click();
  await expect(page.locator("#optimizer-result-summary")).toContainText("CAGR");

  await page.locator("#optimizer-result-body [data-detail-id]").first().click();
  await expect(page.locator("#optimizer-detail-panel")).toBeVisible();
  await expect(page.locator("#optimizer-detail-body")).toContainText("再平衡事件");
});
