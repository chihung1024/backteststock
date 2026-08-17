import type {
  WalkForwardApiRequest,
  WalkForwardResultResponse,
} from "./walkForwardTypes";

export interface ResearchRunHealthResponse {
  status: string;
  service: string;
  contractVersion: string;
  durableStore: string;
  schemaReady: boolean;
}

export interface ResearchRunSummary {
  runId: string;
  sourceRunId: string | null;
  name: string;
  jobHash: string;
  resultContractVersion: string;
  decisionCount: number;
  createdAt?: string;
}

export interface ResearchRunCreateResponse {
  contractVersion: string;
  libraryId: string;
  libraryCapability?: string;
  run: ResearchRunSummary;
  result: WalkForwardResultResponse;
}

export interface ResearchRunListResponse {
  contractVersion: string;
  libraryId: string;
  runs: ResearchRunSummary[];
}

export interface ResearchRunDetailResponse {
  contractVersion: string;
  libraryId: string;
  run: ResearchRunSummary;
  executionRequest: WalkForwardApiRequest;
  result: WalkForwardResultResponse;
}
