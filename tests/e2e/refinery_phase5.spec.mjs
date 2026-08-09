import { expect, test } from "@playwright/test";

const REFINERY_KEY = "backteststock.refinery.workspace.v1";
const ACTIVE_WORKSPACE_KEY = "backteststock.portfolio.active-workspace.v1";

function matrixFor(symbols, offDiagonal = 0.72) {
  return symbols.map((_, row) => symbols.map((__, column) => row === column ? 1 : offDiagonal));
}

function correlationView(symbols, matrix, status = "ok") {
  return {
    status,
    input_observations: status === "ok" ? 252 : 0,
    observations: status === "ok" ? 252 : 0,
    dropped_observations: 0,
    window: status === "ok" ? 252 : null,
    condition: status === "ok" ? "phase5_fixture" : "fixture_unavailable",
    threshold: null,
    matrix: status === "ok" ? { symbols, values: matrix } : null,
  };
}

function preflightResponse(symbols) {
  return {
    contract_version: "refinery-v1",
    schema_version: "refinery-v1-2026-08-10.2",
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
      clustering_contract_version: "refinery-clustering-twd-2026-08-10.1",
      clustering_primary_linkage: "average",
      clustering_sensitivity_linkage: "complete",
      clustering_flat_cut_distance: 0.5,
      clustering_stability_windows_weeks: [52, 104, 156],
      clustering_bootstrap_replicates: 200,
      clustering_bootstrap_block_weeks: 4,
    },
    dataset: {
      candidate_dataset_hash: "phase5fixture1234567890abcdef1234567890",
      benchmark_dataset_hash: null,
      requested_symbols: symbols,
      resolved_symbols: symbols,
      failures: {},
      effective_start: "2024-01-02",
      effective_end: "2025-01-01",
      reference_observations: 252,
      daily_return_observations: 251,
      daily_complete_case_observations: 251,
      weekly_return_observations: 156,
      weekly_complete_case_observations: 156,
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

function covariancePayload(featureCount) {
  return {
    primary_method: "ledoit_wolf",
    annualization: 252,
    ledoit_wolf_shrinkage: 0.18,
    estimators: {
      ledoit_wolf: {
        method: "ledoit_wolf",
        observations: 251,
        features: featureCount,
        annualization: 252,
        shrinkage: 0.18,
        diagnostics: {
          observations: 251,
          features: featureCount,
          symmetry_error: 0,
          tolerance: 1e-12,
          min_eigenvalue: 0.01,
          max_eigenvalue: 0.05,
          is_psd: true,
          numerical_rank: featureCount,
          condition_number: 5,
        },
      },
    },
    estimator_dispersion: {
      pairwise_relative_frobenius: {},
      maximum_relative_frobenius: 0.12,
    },
  };
}

function clusterEvidence(symbols) {
  const midpoint = Math.max(1, Math.ceil(symbols.length / 2));
  const groups = [symbols.slice(0, midpoint), symbols.slice(midpoint)].filter((group) => group.length > 0);
  const clusterBySymbol = Object.fromEntries(groups.flatMap((group, index) => group.map((symbol) => [symbol, `C${index + 1}`])));
  const clusters = groups.map((group, index) => ({
    cluster_id: `C${index + 1}`,
    members: group,
    member_count: group.length,
    structural_correlation: group.length > 1 ? { minimum: 0.68, mean: 0.76, maximum: 0.84 } : null,
    bootstrap_stability: group.length > 1 ? 0.82 : null,
    bootstrap_stability_status: group.length > 1 ? "ok" : "not_applicable",
    complete_linkage_agreement: group.length > 1 ? true : null,
  }));
  const hierarchy = (method) => ({
    method,
    cut_distance: 0.5,
    symbols,
    merges: [],
    clusters: groups.map((group, index) => ({ cluster_id: `C${index + 1}`, members: group })),
    cluster_by_symbol: clusterBySymbol,
  });
  return {
    contract_version: "refinery-clustering-twd-2026-08-10.1",
    primary_linkage: "average",
    sensitivity_linkage: "complete",
    flat_cut_distance: 0.5,
    stability_windows_weeks: [52, 104, 156],
    bootstrap_replicates: 200,
    bootstrap_block_weeks: 4,
    status: "ok",
    reason: null,
    primary: hierarchy("average"),
    sensitivity: hierarchy("complete"),
    multi_window: {
      windows: [52, 104, 156].map((window) => ({ window_weeks: window, status: "ok", input_observations: window, observations: window })),
      pair_agreements: [],
    },
    bootstrap: {
      status: "ok",
      requested_replicates: 200,
      usable_replicates: 200,
      unusable_replicates: 0,
      block_weeks: 4,
      observations: 156,
      seed: 1234,
      pair_probabilities: [],
    },
    clusters,
    bootstrap_seed_fingerprint: "abcdef1234567890",
  };
}

function redundancyPair(symbolA, symbolB, verdict = "MEDIUM") {
  return {
    symbol_a: symbolA,
    symbol_b: symbolB,
    verdict,
    confidence: "HIGH",
    structural_correlation: verdict === "LOW" ? 0.2 : 0.76,
    medium_correlation: verdict === "LOW" ? 0.25 : 0.7,
    downside_correlation: null,
    stress_correlation: null,
    factor_implied_correlation: verdict === "LOW" ? null : 0.69,
    same_average_cluster: verdict !== "LOW",
    same_complete_cluster: verdict === "HIGH",
    available_stability_windows: 3,
    window_cocluster_agreement: verdict === "LOW" ? 0.1 : 0.8,
    bootstrap_cocluster_probability: verdict === "LOW" ? 0.2 : 0.82,
    correlation_status: {
      structural_weekly: "ok",
      medium_daily: "ok",
      downside: "unavailable_benchmark_not_supplied",
      stress: "unavailable_benchmark_not_supplied",
    },
  };
}

function smallRedundancy(symbols) {
  const pairs = [
    redundancyPair(symbols[0], symbols[1], "HIGH"),
    redundancyPair(symbols[0], symbols[2], "MEDIUM"),
    redundancyPair(symbols[1], symbols[2], "LOW"),
  ];
  return {
    status: "ok",
    verdict_semantics: "historical_exposure_redundancy_evidence_only",
    magic_numeric_score: false,
    counts: { HIGH: 1, MEDIUM: 1, LOW: 1, UNCERTAIN: 0 },
    pairs,
  };
}

function largeRedundancy(symbols) {
  const pairs = [];
  for (let row = 0; row < symbols.length; row += 1) {
    for (let column = row + 1; column < symbols.length; column += 1) {
      pairs.push(redundancyPair(symbols[row], symbols[column], "LOW"));
    }
  }
  return {
    status: "ok",
    verdict_semantics: "historical_exposure_redundancy_evidence_only",
    magic_numeric_score: false,
    counts: { HIGH: 0, MEDIUM: 0, LOW: pairs.length, UNCERTAIN: 0 },
    pairs,
  };
}

function factorEvidence(symbols, available = true) {
  const assets = Object.fromEntries(symbols.map((symbol, index) => [symbol, available && index === 0
    ? { status: "ok", quote_currency: "USD", observations: 48, r_squared: 0.61, betas: { MKT_RF: 1.1 } }
    : { status: "unavailable_non_usd_quote_currency", quote_currency: "TWD", observations: 0, r_squared: null, betas: null }]));
  return {
    source: "Kenneth French Data Library",
    scope: "U.S.-factor co-movement diagnostic",
    return_currency: "native_quote_currency",
    minimum_monthly_observations: 36,
    status: available ? "ok" : "unavailable_no_eligible_assets",
    factor_sample: available ? { observations: 60, start: "2020-01-31", end: "2024-12-31", fingerprint_sha256: "factorfixture" } : null,
    assets,
    systematic_relationship: null,
  };
}

function analyzeResponse(symbols, { large = false } = {}) {
  const base = preflightResponse(symbols);
  const matrix = matrixFor(symbols);
  return {
    ...base,
    endpoint: "analyze",
    status: "ok",
    analysis: {
      symbols,
      covariance: covariancePayload(symbols.length),
      effective_dimensions: {
        covariance: { entropy_effective_rank: Math.min(symbols.length, 2.4), participation_ratio: Math.min(symbols.length, 2.2), positive_eigenvalues: [0.04, 0.03] },
        medium_correlation: large ? null : { entropy_effective_rank: 2.1, participation_ratio: 2, positive_eigenvalues: [1.7, 0.8, 0.5] },
      },
      portfolio: { status: "unavailable_weights_not_supplied", weights: null },
      correlations: {
        tactical_daily: large ? correlationView(symbols, [], "unavailable_large_fixture") : correlationView(symbols, matrix),
        medium_daily: large ? correlationView(symbols, [], "unavailable_large_fixture") : correlationView(symbols, matrix),
        structural_weekly: large ? correlationView(symbols, [], "unavailable_large_fixture") : correlationView(symbols, matrix),
        downside: correlationView(symbols, [], "unavailable_benchmark_not_supplied"),
        stress: correlationView(symbols, [], "unavailable_benchmark_not_supplied"),
      },
      clustering: clusterEvidence(symbols),
      redundancy: large ? largeRedundancy(symbols) : smallRedundancy(symbols),
      factor_relationships: factorEvidence(symbols, !large),
      theme_relationships: {
        status: "unavailable_no_traceable_theme_source",
        source: null,
        taxonomy_version: null,
        relationships: null,
      },
    },
  };
}

async function mockPortfolioHealth(page) {
  await page.route("**/api/v3/portfolio/health", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) });
  });
}

async function openRefinery(page, symbols) {
  await mockPortfolioHealth(page);
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: /持股精煉診斷/ }).click();
  for (let index = 0; index < symbols.length; index += 1) {
    if (index >= 2) await page.getByRole("button", { name: "＋ 新增持股" }).click();
    await page.getByLabel(`Refinery 持股 ${index + 1} 代碼`, { exact: true }).fill(symbols[index]);
  }
}

async function installRefineryModel(page, symbols) {
  await page.addInitScript(({ refineryKey, activeKey, symbols }) => {
    const model = {
      schemaVersion: 1,
      symbols: symbols.map((symbol, index) => ({ id: `phase5-${index}`, symbol, weightPercent: null })),
      benchmark: "",
      startDate: "2024-01-01",
      endDate: "2025-01-01",
      useWeights: false,
      ewmaDecay: 0.94,
      stressQuantile: 0.1,
    };
    localStorage.setItem(refineryKey, JSON.stringify(model));
    localStorage.setItem(activeKey, "refinery");
  }, { refineryKey: REFINERY_KEY, activeKey: ACTIVE_WORKSPACE_KEY, symbols });
}

test("Phase 5 renders clustering, redundancy, factor scope and explicit unavailable theme evidence", async ({ page }) => {
  const symbols = ["AAPL", "MSFT", "2330.TW"];
  await page.route("**/api/v1/refinery/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = path.endsWith("/preflight") ? preflightResponse(symbols) : analyzeResponse(symbols);
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await openRefinery(page, symbols);
  await page.getByRole("button", { name: "資料預檢" }).click();
  await page.getByRole("button", { name: "執行風險診斷" }).click();

  await expect(page.getByRole("heading", { name: "群聚結構" })).toBeVisible();
  await expect(page.getByText("average", { exact: true })).toBeVisible();
  await expect(page.getByText("complete", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "群聚群組摘要" })).toBeVisible();
  await expect(page.getByText("52W · ok · 52 obs", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "重複曝險證據" })).toBeVisible();
  await expect(page.getByRole("region", { name: "重複曝險 pair evidence" })).toBeVisible();
  await expect(page.getByText("HIGH", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("MEDIUM", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("LOW", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "因子關係" })).toBeVisible();
  await expect(page.getByText("unavailable_non_usd_quote_currency", { exact: true })).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "主題關係" })).toBeVisible();
  await expect(page.getByText(/unavailable_no_traceable_theme_source/)).toBeVisible();
  await expect(page.getByRole("button", { name: /KEEP|TRIM|REPLACE/ })).toHaveCount(0);
});

test("Phase 5 limits a 100-candidate pair table DOM and remains page-width safe at 390px", async ({ page }) => {
  const symbols = Array.from({ length: 100 }, (_, index) => `T${String(index + 1).padStart(3, "0")}`);
  await installRefineryModel(page, symbols);
  await mockPortfolioHealth(page);
  await page.route("**/api/v1/refinery/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = path.endsWith("/preflight") ? preflightResponse(symbols) : analyzeResponse(symbols, { large: true });
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/portfolio/");
  await expect(page.getByRole("heading", { name: "持股精煉診斷" })).toBeVisible();
  await page.getByRole("button", { name: "資料預檢" }).click();
  await page.getByRole("button", { name: "執行風險診斷" }).click();

  const pairRegion = page.getByRole("region", { name: "重複曝險 pair evidence" });
  await expect(pairRegion).toBeVisible();
  await expect(pairRegion.locator("tbody tr")).toHaveCount(80);
  await expect(page.getByText(/API 保留 4950 組完整證據/)).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
