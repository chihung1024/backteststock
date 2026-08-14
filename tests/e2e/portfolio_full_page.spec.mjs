import { expect, test } from "@playwright/test";

function preflightPayload() {
  return {
    request_id: "preflight-12345678",
    generated_at: "2026-08-04T00:00:00Z",
    contract_version: "portfolio-v3",
    schema_version: "portfolio-v3-2026-08-04.1",
    base_currency: "TWD",
    requested_start: "2016-08-04",
    requested_end: "2026-08-04",
    effective_end: "2026-08-04",
    assets: [
      {
        symbol: "SPY",
        status: "ready",
        retryable: false,
        quote_currency: "USD",
        effective_start: "2016-08-04",
        effective_end: "2026-08-03",
        observations: 2515,
        corporate_action_audit: { status: "verified_standard_actions" },
        fx_audit: { method: "direct", source_currency: "USD", target_currency: "TWD" },
        return_component_audit: { contract_version: "twd-return-components-2026-08-04.1" },
        fingerprints: { adjusted_close_twd: "abc1234567890portfolio" },
      },
      {
        symbol: "2330.TW",
        status: "ready",
        retryable: false,
        quote_currency: "TWD",
        effective_start: "2016-08-04",
        effective_end: "2026-08-03",
        observations: 2440,
        corporate_action_audit: { status: "verified_standard_actions" },
        fx_audit: { method: "identity", source_currency: "TWD", target_currency: "TWD" },
        return_component_audit: { contract_version: "twd-return-components-2026-08-04.1" },
        fingerprints: { adjusted_close_twd: "def1234567890portfolio" },
      },
      {
        symbol: "VT",
        status: "ready",
        retryable: false,
        quote_currency: "USD",
        effective_start: "2016-08-04",
        effective_end: "2026-08-03",
        observations: 2515,
        corporate_action_audit: { status: "verified_standard_actions" },
        fx_audit: { method: "direct", source_currency: "USD", target_currency: "TWD" },
        return_component_audit: { contract_version: "twd-return-components-2026-08-04.1" },
        fingerprints: { adjusted_close_twd: "ghi1234567890portfolio" },
      },
    ],
    portfolios: [
      { name: "全球核心", status: "ready", symbols: ["SPY", "2330.TW", "VT"], missing_symbols: [], effective_start: "2016-08-04", effective_end: "2026-08-03", observations: 2440 },
      { name: "全球股票", status: "ready", symbols: ["VT"], missing_symbols: [], effective_start: "2016-08-04", effective_end: "2026-08-03", observations: 2515 },
    ],
    benchmark: {
      symbol: "SPY",
      status: "ready",
      retryable: false,
      quote_currency: "USD",
      effective_start: "2016-08-04",
      effective_end: "2026-08-03",
      observations: 2515,
      fingerprints: { adjusted_close_twd: "abc1234567890portfolio" },
    },
    analysis_dependencies: [],
    warnings: [],
  };
}

function resultItem(name, multiplier = 1) {
  const dates = ["2024-01-02", "2024-06-28", "2024-12-31", "2025-06-30", "2025-12-31"];
  const values = [1_000_000, 1_080_000, 1_150_000, 1_210_000, 1_330_000].map((value) => value * multiplier);
  const series = dates.map((date, index) => ({
    date,
    value: values[index],
    return_index: [1, 1.08, 1.15, 1.21, 1.33][index],
    daily_return: index ? 0.01 : 0,
    external_flow: 0,
    income: index ? 5000 * multiplier : 0,
    cumulative_income: index * 5000 * multiplier,
    cash: 0,
    debt: 0,
    gross_exposure: values[index],
  }));
  return {
    name,
    display_name: `${name} · SPY 50% · 2330.TW 30% · VT 20%`,
    metrics: {
      initial_balance: 1_000_000,
      final_balance: values.at(-1),
      contributions: 0,
      withdrawals: 0,
      net_contributions: 0,
      net_profit: values.at(-1) - 1_000_000,
      total_return: 0.33,
      cagr: 0.153,
      money_weighted_return: 0.153,
      xirr_status: "unique",
      volatility: 0.18,
      sharpe_ratio: 0.92,
      sortino_ratio: 1.31,
      max_drawdown: -0.14,
      calmar_ratio: 1.09,
      var_95_daily: -0.021,
      cvar_95_daily: -0.031,
      beta: 0.91,
      alpha: 0.024,
      benchmark_correlation: 0.88,
      transaction_costs: 1200,
      borrowing_costs: 0,
      total_income: 20_000,
      rebalance_count: 2,
      observations: 500,
    },
    xirr: { status: "unique", value: 0.153, roots: [0.153], method: "log-rate-grid-plus-bisection" },
    tail_risk: { method: "historical_simulation", horizon: "daily", confidence: 0.95, var: -0.021, cvar: -0.031, observations: 499 },
    drawdown_events: [{ peak: "2024-07-15", trough: "2024-08-05", recovery: "2024-09-10", depth: -0.14, duration_days: 57, recovered: true }],
    annual_returns: [
      { period: "2024", start: "2024-01-02", end: "2024-12-31", return_value: 0.15, partial: false },
      { period: "2025", start: "2025-01-02", end: "2025-12-31", return_value: 0.1565, partial: false },
    ],
    monthly_returns: [
      { period: "2024-01", start: "2024-01-02", end: "2024-01-31", return_value: 0.02, partial: true },
      { period: "2024-02", start: "2024-02-01", end: "2024-02-29", return_value: -0.015, partial: false },
      { period: "2024-03", start: "2024-03-01", end: "2024-03-28", return_value: 0.04, partial: false },
    ],
    target_allocation: { SPY: 0.5, "2330.TW": 0.3, VT: 0.2 },
    final_allocation: { SPY: 0.53, "2330.TW": 0.28, VT: 0.19 },
    series,
    analytics: {
      factor: { regression_currency: "TWD", factor_betas: { MKT_RF: 0.9 }, fx_betas: { FX_USD_TWD: 0.32 }, r_squared: 0.84 },
      style: { constraint: "weights >= 0 and sum(weights) = 1", exposures: { large_growth: 0.6, large_value: 0.4 } },
    },
    warnings: [],
    metadata: { metric_context_version: "portfolio-metrics-twd-2026-08-04.1" },
    events: [],
  };
}

function backtestPayload() {
  return {
    request_id: "backtest-12345678",
    generated_at: "2026-08-04T00:00:00Z",
    contract_version: "portfolio-v3",
    schema_version: "portfolio-v3-2026-08-04.1",
    base_currency: "TWD",
    requested_start: "2016-08-04",
    requested_end: "2026-08-04",
    effective_end: "2026-08-03",
    results: [resultItem("全球核心"), resultItem("全球股票", 0.93)],
    failures: [],
    assets: preflightPayload().assets,
    benchmark: resultItem("Benchmark · SPY", 0.88),
    warnings: [],
    timing: { market_ms: 210.4, compute_ms: 34.2, total_ms: 246.1 },
    reproducibility: {
      api_schema_version: "portfolio-v3-2026-08-04.1",
      ledger_contract_version: "portfolio-ledger-twd-2026-08-04.1",
      twd_valuation_contract_version: "twd-adjusted-close-union-calendar-2026-08-03.2",
    },
  };
}

async function mockPortfolioApi(page) {
  await page.route("**/api/v3/portfolio/health", (route) => route.fulfill({ json: { status: "ok", service: "backteststock-portfolio-v3" } }));
  await page.route("**/api/v3/portfolio/preflight", (route) => route.fulfill({ json: preflightPayload() }));
  await page.route("**/api/v3/portfolio/backtests", (route) => route.fulfill({ json: backtestPayload() }));
  await page.route("**/api/v3/portfolio/assets/search**", (route) => route.fulfill({ json: [{ symbol: "SPY", name: "SPDR S&P 500 ETF Trust", exchange: "NYSE Arca", currency: "USD" }] }));
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async (value) => { window.__portfolioCopiedText = value; } },
    });
  });
}

test("Portfolio Research is a direct full page and completes the v3 workflow", async ({ page }) => {
  await mockPortfolioApi(page);
  await page.goto("/portfolio/");

  await expect(page).toHaveTitle(/Portfolio Research/);
  await expect(page.locator("main#portfolio-main")).toBeVisible();
  await expect(page.getByRole("heading", { name: "投資組合研究工作區" })).toBeVisible();
  await expect(page.locator("dialog")).toHaveCount(0);
  await expect(page.locator("iframe")).toHaveCount(0);

  await page.getByRole("button", { name: "載入範例" }).click();
  await expect(page.locator(".desktop-matrix")).toBeVisible();
  await expect(page.getByText("全球核心").first()).toBeVisible();
  await expect(page.getByText("設定可執行")).toBeVisible();

  await page.getByRole("button", { name: "資料預檢" }).click();
  await expect(page.getByRole("heading", { name: "資料預檢" })).toBeVisible();
  await expect(page.getByText("2/2 投組可執行")).toBeVisible();

  await page.getByRole("button", { name: "執行回測" }).click();
  await expect(page.getByRole("heading", { name: "回測結果" })).toBeVisible();
  await expect(page.getByText("CAGR").first()).toBeVisible();
  await expect(page.getByText("15.3%").first()).toBeVisible();

  await page.getByRole("tab", { name: "資產成長" }).click();
  await expect(page.locator(".chart-frame svg").first()).toBeVisible();
  await page.getByRole("tab", { name: "月報酬" }).click();
  await expect(page.getByRole("region", { name: "月報酬熱圖" })).toBeVisible();
  await page.getByRole("tab", { name: "資料稽核" }).click();
  await expect(page.getByRole("region", { name: "資產資料稽核" }).first()).toBeVisible();
  await expect(page.getByText("twd_valuation_contract_version")).toBeVisible();

  await page.getByRole("button", { name: "儲存" }).click();
  const saved = await page.evaluate(() => localStorage.getItem("backteststock.portfolio.model.v1"));
  expect(saved).toContain("全球核心");

  await page.getByRole("button", { name: "分享" }).click();
  const copied = await page.evaluate(() => window.__portfolioCopiedText);
  expect(copied).toContain("/portfolio/?model=");
  await expect(page).toHaveURL(/\/portfolio\/\?model=/);
});

test("Portfolio workspace enforces five portfolios and twenty global asset rows", async ({ page }) => {
  await mockPortfolioApi(page);
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: "載入範例" }).click();

  const addPortfolio = page.getByRole("button", { name: "新增投組" });
  await addPortfolio.click();
  await addPortfolio.click();
  await addPortfolio.click();
  await expect(addPortfolio).toBeDisabled();
  await expect(page.locator(".allocation-matrix thead .portfolio-name-input")).toHaveCount(5);

  const addAsset = page.getByRole("button", { name: "新增資產" }).first();
  for (let index = 0; index < 17; index += 1) await addAsset.click();
  await expect(addAsset).toBeDisabled();
  await expect(page.locator(".allocation-matrix tbody tr")).toHaveCount(20);
});

test("390px mobile uses the focused portfolio editor and safe full-width actions", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockPortfolioApi(page);
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: "載入範例" }).click();

  await expect(page.locator(".desktop-matrix")).toBeHidden();
  await expect(page.locator(".mobile-allocation")).toBeVisible();
  await expect(page.getByLabel("目前編輯投組")).toBeVisible();
  await expect(page.locator(".run-bar")).toBeVisible();
  await expect(page.getByRole("button", { name: "資料預檢" })).toBeVisible();
  await expect(page.getByRole("button", { name: "執行回測" })).toBeVisible();

  await page.getByRole("button", { name: "資料預檢" }).click();
  await expect(page.getByText("2/2 投組可執行")).toBeVisible();
});

test("asset autocomplete ignores late responses from older queries", async ({ page }) => {
  let releaseA;
  let releaseAP;
  const firstQueryGate = new Promise((resolve) => { releaseA = resolve; });
  const secondQueryGate = new Promise((resolve) => { releaseAP = resolve; });
  let aStarted;
  let apStarted;
  const firstQueryStarted = new Promise((resolve) => { aStarted = resolve; });
  const secondQueryStarted = new Promise((resolve) => { apStarted = resolve; });

  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const requestInit = init ? { ...init } : undefined;
      if (requestInit) delete requestInit.signal;
      return originalFetch(input, requestInit);
    };
  });
  await page.route("**/api/v3/portfolio/health", (route) => route.fulfill({ json: { status: "ok", service: "backteststock-portfolio-v3" } }));
  await page.route("**/api/v3/portfolio/assets/search**", async (route) => {
    const query = new URL(route.request().url()).searchParams.get("q");
    if (query === "A") {
      aStarted();
      await firstQueryGate;
      try {
        await route.fulfill({ json: [{ symbol: "AAPL", name: "Apple Inc.", exchange: "NASDAQ", currency: "USD" }] });
      } catch {
        // The page may close the route after the assertion; the UI guard is the subject of this test.
      }
      return;
    }
    if (query === "AP") {
      apStarted();
      await secondQueryGate;
      await route.fulfill({ json: [{ symbol: "AP ETF", name: "AP result", exchange: "TEST", currency: "USD" }] });
      return;
    }
    await route.fulfill({ json: [] });
  });
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: "載入範例" }).click();

  const ticker = page.locator(".desktop-matrix input[id^=ticker-]").first();
  await ticker.fill("A");
  await firstQueryStarted;
  await ticker.fill("AP");
  await secondQueryStarted;

  releaseA();
  const desktopSearchMenu = page.locator(".desktop-matrix .search-suggestions");
  await expect(desktopSearchMenu.getByText("搜尋中…")).toBeVisible();
  await expect(desktopSearchMenu.getByRole("option")).toHaveCount(0);

  releaseAP();
  await expect(desktopSearchMenu.getByRole("option", { name: /AP ETF/ })).toBeVisible();
  await expect(desktopSearchMenu.getByText("AAPL", { exact: true })).toHaveCount(0);
});

test("switching asset inputs keeps the newer autocomplete menu open", async ({ page }) => {
  await page.route("**/api/v3/portfolio/health", (route) => route.fulfill({ json: { status: "ok", service: "backteststock-portfolio-v3" } }));
  await page.route("**/api/v3/portfolio/assets/search**", (route) => route.fulfill({ json: [{ symbol: "AP ETF", name: "AP result", exchange: "TEST", currency: "USD" }] }));
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: "載入範例" }).click();

  await page.evaluate(() => {
    const inputs = document.querySelectorAll(".desktop-matrix input[id^=ticker-]");
    const first = inputs[0];
    const second = inputs[1];
    if (!(first instanceof HTMLInputElement) || !(second instanceof HTMLInputElement)) throw new Error("ticker inputs missing");
    first.focus();
    second.focus();
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    setter?.call(second, "AP");
    second.dispatchEvent(new Event("input", { bubbles: true }));
  });

  const desktopSearchMenu = page.locator(".desktop-matrix .search-suggestions");
  await expect(desktopSearchMenu.getByRole("option", { name: /AP ETF/ })).toBeVisible();
});

test("model changes invalidate late Portfolio evidence and replacement clears completed evidence", async ({ page }) => {
  let releaseFirstBacktest;
  const firstBacktestGate = new Promise((resolve) => {
    releaseFirstBacktest = resolve;
  });
  let backtestStarted;
  const firstBacktestStarted = new Promise((resolve) => {
    backtestStarted = resolve;
  });
  let backtestCount = 0;

  await page.route("**/api/v3/portfolio/health", (route) => route.fulfill({ json: { status: "ok", service: "backteststock-portfolio-v3" } }));
  await page.route("**/api/v3/portfolio/preflight", (route) => route.fulfill({ json: preflightPayload() }));
  await page.route("**/api/v3/portfolio/backtests", async (route) => {
    backtestCount += 1;
    if (backtestCount === 1) {
      backtestStarted();
      await firstBacktestGate;
    }
    try {
      await route.fulfill({ json: backtestPayload() });
    } catch {
      // The first request is expected to be aborted after the model changes.
    }
  });
  await page.route("**/api/v3/portfolio/assets/search**", (route) => route.fulfill({ json: [] }));
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: "載入範例" }).click();

  await page.getByRole("button", { name: "執行回測" }).click();
  await firstBacktestStarted;
  await page.locator(".desktop-matrix input[type=number]").first().fill("60");
  await expect(page.getByRole("heading", { name: "回測結果" })).toHaveCount(0);

  releaseFirstBacktest();
  await expect(page.getByRole("heading", { name: "回測結果" })).toHaveCount(0);

  await page.getByRole("button", { name: "載入範例" }).click();
  await page.getByRole("button", { name: "執行回測" }).click();
  await expect(page.getByRole("heading", { name: "回測結果" })).toBeVisible();

  await page.getByRole("button", { name: "載入範例" }).click();
  await expect(page.getByRole("heading", { name: "回測結果" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "資料預檢" })).toHaveCount(0);
});

test("late Portfolio cleanup cannot clear busy state for a newer backtest", async ({ page }) => {
  let releaseFirstBacktest;
  let releaseSecondBacktest;
  const firstBacktestGate = new Promise((resolve) => { releaseFirstBacktest = resolve; });
  const secondBacktestGate = new Promise((resolve) => { releaseSecondBacktest = resolve; });
  let firstBacktestStarted;
  let secondBacktestStarted;
  const firstBacktestStartedPromise = new Promise((resolve) => { firstBacktestStarted = resolve; });
  const secondBacktestStartedPromise = new Promise((resolve) => { secondBacktestStarted = resolve; });
  let backtestCount = 0;

  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const requestInit = init ? { ...init } : undefined;
      if (requestInit) delete requestInit.signal;
      return originalFetch(input, requestInit);
    };
  });
  await page.route("**/api/v3/portfolio/health", (route) => route.fulfill({ json: { status: "ok", service: "backteststock-portfolio-v3" } }));
  await page.route("**/api/v3/portfolio/preflight", (route) => route.fulfill({ json: preflightPayload() }));
  await page.route("**/api/v3/portfolio/backtests", async (route) => {
    backtestCount += 1;
    if (backtestCount === 1) {
      firstBacktestStarted();
      await firstBacktestGate;
    } else if (backtestCount === 2) {
      secondBacktestStarted();
      await secondBacktestGate;
    }
    try {
      await route.fulfill({ json: backtestPayload() });
    } catch {
      // A released request may already have been superseded by the next model run.
    }
  });
  await page.route("**/api/v3/portfolio/assets/search**", (route) => route.fulfill({ json: [] }));
  await page.goto("/portfolio/");
  await page.getByRole("button", { name: "載入範例" }).click();

  await page.getByRole("button", { name: "執行回測" }).click();
  await firstBacktestStartedPromise;
  const weights = page.locator(".desktop-matrix input[type=number]");
  await weights.nth(0).fill("60");
  await weights.nth(2).fill("20");
  await expect(page.getByRole("button", { name: "執行回測" })).toBeEnabled();

  await page.getByRole("button", { name: "執行回測" }).click();
  await secondBacktestStartedPromise;
  releaseFirstBacktest();

  await expect(page.getByRole("button", { name: "回測中…" })).toBeVisible();
  await expect(page.getByRole("button", { name: "取消" })).toBeVisible();

  releaseSecondBacktest();
  await expect(page.getByRole("heading", { name: "回測結果" })).toBeVisible();
});
