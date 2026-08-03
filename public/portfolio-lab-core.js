const PANEL_SELECTOR = "#backtest-panel";
const STORAGE_KEY = "backteststock-portfolio-lab-v1";
const SHARE_PREFIX = "#portfolio-lab=";
const MAX_PORTFOLIOS = 5;
const MAX_ASSETS = 20;
const COLORS = ["#0f766e", "#2563eb", "#7c3aed", "#b45309", "#be123c", "#475569"];

const TEXT = {
  "zh-TW": {
    title: "投資組合回測實驗室",
    subtitle: "完整移植原版 Portfolio Backtest Lab 的設定、資產矩陣、現金流、再平衡、槓桿與多維結果分析。",
    settings: "回測設定",
    assets: "資產配置",
    run: "執行完整回測",
    running: "正在執行完整回測…",
    save: "儲存",
    share: "複製分享網址",
    exportConfig: "匯出設定",
    reset: "重設",
    close: "關閉並返回績效列表",
    period: "期間與估值",
    cashflows: "定期現金流",
    rebalancing: "再平衡",
    leverage: "槓桿與保證金",
    dividends: "股息與成本",
    analytics: "進階分析",
    start: "起始日期",
    end: "結束日期",
    initial: "初始投資金額",
    currency: "基準幣別",
    output: "曲線輸出頻率",
    includeYtd: "納入今年 YTD",
    none: "停用",
    fixed: "固定金額",
    percent: "投組淨值比例",
    amount: "金額／比例",
    frequency: "頻率",
    timing: "發生時點",
    growth: "每年成長率",
    monthly: "每月",
    quarterly: "每季",
    semiannual: "每半年",
    annual: "每年",
    beginning: "期初",
    ending: "期末",
    threshold: "偏離門檻",
    leverageType: "槓桿方式",
    fixedRatio: "固定槓桿倍數",
    fixedDebt: "固定借款金額",
    ratio: "槓桿倍數",
    debt: "借款金額",
    interest: "年利率",
    maintenance: "維持保證金率",
    reinvest: "股息再投入",
    income: "顯示股息收入",
    cost: "交易成本",
    style: "報酬式風格分析",
    factors: "Fama–French 因子回歸",
    inflation: "通膨調整報酬",
    regime: "市場環境分析",
    riskFree: "無風險利率",
    benchmark: "比較基準",
    addPortfolio: "新增投組",
    removePortfolio: "減少投組",
    addAsset: "新增資產",
    clear: "清除",
    ticker: "股票代碼",
    portfolio: "投資組合",
    total: "合計",
    ready: "可執行",
    adjust: "需調整至 100%",
    results: "完整回測結果",
    overview: "總覽",
    growthTab: "資產成長",
    drawdownTab: "回撤",
    annualTab: "年度報酬",
    monthlyTab: "月報酬熱圖",
    incomeTab: "股息收入",
    allocationTab: "配置",
    analyticsTab: "分析",
    exportCsv: "匯出 CSV",
    exportJson: "匯出 JSON",
    warnings: "資料與模型警告",
    copied: "分享網址已複製。",
  },
  en: {
    title: "Portfolio Backtest Lab",
    subtitle: "Full settings, allocation matrix, cash flows, rebalancing, leverage and multi-view analysis from the original application.",
    settings: "Settings", assets: "Assets", run: "Run full backtest", running: "Running full backtest…",
    save: "Save", share: "Copy share URL", exportConfig: "Export config", reset: "Reset", close: "Close and return",
    period: "Period & valuation", cashflows: "Cash flows", rebalancing: "Rebalancing", leverage: "Leverage & margin",
    dividends: "Dividends & costs", analytics: "Advanced analysis", start: "Start date", end: "End date",
    initial: "Initial amount", currency: "Base currency", output: "Output frequency", includeYtd: "Include YTD",
    none: "None", fixed: "Fixed amount", percent: "% of equity", amount: "Amount / percent", frequency: "Frequency",
    timing: "Timing", growth: "Annual growth", monthly: "Monthly", quarterly: "Quarterly", semiannual: "Semiannual",
    annual: "Annual", beginning: "Beginning", ending: "End", threshold: "Drift threshold", leverageType: "Leverage type",
    fixedRatio: "Fixed ratio", fixedDebt: "Fixed debt", ratio: "Leverage ratio", debt: "Debt amount", interest: "Interest rate",
    maintenance: "Maintenance margin", reinvest: "Reinvest dividends", income: "Display income", cost: "Transaction cost",
    style: "Returns-based style analysis", factors: "Fama–French regression", inflation: "Inflation-adjusted returns",
    regime: "Regime analysis", riskFree: "Risk-free rate", benchmark: "Benchmark", addPortfolio: "Add portfolio",
    removePortfolio: "Remove portfolio", addAsset: "Add asset", clear: "Clear", ticker: "Ticker", portfolio: "Portfolio",
    total: "Total", ready: "Ready", adjust: "Must total 100%", results: "Backtest results", overview: "Overview",
    growthTab: "Growth", drawdownTab: "Drawdown", annualTab: "Annual returns", monthlyTab: "Monthly heatmap",
    incomeTab: "Income", allocationTab: "Allocation", analyticsTab: "Analytics", exportCsv: "Export CSV",
    exportJson: "Export JSON", warnings: "Warnings", copied: "Share URL copied.",
  },
};

function id() { return crypto.randomUUID(); }
function isMobile() { return window.matchMedia?.("(max-width:760px)").matches; }
function blankWeights() { return Array.from({ length: MAX_PORTFOLIOS }, () => ""); }
function blankAsset(symbol = "") { return { id: id(), symbol, weights: blankWeights() }; }
function isoDate(date) { return date.toISOString().slice(0, 10); }
function defaults() {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(start.getFullYear() - 10);
  return {
    locale: "zh-TW", theme: "light", activeConfigTab: "settings", portfolioCount: isMobile() ? 2 : 5,
    portfolioNames: Array.from({ length: MAX_PORTFOLIOS }, (_, index) => `投組 ${index + 1}`),
    benchmark: "SPY", startDate: isoDate(start), endDate: isoDate(end), includeYtd: true,
    initialAmount: 1_000_000, baseCurrency: "TWD", outputFrequency: "daily",
    cashflowType: "none", cashflowAmount: 0, cashflowFrequency: "none", cashflowTiming: "end", cashflowGrowthRate: 0,
    rebalanceFrequency: "annual", rebalanceThreshold: null,
    leverageType: "none", leverageRatio: 1.5, debtAmount: 0, interestRate: 0, maintenanceMargin: 25,
    reinvestDividends: true, displayIncome: true, transactionCostBps: 0,
    styleAnalysis: false, factorRegression: false, inflationAdjusted: false, regime: "none", riskFreeRate: 0,
    assets: [
      { id: id(), symbol: "QQQ", weights: [60, 40, "", "", ""] },
      { id: id(), symbol: "SOXX", weights: [40, 60, "", "", ""] },
      ...Array.from({ length: 4 }, () => blankAsset()),
    ],
  };
}

function safeParse(value) { try { return JSON.parse(value); } catch { return null; } }
function normalizeState(source) {
  const base = defaults();
  const next = { ...base, ...(source && typeof source === "object" ? source : {}) };
  next.locale = next.locale === "en" ? "en" : "zh-TW";
  next.theme = next.theme === "dark" ? "dark" : "light";
  next.portfolioCount = Math.min(MAX_PORTFOLIOS, Math.max(1, Number(next.portfolioCount) || base.portfolioCount));
  next.portfolioNames = Array.from({ length: MAX_PORTFOLIOS }, (_, index) => String(next.portfolioNames?.[index] || `投組 ${index + 1}`));
  next.assets = (Array.isArray(next.assets) && next.assets.length ? next.assets : base.assets).slice(0, MAX_ASSETS).map((asset) => ({
    id: asset.id || id(), symbol: String(asset.symbol || "").toUpperCase().slice(0, 32),
    weights: Array.from({ length: MAX_PORTFOLIOS }, (_, index) => asset.weights?.[index] === "" || asset.weights?.[index] == null ? "" : Number(asset.weights[index])),
  }));
  return next;
}
function decodeShared() {
  if (!location.hash.startsWith(SHARE_PREFIX)) return null;
  try {
    const raw = location.hash.slice(SHARE_PREFIX.length).replace(/-/g, "+").replace(/_/g, "/");
    const bytes = Uint8Array.from(atob(raw), (character) => character.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch { return null; }
}
function load() { return normalizeState(decodeShared() || safeParse(localStorage.getItem(STORAGE_KEY))); }
function persist() { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
function encodeShare() {
  const bytes = new TextEncoder().encode(JSON.stringify(state));
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function e(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text != null) node.textContent = options.text;
  if (options.html != null) node.innerHTML = options.html;
  for (const [key, value] of Object.entries(options.attributes || {})) node.setAttribute(key, value);
  for (const [key, value] of Object.entries(options.properties || {})) node[key] = value;
  children.filter(Boolean).forEach((child) => node.append(child));
  return node;
}
function t(key) { return TEXT[state.locale]?.[key] || TEXT["zh-TW"][key] || key; }
function number(value, fallback = 0) { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : fallback; }
function formatMoney(value) { return new Intl.NumberFormat(state.locale, { style: "currency", currency: "TWD", maximumFractionDigits: 0 }).format(number(value)); }
function formatPercent(value) { return Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(2)}%` : "—"; }
function formatNumber(value) { return Number.isFinite(Number(value)) ? Number(value).toFixed(2) : "—"; }
function download(name, content, type = "application/json") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = e("a", { properties: { href: url, download: name } });
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 0);
}

let state = load();
let panel;
let mount;
let response = null;
let activeResultTab = "overview";
let selectedResult = 0;
let searchTimer = null;
let abortController = null;

function field(label, control, hint = "") {
  const box = e("label", { className: "pl-field" }, [e("span", { className: "pl-label", text: label }), control]);
  if (hint) box.append(e("small", { text: hint }));
  return box;
}
function input(type, value, onChange, attributes = {}) {
  const node = e("input", { attributes: { type, ...attributes }, properties: { value: value ?? "" } });
  node.addEventListener("input", () => onChange(node.value));
  return node;
}
function select(value, choices, onChange, attributes = {}) {
  const node = e("select", { attributes });
  choices.forEach(([optionValue, label]) => node.append(e("option", { text: label, properties: { value: optionValue, selected: value === optionValue } })));
  node.addEventListener("change", () => onChange(node.value));
  return node;
}
function toggle(label, checked, onChange) {
  const control = e("label", { className: "pl-toggle" }, [
    e("input", { attributes: { type: "checkbox" }, properties: { checked } }),
    e("span", { className: "pl-toggle-track" }), e("span", { text: label }),
  ]);
  control.querySelector("input").addEventListener("change", (event) => onChange(event.target.checked));
  return control;
}
function patch(values, rerender = true) { Object.assign(state, values); persist(); if (rerender) render(); }
function section(title, content) { return e("section", { className: "pl-settings-section" }, [e("h3", { text: title }), content]); }
