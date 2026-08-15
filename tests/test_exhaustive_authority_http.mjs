import assert from "node:assert/strict";
import { Readable } from "node:stream";
import test from "node:test";

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
});

test("HTTP authority fails before numerical work when server combination budget is exceeded", async () => {
  const res = response();
  const candidates = Array.from({ length: 100 }, (_, index) => `S${String(index).padStart(3, "0")}`);
  await handler(
    request({
      candidateTickers: candidates,
      settings: { holdingCount: 5 },
    }),
    res,
  );

  assert.equal(res.statusCode, 422);
  const payload = JSON.parse(res.body);
  assert.match(payload.error, new RegExp(`exceeds ${MAX_SERVER_EXHAUSTIVE_COMBINATIONS}`));
});

test("HTTP authority allows only POST", async () => {
  const res = response();
  await handler(request({}, { method: "GET" }), res);
  assert.equal(res.statusCode, 405);
  assert.equal(JSON.parse(res.body).error, "Method not allowed");
});
