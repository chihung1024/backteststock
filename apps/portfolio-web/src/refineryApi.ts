import type {
  RefineryAnalyzeResponse,
  RefineryApiRequest,
  RefineryPreflightResponse,
} from "./refineryTypes";

const REFINERY_API_PREFIX = "/api/v1/refinery";

export class RefineryApiError extends Error {
  readonly status: number;
  readonly requestId: string | null;
  readonly code: string | null;

  constructor(message: string, status: number, requestId: string | null, code: string | null) {
    super(message);
    this.name = "RefineryApiError";
    this.status = status;
    this.requestId = requestId;
    this.code = code;
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  const requestId = response.headers.get("x-request-id");
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text) as unknown;
    } catch {
      throw new RefineryApiError(
        response.ok ? "Refinery API 回傳無效 JSON。" : text.slice(0, 400),
        response.status,
        requestId,
        null,
      );
    }
  }

  if (!response.ok) {
    const record = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
    const error = record.error && typeof record.error === "object"
      ? (record.error as Record<string, unknown>)
      : {};
    const message = typeof error.message === "string"
      ? error.message
      : `Refinery API HTTP ${response.status}`;
    const code = typeof error.code === "string" ? error.code : null;
    throw new RefineryApiError(message, response.status, requestId, code);
  }
  return payload as T;
}

async function post<T>(path: "preflight" | "analyze", request: RefineryApiRequest, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${REFINERY_API_PREFIX}/${path}`, {
    method: "POST",
    headers: {
      accept: "application/json",
      "content-type": "application/json",
    },
    body: JSON.stringify(request),
    cache: "no-store",
    ...(signal ? { signal } : {}),
  });
  return parseResponse<T>(response);
}

export function runRefineryPreflight(
  request: RefineryApiRequest,
  signal?: AbortSignal,
): Promise<RefineryPreflightResponse> {
  return post<RefineryPreflightResponse>("preflight", request, signal);
}

export function runRefineryAnalyze(
  request: RefineryApiRequest,
  signal?: AbortSignal,
): Promise<RefineryAnalyzeResponse> {
  return post<RefineryAnalyzeResponse>("analyze", request, signal);
}
