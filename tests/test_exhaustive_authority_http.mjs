import assert from "node:assert/strict";
import { Readable } from "node:stream";
import test from "node:test";
import { gzipSync } from "node:zlib";

import handler, {
  EXHAUSTIVE_AUTHORITY_HTTP_CONTRACT_VERSION,
  MAX_SERVER_EXHAUSTIVE_COMBINATIONS,
} from "../api/exhaustive_selection_authority.mjs";

function request(payload, { method = "POST", headers = {} } = {}) {
  const body = JSON.stringify(payload);
  const stream = Readable.from([Buffer.from(body)]);
  stream.method = method;
  stream.headers = {
    "content-type": "application/json",
    "content-length": String(Buffer.byteLength(body)),
    ...headers,
  };
  return stream;
}

function gzipRequest(payload, { method = "POST", headers = {} } = {}) {
  const body = gzipSync(Buffer.from(JSON.stringify(payload)));
  const stream = Readable.from([body]);
  stream.method = method;
  stream.headers = {
    "content-type": "application/json",
    "content-encoding": "gzip",
    "content-length": String(body.length),
    ...headers,
  };
  return stream;
}

function parsedRequest(payload, { method = "POST", headers = {} } = {}) {
  return {
    method,
    body: payload,
    headers: {
      "content-type": "application/json",
      "content-length": String(Buffer.byteLength(JSON.stringify(payload))),
      ...headers,
    },
  };
}

function response() {
  const headers = new Map();
  return {
    statusCode: 200,
    body: "",
    setHeader(name, value) {
      headers.set(String(name).toLowerCase(), String(value));
    },
    end(value = "") {
      this.body += String(value);
    },
    header(name) {
      return headers.get(String(name).toLowerCase()) ?? null;
    },
  };
}

function oversizedPayload() {
  return {
    candidateTickers: Array.from(
      { length: 100 },
      (_, index) => `S${String(index).padStart(3, "0")}`,
    ),
    settings: { holdingCount: 5 },
  };
}

test("HTTP authority version endpoint exposes the existing JS authority identity", async () => {
  const res = response();
  await handler(request({ type: "version" }), res);

  assert.equal(res.statusCode, 200);
  assert.equal(
    res.header("x-exhaustive-authority-http-contract-version"),
    EXHAUSTIVE_AUTHORITY_HTTP_CONTRACT_VERSION,
  );
  const payload = JSON.parse(res.body);
  assert.match(payload.authorityVersion, /^exhaustive-/u);
  assert.match(payload.bridgeVersion, /^exhaustive-selection-authority-/u);
  assert.match(payload.internalAuthMode, /^(secret-plus-deployment|deployment-bound-bounded-fallback)$/u);
});

test("HTTP authority accepts gzip JSON without changing authority identity", async () => {
  const res = response();
  await handler(gzipRequest({ type: "version" }), res);

  assert.equal(res.statusCode, 200);
  const payload = JSON.parse(res.body);
  assert.match(payload.authorityVersion, /^exhaustive-/u);
  assert.match(payload.bridgeVersion, /^exhaustive-selection-authority-/u);
});

test("HTTP authority accepts a Vercel-style pre-parsed request body", async () => {
  const res = response();
  await handler(parsedRequest({ type: "version" }), res);

  assert.equal(res.statusCode, 200);
  const payload = JSON.parse(res.body);
  assert.match(payload.authorityVersion, /^exhaustive-/u);
  assert.match(payload.bridgeVersion, /^exhaustive-selection-authority-/u);
});

test("HTTP authority rejects unsupported content encodings", async () => {
  const res = response();
  await handler(
    request({ type: "version" }, { headers: { "content-encoding": "br" } }),
    res,
  );
  assert.equal(res.statusCode, 415);
});

test("HTTP authority fails before numerical work when server combination budget is exceeded", async () => {
  const res = response();
  await handler(request(oversizedPayload()), res);

  assert.equal(res.statusCode, 422);
  const payload = JSON.parse(res.body);
  assert.match(payload.error, new RegExp(`exceeds ${MAX_SERVER_EXHAUSTIVE_COMBINATIONS}`));
});

test("HTTP authority requires configured internal secret for selection but not version", async () => {
  const previous = process.env.WALK_FORWARD_INTERNAL_SECRET;
  process.env.WALK_FORWARD_INTERNAL_SECRET = "fixture-secret";
  try {
    const versionResponse = response();
    await handler(request({ type: "version" }), versionResponse);
    assert.equal(versionResponse.statusCode, 200);
    assert.equal(JSON.parse(versionResponse.body).internalAuthMode, "secret-plus-deployment");

    const denied = response();
    await handler(request(oversizedPayload()), denied);
    assert.equal(denied.statusCode, 401);

    const admitted = response();
    await handler(
      request(oversizedPayload(), {
        headers: { "x-backteststock-internal-secret": "fixture-secret" },
      }),
      admitted,
    );
    assert.equal(admitted.statusCode, 422);
    assert.match(
      JSON.parse(admitted.body).error,
      new RegExp(`exceeds ${MAX_SERVER_EXHAUSTIVE_COMBINATIONS}`),
    );
  } finally {
    if (previous === undefined) delete process.env.WALK_FORWARD_INTERNAL_SECRET;
    else process.env.WALK_FORWARD_INTERNAL_SECRET = previous;
  }
});

test("HTTP authority allows only POST", async () => {
  const res = response();
  await handler(request({}, { method: "GET" }), res);
  assert.equal(res.statusCode, 405);
  assert.equal(JSON.parse(res.body).error, "Method not allowed");
});
