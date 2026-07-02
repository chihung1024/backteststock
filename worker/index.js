const API_ROUTES = new Map([
  ["/api/health", new Set(["GET"])],
  ["/api/all-tickers", new Set(["GET"])],
  ["/api/backtest", new Set(["POST"])],
  ["/api/scan", new Set(["POST"])],
  ["/api/screener", new Set(["POST"])],
]);

const MAX_REQUEST_BYTES = 256 * 1024;
const API_TIMEOUT_MS = 45_000;

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

function applySecurityHeaders(response, requestId) {
  const headers = new Headers(response.headers);
  headers.set("x-content-type-options", "nosniff");
  headers.set("referrer-policy", "strict-origin-when-cross-origin");
  headers.set("permissions-policy", "camera=(), microphone=(), geolocation=()");
  headers.set("x-frame-options", "DENY");
  headers.set("x-request-id", requestId);

  if ((headers.get("content-type") || "").includes("text/html")) {
    headers.set(
      "content-security-policy",
      "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
    );
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function proxyApi(request, env, requestId) {
  const incomingUrl = new URL(request.url);
  const allowedMethods = API_ROUTES.get(incomingUrl.pathname);

  if (!allowedMethods) {
    return jsonResponse({ error: "找不到 API 路徑。" }, 404, requestId);
  }
  if (!allowedMethods.has(request.method)) {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }
  if (!env.BACKEND_ORIGIN) {
    return jsonResponse({ error: "後端服務尚未設定。" }, 503, requestId);
  }

  const contentLength = Number(request.headers.get("content-length") || "0");
  if (contentLength > MAX_REQUEST_BYTES) {
    return jsonResponse({ error: "請求內容過大。" }, 413, requestId);
  }

  let backendOrigin;
  try {
    backendOrigin = new URL(env.BACKEND_ORIGIN);
  } catch {
    return jsonResponse({ error: "後端服務設定無效。" }, 503, requestId);
  }

  if (!/^https?:$/.test(backendOrigin.protocol)) {
    return jsonResponse({ error: "後端服務設定無效。" }, 503, requestId);
  }

  const target = new URL(incomingUrl.pathname + incomingUrl.search, backendOrigin);
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("cf-connecting-ip");
  headers.delete("cf-ipcountry");
  headers.delete("cf-ray");
  headers.delete("x-forwarded-for");
  headers.set("x-request-id", requestId);
  headers.set("x-forwarded-proto", incomingUrl.protocol.replace(":", ""));

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort("timeout"), API_TIMEOUT_MS);

  try {
    const response = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      redirect: "manual",
      signal: controller.signal,
    });

    const responseHeaders = new Headers(response.headers);
    responseHeaders.delete("server");
    responseHeaders.delete("x-powered-by");
    responseHeaders.delete("set-cookie");
    responseHeaders.set("cache-control", "no-store");
    responseHeaders.set("x-content-type-options", "nosniff");
    responseHeaders.set("x-request-id", requestId);

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    if (controller.signal.aborted) {
      return jsonResponse({ error: "後端處理逾時，請縮小查詢範圍後重試。" }, 504, requestId);
    }
    console.error("API proxy failure", { requestId, message: String(error) });
    return jsonResponse({ error: "暫時無法連線至後端服務。" }, 502, requestId);
  } finally {
    clearTimeout(timeout);
  }
}

export default {
  async fetch(request, env) {
    const requestId = crypto.randomUUID();
    const url = new URL(request.url);

    if (url.pathname === "/api/edge-health") {
      return jsonResponse(
        {
          status: "ok",
          service: "backteststock-edge",
          backendConfigured: Boolean(env.BACKEND_ORIGIN),
        },
        200,
        requestId,
      );
    }

    if (url.pathname.startsWith("/api/")) {
      return proxyApi(request, env, requestId);
    }

    const assetResponse = await env.ASSETS.fetch(request);
    return applySecurityHeaders(assetResponse, requestId);
  },
};
