import assert from "node:assert/strict";
import test from "node:test";

import worker from "../worker/index.js";
import {
  applyTrustedBackendHeaders,
  enforceEdgeRequestPolicy,
} from "../worker/security.js";

function limiter(success = true) {
  const keys = [];
  return {
    keys,
    async limit({ key }) {
      keys.push(key);
      return { success };
    },
  };
}

function protectedEnv(overrides = {}) {
  return {
    BACKEND_ORIGIN: "https://backend.example",
    BACKTESTSTOCK_EDGE_SECRET: "test-edge-secret-with-at-least-32-bytes",
    BACKTESTSTOCK_REQUIRE_EDGE_AUTH: "true",
    BACKTESTSTOCK_REQUIRE_RATE_LIMIT: "true",
    API_RATE_LIMITER: limiter(),
    EXPENSIVE_API_RATE_LIMITER: limiter(),
    ...overrides,
  };
}

test("required edge authentication fails closed when its secret is absent", async () => {
  const decision = await enforceEdgeRequestPolicy(
    new Request("https://example.com/api/health"),
    {
      BACKTESTSTOCK_REQUIRE_EDGE_AUTH: "true",
      BACKTESTSTOCK_REQUIRE_RATE_LIMIT: "false",
    },
  );

  assert.equal(decision.ok, false);
  assert.equal(decision.status, 503);
  assert.equal(decision.code, "edge_auth_not_configured");
});

test("invalid required-policy modes fail closed instead of disabling protection", async () => {
  const authDecision = await enforceEdgeRequestPolicy(
    new Request("https://example.com/api/health"),
    {
      BACKTESTSTOCK_REQUIRE_EDGE_AUTH: "treu",
      BACKTESTSTOCK_REQUIRE_RATE_LIMIT: "false",
    },
  );
  assert.equal(authDecision.ok, false);
  assert.equal(authDecision.code, "edge_auth_not_configured");

  const rateDecision = await enforceEdgeRequestPolicy(
    new Request("https://example.com/api/health"),
    protectedEnv({
      BACKTESTSTOCK_REQUIRE_RATE_LIMIT: "treu",
      API_RATE_LIMITER: undefined,
    }),
  );
  assert.equal(rateDecision.ok, false);
  assert.equal(rateDecision.code, "rate_limit_not_configured");
});

test("expensive and general routes use distinct rate-limit bindings", async () => {
  const env = protectedEnv();
  const requestHeaders = { "cf-connecting-ip": "198.51.100.8" };
  const general = await enforceEdgeRequestPolicy(
    new Request("https://example.com/api/health", { headers: requestHeaders }),
    env,
  );
  const expensive = await enforceEdgeRequestPolicy(
    new Request("https://example.com/api/scan", { headers: requestHeaders }),
    env,
  );

  assert.equal(general.ok, true);
  assert.equal(expensive.ok, true);
  assert.equal(env.API_RATE_LIMITER.keys.length, 1);
  assert.equal(env.EXPENSIVE_API_RATE_LIMITER.keys.length, 1);
  assert.match(env.API_RATE_LIMITER.keys[0], /:\/api\/health$/u);
  assert.match(env.EXPENSIVE_API_RATE_LIMITER.keys[0], /:\/api\/scan$/u);
  assert.doesNotMatch(env.EXPENSIVE_API_RATE_LIMITER.keys[0], /198\.51\.100\.8/u);
});

test("rate-limit denial returns a bounded retry contract", async () => {
  const env = protectedEnv({ EXPENSIVE_API_RATE_LIMITER: limiter(false) });
  const decision = await enforceEdgeRequestPolicy(
    new Request("https://example.com/api/backtest"),
    env,
  );

  assert.equal(decision.ok, false);
  assert.equal(decision.status, 429);
  assert.equal(decision.code, "rate_limit_exceeded");
  assert.equal(decision.retryAfter, 60);
});

test("trusted backend headers replace spoofed identity and sensitive headers", async () => {
  const env = protectedEnv();
  const request = new Request("https://example.com/api/scan", {
    headers: { "cf-connecting-ip": "198.51.100.8" },
  });
  const identity = await enforceEdgeRequestPolicy(request, env);
  const headers = applyTrustedBackendHeaders(new Headers({
    authorization: "Bearer browser-token",
    cookie: "session=browser",
    forwarded: "for=203.0.113.10;proto=http",
    "x-forwarded-for": "203.0.113.10",
    "x-forwarded-host": "attacker.example",
    "x-forwarded-port": "81",
    "x-forwarded-proto": "http",
    "x-real-ip": "203.0.113.11",
    "x-client-ip": "203.0.113.12",
    "true-client-ip": "203.0.113.13",
    "cf-pseudo-ipv4": "203.0.113.14",
    "x-backteststock-edge-auth": "attacker",
    "x-backteststock-client-id": "attacker-id",
  }), identity);

  assert.equal(headers.get("authorization"), null);
  assert.equal(headers.get("cookie"), null);
  for (const name of [
    "forwarded",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-port",
    "x-forwarded-proto",
    "x-real-ip",
    "x-client-ip",
    "true-client-ip",
    "cf-pseudo-ipv4",
  ]) {
    assert.equal(headers.get(name), null, `${name} must be stripped`);
  }
  assert.equal(
    headers.get("x-backteststock-edge-auth"),
    env.BACKTESTSTOCK_EDGE_SECRET,
  );
  assert.equal(headers.get("x-backteststock-client-id"), identity.clientId);
  assert.notEqual(headers.get("x-backteststock-client-id"), "attacker-id");
});

test("Worker injects authenticated identity before proxying a protected request", async () => {
  const originalFetch = globalThis.fetch;
  let captured;
  globalThis.fetch = async (_url, init) => {
    captured = init;
    return new Response(JSON.stringify([{ ticker: "AAA", status: "ok" }]), {
      status: 200,
      headers: {
        "content-type": "application/json",
        "x-scan-requested": "1",
        "x-scan-resolved": "1",
      },
    });
  };

  try {
    const response = await worker.fetch(new Request("https://example.com/api/scan", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "cf-connecting-ip": "198.51.100.8",
        authorization: "Bearer browser-token",
        cookie: "session=browser",
        forwarded: "for=203.0.113.10;proto=http",
        "x-real-ip": "203.0.113.11",
        "x-forwarded-proto": "http",
        "x-backteststock-edge-auth": "attacker",
        "x-backteststock-client-id": "attacker-id",
      },
      body: JSON.stringify({ tickers: ["AAA"], benchmark: "SPY" }),
    }), protectedEnv());

    assert.equal(response.status, 200);
    assert.equal(captured.headers.get("authorization"), null);
    assert.equal(captured.headers.get("cookie"), null);
    assert.equal(captured.headers.get("forwarded"), null);
    assert.equal(captured.headers.get("x-real-ip"), null);
    assert.equal(captured.headers.get("x-forwarded-proto"), "https");
    assert.equal(
      captured.headers.get("x-backteststock-edge-auth"),
      "test-edge-secret-with-at-least-32-bytes",
    );
    assert.notEqual(captured.headers.get("x-backteststock-client-id"), "attacker-id");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("required rate-limit binding fails closed before reaching the backend", async () => {
  const originalFetch = globalThis.fetch;
  let called = false;
  globalThis.fetch = async () => {
    called = true;
    throw new Error("backend must not be called");
  };

  try {
    const env = protectedEnv({ EXPENSIVE_API_RATE_LIMITER: undefined });
    const response = await worker.fetch(new Request("https://example.com/api/scan", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{}",
    }), env);

    assert.equal(response.status, 503);
    assert.equal((await response.json()).code, "rate_limit_not_configured");
    assert.equal(called, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
