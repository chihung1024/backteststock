import router from "./router.js";
import {
  RESEARCH_RUN_HEALTH_PATH,
  getResearchRunHealth,
} from "./research_run_health.js";
import {
  RESEARCH_RUNS_PATH,
  handleResearchRunRequest,
} from "./research_runs.js";
import {
  WALK_FORWARD_ADMISSION_PATH,
  getWalkForwardAdmission,
} from "./walk_forward_admission.js";

const WALK_FORWARD_PATH = "/api/v1/research/walk-forward";
const WALK_FORWARD_HEALTH_PATH = `${WALK_FORWARD_PATH}/health`;
const WALK_FORWARD_REQUEST_MAX_BYTES = 128 * 1024;
const API_TIMEOUT_MS = 240_000;

function jsonResponse(payload, status, requestId) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "x-request-id": requestId,
    },
  });
}

function backendOrigin(env, requestId) {
  if (!env.BACKEND_ORIGIN) {
    return jsonResponse({ error: "後端服務尚未設定。" }, 503, requestId);
  }
  try {
    const origin = new URL(env.BACKEND_ORIGIN);
    if (!/^https?:$/u.test(origin.protocol)) throw new Error("unsupported protocol");
    return origin;
  } catch {
    return jsonResponse({ error: "後端服務設定無效。" }, 503, requestId);
  }
}

function safeHeaders(request, requestId, incomingUrl) {
  const headers = new Headers(request.headers);
  for (const name of [
    "host",
    "content-length",
    "cf-ipcountry",
    "cf-ray",
    "x-forwarded-for",
    "authorization",
    "cookie",
  ]) headers.delete(name);
  headers.set("x-request-id", requestId);
  headers.set("x-forwarded-proto", incomingUrl.protocol.replace(":", ""));
  const clientIp = request.headers.get("cf-connecting-ip");
  if (clientIp) headers.set("x-forwarded-for", clientIp);
  return headers;
}

function sanitizedResponse(response, requestId) {
  const headers = new Headers(response.headers);
  headers.delete("server");
  headers.delete("x-powered-by");
  headers.delete("set-cookie");
  headers.set("cache-control", "no-store");
  headers.set("x-content-type-options", "nosniff");
  headers.set("x-request-id", requestId);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function boundedBody(request, requestId) {
  const declared = Number(request.headers.get("content-length") || "0");
  if (declared > WALK_FORWARD_REQUEST_MAX_BYTES) {
    return jsonResponse({ error: "Walk-Forward 請求內容過大。" }, 413, requestId);
  }
  const body = await request.arrayBuffer();
  if (body.byteLength > WALK_FORWARD_REQUEST_MAX_BYTES) {
    return jsonResponse({ error: "Walk-Forward 請求內容過大。" }, 413, requestId);
  }
  return body;
}

async function proxyWalkForward(request, env) {
  const requestId = crypto.randomUUID();
  const incomingUrl = new URL(request.url);
  const isAdmission = incomingUrl.pathname === WALK_FORWARD_ADMISSION_PATH;
  const isHealth = incomingUrl.pathname === WALK_FORWARD_HEALTH_PATH;
  const isRun = incomingUrl.pathname === WALK_FORWARD_PATH;
  if (!isAdmission && !isHealth && !isRun) {
    return jsonResponse({ error: "找不到 Walk-Forward API 路徑。" }, 404, requestId);
  }
  if (isAdmission) {
    if (request.method !== "GET") {
      return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
    }
    return getWalkForwardAdmission(env, requestId);
  }
  const expectedMethod = isHealth ? "GET" : "POST";
  if (request.method !== expectedMethod) {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }

  let body;
  if (isRun) {
    body = await boundedBody(request, requestId);
    if (body instanceof Response) return body;
  }

  const origin = backendOrigin(env, requestId);
  if (origin instanceof Response) return origin;
  const target = new URL(incomingUrl.pathname + incomingUrl.search, origin);
  const headers = safeHeaders(request, requestId, incomingUrl);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort("timeout"), API_TIMEOUT_MS);
  try {
    const response = await fetch(target, {
      method: request.method,
      headers,
      body,
      redirect: "manual",
      signal: controller.signal,
    });
    return sanitizedResponse(response, requestId);
  } catch (error) {
    if (controller.signal.aborted) {
      return jsonResponse(
        { error: "Walk-Forward 研究逾時；請縮小 period 或 Exhaustive 組合數後重試。" },
        504,
        requestId,
      );
    }
    console.error("Walk-Forward proxy failure", {
      requestId,
      message: String(error),
    });
    return jsonResponse({ error: "暫時無法連線至 Walk-Forward 服務。" }, 502, requestId);
  } finally {
    clearTimeout(timeout);
  }
}

function executeTrustedWalkForward(executionRequest, env, sourceRequest) {
  const headers = new Headers({
    "content-type": "application/json",
    "cache-control": "no-store",
  });
  // Preserve only Cloudflare's trusted client identity so the existing backend
  // rate-limit authority remains per client. Never propagate browser credentials.
  const clientIp = sourceRequest?.headers.get("cf-connecting-ip");
  if (clientIp) headers.set("cf-connecting-ip", clientIp);
  const request = new Request(`https://research-run.internal${WALK_FORWARD_PATH}`, {
    method: "POST",
    headers,
    body: JSON.stringify(executionRequest),
  });
  return proxyWalkForward(request, env);
}

async function routeResearchRun(request, env) {
  const pathname = new URL(request.url).pathname;
  if (pathname === RESEARCH_RUN_HEALTH_PATH) {
    const requestId = crypto.randomUUID();
    if (request.method !== "GET") {
      return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
    }
    return getResearchRunHealth(env, requestId);
  }
  try {
    return await handleResearchRunRequest(
      request,
      env,
      (executionRequest) => executeTrustedWalkForward(executionRequest, env, request),
    );
  } catch (error) {
    const requestId = crypto.randomUUID();
    console.error("ResearchRun route failure", { requestId, message: String(error) });
    return jsonResponse({ error: "ResearchRun durable store 暫時無法使用。" }, 503, requestId);
  }
}

export { executeTrustedWalkForward, proxyWalkForward, routeResearchRun };

export default {
  async fetch(request, env, context) {
    const pathname = new URL(request.url).pathname;
    if (pathname === RESEARCH_RUNS_PATH || pathname.startsWith(`${RESEARCH_RUNS_PATH}/`)) {
      return routeResearchRun(request, env);
    }
    if (pathname === WALK_FORWARD_PATH || pathname.startsWith(`${WALK_FORWARD_PATH}/`)) {
      return proxyWalkForward(request, env);
    }
    return router.fetch(request, env, context);
  },
};
