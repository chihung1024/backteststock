import assert from "node:assert/strict";
import test from "node:test";

import router from "../worker/walk_forward_router.js";
import {
  generateLibraryCapability,
  hashLibraryCapability,
  parseBearerCapability,
} from "../worker/research_runs.js";

const JOB_HASH_A = "a".repeat(64);
const JOB_HASH_B = "b".repeat(64);

function successfulResult(request, jobHash = JOB_HASH_A) {
  return {
    contractVersion: "walk-forward-job-2026-08-15.1",
    status: "completed",
    jobHash,
    decisions: [{
      decisionHash: "d".repeat(64),
      selectedConstituents: ["AMD"],
      pitUniverse: { membershipAuthoritative: true },
    }],
    request,
    oos: { ledger: { equity: [{ date: "2026-08-01", value: 100000 }] } },
  };
}

class FakeD1 {
  constructor() {
    this.libraries = new Map();
    this.runs = new Map();
  }

  prepare(sql) {
    const db = this;
    return {
      bind(...args) {
        return {
          async first() {
            if (sql.includes("FROM research_libraries") && sql.includes("capability_hash = ?1")) {
              const row = [...db.libraries.values()].find((item) => item.capability_hash === args[0]);
              return row ? { ...row } : null;
            }
            if (sql.includes("FROM research_runs") && sql.includes("execution_request_json") && sql.includes("result_json")) {
              const row = db.runs.get(args[1]);
              return row && row.library_id === args[0] ? { ...row } : null;
            }
            if (sql.includes("SELECT run_id, name, execution_request_json")) {
              const row = db.runs.get(args[1]);
              if (!row || row.library_id !== args[0]) return null;
              return {
                run_id: row.run_id,
                name: row.name,
                execution_request_json: row.execution_request_json,
              };
            }
            throw new Error(`unexpected first query: ${sql}`);
          },
          async all() {
            if (sql.includes("FROM research_runs") && sql.includes("ORDER BY created_at DESC")) {
              const limit = Number(args[1]);
              const results = [...db.runs.values()]
                .filter((row) => row.library_id === args[0])
                .sort((left, right) => `${right.created_at}-${right.run_id}`.localeCompare(`${left.created_at}-${left.run_id}`))
                .slice(0, limit)
                .map((row) => ({ ...row }));
              return { results };
            }
            throw new Error(`unexpected all query: ${sql}`);
          },
          async run() {
            if (sql.includes("INSERT INTO research_libraries")) {
              const [libraryId, capabilityHash, capabilityHashVersion] = args;
              if ([...db.libraries.values()].some((item) => item.capability_hash === capabilityHash)) {
                throw new Error("duplicate capability hash");
              }
              db.libraries.set(libraryId, {
                library_id: libraryId,
                capability_hash: capabilityHash,
                capability_hash_version: capabilityHashVersion,
                created_at: "2026-08-17 05:00:00",
                last_used_at: "2026-08-17 05:00:00",
              });
              return { success: true };
            }
            if (sql.includes("INSERT INTO research_runs")) {
              let row;
              if (args.length === 9) {
                const [runId, libraryId, sourceRunId, name, jobHash, requestJson, resultJson, contractVersion, decisionCount] = args;
                row = {
                  run_id: runId,
                  library_id: libraryId,
                  source_run_id: sourceRunId,
                  name,
                  job_hash: jobHash,
                  execution_request_json: requestJson,
                  result_json: resultJson,
                  result_contract_version: contractVersion,
                  decision_count: decisionCount,
                  created_at: "2026-08-17 05:01:00",
                };
              } else {
                const [runId, libraryId, name, jobHash, requestJson, resultJson, contractVersion, decisionCount] = args;
                row = {
                  run_id: runId,
                  library_id: libraryId,
                  source_run_id: null,
                  name,
                  job_hash: jobHash,
                  execution_request_json: requestJson,
                  result_json: resultJson,
                  result_contract_version: contractVersion,
                  decision_count: decisionCount,
                  created_at: "2026-08-17 05:01:00",
                };
              }
              if (!db.libraries.has(row.library_id)) throw new Error("missing library");
              db.runs.set(row.run_id, row);
              return { success: true };
            }
            if (sql.includes("UPDATE research_libraries SET last_used_at")) {
              const row = db.libraries.get(args[0]);
              if (row) row.last_used_at = "2026-08-17 05:02:00";
              return { success: true };
            }
            throw new Error(`unexpected run query: ${sql}`);
          },
        };
      },
    };
  }

  async batch(statements) {
    const librariesBackup = new Map([...this.libraries].map(([key, value]) => [key, { ...value }]));
    const runsBackup = new Map([...this.runs].map(([key, value]) => [key, { ...value }]));
    try {
      const results = [];
      for (const statement of statements) results.push(await statement.run());
      return results;
    } catch (error) {
      this.libraries = librariesBackup;
      this.runs = runsBackup;
      throw error;
    }
  }
}

function sampleRequest(symbol = "soxx") {
  return {
    periods: [{
      periodId: "period-1",
      trainingStart: "2024-07-29",
      trainingEnd: "2026-07-29",
      decisionDate: "2026-07-29",
      evaluationStart: "2026-07-30",
      evaluationEnd: "2026-08-16",
    }],
    selector: { universe: symbol, benchmark: "SPY", holdingCount: 5 },
    execution: { initialAmountTwd: 100000, transitionCostBps: 5 },
  };
}

async function withBackend(handler, callback) {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (input, init) => handler(input instanceof Request ? input : new Request(input, init));
  try {
    return await callback();
  } finally {
    globalThis.fetch = originalFetch;
  }
}

async function createLibraryRun(db, request = sampleRequest(), name = "Baseline") {
  return withBackend(async (backendRequest) => {
    const body = await backendRequest.json();
    return Response.json(successfulResult(body));
  }, async () => {
    const response = await router.fetch(
      new Request("https://edge.example/api/v1/research/runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name, request }),
      }),
      { DB: db, BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    const payload = await response.json();
    return { response, payload };
  });
}

test("capabilities use 256-bit opaque tokens and only hashes are durable lookup material", async () => {
  const capability = generateLibraryCapability();
  assert.match(capability, /^rrl_[A-Za-z0-9_-]{43}$/u);
  const hash = await hashLibraryCapability(capability);
  assert.match(hash, /^[0-9a-f]{64}$/u);
  assert.notEqual(hash, capability);
  const parsed = parseBearerCapability(new Request("https://edge.example", {
    headers: { authorization: `Bearer ${capability}` },
  }));
  assert.equal(parsed.provided, true);
  assert.equal(parsed.capability, capability);
});

test("first successful run creates a durable library, returns capability once, and supports list/detail", async () => {
  const db = new FakeD1();
  const request = sampleRequest();
  const { response, payload } = await createLibraryRun(db, request, "SOXX baseline");

  assert.equal(response.status, 201);
  assert.equal(payload.contractVersion, "research-run-memory-2026-08-17.1");
  assert.match(payload.libraryCapability, /^rrl_[A-Za-z0-9_-]{43}$/u);
  assert.match(payload.run.runId, /^run_[0-9a-f-]+$/u);
  assert.equal(payload.run.jobHash, JOB_HASH_A);
  assert.equal(db.libraries.size, 1);
  assert.equal(db.runs.size, 1);
  const durableLibrary = [...db.libraries.values()][0];
  assert.equal(durableLibrary.capability_hash, await hashLibraryCapability(payload.libraryCapability));
  assert.equal(JSON.stringify(durableLibrary).includes(payload.libraryCapability), false);

  const authorization = `Bearer ${payload.libraryCapability}`;
  const listResponse = await router.fetch(
    new Request("https://edge.example/api/v1/research/runs", { headers: { authorization } }),
    { DB: db, BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(listResponse.status, 200);
  const list = await listResponse.json();
  assert.equal(list.runs.length, 1);
  assert.equal(list.runs[0].runId, payload.run.runId);
  assert.equal("libraryCapability" in list, false);

  const detailResponse = await router.fetch(
    new Request(`https://edge.example/api/v1/research/runs/${payload.run.runId}`, { headers: { authorization } }),
    { DB: db, BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(detailResponse.status, 200);
  const detail = await detailResponse.json();
  assert.deepEqual(detail.executionRequest, request);
  assert.equal(detail.result.jobHash, JOB_HASH_A);
});

test("trusted ResearchRun execution preserves Cloudflare client identity without forwarding browser credentials", async () => {
  const db = new FakeD1();
  const first = await createLibraryRun(db);
  assert.equal(first.response.status, 201);
  let forwardedHeaders;
  await withBackend(async (backendRequest) => {
    forwardedHeaders = new Headers(backendRequest.headers);
    const body = await backendRequest.json();
    return Response.json(successfulResult(body, JOB_HASH_B));
  }, async () => {
    const response = await router.fetch(
      new Request("https://edge.example/api/v1/research/runs", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: `Bearer ${first.payload.libraryCapability}`,
          cookie: "browser=secret",
          "cf-connecting-ip": "203.0.113.24",
          "x-forwarded-for": "198.51.100.99",
        },
        body: JSON.stringify({ name: "Per-client limiter context", request: sampleRequest("smh") }),
      }),
      { DB: db, BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    assert.equal(response.status, 201);
  });
  assert.equal(forwardedHeaders.get("x-forwarded-for"), "203.0.113.24");
  assert.equal(forwardedHeaders.get("authorization"), null);
  assert.equal(forwardedHeaders.get("cookie"), null);
});

test("failed Walk-Forward execution creates neither empty library nor partial run", async () => {
  const db = new FakeD1();
  await withBackend(async () => Response.json({ error: "causal evidence unavailable" }, { status: 422 }), async () => {
    const response = await router.fetch(
      new Request("https://edge.example/api/v1/research/runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: "Must fail", request: sampleRequest() }),
      }),
      { DB: db, BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    assert.equal(response.status, 422);
  });
  assert.equal(db.libraries.size, 0);
  assert.equal(db.runs.size, 0);
});

test("completed result larger than the safe D1 row budget fails before persistence", async () => {
  const db = new FakeD1();
  await withBackend(async (backendRequest) => {
    const body = await backendRequest.json();
    return Response.json({
      ...successfulResult(body),
      padding: "x".repeat(1_850_000),
    });
  }, async () => {
    const response = await router.fetch(
      new Request("https://edge.example/api/v1/research/runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: "Too large for one D1 row", request: sampleRequest() }),
      }),
      { DB: db, BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    assert.equal(response.status, 413);
    const payload = await response.json();
    assert.match(payload.error, /超過 ResearchRun V1 可保存大小/u);
  });
  assert.equal(db.libraries.size, 0);
  assert.equal(db.runs.size, 0);
});

test("browser cannot submit completed result evidence for persistence", async () => {
  const db = new FakeD1();
  let backendCalls = 0;
  await withBackend(async () => {
    backendCalls += 1;
    return Response.json(successfulResult(sampleRequest()));
  }, async () => {
    const response = await router.fetch(
      new Request("https://edge.example/api/v1/research/runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          name: "Forged",
          request: sampleRequest(),
          result: successfulResult(sampleRequest()),
          jobHash: JOB_HASH_B,
        }),
      }),
      { DB: db, BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    assert.equal(response.status, 400);
  });
  assert.equal(backendCalls, 0);
  assert.equal(db.libraries.size, 0);
  assert.equal(db.runs.size, 0);
});

test("existing library bearer is consumed at the edge and never forwarded to Walk-Forward backend", async () => {
  const db = new FakeD1();
  const first = await createLibraryRun(db);
  const authorization = `Bearer ${first.payload.libraryCapability}`;
  let backendAuthorization = "not-checked";
  let backendCookie = "not-checked";

  await withBackend(async (backendRequest) => {
    backendAuthorization = backendRequest.headers.get("authorization");
    backendCookie = backendRequest.headers.get("cookie");
    const body = await backendRequest.json();
    return Response.json(successfulResult(body, JOB_HASH_B));
  }, async () => {
    const response = await router.fetch(
      new Request("https://edge.example/api/v1/research/runs", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization,
          cookie: "session=must-not-forward",
        },
        body: JSON.stringify({ name: "Second", request: sampleRequest() }),
      }),
      { DB: db, BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    assert.equal(response.status, 201);
    const payload = await response.json();
    assert.equal(payload.run.jobHash, JOB_HASH_B);
    assert.equal("libraryCapability" in payload, false);
  });

  assert.equal(backendAuthorization, null);
  assert.equal(backendCookie, null);
  assert.equal(db.libraries.size, 1);
  assert.equal(db.runs.size, 2);
});

test("rerun is bound to D1 accepted request and creates a new run with source identity", async () => {
  const db = new FakeD1();
  const originalRequest = sampleRequest("soxx");
  const first = await createLibraryRun(db, originalRequest, "Rerunnable");
  const authorization = `Bearer ${first.payload.libraryCapability}`;
  let executedRequest = null;

  await withBackend(async (backendRequest) => {
    executedRequest = await backendRequest.json();
    return Response.json(successfulResult(executedRequest, JOB_HASH_A));
  }, async () => {
    const response = await router.fetch(
      new Request(`https://edge.example/api/v1/research/runs/${first.payload.run.runId}/rerun`, {
        method: "POST",
        headers: { authorization },
      }),
      { DB: db, BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    assert.equal(response.status, 201);
    const payload = await response.json();
    assert.equal(payload.run.sourceRunId, first.payload.run.runId);
    assert.notEqual(payload.run.runId, first.payload.run.runId);
  });
  assert.deepEqual(executedRequest, originalRequest);
  assert.equal(db.runs.size, 2);

  const replacementResponse = await router.fetch(
    new Request(`https://edge.example/api/v1/research/runs/${first.payload.run.runId}/rerun`, {
      method: "POST",
      headers: { authorization, "content-type": "application/json" },
      body: JSON.stringify({ request: sampleRequest("sp500") }),
    }),
    { DB: db, BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(replacementResponse.status, 400);
});

test("wrong capability is unauthorized and a valid different library sees foreign run as not found", async () => {
  const db = new FakeD1();
  const first = await createLibraryRun(db, sampleRequest(), "Library A");
  const second = await createLibraryRun(db, sampleRequest(), "Library B");

  const wrongCapability = generateLibraryCapability();
  const unauthorized = await router.fetch(
    new Request("https://edge.example/api/v1/research/runs", {
      headers: { authorization: `Bearer ${wrongCapability}` },
    }),
    { DB: db, BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(unauthorized.status, 401);

  const crossLibrary = await router.fetch(
    new Request(`https://edge.example/api/v1/research/runs/${first.payload.run.runId}`, {
      headers: { authorization: `Bearer ${second.payload.libraryCapability}` },
    }),
    { DB: db, BACKEND_ORIGIN: "https://backend.example" },
    {},
  );
  assert.equal(crossLibrary.status, 404);
});
