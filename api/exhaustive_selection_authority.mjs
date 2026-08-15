import { timingSafeEqual } from "node:crypto";
import { gunzipSync } from "node:zlib";

// The browser core re-exports this module through a cache-busted `?v=`
// specifier. Keep one plain, semantically-used server-side edge in the Vercel
// entrypoint so @vercel/node's dependency tracer always includes the physical
// module in the function bundle. This does not create another numerical authority.
import { MAX_EXHAUSTIVE_COMBINATIONS } from "../public/exhaustive-retention.js";
import {
  authorityIdentity,
  selectBestExhaustivePortfolio,
} from "../scripts/exhaustive_selection_authority.mjs";
import { combinationCountNumber } from "../public/exhaustive-optimizer-core.js";

export const config = { maxDuration: 240 };
export const EXHAUSTIVE_AUTHORITY_HTTP_CONTRACT_VERSION =
  "exhaustive-authority-http-2026-08-15.1";
export const MAX_SERVER_EXHAUSTIVE_COMBINATIONS = 500_000;
export const MAX_AUTHORITY_WIRE_BYTES = 3 * 1024 * 1024;
export const MAX_AUTHORITY_JSON_BYTES = 16 * 1024 * 1024;

if (MAX_SERVER_EXHAUSTIVE_COMBINATIONS > MAX_EXHAUSTIVE_COMBINATIONS) {
  throw new Error("server Exhaustive budget cannot exceed the existing engine ceiling");
}

function sendJson(response, status, payload) {
  response.statusCode = status;
  response.setHeader("content-type", "application/json; charset=utf-8");
  response.setHeader("cache-control", "no-store");
  response.setHeader("x-content-type-options", "nosniff");
  response.setHeader("x-exhaustive-authority-http-contract-version", EXHAUSTIVE_AUTHORITY_HTTP_CONTRACT_VERSION);
  const deploymentSha = String(process.env.VERCEL_GIT_COMMIT_SHA || "").trim();
  if (deploymentSha) response.setHeader("x-backteststock-deployment-sha", deploymentSha);
  response.end(JSON.stringify(payload));
}

function requestTooLarge(message = "Exhaustive authority request is too large") {
  const error = new Error(message);
  error.statusCode = 413;
  return error;
}

function invalidJson(message = "Exhaustive authority request must be valid JSON") {
  const error = new Error(message);
  error.statusCode = 400;
  return error;
}

function unsupportedEncoding(encoding) {
  const error = new Error(`Unsupported Exhaustive authority content encoding: ${encoding}`);
  error.statusCode = 415;
  return error;
}

function contentEncoding(request) {
  return String(request.headers?.["content-encoding"] || "identity").trim().toLowerCase() || "identity";
}

function decodeRawBody(buffer, encoding) {
  if (buffer.length > MAX_AUTHORITY_WIRE_BYTES) throw requestTooLarge();
  let decoded = buffer;
  if (encoding === "gzip") {
    try {
      decoded = gunzipSync(buffer, { maxOutputLength: MAX_AUTHORITY_JSON_BYTES });
    } catch (error) {
      if (error?.code === "ERR_BUFFER_TOO_LARGE") {
        throw requestTooLarge("Exhaustive authority decoded JSON is too large");
      }
      throw invalidJson("Exhaustive authority gzip body is invalid");
    }
  } else if (encoding !== "identity") {
    throw unsupportedEncoding(encoding);
  }
  if (decoded.length > MAX_AUTHORITY_JSON_BYTES) {
    throw requestTooLarge("Exhaustive authority decoded JSON is too large");
  }
  try {
    return JSON.parse(decoded.toString("utf8") || "{}");
  } catch {
    throw invalidJson();
  }
}

function validateParsedBody(body) {
  let encoded;
  try {
    encoded = Buffer.from(JSON.stringify(body));
  } catch {
    throw invalidJson();
  }
  if (encoded.length > MAX_AUTHORITY_JSON_BYTES) {
    throw requestTooLarge("Exhaustive authority decoded JSON is too large");
  }
  return body;
}

async function readJsonBody(request) {
  const declared = Number(request.headers?.["content-length"] || 0);
  if (Number.isFinite(declared) && declared > MAX_AUTHORITY_WIRE_BYTES) {
    throw requestTooLarge();
  }
  const encoding = contentEncoding(request);

  // @vercel/node may populate req.body before the function runs. A parsed
  // object is already decoded by the runtime; raw Buffer/string bodies still
  // honor Content-Encoding and the independent wire/decoded ceilings.
  if (request.body !== undefined && request.body !== null) {
    if (Buffer.isBuffer(request.body)) {
      return decodeRawBody(request.body, encoding);
    }
    if (typeof request.body === "string") {
      return decodeRawBody(Buffer.from(request.body), encoding);
    }
    if (typeof request.body === "object") {
      return validateParsedBody(request.body);
    }
    throw invalidJson();
  }

  const chunks = [];
  let total = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buffer.length;
    if (total > MAX_AUTHORITY_WIRE_BYTES) throw requestTooLarge();
    chunks.push(buffer);
  }
  return decodeRawBody(Buffer.concat(chunks), encoding);
}

function configuredInternalSecret() {
  return String(
    process.env.WALK_FORWARD_INTERNAL_SECRET
      || process.env.VERCEL_AUTOMATION_BYPASS_SECRET
      || "",
  ).trim();
}

function equalSecret(provided, expected) {
  const left = Buffer.from(String(provided || ""));
  const right = Buffer.from(String(expected || ""));
  return left.length === right.length && left.length > 0 && timingSafeEqual(left, right);
}

function requireMatchingDeployment(request) {
  const expected = String(process.env.VERCEL_GIT_COMMIT_SHA || "").trim();
  if (!expected) return;
  const provided = String(request.headers?.["x-backteststock-internal-deployment"] || "").trim();
  if (provided !== expected) {
    const error = new Error("Exhaustive authority caller deployment does not match");
    error.statusCode = 409;
    throw error;
  }
}

function requireSelectionSecret(request, payload) {
  if (payload?.type === "version") return;
  const expected = configuredInternalSecret();
  if (!expected) return;
  const provided = request.headers?.["x-backteststock-internal-secret"];
  if (!equalSecret(provided, expected)) {
    const error = new Error("Exhaustive authority selection requires internal authentication");
    error.statusCode = 401;
    throw error;
  }
}

function enforceServerBudget(payload) {
  if (payload?.type === "version") return;
  const candidates = payload?.candidateTickers;
  const holdingCount = Number(payload?.settings?.holdingCount);
  if (!Array.isArray(candidates) || !Number.isInteger(holdingCount)) return;
  const combinations = combinationCountNumber(candidates.length, holdingCount);
  if (combinations > MAX_SERVER_EXHAUSTIVE_COMBINATIONS) {
    const error = new Error(
      `server Exhaustive combination count ${combinations} exceeds ${MAX_SERVER_EXHAUSTIVE_COMBINATIONS}`,
    );
    error.statusCode = 422;
    throw error;
  }
}

export default async function handler(request, response) {
  if (request.method !== "POST") {
    response.setHeader("allow", "POST");
    sendJson(response, 405, { error: "Method not allowed" });
    return;
  }
  try {
    requireMatchingDeployment(request);
    const payload = await readJsonBody(request);
    requireSelectionSecret(request, payload);
    enforceServerBudget(payload);
    const result = payload?.type === "version"
      ? {
          ...authorityIdentity(),
          internalAuthMode: configuredInternalSecret()
            ? "secret-plus-deployment"
            : "deployment-bound-bounded-fallback",
        }
      : selectBestExhaustivePortfolio(payload);
    sendJson(response, 200, result);
  } catch (error) {
    const status = Number(error?.statusCode) || 422;
    sendJson(response, status, {
      error: error instanceof Error ? error.message : String(error),
    });
  }
}
