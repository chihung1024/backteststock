import assert from "node:assert/strict";
import test from "node:test";

import router from "../worker/walk_forward_router.js";

const JOB_HASH = "a".repeat(64);

function autoOptimizationRequest() {
  return {
    periods: [{
      periodId: "auto-2026-07",
      trainingStart: "2024-01-01",
      trainingEnd: "2026-06-30",
      decisionDate: "2026-06-30",
      evaluationStart: "2026-07-01",
      evaluationEnd: "2026-07-31",
    }],
    selector: {
      strategy: "dual_momentum",
      riskySymbols: ["SPY", "QQQ", "IWM"],
      defensiveSymbols: ["IEF"],
      parameterOptimization: {
        searchSpace: {
          lookbackMonths: [6, 12],
          topK: [1, 2],
          absoluteThresholds: [0, 0.05],
          allocationMethods: ["equal", "inverse_volatility"],
        },
        innerValidation: {
          foldCount: 3,
          evaluationMonths: 1,
          stepMonths: 1,
        },
      },
    },
    execution: { initialAmountTwd: 100000, transitionCostBps: 5 },
  };
}

function successfulResult(request, jobHash = JOB_HASH) {
  return {
    contractVersion: "walk-forward-dual-momentum-parameter-optimization-job-2026-08-18.1",
    status: "completed",
    jobHash,
    decisions: [{
      decisionHash: "d".repeat(64),
      selectedConstituents: ["SPY"],
      configuredUniverse: { members: ["SPY", "QQQ", "IWM", "IEF"] },
    }],
    request,
    oos: { ledger: { equity: [{ date: "2026-07-01", value: 100000 }] } },
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
          async run() {
            if (sql.includes("INSERT INTO research_libraries")) {
              const [libraryId, capabilityHash, capabilityHashVersion] = args;
              db.libraries.set(libraryId, {
                library_id: libraryId,
                capability_hash: capabilityHash,
                capability_hash_version: capabilityHashVersion,
                created_at: "2026-08-18 00:00:00",
                last_used_at: "2026-08-18 00:00:00",
              });
              return { success: true };
            }
            if (sql.includes("INSERT INTO research_runs")) {
              const hasSourceRun = args.length === 9;
              const [runId, libraryId] = args;
              const offset = hasSourceRun ? 1 : 0;
              db.runs.set(runId, {
                run_id: runId,
                library_id: libraryId,
                source_run_id: hasSourceRun ? args[2] : null,
                name: args[2 + offset],
                job_hash: args[3 + offset],
                execution_request_json: args[4 + offset],
                result_json: args[5 + offset],
                result_contract_version: args[6 + offset],
                decision_count: args[7 + offset],
                created_at: "2026-08-18 00:01:00",
              });
              return { success: true };
            }
            if (sql.includes("UPDATE research_libraries SET last_used_at")) return { success: true };
            throw new Error(`unexpected run query: ${sql}`);
          },
        };
      },
    };
  }

  async batch(statements) {
    const results = [];
    for (const statement of statements) results.push(await statement.run());
    return results;
  }
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

test("ResearchRun rerun replays the exact durable Auto Optimize request instead of winner parameters", async () => {
  const db = new FakeD1();
  const originalRequest = autoOptimizationRequest();

  const first = await withBackend(async (backendRequest) => {
    const body = await backendRequest.json();
    return Response.json(successfulResult(body));
  }, async () => {
    const response = await router.fetch(
      new Request("https://edge.example/api/v1/research/runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: "Auto Optimize durable request", request: originalRequest }),
      }),
      { DB: db, BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    assert.equal(response.status, 201);
    return response.json();
  });

  let replayedRequest = null;
  await withBackend(async (backendRequest) => {
    replayedRequest = await backendRequest.json();
    return Response.json(successfulResult(replayedRequest));
  }, async () => {
    const response = await router.fetch(
      new Request(`https://edge.example/api/v1/research/runs/${first.run.runId}/rerun`, {
        method: "POST",
        headers: { authorization: `Bearer ${first.libraryCapability}` },
      }),
      { DB: db, BACKEND_ORIGIN: "https://backend.example" },
      {},
    );
    assert.equal(response.status, 201);
    const payload = await response.json();
    assert.equal(payload.run.sourceRunId, first.run.runId);
  });

  assert.deepEqual(replayedRequest, originalRequest);
  assert.deepEqual(replayedRequest.selector.parameterOptimization, originalRequest.selector.parameterOptimization);
  assert.equal("lookbackMonths" in replayedRequest.selector, false);
  assert.equal("topK" in replayedRequest.selector, false);
  assert.equal("allocationMethod" in replayedRequest.selector, false);
  assert.equal(db.runs.size, 2);
});
