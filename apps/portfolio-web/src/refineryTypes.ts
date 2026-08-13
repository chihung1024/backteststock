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

export type RefineryExperimentOperationType = "remove_one" | "add_one" | "replace_one";

export interface RefineryExperimentOperation {
  type: RefineryExperimentOperationType;
  remove?: string;
  add?: string;
}

export interface RefineryExperimentDraft {
  id: string;
  type: RefineryExperimentOperationType;
  remove: string;
  add: string;
}

export interface RefineryApiRequest {
  contract_version: "refinery-v1";
  symbols: string[];
  benchmark?: string;
  start_date: string;
  end_date: string;
  weights?: Array<{ symbol: string; weight_percent: number }>;
  experiment_plan?: RefineryExperimentOperation[];
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
  experiment_plan?: RefineryExperimentOperation[];
  ewma_decay: number;
  stress_quantile: number;
}

export interface RefineryBaseResponse {
  contract_version: string;
  schema_version: string;
  endpoint: "preflight" | "analyze";
  status: "ready" | "incomplete" | "insufficient_data" | "ok" | string;
  request: RefineryRequestEcho;
  methodology: Record<string, string | number | boolean | number[] | null>;
  dataset: RefineryDatasetEvidence;
  eligibility: RefineryEligibility;
  marginal_experiments?: RefineryMarginalExperiments;
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

export interface RefineryFrozenSampleIdentity {
  effective_start: string | null;
  effective_end: string | null;
  observations: number;
  canonical_symbols: string[];
  fingerprint_sha256: string;
}

export interface RefineryMarginalCommonSample {
  status: string;
  experiment_union_dataset_hash: string;
  experiment_union_symbols: string[];
  daily: RefineryFrozenSampleIdentity | null;
  weekly: RefineryFrozenSampleIdentity | null;
}

export interface RefineryMarginalHierarchy {
  method: string;
  cut_distance: number | null;
  symbols: string[];
  cluster_count: number;
  clusters: RefineryClusterGroup[];
  merges: RefineryClusterMerge[];
}

export interface RefineryMarginalSnapshot {
  symbols: string[];
  covariance: {
    primary_method: string;
    observations: number;
    features: number;
    annualization: number;
    ledoit_wolf_shrinkage: number | null;
  };
  effective_dimensions: {
    covariance: RefineryEffectiveDimension;
    medium_correlation: RefineryEffectiveDimension | null;
  };
  correlations: Pick<
    Record<RefineryCorrelationKey, RefineryCorrelationView>,
    "tactical_daily" | "medium_daily" | "structural_weekly"
  >;
  clustering: {
    status: string;
    reason?: string | null;
    primary: RefineryMarginalHierarchy | null;
    sensitivity: RefineryMarginalHierarchy | null;
  };
}

export interface RefineryScalarDelta {
  baseline: number | null;
  variant: number | null;
  delta: number | null;
}

export interface RefineryMarginalPairEvidence {
  symbol_a: string;
  symbol_b: string;
  correlations: Record<string, number | null>;
}

export interface RefineryMarginalPairImpacts {
  maximum_pairs: number;
  shared_pair_invariant: Record<
    string,
    {
      shared_pairs: number;
      compared_pairs: number;
      maximum_absolute_delta: number | null;
      tolerance: number;
    }
  >;
  removed_pairs: RefineryMarginalPairEvidence[];
  added_pairs: RefineryMarginalPairEvidence[];
}

export interface RefineryMarginalResult {
  id: string;
  operation: RefineryExperimentOperation;
  variant_symbols: string[];
  common_sample: {
    daily: RefineryFrozenSampleIdentity;
    weekly: RefineryFrozenSampleIdentity;
  };
  variant: RefineryMarginalSnapshot;
  deltas: {
    effective_dimensions: {
      covariance: Record<string, RefineryScalarDelta> | null;
      medium_correlation: Record<string, RefineryScalarDelta> | null;
    };
    clusters: {
      primary: RefineryScalarDelta;
      sensitivity: RefineryScalarDelta;
    };
    pair_impacts: RefineryMarginalPairImpacts;
  };
}

export interface RefineryMarginalExperiments {
  status: string;
  eligibility: {
    baseline_analysis_ready: boolean;
    experiment_membership_complete: boolean;
    daily_global_observations_sufficient: boolean;
    weekly_global_observations_sufficient: boolean;
    reasons: string[];
  };
  failures: Record<string, RefineryFailure>;
  common_sample: RefineryMarginalCommonSample;
  methodology: Record<string, string>;
  experiment_baseline: RefineryMarginalSnapshot | null;
  results: RefineryMarginalResult[];
}

export type RefineryCorrelationKey =
  | "tactical_daily"
  | "medium_daily"
  | "structural_weekly"
  | "downside"
  | "stress";

export interface RefineryClusterMerge {
  node_id: number;
  left: number;
  right: number;
  distance: number;
  count: number;
}

export interface RefineryClusterGroup {
  cluster_id: string;
  members: string[];
}

export interface RefineryHierarchyEvidence {
  method: string;
  cut_distance: number;
  symbols: string[];
  merges: RefineryClusterMerge[];
  clusters: RefineryClusterGroup[];
  cluster_by_symbol: Record<string, string>;
}

export interface RefineryClusterSummary {
  cluster_id: string;
  members: string[];
  member_count: number;
  structural_correlation: {
    minimum: number;
    mean: number;
    maximum: number;
  } | null;
  bootstrap_stability: number | null;
  bootstrap_stability_status: string;
  complete_linkage_agreement: boolean | null;
}

export interface RefineryClusterWindowEvidence {
  window_weeks: number;
  status: string;
  input_observations: number;
  observations: number;
}

export interface RefineryClusterPairAgreement {
  symbol_a: string;
  symbol_b: string;
  available_windows: number;
  same_cluster_windows: number;
  agreement: number | null;
}

export interface RefineryBootstrapPairEvidence {
  symbol_a: string;
  symbol_b: string;
  probability: number | null;
}

export interface RefineryClusteringEvidence {
  contract_version: string;
  primary_linkage: string;
  sensitivity_linkage: string;
  flat_cut_distance: number;
  stability_windows_weeks: number[];
  bootstrap_replicates: number;
  bootstrap_block_weeks: number;
  status: string;
  reason: string | null;
  primary: RefineryHierarchyEvidence | null;
  sensitivity: RefineryHierarchyEvidence | null;
  multi_window: {
    windows: RefineryClusterWindowEvidence[];
    pair_agreements: RefineryClusterPairAgreement[];
  } | null;
  bootstrap: {
    status: string;
    requested_replicates: number;
    usable_replicates: number;
    unusable_replicates: number;
    block_weeks: number;
    observations: number;
    seed: number;
    pair_probabilities: RefineryBootstrapPairEvidence[];
  } | null;
  clusters: RefineryClusterSummary[];
  bootstrap_window_weeks: number;
  bootstrap_input_fingerprint_sha256: string;
}

export type RefineryRedundancyVerdict = "HIGH" | "MEDIUM" | "LOW" | "UNCERTAIN";
export type RefineryEvidenceConfidence = "HIGH" | "MEDIUM" | "LOW";

export interface RefineryRedundancyPair {
  symbol_a: string;
  symbol_b: string;
  verdict: RefineryRedundancyVerdict;
  confidence: RefineryEvidenceConfidence;
  structural_correlation: number | null;
  medium_correlation: number | null;
  downside_correlation: number | null;
  stress_correlation: number | null;
  factor_implied_correlation: number | null;
  factor_corroboration_eligible: boolean;
  factor_corroboration_reason: string | null;
  same_average_cluster: boolean;
  same_complete_cluster: boolean;
  available_stability_windows: number;
  window_cocluster_agreement: number | null;
  bootstrap_cocluster_probability: number | null;
  correlation_status: Record<string, string>;
}

export interface RefineryRedundancyEvidence {
  status: string;
  verdict_semantics: string;
  magic_numeric_score: boolean;
  counts: Record<RefineryRedundancyVerdict, number>;
  pairs: RefineryRedundancyPair[];
}

export interface RefineryFactorAssetEvidence {
  status: string;
  quote_currency: string | null;
  factor_computable: boolean;
  factor_model_scope: string;
  factor_corroboration_eligible: boolean;
  factor_corroboration_reason: string | null;
  monthly_return_policy: string;
  observations: number;
  start?: string | null;
  end?: string | null;
  intercept_monthly?: number | null;
  r_squared: number | null;
  betas: Record<string, number> | null;
}

export interface RefineryFactorRelationships {
  source: string;
  scope: string;
  factor_model_scope: string;
  factor_corroboration_policy: string;
  return_currency: string;
  monthly_return_policy: string;
  minimum_monthly_observations: number;
  status: string;
  factor_sample: {
    observations: number;
    start: string | null;
    end: string | null;
    fingerprint_sha256: string;
  } | null;
  assets: Record<string, RefineryFactorAssetEvidence>;
  systematic_relationship: {
    status: string;
    observations: number;
    start: string | null;
    end: string | null;
    sample_fingerprint_sha256: string | null;
    matrix: RefineryCorrelationMatrix | null;
  } | null;
}

export interface RefineryThemeRelationships {
  status: string;
  source: string | null;
  taxonomy_version: string | null;
  relationships: unknown;
}

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
  clustering?: RefineryClusteringEvidence;
  redundancy?: RefineryRedundancyEvidence;
  factor_relationships?: RefineryFactorRelationships;
  theme_relationships?: RefineryThemeRelationships;
}

export interface RefineryAnalyzeResponse extends RefineryBaseResponse {
  analysis: RefineryAnalysis | null;
}
