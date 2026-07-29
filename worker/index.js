const API_ROUTES = new Map([
  ["/api/health", new Set(["GET"])],
  ["/api/all-tickers", new Set(["GET"])],
  ["/api/backtest", new Set(["POST"])],
  ["/api/scan", new Set(["POST"])],
  ["/api/screener", new Set(["POST"])],
  ["/api/v2/screener", new Set(["POST"])],
]);

const MAX_REQUEST_BYTES = 256 * 1024;
const API_TIMEOUT_MS = 45_000;
const SOURCE_TIMEOUT_MS = 15_000;
const SOURCE_MAX_BYTES = 512 * 1024;
const SOURCE_CACHE_TTL_SECONDS = 6 * 60 * 60;
const UNIVERSE_STALE_MS = 10 * 24 * 60 * 60 * 1000;
const UNIVERSE_ID_PATTERN = /^[a-z0-9-]{2,40}$/;
const INVESCO_QQQM_HOLDINGS_URL =
  "https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/46138G649/holdings/fund?idType=cusip&productType=ETF";

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

function sanitizeQqqmHoldings(payload) {
  const sourceDate = String(
    payload?.effectiveBusinessDate || payload?.effectiveDate || "",
  ).trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(sourceDate)) {
    throw new Error("source date is missing or invalid");
  }
  if (!Array.isArray(payload?.holdings)) {
    throw new Error("holdings are missing");
  }

  const holdings = payload.holdings
    .filter((row) => row && typeof row === "object" && !Array.isArray(row))
    .map((row) => ({
      ticker: row.ticker,
      issuerName: row.issuerName,
      securityTypeCode: row.securityTypeCode,
      percentageOfTotalNetAssets: row.percentageOfTotalNetAssets,
      marketValueBase: row.marketValueBase,
    }));
  if (holdings.length < 95 || holdings.length > 200) {
    throw new Error(`unexpected holdings count: ${holdings.length}`);
  }

  return {
    effectiveBusinessDate: sourceDate,
    holdings,
  };
}

async function getQqqmHoldingsSource(request, requestId) {
  if (request.method !== "GET") {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort("timeout"), SOURCE_TIMEOUT_MS);

  try {
    const upstream = await fetch(INVESCO_QQQM_HOLDINGS_URL, {
      method: "GET",
      headers: {
        accept: "application/json",
        "user-agent":
          "Mozilla/5.0 (compatible; BacktestStockUniverseRelay/1.0; +https://github.com/chihung1024/backteststock)",
      },
      redirect: "error",
      signal: controller.signal,
      cf: {
        cacheTtlByStatus: {
          "200-299": SOURCE_CACHE_TTL_SECONDS,
          "400-599": 0,
        },
      },
    });
    if (!upstream.ok) {
      throw new Error(`upstream status ${upstream.status}`);
    }

    const declaredLength = Number(upstream.headers.get("content-length") || "0");
    if (declaredLength > SOURCE_MAX_BYTES) {
      throw new Error("upstream response is too large");
    }
    const rawBody = await upstream.arrayBuffer();
    if (rawBody.byteLength > SOURCE_MAX_BYTES) {
      throw new Error("upstream response is too large");
    }

    const payload = JSON.parse(new TextDecoder().decode(rawBody));
    const sanitized = sanitizeQqqmHoldings(payload);
    return new Response(JSON.stringify(sanitized), {
      status: 200,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "public, max-age=300",
        "x-content-type-options": "nosniff",
        "x-request-id": requestId,
        "x-source-origin": "dng-api.invesco.com",
      },
    });
  } catch (error) {
    const timedOut = controller.signal.aborted;
    console.error("QQQM source relay failure", {
      requestId,
      message: String(error),
    });
    return jsonResponse(
      {
        error: timedOut
          ? "Invesco 來源回應逾時。"
          : "Invesco 來源暫時無法讀取。",
      },
      timedOut ? 504 : 502,
      requestId,
    );
  } finally {
    clearTimeout(timeout);
  }
}

async function readValidatedBody(request, requestId) {
  if (request.method === "GET" || request.method === "HEAD") return undefined;

  const declaredLength = Number(request.headers.get("content-length") || "0");
  if (declaredLength > MAX_REQUEST_BYTES) {
    return jsonResponse({ error: "請求內容過大。" }, 413, requestId);
  }

  const body = await request.arrayBuffer();
  if (body.byteLength > MAX_REQUEST_BYTES) {
    return jsonResponse({ error: "請求內容過大。" }, 413, requestId);
  }
  return body;
}

function validateBackendOrigin(env, requestId) {
  if (!env.BACKEND_ORIGIN) {
    return jsonResponse({ error: "後端服務尚未設定。" }, 503, requestId);
  }

  try {
    const backendOrigin = new URL(env.BACKEND_ORIGIN);
    if (!/^https?:$/.test(backendOrigin.protocol)) throw new Error("unsupported protocol");
    return backendOrigin;
  } catch {
    return jsonResponse({ error: "後端服務設定無效。" }, 503, requestId);
  }
}

async function proxyBackend(request, env, requestId, requestBody) {
  const incomingUrl = new URL(request.url);
  const backendOrigin = validateBackendOrigin(env, requestId);
  if (backendOrigin instanceof Response) return backendOrigin;

  const target = new URL(incomingUrl.pathname + incomingUrl.search, backendOrigin);
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");
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
      body: requestBody,
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

async function proxyApi(request, env, requestId) {
  const incomingUrl = new URL(request.url);
  const allowedMethods = API_ROUTES.get(incomingUrl.pathname);

  if (!allowedMethods) {
    return jsonResponse({ error: "找不到 API 路徑。" }, 404, requestId);
  }
  if (!allowedMethods.has(request.method)) {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }

  const requestBody = await readValidatedBody(request, requestId);
  if (requestBody instanceof Response) return requestBody;
  return proxyBackend(request, env, requestId, requestBody);
}

function requireUniverseDatabase(env, requestId) {
  if (!env.DB) {
    return jsonResponse({ error: "Universe 資料庫尚未綁定。" }, 503, requestId);
  }
  return env.DB;
}

function parseDateAge(value) {
  const timestamp = Date.parse(value || "");
  return Number.isFinite(timestamp) ? Date.now() - timestamp : Number.POSITIVE_INFINITY;
}

function universeFromRow(row) {
  const available = Boolean(row.version_id);
  const warnings = [];
  if (row.proxy_note) warnings.push(row.proxy_note);
  if (available && parseDateAge(row.fetched_at) > UNIVERSE_STALE_MS) {
    warnings.push("Universe 超過 10 天未成功更新，目前沿用最後一個有效版本。");
  }
  if (!available) warnings.push("尚無有效成分股版本；請先執行 Universe 更新工作流程。");

  return {
    id: row.id,
    name: row.name,
    description: row.description,
    source: {
      label: row.source_label,
      url: row.source_url,
      isProxy: Boolean(row.is_proxy),
    },
    available,
    version: row.version || null,
    sourceAsOf: row.source_as_of || null,
    fetchedAt: row.fetched_at || null,
    memberCount: Number(row.member_count || 0),
    warnings,
  };
}

async function getUniverseCatalog(env, requestId) {
  const db = requireUniverseDatabase(env, requestId);
  if (db instanceof Response) return db;

  try {
    const result = await db.prepare(
      `SELECT
         u.id, u.name, u.description,
         COALESCE(NULLIF(v.source_label, ''), u.source_label) AS source_label,
         COALESCE(v.source_url, u.source_url) AS source_url,
         COALESCE(v.is_proxy, u.is_proxy) AS is_proxy,
         COALESCE(v.warning, u.proxy_note) AS proxy_note,
         v.id AS version_id, v.version, v.source_as_of, v.fetched_at, v.member_count
       FROM universes AS u
       LEFT JOIN universe_current AS c ON c.universe_id = u.id
       LEFT JOIN universe_versions AS v ON v.id = c.version_id
       WHERE u.enabled = 1
       ORDER BY u.sort_order, u.id`,
    ).all();
    return jsonResponse({ data: result.results.map(universeFromRow) }, 200, requestId);
  } catch (error) {
    console.error("Universe catalog query failed", { requestId, message: String(error) });
    return jsonResponse({ error: "Universe 資料庫尚未初始化或暫時無法讀取。" }, 503, requestId);
  }
}

async function loadUniverseSnapshot(env, universeId, requestId) {
  if (!UNIVERSE_ID_PATTERN.test(universeId)) {
    return jsonResponse({ error: "Universe 代碼格式不正確。" }, 400, requestId);
  }
  const db = requireUniverseDatabase(env, requestId);
  if (db instanceof Response) return db;

  try {
    const row = await db.prepare(
      `SELECT
         u.id, u.name, COALESCE(v.warning, u.proxy_note) AS proxy_note,
         v.id AS version_id, v.version, v.source_as_of, v.fetched_at, v.member_count
       FROM universes AS u
       LEFT JOIN universe_current AS c ON c.universe_id = u.id
       LEFT JOIN universe_versions AS v ON v.id = c.version_id
       WHERE u.id = ?1 AND u.enabled = 1`,
    ).bind(universeId).first();
    if (!row) return jsonResponse({ error: "找不到指定的 Universe。" }, 404, requestId);
    if (!row.version_id) {
      return jsonResponse({ error: "此 Universe 尚無有效成分股版本。" }, 503, requestId);
    }

    const membersResult = await db.prepare(
      `SELECT ticker, source_ticker
       FROM universe_members
       WHERE version_id = ?1
       ORDER BY ticker`,
    ).bind(row.version_id).all();
    if (membersResult.results.length !== Number(row.member_count)) {
      console.error("Universe member count mismatch", {
        requestId,
        universeId,
        expected: row.member_count,
        actual: membersResult.results.length,
      });
      return jsonResponse({ error: "Universe 快照完整性檢查失敗，已停止使用此版本。" }, 503, requestId);
    }

    return {
      id: row.id,
      name: row.name,
      version: row.version,
      sourceAsOf: row.source_as_of,
      fetchedAt: row.fetched_at,
      proxyNote: row.proxy_note,
      members: membersResult.results,
    };
  } catch (error) {
    console.error("Universe snapshot query failed", { requestId, message: String(error) });
    return jsonResponse({ error: "Universe 快照暫時無法讀取。" }, 503, requestId);
  }
}

async function getUniverseDetail(request, env, requestId, universeId) {
  if (request.method !== "GET") {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }
  const snapshot = await loadUniverseSnapshot(env, universeId, requestId);
  if (snapshot instanceof Response) return snapshot;
  return jsonResponse(
    {
      data: {
        ...snapshot,
        members: snapshot.members.map((member) => ({
          ticker: member.ticker,
          sourceTicker: member.source_ticker,
        })),
      },
    },
    200,
    requestId,
  );
}

async function runVersionedScreener(request, env, requestId) {
  if (request.method !== "POST") {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }
  const rawBody = await readValidatedBody(request, requestId);
  if (rawBody instanceof Response) return rawBody;

  let payload;
  try {
    payload = JSON.parse(new TextDecoder().decode(rawBody));
  } catch {
    return jsonResponse({ error: "請提供有效的 JSON 物件。" }, 400, requestId);
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return jsonResponse({ error: "請提供有效的 JSON 物件。" }, 400, requestId);
  }
  const universeId = String(payload.universe || "").trim().toLowerCase();
  const snapshot = await loadUniverseSnapshot(env, universeId, requestId);
  if (snapshot instanceof Response) return snapshot;

  const trustedPayload = {
    ...payload,
    universe: universeId,
    _universe: snapshot,
  };
  const body = new TextEncoder().encode(JSON.stringify(trustedPayload));
  if (body.byteLength > MAX_REQUEST_BYTES) {
    return jsonResponse({ error: "Universe 快照超過安全請求大小。" }, 503, requestId);
  }
  return proxyBackend(request, env, requestId, body);
}

export {
  getUniverseCatalog,
  getQqqmHoldingsSource,
  loadUniverseSnapshot,
  runVersionedScreener,
  sanitizeQqqmHoldings,
  universeFromRow,
};

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
          universeDatabaseConfigured: Boolean(env.DB),
        },
        200,
        requestId,
      );
    }

    if (url.pathname === "/api/v2/universes") {
      if (request.method !== "GET") {
        return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
      }
      return getUniverseCatalog(env, requestId);
    }

    if (url.pathname === "/api/v2/sources/qqqm-holdings") {
      return getQqqmHoldingsSource(request, requestId);
    }

    const universeMatch = url.pathname.match(/^\/api\/v2\/universes\/([a-z0-9-]+)$/);
    if (universeMatch) {
      return getUniverseDetail(request, env, requestId, universeMatch[1]);
    }

    if (url.pathname === "/api/v2/screener") {
      return runVersionedScreener(request, env, requestId);
    }

    if (url.pathname.startsWith("/api/")) {
      return proxyApi(request, env, requestId);
    }

    const assetResponse = await env.ASSETS.fetch(request);
    return applySecurityHeaders(assetResponse, requestId);
  },
};
