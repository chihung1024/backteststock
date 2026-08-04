import worker from "./index.js";

const EXHAUSTIVE_PREPARE_PATH = "/api/optimizer/exhaustive/prepare";
const PORTFOLIO_V3_PREFIX = "/api/v3/portfolio/";
const PORTFOLIO_V3_ROUTES = new Map([
  ["health", { method: "GET" }],
  ["assets/search", { method: "GET" }],
  ["preflight", { method: "POST" }],
  ["backtests", { method: "POST" }],
]);
const OPTIMIZER_MAX_REQUEST_BYTES = 3 * 1024 * 1024;
const PORTFOLIO_REQUEST_MAX_BYTES = 512 * 1024;
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

function validatedBackendOrigin(env, requestId) {
  if (!env.BACKEND_ORIGIN) {
    return jsonResponse({ error: "後端服務尚未設定。" }, 503, requestId);
  }
  try {
    const origin = new URL(env.BACKEND_ORIGIN);
    if (!/^https?:$/.test(origin.protocol)) throw new Error("unsupported protocol");
    return origin;
  } catch {
    return jsonResponse({ error: "後端服務設定無效。" }, 503, requestId);
  }
}

function safeProxyHeaders(request, requestId, incomingUrl) {
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
  return headers;
}

function sanitizedProxyResponse(response, requestId) {
  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("server");
  responseHeaders.delete("x-powered-by");
  responseHeaders.delete("set-cookie");
  responseHeaders.set("cache-control", "no-store");
  responseHeaders.set("x-content-type-options", "nosniff");
  responseHeaders.set("x-request-id", requestId);
  const backendTiming = response.headers.get("server-timing");
  if (backendTiming) responseHeaders.set("x-backend-server-timing", backendTiming);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

async function readBoundedBody(request, maximumBytes, requestId, message) {
  const declaredLength = Number(request.headers.get("content-length") || "0");
  if (declaredLength > maximumBytes) {
    return jsonResponse({ error: message }, 413, requestId);
  }
  const body = await request.arrayBuffer();
  if (body.byteLength > maximumBytes) {
    return jsonResponse({ error: message }, 413, requestId);
  }
  return body;
}

async function proxyPortfolioV3(request, env) {
  const requestId = crypto.randomUUID();
  const incomingUrl = new URL(request.url);
  const routeName = incomingUrl.pathname.slice(PORTFOLIO_V3_PREFIX.length);
  const route = PORTFOLIO_V3_ROUTES.get(routeName);
  if (!route) return jsonResponse({ error: "找不到 Portfolio v3 API 路徑。" }, 404, requestId);
  if (request.method !== route.method) {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }

  let body;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await readBoundedBody(
      request,
      PORTFOLIO_REQUEST_MAX_BYTES,
      requestId,
      "Portfolio v3 請求內容過大。",
    );
    if (body instanceof Response) return body;
  }

  const backendOrigin = validatedBackendOrigin(env, requestId);
  if (backendOrigin instanceof Response) return backendOrigin;
  const target = new URL(incomingUrl.pathname + incomingUrl.search, backendOrigin);
  const headers = safeProxyHeaders(request, requestId, incomingUrl);
  const clientIp = request.headers.get("cf-connecting-ip");
  if (clientIp) headers.set("x-forwarded-for", clientIp);

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
    return sanitizedProxyResponse(response, requestId);
  } catch (error) {
    if (controller.signal.aborted) {
      return jsonResponse({ error: "Portfolio v3 服務回應逾時，請稍後重試。" }, 504, requestId);
    }
    console.error("Portfolio v3 proxy failure", {
      requestId,
      message: String(error),
    });
    return jsonResponse({ error: "暫時無法連線至 Portfolio v3 服務。" }, 502, requestId);
  } finally {
    clearTimeout(timeout);
  }
}

async function proxyExhaustivePrepare(request, env) {
  const requestId = crypto.randomUUID();
  if (request.method !== "POST") {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }

  const body = await readBoundedBody(
    request,
    OPTIMIZER_MAX_REQUEST_BYTES,
    requestId,
    "請求內容過大。",
  );
  if (body instanceof Response) return body;

  const backendOrigin = validatedBackendOrigin(env, requestId);
  if (backendOrigin instanceof Response) return backendOrigin;
  const incomingUrl = new URL(request.url);
  const target = new URL(incomingUrl.pathname + incomingUrl.search, backendOrigin);
  const headers = safeProxyHeaders(request, requestId, incomingUrl);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort("timeout"), API_TIMEOUT_MS);
  try {
    const response = await fetch(target, {
      method: "POST",
      headers,
      body,
      redirect: "manual",
      signal: controller.signal,
    });
    return sanitizedProxyResponse(response, requestId);
  } catch (error) {
    if (controller.signal.aborted) {
      return jsonResponse(
        { error: "行情服務回應逾時；請稍後重試預檢。" },
        504,
        requestId,
      );
    }
    console.error("Exhaustive optimizer proxy failure", {
      requestId,
      message: String(error),
    });
    return jsonResponse({ error: "暫時無法連線至後端服務。" }, 502, requestId);
  } finally {
    clearTimeout(timeout);
  }
}

export { proxyExhaustivePrepare, proxyPortfolioV3 };

export default {
  async fetch(request, env, context) {
    const url = new URL(request.url);
    if (url.pathname.startsWith(PORTFOLIO_V3_PREFIX)) {
      return proxyPortfolioV3(request, env);
    }
    if (url.pathname === EXHAUSTIVE_PREPARE_PATH) {
      return proxyExhaustivePrepare(request, env);
    }
    return worker.fetch(request, env, context);
  },
};
