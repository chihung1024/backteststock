import {
  authorityIdentity,
  selectBestExhaustivePortfolio,
} from "../scripts/exhaustive_selection_authority.mjs";
import { combinationCountNumber } from "../public/exhaustive-optimizer-core.js";

export const EXHAUSTIVE_AUTHORITY_HTTP_CONTRACT_VERSION =
  "exhaustive-authority-http-2026-08-15.1";
export const MAX_SERVER_EXHAUSTIVE_COMBINATIONS = 500_000;
const MAX_REQUEST_BYTES = 3 * 1024 * 1024;

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

function requestTooLarge() {
  const error = new Error("Exhaustive authority request is too large");
  error.statusCode = 413;
  return error;
}

function invalidJson() {
  const error = new Error("Exhaustive authority request must be valid JSON");
  error.statusCode = 400;
  return error;
}

function parseRawJson(raw) {
  if (Buffer.byteLength(raw) > MAX_REQUEST_BYTES) throw requestTooLarge();
  try {
    return JSON.parse(raw || "{}");
  } catch {
    throw invalidJson();
  }
}

async function readJsonBody(request) {
  const declared = Number(request.headers?.["content-length"] || 0);
  if (Number.isFinite(declared) && declared > MAX_REQUEST_BYTES) throw requestTooLarge();

  // @vercel/node may populate req.body before the function runs. Support that
  // runtime shape without assuming the request remains an unread stream.
  if (request.body !== undefined && request.body !== null) {
    if (Buffer.isBuffer(request.body)) {
      return parseRawJson(request.body.toString("utf8"));
    }
    if (typeof request.body === "string") {
      return parseRawJson(request.body);
    }
    if (typeof request.body === "object") {
      let encoded;
      try {
        encoded = JSON.stringify(request.body);
      } catch {
        throw invalidJson();
      }
      if (Buffer.byteLength(encoded) > MAX_REQUEST_BYTES) throw requestTooLarge();
      return request.body;
    }
    throw invalidJson();
  }

  const chunks = [];
  let total = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buffer.length;
    if (total > MAX_REQUEST_BYTES) throw requestTooLarge();
    chunks.push(buffer);
  }
  return parseRawJson(Buffer.concat(chunks).toString("utf8"));
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
    enforceServerBudget(payload);
    const result = payload?.type === "version"
      ? authorityIdentity()
      : selectBestExhaustivePortfolio(payload);
    sendJson(response, 200, result);
  } catch (error) {
    const status = Number(error?.statusCode) || 422;
    sendJson(response, status, {
      error: error instanceof Error ? error.message : String(error),
    });
  }
}
