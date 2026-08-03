import { useEffect, useMemo, useRef, useState } from "react";
import { AllocationEditor } from "./AllocationEditor";
import { PortfolioApiError, checkHealth, runBacktest, runPreflight } from "./api";
import {
  createDefaultModel,
  createExampleModel,
  migrateModel,
  portfolioWeightTotal,
  toApiRequest,
  validateModel,
} from "./model";
import { ResultsDashboard } from "./ResultsDashboard";
import { SettingsPanels } from "./SettingsPanels";
import type {
  BacktestResponse,
  Locale,
  PreflightResponse,
  Theme,
  WorkspaceModel,
} from "./types";

const MODEL_KEY = "backteststock.portfolio.model.v1";
const THEME_KEY = "backteststock.portfolio.theme";
const LOCALE_KEY = "backteststock.portfolio.locale";

function encodeModel(model: WorkspaceModel): string {
  const bytes = new TextEncoder().encode(JSON.stringify(model));
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/u, "");
}

function decodeModel(encoded: string): WorkspaceModel {
  const normalized = encoded.replaceAll("-", "+").replaceAll("_", "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return migrateModel(JSON.parse(new TextDecoder().decode(bytes)) as unknown);
}

function loadInitialModel(): WorkspaceModel {
  const parameters = new URLSearchParams(window.location.search);
  const shared = parameters.get("model");
  if (shared) {
    try {
      return decodeModel(shared);
    } catch {
      // Fall through to the local model. The UI will remain usable.
    }
  }
  try {
    const saved = window.localStorage.getItem(MODEL_KEY);
    return saved ? migrateModel(JSON.parse(saved) as unknown) : createDefaultModel();
  } catch {
    return createDefaultModel();
  }
}

function downloadFile(filename: string, content: string, type: string): void {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function csvEscape(value: unknown): string {
  const text = value == null ? "" : String(value);
  return /[",\n\r]/u.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function resultsCsv(response: BacktestResponse): string {
  const metricKeys = [...new Set(response.results.flatMap((result) => Object.keys(result.metrics)))];
  const rows = [
    ["portfolio", ...metricKeys],
    ...response.results.map((result) => [
      result.name,
      ...metricKeys.map((key) => result.metrics[key] ?? ""),
    ]),
  ];
  return `\uFEFF${rows.map((row) => row.map(csvEscape).join(",")).join("\r\n")}`;
}

function statusText(error: unknown): string {
  if (error instanceof PortfolioApiError) {
    const request = error.requestId ? `（Request ${error.requestId}）` : "";
    return `${error.message}${request}`;
  }
  if (error instanceof Error) return error.message;
  return "發生未知錯誤。";
}

function PreflightSummary({ response }: { response: PreflightResponse }) {
  const readyAssets = response.assets.filter((asset) => asset.status === "ready").length;
  const readyPortfolios = response.portfolios.filter((portfolio) => portfolio.status === "ready").length;
  return (
    <section className="workspace-card preflight-card" aria-labelledby="preflight-title">
      <div className="section-heading">
        <div>
          <span className="section-index">✓</span>
          <div>
            <h2 id="preflight-title">資料預檢</h2>
            <p>Request {response.request_id.slice(0, 8)} · 有效結束日 {response.effective_end}</p>
          </div>
        </div>
        <div className="preflight-counts">
          <span>{readyAssets}/{response.assets.length} 資產可用</span>
          <span>{readyPortfolios}/{response.portfolios.length} 投組可執行</span>
        </div>
      </div>
      {response.warnings.length > 0 && (
        <div className="notice warning"><strong>預檢提醒</strong><ul>{response.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></div>
      )}
      <div className="preflight-grid">
        {response.portfolios.map((portfolio) => (
          <article className={`preflight-item ${portfolio.status}`} key={portfolio.name}>
            <div><strong>{portfolio.name}</strong><span className={`status-pill ${portfolio.status}`}>{portfolio.status === "ready" ? "可執行" : "失敗"}</span></div>
            <p>{portfolio.status === "ready" ? `${portfolio.effective_start} → ${portfolio.effective_end} · ${portfolio.observations} 筆` : portfolio.detail}</p>
            <small>{portfolio.symbols.join(" · ")}</small>
          </article>
        ))}
      </div>
      <details className="preflight-details">
        <summary>查看逐檔資料狀態</summary>
        <div className="table-scroll" tabIndex={0} role="region" aria-label="預檢資產列表">
          <table className="data-table">
            <thead><tr><th>代碼</th><th>狀態</th><th>幣別</th><th>有效期間</th><th>觀察數</th><th>說明</th></tr></thead>
            <tbody>{response.assets.map((asset) => <tr key={asset.symbol}><th scope="row">{asset.symbol}</th><td>{asset.status === "ready" ? "可用" : "失敗"}</td><td>{asset.quote_currency ?? "—"}</td><td>{asset.effective_start && asset.effective_end ? `${asset.effective_start} → ${asset.effective_end}` : "—"}</td><td>{asset.observations}</td><td>{asset.detail ?? "—"}</td></tr>)}</tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

export default function App() {
  const [model, setModelState] = useState<WorkspaceModel>(loadInitialModel);
  const [theme, setTheme] = useState<Theme>(() => (window.localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark"));
  const [locale, setLocale] = useState<Locale>(() => (window.localStorage.getItem(LOCALE_KEY) === "en" ? "en" : "zh-TW"));
  const [health, setHealth] = useState<"checking" | "online" | "offline">("checking");
  const [preflight, setPreflight] = useState<PreflightResponse | null>(null);
  const [response, setResponse] = useState<BacktestResponse | null>(null);
  const [busy, setBusy] = useState<"preflight" | "backtest" | null>(null);
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const validationRef = useRef<HTMLDivElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const activeController = useRef<AbortController | null>(null);
  const issues = useMemo(() => validateModel(model), [model]);
  const activePortfolioCount = useMemo(
    () => model.portfolios.filter((portfolio) => portfolioWeightTotal(portfolio, model) > 0).length,
    [model],
  );
  const uniqueSymbols = useMemo(
    () => new Set(model.assets.map((asset) => asset.symbol.trim().toUpperCase()).filter(Boolean)).size,
    [model.assets],
  );

  function setModel(updater: (current: WorkspaceModel) => WorkspaceModel) {
    setModelState((current) => updater(current));
    setPreflight(null);
    setResponse(null);
    setMessage("");
  }

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = locale === "en" ? "en" : "zh-Hant";
    window.localStorage.setItem(LOCALE_KEY, locale);
  }, [locale]);

  useEffect(() => {
    const controller = new AbortController();
    checkHealth(controller.signal)
      .then(() => setHealth("online"))
      .catch(() => setHealth("offline"));
    return () => controller.abort();
  }, []);

  useEffect(() => () => activeController.current?.abort(), []);

  function ensureValid(): boolean {
    setError("");
    if (!issues.length) return true;
    setError("設定尚未通過驗證，請先修正下列項目。 ");
    window.requestAnimationFrame(() => validationRef.current?.focus());
    return false;
  }

  async function preflightModel() {
    if (!ensureValid()) return;
    activeController.current?.abort();
    const controller = new AbortController();
    activeController.current = controller;
    setBusy("preflight");
    setError("");
    setMessage("正在取得行情、匯率與公司行為稽核…");
    try {
      const result = await runPreflight(toApiRequest(model), controller.signal);
      setPreflight(result);
      setMessage("資料預檢完成。可執行投組已明確列出。 ");
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(statusText(caught));
    } finally {
      if (activeController.current === controller) activeController.current = null;
      setBusy(null);
    }
  }

  async function backtestModel() {
    if (!ensureValid()) return;
    activeController.current?.abort();
    const controller = new AbortController();
    activeController.current = controller;
    setBusy("backtest");
    setError("");
    setMessage("正在執行每日 TWD Portfolio Ledger…");
    try {
      const request = toApiRequest(model);
      const preflightResult = preflight ?? (await runPreflight(request, controller.signal));
      setPreflight(preflightResult);
      if (!preflightResult.portfolios.some((portfolio) => portfolio.status === "ready")) {
        throw new Error("沒有任何投資組合通過資料預檢。 ");
      }
      const result = await runBacktest(request, controller.signal);
      setResponse(result);
      setMessage(`回測完成：${result.results.length} 組成功，${result.failures.length} 組失敗。`);
      window.requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(statusText(caught));
    } finally {
      if (activeController.current === controller) activeController.current = null;
      setBusy(null);
    }
  }

  function cancelRun() {
    activeController.current?.abort();
    activeController.current = null;
    setBusy(null);
    setMessage("已取消目前請求。 ");
  }

  function saveModel() {
    window.localStorage.setItem(MODEL_KEY, JSON.stringify(model));
    setMessage("模型已儲存在此瀏覽器。 ");
  }

  async function shareModel() {
    const encoded = encodeModel(model);
    const url = new URL(window.location.href);
    url.search = "";
    url.searchParams.set("model", encoded);
    await navigator.clipboard.writeText(url.toString());
    window.history.replaceState(null, "", url);
    setMessage(encoded.length > 6000 ? "分享網址已複製；模型較大，部分通訊軟體可能截斷長網址。" : "分享網址已複製到剪貼簿。 ");
  }

  function exportModel() {
    downloadFile("portfolio-model.json", JSON.stringify(model, null, 2), "application/json;charset=utf-8");
  }

  async function importModel(file: File) {
    try {
      const raw = JSON.parse(await file.text()) as unknown;
      setModelState(migrateModel(raw));
      setPreflight(null);
      setResponse(null);
      setError("");
      setMessage("模型匯入完成。 ");
    } catch {
      setError("無法讀取此 JSON 模型檔。 ");
    }
  }

  return (
    <div className="portfolio-app">
      <header className="app-header">
        <div className="header-inner">
          <a className="brand" href="/" aria-label="返回 BacktestStock 個股研究">
            <span className="brand-mark">B</span>
            <span><strong>BacktestStock</strong><small>Portfolio Research</small></span>
          </a>
          <nav className="header-actions" aria-label="Portfolio 工作區操作">
            <span className={`service-state ${health}`}><i />{health === "online" ? "服務正常" : health === "checking" ? "檢查服務" : "服務離線"}</span>
            <button type="button" onClick={saveModel}>儲存</button>
            <button type="button" onClick={() => void shareModel()}>分享</button>
            <button type="button" onClick={() => fileInputRef.current?.click()}>匯入</button>
            <button type="button" onClick={exportModel}>匯出模型</button>
            <button type="button" onClick={() => setTheme((current) => current === "dark" ? "light" : "dark")} aria-label="切換明暗模式">{theme === "dark" ? "淺色" : "深色"}</button>
            <button type="button" onClick={() => setLocale((current) => current === "zh-TW" ? "en" : "zh-TW")} aria-label="切換語言">{locale === "zh-TW" ? "EN" : "繁中"}</button>
          </nav>
          <input ref={fileInputRef} className="sr-only" type="file" accept="application/json,.json" onChange={(event) => { const file = event.target.files?.[0]; if (file) void importModel(file); event.target.value = ""; }} />
        </div>
      </header>

      <main id="portfolio-main" className="app-main">
        <section className="hero">
          <div>
            <p className="eyebrow">DAILY TWD · AUDITABLE LEDGER · SELF-OWNED API</p>
            <h1>投資組合研究工作區</h1>
            <p>同時比較最多五組投資組合，完整處理現金流、配息、再平衡、交易成本、槓桿與資料稽核。這是一個可直接開啟與重新整理的獨立專頁，不是彈出視窗。</p>
          </div>
          <div className="hero-actions">
            <button type="button" className="secondary" onClick={() => setModelState(createExampleModel())}>載入範例</button>
            <button type="button" className="secondary danger-text" onClick={() => { setModelState(createDefaultModel()); setPreflight(null); setResponse(null); setMessage("已重設為空白模型。 "); }}>重設</button>
          </div>
        </section>

        <section className="model-summary" aria-label="目前模型摘要">
          <span><strong>{activePortfolioCount}</strong> 組有效投組</span>
          <span><strong>{uniqueSymbols}</strong> 項唯一資產</span>
          <span><strong>{model.startDate}</strong> → <strong>{model.endDate}</strong></span>
          <span>每日 TWD 估值</span>
          <span>{model.rebalancing.frequency === "none" ? "不定期再平衡" : `${model.rebalancing.frequency} 再平衡`}</span>
          <span>{model.leverage.type === "none" ? "無槓桿" : "槓桿啟用"}</span>
        </section>

        {issues.length > 0 && (
          <div className="validation-summary" role="alert" tabIndex={-1} ref={validationRef}>
            <strong>設定檢查</strong>
            <ul>{issues.map((issue, index) => <li key={`${issue.field}-${index}`}>{issue.message}</li>)}</ul>
          </div>
        )}
        {error && <div className="notice error" role="alert"><strong>無法執行</strong><p>{error}</p></div>}
        {message && <div className="notice info" aria-live="polite"><p>{message}</p></div>}

        <AllocationEditor model={model} setModel={setModel} />
        <SettingsPanels model={model} setModel={setModel} />
        {preflight && <PreflightSummary response={preflight} />}
        <div ref={resultsRef}>
          {response && <ResultsDashboard response={response} preflight={preflight} onExportJson={() => downloadFile("portfolio-results.json", JSON.stringify(response, null, 2), "application/json;charset=utf-8")} onExportCsv={() => downloadFile("portfolio-results.csv", resultsCsv(response), "text/csv;charset=utf-8")} />}
        </div>
      </main>

      <footer className="run-bar" aria-label="回測執行列">
        <div>
          <strong>{issues.length ? `${issues.length} 項設定需修正` : "設定可執行"}</strong>
          <span>{busy ? (busy === "preflight" ? "正在預檢資料" : "正在執行回測") : "先預檢資料，再執行完整回測"}</span>
        </div>
        <div className="run-actions">
          {busy && <button type="button" className="secondary" onClick={cancelRun}>取消</button>}
          <button type="button" className="secondary" disabled={Boolean(busy) || issues.length > 0} onClick={() => void preflightModel()}>{busy === "preflight" ? "預檢中…" : "資料預檢"}</button>
          <button type="button" className="primary" disabled={Boolean(busy) || issues.length > 0} onClick={() => void backtestModel()}>{busy === "backtest" ? "回測中…" : "執行回測"}</button>
        </div>
      </footer>
    </div>
  );
}
