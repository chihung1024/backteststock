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

test("GET /api/v2/sources/qqqm-holdings relays a bounded sanitized payload", async () => {
  const originalFetch = globalThis.fetch;
  let upstreamUrl;
  let upstreamOptions;
  globalThis.fetch = async (url, options) => {
    upstreamUrl = String(url);
    upstreamOptions = options;
    return Response.json({
      effectiveBusinessDate: "2026-07-28",
      holdings: Array.from({ length: 103 }, (_unused, index) => ({
        ticker: `T${index}`,
        issuerName: `Company ${index}`,
        securityTypeCode: "COM",
        percentageOfTotalNetAssets: 0.5,
        marketValueBase: 1000,
        ignoredField: "not relayed",
      })),
    });
  };

  try {
    const response = await worker.fetch(
      new Request("https://example.com/api/v2/sources/qqqm-holdings"),
      {},
    );
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("x-source-origin"), "dng-api.invesco.com");
    const payload = await response.json();
    assert.equal(payload.effectiveBusinessDate, "2026-07-28");
    assert.equal(payload.holdings.length, 103);
    assert.equal(payload.holdings[0].ignoredField, undefined);
    assert.match(upstreamUrl, /^https:\/\/dng-api\.invesco\.com\//);
    assert.equal(upstreamOptions.redirect, "error");
    assert.equal(upstreamOptions.cf.cacheTtlByStatus["200-299"], 21600);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("QQQM source relay fails closed for an invalid upstream payload", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    Response.json({
      effectiveBusinessDate: "2026-07-28",
      holdings: [{ ticker: "AAPL" }],
    });

  try {
    const response = await worker.fetch(
      new Request("https://example.com/api/v2/sources/qqqm-holdings"),
      {},
    );
    assert.equal(response.status, 502);
    assert.match((await response.json()).error, /暫時無法讀取/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("QQQM source relay rejects non-GET methods without fetching", async () => {
  const originalFetch = globalThis.fetch;
  let called = false;
  globalThis.fetch = async () => {
    called = true;
    return Response.json({});
  };

  try {
    const response = await worker.fetch(
      new Request("https://example.com/api/v2/sources/qqqm-holdings", {
        method: "POST",
      }),
      {},
    );
    assert.equal(response.status, 405);
    assert.equal(called, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
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
