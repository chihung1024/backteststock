import {
  MAX_REFINERY_EXPERIMENT_OPERATIONS,
  MAX_REFINERY_EXPERIMENT_UNION_SYMBOLS,
  createRefineryExperimentDraft,
  normalizeRefinerySymbol,
} from "./refineryModel";
import type {
  RefineryExperimentDraft,
  RefineryExperimentOperationType,
} from "./refineryTypes";

const OPERATION_LABELS: Record<RefineryExperimentOperationType, string> = {
  remove_one: "移除一檔",
  add_one: "新增一檔",
  replace_one: "替換一檔",
};

function externalSymbols(plan: RefineryExperimentDraft[]): string[] {
  const values = new Set<string>();
  for (const draft of plan) {
    if (draft.type === "remove_one") continue;
    const symbol = normalizeRefinerySymbol(draft.add);
    if (symbol) values.add(symbol);
  }
  return [...values];
}

function updateDraftType(
  draft: RefineryExperimentDraft,
  type: RefineryExperimentOperationType,
): RefineryExperimentDraft {
  return {
    ...draft,
    type,
    remove: type === "add_one" ? "" : draft.remove,
    add: type === "remove_one" ? "" : draft.add,
  };
}

function planSummary(
  baselineSymbols: string[],
  plan: RefineryExperimentDraft[],
): string {
  const external = externalSymbols(plan);
  return `${baselineSymbols.length} baseline + ${external.length} 外部代碼 = ${baselineSymbols.length + external.length} / ${MAX_REFINERY_EXPERIMENT_UNION_SYMBOLS} 聯集上限`;
}

interface RefineryExperimentPlanEditorProps {
  baselineSymbols: string[];
  plan: RefineryExperimentDraft[];
  onChange: (plan: RefineryExperimentDraft[]) => void;
}

export function RefineryExperimentPlanEditor({
  baselineSymbols,
  plan,
  onChange,
}: RefineryExperimentPlanEditorProps) {
  function updateDraft(id: string, updater: (draft: RefineryExperimentDraft) => RefineryExperimentDraft) {
    onChange(plan.map((draft) => (draft.id === id ? updater(draft) : draft)));
  }

  return (
    <section className="workspace-card refinery-phase6-editor" aria-labelledby="refinery-phase6-plan-title">
      <div className="section-heading">
        <div>
          <span className="section-index">2</span>
          <div>
            <h2 id="refinery-phase6-plan-title">Phase 6 邊際實驗（選填）</h2>
            <p>只執行明確列出的移除／新增／替換；不會自動產生 Cartesian 組合，也不提供持股建議。</p>
          </div>
        </div>
        <span className="summary-chip">{plan.length} / {MAX_REFINERY_EXPERIMENT_OPERATIONS} 筆</span>
      </div>

      <div className="refinery-phase6-baseline" aria-label="目前 baseline candidate">
        <span>Baseline</span>
        <strong>{baselineSymbols.length > 0 ? baselineSymbols.join(" · ") : "尚未輸入有效候選持股"}</strong>
      </div>

      {plan.length === 0 ? (
        <div className="notice info">
          <strong>未啟用邊際實驗</strong>
          <p>維持既有 Phase 3–5 診斷；此區的設定只在本次頁面工作階段保留，不寫入 Refinery workspace。</p>
        </div>
      ) : (
        <div className="refinery-phase6-plan-list" aria-label="Phase 6 實驗計畫">
          {plan.map((draft, index) => (
            <article className="refinery-phase6-plan-row" key={draft.id}>
              <div className="refinery-phase6-plan-row-heading">
                <strong>實驗 {index + 1}</strong>
                <button
                  type="button"
                  className="icon-button danger"
                  aria-label={`刪除實驗 ${index + 1}`}
                  onClick={() => onChange(plan.filter((item) => item.id !== draft.id))}
                >
                  ×
                </button>
              </div>
              <label>
                <span>操作</span>
                <select
                  aria-label={`實驗 ${index + 1} 操作`}
                  value={draft.type}
                  onChange={(event) => updateDraft(
                    draft.id,
                    (current) => updateDraftType(
                      current,
                      event.target.value as RefineryExperimentOperationType,
                    ),
                  )}
                >
                  {(Object.keys(OPERATION_LABELS) as RefineryExperimentOperationType[]).map((type) => (
                    <option value={type} key={type}>{OPERATION_LABELS[type]}</option>
                  ))}
                </select>
              </label>
              {draft.type !== "add_one" && (
                <label>
                  <span>移除 baseline 代碼</span>
                  <input
                    aria-label={`實驗 ${index + 1} 移除代碼`}
                    value={draft.remove}
                    placeholder="例如 AAPL"
                    onChange={(event) => updateDraft(
                      draft.id,
                      (current) => ({ ...current, remove: event.target.value.toUpperCase() }),
                    )}
                  />
                </label>
              )}
              {draft.type !== "remove_one" && (
                <label>
                  <span>新增外部代碼</span>
                  <input
                    aria-label={`實驗 ${index + 1} 新增代碼`}
                    value={draft.add}
                    placeholder="例如 MSFT / 2330"
                    onChange={(event) => updateDraft(
                      draft.id,
                      (current) => ({ ...current, add: event.target.value.toUpperCase() }),
                    )}
                  />
                </label>
              )}
            </article>
          ))}
        </div>
      )}

      <div className="inline-actions refinery-phase6-plan-actions">
        <button
          type="button"
          className="secondary-button"
          disabled={plan.length >= MAX_REFINERY_EXPERIMENT_OPERATIONS}
          onClick={() => onChange([...plan, createRefineryExperimentDraft()])}
        >
          ＋ 新增明確實驗
        </button>
        <span className="workspace-hint">{planSummary(baselineSymbols, plan)}</span>
      </div>
      <p className="refinery-method-note">後端會再次正規化 ticker、驗證 membership 與資源上限。所有可用實驗會共享同一份全聯集日／週共同樣本；這是 in-sample historical diagnostic，不是 OOS 或交易訊號。</p>
    </section>
  );
}
