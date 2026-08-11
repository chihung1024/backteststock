import { pathToFileURL } from "node:url";

export const REFINERY_CONTRACT_VERSION = "refinery-v1";
export const REFINERY_SCHEMA_VERSION = "refinery-v1-2026-08-10.3";
export const CLUSTERING_CONTRACT_VERSION = "refinery-clustering-twd-2026-08-10.2";
export const FACTOR_MODEL_SCOPE = "U.S.-factor co-movement diagnostic";
export const FACTOR_CORROBORATION_POLICY = "fail_closed_without_traceable_instrument_scope_v1";

export const REFINERY_SMOKE_REQUEST = Object.freeze({
  contract_version: REFINERY_CONTRACT_VERSION,
  symbols: ["AAPL", "MSFT"],
  benchmark: "SPY",
  start_date: "2021-01-04",
  end_date: "2025-12-31",
});

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function positiveNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function assertSecureResponse(response) {
  assert(
    response.headers.get("cache-control")?.toLowerCase().includes("no-store"),
    "Refinery response is missing cache-control: no-store",
  );
  assert(
    response.headers.get("x-content-type-options")?.toLowerCase() === "nosniff",
    "Refinery response is missing x-content-type-options: nosniff",
  );
  assert(
    response.headers.get("x-refinery-api-schema-version") === REFINERY_SCHEMA_VERSION,
    "Refinery schema response header does not match the Phase 5 schema",
  );
  const requestId = String(response.headers.get("x-request-id") || "").trim();
  assert(requestId.length > 0, "Refinery response is missing a traceable x-request-id");
  return requestId;
}

function assertNoSensitiveFailureText(text) {
  const normalized = text.toLowerCase();
  assert(!normalized.includes("traceback"), "Refinery response exposed a traceback");
  assert(!normalized.includes("environment variable"), "Refinery response exposed environment detail");
}

async function requestJson(fetchImpl, origin, path, body, requestTimeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const response = await fetchImpl(new URL(path, origin), {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const text = await response.text();
    assertNoSensitiveFailureText(text);
    let payload;
    try {
      payload = JSON.parse(text);
    } catch (error) {
      throw new Error(`${path} did not return JSON: ${text.slice(0, 500)}`, { cause: error });
    }
    if (!response.ok) {
      throw new Error(`${path} returned HTTP ${response.status}: ${text.slice(0, 500)}`);
    }
    const requestId = assertSecureResponse(response);
    return { payload, requestId };
  } finally {
    clearTimeout(timeout);
  }
}

function assertCommonContract(payload, endpoint) {
  assert(payload?.contract_version === REFINERY_CONTRACT_VERSION, `${endpoint} contract mismatch`);
  assert(payload?.schema_version === REFINERY_SCHEMA_VERSION, `${endpoint} schema mismatch`);
  assert(payload?.endpoint === endpoint, `${endpoint} endpoint marker mismatch`);
  assert(
    payload?.methodology?.clustering_contract_version === CLUSTERING_CONTRACT_VERSION,
    `${endpoint} clustering methodology mismatch`,
  );
  assert(
    payload?.methodology?.factor_monthly_return_policy === "boundary-month-exclusion-v1",
    `${endpoint} boundary-month policy mismatch`,
  );
  assert(
    payload?.methodology?.factor_relationship_sample_policy === "global_common_monthly_sample_v1",
    `${endpoint} factor relationship sample policy mismatch`,
  );
  assert(
    payload?.methodology?.factor_corroboration_policy === FACTOR_CORROBORATION_POLICY,
    `${endpoint} factor corroboration policy mismatch`,
  );
  assert(
    JSON.stringify(payload?.dataset?.requested_symbols) === JSON.stringify(["AAPL", "MSFT"]),
    `${endpoint} requested candidate membership mismatch`,
  );
  assert(
    JSON.stringify(payload?.dataset?.resolved_symbols) === JSON.stringify(["AAPL", "MSFT"]),
    `${endpoint} resolved candidate membership mismatch`,
  );
}

function assertAnalyzeContract(payload) {
  assert(payload?.status === "ok", "Refinery analyze did not complete formal analysis");
  const analysis = payload.analysis;
  assert(analysis && typeof analysis === "object", "Refinery analyze returned no analysis payload");

  const clustering = analysis.clustering;
  assert(clustering?.status === "ok", "Phase 5 clustering is not available in production");
  assert(clustering?.primary?.method === "average", "Primary clustering method is not average linkage");
  assert(clustering?.sensitivity?.method === "complete", "Sensitivity clustering method is not complete linkage");
  assert(
    clustering?.bootstrap?.requested_replicates === 200,
    "Phase 5 bootstrap replicate contract mismatch",
  );
  assert(
    typeof clustering?.bootstrap_input_fingerprint_sha256 === "string"
      && clustering.bootstrap_input_fingerprint_sha256.length === 64,
    "Phase 5 effective bootstrap input fingerprint is missing",
  );

  const redundancy = analysis.redundancy;
  assert(redundancy?.status === "ok", "Phase 5 redundancy evidence is unavailable");
  assert(Array.isArray(redundancy?.pairs) && redundancy.pairs.length === 1, "Expected exactly one redundancy pair");
  assert(redundancy?.magic_numeric_score === false, "A forbidden numeric redundancy score appeared");
  assert(
    Object.values(redundancy?.counts || {}).reduce((sum, value) => sum + Number(value || 0), 0) === 1,
    "Redundancy verdict counts do not match the two-candidate smoke set",
  );
  assert(
    redundancy.pairs[0]?.factor_corroboration_eligible === false,
    "Factor evidence became verdict-eligible without traceable instrument-scope authority",
  );

  const factors = analysis.factor_relationships;
  assert(factors?.factor_model_scope === FACTOR_MODEL_SCOPE, "Factor model scope mismatch");
  assert(
    factors?.factor_corroboration_policy === FACTOR_CORROBORATION_POLICY,
    "Factor corroboration policy mismatch",
  );
  for (const symbol of ["AAPL", "MSFT"]) {
    assert(factors?.assets?.[symbol], `Factor diagnostic evidence missing for ${symbol}`);
    assert(
      factors.assets[symbol].factor_corroboration_eligible === false,
      `${symbol} factor evidence unexpectedly became verdict-eligible`,
    );
    assert(
      factors.assets[symbol].factor_model_scope === FACTOR_MODEL_SCOPE,
      `${symbol} factor model scope mismatch`,
    );
  }

  assert(
    analysis?.theme_relationships?.status === "unavailable_no_traceable_theme_source",
    "Theme evidence no longer fails closed without a traceable source",
  );
}

export async function runRefinerySmoke(originArgument, options = {}) {
  assert(originArgument, "Refinery smoke requires a Worker origin");
  const origin = new URL(originArgument).origin;
  const fetchImpl = options.fetchImpl || fetch;
  const requestTimeoutMs = positiveNumber(
    options.requestTimeoutMs ?? process.env.REFINERY_REQUEST_TIMEOUT_MS,
    240_000,
  );

  const preflightResponse = await requestJson(
    fetchImpl,
    origin,
    "/api/v1/refinery/preflight",
    REFINERY_SMOKE_REQUEST,
    requestTimeoutMs,
  );
  const preflight = preflightResponse.payload;
  assertCommonContract(preflight, "preflight");
  assert(preflight.status === "ready", "Refinery preflight is not ready for the bounded smoke set");

  const analyzeResponse = await requestJson(
    fetchImpl,
    origin,
    "/api/v1/refinery/analyze",
    REFINERY_SMOKE_REQUEST,
    requestTimeoutMs,
  );
  const analyze = analyzeResponse.payload;
  assertCommonContract(analyze, "analyze");
  assertAnalyzeContract(analyze);

  const summary = {
    origin,
    contractVersion: analyze.contract_version,
    schemaVersion: analyze.schema_version,
    clusteringContractVersion: analyze.methodology.clustering_contract_version,
    status: analyze.status,
    symbols: analyze.dataset.resolved_symbols,
    effectiveStart: analyze.dataset.effective_start,
    effectiveEnd: analyze.dataset.effective_end,
    preflightRequestId: preflightResponse.requestId,
    analyzeRequestId: analyzeResponse.requestId,
    clusteringStatus: analyze.analysis.clustering.status,
    redundancyVerdict: analyze.analysis.redundancy.pairs[0]?.verdict ?? null,
    factorStatus: analyze.analysis.factor_relationships.status,
    factorRelationshipStatus: analyze.analysis.factor_relationships.systematic_relationship?.status ?? null,
  };
  console.log(JSON.stringify(summary, null, 2));
  return summary;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const originArgument = process.argv[2];
  if (!originArgument) {
    throw new Error("Usage: node scripts/smoke_test_refinery_v1.mjs <worker-origin>");
  }
  await runRefinerySmoke(originArgument);
}
