import assert from "node:assert/strict";
import test from "node:test";

import router from "../worker/router.js";

test("Portfolio v3 GET preserves path and query on BACKEND_ORIGIN", async () => {
  const originalFetch = globalThis.fetch;
  let forwardedUrl;
  let forwardedHeaders;
  globalThis.fetch = async (url, options) => {
    forwardedUrl = String(url);
    forwardedHeaders = new Headers(options.headers);
    return new Response(JSON.stringify([{ symbol: "SPY", name: "SPDR" }]), {
      status: 200,
      headers: {
        "content-type": "application/json",
        "server": "hidden",
        "set-cookie": "secret=1",
      },
    });
  };

  try {
    const response = await router.fetch(
      new Request("https://edge.example/api/v3/portfolio/assets/search?q=SPY&limit=5", {
        headers: {
          cookie: "browser=secret",
          authorization: "Bearer secret",
          "cf-connecting-ip": "203.0.113.10",
        },
      }),
      { BACKEND_ORIGIN: "https://backend.example/base" },
      {},
    );
    assert.equal(response.status, 200);
    assert.equal(
      forwardedUrl,
      "https://backend.example/api/v3/portfolio/assets/search?q=SPY&limit=5",
    );
    assert.equal(forwardedHeaders.get("cookie"), null);
    assert.equal(forwardedHeaders.get("authorization"), null);
    assert.equal(forwardedHeaders.get("origin"), null);
    assert.equal(forwardedHeaders.get("referer"), null);
    assert.equal(forwardedHeaders.get("x-forwarded-for"), "203.0.113.10");
    assert.equal(response.headers.get("server"), null);
    assert.equal(response.headers.get("set-cookie"), null);
    assert.ok(response.headers.get("x-request-id"));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Portfolio v3 POST forwards exact JSON without legacy origin impersonation", async () => {
  const originalFetch = globalThis.fetch;
  let forwardedBody;
  let forwardedHeaders;
  globalThis.fetch = async (_url, options) => {
    forwardedBody = JSON.parse(new TextDecoder().decode(options.body));
    forwardedHeaders = new Headers(options.headers);
    return new Response(JSON.stringify({ results: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };

  try {
    const payload = {
      contract_version: "portfolio-v3",
      portfolios: [
        {
          name: "Core",
          assets: [{ symbol: "SPY", weight: 100 }],
        },
      ],
      start_date: "2024-01-01",
      end_date: "2024-06-30",
    };
    const response = await router.fetch(
      new Request("https://edge.example/api/v3/portfolio/preflight", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
      { BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    assert.equal(response.status, 200);
    assert.deepEqual(forwardedBody, payload);
    assert.equal(forwardedHeaders.get("origin"), null);
    assert.equal(forwardedHeaders.get("referer"), null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Portfolio v3 rejects unknown paths, wrong methods and oversized bodies", async () => {
  const unknown = await router.fetch(
    new Request("https://edge.example/api/v3/portfolio/unknown"),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(unknown.status, 404);

  const wrongMethod = await router.fetch(
    new Request("https://edge.example/api/v3/portfolio/backtests"),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(wrongMethod.status, 405);

  const oversized = await router.fetch(
    new Request("https://edge.example/api/v3/portfolio/backtests", {
      method: "POST",
      headers: { "content-length": String(512 * 1024 + 1) },
      body: "{}",
    }),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(oversized.status, 413);
});

test("Portfolio v3 requires the self-owned backend origin", async () => {
  const response = await router.fetch(
    new Request("https://edge.example/api/v3/portfolio/health"),
    {},
    {},
  );
  assert.equal(response.status, 503);
  const payload = await response.json();
  assert.equal(payload.error, "後端服務尚未設定。");
});