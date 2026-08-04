import { createDefaultModel, normalizeSymbol } from "./model";
import type { WorkspaceModel } from "./types";

const MODEL_KEY = "backteststock.portfolio.model.v1";
const HANDOFF_KEY = "backteststock-portfolio-handoff-v1";
const MAX_ASSETS = 20;

export interface PortfolioHandoffRecord {
  version: 1;
  id: string;
  source: "main" | "scanner";
  createdAt: string;
  expiresAt: string;
  sourceJobId: string | null;
  selectedTickers: string[];
  startDate: string;
  endDate: string;
  benchmark: string;
  coverageThresholdPercent: number;
  returnUrl: string;
  returnState?: Record<string, unknown>;
}

export interface PortfolioHandoffContext {
  record: PortfolioHandoffRecord;
  importedModel: boolean;
  returnUrl: string;
}

function readJson<T>(storage: Storage, key: string): T | null {
  try {
    const value = JSON.parse(storage.getItem(key) || "null") as T | null;
    return value;
  } catch {
    return null;
  }
}

function validDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/u.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`));
}

function safeReturnUrl(value: string): string {
  try {
    const url = new URL(value || "/", window.location.origin);
    if (url.origin !== window.location.origin || url.pathname !== "/") return "/";
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return "/";
  }
}

function readHandoff(): PortfolioHandoffRecord | null {
  const id = new URLSearchParams(window.location.search).get("handoff");
  if (!id) return null;
  const record = readJson<PortfolioHandoffRecord>(window.sessionStorage, HANDOFF_KEY);
  if (
    !record
    || record.version !== 1
    || record.id !== id
    || !["main", "scanner"].includes(record.source)
    || Date.parse(record.expiresAt || "") < Date.now()
  ) return null;
  return record;
}

function equalWeights(assetIds: string[]): Record<string, number> {
  const base = Math.floor((100 / assetIds.length) * 100) / 100;
  return Object.fromEntries(assetIds.map((id, index) => [
    id,
    index === assetIds.length - 1
      ? Number((100 - base * (assetIds.length - 1)).toFixed(2))
      : base,
  ]));
}

function buildScannerModel(record: PortfolioHandoffRecord): WorkspaceModel | null {
  const tickers = [...new Set(record.selectedTickers.map(normalizeSymbol).filter(Boolean))]
    .slice(0, MAX_ASSETS);
  if (!tickers.length) return null;

  const model = createDefaultModel();
  const assets = tickers.map((symbol) => ({ id: crypto.randomUUID(), symbol }));
  model.assets = assets;
  model.portfolios = [{
    id: crypto.randomUUID(),
    name: `績效列表已選 ${tickers.length} 檔等權組合`,
    weights: equalWeights(assets.map((asset) => asset.id)),
  }];
  if (validDate(record.startDate) && validDate(record.endDate) && record.startDate < record.endDate) {
    model.startDate = record.startDate;
    model.endDate = record.endDate;
  }
  const benchmark = normalizeSymbol(record.benchmark);
  if (benchmark) model.benchmark = benchmark;
  return model;
}

export function applyPortfolioHandoff(): PortfolioHandoffContext | null {
  const record = readHandoff();
  if (!record) return null;
  const imported = record.source === "scanner" ? buildScannerModel(record) : null;
  if (imported) window.localStorage.setItem(MODEL_KEY, JSON.stringify(imported));
  return {
    record,
    importedModel: Boolean(imported),
    returnUrl: safeReturnUrl(record.returnUrl),
  };
}

function handoffSummary(record: PortfolioHandoffRecord): string {
  if (record.source !== "scanner") return "由 BacktestStock 主站進入投資組合研究工作區。";
  const parts = [
    `已導入 ${record.selectedTickers.length} 檔等權組合`,
    record.startDate && record.endDate ? `${record.startDate} → ${record.endDate}` : "",
    record.benchmark ? `Benchmark ${record.benchmark}` : "",
    Number.isFinite(record.coverageThresholdPercent)
      ? `資料覆蓋率門檻 ${record.coverageThresholdPercent.toLocaleString("zh-TW", { maximumFractionDigits: 1 })}%`
      : "",
    record.sourceJobId ? `Scan Job ${record.sourceJobId.slice(0, 8)}` : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

function installUi(context: PortfolioHandoffContext): boolean {
  const brand = document.querySelector<HTMLAnchorElement>("a.brand");
  const actions = document.querySelector<HTMLElement>(".header-actions");
  const summary = document.querySelector<HTMLElement>(".model-summary");
  if (!brand || !actions || !summary) return false;

  brand.href = context.returnUrl;
  brand.setAttribute(
    "aria-label",
    context.record.source === "scanner" ? "返回個股績效掃描" : "返回 BacktestStock 個股研究",
  );

  let returnLink = actions.querySelector<HTMLAnchorElement>("#portfolio-return-link");
  if (!returnLink) {
    returnLink = document.createElement("a");
    returnLink.id = "portfolio-return-link";
    returnLink.className = "portfolio-return-link";
    actions.prepend(returnLink);
  }
  returnLink.href = context.returnUrl;
  returnLink.textContent = context.record.source === "scanner" ? "返回績效列表" : "返回個股研究";

  let banner = document.querySelector<HTMLElement>("#portfolio-handoff-banner");
  if (!banner) {
    banner = document.createElement("section");
    banner.id = "portfolio-handoff-banner";
    banner.className = "handoff-banner";
    banner.setAttribute("aria-live", "polite");
    summary.insertAdjacentElement("beforebegin", banner);
  }
  const title = document.createElement("strong");
  title.textContent = context.importedModel ? "Scanner 選股已導入" : "來源狀態已保留";
  const detail = document.createElement("span");
  detail.textContent = handoffSummary(context.record);
  banner.replaceChildren(title, detail);
  return true;
}

export function installPortfolioHandoffUi(context: PortfolioHandoffContext | null): void {
  if (!context) return;
  let attempts = 0;
  const tryInstall = () => {
    attempts += 1;
    if (installUi(context) || attempts >= 120) return;
    window.setTimeout(tryInstall, 25);
  };
  tryInstall();
}
