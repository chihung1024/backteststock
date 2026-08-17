import { useEffect, useMemo, useRef, useState } from "react";
import {
  ResearchRunApiError,
  checkResearchRunHealth,
  createResearchRun,
  getResearchRun,
  isResearchLibraryCapability,
  listResearchRuns,
  rerunResearchRun,
} from "./researchRunApi";
import type { ResearchRunSummary } from "./researchRunTypes";
import type { WalkForwardApiRequest, WalkForwardResultResponse } from "./walkForwardTypes";

export const RESEARCH_LIBRARY_CAPABILITY_STORAGE_KEY = "backteststock.research-library.capability.v1";

type LibraryAction = "save" | "load" | "rerun" | "connect" | "refresh" | null;
type LibraryHealth = "checking" | "online" | "offline";

function readStoredCapability(): string | null {
  try {
    const value = window.localStorage.getItem(RESEARCH_LIBRARY_CAPABILITY_STORAGE_KEY)?.trim() || "";
    return isResearchLibraryCapability(value) ? value : null;
  } catch {
    return null;
  }
}

function persistCapability(capability: string | null): void {
  try {
    if (capability) window.localStorage.setItem(RESEARCH_LIBRARY_CAPABILITY_STORAGE_KEY, capability);
    else window.localStorage.removeItem(RESEARCH_LIBRARY_CAPABILITY_STORAGE_KEY);
  } catch {
    // Credential persistence is best-effort. D1 remains the durable run authority.
  }
}

function shortHash(value: string): string {
  return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;
}

function libraryErrorText(error: unknown): string {
  if (error instanceof ResearchRunApiError) {
    if (error.status === 401) return "研究庫復原碼無效或已無法使用。請確認復原碼後重新連結。";
    if (error.status === 404) return "此 ResearchRun 不存在於目前研究庫。";
    if (error.status === 413) return `研究結果超過目前可安全保存的大小：${error.message}`;
    if (error.status === 429) return "研究執行頻率已達上限。請等待約一分鐘，並先重新整理研究庫避免重複保存。";
    if (error.status === 409 || error.status === 422) return `Walk-Forward 研究未通過後端因果／容量驗證，因此沒有保存：${error.message}`;
    if (error.status === 502 || error.status === 504) return `Walk-Forward authority 暫時無法完成，因此沒有建立新的 ResearchRun：${error.message}`;
    if (error.status === 503) return `Research Library 暫時無法安全讀寫：${error.message}`;
    return `Research Library API 失敗（HTTP ${error.status}）：${error.message}`;
  }
  if (error instanceof Error) return error.message;
  return "Research Library 發生未知錯誤。";
}

function suggestedRunName(request: WalkForwardApiRequest | null): string {
  if (!request) return "Walk-Forward research";
  const decision = request.periods[0]?.decisionDate || "research";
  return `${request.selector.universe.toUpperCase()} · ${decision}`;
}

function mergeRun(runs: ResearchRunSummary[], next: ResearchRunSummary): ResearchRunSummary[] {
  return [next, ...runs.filter((run) => run.runId !== next.runId)].slice(0, 100);
}

function downloadRecoveryCode(capability: string): void {
  const blob = new Blob([
    "BacktestStock Research Library recovery code\n",
    "Keep this code private. Anyone with it can access this research library.\n\n",
    `${capability}\n`,
  ], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "backteststock-research-library-recovery.txt";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function ResearchLibraryPanel({
  request,
  disabled,
  onBusyChange,
  onResult,
}: {
  request: WalkForwardApiRequest | null;
  disabled: boolean;
  onBusyChange: (busy: boolean) => void;
  onResult: (result: WalkForwardResultResponse, message: string) => void;
}) {
  const [health, setHealth] = useState<LibraryHealth>("checking");
  const [capability, setCapability] = useState<string | null>(readStoredCapability);
  const [candidateCapability, setCandidateCapability] = useState("");
  const [libraryId, setLibraryId] = useState<string | null>(null);
  const [runs, setRuns] = useState<ResearchRunSummary[]>([]);
  const [runName, setRunName] = useState("");
  const [action, setAction] = useState<LibraryAction>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [showCapability, setShowCapability] = useState(false);
  const [newRecoveryCode, setNewRecoveryCode] = useState(false);
  const activeController = useRef<AbortController | null>(null);
  const namePlaceholder = useMemo(() => suggestedRunName(request), [request]);

  useEffect(() => {
    const controller = new AbortController();
    checkResearchRunHealth(controller.signal)
      .then((response) => setHealth(response.status === "ok" && response.schemaReady ? "online" : "offline"))
      .catch(() => setHealth("offline"));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!capability) return;
    const controller = new AbortController();
    setAction("refresh");
    setError("");
    listResearchRuns(capability, controller.signal)
      .then((response) => {
        setLibraryId(response.libraryId);
        setRuns(response.runs);
      })
      .catch((caught) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(libraryErrorText(caught));
      })
      .finally(() => setAction((current) => current === "refresh" ? null : current));
    return () => controller.abort();
  }, [capability]);

  useEffect(() => () => activeController.current?.abort(), []);

  async function runWorkspaceOperation<T>(
    nextAction: Exclude<LibraryAction, "connect" | "refresh" | null>,
    operation: (signal: AbortSignal) => Promise<T>,
  ): Promise<T | null> {
    activeController.current?.abort();
    const controller = new AbortController();
    activeController.current = controller;
    setAction(nextAction);
    setError("");
    setMessage("");
    onBusyChange(true);
    try {
      return await operation(controller.signal);
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(libraryErrorText(caught));
      return null;
    } finally {
      if (activeController.current === controller) activeController.current = null;
      setAction((current) => current === nextAction ? null : current);
      onBusyChange(false);
    }
  }

  async function saveResearch() {
    if (!request || disabled) return;
    const name = runName.trim() || namePlaceholder;
    const response = await runWorkspaceOperation("save", (signal) =>
      createResearchRun(name, request, capability, signal),
    );
    if (!response) return;

    if (response.libraryCapability) {
      persistCapability(response.libraryCapability);
      setCapability(response.libraryCapability);
      setNewRecoveryCode(true);
      setShowCapability(false);
    }
    setLibraryId(response.libraryId);
    setRuns((current) => mergeRun(current, response.run));
    setRunName("");
    setMessage(response.libraryCapability
      ? "研究已完成並保存。這是新研究庫：請立即備份復原碼，遺失後目前沒有帳號可替你找回。"
      : `研究已完成並保存為 ${response.run.name}。`);
    onResult(response.result, `已從 ResearchRun ${shortHash(response.run.runId)} 載入剛完成的 authoritative result。`);
  }

  async function openRun(run: ResearchRunSummary) {
    if (!capability || disabled) return;
    const response = await runWorkspaceOperation("load", (signal) => getResearchRun(run.runId, capability, signal));
    if (!response) return;
    setMessage(`已從 D1 讀取「${response.run.name}」；畫面直接使用保存的 completed result，沒有重新計算。`);
    onResult(response.result, `已載入保存的 ResearchRun ${shortHash(response.run.runId)}。`);
  }

  async function rerun(run: ResearchRunSummary) {
    if (!capability || disabled) return;
    const response = await runWorkspaceOperation("rerun", (signal) => rerunResearchRun(run.runId, capability, signal));
    if (!response) return;
    setRuns((current) => mergeRun(current, response.run));
    setMessage(`已使用 D1 保存的原始 request 重新執行「${response.run.name}」並建立新的 run。`);
    onResult(response.result, `ResearchRun rerun 完成：${shortHash(response.run.runId)}。`);
  }

  async function connectLibrary() {
    const nextCapability = candidateCapability.trim();
    if (!isResearchLibraryCapability(nextCapability)) {
      setError("復原碼格式無效。請貼上完整的 rrl_… 復原碼。 ");
      return;
    }
    const controller = new AbortController();
    activeController.current?.abort();
    activeController.current = controller;
    setAction("connect");
    setError("");
    setMessage("");
    try {
      const response = await listResearchRuns(nextCapability, controller.signal);
      persistCapability(nextCapability);
      setCapability(nextCapability);
      setCandidateCapability("");
      setLibraryId(response.libraryId);
      setRuns(response.runs);
      setNewRecoveryCode(false);
      setShowCapability(false);
      setMessage(`已連結研究庫，共 ${response.runs.length} 筆最近研究。`);
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(libraryErrorText(caught));
    } finally {
      if (activeController.current === controller) activeController.current = null;
      setAction((current) => current === "connect" ? null : current);
    }
  }

  async function refreshLibrary() {
    if (!capability || action) return;
    const controller = new AbortController();
    activeController.current = controller;
    setAction("refresh");
    setError("");
    try {
      const response = await listResearchRuns(capability, controller.signal);
      setLibraryId(response.libraryId);
      setRuns(response.runs);
      setMessage(`研究庫已重新整理，共 ${response.runs.length} 筆最近研究。`);
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(libraryErrorText(caught));
    } finally {
      if (activeController.current === controller) activeController.current = null;
      setAction((current) => current === "refresh" ? null : current);
    }
  }

  function cancelOperation() {
    activeController.current?.abort();
    activeController.current = null;
    setAction(null);
    onBusyChange(false);
    setMessage("已停止瀏覽器等待。伺服器端研究可能仍已完成並保存；請先重新整理研究庫，再決定是否重送。 ");
  }

  function forgetDeviceCredential() {
    activeController.current?.abort();
    activeController.current = null;
    persistCapability(null);
    setCapability(null);
    setLibraryId(null);
    setRuns([]);
    setCandidateCapability("");
    setShowCapability(false);
    setNewRecoveryCode(false);
    setAction(null);
    setError("");
    setMessage("已從此瀏覽器移除研究庫復原碼。D1 中的研究沒有刪除；要重新存取必須再次匯入復原碼。 ");
  }

  async function copyCapability() {
    if (!capability) return;
    try {
      await navigator.clipboard.writeText(capability);
      setMessage("研究庫復原碼已複製。請像密碼一樣保管。 ");
    } catch {
      setError("瀏覽器未允許剪貼簿存取；可按「顯示復原碼」後手動複製。 ");
    }
  }

  const workspaceAction = action === "save" || action === "load" || action === "rerun";

  return (
    <section className="workspace-card research-library-card" aria-labelledby="research-library-title">
      <div className="section-heading">
        <div>
          <span className="section-index">5</span>
          <div>
            <h2 id="research-library-title">Research Library</h2>
            <p>D1 保存 completed ResearchRun；此瀏覽器只保存研究庫復原碼，不把結果或 jobHash 當作 localStorage truth。</p>
          </div>
        </div>
        <span className={`research-library-health ${health}`}><i />{health === "online" ? "Durable memory 正常" : health === "checking" ? "檢查 durable memory" : "Durable memory 不可用"}</span>
      </div>

      {error && <div className="notice error" role="alert"><strong>Research Library 無法完成操作</strong><p>{error}</p></div>}
      {message && <div className="notice info" aria-live="polite"><p>{message}</p></div>}
      {newRecoveryCode && capability && (
        <div className="notice warning research-recovery-warning" role="status">
          <strong>新研究庫已建立：請立即備份復原碼</strong>
          <p>目前沒有帳號救援機制。復原碼等同此研究庫的存取權，請勿公開或貼到 issue / PR / 訊息紀錄。</p>
        </div>
      )}

      <div className="research-library-grid">
        <div className="research-library-save">
          <h3>執行並保存</h3>
          <label className="field">
            <span>研究名稱</span>
            <input
              aria-label="ResearchRun 研究名稱"
              maxLength={120}
              value={runName}
              placeholder={namePlaceholder}
              disabled={disabled || workspaceAction}
              onChange={(event) => setRunName(event.target.value)}
            />
          </label>
          <p className="research-library-help">按下後由 Worker 執行既有 Walk-Forward authority；只有 `completed` result 才會寫入 D1。瀏覽器沒有上傳 completed result 的 API。</p>
          <div className="section-actions research-library-actions">
            {workspaceAction && <button type="button" className="secondary" onClick={cancelOperation}>停止等待</button>}
            <button
              type="button"
              className="primary"
              disabled={disabled || workspaceAction || !request || health !== "online"}
              onClick={() => void saveResearch()}
            >
              {action === "save" ? "執行並保存中…" : "執行並保存"}
            </button>
          </div>
        </div>

        <div className="research-library-access">
          <h3>研究庫復原碼</h3>
          {capability ? (
            <>
              <div className="research-capability-row">
                <code aria-label="Research Library 復原碼">{showCapability ? capability : `rrl_${"•".repeat(24)}`}</code>
                <button type="button" className="secondary" onClick={() => setShowCapability((current) => !current)}>{showCapability ? "隱藏" : "顯示"}</button>
              </div>
              <p className="research-library-help">Library {libraryId ? shortHash(libraryId) : "連結中…"}。復原碼只用來驗證此研究庫；D1 僅保存其 SHA-256 hash。</p>
              <div className="section-actions research-library-actions compact">
                <button type="button" className="secondary" onClick={() => void copyCapability()}>複製復原碼</button>
                <button type="button" className="secondary" onClick={() => downloadRecoveryCode(capability)}>匯出復原碼</button>
                <button type="button" className="secondary danger-text" disabled={workspaceAction} onClick={forgetDeviceCredential}>忘記此裝置</button>
              </div>
            </>
          ) : (
            <>
              <label className="field">
                <span>跨裝置連結既有研究庫</span>
                <input
                  aria-label="匯入 Research Library 復原碼"
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  value={candidateCapability}
                  placeholder="rrl_…"
                  disabled={action === "connect"}
                  onChange={(event) => setCandidateCapability(event.target.value)}
                />
              </label>
              <p className="research-library-help">沒有復原碼也可第一次「執行並保存」；研究成功後才建立新 library 並回傳一次復原碼。</p>
              <button type="button" className="secondary" disabled={action === "connect" || !candidateCapability.trim()} onClick={() => void connectLibrary()}>{action === "connect" ? "驗證復原碼…" : "連結研究庫"}</button>
            </>
          )}
        </div>
      </div>

      <div className="research-history-heading">
        <div>
          <h3>研究歷史</h3>
          <p>{capability ? `最近 ${runs.length} 筆 durable runs` : "連結或建立研究庫後，這裡會顯示 D1 durable history。"}</p>
        </div>
        {capability && <button type="button" className="secondary" disabled={Boolean(action)} onClick={() => void refreshLibrary()}>{action === "refresh" ? "重新整理中…" : "重新整理"}</button>}
      </div>

      {capability && runs.length > 0 ? (
        <div className="research-run-list">
          {runs.map((run) => (
            <article className="research-run-item" key={run.runId}>
              <div>
                <strong>{run.name}</strong>
                <span>{run.createdAt || "剛建立"} · {run.decisionCount} Decision</span>
                <small>job {shortHash(run.jobHash)}{run.sourceRunId ? ` · rerun of ${shortHash(run.sourceRunId)}` : ""}</small>
              </div>
              <div className="research-run-actions">
                <button type="button" className="secondary" disabled={disabled || workspaceAction} onClick={() => void openRun(run)}>{action === "load" ? "讀取中…" : "查看保存結果"}</button>
                <button type="button" className="secondary" disabled={disabled || workspaceAction} onClick={() => void rerun(run)}>{action === "rerun" ? "重跑中…" : "用原 Request 重跑"}</button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state">{capability ? "這個研究庫目前沒有可顯示的 ResearchRun。" : "尚未連結 Research Library。"}</div>
      )}
    </section>
  );
}
