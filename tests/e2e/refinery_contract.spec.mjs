import { expect, test } from "@playwright/test";

function correlationView(symbols, matrix, status = "ok") {
  return {
    status,
    input_observations: status === "ok" ? 120 : 0,
    observations: status === "ok" ? 120 : 0,
    dropped_observations: 0,
    window: status === "ok" ? 252 : null,
    condition: status === "ok" ? "contract_fixture" : "benchmark_not_supplied",
    threshold: null,
    matrix: status === "ok" ? { symbols, values: matrix } : null,
  };
}

function preflightResponse(symbols, status = "ready") {
  const analysisReady = status === "ready";
  return {
    contract_version: "refinery-v1",
    schema_version: "refinery-v1-2026-08-09.1",
    endpoint: "preflight",
    status,
    request: {
      symbols,
      benchmark: null,
      start_date: "2024-01-01",
      end_date: "2025-01-01",
      weights_supplied: false,
      weights: null,
      weight_input_total_percent: null,
      weight_normalization: null,
      ewma_decay: 0.94,
      stress_quantile: 0.1,
    },
    methodology: {
      research_dataset_contract_version: "research-dataset-twd-2026-08-09.1",
      risk_math_contract_version: "risk-math-twd-2026-08-09.1",
    },
    dataset: {
      candidate_dataset_hash: "abcdef1234567890abcdef1234567890",
      benchmark_dataset_hash: null,
      requested_symbols: symbols,
      resolved_symbols: status === "incomplete" ? symbols.slice(0, -1) : symbols,
      failures: status === "incomplete"
        ? {
            [symbols.at(-1)]: {
              symbol: symbols.at(-1),
              stage: "history",
              code: "fixture_failure",
              detail: "Contract fixture intentionally leaves one requested candidate unresolved.",
              retryable: false,
            },
          }
        : {},
      effective_start: "2024-01-02",
      effective_end: "2025-01-01",
      reference_observations: status === "insufficient_data" ? 10 : 252,
      daily_return_observations: status === "insufficient_data" ? 9 : 251,
      daily_complete_case_observations: status === "insufficient_data" ? 9 : 251,
      weekly_return_observations: status === "insufficient_data" ? 1 : 52,
      weekly_complete_case_observations: status === "insufficient_data" ? 1 : 52,
      coverage: Object.fromEntries(symbols.map((symbol) => [symbol, { ratio: status === "incomplete" && symbol === symbols.at(-1) ? 0 : 1 }])),
      assets: {},
      benchmark: {
        symbol: null,
        status: "not_requested",
        failure: null,
        effective_start: null,
        effective_end: null,
      },
    },
    eligibility: {
      analysis_ready: analysisReady,
      candidate_membership_complete: status !== "incomplete",
      reasons: analysisReady
        ? []
        : [status === "incomplete" ? "requested candidate unresolved" : "insufficient common observations"],
    },
  };
}

function analyzeResponse(symbols) {
  const matrix = symbols.map((_, row) => symbols.map((__, column) => row === column ? 1 : 0.35));
  const base = preflightResponse(symbols);
  return {
    ...base,
    endpoint: "analyze",
    status: "ok",
    request: {
      ...base.request,
      weights_supplied: true,
      weights: symbols.map(() => 1 / symbols.length),
      weight_input_total_percent: 100,
      weight_normalization: "normalized_from_percent",
    },
    analysis: {
      symbols,
      covariance: {
        primary_method: "ledoit_wolf",
        annualization: 252,
        ledoit_wolf_shrinkage: 0.18,
        estimators: {
          sample: {
            method: "sample",
            observations: 251,
            features: symbols.length,
            annualization: 252,
            shrinkage: null,
            diagnostics: {
              observations: 251,
              features: symbols.length,
              symmetry_error: 0,
              tolerance: 1e-12,
              min_eigenvalue: 0.01,
              max_eigenvalue: 0.05,
              is_psd: true,
              numerical_rank: symbols.length,
              condition_number: 5,
            },
          },
          ledoit_wolf: {
            method: "ledoit_wolf",
            observations: 251,
            features: symbols.length,
            annualization: 252,
            shrinkage: 0.18,
            diagnostics: {
              observations: 251,
              features: symbols.length,
              symmetry_error: 0,
              tolerance: 1e-12,
              min_eigenvalue: 0.012,
              max_eigenvalue: 0.045,
              is_psd: true,
              numerical_rank: symbols.length,
              condition_number: 3.75,
            },
          },
          ewma: {
            method: "ewma",
            observations: 251,
            features: symbols.length,
            annualization: 252,
            shrinkage: null,
            diagnostics: {
              observations: 251,
              features: symbols.length,
              symmetry_error: 0,
              tolerance: 1e-12,
              min_eigenvalue: 0.009,
              max_eigenvalue: 0.052,
              is_psd: true,
              numerical_rank: symbols.length,
              condition_number: 5.78,
            },
          },
        },
        estimator_dispersion: {
          pairwise_relative_frobenius: {
            "sample::ledoit_wolf": 0.08,
            "sample::ewma": 0.12,
            "ledoit_wolf::ewma": 0.1,
          },
          maximum_relative_frobenius: 0.12,
        },
      },
      effective_dimensions: {
        covariance: {
          entropy_effective_rank: 1.8,
          participation_ratio: 1.7,
          positive_eigenvalues: [0.04, 0.03],
        },
        medium_correlation: {
          entropy_effective_rank: 1.6,
          participation_ratio: 1.5,
          positive_eigenvalues: [1.4, 0.6],
        },
      },
      portfolio: {
        status: "ok",
        weights: symbols.map(() => 1 / symbols.length),
        variance: 0.0196,
        volatility: 0.14,
        marginal_risk_contribution: symbols.map(() => 0.14),
        signed_component_risk_contribution: symbols.map(() => 0.14 / symbols.length),
        diversification_ratio: 1.35,
        weight_effective_holdings: symbols.length,
        gross_risk_contribution_equivalent_holdings: symbols.length,
      },
      correlations: {
        tactical_daily: correlationView(symbols, matrix),
        medium_daily: correlationView(symbols, matrix),
        structural_weekly: correlationView(symbols, matrix),
        downside: correlationView(symbols, matrix, "unavailable_benchmark_not_supplied"),
        stress: correlationView(symbols, matrix, "unavailable_benchmark_not_supplied"),
      },
    },
  };
}

async function mockPortfolioHealth(page) {
  await page.route("**/api/v3/portfolio/health", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) });
  });
}

async function openRefineryWithSymbols(page, symbols) {
  await mockPortfolioHealth(page);
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: /持股精煉診斷/ }).click();
  for (let index = 0; index < symbols.length; index += 1) {
    if (index >= 2) await page.getByRole("button", { name: "＋ 新增持股" }).click();
    await page.getByLabel(`Refinery 持股 ${index + 1} 代碼`, { exact: true }).fill(symbols[index]);
  }
}

for (const status of ["incomplete", "insufficient_data"]) {
  test(`Refinery preflight ${status} fails closed and keeps analyze disabled`, async ({ page }) => {
    const symbols = ["AAPL", "MSFT"];
    await page.route("**/api/v1/refinery/preflight", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "x-request-id": `e2e-${status}` },
        body: JSON.stringify(preflightResponse(symbols, status)),
      });
    });
    await openRefineryWithSymbols(page, symbols);

    await page.getByRole("button", { name: "資料預檢" }).click();
    await expect(page.getByRole("heading", { name: "Refinery 資料預檢" })).toBeVisible();
    await expect(page.getByText(status === "incomplete" ? "資料不完整" : "樣本不足", { exact: true })).toBeVisible();
    await expect(page.getByText("目前不可正式分析", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "執行風險診斷" })).toBeDisabled();
  });
}

test("explicit weights expose signed risk, covariance diagnostics and all correlation views without recommendations", async ({ page }) => {
  const symbols = ["AAPL", "MSFT"];
  await page.route("**/api/v1/refinery/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const payload = path.endsWith("/preflight") ? preflightResponse(symbols) : analyzeResponse(symbols);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "x-request-id": "e2e-refinery-contract" },
      body: JSON.stringify(payload),
    });
  });
  await openRefineryWithSymbols(page, symbols);

  await page.getByLabel("提供目前資本權重").check();
  await page.getByLabel("Refinery 持股 1 權重", { exact: true }).fill("50");
  await page.getByLabel("Refinery 持股 2 權重", { exact: true }).fill("50");
  await expect(page.getByText("合計 100.00%", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "資料預檢" }).click();
  await expect(page.getByText("可分析", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "執行風險診斷" }).click();

  await expect(page.getByRole("heading", { name: "結構摘要" })).toBeVisible();
  await expect(page.getByText("Cov. Effective Rank", { exact: true })).toBeVisible();
  await expect(page.getByText("Diversification Ratio", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "資本與風險貢獻列表" })).toBeVisible();
  await expect(page.getByText("50%", { exact: true })).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "Covariance 穩定度" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Covariance 診斷" })).toBeVisible();

  const correlationTabs = page.getByRole("tablist", { name: "相關視圖" });
  await expect(correlationTabs.getByRole("tab")).toHaveCount(5);
  for (const label of ["戰術 63D", "中期 252D", "結構 156W"]) {
    await correlationTabs.getByRole("tab", { name: label }).click();
    await expect(page.getByRole("region", { name: "完整相關矩陣" })).toBeVisible();
  }
  for (const label of ["下跌日", "壓力尾端"]) {
    await correlationTabs.getByRole("tab", { name: label }).click();
    await expect(page.getByText("此相關視圖目前不可用", { exact: true })).toBeVisible();
    await expect(page.getByText(/未提供基準/)).toBeVisible();
  }

  await expect(page.getByText(/KEEP|TRIM|REPLACE|冗餘判定/)).toHaveCount(0);
});
