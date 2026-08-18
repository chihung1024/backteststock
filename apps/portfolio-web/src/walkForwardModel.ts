import type {
  WalkForwardAdmissionResponse,
  WalkForwardAllocationMethod,
  WalkForwardApiRequest,
  WalkForwardApiSelectorRequest,
  WalkForwardOptimizationMode,
  WalkForwardParameterOptimizationInnerValidation,
  WalkForwardParameterOptimizationSearchSpace,
  WalkForwardPeriodDraft,
  WalkForwardStrategy,
  WalkForwardValidationIssue,
  WalkForwardWorkspaceModel,
} from "./walkForwardTypes";

export const WALK_FORWARD_WORKSPACE_STORAGE_KEY = "backteststock.walk-forward.workspace.v1";
export const MAX_WALK_FORWARD_PERIODS = 24;
export const MAX_WALK_FORWARD_HOLDING_COUNT = 20;
export const MAX_WALK_FORWARD_TRANSITION_COST_BPS = 1000;
export const MAX_CONFIGURED_STRATEGY_SYMBOLS = 50;
export const MAX_MOMENTUM_LOOKBACK_MONTHS = 60;
export const MAX_PARAMETER_CANDIDATES = 48;
export const MAX_INNER_FOLDS = 6;
export const MAX_TUNING_EVALUATIONS_PER_JOB = 288;
export const DEFAULT_DUAL_MOMENTUM_PERIODS = 6;

const ALLOCATION_METHOD_ORDER: WalkForwardAllocationMethod[] = [
  "equal",
  "inverse_volatility",
  "risk_parity_erc",
];

function uid(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isoUtc(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function dateUtc(value: string): Date {
  return new Date(`${value}T00:00:00Z`);
}

function shiftUtcDays(value: string, days: number): string {
  const date = dateUtc(value);
  date.setUTCDate(date.getUTCDate() + days);
  return isoUtc(date);
}

function monthSerial(value: string): number {
  const date = dateUtc(value);
  return date.getUTCFullYear() * 12 + date.getUTCMonth();
}

function monthStartUtc(value: string): string {
  const date = dateUtc(value);
  return isoUtc(new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1)));
}

function monthEndUtc(value: string): string {
  const date = dateUtc(value);
  return isoUtc(new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)));
}

function shiftUtcMonthsClamped(value: string, months: number): string {
  const source = dateUtc(value);
  const targetMonthStart = new Date(Date.UTC(
    source.getUTCFullYear(),
    source.getUTCMonth() + months,
    1,
  ));
  const lastDay = new Date(Date.UTC(
    targetMonthStart.getUTCFullYear(),
    targetMonthStart.getUTCMonth() + 1,
    0,
  )).getUTCDate();
  targetMonthStart.setUTCDate(Math.min(source.getUTCDate(), lastDay));
  return isoUtc(targetMonthStart);
}

function calendarDaySpan(start: string, end: string): number {
  return Math.round((dateUtc(end).getTime() - dateUtc(start).getTime()) / 86_400_000);
}

export function latestCompleteUtcDate(): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() - 1);
  return isoUtc(date);
}

function createPeriodFromOffsets(
  periodId: string,
  latestComplete: string,
  decisionOffsetDays: number,
  evaluationEndOffsetDays: number,
): WalkForwardPeriodDraft {
  const decisionDate = shiftUtcDays(latestComplete, decisionOffsetDays);
  return {
    id: uid("walk-forward-period"),
    periodId,
    trainingStart: shiftUtcDays(decisionDate, -730),
    trainingEnd: decisionDate,
    decisionDate,
    evaluationStart: shiftUtcDays(decisionDate, 1),
    evaluationEnd: shiftUtcDays(latestComplete, evaluationEndOffsetDays),
  };
}

function defaultOptimizationSearchSpace(): WalkForwardParameterOptimizationSearchSpace {
  return {
    lookbackMonths: [6, 12],
    topK: [1, 3],
    absoluteThresholds: [0],
    allocationMethods: [...ALLOCATION_METHOD_ORDER],
  };
}

function defaultOptimizationInnerValidation(): WalkForwardParameterOptimizationInnerValidation {
  return {
    foldCount: 3,
    evaluationMonths: 1,
    stepMonths: 1,
  };
}

function baseWorkspaceFields(): Pick<
  WalkForwardWorkspaceModel,
  | "universe"
  | "benchmark"
  | "holdingCount"
  | "riskySymbolsText"
  | "defensiveSymbolsText"
  | "lookbackMonths"
  | "topK"
  | "absoluteThresholdPct"
  | "allocationMethod"
  | "optimizationMode"
  | "optimizationSearchSpace"
  | "optimizationInnerValidation"
  | "initialAmountTwd"
  | "transitionCostBps"
> {
  return {
    universe: "soxx",
    benchmark: "SPY",
    holdingCount: 5,
    riskySymbolsText: "QQQ, SMH, SPY, IWM, VEA, VWO",
    defensiveSymbolsText: "BIL",
    lookbackMonths: 12,
    topK: 3,
    absoluteThresholdPct: 0,
    allocationMethod: "equal",
    optimizationMode: "manual",
    optimizationSearchSpace: defaultOptimizationSearchSpace(),
    optimizationInnerValidation: defaultOptimizationInnerValidation(),
    initialAmountTwd: 100000,
    transitionCostBps: 5,
  };
}

export function createDefaultWalkForwardModel(): WalkForwardWorkspaceModel {
  const latestComplete = latestCompleteUtcDate();
  return {
    schemaVersion: 4,
    strategy: "exhaustive",
    ...baseWorkspaceFields(),
    periods: [createPeriodFromOffsets("period-1", latestComplete, -3, 0)],
  };
}

export function createWalkForwardModelFromAdmission(
  admission: WalkForwardAdmissionResponse,
): WalkForwardWorkspaceModel | null {
  const recommendation = admission.recommended;
  if (!recommendation) return null;
  const decisionDate = recommendation.decisionDate;
  return {
    schemaVersion: 4,
    strategy: "exhaustive",
    ...baseWorkspaceFields(),
    universe: recommendation.universe,
    benchmark: "SPY",
    holdingCount: recommendation.holdingCount,
    periods: [
      {
        id: uid("walk-forward-period"),
        periodId: "period-1",
        trainingStart: shiftUtcDays(decisionDate, -730),
        trainingEnd: decisionDate,
        decisionDate,
        evaluationStart: shiftUtcDays(decisionDate, 1),
        evaluationEnd: admission.asOfDate,
      },
    ],
  };
}

export function createExampleWalkForwardModel(): WalkForwardWorkspaceModel {
  return createDefaultWalkForwardModel();
}

export function createDualMomentumMonthlyPeriods(
  lookbackMonths: number,
  periodCount = DEFAULT_DUAL_MOMENTUM_PERIODS,
  latestComplete = latestCompleteUtcDate(),
): WalkForwardPeriodDraft[] {
  if (!Number.isInteger(lookbackMonths) || lookbackMonths < 1 || lookbackMonths > MAX_MOMENTUM_LOOKBACK_MONTHS) {
    throw new Error(`lookbackMonths must be an integer between 1 and ${MAX_MOMENTUM_LOOKBACK_MONTHS}`);
  }
  if (!Number.isInteger(periodCount) || periodCount < 1 || periodCount > MAX_WALK_FORWARD_PERIODS) {
    throw new Error(`periodCount must be an integer between 1 and ${MAX_WALK_FORWARD_PERIODS}`);
  }
  if (!isIsoDate(latestComplete)) throw new Error("latestComplete must be an ISO date");

  const latestEvaluationMonthStart = monthStartUtc(latestComplete);
  const periods: WalkForwardPeriodDraft[] = [];
  for (let offset = periodCount - 1; offset >= 0; offset -= 1) {
    const evaluationStart = shiftUtcMonthsClamped(latestEvaluationMonthStart, -offset);
    const decisionDate = shiftUtcDays(evaluationStart, -1);
    const fullEvaluationEnd = monthEndUtc(evaluationStart);
    const evaluationEnd = fullEvaluationEnd > latestComplete ? latestComplete : fullEvaluationEnd;
    periods.push({
      id: uid("walk-forward-period"),
      periodId: `dm-${evaluationStart.slice(0, 7)}`,
      trainingStart: shiftUtcMonthsClamped(decisionDate, -lookbackMonths),
      trainingEnd: decisionDate,
      decisionDate,
      evaluationStart,
      evaluationEnd,
    });
  }
  return periods;
}

export function requiredOptimizationTrainingStart(
  decisionDate: string,
  searchSpace: WalkForwardParameterOptimizationSearchSpace,
  innerValidation: WalkForwardParameterOptimizationInnerValidation,
): string {
  const normalized = normalizeOptimizationSearchSpace(searchSpace);
  const maximumLookback = Math.max(...normalized.lookbackMonths);
  const decisionMonthEnd = monthEndUtc(decisionDate);
  const newestCompletedMonthEnd = decisionDate === decisionMonthEnd
    ? decisionDate
    : monthEndUtc(shiftUtcMonthsClamped(monthStartUtc(decisionDate), -1));
  const earliestEvaluationEnd = shiftUtcMonthsClamped(
    newestCompletedMonthEnd,
    -(innerValidation.foldCount - 1) * innerValidation.stepMonths,
  );
  const earliestEvaluationStart = monthStartUtc(
    shiftUtcMonthsClamped(
      earliestEvaluationEnd,
      -(innerValidation.evaluationMonths - 1),
    ),
  );
  const earliestInnerDecision = shiftUtcDays(earliestEvaluationStart, -1);
  return shiftUtcMonthsClamped(earliestInnerDecision, -maximumLookback);
}

export function createDualMomentumAutoPeriods(
  searchSpace: WalkForwardParameterOptimizationSearchSpace,
  innerValidation: WalkForwardParameterOptimizationInnerValidation,
  periodCount = DEFAULT_DUAL_MOMENTUM_PERIODS,
  latestComplete = latestCompleteUtcDate(),
): WalkForwardPeriodDraft[] {
  const normalized = normalizeOptimizationSearchSpace(searchSpace);
  const periods = createDualMomentumMonthlyPeriods(
    Math.max(...normalized.lookbackMonths),
    periodCount,
    latestComplete,
  );
  return periods.map((period) => ({
    ...period,
    trainingStart: requiredOptimizationTrainingStart(
      period.decisionDate,
      normalized,
      innerValidation,
    ),
  }));
}

export function createDualMomentumWalkForwardModel(): WalkForwardWorkspaceModel {
  const base = baseWorkspaceFields();
  return {
    schemaVersion: 4,
    strategy: "dual_momentum",
    ...base,
    periods: createDualMomentumMonthlyPeriods(base.lookbackMonths),
  };
}

export function createBlankWalkForwardPeriod(index: number): WalkForwardPeriodDraft {
  return {
    id: uid("walk-forward-period"),
    periodId: `period-${index + 1}`,
    trainingStart: "",
    trainingEnd: "",
    decisionDate: "",
    evaluationStart: "",
    evaluationEnd: "",
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringValue(record: Record<string, unknown>, key: string, fallback: string): string {
  const value = record[key];
  return typeof value === "string" ? value : fallback;
}

function numberValue(record: Record<string, unknown>, key: string, fallback: number): number {
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function strategyValue(record: Record<string, unknown>): WalkForwardStrategy {
  return record.strategy === "dual_momentum" ? "dual_momentum" : "exhaustive";
}

function allocationMethodValue(record: Record<string, unknown>): WalkForwardAllocationMethod {
  if (record.allocationMethod === "inverse_volatility") return "inverse_volatility";
  if (record.allocationMethod === "risk_parity_erc") return "risk_parity_erc";
  return "equal";
}

function optimizationModeValue(record: Record<string, unknown>): WalkForwardOptimizationMode {
  return record.optimizationMode === "auto" ? "auto" : "manual";
}

function finiteNumberArray(value: unknown, fallback: number[]): number[] {
  if (!Array.isArray(value)) return [...fallback];
  const values = value.filter((item): item is number => typeof item === "number" && Number.isFinite(item));
  return values.length ? values : [...fallback];
}

function allocationMethodsValue(
  value: unknown,
  fallback: WalkForwardAllocationMethod[],
): WalkForwardAllocationMethod[] {
  if (!Array.isArray(value)) return [...fallback];
  const methods = value.filter((item): item is WalkForwardAllocationMethod => (
    item === "equal" || item === "inverse_volatility" || item === "risk_parity_erc"
  ));
  return methods.length ? methods : [...fallback];
}

function optimizationSearchSpaceValue(
  record: Record<string, unknown>,
  fallback: WalkForwardParameterOptimizationSearchSpace,
): WalkForwardParameterOptimizationSearchSpace {
  const raw = asRecord(record.optimizationSearchSpace);
  if (!raw) return { ...fallback, allocationMethods: [...fallback.allocationMethods] };
  return {
    lookbackMonths: finiteNumberArray(raw.lookbackMonths, fallback.lookbackMonths),
    topK: finiteNumberArray(raw.topK, fallback.topK),
    absoluteThresholds: finiteNumberArray(raw.absoluteThresholds, fallback.absoluteThresholds),
    allocationMethods: allocationMethodsValue(raw.allocationMethods, fallback.allocationMethods),
  };
}

function optimizationInnerValidationValue(
  record: Record<string, unknown>,
  fallback: WalkForwardParameterOptimizationInnerValidation,
): WalkForwardParameterOptimizationInnerValidation {
  const raw = asRecord(record.optimizationInnerValidation);
  if (!raw) return { ...fallback };
  return {
    foldCount: numberValue(raw, "foldCount", fallback.foldCount),
    evaluationMonths: numberValue(raw, "evaluationMonths", fallback.evaluationMonths),
    stepMonths: numberValue(raw, "stepMonths", fallback.stepMonths),
  };
}

export function migrateWalkForwardModel(value: unknown): WalkForwardWorkspaceModel {
  const fallback = createDefaultWalkForwardModel();
  const record = asRecord(value);
  if (!record || ![1, 2, 3, 4].includes(Number(record.schemaVersion))) return fallback;

  const periodsValue = Array.isArray(record.periods) ? record.periods.slice(0, MAX_WALK_FORWARD_PERIODS) : [];
  const periods = periodsValue.map((item, index) => {
    const period = asRecord(item) ?? {};
    return {
      id: stringValue(period, "id", uid("walk-forward-period")),
      periodId: stringValue(period, "periodId", `period-${index + 1}`),
      trainingStart: stringValue(period, "trainingStart", ""),
      trainingEnd: stringValue(period, "trainingEnd", ""),
      decisionDate: stringValue(period, "decisionDate", ""),
      evaluationStart: stringValue(period, "evaluationStart", ""),
      evaluationEnd: stringValue(period, "evaluationEnd", ""),
    } satisfies WalkForwardPeriodDraft;
  });

  const optimizationSearchSpace = optimizationSearchSpaceValue(
    record,
    fallback.optimizationSearchSpace,
  );
  const optimizationInnerValidation = optimizationInnerValidationValue(
    record,
    fallback.optimizationInnerValidation,
  );

  return {
    schemaVersion: 4,
    strategy: record.schemaVersion === 1 ? "exhaustive" : strategyValue(record),
    allocationMethod: allocationMethodValue(record),
    optimizationMode: Number(record.schemaVersion) >= 4
      ? optimizationModeValue(record)
      : "manual",
    optimizationSearchSpace,
    optimizationInnerValidation,
    universe: stringValue(record, "universe", fallback.universe),
    benchmark: stringValue(record, "benchmark", fallback.benchmark),
    holdingCount: numberValue(record, "holdingCount", fallback.holdingCount),
    riskySymbolsText: stringValue(record, "riskySymbolsText", fallback.riskySymbolsText),
    defensiveSymbolsText: stringValue(record, "defensiveSymbolsText", fallback.defensiveSymbolsText),
    lookbackMonths: numberValue(record, "lookbackMonths", fallback.lookbackMonths),
    topK: numberValue(record, "topK", fallback.topK),
    absoluteThresholdPct: numberValue(record, "absoluteThresholdPct", fallback.absoluteThresholdPct),
    initialAmountTwd: numberValue(record, "initialAmountTwd", fallback.initialAmountTwd),
    transitionCostBps: numberValue(record, "transitionCostBps", fallback.transitionCostBps),
    periods: periods.length ? periods : fallback.periods,
  };
}

function isIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(value)) return false;
  const parsed = dateUtc(value);
  return !Number.isNaN(parsed.getTime()) && isoUtc(parsed) === value;
}

export function parseWalkForwardSymbols(value: string): string[] {
  return value
    .split(/[\s,;]+/u)
    .map((symbol) => symbol.trim().toUpperCase())
    .filter(Boolean);
}

function pushDateIssue(
  issues: WalkForwardValidationIssue[],
  period: WalkForwardPeriodDraft,
  field: keyof Pick<
    WalkForwardPeriodDraft,
    "trainingStart" | "trainingEnd" | "decisionDate" | "evaluationStart" | "evaluationEnd"
  >,
  label: string,
): boolean {
  const value = period[field];
  if (isIsoDate(value)) return true;
  issues.push({ field: `${period.id}.${field}`, message: `${period.periodId || "Period"}：${label}必須是有效日期。` });
  return false;
}

function validateExhaustiveSettings(
  model: WalkForwardWorkspaceModel,
  issues: WalkForwardValidationIssue[],
): void {
  const universe = model.universe.trim();
  const benchmark = model.benchmark.trim();
  if (!universe) {
    issues.push({ field: "universe", message: "Universe 不可空白。" });
  } else if (!/^[a-z0-9-]+$/u.test(universe)) {
    issues.push({ field: "universe", message: "Universe 只能使用小寫英文字母、數字與連字號。" });
  }
  if (!benchmark) {
    issues.push({ field: "benchmark", message: "Benchmark 不可空白。" });
  } else if (benchmark !== benchmark.toUpperCase()) {
    issues.push({ field: "benchmark", message: "Benchmark 必須使用大寫 canonical symbol。" });
  }
  if (!Number.isInteger(model.holdingCount) || model.holdingCount < 1 || model.holdingCount > MAX_WALK_FORWARD_HOLDING_COUNT) {
    issues.push({ field: "holdingCount", message: `持股檔數必須是 1–${MAX_WALK_FORWARD_HOLDING_COUNT} 的整數。` });
  }
}

function sortedUniqueNumbers(values: number[]): number[] {
  return [...new Set(values.map((value) => (Object.is(value, -0) ? 0 : value)))].sort((a, b) => a - b);
}

export function normalizeOptimizationSearchSpace(
  searchSpace: WalkForwardParameterOptimizationSearchSpace,
): WalkForwardParameterOptimizationSearchSpace {
  const methodSet = new Set(searchSpace.allocationMethods);
  return {
    lookbackMonths: sortedUniqueNumbers(searchSpace.lookbackMonths),
    topK: sortedUniqueNumbers(searchSpace.topK),
    absoluteThresholds: sortedUniqueNumbers(searchSpace.absoluteThresholds),
    allocationMethods: ALLOCATION_METHOD_ORDER.filter((method) => methodSet.has(method)),
  };
}

export function parameterOptimizationCandidateCount(
  searchSpace: WalkForwardParameterOptimizationSearchSpace,
): number {
  const normalized = normalizeOptimizationSearchSpace(searchSpace);
  return normalized.lookbackMonths.length
    * normalized.topK.length
    * normalized.absoluteThresholds.length
    * normalized.allocationMethods.length;
}

export function parameterOptimizationPlannedEvaluations(model: WalkForwardWorkspaceModel): number {
  return parameterOptimizationCandidateCount(model.optimizationSearchSpace)
    * model.optimizationInnerValidation.foldCount
    * model.periods.length;
}

function validateAutoOptimizationSettings(
  model: WalkForwardWorkspaceModel,
  risky: string[],
  issues: WalkForwardValidationIssue[],
): void {
  const search = normalizeOptimizationSearchSpace(model.optimizationSearchSpace);
  if (!search.lookbackMonths.length || search.lookbackMonths.some((value) => (
    !Number.isInteger(value) || value < 1 || value > MAX_MOMENTUM_LOOKBACK_MONTHS
  ))) {
    issues.push({ field: "optimizationSearchSpace.lookbackMonths", message: `Auto Optimize Lookback 必須包含 1–${MAX_MOMENTUM_LOOKBACK_MONTHS} 的整數。` });
  }
  if (!search.topK.length || search.topK.some((value) => (
    !Number.isInteger(value) || value < 1 || value > risky.length
  ))) {
    issues.push({ field: "optimizationSearchSpace.topK", message: `Auto Optimize Top K 必須介於 1–${Math.max(1, risky.length)}。` });
  }
  if (!search.absoluteThresholds.length || search.absoluteThresholds.some((value) => !Number.isFinite(value))) {
    issues.push({ field: "optimizationSearchSpace.absoluteThresholds", message: "Auto Optimize Threshold 必須包含有限數值。" });
  }
  if (!search.allocationMethods.length) {
    issues.push({ field: "optimizationSearchSpace.allocationMethods", message: "Auto Optimize 至少需要 1 種 Allocation 方法。" });
  }
  const validation = model.optimizationInnerValidation;
  if (!Number.isInteger(validation.foldCount) || validation.foldCount < 1 || validation.foldCount > MAX_INNER_FOLDS) {
    issues.push({ field: "optimizationInnerValidation.foldCount", message: `Inner Fold 必須介於 1–${MAX_INNER_FOLDS}。` });
  }
  if (!Number.isInteger(validation.evaluationMonths) || validation.evaluationMonths < 1 || validation.evaluationMonths > 60) {
    issues.push({ field: "optimizationInnerValidation.evaluationMonths", message: "Inner Evaluation Months 必須是 1–60 的整數。" });
  }
  if (!Number.isInteger(validation.stepMonths) || validation.stepMonths < validation.evaluationMonths || validation.stepMonths > 60) {
    issues.push({ field: "optimizationInnerValidation.stepMonths", message: "Inner Step Months 必須大於等於 Evaluation Months，且不超過 60。" });
  }
  const candidates = parameterOptimizationCandidateCount(search);
  if (candidates < 1 || candidates > MAX_PARAMETER_CANDIDATES) {
    issues.push({ field: "optimizationSearchSpace", message: `Auto Optimize 正規化後候選數必須介於 1–${MAX_PARAMETER_CANDIDATES}，目前 ${candidates}。` });
  }
  const planned = candidates * validation.foldCount * model.periods.length;
  if (planned > MAX_TUNING_EVALUATIONS_PER_JOB) {
    issues.push({ field: "optimizationSearchSpace", message: `Auto Optimize 預計 ${planned} 次 candidate-fold 評估，超過目前同步上限 ${MAX_TUNING_EVALUATIONS_PER_JOB}。` });
  }
}

function validateDualMomentumSettings(
  model: WalkForwardWorkspaceModel,
  issues: WalkForwardValidationIssue[],
): void {
  const risky = parseWalkForwardSymbols(model.riskySymbolsText);
  const defensive = parseWalkForwardSymbols(model.defensiveSymbolsText);
  if (!risky.length) issues.push({ field: "riskySymbolsText", message: "Dual Momentum 至少需要 1 檔風險資產。" });
  if (!defensive.length) issues.push({ field: "defensiveSymbolsText", message: "Dual Momentum 至少需要 1 檔防禦資產。" });
  if (new Set(risky).size !== risky.length) issues.push({ field: "riskySymbolsText", message: "風險資產不可重複。" });
  if (new Set(defensive).size !== defensive.length) issues.push({ field: "defensiveSymbolsText", message: "防禦資產不可重複。" });
  const overlap = risky.filter((symbol) => defensive.includes(symbol));
  if (overlap.length) issues.push({ field: "defensiveSymbolsText", message: `風險與防禦資產不可重疊：${[...new Set(overlap)].join(", ")}。` });
  if (risky.length + defensive.length > MAX_CONFIGURED_STRATEGY_SYMBOLS) {
    issues.push({ field: "riskySymbolsText", message: `Dual Momentum 合計最多 ${MAX_CONFIGURED_STRATEGY_SYMBOLS} 檔資產。` });
  }
  if (model.optimizationMode === "auto") {
    validateAutoOptimizationSettings(model, risky, issues);
    return;
  }
  if (!Number.isInteger(model.lookbackMonths) || model.lookbackMonths < 1 || model.lookbackMonths > MAX_MOMENTUM_LOOKBACK_MONTHS) {
    issues.push({ field: "lookbackMonths", message: `Momentum Lookback 必須是 1–${MAX_MOMENTUM_LOOKBACK_MONTHS} 個月的整數。` });
  }
  if (!Number.isInteger(model.topK) || model.topK < 1 || model.topK > risky.length) {
    issues.push({ field: "topK", message: `Top K 必須是 1–${Math.max(1, risky.length)} 的整數，且不可超過風險資產數。` });
  }
  if (!Number.isFinite(model.absoluteThresholdPct)) {
    issues.push({ field: "absoluteThresholdPct", message: "Absolute Threshold 必須是有限數值。" });
  }
}

export function validateWalkForwardModel(model: WalkForwardWorkspaceModel): WalkForwardValidationIssue[] {
  const issues: WalkForwardValidationIssue[] = [];
  if (model.strategy === "dual_momentum") validateDualMomentumSettings(model, issues);
  else validateExhaustiveSettings(model, issues);

  if (!Number.isFinite(model.initialAmountTwd) || model.initialAmountTwd <= 0 || model.initialAmountTwd > 1e12) {
    issues.push({ field: "initialAmountTwd", message: "初始資金必須大於 0，且不得超過 1 兆 TWD。" });
  }
  if (!Number.isFinite(model.transitionCostBps) || model.transitionCostBps < 0 || model.transitionCostBps > MAX_WALK_FORWARD_TRANSITION_COST_BPS) {
    issues.push({ field: "transitionCostBps", message: `換倉成本必須介於 0–${MAX_WALK_FORWARD_TRANSITION_COST_BPS} bps。` });
  }
  if (model.periods.length < 1 || model.periods.length > MAX_WALK_FORWARD_PERIODS) {
    issues.push({ field: "periods", message: `Walk-Forward 必須包含 1–${MAX_WALK_FORWARD_PERIODS} 個 Period。` });
    return issues;
  }

  const periodIds = model.periods.map((period) => period.periodId.trim());
  if (periodIds.some((periodId) => !periodId)) {
    issues.push({ field: "periods.periodId", message: "每個 Period 都必須有唯一名稱。" });
  }
  if (new Set(periodIds).size !== periodIds.length) {
    issues.push({ field: "periods.periodId", message: "Period 名稱不可重複。" });
  }

  const latestComplete = latestCompleteUtcDate();
  model.periods.forEach((period, index) => {
    const trainingStartOk = pushDateIssue(issues, period, "trainingStart", "Training 起始日");
    const trainingEndOk = pushDateIssue(issues, period, "trainingEnd", "Training 結束日");
    const decisionOk = pushDateIssue(issues, period, "decisionDate", "Decision 日期");
    const evaluationStartOk = pushDateIssue(issues, period, "evaluationStart", "Evaluation 起始日");
    const evaluationEndOk = pushDateIssue(issues, period, "evaluationEnd", "Evaluation 結束日");

    if (trainingStartOk && trainingEndOk && period.trainingStart > period.trainingEnd) {
      issues.push({ field: `${period.id}.training`, message: `${period.periodId}：Training 起始日不可晚於結束日。` });
    }
    if (trainingEndOk && decisionOk && period.trainingEnd > period.decisionDate) {
      issues.push({ field: `${period.id}.decisionDate`, message: `${period.periodId}：Training 資料必須在 Decision 日期以前或當日結束。` });
    }
    if (decisionOk && evaluationStartOk && period.evaluationStart <= period.decisionDate) {
      issues.push({ field: `${period.id}.evaluationStart`, message: `${period.periodId}：Evaluation 起始日必須嚴格晚於 Decision 日期。` });
    }
    if (evaluationStartOk && evaluationEndOk && period.evaluationStart > period.evaluationEnd) {
      issues.push({ field: `${period.id}.evaluation`, message: `${period.periodId}：Evaluation 起始日不可晚於結束日。` });
    }
    if (evaluationEndOk && period.evaluationEnd > latestComplete) {
      issues.push({ field: `${period.id}.evaluationEnd`, message: `${period.periodId}：Evaluation 結束日不得晚於最後完整 UTC 日 ${latestComplete}。` });
    }

    if (model.strategy === "dual_momentum" && trainingStartOk && trainingEndOk && decisionOk && evaluationStartOk && evaluationEndOk) {
      if (period.trainingEnd !== period.decisionDate) {
        issues.push({ field: `${period.id}.trainingEnd`, message: `${period.periodId}：Dual Momentum 的 Training 結束日必須等於 Decision 日期。` });
      }
      if (period.evaluationStart !== shiftUtcDays(period.decisionDate, 1)) {
        issues.push({ field: `${period.id}.evaluationStart`, message: `${period.periodId}：Dual Momentum 的 Evaluation 必須從 Decision 次一日開始。` });
      }
      if (calendarDaySpan(period.decisionDate, period.evaluationEnd) > 35) {
        issues.push({ field: `${period.id}.evaluationEnd`, message: `${period.periodId}：Dual Momentum 每個 OOS 月度區間最多 35 個日曆日。` });
      }
      if (model.optimizationMode === "auto") {
        const normalized = normalizeOptimizationSearchSpace(model.optimizationSearchSpace);
        if (normalized.lookbackMonths.length && model.optimizationInnerValidation.foldCount >= 1) {
          const requiredStart = requiredOptimizationTrainingStart(
            period.decisionDate,
            normalized,
            model.optimizationInnerValidation,
          );
          if (period.trainingStart > requiredStart) {
            issues.push({ field: `${period.id}.trainingStart`, message: `${period.periodId}：Auto Optimize Training 起始日不足以涵蓋最大 Lookback 與 Inner Folds，至少需到 ${requiredStart}。` });
          }
        }
      } else if (Number.isInteger(model.lookbackMonths) && model.lookbackMonths >= 1 && model.lookbackMonths <= MAX_MOMENTUM_LOOKBACK_MONTHS) {
        const requiredStart = shiftUtcMonthsClamped(period.decisionDate, -model.lookbackMonths);
        if (period.trainingStart > requiredStart) {
          issues.push({ field: `${period.id}.trainingStart`, message: `${period.periodId}：Training 起始日必須涵蓋完整 ${model.lookbackMonths} 個月 Momentum Lookback。` });
        }
      }
    }

    if (index > 0) {
      const previous = model.periods[index - 1];
      if (!previous) return;
      if (decisionOk && isIsoDate(previous.decisionDate) && period.decisionDate <= previous.decisionDate) {
        issues.push({ field: `${period.id}.decisionOrder`, message: `${period.periodId}：Decision 日期必須嚴格晚於前一期。` });
      }
      if (evaluationStartOk && isIsoDate(previous.evaluationEnd) && period.evaluationStart <= previous.evaluationEnd) {
        issues.push({ field: `${period.id}.evaluationOverlap`, message: `${period.periodId}：Evaluation 區間不可與前一期重疊。` });
      }
      if (decisionOk && isIsoDate(previous.evaluationEnd) && period.decisionDate < previous.evaluationEnd) {
        issues.push({ field: `${period.id}.decisionOverlap`, message: `${period.periodId}：下一個 Decision 日期不可早於前一期 Evaluation 結束日。` });
      }
      if (model.strategy === "dual_momentum" && decisionOk && isIsoDate(previous.decisionDate) && isIsoDate(previous.evaluationEnd)) {
        if (monthSerial(period.decisionDate) !== monthSerial(previous.decisionDate) + 1) {
          issues.push({ field: `${period.id}.decisionMonth`, message: `${period.periodId}：Dual Momentum 必須每個連續月份形成一次 Decision。` });
        }
        if (previous.evaluationEnd !== period.decisionDate) {
          issues.push({ field: `${period.id}.oosGap`, message: `${period.periodId}：Dual Momentum 月度 OOS 必須連續銜接，前一期 Evaluation 結束日需等於本期 Decision 日期。` });
        }
      }
    }
  });

  return issues;
}

export function toWalkForwardApiRequest(model: WalkForwardWorkspaceModel): WalkForwardApiRequest {
  const selector: WalkForwardApiSelectorRequest = model.strategy === "dual_momentum"
    ? model.optimizationMode === "auto"
      ? {
          strategy: "dual_momentum",
          riskySymbols: parseWalkForwardSymbols(model.riskySymbolsText),
          defensiveSymbols: parseWalkForwardSymbols(model.defensiveSymbolsText),
          parameterOptimization: {
            searchSpace: normalizeOptimizationSearchSpace(model.optimizationSearchSpace),
            innerValidation: { ...model.optimizationInnerValidation },
          },
        }
      : {
          strategy: "dual_momentum",
          riskySymbols: parseWalkForwardSymbols(model.riskySymbolsText),
          defensiveSymbols: parseWalkForwardSymbols(model.defensiveSymbolsText),
          lookbackMonths: model.lookbackMonths,
          topK: model.topK,
          absoluteThreshold: model.absoluteThresholdPct / 100,
          allocationMethod: model.allocationMethod,
        }
    : {
        universe: model.universe.trim().toLowerCase(),
        benchmark: model.benchmark.trim().toUpperCase(),
        holdingCount: model.holdingCount,
      };

  return {
    periods: model.periods.map((period) => ({
      periodId: period.periodId.trim(),
      trainingStart: period.trainingStart,
      trainingEnd: period.trainingEnd,
      decisionDate: period.decisionDate,
      evaluationStart: period.evaluationStart,
      evaluationEnd: period.evaluationEnd,
    })),
    selector,
    execution: {
      initialAmountTwd: model.initialAmountTwd,
      transitionCostBps: model.transitionCostBps,
    },
  };
}