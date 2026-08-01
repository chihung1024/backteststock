import assert from "node:assert/strict";
import test from "node:test";

import worker from "../worker/index.js";


test("optimizer routes proxy payloads larger than the ordinary API limit", async () => {
  const originalFetch = globalThis.fetch;
  let forwardedBytes = 0;
  globalThis.fetch = async (_url, options) => {
    forwardedBytes = options.body.byteLength;
    return Response.json({ results: [], metadata: {} });
  };

  try {
    const largeValue = "x".repeat(300 * 1024);
    const response = await worker.fetch(
      new Request("https://example.com/api/optimizer/verify", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ snapshot: { data: largeValue } }),
      }),
      { BACKEND_ORIGIN: "https://backend.example.com" },
    );
    assert.equal(response.status, 200);
    assert.ok(forwardedBytes > 256 * 1024);
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


test("optimizer payloads above 2 MiB fail closed", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/optimizer/verify", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ value: "x".repeat(2 * 1024 * 1024 + 1024) }),
    }),
    { BACKEND_ORIGIN: "https://backend.example.com" },
  );
  assert.equal(response.status, 413);
});