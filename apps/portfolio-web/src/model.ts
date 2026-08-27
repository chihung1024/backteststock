import type {
  PortfolioApiRequest,
  PortfolioColumn,
  ValidationIssue,
  WorkspaceModel,
} from "./types";

const MAX_PORTFOLIOS = 5;
const MAX_ASSETS = 20;
const WEIGHT_TOLERANCE = 0.05;

export type PortfolioExposureKind = "inactive" | "cash" | "fully_invested" | "leveraged";

export interface PortfolioExposureSummary {
  kind: PortfolioExposureKind;
  label: string;
  detail: string;
}

function uid(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function yearsAgoIso(years: number): string {
  const date = new Date();
  date.setUTCFullYear(date.getUTCFullYear() - years);
  return date.toISOString().slice(0, 10);
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function createDefaultModel(): WorkspaceModel {
  const assetId = uid("asset");
  return {
    schemaVersion: 1,
    assets: [{ id: assetId, symbol: "" }],
    portfolios: [
      { id: uid("portfolio"), name: "投資組合 1", weights: { [assetId]: 0 } },
      { id: uid("portfolio"), name: "投資組合 2", weights: { [assetId]: 0 } },
    ],
    startDate: yearsAgoIso(10),
    endDate: todayIso(),
    initialAmount: 1_000_000,
    benchmark: "SPY",
    includeYtd: true,
    reinvestDistributions: true,
    transactionCostBps: 0,
    cashflow: {
      type: "none",
      amount: 0,
      frequency: "none",
      timing: "end",
      annualGrowthRatePercent: 0,
    },
    rebalancing: { frequency: "annual", thresholdPercent: null },
    leverage: {
      type: "none",
      ratio: 1,
      debtAmount: 0,
      annualInterestRatePercent: 0,
      maintenanceMarginPercent: 25,
    },
    exposureMaintenance: {
      mode: "band",
      tolerancePercent: 10,
    },
    analytics: {
      factorAnalysis: false,
      styleAnalysis: false,
      regime: "none",
      inflationAdjusted: false,
      riskFreeRatePercent: 0,
    },
    outputFrequency: "daily",
    includeEvents: true,
    includeAllocationHistory: false,
  };
}

export function createExampleModel(): WorkspaceModel {
  const model = createDefaultModel();
  const assets = [
    { id: uid("asset"), symbol: "SPY" },
    { id: uid("asset"), symbol: "2330.TW" },
    { id: uid("asset"), symbol: "VT" },
  ];
  model.assets = assets;
  model.portfolios = [
    {
      id: uid("portfolio"),
      name: "全球核心",
      weights: { [assets[0]!.id]: 50, [assets[1]!.id]: 30, [assets[2]!.id]: 20 },
    },
    {
      id: uid("portfolio"),
      name: "全球股票",
      weights: { [assets[0]!.id]: 0, [assets[1]!.id]: 0, [assets[2]!.id]: 100 },
    },
  ];
  return model;
}

export function normalizeSymbol(value: string): string {
  const symbol = value.trim().toUpperCase();
  if (/^\d{4,6}$/.test(symbol)) return `${symbol}.TW`;
  return symbol;
}

export function portfolioWeightTotal(portfolio: PortfolioColumn, model: WorkspaceModel): number {
  return model.assets.reduce(
    (total, asset) => total + (Number(portfolio.weights[asset.id]) || 0),
    0,
  );
}

export function portfolioExposureSummary(total: number): PortfolioExposureSummary {
  if (!Number.isFinite(total) || total <= 0) {
    return {
      kind: "inactive",
      label: "0.0% · 未啟用",
      detail: "輸入正曝險後啟用此投組",
    };
  }
  if (Math.abs(total - 100) <= WEIGHT_TOLERANCE) {
    return {
      kind: "fully_invested",
      label: `${total.toFixed(1)}% · 全額投資`,
      detail: "內部比例依再平衡設定",
    };
  }
  if (total < 100) {
    return {
      kind: "cash",
      label: `${total.toFixed(1)}% · 現金 ${(100 - total).toFixed(1)}%`,
      detail: "現金部位自然漂移；內部比例依再平衡設定",
    };
  }
  return {
    kind: "leveraged",
    label: `${total.toFixed(1)}% · ${(total / 100).toFixed(2)}× · 融資 ${(total - 100).toFixed(1)}%`,
    detail: "融資曝險依維持模式控制；內部比例依再平衡設定",
  };
}

export function activePortfolios(model: WorkspaceModel): PortfolioColumn[] {
  return model.portfolios.filter((portfolio) => portfolioWeightTotal(portfolio, model) > 0);
}

export function validateModel(model: WorkspaceModel): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (!model.startDate || !model.endDate || model.startDate >= model.endDate) {
    issues.push({ field: "period", message: "開始日期必須早於結束日期。" });
  }
  if (!Number.isFinite(model.initialAmount) || model.initialAmount <= 0) {
    issues.push({ field: "initialAmount", message: "初始金額必須大於 0。" });
  }
  if (model.assets.length < 1 || model.assets.length > MAX_ASSETS) {
    issues.push({ field: "assets", message: `資產列必須介於 1 至 ${MAX_ASSETS} 列。` });
  }
  if (model.portfolios.length < 1 || model.portfolios.length > MAX_PORTFOLIOS) {
    issues.push({ field: "portfolios", message: `投資組合必須介於 1 至 ${MAX_PORTFOLIOS} 組。` });
  }

  const normalized = model.assets.map((asset) => normalizeSymbol(asset.symbol));
  const nonBlank = normalized.filter(Boolean);
  if (new Set(nonBlank).size !== nonBlank.length) {
    issues.push({ field: "assets", message: "股票代碼不可重複。" });
  }

  const active = activePortfolios(model);
  if (!active.length) {
    issues.push({ field: "portfolios", message: "至少需要一組總曝險大於 0% 的投資組合。" });
  }
  for (const portfolio of model.portfolios) {
    const rawWeights = model.assets.map((asset) => Number(portfolio.weights[asset.id]) || 0);
    if (rawWeights.some((weight) => weight < 0)) {
      issues.push({ field: portfolio.id, message: `${portfolio.name || "未命名投組"} 的資產曝險不可為負數。` });
    }
  }
  for (const portfolio of active) {
    const total = portfolioWeightTotal(portfolio, model);
    const positiveRows = model.assets.filter(
      (asset) => (Number(portfolio.weights[asset.id]) || 0) > 0,
    );
    if (positiveRows.some((asset) => !normalizeSymbol(asset.symbol))) {
      issues.push({ field: portfolio.id, message: `${portfolio.name} 有曝險但缺少股票代碼。` });
    }
    if (model.leverage.type !== "none" && Math.abs(total - 100) > WEIGHT_TOLERANCE) {
      issues.push({
        field: "leverage",
        message: `${portfolio.name || "未命名投組"} 使用舊版槓桿時資產權重必須為 100%；非 100% 請停用舊版槓桿並直接用權重總和定義曝險。`,
      });
    }
  }

  if (model.cashflow.type !== "none" && model.cashflow.frequency === "none") {
    issues.push({ field: "cashflow", message: "啟用現金流時必須選擇頻率。" });
  }
  if (model.leverage.type === "fixed_ratio" && model.leverage.ratio <= 1) {
    issues.push({ field: "leverage", message: "固定倍數槓桿必須大於 1 倍。" });
  }
  if (model.leverage.type === "fixed_debt" && model.leverage.debtAmount <= 0) {
    issues.push({ field: "leverage", message: "固定借款金額必須大於 0。" });
  }
  if (
    !Number.isFinite(model.exposureMaintenance.tolerancePercent)
    || model.exposureMaintenance.tolerancePercent <= 0
    || model.exposureMaintenance.tolerancePercent > 100
  ) {
    issues.push({ field: "exposureMaintenance", message: "曝險容忍帶必須介於 0% 到 100% 之間。" });
  }
  return issues;
}

export function toApiRequest(model: WorkspaceModel): PortfolioApiRequest {
  const portfolios = activePortfolios(model).map((portfolio) => ({
    name: portfolio.name.trim() || "未命名投組",
    assets: model.assets
      .map((asset) => ({
        symbol: normalizeSymbol(asset.symbol),
        weight: Number(portfolio.weights[asset.id]) || 0,
      }))
      .filter((asset) => asset.symbol && asset.weight > 0),
  }));
  const request: PortfolioApiRequest = {
    contract_version: "portfolio-v3",
    portfolios,
    start_date: model.startDate,
    end_date: model.endDate,
    initial_amount: model.initialAmount,
    base_currency: "TWD",
    include_ytd: model.includeYtd,
    reinvest_distributions: model.reinvestDistributions,
    transaction_cost_bps: model.transactionCostBps,
    cashflow: {
      type: model.cashflow.type,
      amount: model.cashflow.amount,
      frequency: model.cashflow.type === "none" ? "none" : model.cashflow.frequency,
      timing: model.cashflow.timing,
      annual_growth_rate_percent: model.cashflow.annualGrowthRatePercent,
    },
    rebalancing: {
      frequency: model.rebalancing.frequency,
      ...(model.rebalancing.thresholdPercent
        ? { threshold_percent: model.rebalancing.thresholdPercent }
        : {}),
    },
    leverage: {
      type: model.leverage.type,
      ratio: model.leverage.ratio,
      debt_amount: model.leverage.debtAmount,
      annual_interest_rate_percent: model.leverage.annualInterestRatePercent,
      maintenance_margin_percent: model.leverage.maintenanceMarginPercent,
    },
    exposure_maintenance: {
      mode: model.exposureMaintenance.mode,
      tolerance_percent: model.exposureMaintenance.tolerancePercent,
    },
    analytics: {
      factor_analysis: model.analytics.factorAnalysis,
      style_analysis: model.analytics.styleAnalysis,
      regime: model.analytics.regime,
      inflation_adjusted: model.analytics.inflationAdjusted,
      risk_free_rate_percent: model.analytics.riskFreeRatePercent,
    },
    output_frequency: model.outputFrequency,
    include_events: model.includeEvents,
    include_allocation_history: model.includeAllocationHistory,
  };
  const benchmark = normalizeSymbol(model.benchmark);
  if (benchmark) request.benchmark = benchmark;
  return request;
}

export function migrateModel(value: unknown): WorkspaceModel {
  if (!value || typeof value !== "object") return createDefaultModel();
  const raw = value as Partial<WorkspaceModel>;
  if (raw.schemaVersion !== 1 || !Array.isArray(raw.assets) || !Array.isArray(raw.portfolios)) {
    return createDefaultModel();
  }
  const fallback = createDefaultModel();
  return {
    ...fallback,
    ...raw,
    schemaVersion: 1,
    assets: raw.assets.slice(0, MAX_ASSETS).map((asset) => ({
      id: String(asset.id || uid("asset")),
      symbol: String(asset.symbol || ""),
    })),
    portfolios: raw.portfolios.slice(0, MAX_PORTFOLIOS).map((portfolio, index) => ({
      id: String(portfolio.id || uid("portfolio")),
      name: String(portfolio.name || `投資組合 ${index + 1}`),
      weights: { ...(portfolio.weights || {}) },
    })),
    cashflow: { ...fallback.cashflow, ...(raw.cashflow || {}) },
    rebalancing: { ...fallback.rebalancing, ...(raw.rebalancing || {}) },
    leverage: { ...fallback.leverage, ...(raw.leverage || {}) },
    exposureMaintenance: {
      ...fallback.exposureMaintenance,
      ...(raw.exposureMaintenance || {}),
    },
    analytics: { ...fallback.analytics, ...(raw.analytics || {}) },
  };
}

export function addAsset(model: WorkspaceModel): WorkspaceModel {
  if (model.assets.length >= MAX_ASSETS) return model;
  const asset = { id: uid("asset"), symbol: "" };
  return {
    ...model,
    assets: [...model.assets, asset],
    portfolios: model.portfolios.map((portfolio) => ({
      ...portfolio,
      weights: { ...portfolio.weights, [asset.id]: 0 },
    })),
  };
}

export function removeAsset(model: WorkspaceModel, assetId: string): WorkspaceModel {
  if (model.assets.length <= 1) return model;
  return {
    ...model,
    assets: model.assets.filter((asset) => asset.id !== assetId),
    portfolios: model.portfolios.map((portfolio) => {
      const weights = { ...portfolio.weights };
      delete weights[assetId];
      return { ...portfolio, weights };
    }),
  };
}

export function addPortfolio(model: WorkspaceModel): WorkspaceModel {
  if (model.portfolios.length >= MAX_PORTFOLIOS) return model;
  return {
    ...model,
    portfolios: [
      ...model.portfolios,
      {
        id: uid("portfolio"),
        name: `投資組合 ${model.portfolios.length + 1}`,
        weights: Object.fromEntries(model.assets.map((asset) => [asset.id, 0])),
      },
    ],
  };
}

export function removePortfolio(model: WorkspaceModel, portfolioId: string): WorkspaceModel {
  if (model.portfolios.length <= 1) return model;
  return { ...model, portfolios: model.portfolios.filter((item) => item.id !== portfolioId) };
}

export function equalWeightPortfolio(model: WorkspaceModel, portfolioId: string): WorkspaceModel {
  const validAssets = model.assets.filter((asset) => normalizeSymbol(asset.symbol));
  if (!validAssets.length) return model;
  const weight = 100 / validAssets.length;
  return {
    ...model,
    portfolios: model.portfolios.map((portfolio) =>
      portfolio.id === portfolioId
        ? {
            ...portfolio,
            weights: Object.fromEntries(
              model.assets.map((asset) => [
                asset.id,
                validAssets.some((valid) => valid.id === asset.id) ? weight : 0,
              ]),
            ),
          }
        : portfolio,
    ),
  };
}

export function normalizePortfolio(model: WorkspaceModel, portfolioId: string): WorkspaceModel {
  const portfolio = model.portfolios.find((item) => item.id === portfolioId);
  if (!portfolio) return model;
  const total = portfolioWeightTotal(portfolio, model);
  if (total <= 0) return model;
  return {
    ...model,
    portfolios: model.portfolios.map((item) =>
      item.id === portfolioId
        ? {
            ...item,
            weights: Object.fromEntries(
              model.assets.map((asset) => [
                asset.id,
                ((Number(item.weights[asset.id]) || 0) / total) * 100,
              ]),
            ),
          }
        : item,
    ),
  };
}

export function clearPortfolio(model: WorkspaceModel, portfolioId: string): WorkspaceModel {
  return {
    ...model,
    portfolios: model.portfolios.map((portfolio) =>
      portfolio.id === portfolioId
        ? {
            ...portfolio,
            weights: Object.fromEntries(model.assets.map((asset) => [asset.id, 0])),
          }
        : portfolio,
    ),
  };
}

export function copyPortfolio(model: WorkspaceModel, portfolioId: string): WorkspaceModel {
  if (model.portfolios.length >= MAX_PORTFOLIOS) return model;
  const source = model.portfolios.find((portfolio) => portfolio.id === portfolioId);
  if (!source) return model;
  return {
    ...model,
    portfolios: [
      ...model.portfolios,
      { id: uid("portfolio"), name: `${source.name} 複本`, weights: { ...source.weights } },
    ],
  };
}
