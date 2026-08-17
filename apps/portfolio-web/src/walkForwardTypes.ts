export type WalkForwardStrategy = "exhaustive" | "dual_momentum";

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
  schemaVersion: 2;
  strategy: WalkForwardStrategy;
  universe: string;
  benchmark: string;
  holdingCount: number;
  riskySymbolsText: string;
  defensiveSymbolsText: string;
  lookbackMonths: number;
  topK: number;
  absoluteThresholdPct: number;
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

export interface WalkForwardExhaustiveSelectorRequest {
  universe: string;
  benchmark: string;
  holdingCount: number;
}

export interface WalkForwardDualMomentumSelectorRequest {
  strategy: "dual_momentum";
  riskySymbols: string[];
  defensiveSymbols: string[];
  lookbackMonths: number;
  topK: number;
  absoluteThreshold: number;
}

export type WalkForwardApiSelectorRequest =
  | WalkForwardExhaustiveSelectorRequest
  | WalkForwardDualMomentumSelectorRequest;

export interface WalkForwardApiRequest {
  periods: WalkForwardApiPeriod[];
  selector: WalkForwardApiSelectorRequest;
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
  dual_momentum_job_contract_version?: string;
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

export interface WalkForwardPitUniverseResponse {
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
}

export interface WalkForwardConfiguredUniverseResponse {
  contractVersion: string;
  provenanceType: "configured-request" | string;
  members: string[];
  universeHash: string;
}

export interface WalkForwardMomentumRankingEvidence {
  symbol: string;
  lookbackMonths: number;
  requestedStart: string;
  baselineDate: string;
  endDate: string;
  baselineLevelTwd: number;
  endLevelTwd: number;
  totalReturn: number;
  relativeRank: number;
  absolutePass?: boolean;
}

export interface WalkForwardSelectionEvidence {
  contractVersion?: string;
  signalAsOf?: string;
  lookbackMonths?: number;
  absoluteThreshold?: number;
  boundaryToleranceCalendarDays?: number;
  signalAuthority?: string;
  regime?: "risk_on" | "defensive" | string;
  fallbackReason?: string | null;
  riskyRanking?: WalkForwardMomentumRankingEvidence[];
  defensiveRanking?: WalkForwardMomentumRankingEvidence[];
  selected?: string[];
  [key: string]: unknown;
}

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
  pitUniverse?: WalkForwardPitUniverseResponse;
  configuredUniverse?: WalkForwardConfiguredUniverseResponse;
  selectionEvidence?: WalkForwardSelectionEvidence;
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
  pit_member_count?: number;
  configured_member_count?: number;
  exhaustive_combination_count?: number;
  training_dataset_hash: string;
  authority_dataset_hash?: string;
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
