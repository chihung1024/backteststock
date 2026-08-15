import assert from "node:assert/strict";
import test from "node:test";

import router from "../worker/walk_forward_router.js";

test("Walk-Forward POST proxies exact JSON through BACKEND_ORIGIN with sanitized headers", async () => {
  const originalFetch = globalThis.fetch;
  let forwardedUrl;
  let forwardedBody;
  let forwardedHeaders;
  globalThis.fetch = async (url, options) => {
    forwardedUrl = String(url);
    forwardedBody = JSON.parse(new TextDecoder().decode(options.body));
    forwardedHeaders = new Headers(options.headers);
    return new Response(JSON.stringify({ status: "completed" }), {
      status: 200,
      headers: {
        "content-type": "application/json",
        "server": "hidden",
        "set-cookie": "secret=1",
      },
    });
  };

  try {
    const payload = {
      periods: [{ periodId: "p1" }],
      selector: { universe: "soxx", holdingCount: 5 },
    };
    const response = await router.fetch(
      new Request("https://edge.example/api/v1/research/walk-forward", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          cookie: "browser=secret",
          authorization: "Bearer secret",
          "cf-connecting-ip": "203.0.113.10",
        },
        body: JSON.stringify(payload),
      }),
      { BACKEND_ORIGIN: "https://backend.example/base" },
      {},
    );

    assert.equal(response.status, 200);
    assert.equal(forwardedUrl, "https://backend.example/api/v1/research/walk-forward");
    assert.deepEqual(forwardedBody, payload);
    assert.equal(forwardedHeaders.get("cookie"), null);
    assert.equal(forwardedHeaders.get("authorization"), null);
    assert.equal(forwardedHeaders.get("x-forwarded-for"), "203.0.113.10");
    assert.equal(response.headers.get("server"), null);
    assert.equal(response.headers.get("set-cookie"), null);
    assert.ok(response.headers.get("x-request-id"));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Walk-Forward health preserves path and query", async () => {
  const originalFetch = globalThis.fetch;
  let forwardedUrl;
  globalThis.fetch = async (url) => {
    forwardedUrl = String(url);
    return Response.json({ status: "ok" });
  };
  try {
    const response = await router.fetch(
      new Request("https://edge.example/api/v1/research/walk-forward/health?probe=1"),
      { BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    assert.equal(response.status, 200);
    assert.equal(
      forwardedUrl,
      "https://backend.example/api/v1/research/walk-forward/health?probe=1",
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Walk-Forward edge rejects wrong methods, unknown suffixes and oversized bodies", async () => {
  const wrongMethod = await router.fetch(
    new Request("https://edge.example/api/v1/research/walk-forward"),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(wrongMethod.status, 405);

  const unknown = await router.fetch(
    new Request("https://edge.example/api/v1/research/walk-forward/unknown"),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(unknown.status, 404);

  const oversized = await router.fetch(
    new Request("https://edge.example/api/v1/research/walk-forward", {
      method: "POST",
      headers: { "content-length": String(128 * 1024 + 1) },
      body: "{}",
    }),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(oversized.status, 413);
});

test("Walk-Forward edge requires BACKEND_ORIGIN", async () => {
  const response = await router.fetch(
    new Request("https://edge.example/api/v1/research/walk-forward/health"),
    {},
    {},
  );
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error, "後端服務尚未設定。");
});
