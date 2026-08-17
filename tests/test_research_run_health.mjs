import assert from "node:assert/strict";
import test from "node:test";

import router from "../worker/walk_forward_router.js";

function healthyDb() {
  return {
    prepare(sql) {
      assert.match(sql, /sqlite_master/u);
      return {
        async all() {
          return { results: [{ name: "research_libraries" }, { name: "research_runs" }] };
        },
      };
    },
  };
}

test("ResearchRun health verifies durable schema without exposing library data", async () => {
  const response = await router.fetch(
    new Request("https://edge.example/api/v1/research/runs/health"),
    { DB: healthyDb(), BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(response.status, 200);
  assert.match(response.headers.get("cache-control") || "", /no-store/u);
  assert.equal(response.headers.get("x-research-run-contract-version"), "research-run-memory-2026-08-17.1");
  const payload = await response.json();
  assert.deepEqual(payload, {
    status: "ok",
    service: "backteststock-research-run-memory-v1",
    contractVersion: "research-run-memory-2026-08-17.1",
    durableStore: "d1",
    schemaReady: true,
  });
  assert.equal("libraryCount" in payload, false);
  assert.equal("runCount" in payload, false);
});

test("ResearchRun health fails closed when DB or schema is unavailable", async () => {
  const missingDb = await router.fetch(
    new Request("https://edge.example/api/v1/research/runs/health"),
    { BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(missingDb.status, 503);

  const missingTable = await router.fetch(
    new Request("https://edge.example/api/v1/research/runs/health"),
    {
      DB: {
        prepare() {
          return { async all() { return { results: [{ name: "research_libraries" }] }; } };
        },
      },
      BACKEND_ORIGIN: "https://backend.example",
    },
    {},
  );
  assert.equal(missingTable.status, 503);
  const payload = await missingTable.json();
  assert.equal(payload.status, "unavailable");
  assert.equal(payload.contractVersion, "research-run-memory-2026-08-17.1");
});

test("ResearchRun health is GET-only", async () => {
  const response = await router.fetch(
    new Request("https://edge.example/api/v1/research/runs/health", { method: "POST" }),
    { DB: healthyDb(), BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(response.status, 405);
});

test("unexpected D1 errors converge to structured ResearchRun 503", async () => {
  const response = await router.fetch(
    new Request("https://edge.example/api/v1/research/runs", {
      headers: { authorization: `Bearer rrl_${"A".repeat(43)}` },
    }),
    {
      DB: {
        prepare() {
          throw new Error("simulated D1 failure");
        },
      },
      BACKEND_ORIGIN: "https://backend.example",
    },
    {},
  );
  assert.equal(response.status, 503);
  assert.match(response.headers.get("cache-control") || "", /no-store/u);
  const payload = await response.json();
  assert.match(payload.error, /durable store/u);
  assert.equal(JSON.stringify(payload).includes("simulated D1 failure"), false);
});
