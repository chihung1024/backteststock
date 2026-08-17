export interface WalkForwardPeriodDraft {
  id: string;
  periodId: string;
  trainingStart: string;
  trainingEnd: string;
  decisionDate: string;
  evaluationStart: string;
  evaluationEnd: string;
}

export interface WalkForwardWorkspaceModel {
  schemaVersion: 1;
  universe: string;
  benchmark: string;
  holdingCount: number;
  initialAmountTwd: number;
  transitionCostBps: number;
  periods: WalkForwardPeriodDraft[];
}

export interface WalkForwardValidationIssue {
  field: string;
  message: string;
}

export interface WalkForwardApiPeriod {
  periodId: string;
  trainingStart: string;
  trainingEnd: string;
  decisionDate: string;
  evaluationStart: string;
  evaluationEnd: string;
}

export interface WalkForwardApiRequest {
  periods: WalkForwardApiPeriod[];
  selector: {
    universe: string;
    benchmark: string;
    holdingCount: number;
  };
  execution: {
    initialAmountTwd: number;
    transitionCostBps: number;
  };
}

export interface WalkForwardHealthResponse {
  status: string;
  service: string;
  api_contract_version: string;
  job_contract_version: string;
  deployment_sha: string;
}

export type WalkForwardAdmissionStatus = "eligible" | "blocked";

export interface WalkForwardAdmissionUniverse {
  id: string;
  name: string;
  status: WalkForwardAdmissionStatus;
  reason?: string;
  minimumMemberCount?: number;
  earliestDecisionDate?: string;
  latestDecisionDate?: string;
  recommendedDecisionDate?: string;
  recommendedMemberCount?: number;
  recommendedHoldingCount?: number;
  recommendedCombinationCount?: number;
  sourceAsOf?: string;
  evidenceAvailableAsOf?: string;
  version?: string;
}

export interface WalkForwardAdmissionResponse {
  contractVersion: string;
  asOfDate: string;
  limits: {
    maxCandidates: number;
    maxCombinationsPerPeriod: number;
    maxHoldingCount: number;
    pitMaxAgeDays: number;
  };
  universes: WalkForwardAdmissionUniverse[];
  recommended: null | {
    universe: string;
    decisionDate: string;
    holdingCount: number;
    memberCount: number;
    combinationCount: number;
  };
}

export type WalkForwardMetricValue = number | string | null;

export interface WalkForwardDecisionResponse {
  contractVersion: string;
  period: {
    periodId: string;
    trainingStart: string;
    trainingEnd: string;
    decisionDate: string;
    decisionTiming: string;
    evaluationStart: string;
    evaluationEnd: string;
  };
  pitUniverse: {
    universeId: string;
    requestedAsOf: string;
    sourceAsOf: string;
    evidenceAvailableAsOf: string;
    fetchedAt: string;
    version: string;
    checksum: string;
    members: string[];
    membershipPolicy: string;
    membershipAuthoritative: boolean;
    sourceLabel: string;
    sourceUrl: string;
    sourceIsProxy: boolean;
  };
  trainingDataset: {
    datasetHash: string;
    effectiveStart: string;
    effectiveEnd: string;
  };
  selector: {
    contractVersion: string;
    rule: string;
    parameters: Record<string, unknown>;
  };
  eligibleCandidates: string[];
  selectedConstituents: string[];
  weights: number[];
  decisionHash: string;
}

export interface WalkForwardPeriodAuditResponse {
  period_id: string;
  pit_member_count: number;
  exhaustive_combination_count: number;
  training_dataset_hash: string;
  authority_dataset_hash: string;
  decision_hash: string;
  evaluation_dataset_hash: string;
}

export interface WalkForwardOosPeriodResponse {
  period_id: string;
  decision_hash: string;
  evaluation_dataset_hash: string;
  requested_start: string;
  requested_end: string;
  effective_start: string;
  effective_end: string;
  selected_constituents: string[];
  weights: number[];
  transition_traded_notional: number;
  transition_cost: number;
}

export interface WalkForwardResultResponse {
  contractVersion: string;
  jobHash: string;
  hashAlgorithm: string;
  status: "completed" | string;
  asOfDate: string;
  asOfPolicy: string;
  selectorPolicy: string;
  oosPolicy: string;
  request: Record<string, unknown>;
  periods: WalkForwardPeriodAuditResponse[];
  decisions: WalkForwardDecisionResponse[];
  oos: {
    contractVersion: string;
    executionPolicy: string;
    gapPolicy: string;
    returnComponentPolicy: string;
    periods: WalkForwardOosPeriodResponse[];
    ledger: {
      contractVersion: string;
      valuationCurrency: "TWD" | string;
      equity: Array<{ date: string; value: number }>;
      returnIndex: Array<{ date: string; value: number }>;
      transactionCosts: number;
      borrowingCosts: number;
      rebalanceCount: number;
      liquidated: boolean;
      warnings: string[];
      events: Array<{ date: string; type: string; details: Record<string, unknown> }>;
    };
    metrics: {
      metrics: Record<string, WalkForwardMetricValue>;
      xirr: Record<string, unknown>;
      tail_risk: Record<string, unknown>;
      drawdown_events: Array<Record<string, unknown>>;
      annual_returns: Array<Record<string, unknown>>;
      monthly_returns: Array<Record<string, unknown>>;
      metadata: Record<string, unknown>;
    };
  };
}
