import type {
  WalkForwardAdmissionResponse,
  WalkForwardApiRequest,
  WalkForwardHealthResponse,
  WalkForwardResultResponse,
} from "./walkForwardTypes";

const WALK_FORWARD_API_PREFIX = "/api/v1/research/walk-forward";

export class WalkForwardApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "WalkForwardApiError";
    this.status = status;
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text) as unknown;
    } catch {
      throw new WalkForwardApiError(
        response.ok ? "Walk-Forward 服務回傳無效 JSON。" : text.slice(0, 400),
        response.status,
      );
    }
  }
  if (!response.ok) {
    const record = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
    throw new WalkForwardApiError(
      String(record.detail ?? record.error ?? `HTTP ${response.status}`),
      response.status,
    );
  }
  return payload as T;
}

export async function checkWalkForwardHealth(signal?: AbortSignal): Promise<WalkForwardHealthResponse> {
  const response = await fetch(`${WALK_FORWARD_API_PREFIX}/health`, {
    headers: { accept: "application/json" },
    cache: "no-store",
    ...(signal ? { signal } : {}),
  });
  return parseResponse<WalkForwardHealthResponse>(response);
}

export async function getWalkForwardAdmission(signal?: AbortSignal): Promise<WalkForwardAdmissionResponse> {
  const response = await fetch(`${WALK_FORWARD_API_PREFIX}/admission`, {
    headers: { accept: "application/json" },
    cache: "no-store",
    ...(signal ? { signal } : {}),
  });
  return parseResponse<WalkForwardAdmissionResponse>(response);
}

export async function runWalkForward(
  request: WalkForwardApiRequest,
  signal?: AbortSignal,
): Promise<WalkForwardResultResponse> {
  const response = await fetch(WALK_FORWARD_API_PREFIX, {
    method: "POST",
    headers: {
      accept: "application/json",
      "content-type": "application/json",
    },
    body: JSON.stringify(request),
    cache: "no-store",
    ...(signal ? { signal } : {}),
  });
  return parseResponse<WalkForwardResultResponse>(response);
}
