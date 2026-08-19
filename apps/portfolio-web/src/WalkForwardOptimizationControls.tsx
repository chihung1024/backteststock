import type {
  WalkForwardAllocationMethod,
  WalkForwardWorkspaceModel,
} from "./walkForwardTypes";
import {
  MAX_INNER_FOLDS,
  MAX_PARAMETER_CANDIDATES,
  MAX_TUNING_EVALUATIONS_PER_JOB,
  parameterOptimizationCandidateCount,
  parameterOptimizationPlannedEvaluations,
} from "./walkForwardModel";

const ALLOCATION_METHODS: Array<{ value: WalkForwardAllocationMethod; label: string }> = [
  { value: "equal", label: "Equal Weight" },
  { value: "inverse_volatility", label: "Inverse Volatility" },
  { value: "risk_parity_erc", label: "Risk Parity / ERC" },
];

function parseNumberList(value: string): number[] | null {
  const tokens = value.split(/[\s,]+/).map((item) => item.trim()).filter(Boolean);
  if (!tokens.length) return [];
  const numbers = tokens.map(Number);
  return numbers.every((item) => Number.isFinite(item)) ? numbers : null;
}

function numberList(values: number[], scale = 1): string {
  return values.map((value) => Number((value * scale).toFixed(8))).join(", ");
}

export function WalkForwardOptimizationControls({
  model,
  disabled,
  onPatch,
}: {
  model: WalkForwardWorkspaceModel;
  disabled: boolean;
  onPatch: (patch: Partial<WalkForwardWorkspaceModel>) => void;
}) {
  const search = model.optimizationSearchSpace;
  const inner = model.optimizationInnerValidation;
  const candidateCount = parameterOptimizationCandidateCount(search);
  const plannedEvaluations = parameterOptimizationPlannedEvaluations(model);
  const withinBudget = candidateCount >= 1
    && candidateCount <= MAX_PARAMETER_CANDIDATES
    && inner.foldCount >= 1
    && inner.foldCount <= MAX_INNER_FOLDS
    && plannedEvaluations <= MAX_TUNING_EVALUATIONS_PER_JOB;

  function commitList(
    raw: string,
    key: "lookbackMonths" | "topK" | "absoluteThresholds",
    scale = 1,
  ) {
    const parsed = parseNumberList(raw);
    if (parsed === null) return;
    onPatch({
      optimizationSearchSpace: {
        ...search,
        [key]: parsed.map((value) => value / scale),
      },
    });
  }

  function toggleAllocation(method: WalkForwardAllocationMethod, checked: boolean) {
    const next = new Set(search.allocationMethods);
    if (checked) next.add(method);
    else next.delete(method);
    onPatch({
      optimizationSearchSpace: {
        ...search,
        allocationMethods: ALLOCATION_METHODS
          .map((item) => item.value)
          .filter((item) => next.has(item)),
      },
    });
  }

  return (
    <div className="wf-optimizer-panel">
      <label className="field">
        <span>Parameter Optimization</span>
        <select
          aria-label="Dual Momentum Optimization Mode"
          value={model.optimizationMode}
          disabled={disabled}
          onChange={(event) => onPatch({ optimizationMode: event.target.value === "auto" ? "auto" : "manual" })}
        >
          <option value="manual">Manual</option>
          <option value="auto">Auto Optimize</option>
        </select>
        <small>Manual 沿用既有 4B-1/4B-2 request identity；Auto 才送出獨立、版本化的 nested parameterOptimization contract。</small>
      </label>

      {model.optimizationMode === "auto" && (
        <>
          <label className="field">
            <span>Lookback 搜尋（月）</span>
            <input
              key={`lookback-${numberList(search.lookbackMonths)}`}
              aria-label="Auto Optimize Lookback Search"
              defaultValue={numberList(search.lookbackMonths)}
              disabled={disabled}
              onBlur={(event) => commitList(event.currentTarget.value, "lookbackMonths")}
            />
            <small>逗號或空白分隔；後端 canonicalize、去重並排序，合法範圍 1–60 月。</small>
          </label>
          <label className="field">
            <span>Top K 搜尋</span>
            <input
              key={`topk-${numberList(search.topK)}`}
              aria-label="Auto Optimize Top K Search"
              defaultValue={numberList(search.topK)}
              disabled={disabled}
              onBlur={(event) => commitList(event.currentTarget.value, "topK")}
            />
            <small>每個值都必須介於 1 與目前 Risky 資產數之間。</small>
          </label>
          <label className="field">
            <span>Absolute Threshold 搜尋</span>
            <div className="input-with-suffix">
              <input
                key={`threshold-${numberList(search.absoluteThresholds, 100)}`}
                aria-label="Auto Optimize Absolute Threshold Search"
                defaultValue={numberList(search.absoluteThresholds, 100)}
                disabled={disabled}
                onBlur={(event) => commitList(event.currentTarget.value, "absoluteThresholds", 100)}
              />
              <span>%</span>
            </div>
            <small>畫面使用百分比；送往後端時保存為 return decimal，例如 5% = 0.05。</small>
          </label>
          <fieldset className="field wf-optimizer-methods" disabled={disabled}>
            <legend>Allocation 搜尋</legend>
            <div className="wf-checkbox-list">
              {ALLOCATION_METHODS.map((method) => (
                <label key={method.value}>
                  <input
                    type="checkbox"
                    checked={search.allocationMethods.includes(method.value)}
                    onChange={(event) => toggleAllocation(method.value, event.currentTarget.checked)}
                  />
                  <span>{method.label}</span>
                </label>
              ))}
            </div>
            <small>至少保留一種；瀏覽器不計算權重，候選仍由後端 4B-2 Allocation authority 執行。</small>
          </fieldset>
          <label className="field">
            <span>Inner folds</span>
            <input
              type="number"
              aria-label="Auto Optimize Inner Fold Count"
              min={1}
              max={MAX_INNER_FOLDS}
              step={1}
              value={inner.foldCount}
              disabled={disabled}
              onChange={(event) => onPatch({
                optimizationInnerValidation: { ...inner, foldCount: Number(event.currentTarget.value) },
              })}
            />
            <small>每一 fold 都完全位於該 Outer Training 內；outer Evaluation 不參與 tuning。</small>
          </label>
          <label className="field">
            <span>Inner Evaluation</span>
            <div className="input-with-suffix">
              <input
                type="number"
                aria-label="Auto Optimize Inner Evaluation Months"
                min={1}
                max={60}
                step={1}
                value={inner.evaluationMonths}
                disabled={disabled}
                onChange={(event) => onPatch({
                  optimizationInnerValidation: { ...inner, evaluationMonths: Number(event.currentTarget.value) },
                })}
              />
              <span>月</span>
            </div>
          </label>
          <label className="field">
            <span>Inner step</span>
            <div className="input-with-suffix">
              <input
                type="number"
                aria-label="Auto Optimize Inner Step Months"
                min={1}
                max={60}
                step={1}
                value={inner.stepMonths}
                disabled={disabled}
                onChange={(event) => onPatch({
                  optimizationInnerValidation: { ...inner, stepMonths: Number(event.currentTarget.value) },
                })}
              />
              <span>月</span>
            </div>
            <small>必須 ≥ Inner Evaluation，避免 inner OOS folds 重疊。</small>
          </label>
          <div className={`wf-optimizer-preflight ${withinBudget ? "ready" : "warning"}`} role="status">
            <strong>{withinBudget ? "Search budget 預檢通過" : "Search budget 需修正"}</strong>
            <span>{candidateCount} candidates × {inner.foldCount} folds × {model.periods.length} outer periods = {plannedEvaluations} tuning evaluations</span>
            <small>上限：{MAX_PARAMETER_CANDIDATES} candidates、{MAX_INNER_FOLDS} folds、{MAX_TUNING_EVALUATIONS_PER_JOB} total evaluations。後端會在任何 market-data 工作前再次 fail closed。</small>
          </div>
        </>
      )}
    </div>
  );
}
