import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

async function fulfillJson(route, body, status = 200, headers = {}) {
  await route.fulfill({
    status,
    contentType: "application/json",
    headers,
    body: JSON.stringify(body),
  });
}

const scanRow = {
  ticker: "AAA",
  status: "ok",
  retryable: false,
  total_return: 1.25,
  cagr: 0.18,
  volatility: 0.25,
  mdd: -0.32,
  sharpe_ratio: 0.9,
  sortino_ratio: 1.3,
  beta: 1.1,
  alpha: 0.05,
  data_coverage: 0.97,
  trading_days: 220,
  data_start: "2025-02-13",
  data_end: "2026-07-31",
  metric_start: "2025-02-13",
  metric_end: "2026-07-31",
  metric_price_observations: 220,
  metric_return_observations: 219,
  note: "（從 2025-02-13 開始；再現資訊 metric=legacy;asset_sha256=abc;aligned_sha256=def）",
  metric_definition_version: "2026-08-01.2",
  data_source: "Yahoo Finance via yfinance",
  data_source_version: "1.5.2",
  numpy_version: "2.2.6",
  pandas_version: "2.2.3",
  scipy_version: "1.17.1",
  fingerprint_algorithm: "sha256-le-i8-f8-v1",
  risk_free_rate: 0,
  trading_days_per_year: 252,
  benchmark: "SPY",
  benchmark_available: true,
  requested_start: "2025-01-01",
  requested_end_exclusive: "2026-08-01",
  return_basis: "yahoo_adjusted_close_total_return_gross_reinvestment",
  return_price_column: "Adj Close",
  dividend_reinvestment_assumption: "gross_distribution_reinvestment_as_embedded_in_yahoo_adjusted_close",
  market_data_contract_version: "adjusted-close-actions-2026-08-01.2",
  corporate_action_policy_version: "2026-08-01.2",
  corporate_action_status: "verified_standard_actions",
  benchmark_corporate_action_audit: { status: "verified_standard_actions" },
  dividend_events: 4,
  stock_split_events: 1,
  capital_gain_events: 0,
  price_repaired_rows: 2,
  unexplained_adjustment_changes: 0,
  distribution_adjustment_mismatches: 0,
  split_like_unreported_changes: 0,
  large_unexplained_returns: 0,
  corporate_action_warning_dates: "",
  standard_action_coverage: [
    "cash_dividends_reported_by_yahoo",
    "stock_splits_and_reverse_splits_reported_by_yahoo",
  ],
  nonstandard_action_limitations: [
    "spin_off_distribution_not_reported_as_yahoo_adjustment",
    "rights_or_warrant_distribution",
  ],
  price_fingerprint: "abc",
  aligned_price_fingerprint: "def",
  benchmark_price_fingerprint: "ghi",
  reproducibility: "metric=2026-08-01.2;basis=yahoo_adjusted_close_total_return_gross_reinvestment;asset_sha256=abc;aligned_sha256=def",
  data_source_settings: {
    interval: "1d",
    auto_adjust: false,
    repair: true,
    actions: true,
    keepna: false,
  },
};

test("scan table stays compact and separates concise from audit CSV", async ({ page }) => {
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));
  await page.route("**/api/scan", (route) => fulfillJson(
    route,
    [scanRow],
    200,
    {
      "x-backend-server-timing": "market;dur=1250.0, compute;dur=220.0, total;dur=1500.0",
      "x-scan-requested": "1",
      "x-scan-resolved": "1",
    },
  ));

  await page.goto("/");
  await page.getByRole("button", { name: "個股掃描" }).click();
  await page.locator("#scan-tickers").fill("AAA");
  await page.locator("#scan-start-period").fill("2025-01");
  await page.locator("#scan-end-period").fill("2026-07");
  await page.getByRole("button", { name: "開始集體回測" }).click();
  await expect(page.locator("#loading-overlay")).toHaveClass(/hidden/);

  const tickerCell = page.locator("#scan-table tbody th").first();
  await expect(tickerCell).toContainText("AAA");
  await expect(tickerCell).toContainText("從 2025-02-13 開始");
  await expect(tickerCell).not.toContainText("asset_sha256");
  const tickerWidth = await tickerCell.evaluate((element) => element.getBoundingClientRect().width);
  expect(tickerWidth).toBeLessThanOrEqual(190);

  await expect(page.locator("#scan-batch-timing")).toContainText("行情下載與修復 1.3 秒");
  await expect(page.locator("#scan-batch-timing")).toContainText("指標與稽核計算 0.2 秒");

  const formulaDetails = page.locator("#score-formula-comparison");
  await expect(formulaDetails).toBeVisible();
  await expect(formulaDetails).toHaveJSProperty("tagName", "DETAILS");
  await expect(formulaDetails).toHaveJSProperty("open", false);
  await expect(formulaDetails.locator("summary")).toHaveText("分數公式與排名說明");

  const conciseDownloadPromise = page.waitForEvent("download");
  await page.locator("#export-scan").click();
  const conciseDownload = await conciseDownloadPromise;
  const concisePath = await conciseDownload.path();
  const conciseText = await readFile(concisePath, "utf8");
  expect(conciseDownload.suggestedFilename()).toBe("scan-results.csv");
  expect(conciseText).toContain("sortino_growth_beta_score");
  expect(conciseText).not.toContain("sortino_growth_beta_score_status");
  expect(conciseText).not.toContain("price_fingerprint");
  expect(conciseText).not.toContain("asset_sha256");
  expect(conciseText).not.toContain("corporate_action_status");
  expect(conciseText).not.toContain("return_basis");
  expect(conciseText).toContain("從 2025-02-13 開始");

  const auditDownloadPromise = page.waitForEvent("download");
  await page.locator("#export-scan-audit").click();
  const auditDownload = await auditDownloadPromise;
  const auditPath = await auditDownload.path();
  const auditText = await readFile(auditPath, "utf8");
  expect(auditDownload.suggestedFilename()).toBe("scan-results-audit.csv");
  expect(auditText).toContain("sortino_growth_beta_score_status");
  expect(auditText).toContain("fingerprint_algorithm");
  expect(auditText).toContain("price_fingerprint");
  expect(auditText).toContain("asset_sha256=abc");
  expect(auditText).toContain("return_basis");
  expect(auditText).toContain("yahoo_adjusted_close_total_return_gross_reinvestment");
  expect(auditText).toContain("corporate_action_status");
  expect(auditText).toContain("verified_standard_actions");
  expect(auditText).toContain("dividend_events");
  expect(auditText).toContain("stock_split_events");
  expect(auditText).toContain("price_repaired_rows");
  expect(auditText).toContain("corporate_action_warning_dates");
  expect(auditText).toContain("spin_off_distribution_not_reported_as_yahoo_adjustment");
});
