import type {
  RefineryApiRequest,
  RefineryAssetRow,
  RefineryExperimentDraft,
  RefineryExperimentOperation,
  RefineryExperimentOperationType,
  RefineryValidationIssue,
  RefineryWorkspaceModel,
} from "./refineryTypes";

export const REFINERY_UI_SCHEMA_VERSION = "refinery-ui-v1-2026-08-09.1";
export const REFINERY_WORKSPACE_STORAGE_KEY = "backteststock.refinery.workspace.v1";
export const ACTIVE_WORKSPACE_STORAGE_KEY = "backteststock.portfolio.active-workspace.v1";
export const MAX_REFINERY_CANDIDATES = 100;
export const MIN_REFINERY_CANDIDATES = 2;
export const MAX_REFINERY_EXPERIMENT_OPERATIONS = 12;
export const MAX_REFINERY_EXPERIMENT_UNION_SYMBOLS = 24;
export const REFINERY_WEIGHT_TOLERANCE = 0.05;
const MAX_HISTORY_CALENDAR_DAYS = 15 * 366;

function uid(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function yearsAgoIso(years: number): string {
  const date = new Date();
  date.setUTCFullYear(date.getUTCFullYear() - years);
  return date.toISOString().slice(0, 10);
}

export function createRefineryAsset(symbol = "", weightPercent: number | null = null): RefineryAssetRow {
  return { id: uid("refinery-asset"), symbol, weightPercent };
}

export function createRefineryExperimentDraft(
  type: RefineryExperimentOperationType = "remove_one",
): RefineryExperimentDraft {
  return {
    id: uid("refinery-experiment"),
    type,
    remove: "",
    add: "",
  };
}

export function createDefaultRefineryModel(): RefineryWorkspaceModel {
  return {
    schemaVersion: 1,
    symbols: [createRefineryAsset(), createRefineryAsset()],
    benchmark: "",
    startDate: yearsAgoIso(5),
    endDate: todayIso(),
    useWeights: false,
    ewmaDecay: 0.94,
    stressQuantile: 0.1,
  };
}

export function createExampleRefineryModel(): RefineryWorkspaceModel {
  return {
    ...createDefaultRefineryModel(),
    symbols: [
      createRefineryAsset("NVDA", 25),
      createRefineryAsset("ANET", 25),
      createRefineryAsset("PWR", 25),
      createRefineryAsset("WMT", 25),
    ],
    benchmark: "SPY",
    useWeights: true,
  };
}

export function normalizeRefinerySymbol(value: string): string {
  const symbol = value.trim().toUpperCase();
  if (/^\d{4,6}$/u.test(symbol)) return `${symbol}.TW`;
  return symbol;
}

export function activeRefineryRows(model: RefineryWorkspaceModel): RefineryAssetRow[] {
  return model.symbols.filter((row) => normalizeRefinerySymbol(row.symbol));
}

export function refineryWeightTotal(model: RefineryWorkspaceModel): number {
  return activeRefineryRows(model).reduce(
    (total, row) => total + (Number(row.weightPercent) || 0),
    0,
  );
}

export function validateRefineryModel(model: RefineryWorkspaceModel): RefineryValidationIssue[] {
  const issues: RefineryValidationIssue[] = [];
  const rows = activeRefineryRows(model);
  const symbols = rows.map((row) => normalizeRefinerySymbol(row.symbol));

  if (rows.length < MIN_REFINERY_CANDIDATES || rows.length > MAX_REFINERY_CANDIDATES) {
    issues.push({
      field: "symbols",
      message: `持股代碼必須介於 ${MIN_REFINERY_CANDIDATES} 至 ${MAX_REFINERY_CANDIDATES} 檔。`,
    });
  }
  if (new Set(symbols).size !== symbols.length) {
    issues.push({ field: "symbols", message: "持股代碼不可重複。" });
  }
  if (model.symbols.some((row) => !normalizeRefinerySymbol(row.symbol) && (Number(row.weightPercent) || 0) > 0)) {
    issues.push({ field: "weights", message: "空白持股列不可設定權重。" });
  }

  if (!model.startDate || !model.endDate || model.startDate >= model.endDate) {
    issues.push({ field: "period", message: "開始日期必須早於結束日期。" });
  } else {
    const start = new Date(`${model.startDate}T00:00:00Z`);
    const end = new Date(`${model.endDate}T00:00:00Z`);
    const today = new Date(`${todayIso()}T00:00:00Z`);
    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime())) {
      issues.push({ field: "period", message: "日期格式無效。" });
    } else {
      if (end > today) issues.push({ field: "period", message: "結束日期不可晚於今天。" });
      const spanDays = Math.round((end.getTime() - start.getTime()) / 86_400_000);
      if (spanDays > MAX_HISTORY_CALENDAR_DAYS) {
        issues.push({ field: "period", message: "研究期間不可超過 15 年的 API 資源上限。" });
      }
    }
  }

  if (!Number.isFinite(model.ewmaDecay) || model.ewmaDecay <= 0 || model.ewmaDecay >= 1) {
    issues.push({ field: "ewmaDecay", message: "EWMA decay 必須介於 0 與 1 之間。" });
  }
  if (!Number.isFinite(model.stressQuantile) || model.stressQuantile < 0.05 || model.stressQuantile > 0.25) {
    issues.push({ field: "stressQuantile", message: "壓力分位必須介於 5% 與 25%。" });
  }

  if (model.useWeights) {
    if (rows.some((row) => !Number.isFinite(Number(row.weightPercent)) || Number(row.weightPercent) <= 0)) {
      issues.push({ field: "weights", message: "啟用權重時，每檔有效持股都必須有大於 0 的權重。" });
    }
    const total = refineryWeightTotal(model);
    if (Math.abs(total - 100) > REFINERY_WEIGHT_TOLERANCE) {
      issues.push({
        field: "weights",
        message: `權重合計為 ${total.toFixed(2)}%，必須為 100%（容許 ±${REFINERY_WEIGHT_TOLERANCE.toFixed(2)} 個百分點）。`,
      });
    }
  }
  return issues;
}

export function validateRefineryExperimentPlan(
  model: RefineryWorkspaceModel,
  plan: RefineryExperimentDraft[],
): RefineryValidationIssue[] {
  const issues: RefineryValidationIssue[] = [];
  const baseline = activeRefineryRows(model).map((row) => normalizeRefinerySymbol(row.symbol));
  const baselineSet = new Set(baseline);
  const union = new Set(baseline);
  const seen = new Set<string>();

  if (plan.length > MAX_REFINERY_EXPERIMENT_OPERATIONS) {
    issues.push({
      field: "experiment_plan",
      message: `實驗操作最多 ${MAX_REFINERY_EXPERIMENT_OPERATIONS} 筆。`,
    });
  }

  plan.forEach((draft, index) => {
    const remove = normalizeRefinerySymbol(draft.remove);
    const add = normalizeRefinerySymbol(draft.add);
    const label = `實驗 ${index + 1}`;
    const identity = `${draft.type}::${remove}::${add}`;

    if (draft.type === "remove_one") {
      if (!remove) {
        issues.push({ field: "experiment_plan", message: `${label} 必須指定要移除的候選持股。` });
      } else if (!baselineSet.has(remove)) {
        issues.push({ field: "experiment_plan", message: `${label} 的移除代碼必須在候選持股中。` });
      }
      if (baseline.length - 1 < MIN_REFINERY_CANDIDATES) {
        issues.push({ field: "experiment_plan", message: `${label} 移除後至少須保留 ${MIN_REFINERY_CANDIDATES} 檔。` });
      }
    }

    if (draft.type === "add_one") {
      if (!add) {
        issues.push({ field: "experiment_plan", message: `${label} 必須指定要新增的代碼。` });
      } else if (baselineSet.has(add)) {
        issues.push({ field: "experiment_plan", message: `${label} 的新增代碼已在候選持股中。` });
      } else {
        union.add(add);
      }
    }

    if (draft.type === "replace_one") {
      if (!remove || !add) {
        issues.push({ field: "experiment_plan", message: `${label} 必須同時指定移除與新增代碼。` });
      }
      if (remove && !baselineSet.has(remove)) {
        issues.push({ field: "experiment_plan", message: `${label} 的移除代碼必須在候選持股中。` });
      }
      if (add && baselineSet.has(add)) {
        issues.push({ field: "experiment_plan", message: `${label} 的新增代碼已在候選持股中。` });
      } else if (add) {
        union.add(add);
      }
    }

    if ((remove || add) && seen.has(identity)) {
      issues.push({ field: "experiment_plan", message: `${label} 與其他實驗在正規化後重複。` });
    }
    if (remove || add) seen.add(identity);
  });

  if (union.size > MAX_REFINERY_EXPERIMENT_UNION_SYMBOLS) {
    issues.push({
      field: "experiment_plan",
      message: `實驗聯集最多 ${MAX_REFINERY_EXPERIMENT_UNION_SYMBOLS} 檔（baseline 加上外部新增／替換代碼）。`,
    });
  }
  return issues;
}

export function toRefineryExperimentPlan(
  plan: RefineryExperimentDraft[],
): RefineryExperimentOperation[] {
  return plan.map((draft) => {
    const remove = normalizeRefinerySymbol(draft.remove);
    const add = normalizeRefinerySymbol(draft.add);
    if (draft.type === "remove_one") return { type: draft.type, remove };
    if (draft.type === "add_one") return { type: draft.type, add };
    return { type: draft.type, remove, add };
  });
}

export function toRefineryApiRequest(
  model: RefineryWorkspaceModel,
  experimentPlan: RefineryExperimentDraft[] = [],
): RefineryApiRequest {
  const rows = activeRefineryRows(model);
  const request: RefineryApiRequest = {
    contract_version: "refinery-v1",
    symbols: rows.map((row) => normalizeRefinerySymbol(row.symbol)),
    start_date: model.startDate,
    end_date: model.endDate,
    ewma_decay: model.ewmaDecay,
    stress_quantile: model.stressQuantile,
  };
  const benchmark = normalizeRefinerySymbol(model.benchmark);
  if (benchmark) request.benchmark = benchmark;
  if (model.useWeights) {
    request.weights = rows.map((row) => ({
      symbol: normalizeRefinerySymbol(row.symbol),
      weight_percent: Number(row.weightPercent),
    }));
  }
  if (experimentPlan.length > 0) {
    request.experiment_plan = toRefineryExperimentPlan(experimentPlan);
  }
  return request;
}

export function migrateRefineryModel(value: unknown): RefineryWorkspaceModel {
  const fallback = createDefaultRefineryModel();
  if (!value || typeof value !== "object") return fallback;
  const raw = value as Partial<RefineryWorkspaceModel>;
  if (raw.schemaVersion !== 1 || !Array.isArray(raw.symbols)) return fallback;

  const symbols = raw.symbols.slice(0, MAX_REFINERY_CANDIDATES).map((row) => ({
    id: String(row?.id || uid("refinery-asset")),
    symbol: String(row?.symbol || ""),
    weightPercent:
      row?.weightPercent == null || !Number.isFinite(Number(row.weightPercent))
        ? null
        : Number(row.weightPercent),
  }));
  while (symbols.length < MIN_REFINERY_CANDIDATES) symbols.push(createRefineryAsset());

  return {
    schemaVersion: 1,
    symbols,
    benchmark: String(raw.benchmark || ""),
    startDate: typeof raw.startDate === "string" ? raw.startDate : fallback.startDate,
    endDate: typeof raw.endDate === "string" ? raw.endDate : fallback.endDate,
    useWeights: Boolean(raw.useWeights),
    ewmaDecay: Number.isFinite(Number(raw.ewmaDecay)) ? Number(raw.ewmaDecay) : fallback.ewmaDecay,
    stressQuantile: Number.isFinite(Number(raw.stressQuantile)) ? Number(raw.stressQuantile) : fallback.stressQuantile,
  };
}

export function addRefineryAsset(model: RefineryWorkspaceModel): RefineryWorkspaceModel {
  if (model.symbols.length >= MAX_REFINERY_CANDIDATES) return model;
  return { ...model, symbols: [...model.symbols, createRefineryAsset()] };
}

export function removeRefineryAsset(model: RefineryWorkspaceModel, id: string): RefineryWorkspaceModel {
  if (model.symbols.length <= MIN_REFINERY_CANDIDATES) return model;
  return { ...model, symbols: model.symbols.filter((row) => row.id !== id) };
}
