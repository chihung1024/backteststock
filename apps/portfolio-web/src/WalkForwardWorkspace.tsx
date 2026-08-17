import { useEffect, useMemo, useRef, useState } from "react";
import { WalkForwardApiError, checkWalkForwardHealth, runWalkForward } from "./walkForwardApi";
import {
  MAX_WALK_FORWARD_PERIODS,
  WALK_FORWARD_WORKSPACE_STORAGE_KEY,
  createBlankWalkForwardPeriod,
  createDefaultWalkForwardModel,
  createDualMomentumMonthlyPeriods,
  createDualMomentumWalkForwardModel,
  createExampleWalkForwardModel,
  latestCompleteUtcDate,
  migrateWalkForwardModel,
  parseWalkForwardSymbols,
  toWalkForwardApiRequest,
  validateWalkForwardModel,
} from "./walkForwardModel";
import { ResearchLibraryPanel } from "./ResearchLibraryPanel";
import { WalkForwardResults } from "./WalkForwardResults";
import type {
  WalkForwardAllocationMethod,
  WalkForwardPeriodDraft,
  WalkForwardResultResponse,
  WalkForwardStrategy,
  WalkForwardWorkspaceModel,
} from "./walkForwardTypes";

type PeriodField = Exclude<keyof WalkForwardPeriodDraft, "id">;
type ServiceState = "checking" | "online" | "offline";

function loadInitialModel(): WalkForwardWorkspaceModel {
  try {
    const saved = window.localStorage.getItem(WALK_FORWARD_WORKSPACE_STORAGE_KEY);
    return saved ? migrateWalkForwardModel(JSON.parse(saved) as unknown) : createDefaultWalkForwardModel();
  } catch {
    return createDefaultWalkForwardModel();
  }
}

function numericValue(value: string, fallback: number): number {
  if (!value.trim()) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function shortHash(value: string): string {
  return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;
}

function executionErrorText(error: unknown): string {
  if (error instanceof WalkForwardApiError) {
    if (error.status === 429) {
      return "研究執行頻率已達後端上限（每分鐘最多 2 次）。請約一分鐘後再執行；不要連續重送相同研究。";
    }
    if (error.status === 422) {
      return `設定、日期因果、訊號歷史或研究容量未通過後端驗證：${error.message}`;
    }
    if (error.status === 409) {
      return `指定 Decision 日期所需的歷史研究證據不可用或不符合因果要求：${error.message}`;
    }
    if (error.status === 502) {
      return `研究所需的 PIT、行情或後端研究 authority 暫時無法完成：${error.message}`;
    }
    return `Walk-Forward API 執行失敗（HTTP ${error.status}）：${error.message}`;
  }
  if (error instanceof Error) return error.message;
  return "Walk-Forward 研究發生未知錯誤。";
}

function PeriodEditor({
  period,
  index,
  strategy,
  canRemove,
  disabled,
  onChange,
  onRemove,
}: {
  period: WalkForwardPeriodDraft;
  index: number;
  strategy: WalkForwardStrategy;
  canRemove: boolean;
  disabled: boolean;
  onChange: (field: PeriodField, value: string) => void;
  onRemove: () => void;
}) {
  const labelPrefix = `Period ${index + 1}`;
  return (
    <article className="wf-period-card">
      <div className="wf-period-header">
        <div>
          <span className="wf-period-number">{String(index + 1).padStart(2, "0")}</span>
          <div>
            <h3>{labelPrefix}</h3>
            <p>{strategy === "dual_momentum"
              ? "只用 Training 內的 TWD total-return level 形成 Momentum 決策；Decision 凍結後才讀取 Evaluation。"
              : "先用 Training 與當時 PIT Universe 形成決策，再進入未參與選股的 Evaluation。"}</p>
          </div>
        </div>
        <button type="button" className="secondary danger-text" disabled={disabled || !canRemove} onClick={onRemove}>移除</button>
      </div>

      <label className="field wf-period-id">
        <span>Period 名稱</span>
        <input
          aria-label={`${labelPrefix} 名稱`}
          value={period.periodId}
          maxLength={80}
          disabled={disabled}
          onChange={(event) => onChange("periodId", event.target.value)}
        />
      </label>

      <div className="wf-timeline" aria-label={`${labelPrefix} 因果時間線`}>
        <div className="training"><strong>Training</strong><span>{period.trainingStart || "—"} → {period.trainingEnd || "—"}</span></div>
        <i aria-hidden="true">→</i>
        <div className="decision"><strong>Decision</strong><span>{period.decisionDate || "—"}</span></div>
        <i aria-hidden="true">→</i>
        <div className="evaluation"><strong>Evaluation / OOS</strong><span>{period.evaluationStart || "—"} → {period.evaluationEnd || "—"}</span></div>
      </div>

      <div className="wf-date-grid">
        <label className="field">
          <span>Training 起始日</span>
          <input type="date" disabled={disabled} aria-label={`${labelPrefix} Training 起始日`} value={period.trainingStart} onChange={(event) => onChange("trainingStart", event.target.value)} />
        </label>
        <label className="field">
          <span>Training 結束日</span>
          <input type="date" disabled={disabled} aria-label={`${labelPrefix} Training 結束日`} value={period.trainingEnd} onChange={(event) => onChange("trainingEnd", event.target.value)} />
        </label>
        <label className="field">
          <span>Decision 日期</span>
          <input type="date" disabled={disabled} aria-label={`${labelPrefix} Decision 日期`} value={period.decisionDate} onChange={(event) => onChange("decisionDate", event.target.value)} />
        </label>
        <label className="field">
          <span>Evaluation 起始日</span>
          <input type="date" disabled={disabled} aria-label={`${labelPrefix} Evaluation 起始日`} value={period.evaluationStart} onChange={(event) => onChange("evaluationStart", event.target.value)} />
        </label>
        <label className="field">
          <span>Evaluation 結束日</span>
          <input type="date" disabled={disabled} aria-label={`${labelPrefix} Evaluation 結束日`} value={period.evaluationEnd} max={latestCompleteUtcDate()} onChange={(event) => onChange("evaluationEnd", event.target.value)} />
        </label>
      </div>
    </article>
  );
}

export function WalkForwardWorkspace({ onBusyChange }: { onBusyChange?: (busy: boolean) => void }) {
  const [model, setModelState] = useState<WalkForwardWorkspaceModel>(loadInitialModel);
  const [serviceState, setServiceState] = useState<ServiceState>("checking");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [libraryBusy, setLibraryBusy] = useState(false);
  const [result, setResult] = useState<WalkForwardResultResponse | null>(null);
  const validationRef = useRef<HTMLDivElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const activeController = useRef<AbortController | null>(null);
  const requestVersion = useRef(0);
  const issues = useMemo(() => validateWalkForwardModel(model), [model]);
  const request = useMemo(() => issues.length === 0 ? toWalkForwardApiRequest(model) : null, [issues.length, model]);
  const requestPreview = useMemo(() => request ? JSON.stringify(request, null, 2) : "", [request]);
  const latestComplete = latestCompleteUtcDate();
  const workspaceBusy = busy || libraryBusy;
  const riskyCount = useMemo(() => parseWalkForwardSymbols(model.riskySymbolsText).length, [model.riskySymbolsText]);
  const defensiveCount = useMemo(() => parseWalkForwardSymbols(model.defensiveSymbolsText).length, [model.defensiveSymbolsText]);

  useEffect(() => {
    try {
      window.localStorage.setItem(WALK_FORWARD_WORKSPACE_STORAGE_KEY, JSON.stringify(model));
    } catch {
      // Browser persistence is best effort. The workspace remains usable without it.
    }
  }, [model]);

  useEffect(() => {
    const controller = new AbortController();
    checkWalkForwardHealth(controller.signal)
      .then((health) => setServiceState(health.status === "ok" ? "online" : "offline"))
      .catch(() => setServiceState("offline"));
    return () => controller.abort();
  }, []);

  useEffect(() => () => activeController.current?.abort(), []);

  useEffect(() => {
    onBusyChange?.(workspaceBusy);
  }, [onBusyChange, workspaceBusy]);

  useEffect(() => () => onBusyChange?.(false), [onBusyChange]);

  function invalidateExecution() {
    requestVersion.current += 1;
    activeController.current?.abort();
    activeController.current = null;
    setBusy(false);
    setResult(null);
    setError("");
  }

  function mutateModel(updater: (current: WalkForwardWorkspaceModel) => WalkForwardWorkspaceModel) {
    invalidateExecution();
    setMessage("");
    setModelState((current) => updater(current));
  }

  function replaceModel(next: WalkForwardWorkspaceModel, nextMessage: string) {
    invalidateExecution();
    setModelState(next);
    setMessage(nextMessage);
  }

  function updatePeriod(id: string, field: PeriodField, value: string) {
    mutateModel((current) => ({
      ...current,
      periods: current.periods.map((period) => period.id === id ? { ...period, [field]: value } : period),
    }));
  }

  function removePeriod(id: string) {
    mutateModel((current) => ({ ...current, periods: current.periods.filter((period) => period.id !== id) }));
  }

  function addPeriod() {
    mutateModel((current) => {
      if (current.periods.length >= MAX_WALK_FORWARD_PERIODS) return current;
      return {
        ...current,
        periods: [...current.periods, createBlankWalkForwardPeriod(current.periods.length)],
      };
    });
    setMessage("已新增空白 Period；請依因果順序填入日期。 ");
  }

  function regenerateDualMomentumPeriods() {
    mutateModel((current) => ({
      ...current,
      periods: createDualMomentumMonthlyPeriods(current.lookbackMonths),
    }));
    setMessage("已依目前 Lookback 重新產生最近 6 個月的月度 Decision / OOS 區間。 ");
  }

  async function copyRequest() {
    if (!request) {
      validationRef.current?.focus();
      setMessage("設定尚未通過驗證，暫不產生 API Request。 ");
      return;
    }
    try {
      await navigator.clipboard.writeText(requestPreview);
      setMessage("已複製標準化 Walk-Forward API Request。 ");
    } catch {
      setMessage("瀏覽器未允許剪貼簿存取，可直接從 Request 預覽複製。 ");
    }
  }

  async function executeResearch() {
    if (!request) {
      validationRef.current?.focus();
      setError("設定尚未通過瀏覽器因果檢查，無法送出研究。 ");
      return;
    }

    activeController.current?.abort();
    const controller = new AbortController();
    const version = ++requestVersion.current;
    activeController.current = controller;
    setBusy(true);
    setResult(null);
    setError("");
    setMessage("正在同步執行 Training → frozen Decision → Evaluation → continuous OOS ledger。後端會重新驗證全部因果與資料條件，請勿重複送出。 ");

    try {
      const response = await runWalkForward(request, controller.signal);
      if (version !== requestVersion.current) return;
      setResult(response);
      setMessage(`Walk-Forward 研究完成：${response.decisions.length} 個 Decision，job ${shortHash(response.jobHash)}。`);
      window.requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (caught) {
      if (version !== requestVersion.current) return;
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(executionErrorText(caught));
      setMessage("");
    } finally {
      if (version === requestVersion.current && activeController.current === controller) {
        activeController.current = null;
        setBusy(false);
      }
    }
  }

  function cancelResearch() {
    requestVersion.current += 1;
    activeController.current?.abort();
    activeController.current = null;
    setBusy(false);
    setMessage("已取消目前的 Walk-Forward 請求；未完成的結果不會保留。 ");
  }

  function setResearchLibraryBusy(nextBusy: boolean) {
    setLibraryBusy(nextBusy);
    if (!nextBusy) return;
    requestVersion.current += 1;
    activeController.current?.abort();
    activeController.current = null;
    setBusy(false);
    setResult(null);
    setError("");
    setMessage("");
  }

  function showResearchLibraryResult(nextResult: WalkForwardResultResponse, nextMessage: string) {
    setResult(nextResult);
    setError("");
    setMessage(nextMessage);
    window.requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  return (
    <div className="walk-forward-workspace">
      <section className="wf-hero">
        <div>
          <p className="eyebrow">TRAINING → FROZEN DECISION → OUT-OF-SAMPLE</p>
          <h1>Walk-Forward 研究工作區</h1>
          <p>每一期只使用 Decision 當時允許的研究輸入與 Training 證據形成選擇；決策凍結後才讀取 Evaluation / OOS。Optimizer Hub 沿用同一 Walk-Forward、Portfolio v3、metrics 與 ResearchRun authority，不建立第二套回測器。</p>
        </div>
        <div className="wf-hero-actions">
          <button type="button" className="secondary" disabled={workspaceBusy} onClick={() => replaceModel(createExampleWalkForwardModel(), "已載入單期 PIT / Exhaustive 因果範例。 ")}>載入單期範例</button>
          <button type="button" className="secondary" disabled={workspaceBusy} onClick={() => replaceModel(createDualMomentumWalkForwardModel(), "已載入 Dual Momentum 月度 Walk-Forward 範例。 ")}>載入 Dual Momentum 範例</button>
          <button type="button" className="secondary danger-text" disabled={workspaceBusy} onClick={() => replaceModel(createDefaultWalkForwardModel(), "已重設 Walk-Forward 設定。 ")}>重設</button>
        </div>
      </section>

      <section className="model-summary" aria-label="Walk-Forward 設定摘要">
        <span className={`wf-service-state ${serviceState}`}><i />{serviceState === "online" ? "Walk-Forward API 正常" : serviceState === "checking" ? "檢查 Walk-Forward API" : "Walk-Forward API 離線"}</span>
        <span><strong>{model.periods.length}</strong> 個 Period</span>
        {model.strategy === "dual_momentum" ? (
          <>
            <span>Strategy <strong>Dual Momentum</strong></span>
            <span>Risky <strong>{riskyCount}</strong> · Defensive <strong>{defensiveCount}</strong></span>
            <span>Top K <strong>{model.topK}</strong></span>
            <span>Allocation <strong>{model.allocationMethod === "equal" ? "Equal" : model.allocationMethod === "inverse_volatility" ? "Inverse Vol" : "Risk Parity / ERC"}</strong></span>
          </>
        ) : (
          <>
            <span>Universe <strong>{model.universe || "—"}</strong></span>
            <span>持股 <strong>{model.holdingCount}</strong> 檔</span>
          </>
        )}
        <span>最後完整 UTC 日 <strong>{latestComplete}</strong></span>
        <span>{issues.length === 0 ? "因果設定有效" : `${issues.length} 項需修正`}</span>
      </section>

      {issues.length > 0 && (
        <div className="validation-summary" role="alert" tabIndex={-1} ref={validationRef}>
          <strong>Walk-Forward 設定檢查</strong>
          <ul>{issues.map((issue, index) => <li key={`${issue.field}-${index}`}>{issue.message}</li>)}</ul>
        </div>
      )}
      {error && <div className="notice error" role="alert"><strong>研究無法完成</strong><p>{error}</p></div>}
      {message && <div className="notice info" aria-live="polite"><p>{message}</p></div>}

      <section className="workspace-card" aria-labelledby="wf-research-settings-title">
        <div className="section-heading">
          <div>
            <span className="section-index">1</span>
            <div>
              <h2 id="wf-research-settings-title">研究策略與執行假設</h2>
              <p>策略設定只形成後端 request；Selection、訊號、OOS ledger 與績效仍由版本化 authority 計算。</p>
            </div>
          </div>
        </div>
        <div className="wf-settings-grid">
          <label className="field">
            <span>Strategy</span>
            <select
              aria-label="Walk-Forward Strategy"
              value={model.strategy}
              disabled={workspaceBusy}
              onChange={(event) => mutateModel((current) => ({ ...current, strategy: event.target.value as WalkForwardStrategy }))}
            >
              <option value="exhaustive">PIT + Exhaustive</option>
              <option value="dual_momentum">Dual Momentum</option>
            </select>
            <small>策略切換不改寫已輸入日期；後端會依 selector contract 重新驗證。</small>
          </label>

          {model.strategy === "exhaustive" ? (
            <>
              <label className="field">
                <span>Universe</span>
                <input
                  list="walk-forward-universes"
                  aria-label="Walk-Forward Universe"
                  value={model.universe}
                  placeholder="sp500"
                  disabled={workspaceBusy}
                  onChange={(event) => mutateModel((current) => ({ ...current, universe: event.target.value.toLowerCase() }))}
                />
                <small>輸入 D1 Universe ID；不會自動改用今天的成分股。若 PIT candidates 超過 100，後端會明確拒絕而不截斷。</small>
              </label>
              <datalist id="walk-forward-universes">
                <option value="sp500" />
                <option value="nasdaq100" />
                <option value="soxx" />
                <option value="russell2000" />
              </datalist>
              <label className="field">
                <span>Benchmark</span>
                <input aria-label="Walk-Forward Benchmark" value={model.benchmark} maxLength={20} disabled={workspaceBusy} onChange={(event) => mutateModel((current) => ({ ...current, benchmark: event.target.value.toUpperCase() }))} />
                <small>用於 Training 排名與 OOS 比較的 canonical symbol。</small>
              </label>
              <label className="field">
                <span>持股檔數</span>
                <input type="number" aria-label="Walk-Forward 持股檔數" min={1} max={20} step={1} value={model.holdingCount} disabled={workspaceBusy} onChange={(event) => mutateModel((current) => ({ ...current, holdingCount: numericValue(event.target.value, 0) }))} />
                <small>Public v1 支援 1–20 檔，採等權選股。</small>
              </label>
            </>
          ) : (
            <>
              <label className="field">
                <span>風險資產</span>
                <input aria-label="Dual Momentum 風險資產" value={model.riskySymbolsText} disabled={workspaceBusy} onChange={(event) => mutateModel((current) => ({ ...current, riskySymbolsText: event.target.value }))} />
                <small>以逗號或空白分隔。所有標的都會 hash-bound 到 configured request provenance。</small>
              </label>
              <label className="field">
                <span>防禦資產</span>
                <input aria-label="Dual Momentum 防禦資產" value={model.defensiveSymbolsText} disabled={workspaceBusy} onChange={(event) => mutateModel((current) => ({ ...current, defensiveSymbolsText: event.target.value }))} />
                <small>風險資產全部未通過 absolute hurdle 時，才從此集合依 relative momentum 選取。</small>
              </label>
              <label className="field">
                <span>Momentum Lookback</span>
                <div className="input-with-suffix">
                  <input type="number" aria-label="Dual Momentum Lookback 月數" min={1} max={60} step={1} value={model.lookbackMonths} disabled={workspaceBusy} onChange={(event) => mutateModel((current) => ({ ...current, lookbackMonths: numericValue(event.target.value, 0) }))} />
                  <span>月</span>
                </div>
                <small>Server 使用 audited TWD adjusted total-return levels；不由瀏覽器自行算績效。</small>
              </label>
              <label className="field">
                <span>Top K</span>
                <input type="number" aria-label="Dual Momentum Top K" min={1} max={Math.max(1, riskyCount)} step={1} value={model.topK} disabled={workspaceBusy} onChange={(event) => mutateModel((current) => ({ ...current, topK: numericValue(event.target.value, 0) }))} />
                <small>先通過 absolute filter，再按 relative momentum 排名前 K；Allocation 只對 frozen selection 決定權重。</small>
              </label>
              <label className="field">
                <span>Allocation / Weighting</span>
                <select
                  aria-label="Dual Momentum Allocation Method"
                  value={model.allocationMethod}
                  disabled={workspaceBusy}
                  onChange={(event) => mutateModel((current) => ({ ...current, allocationMethod: event.target.value as WalkForwardAllocationMethod }))}
                >
                  <option value="equal">Equal Weight</option>
                  <option value="inverse_volatility">Inverse Volatility</option>
                  <option value="risk_parity_erc">Risk Parity / ERC</option>
                </select>
                <small>Risk-based allocation 只讀 Training 的 TWD daily returns，需至少 60 個完整共同觀察值；Ledoit-Wolf covariance 與 ERC risk contribution 均由後端 Risk Mathematics authority 計算。</small>
              </label>
              <label className="field">
                <span>Absolute Threshold</span>
                <div className="input-with-suffix">
                  <input type="number" aria-label="Dual Momentum Absolute Threshold" step={0.1} value={model.absoluteThresholdPct} disabled={workspaceBusy} onChange={(event) => mutateModel((current) => ({ ...current, absoluteThresholdPct: numericValue(event.target.value, 0) }))} />
                  <span>%</span>
                </div>
                <small>0% 代表正報酬 hurdle；正式 cash / trend hurdle 留給後續版本化擴充。</small>
              </label>
            </>
          )}

          <label className="field">
            <span>初始資金</span>
            <div className="input-with-suffix">
              <input type="number" aria-label="Walk-Forward 初始資金" min={1} step={1000} value={model.initialAmountTwd} disabled={workspaceBusy} onChange={(event) => mutateModel((current) => ({ ...current, initialAmountTwd: numericValue(event.target.value, 0) }))} />
              <span>TWD</span>
            </div>
            <small>連續 OOS ledger 的起始權益。</small>
          </label>
          <label className="field">
            <span>Decision 換倉成本</span>
            <div className="input-with-suffix">
              <input type="number" aria-label="Walk-Forward 換倉成本" min={0} max={1000} step={1} value={model.transitionCostBps} disabled={workspaceBusy} onChange={(event) => mutateModel((current) => ({ ...current, transitionCostBps: numericValue(event.target.value, 0) }))} />
              <span>bps</span>
            </div>
            <small>只在下一個凍結 Decision 改變持股時由 Portfolio v3 ledger 計入。</small>
          </label>
        </div>
      </section>

      <section className="workspace-card" aria-labelledby="wf-periods-title">
        <div className="section-heading">
          <div>
            <span className="section-index">2</span>
            <div>
              <h2 id="wf-periods-title">Training / Decision / Evaluation</h2>
              <p>{model.strategy === "dual_momentum"
                ? "Dual Momentum v1 採月度 Decision。Training 必須涵蓋完整 Lookback；每期 frozen Decision 只影響之後的 OOS 月度區間。"
                : "Period 按輸入順序執行。Decision 必須遞增，Evaluation 不得重疊，Evaluation 起始日必須嚴格晚於 Decision。"}</p>
            </div>
          </div>
          <div className="section-actions">
            {model.strategy === "dual_momentum" && (
              <button type="button" className="secondary" disabled={workspaceBusy || !Number.isInteger(model.lookbackMonths) || model.lookbackMonths < 1 || model.lookbackMonths > 60} onClick={regenerateDualMomentumPeriods}>產生最近 6 個月</button>
            )}
            <button type="button" className="secondary" disabled={workspaceBusy || model.periods.length >= MAX_WALK_FORWARD_PERIODS} onClick={addPeriod}>新增 Period</button>
          </div>
        </div>
        <div className={workspaceBusy ? "wf-period-list busy" : "wf-period-list"}>
          {model.periods.map((period, index) => (
            <PeriodEditor
              key={period.id}
              period={period}
              index={index}
              strategy={model.strategy}
              canRemove={model.periods.length > 1}
              disabled={workspaceBusy}
              onChange={(field, value) => updatePeriod(period.id, field, value)}
              onRemove={() => removePeriod(period.id)}
            />
          ))}
        </div>
      </section>

      <section className="workspace-card" aria-labelledby="wf-request-title">
        <div className="section-heading">
          <div>
            <span className="section-index">3</span>
            <div>
              <h2 id="wf-request-title">因果檢查與 API Request</h2>
              <p>瀏覽器只提供提前驗證與透明預覽；後端仍會重新執行日期、資料完整性、selector contract 與因果 fail-closed 驗證。</p>
            </div>
          </div>
          <div className="section-actions">
            <button type="button" className="secondary" disabled={workspaceBusy || !request} onClick={() => void copyRequest()}>複製 Request</button>
          </div>
        </div>
        {request ? (
          <>
            <div className="notice info"><strong>瀏覽器因果檢查通過</strong><p>{model.strategy === "dual_momentum"
              ? "這代表 configured universe、Momentum / Allocation 參數與月度日期結構可送出；Training history、signal boundary、risk allocation evidence 與 OOS execution 仍以後端實際證據為準。"
              : "這代表 request 結構可送出；PIT membership、候選數、行情與 Exhaustive capacity 仍以後端實際證據為準。"}</p></div>
            <details className="wf-request-preview">
              <summary>查看標準化 API Request</summary>
              <pre>{requestPreview}</pre>
            </details>
          </>
        ) : (
          <div className="empty-state">修正上方設定後，這裡會產生對應的 Walk-Forward API Request。</div>
        )}
      </section>

      <section className="workspace-card wf-run-card" aria-labelledby="wf-run-title">
        <div className="section-heading">
          <div>
            <span className="section-index">4</span>
            <div>
              <h2 id="wf-run-title">執行 Walk-Forward</h2>
              <p>這是 request-scoped 同步研究，不是背景工作。後端依序完成 Training → frozen Decision → Evaluation → continuous OOS。</p>
            </div>
          </div>
          <div className="section-actions wf-run-actions">
            {busy && <button type="button" className="secondary" onClick={cancelResearch}>取消</button>}
            <button type="button" className="primary" disabled={workspaceBusy || !request} onClick={() => void executeResearch()}>{busy ? "研究執行中…" : "執行研究"}</button>
          </div>
        </div>
        <div className="wf-run-guidance">
          <span><strong>請勿重複送出：</strong>正式 API 每分鐘最多 2 次研究 request。</span>
          <span><strong>Fail closed：</strong>{model.strategy === "dual_momentum"
            ? "任一 configured asset 缺少完整 Training signal history、日期不連續或資料證據失敗時會明確拒絕，不會縮短 Lookback。"
            : "歷史 Universe 超過 100 candidates、PIT 證據非 authoritative、資料缺失或組合數超過上限都會明確失敗，不會偷偷截斷。"}</span>
        </div>
        {busy && <div className="wf-progress" role="status" aria-live="polite"><i /><span>後端正在建立可重現的研究證據；完成前不會產生部分績效結論。</span></div>}
      </section>

      <ResearchLibraryPanel
        request={request}
        disabled={workspaceBusy}
        onBusyChange={setResearchLibraryBusy}
        onResult={showResearchLibraryResult}
      />

      <div ref={resultRef}>{result && <WalkForwardResults result={result} />}</div>
    </div>
  );
}
