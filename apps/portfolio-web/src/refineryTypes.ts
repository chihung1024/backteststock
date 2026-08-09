export type WorkspaceKind = "portfolio" | "refinery";

export interface RefineryAssetRow {
  id: string;
  symbol: string;
  weightPercent: number | null;
}

export interface RefineryWorkspaceModel {
  schemaVersion: 1;
  symbols: RefineryAssetRow[];
  benchmark: string;
  startDate: string;
  endDate: string;
  useWeights: boolean;
  ewmaDecay: number;
  stressQuantile: number;
}

export interface RefineryValidationIssue {
  field: string;
  message: string;
}

export interface RefineryApiRequest {
  contract_version: "refinery-v1";
  symbols: string[];
  benchmark?: string;
  start_date: string;
  end_date: string;
  weights?: Array<{ symbol: string; weight_percent: number }>;
  ewma_decay: number;
  stress_quantile: number;
}

export interface RefineryFailure {
  symbol: string;
  stage: string;
  detail: string;
  retryable: boolean;
}

export interface RefineryBenchmarkEvidence {
  symbol: string | null;
  status: "not_requested" | "ready" | "failed" | string;
  failure: RefineryFailure | null;
  effective_start: string | null;
  effective_end: string | null;
}

export interface RefineryDatasetEvidence {
  candidate_dataset_hash: string;
  benchmark_dataset_hash: string | null;
  requested_symbols: string[];
  resolved_symbols: string[];
  failures: Record<string, RefineryFailure>;
  effective_start: string | null;
  effective_end: string | null;
  reference_observations: number;
  daily_return_observations: number;
  daily_complete_case_observations: number;
  weekly_return_observations: number;
  weekly_complete_case_observations: number;
  coverage: Record<string, unknown>;
  assets: Record<string, unknown>;
  benchmark: RefineryBenchmarkEvidence;
}

export interface RefineryEligibility {
  analysis_ready: boolean;
  candidate_membership_complete: boolean;
  reasons: string[];
}

export interface RefineryRequestEcho {
  symbols: string[];
  benchmark: string | null;
  start_date: string;
  end_date: string;
  weights_supplied: boolean;
  weights: Array<{ symbol: string; weight_percent: number }> | null;
  weight_input_total_percent: number | null;
  weight_normalization: string | null;
  ewma_decay: number;
  stress_quantile: number;
}

export interface RefineryBaseResponse {
  contract_version: string;
  schema_version: string;
  endpoint: "preflight" | "analyze";
  status: "ready" | "incomplete" | "insufficient_data" | "ok" | string;
  request: RefineryRequestEcho;
  methodology: Record<string, string | number | boolean | null>;
  dataset: RefineryDatasetEvidence;
  eligibility: RefineryEligibility;
}

export type RefineryPreflightResponse = RefineryBaseResponse;

export interface RefineryCovarianceDiagnostics {
  observations: number;
  features: number;
  symmetry_error: number | null;
  tolerance: number | null;
  min_eigenvalue: number | null;
  max_eigenvalue: number | null;
  is_psd: boolean;
  numerical_rank: number;
  condition_number: number | null;
}

export interface RefineryEstimatorSummary {
  method: string;
  observations: number;
  features: number;
  annualization: number;
  shrinkage: number | null;
  diagnostics: RefineryCovarianceDiagnostics;
}

export interface RefineryEffectiveDimension {
  entropy_effective_rank: number | null;
  participation_ratio: number | null;
  positive_eigenvalues: Array<number | null>;
}

export interface RefineryPortfolioRisk {
  status: string;
  weights: number[] | null;
  variance?: number | null;
  volatility?: number | null;
  marginal_risk_contribution?: Array<number | null> | null;
  signed_component_risk_contribution?: Array<number | null> | null;
  diversification_ratio?: number | null;
  weight_effective_holdings?: number | null;
  gross_risk_contribution_equivalent_holdings?: number | null;
}

export interface RefineryCorrelationMatrix {
  symbols: string[];
  values: Array<Array<number | null>>;
}

export interface RefineryCorrelationView {
  status: string;
  input_observations: number;
  observations: number;
  dropped_observations: number;
  window: number | null;
  condition: string;
  threshold: number | null;
  matrix: RefineryCorrelationMatrix | null;
}

export type RefineryCorrelationKey =
  | "tactical_daily"
  | "medium_daily"
  | "structural_weekly"
  | "downside"
  | "stress";

export interface RefineryAnalysis {
  symbols: string[];
  covariance: {
    primary_method: string;
    annualization: number;
    ledoit_wolf_shrinkage: number | null;
    estimators: Record<string, RefineryEstimatorSummary>;
    estimator_dispersion: {
      pairwise_relative_frobenius: Record<string, number | null>;
      maximum_relative_frobenius: number | null;
    };
  };
  effective_dimensions: {
    covariance: RefineryEffectiveDimension;
    medium_correlation: RefineryEffectiveDimension | null;
  };
  portfolio: RefineryPortfolioRisk;
  correlations: Record<RefineryCorrelationKey, RefineryCorrelationView>;
}

export interface RefineryAnalyzeResponse extends RefineryBaseResponse {
  analysis: RefineryAnalysis | null;
}
