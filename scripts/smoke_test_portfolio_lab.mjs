const originArgument = process.argv[2];

if (!originArgument) {
  throw new Error("Usage: node scripts/smoke_test_portfolio_lab.mjs <worker-origin>");
}

const origin = new URL(originArgument);
const REQUEST_TIMEOUT_MS = 240_000;

function assertCondition(condition, message) {
  if (!condition) throw new Error(message);
}

async function request(pathname, init = {}) {
  const response = await fetch(new URL(pathname, origin), {
    ...init,
    headers: {
      accept: "application/json",
      ...(init.headers || {}),
    },
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${pathname} returned HTTP ${response.status}: ${text.slice(0, 800)}`);
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${pathname} did not return valid JSON: ${text.slice(0, 800)}`);
  }
}

const health = await request("/api/portfolio-lab/health");
assertCondition(health?.status === "ok", "Portfolio Lab upstream health did not report status=ok.");

const search = await request("/api/portfolio-lab/assets/search?q=SPY&limit=5");
assertCondition(Array.isArray(search), "Portfolio Lab asset search did not return an array.");
assertCondition(
  search.some((asset) => asset?.symbol === "SPY"),
  "Portfolio Lab asset search did not return SPY.",
);

const backtest = await request("/api/portfolio-lab/backtests", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({
    portfolios: [
      {
        name: "Production smoke",
        assets: [{ symbol: "SPY", weight: 100 }],
      },
    ],
    benchmark: null,
    start_date: "2025-01-02",
    end_date: "2025-02-28",
    initial_amount: 100000,
    base_currency: "TWD",
    include_ytd: false,
    reinvest_dividends: true,
    display_income: true,
    transaction_cost_bps: 0,
    cashflow: {
      type: "none",
      amount: 0,
      frequency: "none",
      timing: "end",
      annual_growth_rate: 0,
    },
    rebalancing: {
      frequency: "none",
      threshold_percent: null,
    },
    leverage: {
      type: "none",
      ratio: 1.5,
      debt_amount: 0,
      annual_interest_rate: 0,
      maintenance_margin: 25,
    },
    analytics: {
      style_analysis: false,
      factor_regression: false,
      regime: "none",
      risk_free_rate: 0,
      inflation_adjusted: false,
    },
    output_frequency: "daily",
  }),
});

assertCondition(backtest?.base_currency === "TWD", "Portfolio Lab backtest did not use TWD valuation.");
assertCondition(Array.isArray(backtest?.results), "Portfolio Lab backtest results are missing.");
assertCondition(backtest.results.length === 1, "Portfolio Lab backtest did not return one portfolio.");
const result = backtest.results[0];
assertCondition(
  Array.isArray(result?.series) && result.series.length >= 20,
  `Portfolio Lab backtest returned only ${result?.series?.length ?? 0} observations.`,
);
assertCondition(
  Number.isFinite(Number(result?.metrics?.final_balance))
    && Number(result.metrics.final_balance) > 0,
  "Portfolio Lab backtest final balance is invalid.",
);
assertCondition(
  Number.isFinite(Number(result?.metrics?.cagr)),
  "Portfolio Lab backtest CAGR is missing.",
);
assertCondition(
  Number.isFinite(Number(result?.metrics?.max_drawdown)),
  "Portfolio Lab backtest maximum drawdown is missing.",
);

console.log(JSON.stringify({
  workerOrigin: origin.origin,
  upstreamService: health.service,
  upstreamVersion: health.version,
  searchResultCount: search.length,
  requestId: backtest.request_id,
  effectiveStart: backtest.effective_start,
  effectiveEnd: backtest.effective_end,
  seriesObservations: result.series.length,
  finalBalance: result.metrics.final_balance,
  cagr: result.metrics.cagr,
  maxDrawdown: result.metrics.max_drawdown,
}, null, 2));
