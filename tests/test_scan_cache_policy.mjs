import assert from "node:assert/strict";
import test from "node:test";

import worker from "../worker/index.js";

function memoryCache() {
  const stored = new Map();
  return {
    async match(request) {
      return stored.get(request.url)?.clone() || null;
    },
    async put(request, response) {
      stored.set(request.url, response.clone());
    },
  };
}

function scanRequest() {
  return new Request("https://example.com/api/scan", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      tickers: ["T0301", "T0302"],
      benchmark: "SPY",
      startDate: "2025-01-01",
      endDate: "2025-12-31",
      startYear: 2025,
      startMonth: 1,
      endYear: 2025,
      endMonth: 12,
    }),
  });
}

function scanResponse(rows, requested, resolved) {
  const headers = new Headers({ "content-type": "application/json" });
  if (requested != null) headers.set("x-scan-requested", String(requested));
  if (resolved != null) headers.set("x-scan-resolved", String(resolved));
  return new Response(JSON.stringify(rows), { status: 200, headers });
}

test("retryable HTTP-200 scan result is not cached and identical retry reaches backend", async () => {
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  globalThis.fetch = async () => {
    backendCalls += 1;
    if (backendCalls === 1) {
      return scanResponse(
        [
          {
            ticker: "T0301",
            status: "failed",
            retryable: true,
            error_code: "twd_download_unavailable",
            error: "synthetic temporary Yahoo failure",
          },
          {
            ticker: "T0302",
            status: "failed",
            retryable: true,
            error_code: "twd_download_unavailable",
            error: "synthetic temporary Yahoo failure",
          },
        ],
        2,
        0,
      );
    }
    return scanResponse(
      [
        { ticker: "T0301", status: "ok", retryable: false },
        { ticker: "T0302", status: "ok", retryable: false },
      ],
      2,
      2,
    );
  };

  try {
    const env = {
      BACKEND_ORIGIN: "https://backend.example",
      API_CACHE: memoryCache(),
    };

    const first = await worker.fetch(scanRequest(), env);
    const firstPayload = await first.json();
    assert.equal(first.headers.get("x-edge-cache"), "MISS");
    assert.equal(firstPayload[0].retryable, true);

    const second = await worker.fetch(scanRequest(), env);
    const secondPayload = await second.json();
    assert.equal(second.headers.get("x-edge-cache"), "MISS");
    assert.equal(backendCalls, 2);
    assert.equal(secondPayload[0].status, "ok");

    const third = await worker.fetch(scanRequest(), env);
    const thirdPayload = await third.json();
    assert.equal(third.headers.get("x-edge-cache"), "HIT");
    assert.equal(backendCalls, 2);
    assert.equal(thirdPayload[0].status, "ok");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("fully resolved scan response remains cacheable", async () => {
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  globalThis.fetch = async () => {
    backendCalls += 1;
    return scanResponse(
      [
        { ticker: "T0301", status: "ok", retryable: false },
        { ticker: "T0302", status: "ok", retryable: false },
      ],
      2,
      2,
    );
  };

  try {
    const env = {
      BACKEND_ORIGIN: "https://backend.example",
      API_CACHE: memoryCache(),
    };

    const first = await worker.fetch(scanRequest(), env);
    const second = await worker.fetch(scanRequest(), env);
    assert.equal(first.headers.get("x-edge-cache"), "MISS");
    assert.equal(second.headers.get("x-edge-cache"), "HIT");
    assert.equal(backendCalls, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("scan response with missing resolution headers fails closed for cache admission", async () => {
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  globalThis.fetch = async () => {
    backendCalls += 1;
    return scanResponse(
      [
        { ticker: "T0301", status: "ok", retryable: false },
        { ticker: "T0302", status: "ok", retryable: false },
      ],
      null,
      null,
    );
  };

  try {
    const env = {
      BACKEND_ORIGIN: "https://backend.example",
      API_CACHE: memoryCache(),
    };

    const first = await worker.fetch(scanRequest(), env);
    const second = await worker.fetch(scanRequest(), env);
    assert.equal(first.headers.get("x-edge-cache"), "MISS");
    assert.equal(second.headers.get("x-edge-cache"), "MISS");
    assert.equal(backendCalls, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("scan response with mismatched resolution headers is not cached", async () => {
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  globalThis.fetch = async () => {
    backendCalls += 1;
    return scanResponse(
      [
        { ticker: "T0301", status: "ok", retryable: false },
        {
          ticker: "T0302",
          status: "failed",
          retryable: true,
          error: "synthetic partial result",
        },
      ],
      2,
      1,
    );
  };

  try {
    const env = {
      BACKEND_ORIGIN: "https://backend.example",
      API_CACHE: memoryCache(),
    };

    const first = await worker.fetch(scanRequest(), env);
    const second = await worker.fetch(scanRequest(), env);
    assert.equal(first.headers.get("x-edge-cache"), "MISS");
    assert.equal(second.headers.get("x-edge-cache"), "MISS");
    assert.equal(backendCalls, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
