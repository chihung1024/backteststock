export type Locale = "zh-TW" | "en";
export type Theme = "dark" | "light";
export type ResultTab =
  | "overview"
  | "growth"
  | "drawdown"
  | "annual"
  | "monthly"
  | "income"
  | "allocation"
  | "analytics"
  | "audit";

export interface AssetRow {
  id: string;
  symbol: string;
}

export interface PortfolioColumn {
  id: string;
  name: string;
  weights: Record<string, number>;
}

export interface CashflowSettings {
  type: "none" | "fixed" | "percent";
  amount: number;
  frequency: "none" | "monthly" | "quarterly" | "annual";
  timing: "beginning" | "end";
  annualGrowthRatePercent: number;
}

export interface RebalanceSettings {
  frequency: "none" | "monthly" | "quarterly" | "semiannual" | "annual";
  thresholdPercent: number | null;
}

export interface ExposureMaintenanceSettings {
  mode: "none" | "band" | "daily";
  tolerancePercent: number;
}

export interface LeverageSettings {
  type: "none" | "fixed_ratio" | "fixed_debt";
  ratio: number;
  debtAmount: number;
  annualInterestRatePercent: number;
  maintenanceMarginPercent: number;
}

export interface AnalyticsSettings {
  factorAnalysis: boolean;
  styleAnalysis: boolean;
  regime: "none" | "market" | "volatility" | "inflation" | "business_cycle";
  inflationAdjusted: boolean;
  riskFreeRatePercent: number;
}

export interface WorkspaceModel {
  schemaVersion: 1;
  assets: AssetRow[];
  portfolios: PortfolioColumn[];
  startDate: string;
  endDate: string;
  initialAmount: number;
  benchmark: string;
  includeYtd: boolean;
  reinvestDistributions: boolean;
  transactionCostBps: number;
  cashflow: CashflowSettings;
  rebalancing: RebalanceSettings;
  leverage: LeverageSettings;
  exposureMaintenance: ExposureMaintenanceSettings;
  analytics: AnalyticsSettings;
  outputFrequency: "daily" | "weekly" | "monthly";
  includeEvents: boolean;
  includeAllocationHistory: boolean;
}

export interface ValidationIssue {
  field: string;
  message: string;
}

export interface PortfolioApiRequest {
  contract_version: "portfolio-v3";
  portfolios: Array<{
    name: string;
    assets: Array<{ symbol: string; weight: number }>;
  }>;
  benchmark?: string;
  start_date: string;
  end_date: string;
  initial_amount: number;
  base_currency: "TWD";
  include_ytd: boolean;
  reinvest_distributions: boolean;
  transaction_cost_bps: number;
  cashflow: {
    type: CashflowSettings["type"];
    amount: number;
    frequency: CashflowSettings["frequency"];
    timing: CashflowSettings["timing"];
    annual_growth_rate_percent: number;
  };
  rebalancing: {
    frequency: RebalanceSettings["frequency"];
    threshold_percent?: number;
  };
  leverage: {
    type: LeverageSettings["type"];
    ratio: number;
    debt_amount: number;
    annual_interest_rate_percent: number;
    maintenance_margin_percent: number;
  };
  exposure_maintenance: {
    mode: ExposureMaintenanceSettings["mode"];
    tolerance_percent: number;
  };
  analytics: {
    factor_analysis: boolean;
    style_analysis: boolean;
    regime: AnalyticsSettings["regime"];
    inflation_adjusted: boolean;
    risk_free_rate_percent: number;
  };
  output_frequency: WorkspaceModel["outputFrequency"];
  include_events: boolean;
  include_allocation_history: boolean;
}

export interface AssetPreflight {
  symbol: string;
  status: "ready" | "failed";
  stage?: string | null;
  detail?: string | null;
  retryable: boolean;
  quote_currency?: string | null;
  effective_start?: string | null;
  effective_end?: string | null;
  observations: number;
  corporate_action_audit?: Record<string, unknown> | null;
  fx_audit?: Record<string, unknown> | null;
  return_component_audit?: Record<string, unknown> | null;
  fingerprints: Record<string, string | null>;
}

export interface PortfolioPreflight {
  name: string;
  status: "ready" | "failed";
  symbols: string[];
  missing_symbols: string[];
  effective_start?: string | null;
  effective_end?: string | null;
  observations: number;
  detail?: string | null;
}

export interface PreflightResponse {
  request_id: string;
  generated_at: string;
  contract_version: string;
  schema_version: string;
  base_currency: "TWD";
  requested_start: string;
  requested_end: string;
  effective_end: string;
  assets: AssetPreflight[];
  portfolios: PortfolioPreflight[];
  benchmark?: AssetPreflight | null;
  analysis_dependencies: AssetPreflight[];
  warnings: string[];
}

export interface SeriesPoint {
  date: string;
  value: number | null;
  return_index: number | null;
  daily_return: number | null;
  external_flow: number | null;
  income: number | null;
  cumulative_income: number | null;
  cash: number | null;
  debt: number | null;
  gross_exposure: number | null;
}

export interface PeriodReturn {
  period: string;
  start: string;
  end: string;
  return_value: number;
  partial: boolean;
}

export interface DrawdownEvent {
  peak: string;
  trough: string;
  recovery: string | null;
  depth: number;
  duration_days: number;
  recovered: boolean;
}

export interface BacktestResult {
  name: string;
  display_name: string;
  metrics: Record<string, number | string | null>;
  xirr: { status: string; value: number | null; roots: number[]; method: string };
  tail_risk: Record<string, number | string | null>;
  drawdown_events: DrawdownEvent[];
  annual_returns: PeriodReturn[];
  monthly_returns: PeriodReturn[];
  target_allocation: Record<string, number>;
  final_allocation: Record<string, number>;
  series: SeriesPoint[];
  analytics: Record<string, unknown>;
  warnings: string[];
  metadata: Record<string, unknown>;
  events?: Array<Record<string, unknown>>;
  allocation_history?: Array<Record<string, unknown>>;
}

export interface BacktestResponse {
  request_id: string;
  generated_at: string;
  contract_version: string;
  schema_version: string;
  base_currency: "TWD";
  requested_start: string;
  requested_end: string;
  effective_end: string;
  results: BacktestResult[];
  failures: Array<Record<string, unknown>>;
  assets: AssetPreflight[];
  benchmark?: BacktestResult | null;
  warnings: string[];
  timing: Record<string, number>;
  reproducibility: Record<string, unknown>;
}

export interface SearchResult {
  symbol: string;
  name: string;
  exchange?: string | null;
  quote_type?: string | null;
  currency?: string | null;
}
