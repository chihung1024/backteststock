import worker from "./index.js";

const EXHAUSTIVE_PREPARE_PATH = "/api/optimizer/exhaustive/prepare";
const OPTIMIZER_MAX_REQUEST_BYTES = 3 * 1024 * 1024;
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

async function proxyExhaustivePrepare(request, env) {
  const requestId = crypto.randomUUID();
  if (request.method !== "POST") {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }

  const declaredLength = Number(request.headers.get("content-length") || "0");
  if (declaredLength > OPTIMIZER_MAX_REQUEST_BYTES) {
    return jsonResponse({ error: "請求內容過大。" }, 413, requestId);
  }
  const body = await request.arrayBuffer();
  if (body.byteLength > OPTIMIZER_MAX_REQUEST_BYTES) {
    return jsonResponse({ error: "請求內容過大。" }, 413, requestId);
  }

  const backendOrigin = validatedBackendOrigin(env, requestId);
  if (backendOrigin instanceof Response) return backendOrigin;
  const incomingUrl = new URL(request.url);
  const target = new URL(incomingUrl.pathname + incomingUrl.search, backendOrigin);
  const headers = new Headers(request.headers);
  for (const name of [
    "host",
    "content-length",
    "cf-connecting-ip",
    "cf-ipcountry",
    "cf-ray",
    "x-forwarded-for",
  ]) headers.delete(name);
  headers.set("x-request-id", requestId);
  headers.set("x-forwarded-proto", incomingUrl.protocol.replace(":", ""));

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

export { proxyExhaustivePrepare };

export default {
  async fetch(request, env, context) {
    const url = new URL(request.url);
    if (url.pathname === EXHAUSTIVE_PREPARE_PATH) {
      return proxyExhaustivePrepare(request, env);
    }
    return worker.fetch(request, env, context);
  },
};
