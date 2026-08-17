import assert from "node:assert/strict";
import test from "node:test";

import router from "../worker/walk_forward_router.js";
import {
  combinationCount,
  recommendedHoldingCount,
  summarizeUniverse,
} from "../worker/walk_forward_admission.js";

function fakeAdmissionDb() {
  return {
    prepare(sql) {
      return {
        async all() {
          if (sql.includes("FROM universes")) {
            return {
              results: [
                { id: "sp500", name: "S&P 500 proxy", sort_order: 10 },
                { id: "nasdaq100", name: "NASDAQ-100", sort_order: 20 },
                { id: "soxx", name: "SOXX", sort_order: 30 },
              ],
            };
          }
          if (sql.includes("FROM universe_snapshot_archive")) {
            return {
              results: [
                { universe_id: "sp500", source_as_of: "2026-07-27", fetched_at: "2026-07-29T01:00:00Z", member_count: 504, is_proxy: 1, version: "sp-v1" },
                { universe_id: "nasdaq100", source_as_of: "2026-07-29", fetched_at: "2026-07-29T02:00:00Z", member_count: 102, is_proxy: 0, version: "ndx-v1" },
                { universe_id: "soxx", source_as_of: "2026-07-27", fetched_at: "2026-07-29T03:00:00Z", member_count: 30, is_proxy: 0, version: "soxx-v1" },
              ],
            };
          }
          throw new Error(`unexpected query: ${sql}`);
        },
      };
    },
  };
}

test("SOXX 30 choose 5 fits the synchronous budget while 30 choose 10 does not", () => {
  assert.equal(combinationCount(30, 5), 142506);
  assert.ok(combinationCount(30, 10) > 500000);
  assert.equal(recommendedHoldingCount(30), 5);
});

test("admission distinguishes proxy, candidate-limit and executable universes", () => {
  const asOf = "2026-08-16";
  const proxy = summarizeUniverse(
    { id: "sp500", name: "S&P 500 proxy" },
    [{ source_as_of: "2026-07-27", fetched_at: "2026-07-29T01:00:00Z", member_count: 504, is_proxy: 1, version: "sp-v1" }],
    asOf,
  );
  assert.equal(proxy.status, "blocked");
  assert.equal(proxy.reason, "proxy_membership_only");

  const tooLarge = summarizeUniverse(
    { id: "nasdaq100", name: "NASDAQ-100" },
    [{ source_as_of: "2026-07-29", fetched_at: "2026-07-29T01:00:00Z", member_count: 102, is_proxy: 0, version: "ndx-v1" }],
    asOf,
  );
  assert.equal(tooLarge.status, "blocked");
  assert.equal(tooLarge.reason, "candidate_limit");

  const soxx = summarizeUniverse(
    { id: "soxx", name: "SOXX" },
    [{ source_as_of: "2026-07-27", fetched_at: "2026-07-29T01:00:00Z", member_count: 30, is_proxy: 0, version: "soxx-v1" }],
    asOf,
  );
  assert.equal(soxx.status, "eligible");
  assert.equal(soxx.recommendedDecisionDate, "2026-07-29");
  assert.equal(soxx.recommendedHoldingCount, 5);
  assert.equal(soxx.recommendedCombinationCount, 142506);
});

test("edge admission is served from D1 and never forwarded to Vercel", async () => {
  const originalFetch = globalThis.fetch;
  let forwarded = false;
  globalThis.fetch = async () => {
    forwarded = true;
    throw new Error("admission must not proxy to backend");
  };
  try {
    const response = await router.fetch(
      new Request("https://edge.example/api/v1/research/walk-forward/admission"),
      { DB: fakeAdmissionDb(), BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.contractVersion, "walk-forward-admission-2026-08-17.1");
    assert.deepEqual(payload.recommended, {
      universe: "soxx",
      decisionDate: "2026-07-29",
      holdingCount: 5,
      memberCount: 30,
      combinationCount: 142506,
    });
    assert.equal(payload.universes.find((item) => item.id === "sp500").reason, "proxy_membership_only");
    assert.equal(payload.universes.find((item) => item.id === "nasdaq100").reason, "candidate_limit");
    assert.equal(forwarded, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edge admission requires D1 and only allows GET", async () => {
  const missingDb = await router.fetch(
    new Request("https://edge.example/api/v1/research/walk-forward/admission"),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(missingDb.status, 503);

  const wrongMethod = await router.fetch(
    new Request("https://edge.example/api/v1/research/walk-forward/admission", { method: "POST", body: "{}" }),
    { DB: fakeAdmissionDb(), BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(wrongMethod.status, 405);
});
