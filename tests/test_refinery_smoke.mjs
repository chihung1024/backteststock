import assert from "node:assert/strict";
import test from "node:test";

import {
  CLUSTERING_CONTRACT_VERSION,
  FACTOR_CORROBORATION_POLICY,
  FACTOR_MODEL_SCOPE,
  REFINERY_CONTRACT_VERSION,
  REFINERY_SCHEMA_VERSION,
  runRefinerySmoke,
} from "../scripts/smoke_test_refinery_v1.mjs";

function methodology() {
  return {
    clustering_contract_version: CLUSTERING_CONTRACT_VERSION,
    factor_monthly_return_policy: "boundary-month-exclusion-v1",
    factor_relationship_sample_policy: "global_common_monthly_sample_v1",
    factor_corroboration_policy: FACTOR_CORROBORATION_POLICY,
  };
}

function dataset() {
  return {
    requested_symbols: ["AAPL", "MSFT"],
    resolved_symbols: ["AAPL", "MSFT"],
    effective_start: "2021-01-04",
    effective_end: "2025-12-31",
  };
}

function factorAsset() {
  return {
    status: "ok",
    factor_computable: true,
    factor_model_scope: FACTOR_MODEL_SCOPE,
    factor_corroboration_eligible: false,
    factor_corroboration_reason: "unavailable_no_traceable_instrument_scope",
  };
}

function preflightPayload() {
  return {
    contract_version: REFINERY_CONTRACT_VERSION,
    schema_version: REFINERY_SCHEMA_VERSION,
    endpoint: "preflight",
    status: "ready",
    methodology: methodology(),
    dataset: dataset(),
  };
}

function analyzePayload({ factorEligible = false } = {}) {
  const assetA = factorAsset();
  const assetB = factorAsset();
  if (factorEligible) assetA.factor_corroboration_eligible = true;
  return {
    contract_version: REFINERY_CONTRACT_VERSION,
    schema_version: REFINERY_SCHEMA_VERSION,
    endpoint: "analyze",
    status: "ok",
    methodology: methodology(),
    dataset: dataset(),
    analysis: {
      clustering: {
        status: "ok",
        bootstrap_input_fingerprint_sha256: "a".repeat(64),
        primary: { method: "average" },
        sensitivity: { method: "complete" },
        bootstrap: { requested_replicates: 200 },
      },
      redundancy: {
        status: "ok",
        magic_numeric_score: false,
        counts: { HIGH: 0, MEDIUM: 1, LOW: 0, UNCERTAIN: 0 },
        pairs: [
          {
            symbol_a: "AAPL",
            symbol_b: "MSFT",
            verdict: "MEDIUM",
            factor_corroboration_eligible: false,
          },
        ],
      },
      factor_relationships: {
        status: "ok",
        factor_model_scope: FACTOR_MODEL_SCOPE,
        factor_corroboration_policy: FACTOR_CORROBORATION_POLICY,
        assets: { AAPL: assetA, MSFT: assetB },
        systematic_relationship: {
          status: "ok",
          observations: 48,
          sample_fingerprint_sha256: "b".repeat(64),
        },
      },
      theme_relationships: {
        status: "unavailable_no_traceable_theme_source",
      },
    },
  };
}

function jsonResponse(payload, responseRequestId) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "x-refinery-api-schema-version": REFINERY_SCHEMA_VERSION,
      "x-request-id": responseRequestId,
    },
  });
}

function fakeFetchFactory(analyzeOptions = {}, responseRequestIds = ["worker-preflight-id", "worker-analyze-id"]) {
  const requests = [];
  let responseIndex = 0;
  const fetchImpl = async (url, options) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: options.method,
      body: JSON.parse(options.body),
      clientRequestId: options.headers["x-request-id"],
    });
    const responseRequestId = responseRequestIds[responseIndex] || `worker-id-${responseIndex}`;
    responseIndex += 1;
    if (parsed.pathname.endsWith("/preflight")) {
      return jsonResponse(preflightPayload(), responseRequestId);
    }
    if (parsed.pathname.endsWith("/analyze")) {
      return jsonResponse(analyzePayload(analyzeOptions), responseRequestId);
    }
    return new Response(JSON.stringify({ error: "unexpected path" }), { status: 404 });
  };
  return { fetchImpl, requests };
}

test("Refinery smoke exercises bounded preflight and analyze contracts through Worker request IDs", async () => {
  const { fetchImpl, requests } = fakeFetchFactory(
    {},
    ["worker-generated-preflight", "worker-generated-analyze"],
  );
  const summary = await runRefinerySmoke("https://example.test/path", {
    fetchImpl,
    requestTimeoutMs: 5_000,
  });

  assert.equal(requests.length, 2);
  assert.deepEqual(
    requests.map((request) => request.path),
    ["/api/v1/refinery/preflight", "/api/v1/refinery/analyze"],
  );
  assert.ok(requests.every((request) => request.method === "POST"));
  assert.ok(requests.every((request) => request.clientRequestId === undefined));
  assert.ok(requests.every((request) => request.body.contract_version === REFINERY_CONTRACT_VERSION));
  assert.ok(requests.every((request) => request.body.symbols.join(",") === "AAPL,MSFT"));
  assert.equal(summary.schemaVersion, REFINERY_SCHEMA_VERSION);
  assert.equal(summary.clusteringContractVersion, CLUSTERING_CONTRACT_VERSION);
  assert.equal(summary.preflightRequestId, "worker-generated-preflight");
  assert.equal(summary.analyzeRequestId, "worker-generated-analyze");
});

test("Refinery smoke retries a transient request failure before validating the contract", async () => {
  let calls = 0;
  const fetchImpl = async (url) => {
    calls += 1;
    if (calls === 1) {
      return new Response(JSON.stringify({ error: "temporary upstream failure" }), {
        status: 502,
        headers: { "content-type": "application/json" },
      });
    }
    const parsed = new URL(url);
    const payload = parsed.pathname.endsWith("/preflight") ? preflightPayload() : analyzePayload();
    return jsonResponse(payload, `worker-retry-${calls}`);
  };

  const summary = await runRefinerySmoke("https://example.test", {
    fetchImpl,
    requestTimeoutMs: 5_000,
    attempts: 2,
  });
  assert.equal(calls, 3);
  assert.equal(summary.status, "ok");
});

test("Refinery smoke rejects factor corroboration eligibility without scope authority", async () => {
  const { fetchImpl } = fakeFetchFactory({ factorEligible: true });
  await assert.rejects(
    runRefinerySmoke("https://example.test", { fetchImpl, requestTimeoutMs: 5_000 }),
    /AAPL factor evidence unexpectedly became verdict-eligible/,
  );
});

test("Refinery smoke rejects responses that expose traceback text", async () => {
  const fetchImpl = async () => new Response(
    JSON.stringify({ error: "Traceback: internal secret" }),
    {
      status: 502,
      headers: {
        "content-type": "application/json",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
        "x-refinery-api-schema-version": REFINERY_SCHEMA_VERSION,
        "x-request-id": "worker-error-id",
      },
    },
  );
  await assert.rejects(
    runRefinerySmoke("https://example.test", {
      fetchImpl,
      requestTimeoutMs: 5_000,
      attempts: 1,
    }),
    /exposed a traceback/,
  );
});

test("Refinery smoke rejects an otherwise valid response without a traceable Worker request ID", async () => {
  const fetchImpl = async (url) => {
    const parsed = new URL(url);
    const payload = parsed.pathname.endsWith("/preflight") ? preflightPayload() : analyzePayload();
    return new Response(JSON.stringify(payload), {
      status: 200,
      headers: {
        "content-type": "application/json",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
        "x-refinery-api-schema-version": REFINERY_SCHEMA_VERSION,
      },
    });
  };
  await assert.rejects(
    runRefinerySmoke("https://example.test", {
      fetchImpl,
      requestTimeoutMs: 5_000,
      attempts: 1,
    }),
    /missing a traceable x-request-id/,
  );
});
