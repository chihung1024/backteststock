import worker from "./index.js";
import {
  applyTrustedBackendHeaders,
  enforceEdgeRequestPolicy,
} from "./security.js";

const LEGACY_BACKTEST_PATH = "/api/backtest";
const EXHAUSTIVE_PREPARE_PATH = "/api/optimizer/exhaustive/prepare";
const REFINERY_V1_PREFIX = "/api/v1/refinery/";
const REFINERY_V1_ROUTES = new Map([
  ["preflight", { method: "POST" }],
  ["analyze", { method: "POST" }],
]);
const PORTFOLIO_V3_PREFIX = "/api/v3/portfolio/";
const PORTFOLIO_V3_ROUTES = new Map([
  ["health", { method: "GET" }],
  ["assets/search", { method: "GET" }],
  ["preflight", { method: "POST" }],
  ["backtests", { method: "POST" }],
]);
const LEGACY_BACKTEST_REQUEST_MAX_BYTES = 256 * 1024;
const OPTIMIZER_MAX_REQUEST_BYTES = 3 * 1024 * 1024;
const REFINERY_REQUEST_MAX_BYTES = 512 * 1024;
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

function edgePolicyResponse(failure, requestId) {
  const response = jsonResponse(
    { error: failure.message, code: failure.code },
    failure.status,
    requestId,
  );
  if (!failure.retryAfter) return response;
  const headers = new Headers(response.headers);
  headers.set("retry-after", String(failure.retryAfter));
  return new Response(response.body, { status: response.status, headers });
}

function safeProxyHeaders(request, requestId, incomingUrl, edgeIdentity) {
  const headers = applyTrustedBackendHeaders(
    new Headers(request.headers),
    edgeIdentity,
  );
  headers.set("x-request-id", requestId);
  headers.set("x-forwarded-proto", incomingUrl.protocol.replace(":", ""));
  return headers;
}

function legacyProxyHeaders(request, requestId, incomingUrl, edgeIdentity) {
  return safeProxyHeaders(request, requestId, incomingUrl, edgeIdentity);
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

async function proxyLegacyBacktest(request, env) {
  const requestId = crypto.randomUUID();
  if (request.method !== "POST") {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }
  const edgeIdentity = await enforceEdgeRequestPolicy(request, env, {
    expensive: true,
  });
  if (!edgeIdentity.ok) return edgePolicyResponse(edgeIdentity, requestId);

  const body = await readBoundedBody(
    request,
    LEGACY_BACKTEST_REQUEST_MAX_BYTES,
    requestId,
    "請求內容過大。",
  );
  if (body instanceof Response) return body;

  const backendOrigin = validatedBackendOrigin(env, requestId);
  if (backendOrigin instanceof Response) return backendOrigin;
  const incomingUrl = new URL(request.url);
  const target = new URL(incomingUrl.pathname + incomingUrl.search, backendOrigin);
  const headers = legacyProxyHeaders(request, requestId, incomingUrl, edgeIdentity);

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
        { error: "行情服務回應逾時；目前進度已保留，系統可自動接續重試。" },
        504,
        requestId,
      );
    }
    console.error("Legacy backtest proxy failure", {
      requestId,
      message: String(error),
    });
    return jsonResponse({ error: "暫時無法連線至後端服務。" }, 502, requestId);
  } finally {
    clearTimeout(timeout);
  }
}

async function proxyRefineryV1(request, env) {
  const requestId = crypto.randomUUID();
  const incomingUrl = new URL(request.url);
  const routeName = incomingUrl.pathname.slice(REFINERY_V1_PREFIX.length);
  const route = REFINERY_V1_ROUTES.get(routeName);
  if (!route) return jsonResponse({ error: "找不到 Refinery v1 API 路徑。" }, 404, requestId);
  if (request.method !== route.method) {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }
  const edgeIdentity = await enforceEdgeRequestPolicy(request, env, {
    expensive: routeName === "analyze",
  });
  if (!edgeIdentity.ok) return edgePolicyResponse(edgeIdentity, requestId);

  const body = await readBoundedBody(
    request,
    REFINERY_REQUEST_MAX_BYTES,
    requestId,
    "Refinery v1 請求內容過大。",
  );
  if (body instanceof Response) return body;

  const backendOrigin = validatedBackendOrigin(env, requestId);
  if (backendOrigin instanceof Response) return backendOrigin;
  const target = new URL(incomingUrl.pathname + incomingUrl.search, backendOrigin);
  const headers = safeProxyHeaders(request, requestId, incomingUrl, edgeIdentity);

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
      return jsonResponse({ error: "Refinery v1 服務回應逾時，請稍後重試。" }, 504, requestId);
    }
    console.error("Refinery v1 proxy failure", {
      requestId,
      message: String(error),
    });
    return jsonResponse({ error: "暫時無法連線至 Refinery v1 服務。" }, 502, requestId);
  } finally {
    clearTimeout(timeout);
  }
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
  const edgeIdentity = await enforceEdgeRequestPolicy(request, env, {
    expensive: routeName === "backtests",
  });
  if (!edgeIdentity.ok) return edgePolicyResponse(edgeIdentity, requestId);

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
  const headers = safeProxyHeaders(request, requestId, incomingUrl, edgeIdentity);

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
  const edgeIdentity = await enforceEdgeRequestPolicy(request, env, {
    expensive: true,
  });
  if (!edgeIdentity.ok) return edgePolicyResponse(edgeIdentity, requestId);

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
  const headers = safeProxyHeaders(request, requestId, incomingUrl, edgeIdentity);

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

export {
  proxyExhaustivePrepare,
  proxyLegacyBacktest,
  proxyPortfolioV3,
  proxyRefineryV1,
};

export default {
  async fetch(request, env, context) {
    const url = new URL(request.url);
    if (url.pathname === LEGACY_BACKTEST_PATH) {
      return proxyLegacyBacktest(request, env);
    }
    if (url.pathname.startsWith(REFINERY_V1_PREFIX)) {
      return proxyRefineryV1(request, env);
    }
    if (url.pathname.startsWith(PORTFOLIO_V3_PREFIX)) {
      return proxyPortfolioV3(request, env);
    }
    if (url.pathname === EXHAUSTIVE_PREPARE_PATH) {
      return proxyExhaustivePrepare(request, env);
    }
    return worker.fetch(request, env, context);
  },
};
