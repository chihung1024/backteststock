import assert from "node:assert/strict";
import test from "node:test";

import router from "../worker/router.js";

test("POST exhaustive prepare is forwarded to the configured backend", async () => {
  const originalFetch = globalThis.fetch;
  let forwardedUrl;
  let forwardedBody;
  globalThis.fetch = async (url, options) => {
    forwardedUrl = String(url);
    forwardedBody = JSON.parse(new TextDecoder().decode(options.body));
    return new Response(JSON.stringify({ snapshot: { datasetHash: "hash" } }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };

  try {
    const payload = {
      sourceTickers: ["AAPL", "MSFT"],
      benchmark: "SPY",
      startDate: "2016-08-02",
      endDate: "2026-08-01",
    };
    const response = await router.fetch(
      new Request("https://edge.example/api/optimizer/exhaustive/prepare", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
      { BACKEND_ORIGIN: "https://backend.example/base" },
      {},
    );
    assert.equal(response.status, 200);
    assert.equal(
      forwardedUrl,
      "https://backend.example/api/optimizer/exhaustive/prepare",
    );
    assert.deepEqual(forwardedBody, payload);
    assert.ok(response.headers.get("x-request-id"));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("exhaustive prepare rejects unsupported methods and oversized bodies", async () => {
  const getResponse = await router.fetch(
    new Request("https://edge.example/api/optimizer/exhaustive/prepare"),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(getResponse.status, 405);

  const oversized = await router.fetch(
    new Request("https://edge.example/api/optimizer/exhaustive/prepare", {
      method: "POST",
      headers: { "content-length": String(3 * 1024 * 1024 + 1) },
      body: "{}",
    }),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(oversized.status, 413);
});

test("all existing routes remain delegated to the original worker", async () => {
  const response = await router.fetch(
    new Request("https://edge.example/api/edge-health"),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(response.status, 200);
  const payload = await response.json();
  assert.equal(payload.service, "backteststock-edge");
});
