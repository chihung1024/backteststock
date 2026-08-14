import assert from "node:assert/strict";
import test from "node:test";

import worker from "../worker/index.js";

function pitDatabase({ universe = { id: "sp500", name: "S&P 500" }, archive = null } = {}) {
  return {
    prepare(sql) {
      const statement = {
        params: [],
        bind(...params) {
          statement.params = params;
          return statement;
        },
        async first() {
          if (sql.includes("FROM universes\n       WHERE id = ?1")) return universe;
          if (sql.includes("FROM universe_snapshot_archive")) return archive;
          throw new Error(`Unexpected first query: ${sql}`);
        },
      };
      return statement;
    },
  };
}

function currentDatabase() {
  return {
    prepare(sql) {
      const statement = {
        bind() {
          return statement;
        },
        async first() {
          if (sql.includes("FROM universes AS u")) {
            return {
              id: "sp500",
              name: "S&P 500",
              proxy_note: null,
              version_id: "current-version",
              version: "2026-08-14-current",
              source_as_of: "2026-08-14",
              fetched_at: "2026-08-14T12:00:00Z",
              member_count: 2,
            };
          }
          throw new Error(`Unexpected first query: ${sql}`);
        },
        async all() {
          if (sql.includes("FROM universe_members")) {
            return {
              results: [
                { ticker: "AAPL", source_ticker: "AAPL" },
                { ticker: "MSFT", source_ticker: "MSFT" },
              ],
            };
          }
          throw new Error(`Unexpected all query: ${sql}`);
        },
      };
      return statement;
    },
  };
}

const archive = {
  universe_id: "sp500",
  source_as_of: "2026-08-10",
  version: "2026-08-10-pit",
  fetched_at: "2026-08-10T12:00:00Z",
  source_label: "Fixture source",
  source_url: "https://example.com/source",
  is_proxy: 0,
  warning: null,
  checksum: "abc123",
  member_count: 2,
  members_json: JSON.stringify(["AAPL", "OLDCO"]),
};

test("GET Universe asOf returns causal archived membership instead of current membership", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/v2/universes/sp500?asOf=2026-08-12"),
    { DB: pitDatabase({ archive }) },
  );

  assert.equal(response.status, 200);
  const payload = await response.json();
  assert.equal(payload.data.selectionMode, "point_in_time_last_observed");
  assert.equal(payload.data.requestedAsOf, "2026-08-12");
  assert.equal(payload.data.sourceAsOf, "2026-08-10");
  assert.equal(payload.data.observationAgeDays, 2);
  assert.equal(payload.data.pointInTime, true);
  assert.deepEqual(
    payload.data.members.map((member) => member.ticker),
    ["AAPL", "OLDCO"],
  );
});

test("historical Universe lookup fails closed when no prior archived evidence exists", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/v2/universes/sp500?asOf=2020-01-01"),
    { DB: pitDatabase({ archive: null }) },
  );

  assert.equal(response.status, 409);
  assert.match((await response.json()).error, /沒有可驗證/);
});

test("historical Universe lookup rejects stale last-observed membership", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/v2/universes/sp500?asOf=2026-08-25"),
    { DB: pitDatabase({ archive }) },
  );

  assert.equal(response.status, 409);
  assert.match((await response.json()).error, /超過 10 天/);
});

test("historical Universe lookup validates the research date strictly", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/v2/universes/sp500?asOf=2026-02-30"),
    { DB: pitDatabase({ archive }) },
  );

  assert.equal(response.status, 400);
  assert.match((await response.json()).error, /YYYY-MM-DD/);
});

test("PIT membership-only screener never calls current fundamentals backend", async () => {
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  globalThis.fetch = async () => {
    backendCalls += 1;
    throw new Error("PIT membership-only mode must not call backend fundamentals");
  };

  try {
    const response = await worker.fetch(
      new Request("https://example.com/api/v2/screener", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          universe: "sp500",
          selectionAsOf: "2026-08-12",
          sector: "any",
          filters: {},
          sort: "ticker-asc",
        }),
      }),
      { DB: pitDatabase({ archive }) },
    );

    assert.equal(response.status, 200);
    assert.equal(backendCalls, 0);
    const payload = await response.json();
    assert.deepEqual(payload.candidates, [{ ticker: "AAPL" }, { ticker: "OLDCO" }]);
    assert.equal(payload.fundamentalsAsOf, null);
    assert.equal(payload.researchValidity.membershipPointInTime, true);
    assert.equal(payload.researchValidity.fundamentalsApplied, false);
    assert.equal(payload.researchValidity.historicalSelectionSafe, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("PIT screener rejects historical fundamental filtering instead of using current data", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/v2/screener", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        universe: "sp500",
        selectionAsOf: "2026-08-12",
        sector: "Technology",
        filters: { marketCap: { min: 1_000_000_000 } },
        sort: "marketCap-desc",
      }),
    }),
    { DB: pitDatabase({ archive }) },
  );

  assert.equal(response.status, 409);
  assert.match((await response.json()).error, /歷史 fundamentals/);
});

test("current screener remains functional but is explicitly marked retrospective", async () => {
  const originalFetch = globalThis.fetch;
  let forwarded;
  globalThis.fetch = async (_url, options) => {
    forwarded = JSON.parse(new TextDecoder().decode(options.body));
    return Response.json({
      universe: { id: "sp500" },
      candidates: [{ ticker: "AAPL" }],
      warnings: [],
    });
  };

  try {
    const response = await worker.fetch(
      new Request("https://example.com/api/v2/screener", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ universe: "sp500", sort: "marketCap-desc" }),
      }),
      { BACKEND_ORIGIN: "https://backend.example.com", DB: currentDatabase() },
    );

    assert.equal(response.status, 200);
    assert.equal(forwarded._universe.version, "2026-08-14-current");
    const payload = await response.json();
    assert.equal(payload.researchValidity.selectionMode, "current_snapshot_retrospective");
    assert.equal(payload.researchValidity.historicalSelectionSafe, false);
    assert.ok(payload.warnings.some((warning) => warning.includes("不能視為歷史時點選股")));
  } finally {
    globalThis.fetch = originalFetch;
  }
});
