import type {
  WalkForwardAdmissionResponse,
  WalkForwardApiRequest,
  WalkForwardPeriodDraft,
  WalkForwardValidationIssue,
  WalkForwardWorkspaceModel,
} from "./walkForwardTypes";

export const WALK_FORWARD_WORKSPACE_STORAGE_KEY = "backteststock.walk-forward.workspace.v1";
export const MAX_WALK_FORWARD_PERIODS = 24;
export const MAX_WALK_FORWARD_HOLDING_COUNT = 20;
export const MAX_WALK_FORWARD_TRANSITION_COST_BPS = 1000;

function uid(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isoUtc(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function shiftUtcDays(value: string, days: number): string {
  const date = new Date(`${value}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return isoUtc(date);
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

export function createDefaultWalkForwardModel(): WalkForwardWorkspaceModel {
  const latestComplete = latestCompleteUtcDate();
  return {
    schemaVersion: 1,
    // SOXX / 5 is the fail-safe fallback when admission has not loaded yet.
    // Live D1 admission replaces the date with exact causal evidence before first execution.
    universe: "soxx",
    benchmark: "SPY",
    holdingCount: 5,
    initialAmountTwd: 100000,
    transitionCostBps: 5,
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
    schemaVersion: 1,
    universe: recommendation.universe,
    benchmark: "SPY",
    holdingCount: recommendation.holdingCount,
    initialAmountTwd: 100000,
    transitionCostBps: 5,
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
  // Until the PIT archive has enough historical depth for multiple independent
  // OOS segments, examples must remain executable rather than fabricate history.
  return createDefaultWalkForwardModel();
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

export function migrateWalkForwardModel(value: unknown): WalkForwardWorkspaceModel {
  const fallback = createDefaultWalkForwardModel();
  const record = asRecord(value);
  if (!record || record.schemaVersion !== 1) return fallback;

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

  return {
    schemaVersion: 1,
    universe: stringValue(record, "universe", fallback.universe),
    benchmark: stringValue(record, "benchmark", fallback.benchmark),
    holdingCount: numberValue(record, "holdingCount", fallback.holdingCount),
    initialAmountTwd: numberValue(record, "initialAmountTwd", fallback.initialAmountTwd),
    transitionCostBps: numberValue(record, "transitionCostBps", fallback.transitionCostBps),
    periods: periods.length ? periods : fallback.periods,
  };
}

function isIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && isoUtc(parsed) === value;
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

export function validateWalkForwardModel(model: WalkForwardWorkspaceModel): WalkForwardValidationIssue[] {
  const issues: WalkForwardValidationIssue[] = [];
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
    }
  });

  return issues;
}

export function toWalkForwardApiRequest(model: WalkForwardWorkspaceModel): WalkForwardApiRequest {
  return {
    periods: model.periods.map((period) => ({
      periodId: period.periodId.trim(),
      trainingStart: period.trainingStart,
      trainingEnd: period.trainingEnd,
      decisionDate: period.decisionDate,
      evaluationStart: period.evaluationStart,
      evaluationEnd: period.evaluationEnd,
    })),
    selector: {
      universe: model.universe.trim().toLowerCase(),
      benchmark: model.benchmark.trim().toUpperCase(),
      holdingCount: model.holdingCount,
    },
    execution: {
      initialAmountTwd: model.initialAmountTwd,
      transitionCostBps: model.transitionCostBps,
    },
  };
}
