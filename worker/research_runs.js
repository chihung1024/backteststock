const RESEARCH_RUNS_PATH = "/api/v1/research/runs";
const RESEARCH_RUN_MEMORY_CONTRACT_VERSION = "research-run-memory-2026-08-17.1";
const CAPABILITY_HASH_VERSION = "sha256-v1";
const CAPABILITY_PREFIX = "rrl_";
const CREATE_REQUEST_MAX_BYTES = 160 * 1024;
const STORED_RESULT_MAX_BYTES = 4 * 1024 * 1024;
const DEFAULT_LIST_LIMIT = 50;
const MAX_LIST_LIMIT = 100;

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

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function utf8Bytes(value) {
  return new TextEncoder().encode(value).byteLength;
}

function bytesToBase64Url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/u, "");
}

function generateLibraryCapability() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return `${CAPABILITY_PREFIX}${bytesToBase64Url(bytes)}`;
}

async function hashLibraryCapability(capability) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(capability));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function parseBearerCapability(request) {
  const header = request.headers.get("authorization");
  if (!header) return { provided: false, capability: null };
  const match = /^Bearer\s+([^\s]+)$/iu.exec(header.trim());
  if (!match || !new RegExp(`^${CAPABILITY_PREFIX}[A-Za-z0-9_-]{43}$`, "u").test(match[1])) {
    return { provided: true, capability: null };
  }
  return { provided: true, capability: match[1] };
}

async function readBoundedJson(request, requestId) {
  const declared = Number(request.headers.get("content-length") || "0");
  if (declared > CREATE_REQUEST_MAX_BYTES) {
    return jsonResponse({ error: "ResearchRun 請求內容過大。" }, 413, requestId);
  }
  const text = await request.text();
  if (utf8Bytes(text) > CREATE_REQUEST_MAX_BYTES) {
    return jsonResponse({ error: "ResearchRun 請求內容過大。" }, 413, requestId);
  }
  try {
    return JSON.parse(text || "{}");
  } catch {
    return jsonResponse({ error: "ResearchRun 請求必須是有效 JSON。" }, 400, requestId);
  }
}

function validateCreatePayload(payload, requestId) {
  if (!isObject(payload)) {
    return jsonResponse({ error: "ResearchRun 請求格式無效。" }, 400, requestId);
  }
  for (const forbidden of ["result", "jobHash", "decisionHash", "metrics", "ledger"]) {
    if (Object.prototype.hasOwnProperty.call(payload, forbidden)) {
      return jsonResponse({ error: "完成結果只能由可信任的 Walk-Forward 執行產生，不接受瀏覽器提交。" }, 400, requestId);
    }
  }
  const name = typeof payload.name === "string" ? payload.name.trim() : "";
  if (!name || name.length > 120) {
    return jsonResponse({ error: "研究名稱必須是 1–120 個字元。" }, 422, requestId);
  }
  if (!isObject(payload.request)) {
    return jsonResponse({ error: "缺少有效的 Walk-Forward request。" }, 422, requestId);
  }
  return { name, executionRequest: payload.request };
}

async function findLibraryByCapability(env, capability) {
  const capabilityHash = await hashLibraryCapability(capability);
  const row = await env.DB.prepare(
    `SELECT library_id, capability_hash_version, created_at, last_used_at
     FROM research_libraries
     WHERE capability_hash = ?1`,
  ).bind(capabilityHash).first();
  if (!row || row.capability_hash_version !== CAPABILITY_HASH_VERSION) return null;
  return row;
}

async function authorizeLibrary(request, env, requestId, { optional = false } = {}) {
  const parsed = parseBearerCapability(request);
  if (!parsed.provided && optional) return { library: null, capability: null };
  if (!parsed.capability) {
    return jsonResponse({ error: "需要有效的 Research Library 復原碼。" }, 401, requestId);
  }
  const library = await findLibraryByCapability(env, parsed.capability);
  if (!library) {
    return jsonResponse({ error: "Research Library 復原碼無效。" }, 401, requestId);
  }
  return { library, capability: parsed.capability };
}

async function readExecutionResponse(response, requestId) {
  const text = await response.text();
  if (utf8Bytes(text) > STORED_RESULT_MAX_BYTES) {
    return jsonResponse({ error: "完成研究結果超過 ResearchRun V1 可保存大小。" }, 413, requestId);
  }
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    return jsonResponse({ error: "Walk-Forward 完成結果不是有效 JSON，未保存 ResearchRun。" }, 502, requestId);
  }
  if (!response.ok) {
    return jsonResponse(
      isObject(payload) ? payload : { error: "Walk-Forward 執行失敗，未保存 ResearchRun。" },
      response.status,
      requestId,
    );
  }
  if (
    !isObject(payload)
    || payload.status !== "completed"
    || typeof payload.jobHash !== "string"
    || !/^[0-9a-f]{64}$/u.test(payload.jobHash)
    || typeof payload.contractVersion !== "string"
    || !Array.isArray(payload.decisions)
    || payload.decisions.length < 1
  ) {
    return jsonResponse({ error: "Walk-Forward 未回傳可保存的 completed research evidence。" }, 502, requestId);
  }
  return { payload, text };
}

function runSummary(row) {
  return {
    runId: row.run_id,
    sourceRunId: row.source_run_id ?? null,
    name: row.name,
    jobHash: row.job_hash,
    resultContractVersion: row.result_contract_version,
    decisionCount: Number(row.decision_count),
    createdAt: row.created_at,
  };
}

async function persistCompletedRun(env, {
  library,
  newCapability,
  name,
  executionRequest,
  result,
  resultText,
  sourceRunId = null,
}) {
  const runId = `run_${crypto.randomUUID()}`;
  const executionRequestJson = JSON.stringify(executionRequest);
  if (library) {
    await env.DB.batch([
      env.DB.prepare(
        `INSERT INTO research_runs (
           run_id, library_id, source_run_id, name, job_hash,
           execution_request_json, result_json, result_contract_version, decision_count
         ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)`,
      ).bind(
        runId,
        library.library_id,
        sourceRunId,
        name,
        result.jobHash,
        executionRequestJson,
        resultText,
        result.contractVersion,
        result.decisions.length,
      ),
      env.DB.prepare(
        `UPDATE research_libraries SET last_used_at = CURRENT_TIMESTAMP WHERE library_id = ?1`,
      ).bind(library.library_id),
    ]);
    return { runId, libraryId: library.library_id, libraryCapability: null };
  }

  const libraryId = `lib_${crypto.randomUUID()}`;
  const capabilityHash = await hashLibraryCapability(newCapability);
  await env.DB.batch([
    env.DB.prepare(
      `INSERT INTO research_libraries (
         library_id, capability_hash, capability_hash_version
       ) VALUES (?1, ?2, ?3)`,
    ).bind(libraryId, capabilityHash, CAPABILITY_HASH_VERSION),
    env.DB.prepare(
      `INSERT INTO research_runs (
         run_id, library_id, source_run_id, name, job_hash,
         execution_request_json, result_json, result_contract_version, decision_count
       ) VALUES (?1, ?2, NULL, ?3, ?4, ?5, ?6, ?7, ?8)`,
    ).bind(
      runId,
      libraryId,
      name,
      result.jobHash,
      executionRequestJson,
      resultText,
      result.contractVersion,
      result.decisions.length,
    ),
  ]);
  return { runId, libraryId, libraryCapability: newCapability };
}

async function createRun(request, env, requestId, executeWalkForward) {
  const auth = await authorizeLibrary(request, env, requestId, { optional: true });
  if (auth instanceof Response) return auth;
  const body = await readBoundedJson(request, requestId);
  if (body instanceof Response) return body;
  const validated = validateCreatePayload(body, requestId);
  if (validated instanceof Response) return validated;

  const executionResponse = await executeWalkForward(validated.executionRequest);
  const completed = await readExecutionResponse(executionResponse, requestId);
  if (completed instanceof Response) return completed;

  const newCapability = auth.library ? null : generateLibraryCapability();
  try {
    const persisted = await persistCompletedRun(env, {
      library: auth.library,
      newCapability,
      name: validated.name,
      executionRequest: validated.executionRequest,
      result: completed.payload,
      resultText: completed.text,
    });
    return jsonResponse(
      {
        contractVersion: RESEARCH_RUN_MEMORY_CONTRACT_VERSION,
        libraryId: persisted.libraryId,
        ...(persisted.libraryCapability ? { libraryCapability: persisted.libraryCapability } : {}),
        run: {
          runId: persisted.runId,
          sourceRunId: null,
          name: validated.name,
          jobHash: completed.payload.jobHash,
          resultContractVersion: completed.payload.contractVersion,
          decisionCount: completed.payload.decisions.length,
        },
        result: completed.payload,
      },
      201,
      requestId,
    );
  } catch (error) {
    console.error("ResearchRun persistence failed", { requestId, message: String(error) });
    return jsonResponse({ error: "研究已完成，但目前無法安全保存 ResearchRun；未建立部分研究庫紀錄。" }, 503, requestId);
  }
}

async function listRuns(request, env, requestId) {
  const auth = await authorizeLibrary(request, env, requestId);
  if (auth instanceof Response) return auth;
  const url = new URL(request.url);
  const requestedLimit = Number(url.searchParams.get("limit") || DEFAULT_LIST_LIMIT);
  const limit = Number.isInteger(requestedLimit)
    ? Math.min(Math.max(requestedLimit, 1), MAX_LIST_LIMIT)
    : DEFAULT_LIST_LIMIT;
  try {
    const result = await env.DB.prepare(
      `SELECT run_id, source_run_id, name, job_hash, result_contract_version,
              decision_count, created_at
       FROM research_runs
       WHERE library_id = ?1
       ORDER BY created_at DESC, run_id DESC
       LIMIT ?2`,
    ).bind(auth.library.library_id, limit).all();
    return jsonResponse(
      {
        contractVersion: RESEARCH_RUN_MEMORY_CONTRACT_VERSION,
        libraryId: auth.library.library_id,
        runs: result.results.map(runSummary),
      },
      200,
      requestId,
    );
  } catch (error) {
    console.error("ResearchRun list failed", { requestId, message: String(error) });
    return jsonResponse({ error: "Research Library 暫時無法讀取。" }, 503, requestId);
  }
}

async function getRun(request, env, requestId, runId) {
  const auth = await authorizeLibrary(request, env, requestId);
  if (auth instanceof Response) return auth;
  try {
    const row = await env.DB.prepare(
      `SELECT run_id, source_run_id, name, job_hash, execution_request_json,
              result_json, result_contract_version, decision_count, created_at
       FROM research_runs
       WHERE library_id = ?1 AND run_id = ?2`,
    ).bind(auth.library.library_id, runId).first();
    if (!row) return jsonResponse({ error: "找不到此 ResearchRun。" }, 404, requestId);
    let executionRequest;
    let result;
    try {
      executionRequest = JSON.parse(row.execution_request_json);
      result = JSON.parse(row.result_json);
    } catch {
      return jsonResponse({ error: "ResearchRun durable evidence 已損壞，拒絕提供不完整結果。" }, 500, requestId);
    }
    return jsonResponse(
      {
        contractVersion: RESEARCH_RUN_MEMORY_CONTRACT_VERSION,
        libraryId: auth.library.library_id,
        run: runSummary(row),
        executionRequest,
        result,
      },
      200,
      requestId,
    );
  } catch (error) {
    console.error("ResearchRun detail failed", { requestId, message: String(error) });
    return jsonResponse({ error: "ResearchRun 暫時無法讀取。" }, 503, requestId);
  }
}

async function rerun(request, env, requestId, runId, executeWalkForward) {
  const auth = await authorizeLibrary(request, env, requestId);
  if (auth instanceof Response) return auth;
  const body = await request.text();
  if (body.trim()) {
    return jsonResponse({ error: "重新執行會使用 D1 保存的原始 request，不接受替代 request。" }, 400, requestId);
  }
  let source;
  try {
    source = await env.DB.prepare(
      `SELECT run_id, name, execution_request_json
       FROM research_runs
       WHERE library_id = ?1 AND run_id = ?2`,
    ).bind(auth.library.library_id, runId).first();
  } catch (error) {
    console.error("ResearchRun rerun lookup failed", { requestId, message: String(error) });
    return jsonResponse({ error: "ResearchRun 暫時無法讀取。" }, 503, requestId);
  }
  if (!source) return jsonResponse({ error: "找不到此 ResearchRun。" }, 404, requestId);

  let executionRequest;
  try {
    executionRequest = JSON.parse(source.execution_request_json);
  } catch {
    return jsonResponse({ error: "保存的 ResearchRun request 已損壞，拒絕重新執行。" }, 500, requestId);
  }

  const executionResponse = await executeWalkForward(executionRequest);
  const completed = await readExecutionResponse(executionResponse, requestId);
  if (completed instanceof Response) return completed;
  try {
    const persisted = await persistCompletedRun(env, {
      library: auth.library,
      newCapability: null,
      name: source.name,
      executionRequest,
      result: completed.payload,
      resultText: completed.text,
      sourceRunId: source.run_id,
    });
    return jsonResponse(
      {
        contractVersion: RESEARCH_RUN_MEMORY_CONTRACT_VERSION,
        libraryId: persisted.libraryId,
        run: {
          runId: persisted.runId,
          sourceRunId: source.run_id,
          name: source.name,
          jobHash: completed.payload.jobHash,
          resultContractVersion: completed.payload.contractVersion,
          decisionCount: completed.payload.decisions.length,
        },
        result: completed.payload,
      },
      201,
      requestId,
    );
  } catch (error) {
    console.error("ResearchRun rerun persistence failed", { requestId, message: String(error) });
    return jsonResponse({ error: "研究重新執行完成，但目前無法安全保存新的 ResearchRun。" }, 503, requestId);
  }
}

async function handleResearchRunRequest(request, env, executeWalkForward) {
  const requestId = crypto.randomUUID();
  if (!env.DB) {
    return jsonResponse({ error: "ResearchRun durable database is not configured." }, 503, requestId);
  }
  const url = new URL(request.url);
  if (url.pathname === RESEARCH_RUNS_PATH) {
    if (request.method === "POST") return createRun(request, env, requestId, executeWalkForward);
    if (request.method === "GET") return listRuns(request, env, requestId);
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }

  const escaped = RESEARCH_RUNS_PATH.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
  const match = new RegExp(`^${escaped}/(run_[0-9a-f-]+)(/rerun)?$`, "u").exec(url.pathname);
  if (!match) return jsonResponse({ error: "找不到 ResearchRun API 路徑。" }, 404, requestId);
  const runId = match[1];
  if (match[2]) {
    if (request.method !== "POST") return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
    return rerun(request, env, requestId, runId, executeWalkForward);
  }
  if (request.method !== "GET") return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  return getRun(request, env, requestId, runId);
}

export {
  CAPABILITY_HASH_VERSION,
  RESEARCH_RUN_MEMORY_CONTRACT_VERSION,
  RESEARCH_RUNS_PATH,
  generateLibraryCapability,
  handleResearchRunRequest,
  hashLibraryCapability,
  parseBearerCapability,
  validateCreatePayload,
};
