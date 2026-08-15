import router from "./router.js";

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
  const isHealth = incomingUrl.pathname === WALK_FORWARD_HEALTH_PATH;
  const isRun = incomingUrl.pathname === WALK_FORWARD_PATH;
  if (!isHealth && !isRun) {
    return jsonResponse({ error: "找不到 Walk-Forward API 路徑。" }, 404, requestId);
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

export { proxyWalkForward };

export default {
  async fetch(request, env, context) {
    const pathname = new URL(request.url).pathname;
    if (pathname === WALK_FORWARD_PATH || pathname.startsWith(`${WALK_FORWARD_PATH}/`)) {
      return proxyWalkForward(request, env);
    }
    return router.fetch(request, env, context);
  },
};
