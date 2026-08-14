const API_ROUTES = new Map([
  ["/api/health", new Set(["GET"])],
  ["/api/all-tickers", new Set(["GET"])],
  ["/api/backtest", new Set(["POST"])],
  ["/api/scan", new Set(["POST"])],
  ["/api/screener", new Set(["POST"])],
  ["/api/v2/screener", new Set(["POST"])],
]);

const MAX_REQUEST_BYTES = 256 * 1024;
const API_TIMEOUT_MS = 240_000;
const EDGE_CACHE_VERSION = "2026-08-14.1";
const EDGE_CACHE_TTL_SECONDS = 15 * 60;
const EDGE_CACHEABLE_ROUTES = new Set(["/api/scan"]);
const UNIVERSE_STALE_MS = 10 * 24 * 60 * 60 * 1000;
const UNIVERSE_PIT_MAX_AGE_MS = UNIVERSE_STALE_MS;
const UNIVERSE_ID_PATTERN = /^[a-z0-9-]{2,40}$/;
const UNIVERSE_TICKER_PATTERN = /^[A-Z0-9.^=_-]{1,20}$/;
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const PIT_MEMBERSHIP_POLICY = "latest-causally-available-observation-on-or-before-max-10d-v2";
const CURRENT_SCREENER_RESEARCH_WARNING =
  "目前成分股與基本面為 current snapshot；將結果用於更早期間屬回溯研究，不能視為歷史時點選股（PIT）。";

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
      "default-src 'self'; script-src 'self'; worker-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
    );
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function readValidatedBody(request, requestId, pathname) {
  if (request.method === "GET" || request.method === "HEAD") return undefined;

  const limit = MAX_REQUEST_BYTES;
  const declaredLength = Number(request.headers.get("content-length") || "0");
  if (declaredLength > limit) {
    return jsonResponse({ error: "請求內容過大。" }, 413, requestId);
  }

  const body = await request.arrayBuffer();
  if (body.byteLength > limit) {
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

function cacheBackend(env) {
  return env.API_CACHE || globalThis.caches?.default || null;
}

async function buildEdgeCacheKey(pathname, requestBody) {
  const digest = await crypto.subtle.digest("SHA-256", requestBody);
  const hash = [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
  return new Request(
    `https://edge-cache.invalid/${EDGE_CACHE_VERSION}${pathname}/${hash}`,
  );
}

function withEdgeCacheStatus(response, status, requestId) {
  const headers = new Headers(response.headers);
  headers.set("x-edge-cache", status);
  headers.set("x-request-id", requestId);
  headers.set("cache-control", "no-store");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function isCacheableApiResponse(pathname, response) {
  if (pathname !== "/api/scan") return true;

  const requestedRaw = response.headers.get("x-scan-requested") || "";
  const resolvedRaw = response.headers.get("x-scan-resolved") || "";
  if (!/^\d+$/.test(requestedRaw) || !/^\d+$/.test(resolvedRaw)) return false;

  const requested = Number(requestedRaw);
  const resolved = Number(resolvedRaw);
  return Number.isSafeInteger(requested)
    && requested > 0
    && Number.isSafeInteger(resolved)
    && resolved === requested;
}

async function cacheSuccessfulResponse(cache, key, response, pathname) {
  if (!cache || response.status !== 200) return;
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return;
  if (!isCacheableApiResponse(pathname, response)) return;
  const headers = new Headers(response.headers);
  headers.delete("x-request-id");
  headers.set("cache-control", `public, max-age=${EDGE_CACHE_TTL_SECONDS}`);
  const body = await response.clone().arrayBuffer();
  await cache.put(key, new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  }));
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
    const backendServerTiming = response.headers.get("server-timing");
    if (backendServerTiming) {
      responseHeaders.set("server-timing", backendServerTiming);
      responseHeaders.set("x-backend-server-timing", backendServerTiming);
    }
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
      return jsonResponse({ error: "行情服務回應逾時；目前進度已保留，系統可自動接續重試。" }, 504, requestId);
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

  const requestBody = await readValidatedBody(
    request,
    requestId,
    incomingUrl.pathname,
  );
  if (requestBody instanceof Response) return requestBody;

  const cache = cacheBackend(env);
  const cacheEligible = (
    cache
    && EDGE_CACHEABLE_ROUTES.has(incomingUrl.pathname)
    && request.method === "POST"
    && requestBody instanceof ArrayBuffer
    && !request.headers.has("authorization")
    && !request.headers.has("cookie")
  );
  if (!cacheEligible) {
    return proxyBackend(request, env, requestId, requestBody);
  }

  const cacheKey = await buildEdgeCacheKey(incomingUrl.pathname, requestBody);
  const cached = await cache.match(cacheKey);
  if (cached) return withEdgeCacheStatus(cached, "HIT", requestId);

  const response = await proxyBackend(request, env, requestId, requestBody);
  await cacheSuccessfulResponse(cache, cacheKey, response, incomingUrl.pathname);
  return withEdgeCacheStatus(response, "MISS", requestId);
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

function parseIsoDate(value) {
  const raw = String(value || "").trim();
  if (!ISO_DATE_PATTERN.test(raw)) return null;
  const timestamp = Date.parse(`${raw}T00:00:00Z`);
  if (!Number.isFinite(timestamp)) return null;
  if (new Date(timestamp).toISOString().slice(0, 10) !== raw) return null;
  return { raw, timestamp };
}

function timestampDate(value) {
  const timestamp = Date.parse(value || "");
  return Number.isFinite(timestamp) ? new Date(timestamp).toISOString().slice(0, 10) : null;
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

async function loadUniverseSnapshotAsOf(env, universeId, requestedAsOf, requestId) {
  if (!UNIVERSE_ID_PATTERN.test(universeId)) {
    return jsonResponse({ error: "Universe 代碼格式不正確。" }, 400, requestId);
  }
  const requestedDate = parseIsoDate(requestedAsOf);
  if (!requestedDate) {
    return jsonResponse({ error: "selectionAsOf / asOf 必須是有效的 YYYY-MM-DD 日期。" }, 400, requestId);
  }
  const today = new Date().toISOString().slice(0, 10);
  if (requestedDate.raw > today) {
    return jsonResponse({ error: "selectionAsOf / asOf 不得晚於今天；未來日期沒有可驗證的歷史資訊集。" }, 400, requestId);
  }
  const db = requireUniverseDatabase(env, requestId);
  if (db instanceof Response) return db;

  try {
    const universe = await db.prepare(
      `SELECT id, name
       FROM universes
       WHERE id = ?1 AND enabled = 1`,
    ).bind(universeId).first();
    if (!universe) return jsonResponse({ error: "找不到指定的 Universe。" }, 404, requestId);

    const row = await db.prepare(
      `SELECT
         universe_id, source_as_of, version, fetched_at, source_label,
         source_url, is_proxy, warning, checksum, member_count, members_json
       FROM universe_snapshot_archive
       WHERE universe_id = ?1
         AND source_as_of <= ?2
         AND date(fetched_at) <= ?2
       ORDER BY source_as_of DESC, fetched_at DESC
       LIMIT 1`,
    ).bind(universeId, requestedDate.raw).first();
    if (!row) {
      return jsonResponse(
        { error: "所選日期之前沒有可驗證且當時已取得的歷史 Universe 快照；已停止使用目前成分股替代。" },
        409,
        requestId,
      );
    }

    const observedDate = parseIsoDate(row.source_as_of);
    if (!observedDate) {
      return jsonResponse({ error: "歷史 Universe 快照缺少有效成分日。" }, 503, requestId);
    }
    const fetchedDate = timestampDate(row.fetched_at);
    if (!fetchedDate) {
      return jsonResponse({ error: "歷史 Universe 快照缺少有效取得時間。" }, 503, requestId);
    }
    if (fetchedDate > requestedDate.raw) {
      return jsonResponse(
        { error: "歷史 Universe 快照在所選日期之後才被系統取得；為避免回看未來資訊，已停止執行。" },
        409,
        requestId,
      );
    }
    const observationAgeMs = requestedDate.timestamp - observedDate.timestamp;
    if (observationAgeMs < 0 || observationAgeMs > UNIVERSE_PIT_MAX_AGE_MS) {
      return jsonResponse(
        { error: "最近可驗證的歷史 Universe 快照距所選日期超過 10 天；為避免過期成分股推定，已停止執行。" },
        409,
        requestId,
      );
    }

    let tickers;
    try {
      tickers = JSON.parse(row.members_json);
    } catch {
      tickers = null;
    }
    if (
      !Array.isArray(tickers)
      || tickers.length !== Number(row.member_count)
      || tickers.some((ticker) => !UNIVERSE_TICKER_PATTERN.test(String(ticker || "")))
    ) {
      return jsonResponse({ error: "歷史 Universe 快照完整性檢查失敗，已停止使用此版本。" }, 503, requestId);
    }

    const membershipAuthoritative = !Boolean(row.is_proxy);
    return {
      id: universe.id,
      name: universe.name,
      version: row.version,
      sourceAsOf: row.source_as_of,
      fetchedAt: row.fetched_at,
      evidenceAvailableAsOf: fetchedDate,
      proxyNote: row.warning,
      checksum: row.checksum,
      requestedAsOf: requestedDate.raw,
      selectionMode: "point_in_time_last_causally_available",
      pointInTime: true,
      membershipCausal: true,
      membershipAuthoritative,
      observationAgeDays: Math.floor(observationAgeMs / (24 * 60 * 60 * 1000)),
      membershipPolicy: PIT_MEMBERSHIP_POLICY,
      source: {
        label: row.source_label,
        url: row.source_url,
        isProxy: Boolean(row.is_proxy),
      },
      members: tickers.map((ticker) => ({ ticker, source_ticker: ticker })),
    };
  } catch (error) {
    console.error("Historical Universe snapshot query failed", {
      requestId,
      universeId,
      requestedAsOf: requestedDate.raw,
      message: String(error),
    });
    return jsonResponse(
      { error: "歷史 Universe 封存尚未初始化或暫時無法讀取。" },
      503,
      requestId,
    );
  }
}

async function getUniverseDetail(request, env, requestId, universeId) {
  if (request.method !== "GET") {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }
  const requestedAsOf = new URL(request.url).searchParams.get("asOf");
  const snapshot = requestedAsOf
    ? await loadUniverseSnapshotAsOf(env, universeId, requestedAsOf, requestId)
    : await loadUniverseSnapshot(env, universeId, requestId);
  if (snapshot instanceof Response) return snapshot;
  return jsonResponse(
    {
      data: {
        ...snapshot,
        members: snapshot.members.map((member) => ({
          ticker: member.ticker,
          sourceTicker: member.source_ticker || member.ticker,
        })),
      },
    },
    200,
    requestId,
  );
}

function pointInTimeScreenerCompatibilityError(payload) {
  const sector = String(payload.sector || "any").trim();
  const filters = payload.filters && typeof payload.filters === "object" && !Array.isArray(payload.filters)
    ? payload.filters
    : {};
  const sort = String(payload.sort || "ticker-asc").trim();
  if (sector !== "any" || Object.keys(filters).length || sort !== "ticker-asc") {
    return "歷史 PIT 模式目前只有成分股 membership 證據；sector、基本面條件與市值/估值排序需要同時點歷史 fundamentals，不能使用目前資料替代。";
  }
  return null;
}

function normalizedMembershipLimit(rawLimit) {
  if (rawLimit == null || rawLimit === "") return null;
  const limit = Number(rawLimit);
  return Number.isSafeInteger(limit) && limit > 0 ? limit : NaN;
}

function pointInTimeMembershipScreener(payload, snapshot, requestId) {
  const compatibilityError = pointInTimeScreenerCompatibilityError(payload);
  if (compatibilityError) {
    return jsonResponse({ error: compatibilityError }, 409, requestId);
  }
  const limit = normalizedMembershipLimit(payload.limit);
  if (Number.isNaN(limit)) {
    return jsonResponse({ error: "回測檔數上限必須是大於 0 的整數，留空則使用全部成分股。" }, 400, requestId);
  }

  const allCandidates = snapshot.members
    .map((member) => ({ ticker: member.ticker }))
    .sort((left, right) => left.ticker.localeCompare(right.ticker));
  const candidates = limit == null ? allCandidates : allCandidates.slice(0, limit);
  const warnings = [];
  if (snapshot.proxyNote) warnings.push(snapshot.proxyNote);
  warnings.push(
    "歷史 PIT 模式只使用所選日期當時已取得的成分股快照；沒有套用目前 fundamentals。需要歷史基本面條件時會 fail closed。",
  );
  if (!snapshot.membershipAuthoritative) {
    warnings.push(
      "此 Universe 使用 proxy membership；時間因果性已驗證，但不能等同官方指數歷史成分名單。",
    );
  }

  return jsonResponse(
    {
      universe: {
        id: snapshot.id,
        name: snapshot.name,
        version: snapshot.version,
        sourceAsOf: snapshot.sourceAsOf,
        fetchedAt: snapshot.fetchedAt,
        evidenceAvailableAsOf: snapshot.evidenceAvailableAsOf,
        proxyNote: snapshot.proxyNote,
        checksum: snapshot.checksum,
        requestedAsOf: snapshot.requestedAsOf,
        observationAgeDays: snapshot.observationAgeDays,
        membershipPolicy: snapshot.membershipPolicy,
        source: snapshot.source,
      },
      fundamentalsAsOf: null,
      fundamentalsSources: [],
      funnel: {
        universeCount: allCandidates.length,
        fundamentalsAvailable: null,
        sectorMatches: null,
        passedFilters: allCandidates.length,
        selectedForScan: candidates.length,
      },
      candidates,
      truncated: limit != null && candidates.length < allCandidates.length,
      sort: "ticker-asc",
      limit,
      warnings,
      researchValidity: {
        selectionMode: "point_in_time_membership_only",
        requestedAsOf: snapshot.requestedAsOf,
        membershipObservationAsOf: snapshot.sourceAsOf,
        membershipEvidenceAvailableAsOf: snapshot.evidenceAvailableAsOf,
        membershipPointInTime: true,
        membershipCausal: true,
        membershipAuthoritative: snapshot.membershipAuthoritative,
        membershipSourceType: snapshot.membershipAuthoritative ? "authoritative" : "proxy",
        fundamentalsPointInTime: false,
        fundamentalsApplied: false,
        historicalSelectionSafe: snapshot.membershipAuthoritative,
        membershipPolicy: snapshot.membershipPolicy,
      },
    },
    200,
    requestId,
  );
}

async function annotateCurrentScreenerResponse(response, snapshot, requestId) {
  if (response.status !== 200) return response;
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return response;

  let payload;
  try {
    payload = await response.json();
  } catch {
    return response;
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return response;

  const warnings = Array.isArray(payload.warnings) ? [...payload.warnings] : [];
  if (!warnings.includes(CURRENT_SCREENER_RESEARCH_WARNING)) {
    warnings.push(CURRENT_SCREENER_RESEARCH_WARNING);
  }
  const headers = new Headers(response.headers);
  headers.set("content-type", "application/json; charset=utf-8");
  headers.set("cache-control", "no-store");
  headers.set("x-content-type-options", "nosniff");
  headers.set("x-request-id", requestId);
  return new Response(
    JSON.stringify({
      ...payload,
      warnings,
      researchValidity: {
        selectionMode: "current_snapshot_retrospective",
        membershipObservationAsOf: snapshot.sourceAsOf || null,
        membershipPointInTime: false,
        membershipCausal: false,
        membershipAuthoritative: null,
        fundamentalsPointInTime: false,
        fundamentalsApplied: true,
        historicalSelectionSafe: false,
      },
    }),
    {
      status: response.status,
      statusText: response.statusText,
      headers,
    },
  );
}

async function runVersionedScreener(request, env, requestId) {
  if (request.method !== "POST") {
    return jsonResponse({ error: "不支援此 HTTP 方法。" }, 405, requestId);
  }
  const rawBody = await readValidatedBody(
    request,
    requestId,
    "/api/v2/screener",
  );
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
  const selectionAsOf = String(payload.selectionAsOf || "").trim();
  if (selectionAsOf) {
    const historicalSnapshot = await loadUniverseSnapshotAsOf(
      env,
      universeId,
      selectionAsOf,
      requestId,
    );
    if (historicalSnapshot instanceof Response) return historicalSnapshot;
    return pointInTimeMembershipScreener(payload, historicalSnapshot, requestId);
  }

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
  const response = await proxyBackend(request, env, requestId, body);
  return annotateCurrentScreenerResponse(response, snapshot, requestId);
}

export {
  getUniverseCatalog,
  loadUniverseSnapshot,
  loadUniverseSnapshotAsOf,
  runVersionedScreener,
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
