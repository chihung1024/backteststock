import assert from "node:assert/strict";
import test from "node:test";

import worker from "../worker/index.js";


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
