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

test("retryable scan HTTP-200 rows poison an identical edge-cache retry", async () => {
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  globalThis.fetch = async () => {
    backendCalls += 1;
    if (backendCalls === 1) {
      return new Response(
        JSON.stringify([
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
        ]),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
            "x-scan-requested": "2",
            "x-scan-resolved": "0",
          },
        },
      );
    }
    return new Response(
      JSON.stringify([
        { ticker: "T0301", status: "ok", retryable: false },
        { ticker: "T0302", status: "ok", retryable: false },
      ]),
      {
        status: 200,
        headers: {
          "content-type": "application/json",
          "x-scan-requested": "2",
          "x-scan-resolved": "2",
        },
      },
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

    // This is the current defect being reproduced: the backend recovery path
    // is never reached because the retryable HTTP-200 response was cached.
    assert.equal(second.headers.get("x-edge-cache"), "HIT");
    assert.equal(backendCalls, 1);
    assert.equal(secondPayload[0].retryable, true);
    assert.equal(secondPayload[0].status, "failed");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("request-level HTTP 503 is not cached and therefore can recover on retry", async () => {
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  globalThis.fetch = async () => {
    backendCalls += 1;
    if (backendCalls === 1) {
      return new Response(JSON.stringify({ error: "temporary backend outage" }), {
        status: 503,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response(
      JSON.stringify([
        { ticker: "T0301", status: "ok", retryable: false },
        { ticker: "T0302", status: "ok", retryable: false },
      ]),
      {
        status: 200,
        headers: {
          "content-type": "application/json",
          "x-scan-requested": "2",
          "x-scan-resolved": "2",
        },
      },
    );
  };

  try {
    const env = {
      BACKEND_ORIGIN: "https://backend.example",
      API_CACHE: memoryCache(),
    };

    const first = await worker.fetch(scanRequest(), env);
    assert.equal(first.status, 503);
    assert.equal(first.headers.get("x-edge-cache"), "MISS");

    const second = await worker.fetch(scanRequest(), env);
    const secondPayload = await second.json();
    assert.equal(second.status, 200);
    assert.equal(second.headers.get("x-edge-cache"), "MISS");
    assert.equal(backendCalls, 2);
    assert.equal(secondPayload[0].status, "ok");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
