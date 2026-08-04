const originArgument = process.argv[2];

if (!originArgument) {
  throw new Error("Usage: node scripts/smoke_test_portfolio_v3.mjs <worker-origin>");
}

const origin = new URL(originArgument).origin;
const timeoutMs = 240_000;

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function fetchJson(path, options = {}, attempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(new URL(path, origin), {
        ...options,
        headers: {
          accept: "application/json",
          ...(options.body ? { "content-type": "application/json" } : {}),
          ...(options.headers || {}),
        },
        signal: controller.signal,
      });
      const text = await response.text();
      const payload = text ? JSON.parse(text) : null;
      if (!response.ok) {
        throw new Error(`${path} returned ${response.status}: ${text.slice(0, 1000)}`);
      }
      return payload;
    } catch (error) {
      lastError = error;
      if (attempt < attempts) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 2_000));
      }
    } finally {
      clearTimeout(timeout);
    }
  }
  throw lastError;
}

const health = await fetchJson("/api/v3/portfolio/health");
assert(health?.status === "ok", "Portfolio v3 health is not ok");
assert(health?.service === "backteststock-portfolio-v3", "Unexpected Portfolio service");
assert(health?.contract_version === "portfolio-v3", "Unexpected Portfolio contract");
assert(health?.schema_version, "Portfolio schema version is missing");

const search = await fetchJson("/api/v3/portfolio/assets/search?q=2330&limit=5");
assert(
  Array.isArray(search) && search.some((item) => item?.symbol === "2330.TW"),
  "Asset search did not resolve 2330.TW",
);

const request = {
  contract_version: "portfolio-v3",
  portfolios: [
    {
      name: "Production mixed-market smoke",
      assets: [
        { symbol: "SPY", weight: 60 },
        { symbol: "2330.TW", weight: 40 },
      ],
    },
  ],
  benchmark: "SPY",
  start_date: "2025-01-02",
  end_date: "2025-03-31",
  initial_amount: 100000,
  base_currency: "TWD",
  include_ytd: true,
  reinvest_distributions: false,
  transaction_cost_bps: 5,
  cashflow: {
    type: "fixed",
    amount: 1000,
    frequency: "monthly",
    timing: "end",
    annual_growth_rate_percent: 0,
  },
  rebalancing: {
    frequency: "monthly",
    threshold_percent: null,
  },
  leverage: {
    type: "fixed_ratio",
    ratio: 1.2,
    debt_amount: 0,
    annual_interest_rate_percent: 2,
    maintenance_margin_percent: 25,
  },
  analytics: {
    factor_analysis: false,
    style_analysis: false,
    regime: "none",
    inflation_adjusted: false,
    risk_free_rate_percent: 0,
  },
  output_frequency: "daily",
  include_events: true,
  include_allocation_history: true,
};

const preflight = await fetchJson("/api/v3/portfolio/preflight", {
  method: "POST",
  body: JSON.stringify(request),
});
assert(preflight?.base_currency === "TWD", "Preflight base currency is not TWD");
assert(preflight?.contract_version === "portfolio-v3", "Preflight contract mismatch");
assert(
  Array.isArray(preflight?.portfolios) && preflight.portfolios[0]?.status === "ready",
  "Mixed-market portfolio is not ready",
);
assert(
  Array.isArray(preflight?.assets) && preflight.assets.length >= 2,
  "Preflight asset audit is incomplete",
);
assert(
  preflight.assets.every((asset) => asset?.status === "ready"),
  "One or more mixed-market assets failed preflight",
);

const result = await fetchJson("/api/v3/portfolio/backtests", {
  method: "POST",
  body: JSON.stringify(request),
});
assert(result?.base_currency === "TWD", "Backtest base currency is not TWD");
assert(result?.contract_version === "portfolio-v3", "Backtest contract mismatch");
assert(
  Array.isArray(result?.results) && result.results.length === 1,
  "Expected one successful Portfolio result",
);
assert(
  Array.isArray(result?.failures) && result.failures.length === 0,
  "Portfolio v3 smoke returned failures",
);

const portfolio = result.results[0];
assert(
  portfolio?.metrics && Number.isFinite(Number(portfolio.metrics.cagr)),
  "CAGR is missing",
);
assert(
  Number.isFinite(Number(portfolio.metrics.final_balance))
    && Number(portfolio.metrics.final_balance) > 0,
  "Final balance is missing or invalid",
);
assert(
  Number.isFinite(Number(portfolio.metrics.max_drawdown)),
  "Maximum drawdown is missing",
);
assert(
  Array.isArray(portfolio?.series) && portfolio.series.length >= 40,
  "Portfolio series is unexpectedly short",
);
assert(
  Array.isArray(portfolio?.events) && portfolio.events.length > 0,
  "Portfolio ledger events are missing",
);
assert(
  Array.isArray(portfolio?.allocation_history) && portfolio.allocation_history.length > 0,
  "Portfolio allocation history is missing",
);
assert(
  portfolio?.metadata?.metric_context_version,
  "Portfolio metric context metadata is missing",
);
assert(result?.reproducibility?.api_schema_version, "API reproducibility metadata is missing");
assert(result?.reproducibility?.ledger_contract_version, "Ledger contract metadata is missing");
assert(result?.reproducibility?.twd_valuation_contract_version, "TWD valuation metadata is missing");

console.log(JSON.stringify({
  origin,
  service: health.service,
  schemaVersion: health.schema_version,
  requestId: result.request_id,
  effectiveEnd: result.effective_end,
  observations: portfolio.series.length,
  finalValue: portfolio.series.at(-1)?.value,
  cagr: portfolio.metrics.cagr,
  maxDrawdown: portfolio.metrics.max_drawdown,
  eventCount: portfolio.events.length,
  allocationObservations: portfolio.allocation_history.length,
}, null, 2));
