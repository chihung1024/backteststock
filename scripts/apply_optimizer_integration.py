from pathlib import Path


def replace_once(path, old, new):
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "worker/index.js",
    '''  ["/api/scan", new Set(["POST"])],
  ["/api/screener", new Set(["POST"])],''',
    '''  ["/api/scan", new Set(["POST"])],
  ["/api/optimizer/calendar", new Set(["POST"])],
  ["/api/optimizer/prepare", new Set(["POST"])],
  ["/api/optimizer/verify", new Set(["POST"])],
  ["/api/screener", new Set(["POST"])],''',
)
replace_once(
    "worker/index.js",
    '''const MAX_REQUEST_BYTES = 256 * 1024;
const API_TIMEOUT_MS = 240_000;''',
    '''const MAX_REQUEST_BYTES = 256 * 1024;
const OPTIMIZER_MAX_REQUEST_BYTES = 2 * 1024 * 1024;
const API_TIMEOUT_MS = 240_000;''',
)
replace_once(
    "worker/index.js",
    '''async function readValidatedBody(request, requestId) {
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
}''',
    '''function requestSizeLimit(pathname) {
  return pathname.startsWith("/api/optimizer/")
    ? OPTIMIZER_MAX_REQUEST_BYTES
    : MAX_REQUEST_BYTES;
}

async function readValidatedBody(request, requestId, pathname) {
  if (request.method === "GET" || request.method === "HEAD") return undefined;

  const limit = requestSizeLimit(pathname);
  const declaredLength = Number(request.headers.get("content-length") || "0");
  if (declaredLength > limit) {
    return jsonResponse({ error: "請求內容過大。" }, 413, requestId);
  }

  const body = await request.arrayBuffer();
  if (body.byteLength > limit) {
    return jsonResponse({ error: "請求內容過大。" }, 413, requestId);
  }
  return body;
}''',
)
replace_once(
    "worker/index.js",
    '''  const requestBody = await readValidatedBody(request, requestId);''',
    '''  const requestBody = await readValidatedBody(
    request,
    requestId,
    incomingUrl.pathname,
  );''',
)

replace_once(
    "public/index.html",
    '''          <button id="export-scan" class="button ghost" type="button">匯出精簡 CSV</button>
          <button id="export-scan-audit" class="button ghost" type="button">匯出稽核 CSV</button>''',
    '''          <a id="open-optimizer" class="button secondary" href="/optimizer.html" target="_blank" rel="noopener">開啟投資組合最佳化器</a>
          <button id="export-scan" class="button ghost" type="button">匯出精簡 CSV</button>
          <button id="export-scan-audit" class="button ghost" type="button">匯出稽核 CSV</button>''',
)

replace_once(
    ".github/workflows/ci.yml",
    '''    timeout-minutes: 15''',
    '''    timeout-minutes: 20''',
)
replace_once(
    ".github/workflows/ci.yml",
    '''          api/index.py api/index_v2.py api/metrics.py api/scan.py api/scan_v2.py
          api/screener.py scripts/update_universes.py''',
    '''          api/index.py api/index_v2.py api/metrics.py api/scan.py api/scan_v2.py
          api/screener.py api/optimizer.py scripts/update_universes.py''',
)
replace_once(
    ".github/workflows/ci.yml",
    '''      - name: Test score formulas
        run: npm run test:score
      - name: Install browser for end-to-end tests''',
    '''      - name: Test score formulas
        run: npm run test:score
      - name: Test optimizer search
        run: npm run test:optimizer
      - name: Install browser for end-to-end tests''',
)

worker_test = Path("tests/test_worker.mjs")
worker_text = worker_test.read_text(encoding="utf-8")
worker_text += r'''


test("optimizer routes proxy payloads larger than the ordinary API limit", async () => {
  const originalFetch = globalThis.fetch;
  let forwardedBytes = 0;
  globalThis.fetch = async (_url, options) => {
    forwardedBytes = options.body.byteLength;
    return Response.json({ results: [], metadata: {} });
  };

  try {
    const largeValue = "x".repeat(300 * 1024);
    const response = await worker.fetch(
      new Request("https://example.com/api/optimizer/verify", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ snapshot: { data: largeValue } }),
      }),
      { BACKEND_ORIGIN: "https://backend.example.com" },
    );
    assert.equal(response.status, 200);
    assert.ok(forwardedBytes > 256 * 1024);
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("ordinary API routes still reject payloads above 256 KiB", async () => {
  const response = await worker.fetch(
    new Request("https://example.com/api/backtest", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ value: "x".repeat(300 * 1024) }),
    }),
    { BACKEND_ORIGIN: "https://backend.example.com" },
  );
  assert.equal(response.status, 413);
});
'''
worker_test.write_text(worker_text, encoding="utf-8")

Path("scripts/apply_optimizer_integration.py").unlink()
Path(".github/workflows/apply-optimizer-integration.yml").unlink()
