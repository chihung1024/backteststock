import {
  RESEARCH_RUN_MEMORY_CONTRACT_VERSION,
  RESEARCH_RUNS_PATH,
} from "./research_runs.js";

const RESEARCH_RUN_HEALTH_PATH = `${RESEARCH_RUNS_PATH}/health`;

function jsonResponse(payload, status, requestId) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "x-request-id": requestId,
      "x-research-run-contract-version": RESEARCH_RUN_MEMORY_CONTRACT_VERSION,
    },
  });
}

async function getResearchRunHealth(env, requestId) {
  if (!env.DB) {
    return jsonResponse({
      status: "unavailable",
      service: "backteststock-research-run-memory-v1",
      contractVersion: RESEARCH_RUN_MEMORY_CONTRACT_VERSION,
      error: "ResearchRun durable database is not configured.",
    }, 503, requestId);
  }
  try {
    const result = await env.DB.prepare(
      `SELECT name
       FROM sqlite_master
       WHERE type = 'table'
         AND name IN ('research_libraries', 'research_runs')
       ORDER BY name`,
    ).all();
    const tables = new Set((result.results || []).map((row) => row.name));
    if (!tables.has("research_libraries") || !tables.has("research_runs")) {
      return jsonResponse({
        status: "unavailable",
        service: "backteststock-research-run-memory-v1",
        contractVersion: RESEARCH_RUN_MEMORY_CONTRACT_VERSION,
        error: "ResearchRun durable schema is not ready.",
      }, 503, requestId);
    }
    return jsonResponse({
      status: "ok",
      service: "backteststock-research-run-memory-v1",
      contractVersion: RESEARCH_RUN_MEMORY_CONTRACT_VERSION,
      durableStore: "d1",
      schemaReady: true,
    }, 200, requestId);
  } catch (error) {
    console.error("ResearchRun health check failed", { requestId, message: String(error) });
    return jsonResponse({
      status: "unavailable",
      service: "backteststock-research-run-memory-v1",
      contractVersion: RESEARCH_RUN_MEMORY_CONTRACT_VERSION,
      error: "ResearchRun durable schema is unavailable.",
    }, 503, requestId);
  }
}

export {
  RESEARCH_RUN_HEALTH_PATH,
  getResearchRunHealth,
};
