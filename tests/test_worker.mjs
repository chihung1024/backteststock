import assert from "node:assert/strict";
import test from "node:test";

import worker, { universeFromRow } from "../worker/index.js";

function mockDatabase({ catalog = [], universe = null, members = [] } = {}) {
  return {
    prepare(sql) {
      const statement = {
        params: [],
        bind(...params) {
          statement.params = params;
          return statement;
        },
        async first() {
          if (sql.includes("FROM universes AS u")) return universe;
          throw new Error(`Unexpected first query: ${sql}`);
        },
        async all() {
          if (sql.includes("ORDER BY u.sort_order")) return { results: catalog };
          if (sql.includes("FROM universe_members")) return { results: members };
          throw new Error(`Unexpected all query: ${sql}`);
        },
      };
      return statement;
    },
  };
}

test("universeFromRow exposes proxy disclosure and unavailable state", () => {
  const result = universeFromRow({
    id: "russell2000",
    name: "Russell 2000",
    description: "Proxy",
    source_label: "IWM",
    source_url: "https://example.com",
    is_proxy: 1,
    proxy_note: "IWM proxy",
    version_id: null,
    version: null,
    member_count: null,
  });
  assert.equal(result.available, false);
  assert.equal(result.source.isProxy, true);
  assert.equal(result.memberCount, 0);
  assert.ok(result.warnings.some((warning) => warning.includes("IWM proxy")));
  assert.ok(result.warnings.some((warning) => warning.includes("尚無有效")));
});

test("GET /api/v2/universes reads the D1 current-version catalog", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/v2/universes"),
    {
      DB: mockDatabase({
        catalog: [
          {
            id: "soxx",
            name: "SOXX holdings",
            description: "Semiconductors",
            source_label: "iShares",
            source_url: "https://example.com/soxx.csv",
            is_proxy: 0,
            proxy_note: null,
            version_id: "version-id",
            version: "2026-07-28-abc",
            source_as_of: "2026-07-28",
            fetched_at: new Date().toISOString(),
            member_count: 30,
          },
        ],
      }),
    },
  );
  assert.equal(response.status, 200);
  const payload = await response.json();
  assert.equal(payload.data[0].id, "soxx");
  assert.equal(payload.data[0].available, true);
  assert.equal(payload.data[0].memberCount, 30);
});

test("GET /api/v2/universes exposes current-version fallback metadata", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/v2/universes"),
    {
      DB: mockDatabase({
        catalog: [
          {
            id: "nasdaq100",
            name: "NASDAQ-100",
            description: "Fallback capable",
            source_label: "Invesco QQQM holdings",
            source_url: "https://example.com/qqqm",
            is_proxy: 1,
            proxy_note: "QQQM proxy",
            version_id: "version-id",
            version: "2026-07-28-abc",
            source_as_of: "2026-07-28",
            fetched_at: new Date().toISOString(),
            member_count: 103,
          },
        ],
      }),
    },
  );
  const payload = await response.json();
  assert.equal(payload.data[0].source.label, "Invesco QQQM holdings");
  assert.equal(payload.data[0].source.isProxy, true);
  assert.ok(payload.data[0].warnings.includes("QQQM proxy"));
});

test("POST /api/v2/screener injects the trusted D1 snapshot", async () => {
  const originalFetch = globalThis.fetch;
  let forwarded;
  globalThis.fetch = async (_url, options) => {
    forwarded = JSON.parse(new TextDecoder().decode(options.body));
    return Response.json({ ok: true });
  };

  try {
    const response = await worker.fetch(
      new Request("https://example.com/api/v2/screener", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          universe: "sp500",
          limit: 25,
          _universe: { id: "forged", members: ["EVIL"] },
        }),
      }),
      {
        BACKEND_ORIGIN: "https://backend.example.com",
        DB: mockDatabase({
          universe: {
            id: "sp500",
            name: "S&P 500",
            proxy_note: "IVV proxy",
            version_id: "version-id",
            version: "2026-07-28-abc",
            source_as_of: "2026-07-28",
            fetched_at: "2026-07-29T00:00:00Z",
            member_count: 2,
          },
          members: [
            { ticker: "AAPL", source_ticker: "AAPL" },
            { ticker: "BRK-B", source_ticker: "BRKB" },
          ],
        }),
      },
    );
    assert.equal(response.status, 200);
    assert.equal(forwarded._universe.id, "sp500");
    assert.deepEqual(
      forwarded._universe.members.map((member) => member.ticker),
      ["AAPL", "BRK-B"],
    );
    assert.equal(forwarded._universe.proxyNote, "IVV proxy");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("a D1 member-count mismatch fails closed", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/v2/universes/sp500"),
    {
      DB: mockDatabase({
        universe: {
          id: "sp500",
          name: "S&P 500",
          proxy_note: null,
          version_id: "version-id",
          version: "version",
          source_as_of: "2026-07-28",
          fetched_at: "2026-07-29T00:00:00Z",
          member_count: 2,
        },
        members: [{ ticker: "AAPL", source_ticker: "AAPL" }],
      }),
    },
  );
  assert.equal(response.status, 503);
  assert.match((await response.json()).error, /完整性/);
});


test("proxy mirrors backend Server-Timing to a stable edge header", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(
    JSON.stringify([{ ticker: "AAPL", status: "ok" }]),
    {
      status: 200,
      headers: {
        "content-type": "application/json",
        "server-timing": "market;dur=1250.0, compute;dur=220.0, total;dur=1500.0",
        "x-scan-requested": "1",
        "x-scan-resolved": "1",
      },
    },
  );

  try {
    const response = await worker.fetch(
      new Request("https://example.com/api/scan", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ tickers: ["AAPL"] }),
      }),
      { BACKEND_ORIGIN: "https://backend.example.com" },
    );
    const expected = "market;dur=1250.0, compute;dur=220.0, total;dur=1500.0";
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("server-timing"), expected);
    assert.equal(response.headers.get("x-backend-server-timing"), expected);
    assert.equal(response.headers.get("x-scan-requested"), "1");
    assert.equal(response.headers.get("x-scan-resolved"), "1");
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("identical backtest requests reuse the edge response cache", async () => {
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  const stored = new Map();
  const cache = {
    async match(request) {
      return stored.get(request.url)?.clone() || null;
    },
    async put(request, response) {
      stored.set(request.url, response.clone());
    },
  };
  globalThis.fetch = async () => {
    backendCalls += 1;
    return new Response(
      JSON.stringify({ data: [], benchmark: null, metadata: {} }),
      {
        status: 200,
        headers: {
          "content-type": "application/json",
          "server-timing": "market;dur=100",
        },
      },
    );
  };

  try {
    const env = {
      BACKEND_ORIGIN: "https://backend.example",
      API_CACHE: cache,
    };
    const body = JSON.stringify({
      startDate: "2025-08-01",
      endDate: "2026-07-31",
      initialAmount: 10000,
      portfolios: [
        { name: "P", tickers: ["SPY"], weights: [100] },
      ],
    });
    const request = () => new Request(
      "https://example.com/api/backtest",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body,
      },
    );
    const first = await worker.fetch(request(), env);
    const second = await worker.fetch(request(), env);
    assert.equal(first.headers.get("x-edge-cache"), "MISS");
    assert.equal(second.headers.get("x-edge-cache"), "HIT");
    assert.equal(backendCalls, 1);
    assert.deepEqual(
      await second.json(),
      { data: [], benchmark: null, metadata: {} },
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
