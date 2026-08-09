import assert from "node:assert/strict";
import test from "node:test";

import router from "../worker/router.js";

test("Refinery v1 forwards only the approved POST route and sanitizes headers", async () => {
  const originalFetch = globalThis.fetch;
  let forwardedUrl;
  let forwardedBody;
  let forwardedHeaders;
  globalThis.fetch = async (url, options) => {
    forwardedUrl = String(url);
    forwardedBody = JSON.parse(new TextDecoder().decode(options.body));
    forwardedHeaders = new Headers(options.headers);
    return new Response(JSON.stringify({ status: "ready" }), {
      status: 200,
      headers: {
        "content-type": "application/json",
        "server": "hidden",
        "x-powered-by": "hidden",
        "set-cookie": "secret=1",
      },
    });
  };

  try {
    const payload = {
      contract_version: "refinery-v1",
      symbols: ["AAA", "BBB"],
      start_date: "2024-01-01",
      end_date: "2024-12-31",
    };
    const response = await router.fetch(
      new Request("https://edge.example/api/v1/refinery/preflight", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: "Bearer secret",
          cookie: "browser=secret",
          "cf-connecting-ip": "203.0.113.20",
        },
        body: JSON.stringify(payload),
      }),
      { BACKEND_ORIGIN: "https://backend.example/base" },
      {},
    );

    assert.equal(response.status, 200);
    assert.equal(forwardedUrl, "https://backend.example/api/v1/refinery/preflight");
    assert.deepEqual(forwardedBody, payload);
    assert.equal(forwardedHeaders.get("authorization"), null);
    assert.equal(forwardedHeaders.get("cookie"), null);
    assert.equal(forwardedHeaders.get("x-forwarded-for"), "203.0.113.20");
    assert.equal(response.headers.get("server"), null);
    assert.equal(response.headers.get("x-powered-by"), null);
    assert.equal(response.headers.get("set-cookie"), null);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.ok(response.headers.get("x-request-id"));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Refinery v1 rejects unknown paths, wrong methods and oversized bodies", async () => {
  const unknown = await router.fetch(
    new Request("https://edge.example/api/v1/refinery/unknown", {
      method: "POST",
      body: "{}",
    }),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(unknown.status, 404);

  const wrongMethod = await router.fetch(
    new Request("https://edge.example/api/v1/refinery/analyze"),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(wrongMethod.status, 405);

  const oversized = await router.fetch(
    new Request("https://edge.example/api/v1/refinery/analyze", {
      method: "POST",
      headers: { "content-length": String(512 * 1024 + 1) },
      body: "{}",
    }),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(oversized.status, 413);
});

test("Refinery v1 requires the configured self-owned backend origin", async () => {
  const response = await router.fetch(
    new Request("https://edge.example/api/v1/refinery/preflight", {
      method: "POST",
      body: "{}",
    }),
    {},
    {},
  );
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error, "後端服務尚未設定。");
});

test("Refinery v1 analyze preserves path and does not use the generic edge cache", async () => {
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  globalThis.fetch = async () => {
    backendCalls += 1;
    return Response.json({ status: "ok" });
  };

  try {
    const request = () => new Request("https://edge.example/api/v1/refinery/analyze", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        contract_version: "refinery-v1",
        symbols: ["AAA", "BBB"],
        start_date: "2024-01-01",
        end_date: "2024-12-31",
      }),
    });
    const env = {
      BACKEND_ORIGIN: "https://backend.example",
      API_CACHE: {
        async match() {
          throw new Error("Refinery must not use generic edge cache");
        },
        async put() {
          throw new Error("Refinery must not use generic edge cache");
        },
      },
    };
    const first = await router.fetch(request(), env, {});
    const second = await router.fetch(request(), env, {});
    assert.equal(first.status, 200);
    assert.equal(second.status, 200);
    assert.equal(backendCalls, 2);
    assert.equal(first.headers.get("x-edge-cache"), null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
