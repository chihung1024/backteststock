import type {
  BacktestResponse,
  PortfolioApiRequest,
  PreflightResponse,
  SearchResult,
} from "./types";

const API_PREFIX = "/api/v3/portfolio";

export class PortfolioApiError extends Error {
  readonly status: number;
  readonly requestId: string | null;

  constructor(message: string, status: number, requestId: string | null) {
    super(message);
    this.name = "PortfolioApiError";
    this.status = status;
    this.requestId = requestId;
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
      if (!response.ok) {
        throw new PortfolioApiError(text.slice(0, 400), response.status, requestId);
      }
      throw new PortfolioApiError("伺服器回傳無效 JSON。", response.status, requestId);
    }
  }
  if (!response.ok) {
    const record = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
    const detail = record.detail ?? record.error ?? `HTTP ${response.status}`;
    throw new PortfolioApiError(String(detail), response.status, requestId);
  }
  return payload as T;
}

export async function checkHealth(signal?: AbortSignal): Promise<Record<string, string>> {
  const response = await fetch(`${API_PREFIX}/health`, {
    headers: { accept: "application/json" },
    cache: "no-store",
    signal,
  });
  return parseResponse<Record<string, string>>(response);
}

export async function searchAssets(query: string, signal?: AbortSignal): Promise<SearchResult[]> {
  const parameters = new URLSearchParams({ q: query, limit: "8" });
  const response = await fetch(`${API_PREFIX}/assets/search?${parameters}`, {
    headers: { accept: "application/json" },
    cache: "no-store",
    signal,
  });
  return parseResponse<SearchResult[]>(response);
}

async function post<T>(path: string, request: PortfolioApiRequest, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_PREFIX}/${path}`, {
    method: "POST",
    headers: {
      accept: "application/json",
      "content-type": "application/json",
    },
    body: JSON.stringify(request),
    cache: "no-store",
    signal,
  });
  return parseResponse<T>(response);
}

export function runPreflight(
  request: PortfolioApiRequest,
  signal?: AbortSignal,
): Promise<PreflightResponse> {
  return post<PreflightResponse>("preflight", request, signal);
}

export function runBacktest(
  request: PortfolioApiRequest,
  signal?: AbortSignal,
): Promise<BacktestResponse> {
  return post<BacktestResponse>("backtests", request, signal);
}
