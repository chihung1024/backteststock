import assert from "node:assert/strict";
import test from "node:test";

import worker from "../worker/index.js";

const MAX_CACHE_RESPONSE_BYTES = 1024 * 1024;

function memoryCache({ matchError = null, putError = null } = {}) {
  const stored = new Map();
  return {
    stored,
    async match(request) {
      if (matchError) throw matchError;
      return stored.get(request.url)?.clone() || null;
    },
    async put(request, response) {
      if (putError) throw putError;
      stored.set(request.url, response.clone());
    },
  };
}

function scanRequest(search = "") {
  return new Request(`https://example.com/api/scan${search}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      tickers: ["T0301"],
      benchmark: "SPY",
      startDate: "2025-01-01",
      endDate: "2025-12-31",
    }),
  });
}

function scanResponse(body, extraHeaders = {}) {
  return new Response(body, {
    status: 200,
    headers: {
      "content-type": "application/json",
      "x-scan-requested": "1",
      "x-scan-resolved": "1",
      ...extraHeaders,
    },
  });
}

async function withBackend(responseFactory, callback) {
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  globalThis.fetch = async (url) => {
    backendCalls += 1;
    return responseFactory(url, backendCalls);
  };
  try {
    await callback(() => backendCalls);
  } finally {
    globalThis.fetch = originalFetch;
  }
}

test("declared oversized scan responses remain proxyable but are never cached", async () => {
  const cache = memoryCache();
  await withBackend(
    () => scanResponse(JSON.stringify([{ ticker: "T0301" }]), {
      "content-length": String(MAX_CACHE_RESPONSE_BYTES + 1),
    }),
    async (backendCalls) => {
      const env = { BACKEND_ORIGIN: "https://backend.example", API_CACHE: cache };
      const first = await worker.fetch(scanRequest(), env);
      const second = await worker.fetch(scanRequest(), env);

      assert.equal(first.status, 200);
      assert.equal(second.status, 200);
      assert.equal(first.headers.get("x-edge-cache"), "MISS");
      assert.equal(second.headers.get("x-edge-cache"), "MISS");
      await first.arrayBuffer();
      await second.arrayBuffer();
      assert.equal(await backendCalls(), 2);
      assert.equal(cache.stored.size, 0);
    },
  );
});

test("actual oversized scan bodies remain proxyable but are never cached", async () => {
  const cache = memoryCache();
  const oversizedPayload = JSON.stringify(["x".repeat(MAX_CACHE_RESPONSE_BYTES)]);
  assert.ok(new TextEncoder().encode(oversizedPayload).byteLength > MAX_CACHE_RESPONSE_BYTES);

  await withBackend(
    () => scanResponse(oversizedPayload),
    async (backendCalls) => {
      const env = { BACKEND_ORIGIN: "https://backend.example", API_CACHE: cache };
      const first = await worker.fetch(scanRequest(), env);
      const second = await worker.fetch(scanRequest(), env);

      assert.equal(first.status, 200);
      assert.equal(second.status, 200);
      assert.equal(first.headers.get("x-edge-cache"), "MISS");
      assert.equal(second.headers.get("x-edge-cache"), "MISS");
      await first.arrayBuffer();
      await second.arrayBuffer();
      assert.equal(await backendCalls(), 2);
      assert.equal(cache.stored.size, 0);
    },
  );
});

test("oversized streaming bodies cancel the cache reader before consuming the tail", async () => {
  const cache = memoryCache();
  const chunkSizes = [MAX_CACHE_RESPONSE_BYTES - 128, 256, 1];
  let pulls = 0;
  let cancelled = false;
  const stream = new ReadableStream({
    pull(controller) {
      const size = chunkSizes[pulls];
      pulls += 1;
      if (size == null) {
        controller.error(new Error("cache reader consumed past the oversized body"));
        return;
      }
      controller.enqueue(new Uint8Array(size));
    },
    cancel() {
      cancelled = true;
    },
  }, { highWaterMark: 0, size: () => 1 });
  const originalClone = Response.prototype.clone;
  Response.prototype.clone = function cloneWithTrackedStream() {
    return new Response(stream, {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };

  try {
    await withBackend(
      () => scanResponse(JSON.stringify([{ ticker: "T0301", status: "ok" }])),
      async (backendCalls) => {
        const response = await worker.fetch(
          scanRequest(),
          { BACKEND_ORIGIN: "https://backend.example", API_CACHE: cache },
        );

        assert.equal(response.status, 200);
        assert.equal(response.headers.get("x-edge-cache"), "MISS");
        assert.deepEqual(await response.json(), [{ ticker: "T0301", status: "ok" }]);
        assert.equal(await backendCalls(), 1);
        assert.equal(cancelled, true);
        assert.equal(pulls, 2);
        assert.equal(cache.stored.size, 0);
      },
    );
  } finally {
    Response.prototype.clone = originalClone;
  }
});

test("cache.match failures fail open to the normal backend response", async () => {
  const cache = memoryCache({ matchError: new Error("cache unavailable") });
  await withBackend(
    () => scanResponse(JSON.stringify([{ ticker: "T0301", status: "ok" }])),
    async (backendCalls) => {
      const env = { BACKEND_ORIGIN: "https://backend.example", API_CACHE: cache };
      const response = await worker.fetch(scanRequest(), env);

      assert.equal(response.status, 200);
      assert.equal(response.headers.get("x-edge-cache"), "MISS");
      assert.deepEqual(await response.json(), [{ ticker: "T0301", status: "ok" }]);
      assert.equal(await backendCalls(), 1);
    },
  );
});

test("cache.put failures fail open to the normal backend response", async () => {
  const cache = memoryCache({ putError: new Error("cache write failed") });
  await withBackend(
    () => scanResponse(JSON.stringify([{ ticker: "T0301", status: "ok" }])),
    async (backendCalls) => {
      const env = { BACKEND_ORIGIN: "https://backend.example", API_CACHE: cache };
      const response = await worker.fetch(scanRequest(), env);

      assert.equal(response.status, 200);
      assert.equal(response.headers.get("x-edge-cache"), "MISS");
      assert.deepEqual(await response.json(), [{ ticker: "T0301", status: "ok" }]);
      assert.equal(await backendCalls(), 1);
    },
  );
});

test("response body read failures fail open to the normal backend response", async () => {
  const cache = memoryCache();
  const originalClone = Response.prototype.clone;
  Response.prototype.clone = function cloneWithFailure() {
    throw new Error("body read failed");
  };

  try {
    await withBackend(
      () => scanResponse(JSON.stringify([{ ticker: "T0301", status: "ok" }])),
      async (backendCalls) => {
        const response = await worker.fetch(
          scanRequest(),
          { BACKEND_ORIGIN: "https://backend.example", API_CACHE: cache },
        );

        assert.equal(response.status, 200);
        assert.equal(response.headers.get("x-edge-cache"), "MISS");
        assert.deepEqual(await response.json(), [{ ticker: "T0301", status: "ok" }]);
        assert.equal(await backendCalls(), 1);
      },
    );
  } finally {
    Response.prototype.clone = originalClone;
  }
});

test("query variations use distinct edge cache keys", async () => {
  const cache = memoryCache();
  await withBackend(
    (url) => scanResponse(JSON.stringify([{ query: new URL(url).search }])),
    async (backendCalls) => {
      const env = { BACKEND_ORIGIN: "https://backend.example", API_CACHE: cache };
      const summary = await worker.fetch(scanRequest("?view=summary"), env);
      const summaryHit = await worker.fetch(scanRequest("?view=summary"), env);
      const detail = await worker.fetch(scanRequest("?view=detail"), env);
      const detailHit = await worker.fetch(scanRequest("?view=detail"), env);

      assert.equal(summary.headers.get("x-edge-cache"), "MISS");
      assert.equal(summaryHit.headers.get("x-edge-cache"), "HIT");
      assert.equal(detail.headers.get("x-edge-cache"), "MISS");
      assert.equal(detailHit.headers.get("x-edge-cache"), "HIT");
      assert.equal(await backendCalls(), 2);
      assert.equal(cache.stored.size, 2);
      assert.deepEqual(await summaryHit.json(), [{ query: "?view=summary" }]);
      assert.deepEqual(await detailHit.json(), [{ query: "?view=detail" }]);
    },
  );
});
