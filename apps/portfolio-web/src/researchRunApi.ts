import type {
  ResearchRunCreateResponse,
  ResearchRunDetailResponse,
  ResearchRunHealthResponse,
  ResearchRunListResponse,
} from "./researchRunTypes";
import type { WalkForwardApiRequest } from "./walkForwardTypes";

const RESEARCH_RUNS_API = "/api/v1/research/runs";

export class ResearchRunApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ResearchRunApiError";
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
      throw new ResearchRunApiError(
        response.ok ? "Research Library 服務回傳無效 JSON。" : text.slice(0, 400),
        response.status,
      );
    }
  }
  if (!response.ok) {
    const record = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
    throw new ResearchRunApiError(String(record.error ?? record.detail ?? `HTTP ${response.status}`), response.status);
  }
  return payload as T;
}

function credentialHeaders(capability?: string | null): HeadersInit {
  return capability ? { authorization: `Bearer ${capability}` } : {};
}

export function isResearchLibraryCapability(value: string): boolean {
  return /^rrl_[A-Za-z0-9_-]{43}$/u.test(value.trim());
}

export async function checkResearchRunHealth(signal?: AbortSignal): Promise<ResearchRunHealthResponse> {
  const response = await fetch(`${RESEARCH_RUNS_API}/health`, {
    headers: { accept: "application/json" },
    cache: "no-store",
    ...(signal ? { signal } : {}),
  });
  return parseResponse<ResearchRunHealthResponse>(response);
}

export async function createResearchRun(
  name: string,
  request: WalkForwardApiRequest,
  capability?: string | null,
  signal?: AbortSignal,
): Promise<ResearchRunCreateResponse> {
  const response = await fetch(RESEARCH_RUNS_API, {
    method: "POST",
    headers: {
      accept: "application/json",
      "content-type": "application/json",
      ...credentialHeaders(capability),
    },
    body: JSON.stringify({ name, request }),
    cache: "no-store",
    ...(signal ? { signal } : {}),
  });
  return parseResponse<ResearchRunCreateResponse>(response);
}

export async function listResearchRuns(
  capability: string,
  signal?: AbortSignal,
): Promise<ResearchRunListResponse> {
  const response = await fetch(`${RESEARCH_RUNS_API}?limit=100`, {
    headers: { accept: "application/json", ...credentialHeaders(capability) },
    cache: "no-store",
    ...(signal ? { signal } : {}),
  });
  return parseResponse<ResearchRunListResponse>(response);
}

export async function getResearchRun(
  runId: string,
  capability: string,
  signal?: AbortSignal,
): Promise<ResearchRunDetailResponse> {
  const response = await fetch(`${RESEARCH_RUNS_API}/${encodeURIComponent(runId)}`, {
    headers: { accept: "application/json", ...credentialHeaders(capability) },
    cache: "no-store",
    ...(signal ? { signal } : {}),
  });
  return parseResponse<ResearchRunDetailResponse>(response);
}

export async function rerunResearchRun(
  runId: string,
  capability: string,
  signal?: AbortSignal,
): Promise<ResearchRunCreateResponse> {
  const response = await fetch(`${RESEARCH_RUNS_API}/${encodeURIComponent(runId)}/rerun`, {
    method: "POST",
    headers: { accept: "application/json", ...credentialHeaders(capability) },
    cache: "no-store",
    ...(signal ? { signal } : {}),
  });
  return parseResponse<ResearchRunCreateResponse>(response);
}
