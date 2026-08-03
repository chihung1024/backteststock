import assert from "node:assert/strict";
import test from "node:test";

import worker from "../worker/router.js";


test("retired training and out-of-sample optimizer routes fail closed", async () => {
  const originalFetch = globalThis.fetch;
  let forwarded = false;
  globalThis.fetch = async (_url, options) => {
    forwarded = Boolean(options.body);
    return Response.json({ results: [], metadata: {} });
  };

  try {
    const response = await worker.fetch(
      new Request("https://example.com/api/optimizer/verify", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ snapshot: { data: "legacy" } }),
      }),
      { BACKEND_ORIGIN: "https://backend.example.com" },
    );
    assert.equal(response.status, 404);
    assert.equal(forwarded, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("ordinary API routes still reject payloads above 256 KiB", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/backtest", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ value: "x".repeat(300 * 1024) }),
    }),
    { BACKEND_ORIGIN: "https://backend.example.com" },
  );
  assert.equal(response.status, 413);
});


test("retired optimizer routes reject oversized requests without a backend call", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/optimizer/verify", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ value: "x".repeat(3 * 1024 * 1024 + 1024) }),
    }),
    { BACKEND_ORIGIN: "https://backend.example.com" },
  );
  assert.equal(response.status, 404);
});


test("portfolio lab backtests proxy to the original full API contract", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url: String(url), options });
    return Response.json({ request_id: "test", results: [] }, {
      headers: { "server-timing": "compute;dur=12.5", server: "upstream" },
    });
  };

  try {
    const payload = {
      portfolios: [{ name: "P1", assets: [{ symbol: "VT", weight: 100 }] }],
      start_date: "2020-01-01",
      end_date: "2026-01-01",
      initial_amount: 1000000,
      base_currency: "TWD",
    };
    const response = await worker.fetch(
      new Request("https://backtest.example/api/portfolio-lab/backtests", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          cookie: "private=yes",
          authorization: "Bearer private",
          "cf-connecting-ip": "203.0.113.10",
        },
        body: JSON.stringify(payload),
      }),
      { PORTFOLIO_LAB_API_ORIGIN: "https://portfolio.example" },
    );

    assert.equal(response.status, 200);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "https://portfolio.example/api/v1/backtests");
    assert.equal(calls[0].options.method, "POST");
    assert.equal(calls[0].options.headers.get("origin"), "https://chihung1024.github.io");
    assert.equal(calls[0].options.headers.get("referer"), "https://chihung1024.github.io/backtest/");
    assert.equal(calls[0].options.headers.get("x-forwarded-for"), "203.0.113.10");
    assert.equal(calls[0].options.headers.has("cookie"), false);
    assert.equal(calls[0].options.headers.has("authorization"), false);
    assert.deepEqual(JSON.parse(new TextDecoder().decode(calls[0].options.body)), payload);
    assert.equal(response.headers.get("x-backend-server-timing"), "compute;dur=12.5");
    assert.equal(response.headers.has("server"), false);
    assert.equal(response.headers.get("cache-control"), "no-store");
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("portfolio lab search preserves query parameters", async () => {
  const originalFetch = globalThis.fetch;
  let target = "";
  globalThis.fetch = async (url) => {
    target = String(url);
    return Response.json([{ symbol: "2330.TW" }]);
  };

  try {
    const response = await worker.fetch(
      new Request("https://backtest.example/api/portfolio-lab/assets/search?q=2330&limit=8"),
      { PORTFOLIO_LAB_API_ORIGIN: "https://portfolio.example" },
    );
    assert.equal(response.status, 200);
    assert.equal(target, "https://portfolio.example/api/v1/assets/search?q=2330&limit=8");
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("portfolio lab proxy rejects unknown routes, wrong methods, and oversized bodies", async () => {
  const unknown = await worker.fetch(
    new Request("https://backtest.example/api/portfolio-lab/unknown"),
    {},
  );
  assert.equal(unknown.status, 404);

  const wrongMethod = await worker.fetch(
    new Request("https://backtest.example/api/portfolio-lab/backtests"),
    {},
  );
  assert.equal(wrongMethod.status, 405);

  const oversized = await worker.fetch(
    new Request("https://backtest.example/api/portfolio-lab/backtests", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ value: "x".repeat(520 * 1024) }),
    }),
    {},
  );
  assert.equal(oversized.status, 413);
});
