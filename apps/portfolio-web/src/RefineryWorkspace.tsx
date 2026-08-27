import { useEffect, useMemo, useRef, useState } from "react";
import { RefineryApiError, runRefineryAnalyze, runRefineryPreflight } from "./refineryApi";
import {
  MAX_REFINERY_CANDIDATES,
  REFINERY_WORKSPACE_STORAGE_KEY,
  addRefineryAsset,
  createDefaultRefineryModel,
  createExampleRefineryModel,
  migrateRefineryModel,
  normalizeRefinerySymbol,
  refineryWeightTotal,
  removeRefineryAsset,
  toRefineryApiRequest,
  validateRefineryExperimentPlan,
  validateRefineryModel,
} from "./refineryModel";
import { RefineryExperimentPlanEditor } from "./RefineryExperimentPlanEditor";
import { RefineryPhase6Preflight } from "./RefineryPhase6Results";
import { RefineryPreflightCard, RefineryResults } from "./RefineryResults";
import type {
  RefineryAnalyzeResponse,
  RefineryExperimentDraft,
  RefineryPreflightResponse,
  RefineryWorkspaceModel,
} from "./refineryTypes";

function loadInitialRefineryModel(): RefineryWorkspaceModel {
  try {
    const saved = window.localStorage.getItem(REFINERY_WORKSPACE_STORAGE_KEY);
    return saved ? migrateRefineryModel(JSON.parse(saved) as unknown) : createDefaultRefineryModel();
  } catch {
    return createDefaultRefineryModel();
  }
}

function errorText(error: unknown): string {
  if (error instanceof RefineryApiError) {
    const request = error.requestId ? `（Request ${error.requestId}）` : "";
    return `${error.message}${request}`;
  }
  if (error instanceof Error) return error.message;
  return "Refinery 發生未知錯誤。";
}

function statusExplanation(status: string): string {
  if (status === "ready") return "候選持股資料完整且達到分析最低樣本要求。";
  if (status === "incomplete") return "至少一檔 requested candidate 未成功取回；正式分析已停止，沒有縮小 universe 偷算。";
  if (status === "insufficient_data") return "候選持股完整，但共同樣本不足；正式分析不輸出假精度。";
  return status;
}

export function RefineryWorkspace() {
  const [model, setModelState] = useState<RefineryWorkspaceModel>(loadInitialRefineryModel);
  const [experimentPlan, setExperimentPlanState] = useState<RefineryExperimentDraft[]>([]);
  const [preflight, setPreflight] = useState<RefineryPreflightResponse | null>(null);
  const [analysis, setAnalysis] = useState<RefineryAnalyzeResponse | null>(null);
  const [busy, setBusy] = useState<"preflight" | "analyze" | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const activeController = useRef<AbortController | null>(null);
  const requestVersion = useRef(0);
  const resultsRef = useRef<HTMLDivElement>(null);
  const validationRef = useRef<HTMLDivElement>(null);
  const issues = useMemo(
    () => [...validateRefineryModel(model), ...validateRefineryExperimentPlan(model, experimentPlan)],
    [model, experimentPlan],
  );
  const activeRows = useMemo(() => model.symbols.filter((row) => row.symbol.trim()), [model.symbols]);
  const baselineSymbols = useMemo(
    () => activeRows.map((row) => normalizeRefinerySymbol(row.symbol)).filter(Boolean),
    [activeRows],
  );
  const weightTotal = useMemo(() => refineryWeightTotal(model), [model]);

  function invalidateActiveRequest() {
    requestVersion.current += 1;
    activeController.current?.abort();
    activeController.current = null;
    setBusy(null);
  }

  function invalidateEvidence() {
    invalidateActiveRequest();
    setPreflight(null);
    setAnalysis(null);
    setMessage("");
    setError("");
  }

  function setModel(updater: (current: RefineryWorkspaceModel) => RefineryWorkspaceModel) {
    setModelState((current) => updater(current));
    invalidateEvidence();
  }

  function setExperimentPlan(plan: RefineryExperimentDraft[]) {
    setExperimentPlanState(plan);
    invalidateEvidence();
  }

  function replaceModel(next: RefineryWorkspaceModel) {
    setModelState(next);
    setExperimentPlanState([]);
    invalidateEvidence();
  }

  useEffect(() => {
    try {
      window.localStorage.setItem(REFINERY_WORKSPACE_STORAGE_KEY, JSON.stringify(model));
    } catch {
      // Local persistence is best-effort; the workspace stays usable without storage.
    }
  }, [model]);

  useEffect(() => () => {
    requestVersion.current += 1;
    activeController.current?.abort();
    activeController.current = null;
  }, []);

  async function execute(kind: "preflight" | "analyze") {
    if (issues.length > 0) {
      setError("請先修正持股、期間或權重設定。 ");
      validationRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    if (kind === "analyze" && !preflight?.eligibility.analysis_ready) {
      setError("請先完成可分析的資料預檢，再執行正式診斷。 ");
      return;
    }

    activeController.current?.abort();
    const controller = new AbortController();
    const version = ++requestVersion.current;
    activeController.current = controller;
    setBusy(kind);
    setError("");
    setMessage(kind === "preflight" ? "正在建立可重現 ResearchDataset 預檢…" : "正在計算風險結構診斷…");
    try {
      const request = toRefineryApiRequest(model, experimentPlan);
      if (kind === "preflight") {
        const result = await runRefineryPreflight(request, controller.signal);
        if (requestVersion.current !== version) return;
        setPreflight(result);
        setAnalysis(null);
        setMessage(statusExplanation(result.status));
      } else {
        const result = await runRefineryAnalyze(request, controller.signal);
        if (requestVersion.current !== version) return;
        setAnalysis(result);
        setMessage(result.status === "ok" ? "Refinery 風險診斷完成。" : statusExplanation(result.status));
        window.setTimeout(() => {
          if (requestVersion.current === version) {
            resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        }, 0);
      }
    } catch (requestError) {
      if (requestVersion.current !== version) return;
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError(errorText(requestError));
      setMessage("");
    } finally {
      if (activeController.current === controller) {
        activeController.current = null;
        setBusy(null);
      }
    }
  }

  function cancelRequest() {
    invalidateActiveRequest();
    setMessage("已取消目前 Refinery 請求。 ");
  }

  return (
    <div className="refinery-workspace" data-testid="refinery-workspace">
      <section className="model-summary refinery-hero" aria-labelledby="refinery-workspace-title">
        <div>
          <p className="eyebrow">Portfolio Refinery · Read-only diagnosis</p>
          <h2 id="refinery-workspace-title">持股精煉診斷</h2>
          <p>把 Phase 1 可重現資料與 Phase 2 風險數學轉成可讀結構診斷；本階段不提供冗餘判定、選股、TRIM/REPLACE 或權重最佳化。</p>
        </div>
        <div className="refinery-hero-actions">
          <button type="button" className="secondary-button" onClick={() => replaceModel(createExampleRefineryModel())}>載入範例</button>
          <button type="button" className="ghost-button" onClick={() => replaceModel(createDefaultRefineryModel())}>重設</button>
          <span className="autosave-indicator">此工作區自動儲存在此瀏覽器</span>
        </div>
      </section>

      <section className="workspace-card" aria-labelledby="refinery-input-title">
        <div className="section-heading">
          <div><span className="section-index">1</span><div><h2 id="refinery-input-title">候選持股與研究期間</h2><p>2–100 檔；只輸入要診斷的 candidate，不會自動加入 benchmark。</p></div></div>
          <span className="summary-chip">{activeRows.length} / {MAX_REFINERY_CANDIDATES} 檔</span>
        </div>

        <div className="refinery-candidate-desktop table-scroll" tabIndex={0} role="region" aria-label="Refinery 候選持股編輯器">
          <table className="data-table refinery-candidate-table">
            <thead><tr><th>#</th><th>代碼</th>{model.useWeights && <th>權重 %</th>}<th aria-label="刪除" /></tr></thead>
            <tbody>
              {model.symbols.map((row, index) => (
                <tr key={row.id}>
                  <th scope="row">{index + 1}</th>
                  <td><input aria-label={`Refinery 持股 ${index + 1} 代碼`} value={row.symbol} placeholder="AAPL / 2330" onChange={(event) => setModel((current) => ({ ...current, symbols: current.symbols.map((item) => item.id === row.id ? { ...item, symbol: event.target.value.toUpperCase() } : item) }))} /></td>
                  {model.useWeights && <td><input aria-label={`Refinery 持股 ${index + 1} 權重`} type="number" min="0" max="100" step="0.01" value={row.weightPercent ?? ""} placeholder="0.00" onChange={(event) => setModel((current) => ({ ...current, symbols: current.symbols.map((item) => item.id === row.id ? { ...item, weightPercent: event.target.value === "" ? null : Number(event.target.value) } : item) }))} /></td>}
                  <td><button type="button" className="icon-button danger" aria-label={`刪除 Refinery 持股 ${index + 1}`} disabled={model.symbols.length <= 2} onClick={() => setModel((current) => removeRefineryAsset(current, row.id))}>×</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="refinery-candidate-mobile" aria-label="Refinery 候選持股手機編輯器">
          {model.symbols.map((row, index) => (
            <article className="refinery-candidate-mobile-row" key={row.id}>
              <div className="mobile-row-heading"><strong>持股 {index + 1}</strong><button type="button" className="icon-button danger" aria-label={`手機刪除 Refinery 持股 ${index + 1}`} disabled={model.symbols.length <= 2} onClick={() => setModel((current) => removeRefineryAsset(current, row.id))}>×</button></div>
              <label><span>代碼</span><input aria-label={`手機 Refinery 持股 ${index + 1} 代碼`} value={row.symbol} placeholder="AAPL / 2330" onChange={(event) => setModel((current) => ({ ...current, symbols: current.symbols.map((item) => item.id === row.id ? { ...item, symbol: event.target.value.toUpperCase() } : item) }))} /></label>
              {model.useWeights && <label><span>權重 %</span><input aria-label={`手機 Refinery 持股 ${index + 1} 權重`} type="number" min="0" max="100" step="0.01" value={row.weightPercent ?? ""} onChange={(event) => setModel((current) => ({ ...current, symbols: current.symbols.map((item) => item.id === row.id ? { ...item, weightPercent: event.target.value === "" ? null : Number(event.target.value) } : item) }))} /></label>}
            </article>
          ))}
        </div>

        <div className="inline-actions refinery-candidate-actions">
          <button type="button" className="secondary-button" disabled={model.symbols.length >= MAX_REFINERY_CANDIDATES} onClick={() => setModel(addRefineryAsset)}>＋ 新增持股</button>
          <label className="toggle-row"><input type="checkbox" checked={model.useWeights} onChange={(event) => setModel((current) => ({ ...current, useWeights: event.target.checked }))} /><span>提供目前資本權重</span></label>
          {model.useWeights && <span className={Math.abs(weightTotal - 100) <= 0.05 ? "weight-total valid" : "weight-total invalid"}>合計 {weightTotal.toFixed(2)}%</span>}
        </div>

        <div className="settings-grid refinery-settings-grid">
          <label><span>開始日期</span><input type="date" value={model.startDate} onChange={(event) => setModel((current) => ({ ...current, startDate: event.target.value }))} /></label>
          <label><span>結束日期</span><input type="date" value={model.endDate} onChange={(event) => setModel((current) => ({ ...current, endDate: event.target.value }))} /></label>
          <label><span>Benchmark（選填）</span><input value={model.benchmark} placeholder="例如 SPY" onChange={(event) => setModel((current) => ({ ...current, benchmark: event.target.value.toUpperCase() }))} /></label>
          <label><span>EWMA decay</span><input type="number" min="0.01" max="0.999" step="0.01" value={model.ewmaDecay} onChange={(event) => setModel((current) => ({ ...current, ewmaDecay: Number(event.target.value) }))} /></label>
          <label><span>Stress quantile</span><input type="number" min="0.05" max="0.25" step="0.01" value={model.stressQuantile} onChange={(event) => setModel((current) => ({ ...current, stressQuantile: Number(event.target.value) }))} /></label>
        </div>
        <p className="workspace-hint">Benchmark 為空時，下跌日／壓力相關會明確顯示 unavailable；系統不會自動假設 SPY。未啟用權重時，也不會偷偷改成等權。</p>
      </section>

      <RefineryExperimentPlanEditor
        baselineSymbols={baselineSymbols}
        plan={experimentPlan}
        onChange={setExperimentPlan}
      />

      <section className="workspace-card" aria-labelledby="refinery-preflight-action-title">
        <div className="section-heading"><div><span className="section-index">3</span><div><h2 id="refinery-preflight-action-title">資料預檢與正式診斷</h2><p>先確認 membership、coverage 與共同樣本，再決定是否執行 read-only analysis。</p></div></div></div>
        <div ref={validationRef} className="validation-box" aria-live="polite">
          {issues.length === 0 ? <div className="notice success"><strong>本機設定可送出</strong><p>API 仍會再次執行完整驗證與資料完整性 gate。</p></div> : <div className="notice warning"><strong>尚有 {issues.length} 項設定需要修正</strong><ul>{issues.map((issue, index) => <li key={`${issue.field}-${index}`}>{issue.message}</li>)}</ul></div>}
        </div>
        <div className="refinery-action-row">
          <button type="button" className="secondary-button" disabled={busy !== null || issues.length > 0} onClick={() => void execute("preflight")}>資料預檢</button>
          <button type="button" className="primary-button" disabled={busy !== null || issues.length > 0 || !preflight?.eligibility.analysis_ready} onClick={() => void execute("analyze")}>執行風險診斷</button>
          {busy && <button type="button" className="ghost-button" onClick={cancelRequest}>取消</button>}
        </div>
        {preflight && <p className="workspace-hint">預檢狀態：<strong>{preflight.status}</strong> · {statusExplanation(preflight.status)}</p>}
      </section>

      {preflight && <RefineryPreflightCard response={preflight} />}
      {preflight && <RefineryPhase6Preflight marginal={preflight.marginal_experiments} />}
      <div ref={resultsRef} className="refinery-results-shell">{analysis && <RefineryResults response={analysis} />}</div>

      <div className="run-bar refinery-run-bar" aria-live="polite">
        <div><strong>{busy ? (busy === "preflight" ? "正在預檢…" : "正在診斷…") : "Refinery read-only"}</strong><span>{error || message || "先預檢資料，再執行風險結構診斷。"}</span></div>
        <div className="run-actions">
          <button type="button" disabled={busy !== null || issues.length > 0} onClick={() => void execute("preflight")}>預檢</button>
          <button type="button" disabled={busy !== null || issues.length > 0 || !preflight?.eligibility.analysis_ready} onClick={() => void execute("analyze")}>診斷</button>
          {busy && <button type="button" onClick={cancelRequest}>取消</button>}
        </div>
      </div>
    </div>
  );
}
