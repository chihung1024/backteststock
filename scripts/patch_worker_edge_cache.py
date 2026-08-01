from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "worker/index.js"


def replace_once(content: str, old: str, new: str, label: str) -> str:
    count = content.count(old)
    if count != 1:
        raise SystemExit(f"worker/index.js: {label} expected once, found {count}")
    return content.replace(old, new, 1)


def main() -> None:
    content = PATH.read_text(encoding="utf-8")
    content = replace_once(
        content,
        "const API_TIMEOUT_MS = 240_000;",
        '''const API_TIMEOUT_MS = 240_000;
const EDGE_CACHE_VERSION = "2026-08-01.1";
const EDGE_CACHE_TTL_SECONDS = 15 * 60;
const EDGE_CACHEABLE_ROUTES = new Set(["/api/backtest", "/api/scan"]);''',
        "cache constants",
    )

    marker = "\nasync function proxyBackend(request, env, requestId, requestBody) {"
    helpers = '''

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

async function cacheSuccessfulResponse(cache, key, response) {
  if (!cache || response.status !== 200) return;
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return;
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
'''
    content = replace_once(content, marker, helpers + marker, "proxy helper marker")

    content = replace_once(
        content,
        '''  const requestBody = await readValidatedBody(request, requestId);
  if (requestBody instanceof Response) return requestBody;
  return proxyBackend(request, env, requestId, requestBody);''',
        '''  const requestBody = await readValidatedBody(request, requestId);
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
  await cacheSuccessfulResponse(cache, cacheKey, response);
  return withEdgeCacheStatus(response, "MISS", requestId);''',
        "proxy cache flow",
    )

    PATH.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
