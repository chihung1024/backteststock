import assert from "node:assert/strict";
import test from "node:test";

import router from "../worker/router.js";

function request(body = { portfolios: [{ name: "P", tickers: ["SPY"], weights: [100] }] }) {
  return new Request("https://example.com/api/backtest", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

test("legacy backtest bypasses edge cache even for HTTP 200 responses", async () => {
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  let cacheMatches = 0;
  let cachePuts = 0;
  const cache = {
    async match() {
      cacheMatches += 1;
      return null;
    },
    async put() {
      cachePuts += 1;
    },
  };
  globalThis.fetch = async () => {
    backendCalls += 1;
    return Response.json({
      data: [],
      benchmark: null,
      failures: [{ name: "P", stage: "market_data", detail: "temporary" }],
      metadata: {},
    });
  };

  try {
    const env = { BACKEND_ORIGIN: "https://backend.example", API_CACHE: cache };
    const first = await router.fetch(request(), env, {});
    const second = await router.fetch(request(), env, {});
    assert.equal(first.status, 200);
    assert.equal(second.status, 200);
    assert.equal(first.headers.get("x-edge-cache"), null);
    assert.equal(second.headers.get("x-edge-cache"), null);
    assert.equal(backendCalls, 2);
    assert.equal(cacheMatches, 0);
    assert.equal(cachePuts, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("legacy backtest keeps the existing 256 KiB request limit", async () => {
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  globalThis.fetch = async () => {
    backendCalls += 1;
    return Response.json({ ok: true });
  };

  try {
    const response = await router.fetch(
      new Request("https://example.com/api/backtest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ padding: "x".repeat(256 * 1024) }),
      }),
      { BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    assert.equal(response.status, 413);
    assert.equal(backendCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("legacy backtest remains POST-only", async () => {
  const response = await router.fetch(
    new Request("https://example.com/api/backtest"),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(response.status, 405);
});
