import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { once } from "node:events";
import test from "node:test";

const expectedSha = "1234567890abcdef1234567890abcdef12345678";
const staleSha = "abcdef1234567890abcdef1234567890abcdef12";

function json(response, payload, statusCode = 200) {
  response.writeHead(statusCode, { "content-type": "application/json" });
  response.end(JSON.stringify(payload));
}

function backtestPayload() {
  const series = Array.from({ length: 40 }, (_, index) => ({
    date: `2025-02-${String((index % 28) + 1).padStart(2, "0")}`,
    value: 100000 + index * 100,
  }));
  return {
    contract_version: "portfolio-v3",
    base_currency: "TWD",
    request_id: "readiness-test",
    effective_end: "2025-03-31",
    failures: [],
    results: [{
      metrics: {
        cagr: 0.12,
        final_balance: 103900,
        max_drawdown: -0.08,
      },
      series,
      events: [{ date: "2025-01-31", event_type: "cashflow" }],
      allocation_history: [{
        date: "2025-01-02",
        allocations: { SPY: 0.6, "2330.TW": 0.4 },
      }],
      metadata: { metric_context_version: "portfolio-metrics-test" },
    }],
    reproducibility: {
      api_schema_version: "portfolio-v3-test",
      ledger_contract_version: "portfolio-ledger-test",
      twd_valuation_contract_version: "twd-valuation-test",
    },
  };
}

async function runSmoke(origin) {
  const child = spawn(
    process.execPath,
    ["scripts/smoke_test_portfolio_v3.mjs", origin],
    {
      cwd: process.cwd(),
      env: {
        ...process.env,
        EXPECTED_DEPLOYMENT_SHA: expectedSha,
        PORTFOLIO_READINESS_POLL_MS: "10",
        PORTFOLIO_READINESS_TIMEOUT_MS: "2000",
        PORTFOLIO_REQUEST_TIMEOUT_MS: "1000",
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk) => { stdout += chunk; });
  child.stderr.on("data", (chunk) => { stderr += chunk; });
  const [exitCode] = await once(child, "exit");
  return { exitCode, stdout, stderr };
}

test("Portfolio smoke waits through HTML and stale SHA before testing the matching deployment", async () => {
  let healthRequests = 0;
  let searchRequests = 0;
  let preflightRequests = 0;
  let backtestRequests = 0;

  const server = createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    if (url.pathname === "/api/v3/portfolio/health") {
      healthRequests += 1;
      if (healthRequests === 1) {
        response.writeHead(200, { "content-type": "text/html" });
        response.end("<!doctype html><title>old deployment</title>");
        return;
      }
      json(response, {
        status: "ok",
        service: "backteststock-portfolio-v3",
        contract_version: "portfolio-v3",
        schema_version: "portfolio-v3-test",
        deployment_sha: healthRequests === 2 ? staleSha : expectedSha,
      });
      return;
    }
    if (url.pathname === "/api/v3/portfolio/assets/search") {
      searchRequests += 1;
      json(response, [{ symbol: "2330.TW" }]);
      return;
    }
    if (url.pathname === "/api/v3/portfolio/preflight") {
      preflightRequests += 1;
      json(response, {
        contract_version: "portfolio-v3",
        base_currency: "TWD",
        portfolios: [{ status: "ready" }],
        assets: [{ status: "ready" }, { status: "ready" }],
      });
      return;
    }
    if (url.pathname === "/api/v3/portfolio/backtests") {
      backtestRequests += 1;
      json(response, backtestPayload());
      return;
    }
    json(response, { detail: "not found" }, 404);
  });

  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  assert(address && typeof address === "object");

  try {
    const result = await runSmoke(`http://127.0.0.1:${address.port}`);
    assert.equal(result.exitCode, 0, result.stderr || result.stdout);
    assert.equal(healthRequests, 3);
    assert.equal(searchRequests, 1);
    assert.equal(preflightRequests, 1);
    assert.equal(backtestRequests, 1);
    assert.match(result.stdout, /old deployment/);
    assert.match(result.stdout, new RegExp(staleSha));
    assert.match(result.stdout, new RegExp(expectedSha));
    assert.match(result.stdout, /"deploymentSha"/);
  } finally {
    server.close();
    await once(server, "close");
  }
});
