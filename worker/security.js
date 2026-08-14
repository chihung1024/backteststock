const EDGE_AUTH_HEADER = "x-backteststock-edge-auth";
const EDGE_CLIENT_ID_HEADER = "x-backteststock-client-id";
const MIN_EDGE_SECRET_LENGTH = 32;

const EXPENSIVE_PATHS = new Set([
  "/api/backtest",
  "/api/scan",
  "/api/screener",
  "/api/v2/screener",
  "/api/optimizer/exhaustive/prepare",
  "/api/v1/refinery/analyze",
  "/api/v3/portfolio/backtests",
]);

function configured(value) {
  return String(value || "").trim();
}

function truthy(value) {
  return new Set(["1", "true", "yes", "on", "required"])
    .has(configured(value).toLowerCase());
}

function policyFailure(status, code, message, retryAfter = null) {
  return { ok: false, status, code, message, retryAfter };
}

function isExpensiveApiPath(pathname) {
  return EXPENSIVE_PATHS.has(pathname);
}

async function opaqueClientId(request, secret) {
  const source = configured(request.headers.get("cf-connecting-ip")) || "unknown";
  const bytes = new TextEncoder().encode(source);
  let digest;

  if (secret) {
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );
    digest = await crypto.subtle.sign("HMAC", key, bytes);
  } else {
    digest = await crypto.subtle.digest("SHA-256", bytes);
  }

  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
}

async function enforceEdgeRequestPolicy(request, env, options = {}) {
  const pathname = new URL(request.url).pathname;
  const expensive = options.expensive ?? isExpensiveApiPath(pathname);
  const secret = configured(env.BACKTESTSTOCK_EDGE_SECRET);
  const requireAuthentication = truthy(env.BACKTESTSTOCK_REQUIRE_EDGE_AUTH);
  const requireRateLimit = truthy(env.BACKTESTSTOCK_REQUIRE_RATE_LIMIT);

  if (requireAuthentication && secret.length < MIN_EDGE_SECRET_LENGTH) {
    return policyFailure(
      503,
      "edge_auth_not_configured",
      "後端服務驗證尚未完成安全設定。",
    );
  }

  const clientId = await opaqueClientId(request, secret);
  const bindingName = expensive
    ? "EXPENSIVE_API_RATE_LIMITER"
    : "API_RATE_LIMITER";
  const limiter = env[bindingName];

  if (!limiter || typeof limiter.limit !== "function") {
    if (requireRateLimit) {
      return policyFailure(
        503,
        "rate_limit_not_configured",
        "API 流量保護尚未完成設定。",
      );
    }
    return { ok: true, clientId, secret, rateLimitMode: "local-unconfigured" };
  }

  try {
    const outcome = await limiter.limit({ key: `${clientId}:${pathname}` });
    if (!outcome?.success) {
      return policyFailure(
        429,
        "rate_limit_exceeded",
        "請求過於頻繁，請稍後再試。",
        60,
      );
    }
  } catch (error) {
    console.error("Edge rate-limit binding failure", {
      pathname,
      binding: bindingName,
      message: String(error),
    });
    if (requireRateLimit) {
      return policyFailure(
        503,
        "rate_limit_unavailable",
        "API 流量保護暫時無法使用。",
      );
    }
  }

  return { ok: true, clientId, secret, rateLimitMode: bindingName };
}

function applyTrustedBackendHeaders(headers, identity) {
  for (const name of [
    "host",
    "content-length",
    "cf-connecting-ip",
    "cf-ipcountry",
    "cf-ray",
    "x-forwarded-for",
    "authorization",
    "cookie",
    EDGE_AUTH_HEADER,
    EDGE_CLIENT_ID_HEADER,
  ]) headers.delete(name);

  if (identity?.secret) {
    headers.set(EDGE_AUTH_HEADER, identity.secret);
    headers.set(EDGE_CLIENT_ID_HEADER, identity.clientId);
  }
  return headers;
}

export {
  EDGE_AUTH_HEADER,
  EDGE_CLIENT_ID_HEADER,
  applyTrustedBackendHeaders,
  enforceEdgeRequestPolicy,
  isExpensiveApiPath,
};
