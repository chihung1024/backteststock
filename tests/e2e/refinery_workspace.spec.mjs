import { expect, test } from "@playwright/test";

const REFINERY_KEY = "backteststock.refinery.workspace.v1";
const ACTIVE_KEY = "backteststock.portfolio.active-workspace.v1";

function preflightResponse(symbols) {
  return {
    contract_version: "refinery-v1",
    schema_version: "refinery-v1-2026-08-09.1",
    endpoint: "preflight",
    status: "ready",
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
      candidate_dataset_hash: "1234567890abcdef1234567890abcdef",
      benchmark_dataset_hash: null,
      requested_symbols: symbols,
      resolved_symbols: symbols,
      failures: {},
      effective_start: "2024-01-02",
      effective_end: "2025-01-01",
      reference_observations: 252,
      daily_return_observations: 251,
      daily_complete_case_observations: 251,
      weekly_return_observations: 52,
      weekly_complete_case_observations: 52,
      coverage: Object.fromEntries(symbols.map((symbol) => [symbol, { ratio: 1 }])),
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
      analysis_ready: true,
      candidate_membership_complete: true,
      reasons: [],
    },
  };
}

function correlationView(symbols, matrix, status = "ok") {
  return {
    status,
    input_observations: status === "ok" ? 120 : 0,
    observations: status === "ok" ? 120 : 0,
    dropped_observations: 0,
    window: status === "ok" ? 252 : null,
    condition: status === "ok" ? "medium_daily" : "benchmark_not_supplied",
    threshold: null,
    matrix: status === "ok" ? { symbols, values: matrix } : null,
  };
}

function analyzeResponse(symbols, { matrix, withWeights = false } = {}) {
  const values = matrix ?? symbols.map((_, row) => symbols.map((__, column) => row === column ? 1 : 0.35));
  const base = preflightResponse(symbols);
  return {
    ...base,
    endpoint: "analyze",
    status: "ok",
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
          entropy_effective_rank: Math.max(1, symbols.length * 0.68),
          participation_ratio: Math.max(1, symbols.length * 0.61),
          positive_eigenvalues: [0.04, 0.03],
        },
        medium_correlation: {
          entropy_effective_rank: Math.max(1, symbols.length * 0.64),
          participation_ratio: Math.max(1, symbols.length * 0.58),
          positive_eigenvalues: [1.4, 0.6],
        },
      },
      portfolio: withWeights
        ? {
            status: "ok",
            weights: symbols.map(() => 1 / symbols.length),
            variance: 0.02,
            volatility: 0.14,
            marginal_risk_contribution: symbols.map(() => 0.14),
            signed_component_risk_contribution: symbols.map(() => 0.14 / symbols.length),
            diversification_ratio: 1.35,
            weight_effective_holdings: symbols.length,
            gross_risk_contribution_equivalent_holdings: symbols.length,
          }
        : {
            status: "unavailable_weights_not_supplied",
            weights: null,
          },
      correlations: {
        tactical_daily: correlationView(symbols, values),
        medium_daily: correlationView(symbols, values),
        structural_weekly: correlationView(symbols, values),
        downside: correlationView(symbols, values, "unavailable_benchmark_not_supplied"),
        stress: correlationView(symbols, values, "unavailable_benchmark_not_supplied"),
      },
    },
  };
}

async function mockPortfolioHealth(page) {
  await page.route("**/api/v3/portfolio/health", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) });
  });
}

async function mockRefinery(page, symbols, options = {}) {
  await page.route("**/api/v1/refinery/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const payload = path.endsWith("/preflight")
      ? preflightResponse(symbols)
      : analyzeResponse(symbols, options);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "x-request-id": "e2e-refinery-request" },
      body: JSON.stringify(payload),
    });
  });
}

test("Refinery workspace persists independently and shared Portfolio links initially force Portfolio mode", async ({ page }) => {
  await mockPortfolioHealth(page);
  await page.goto("/portfolio/");

  await expect(page.getByRole("button", { name: /投資組合回測/ })).toHaveClass(/active/u);
  await page.getByRole("button", { name: /持股精煉診斷/ }).click();
  await expect(page.getByTestId("refinery-workspace")).toBeVisible();
  await page.getByLabel("Refinery 持股 1 代碼", { exact: true }).fill("AAPL");
  await page.getByLabel("Refinery 持股 2 代碼", { exact: true }).fill("MSFT");

  const stored = await page.evaluate(({ refineryKey, activeKey }) => ({
    refinery: localStorage.getItem(refineryKey),
    active: localStorage.getItem(activeKey),
    portfolio: localStorage.getItem("backteststock.portfolio.model.v1"),
  }), { refineryKey: REFINERY_KEY, activeKey: ACTIVE_KEY });
  expect(stored.active).toBe("refinery");
  expect(stored.refinery).toContain("AAPL");

  await page.reload();
  await expect(page.getByTestId("refinery-workspace")).toBeVisible();
  await expect(page.getByLabel("Refinery 持股 1 代碼", { exact: true })).toHaveValue("AAPL");

  await page.goto("/portfolio/?model=invalid-but-present");
  await expect(page.getByRole("heading", { name: "投資組合研究工作區" })).toBeVisible();
  await expect(page.getByTestId("refinery-workspace")).toHaveCount(0);
  await page.getByRole("button", { name: /持股精煉診斷/ }).click();
  await expect(page.getByTestId("refinery-workspace")).toBeVisible();

  await page.goto("/portfolio/?handoff=missing-session-key");
  await expect(page.getByRole("heading", { name: "投資組合研究工作區" })).toBeVisible();
  await page.getByRole("button", { name: /持股精煉診斷/ }).click();
  await expect(page.getByTestId("refinery-workspace")).toBeVisible();
});

test("Refinery preflight then analyze keeps portfolio risk unavailable when weights are omitted", async ({ page }) => {
  const symbols = ["AAPL", "MSFT"];
  await mockPortfolioHealth(page);
  await mockRefinery(page, symbols);
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: /持股精煉診斷/ }).click();
  await page.getByLabel("Refinery 持股 1 代碼", { exact: true }).fill(symbols[0]);
  await page.getByLabel("Refinery 持股 2 代碼", { exact: true }).fill(symbols[1]);

  await page.getByRole("button", { name: "資料預檢" }).click();
  await expect(page.getByRole("heading", { name: "Refinery 資料預檢" })).toBeVisible();
  await expect(page.getByText("可分析", { exact: true })).toBeVisible();

  const analyzeButton = page.getByRole("button", { name: "執行風險診斷" });
  await expect(analyzeButton).toBeEnabled();
  await analyzeButton.click();

  await expect(page.getByRole("heading", { name: "結構摘要" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "資本 vs 簽名風險貢獻" })).toBeVisible();
  await expect(page.getByText("未提供顯式權重，因此不假設等權。 ")).toBeVisible();
  await expect(page.getByText("Portfolio risk unavailable")).toBeVisible();
});

test("model changes invalidate late Refinery evidence", async ({ page }) => {
  let releaseFirstAnalyze;
  const firstAnalyzeGate = new Promise((resolve) => {
    releaseFirstAnalyze = resolve;
  });
  let firstAnalyzeStarted;
  const firstAnalyzeStartedPromise = new Promise((resolve) => {
    firstAnalyzeStarted = resolve;
  });
  let analyzeCount = 0;

  // Exercise the UI guard even if a transport completes after AbortController.abort().
  await page.addInitScript(() => {
    const nativeFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      if (!init?.signal) return nativeFetch(input, init);
      const passthrough = { ...init };
      delete passthrough.signal;
      return nativeFetch(input, passthrough);
    };
  });
  await mockPortfolioHealth(page);
  await page.route("**/api/v1/refinery/preflight", (route) => route.fulfill({
    json: preflightResponse(["AAPL", "MSFT"]),
  }));
  await page.route("**/api/v1/refinery/analyze", async (route) => {
    analyzeCount += 1;
    if (analyzeCount === 1) {
      firstAnalyzeStarted();
      await firstAnalyzeGate;
    }
    try {
      await route.fulfill({ json: analyzeResponse(["AAPL", "MSFT"]) });
    } catch {
      // The delayed response may be released after the route was superseded.
    }
  });

  await page.goto("/portfolio/");
  await page.getByRole("button", { name: /持股精煉診斷/ }).click();
  await page.getByLabel("Refinery 持股 1 代碼", { exact: true }).fill("AAPL");
  await page.getByLabel("Refinery 持股 2 代碼", { exact: true }).fill("MSFT");
  await page.getByRole("button", { name: "資料預檢" }).click();
  await expect(page.getByRole("heading", { name: "Refinery 資料預檢" })).toBeVisible();
  await page.getByRole("button", { name: "執行風險診斷" }).click();
  await firstAnalyzeStartedPromise;

  await page.getByLabel("Refinery 持股 1 代碼", { exact: true }).fill("NVDA");
  await expect(page.getByRole("heading", { name: "結構摘要" })).toHaveCount(0);

  releaseFirstAnalyze();
  await expect(page.getByRole("heading", { name: "結構摘要" })).toHaveCount(0);
});

test("large correlation results use pair summary instead of mounting a full matrix", async ({ page }) => {
  const symbols = Array.from({ length: 21 }, (_, index) => `SYM${String(index + 1).padStart(2, "0")}`);
  const model = {
    schemaVersion: 1,
    symbols: symbols.map((symbol, index) => ({ id: `asset-${index}`, symbol, weightPercent: null })),
    benchmark: "",
    startDate: "2024-01-01",
    endDate: "2025-01-01",
    useWeights: false,
    ewmaDecay: 0.94,
    stressQuantile: 0.1,
  };
  const matrix = symbols.map((_, row) => symbols.map((__, column) => {
    if (row === column) return 1;
    return Number((0.1 + ((row + column) % 8) * 0.1).toFixed(2));
  }));

  await page.addInitScript(({ modelValue }) => {
    localStorage.setItem("backteststock.portfolio.active-workspace.v1", "refinery");
    localStorage.setItem("backteststock.refinery.workspace.v1", JSON.stringify(modelValue));
  }, { modelValue: model });
  await mockPortfolioHealth(page);
  await mockRefinery(page, symbols, { matrix });
  await page.goto("/portfolio/");
  await expect(page.getByTestId("refinery-workspace")).toBeVisible();

  await page.getByRole("button", { name: "資料預檢" }).click();
  await page.getByRole("button", { name: "執行風險診斷" }).click();

  await expect(page.getByText("大型矩陣摘要")).toBeVisible();
  await expect(page.getByRole("region", { name: "完整相關矩陣" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "大型相關矩陣配對摘要" })).toBeVisible();
});

test("390px Refinery workspace remains usable without page-level horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockPortfolioHealth(page);
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: /持股精煉診斷/ }).click();
  await expect(page.getByTestId("refinery-workspace")).toBeVisible();
  await expect(page.getByLabel("手機 Refinery 持股 1 代碼")).toBeVisible();

  const overflow = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    documentWidth: document.documentElement.scrollWidth,
  }));
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewport + 1);
  await expect(page.locator(".refinery-run-bar")).toBeVisible();
});
