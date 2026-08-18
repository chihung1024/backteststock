export type WalkForwardStrategy = "exhaustive" | "dual_momentum";
export type WalkForwardAllocationMethod = "equal" | "inverse_volatility" | "risk_parity_erc";
export type WalkForwardOptimizationMode = "manual" | "auto";

export interface WalkForwardPeriodDraft {
  id: string;
  periodId: string;
  trainingStart: string;
  trainingEnd: string;
  decisionDate: string;
  evaluationStart: string;
  evaluationEnd: string;
}

export interface WalkForwardParameterOptimizationSearchSpace {
  lookbackMonths: number[];
  topK: number[];
  absoluteThresholds: number[];
  allocationMethods: WalkForwardAllocationMethod[];
}

export interface WalkForwardParameterOptimizationInnerValidation {
  foldCount: number;
  evaluationMonths: number;
  stepMonths: number;
}

export interface WalkForwardWorkspaceModel {
  schemaVersion: 4;
  strategy: WalkForwardStrategy;
  allocationMethod: WalkForwardAllocationMethod;
  optimizationMode: WalkForwardOptimizationMode;
  optimizationSearchSpace: WalkForwardParameterOptimizationSearchSpace;
  optimizationInnerValidation: WalkForwardParameterOptimizationInnerValidation;
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

export interface WalkForwardDualMomentumManualSelectorRequest {
  strategy: "dual_momentum";
  riskySymbols: string[];
  defensiveSymbols: string[];
  lookbackMonths: number;
  topK: number;
  absoluteThreshold: number;
  allocationMethod: WalkForwardAllocationMethod;
}

export interface WalkForwardParameterOptimizationRequest {
  searchSpace: WalkForwardParameterOptimizationSearchSpace;
  innerValidation: WalkForwardParameterOptimizationInnerValidation;
}

export interface WalkForwardDualMomentumAutoSelectorRequest {
  strategy: "dual_momentum";
  riskySymbols: string[];
  defensiveSymbols: string[];
  parameterOptimization: WalkForwardParameterOptimizationRequest;
}

export type WalkForwardDualMomentumSelectorRequest =
  | WalkForwardDualMomentumManualSelectorRequest
  | WalkForwardDualMomentumAutoSelectorRequest;

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
  dual_momentum_allocation_job_contract_version?: string;
  dual_momentum_parameter_optimization_job_contract_version?: string;
  max_parameter_candidates?: number;
  max_inner_folds?: number;
  max_tuning_evaluations_per_job?: number;
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

export interface WalkForwardAllocationEvidence {
  contractVersion: string;
  riskMathContractVersion: string;
  method: WalkForwardAllocationMethod;
  symbols: string[];
  weights: number[];
  status: string;
  inputObservations: number;
  completeCaseObservations: number;
  minimumCompleteCaseObservations: number;
  returnFrequency: string;
  valuationCurrency: string;
  covariance: null | {
    method: string | null;
    annualization: number | null;
    shrinkage: number | null;
    isPsd: boolean | null;
    numericalRank: number | null;
    conditionNumber: number | null;
  };
  portfolioVolatility: number | null;
  componentRisk: number[] | null;
  riskBudgetShares: number[] | null;
  solver: null | {
    algorithm: string;
    iterations: number | null;
    maxAbsRiskBudgetError: number | null;
    tolerance: number;
    maxIterations: number;
  };
}

export interface WalkForwardParameterOptimizationCandidateEvidence {
  parameterHash: string;
  parameters: Record<string, unknown>;
  status: "eligible" | "failed" | string;
  completedFoldCount: number;
  failedFold: string | null;
  failureReason: string | null;
  innerOosMetricSummary: {
    sortino: number | null;
    maxDrawdown: number | null;
    cagr: number | null;
    transactionCosts: number | null;
  };
  innerOosIdentity: string | null;
  decisionHashes: string[];
  evaluationDatasetHashes: string[];
}

export interface WalkForwardParameterOptimizationEvidence {
  contractVersion: string;
  tuningContractVersion: string;
  objectivePolicyVersion: string;
  outerTrainingDatasetHash: string;
  innerFoldSchedule: {
    contractVersion: string;
    calendarPolicy: string;
    periods: Array<{
      periodId: string;
      trainingStart: string;
      trainingEnd: string;
      decisionDate: string;
      evaluationStart: string;
      evaluationEnd: string;
      decisionTiming: string;
    }>;
    innerFoldScheduleHash: string;
  };
  searchPlanHash: string;
  candidateCount: number;
  candidates: WalkForwardParameterOptimizationCandidateEvidence[];
  winnerParameterHash: string;
  winnerParameters: Record<string, unknown>;
  winnerRank: number;
  resultHash: string;
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
  allocation?: WalkForwardAllocationEvidence;
  parameterOptimization?: WalkForwardParameterOptimizationEvidence;
  parameterOptimizationRefit?: {
    policy: string;
    outerTrainingDatasetHash: string;
    winnerParameterHash: string;
  };
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
  tuning_result_hash?: string;
  search_plan_hash?: string;
  winner_parameter_hash?: string;
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
