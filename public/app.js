import { METRIC_DEFINITION_VERSION } from "./scan-score-formulas.js";

const STORAGE_KEY = "backteststock-state-v1";
const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v2";
const COLORS = ["#1d4ed8", "#0f766e", "#b45309", "#7c3aed", "#be123c", "#334155"];
const METRICS = [
  ["cagr", "年化報酬率", "percent", "positive"],
  ["volatility", "年化波動率", "percent", "negative"],
  ["mdd", "最大回撤", "percent", "negative"],
  ["sharpe_ratio", "Sharpe", "number", "positive"],
  ["sortino_ratio", "Sortino", "number", "positive"],
  ["beta", "Beta", "number", ""],
  ["alpha", "Alpha", "percent", "positive"],
];
const SCAN_METRICS = [
  ["total_return", "區間總報酬", "percent", "positive"],
  ["cagr", "年化報酬率", "percent", "positive"],
  ["volatility", "年化波動率", "percent", "negative"],
  ["mdd", "最大回撤", "percent", "negative"],
  ["sharpe_ratio", "Sharpe", "number", "positive"],
  ["sortino_ratio", "Sortino", "number", "positive"],
  ["beta", "Beta", "number", ""],
  ["alpha", "Alpha", "percent", "positive"],
  ["data_coverage", "資料覆蓋率", "percent", ""],
  ["trading_days", "交易日", "integer", ""],
];
const SCAN_CHUNK_SIZE = 100;
const SCAN_REQUEST_RETRIES = 2;
const SCAN_MAX_TICKER_ATTEMPTS = 2;
const SCAN_RETRY_DELAYS_MS = [1_500, 5_000, 15_000, 30_000, 60_000];

const currentMonth = new Date().toISOString().slice(0, 7);
const defaultState = {
  settings: {
    initialAmount: 10000,
    startPeriod: "2015-01",
    endPeriod: currentMonth,
    rebalancingPeriod: "annually",
    benchmark: "SPY",
  },
  portfolios: [
    {
      id: crypto.randomUUID(),
      name: "成長型",
      assets: [
        { id: crypto.randomUUID(), ticker: "QQQ", weight: 60 },
        { id: crypto.randomUUID(), ticker: "SOXX", weight: 40 },
      ],
    },
    {
      id: crypto.randomUUID(),
      name: "市場基準",
      assets: [
        { id: crypto.randomUUID(), ticker: "VTI", weight: 70 },
        { id: crypto.randomUUID(), ticker: "BND", weight: 30 },
      ],
    },
  ],
};

let state = loadState();
let latestBacktest = null;
let latestScan = [];
let latestScreener = null;
let universeCatalog = [];
let activeControllers = new Set();
let cancelRequested = false;
let scanSort = { key: "cagr", direction: "desc" };
let activeScanJob = null;
let scanExecutionRunning = false;
let scanPage = 1;
let scanPageSize = 100;
let tickerUniverse = [];

const dom = {
  tabButtons: document.querySelectorAll(".tab-button"),
  tabPanels: document.querySelectorAll(".tab-panel"),
  portfolioList: document.querySelector("#portfolio-list"),
  backtestForm: document.querySelector("#backtest-form"),
  backtestError: document.querySelector("#backtest-error"),
  backtestResults: document.querySelector("#backtest-results"),
  backtestWarning: document.querySelector("#backtest-warning"),
  metricsTable: document.querySelector("#metrics-table"),
  chart: document.querySelector("#portfolio-chart"),
  chartLegend: document.querySelector("#chart-legend"),
  chartScale: document.querySelector("#chart-scale"),
  scanForm: document.querySelector("#scan-form"),
  scanError: document.querySelector("#scan-error"),
  scanResults: document.querySelector("#scan-results"),
  scanTable: document.querySelector("#scan-table"),
  scanSummary: document.querySelector("#scan-summary"),
  scanContext: document.querySelector("#scan-context"),
  scanProgress: document.querySelector("#scan-progress"),
  scanProgressBar: document.querySelector("#scan-progress-bar"),
  scanProgressLabel: document.querySelector("#scan-progress-label"),
  scanPagination: document.querySelector("#scan-pagination"),
  scanPagePrev: document.querySelector("#scan-page-prev"),
  scanPageNext: document.querySelector("#scan-page-next"),
  scanPageStatus: document.querySelector("#scan-page-status"),
  scanPageSize: document.querySelector("#scan-page-size"),
  screenerIndex: document.querySelector("#screener-index"),
  screenerWarning: document.querySelector("#screener-warning"),
  screenerFunnel: document.querySelector("#screener-funnel"),
  universeMeta: document.querySelector("#universe-meta"),
  universeStatus: document.querySelector("#universe-status"),
  loadingOverlay: document.querySelector("#loading-overlay"),
  loadingMessage: document.querySelector("#loading-message"),
  statusDot: document.querySelector("#status-dot"),
  serviceStatus: document.querySelector("#service-status"),
  tickerOptions: document.querySelector("#ticker-options"),
};

function loadState() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (parsed?.settings && Array.isArray(parsed?.portfolios) && parsed.portfolios.length) {
      return parsed;
    }
  } catch (error) {
    console.warn("Unable to load saved state", error);
  }
  return structuredClone(defaultState);
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function createElement(tag, options = {}, children = []) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(options)) {
    if (key === "className") element.className = value;
    else if (key === "text") element.textContent = value;
    else if (key === "dataset") Object.assign(element.dataset, value);
    else if (key === "attributes") {
      for (const [attribute, attributeValue] of Object.entries(value)) {
        element.setAttribute(attribute, attributeValue);
      }
    } else if (key in element) element[key] = value;
    else element.setAttribute(key, value);
  }
  for (const child of children) {
    if (child != null) element.append(child);
  }
  return element;
}

function parsePeriod(period) {
  const [year, month] = period.split("-").map(Number);
  if (!year || !month) throw new Error("請選擇有效的起訖月份。");
  return { year, month };
}

function formatMetric(value, type) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const numeric = Number(value);
  if (type === "percent") return `${(numeric * 100).toFixed(2)}%`;
  if (type === "integer") return Math.round(numeric).toLocaleString("zh-TW");
  return numeric.toFixed(2);
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function sanitizeTicker(value) {
  return String(value || "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9.^=_-]/g, "")
    .slice(0, 20);
}

function setMessage(element, message = "") {
  element.textContent = message;
  element.classList.toggle("hidden", !message);
}

function showLoading(message) {
  dom.loadingMessage.textContent = message;
  dom.loadingOverlay.classList.remove("hidden");
}

function hideLoading() {
  dom.loadingOverlay.classList.add("hidden");
}

async function apiFetch(path, options = {}, timeoutMs = 50_000) {
  const controller = new AbortController();
  activeControllers.add(controller);
  const timeout = setTimeout(() => controller.abort("timeout"), timeoutMs);

  try {
    const response = await fetch(path, { ...options, signal: controller.signal });
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json")
      ? await response.json()
      : { error: await response.text() };
    if (!response.ok) {
      const error = new Error(payload.error || `HTTP ${response.status}`);
      error.status = response.status;
      error.retryable = response.status === 408
        || response.status === 429
        || response.status >= 500;
      throw error;
    }
    return payload;
  } catch (error) {
    if (controller.signal.aborted) {
      if (controller.signal.reason === "timeout") throw new Error("行情服務回應逾時，系統將保留進度並自動重試。");
      throw new Error("請求已取消。");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
    activeControllers.delete(controller);
  }
}

function initializeControls() {
  document.querySelector("#initial-amount").value = state.settings.initialAmount;
  document.querySelector("#start-period").value = state.settings.startPeriod;
  document.querySelector("#end-period").value = state.settings.endPeriod || currentMonth;
  document.querySelector("#rebalancing-period").value = state.settings.rebalancingPeriod;
  document.querySelector("#benchmark").value = state.settings.benchmark;
  document.querySelector("#scan-end-period").value = currentMonth;
}

function renderPortfolios() {
  dom.portfolioList.replaceChildren();

  state.portfolios.forEach((portfolio, portfolioIndex) => {
    const nameInput = createElement("input", {
      value: portfolio.name,
      maxLength: 80,
      ariaLabel: `投資組合 ${portfolioIndex + 1} 名稱`,
      dataset: { action: "portfolio-name", portfolioId: portfolio.id },
    });
    const deleteButton = createElement("button", {
      type: "button",
      className: "button danger compact",
      text: "刪除投組",
      dataset: { action: "remove-portfolio", portfolioId: portfolio.id },
      disabled: state.portfolios.length === 1,
    });
    const header = createElement("div", { className: "portfolio-header" }, [nameInput, deleteButton]);

    const assetList = createElement("div", { className: "asset-list" });
    portfolio.assets.forEach((asset, assetIndex) => {
      const tickerLabel = createElement("label", {}, [
        createElement("span", { text: assetIndex === 0 ? "股票代碼" : "" }),
        createElement("input", {
          value: asset.ticker,
          attributes: { list: "ticker-options" },
          maxLength: 20,
          autocomplete: "off",
          spellcheck: false,
          dataset: {
            action: "asset-ticker",
            portfolioId: portfolio.id,
            assetId: asset.id,
          },
          ariaLabel: `${portfolio.name} 股票代碼`,
        }),
      ]);
      const weightLabel = createElement("label", {}, [
        createElement("span", { text: assetIndex === 0 ? "權重 %" : "" }),
        createElement("input", {
          type: "number",
          min: "0",
          max: "100",
          step: "0.1",
          value: asset.weight,
          inputMode: "decimal",
          dataset: {
            action: "asset-weight",
            portfolioId: portfolio.id,
            assetId: asset.id,
          },
          ariaLabel: `${portfolio.name} ${asset.ticker || "資產"} 權重`,
        }),
      ]);
      const removeButton = createElement("button", {
        type: "button",
        className: "button danger compact",
        text: "×",
        title: "移除資產",
        ariaLabel: `移除 ${asset.ticker || "資產"}`,
        dataset: {
          action: "remove-asset",
          portfolioId: portfolio.id,
          assetId: asset.id,
        },
        disabled: portfolio.assets.length === 1,
      });
      assetList.append(createElement("div", { className: "asset-row" }, [tickerLabel, weightLabel, removeButton]));
    });

    const total = portfolio.assets.reduce((sum, asset) => sum + Number(asset.weight || 0), 0);
    const totalBadge = createElement("span", {
      className: `weight-total${Math.abs(total - 100) <= 0.01 ? " valid" : ""}`,
      text: `總計 ${total.toFixed(1)}%`,
    });
    const footerActions = createElement("div", { className: "toolbar" }, [
      createElement("button", {
        type: "button",
        className: "button ghost compact",
        text: "新增資產",
        dataset: { action: "add-asset", portfolioId: portfolio.id },
      }),
      createElement("button", {
        type: "button",
        className: "button ghost compact",
        text: "正規化 100%",
        dataset: { action: "normalize", portfolioId: portfolio.id },
      }),
    ]);
    const footer = createElement("div", { className: "portfolio-footer" }, [totalBadge, footerActions]);
    dom.portfolioList.append(createElement("article", { className: "portfolio-card" }, [header, assetList, footer]));
  });
}

function findPortfolio(portfolioId) {
  return state.portfolios.find((portfolio) => portfolio.id === portfolioId);
}

function handlePortfolioInput(event) {
  const action = event.target.dataset.action;
  const portfolio = findPortfolio(event.target.dataset.portfolioId);
  if (!portfolio) return;

  if (action === "portfolio-name") portfolio.name = event.target.value.slice(0, 80);
  if (action === "asset-ticker") {
    const asset = portfolio.assets.find((item) => item.id === event.target.dataset.assetId);
    if (asset) {
      asset.ticker = sanitizeTicker(event.target.value);
      if (event.target.value !== asset.ticker) event.target.value = asset.ticker;
    }
  }
  if (action === "asset-weight") {
    const asset = portfolio.assets.find((item) => item.id === event.target.dataset.assetId);
    if (asset) asset.weight = Math.max(0, Math.min(100, Number(event.target.value || 0)));
    renderPortfolios();
  }
  saveState();
}

function handlePortfolioClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const portfolio = findPortfolio(button.dataset.portfolioId);
  if (!portfolio) return;

  switch (button.dataset.action) {
    case "add-asset":
      portfolio.assets.push({ id: crypto.randomUUID(), ticker: "", weight: 0 });
      break;
    case "remove-asset":
      if (portfolio.assets.length > 1) {
        portfolio.assets = portfolio.assets.filter((asset) => asset.id !== button.dataset.assetId);
      }
      break;
    case "remove-portfolio":
      if (state.portfolios.length > 1) {
        state.portfolios = state.portfolios.filter((item) => item.id !== portfolio.id);
      }
      break;
    case "normalize": {
      const positiveAssets = portfolio.assets.filter((asset) => Number(asset.weight) > 0);
      const total = positiveAssets.reduce((sum, asset) => sum + Number(asset.weight), 0);
      if (total > 0) {
        positiveAssets.forEach((asset, index) => {
          const normalized = index === positiveAssets.length - 1
            ? 100 - positiveAssets.slice(0, -1).reduce((sum, item) => sum + Number(item.weight), 0)
            : (Number(asset.weight) / total) * 100;
          asset.weight = Number(normalized.toFixed(2));
        });
        const normalizedTotal = positiveAssets.reduce((sum, asset) => sum + Number(asset.weight), 0);
        positiveAssets[positiveAssets.length - 1].weight += Number((100 - normalizedTotal).toFixed(2));
      }
      break;
    }
    default:
      return;
  }
  saveState();
  renderPortfolios();
}

function syncSettings() {
  state.settings = {
    initialAmount: Number(document.querySelector("#initial-amount").value),
    startPeriod: document.querySelector("#start-period").value,
    endPeriod: document.querySelector("#end-period").value,
    rebalancingPeriod: document.querySelector("#rebalancing-period").value,
    benchmark: sanitizeTicker(document.querySelector("#benchmark").value),
  };
  document.querySelector("#benchmark").value = state.settings.benchmark;
  saveState();
}

function buildBacktestPayload() {
  syncSettings();
  if (!Number.isFinite(state.settings.initialAmount) || state.settings.initialAmount <= 0) {
    throw new Error("初始投資金額必須大於 0。");
  }
  const start = parsePeriod(state.settings.startPeriod);
  const end = parsePeriod(state.settings.endPeriod);
  const startValue = start.year * 12 + start.month;
  const endValue = end.year * 12 + end.month;
  if (startValue > endValue) throw new Error("結束月份必須晚於或等於起始月份。");

  const names = new Set();
  const portfolios = state.portfolios.map((portfolio) => {
    const name = portfolio.name.trim();
    if (!name) throw new Error("投資組合名稱不可空白。");
    if (names.has(name)) throw new Error(`投資組合名稱「${name}」重複。`);
    names.add(name);

    const assets = portfolio.assets
      .map((asset) => ({ ticker: sanitizeTicker(asset.ticker), weight: Number(asset.weight) }))
      .filter((asset) => asset.ticker && asset.weight > 0);
    if (!assets.length) throw new Error(`投資組合「${name}」沒有有效資產。`);
    if (new Set(assets.map((asset) => asset.ticker)).size !== assets.length) {
      throw new Error(`投資組合「${name}」包含重複股票代碼。`);
    }
    const total = assets.reduce((sum, asset) => sum + asset.weight, 0);
    if (Math.abs(total - 100) > 0.01) throw new Error(`投資組合「${name}」的總權重為 ${total.toFixed(2)}%，必須為 100%。`);
    return {
      name,
      tickers: assets.map((asset) => asset.ticker),
      weights: assets.map((asset) => asset.weight),
      rebalancingPeriod: state.settings.rebalancingPeriod,
    };
  });

  return {
    initialAmount: state.settings.initialAmount,
    startYear: start.year,
    startMonth: start.month,
    endYear: end.year,
    endMonth: end.month,
    rebalancingPeriod: state.settings.rebalancingPeriod,
    benchmark: state.settings.benchmark,
    portfolios,
  };
}

async function runBacktest(event) {
  event.preventDefault();
  setMessage(dom.backtestError);
  setMessage(dom.backtestWarning);

  let payload;
  try {
    payload = buildBacktestPayload();
  } catch (error) {
    setMessage(dom.backtestError, error.message);
    return;
  }

  showLoading("正在下載行情並計算投資組合…");
  try {
    latestBacktest = await apiFetch("/api/backtest", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (latestBacktest.warning) setMessage(dom.backtestWarning, latestBacktest.warning);
    renderBacktestResults(latestBacktest);
    dom.backtestResults.classList.remove("hidden");
    dom.backtestResults.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setMessage(dom.backtestError, error.message);
    dom.backtestResults.classList.add("hidden");
  } finally {
    hideLoading();
  }
}

function renderBacktestResults(result) {
  const series = [...result.data];
  if (result.benchmark) series.push(result.benchmark);
  renderMetrics(series, result.benchmark?.name);
  renderChart(series, result.benchmark?.name);
}

function renderMetrics(series, benchmarkName) {
  const thead = createElement("thead");
  const headerRow = createElement("tr");
  headerRow.append(createElement("th", { text: "指標", scope: "col" }));
  series.forEach((item) => {
    headerRow.append(createElement("th", { text: item.name === benchmarkName ? `${item.name}（基準）` : item.name, scope: "col" }));
  });
  thead.append(headerRow);

  const tbody = createElement("tbody");
  METRICS.forEach(([key, label, type, className]) => {
    const row = createElement("tr");
    row.append(createElement("th", { text: label, scope: "row" }));
    series.forEach((item) => {
      row.append(createElement("td", { text: formatMetric(item[key], type), className }));
    });
    tbody.append(row);
  });
  dom.metricsTable.replaceChildren(thead, tbody);
}

function renderChart(series, benchmarkName) {
  const canvas = dom.chart;
  const context = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(600, Math.round(rect.width * dpr));
  canvas.height = Math.max(320, Math.round(rect.height * dpr));
  context.setTransform(dpr, 0, 0, dpr, 0, 0);

  const width = canvas.width / dpr;
  const height = canvas.height / dpr;
  const padding = { top: 20, right: 24, bottom: 42, left: 78 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const scaleMode = dom.chartScale.value;

  const prepared = series.map((item, index) => ({
    name: item.name,
    color: COLORS[index % COLORS.length],
    benchmark: item.name === benchmarkName,
    points: item.portfolioHistory
      .map((point) => ({ x: new Date(`${point.date}T00:00:00Z`).getTime(), y: Number(point.value) }))
      .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y) && point.y > 0),
  })).filter((item) => item.points.length);

  const allPoints = prepared.flatMap((item) => item.points);
  if (!allPoints.length) return;
  const minX = Math.min(...allPoints.map((point) => point.x));
  const maxX = Math.max(...allPoints.map((point) => point.x));
  const transformedValues = allPoints.map((point) => scaleMode === "log" ? Math.log10(point.y) : point.y);
  let minY = Math.min(...transformedValues);
  let maxY = Math.max(...transformedValues);
  const yPadding = Math.max((maxY - minY) * 0.08, scaleMode === "log" ? 0.03 : 1);
  minY -= yPadding;
  maxY += yPadding;

  const xPosition = (value) => padding.left + ((value - minX) / Math.max(maxX - minX, 1)) * plotWidth;
  const yPosition = (value) => {
    const transformed = scaleMode === "log" ? Math.log10(value) : value;
    return padding.top + (1 - (transformed - minY) / Math.max(maxY - minY, 1)) * plotHeight;
  };

  context.clearRect(0, 0, width, height);
  context.fillStyle = "#f8fafc";
  context.fillRect(0, 0, width, height);
  context.font = "12px system-ui";
  context.textBaseline = "middle";

  for (let index = 0; index <= 5; index += 1) {
    const ratio = index / 5;
    const y = padding.top + ratio * plotHeight;
    context.strokeStyle = "#dbe2ea";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();

    const transformed = maxY - ratio * (maxY - minY);
    const value = scaleMode === "log" ? 10 ** transformed : transformed;
    context.fillStyle = "#64748b";
    context.textAlign = "right";
    context.fillText(formatCurrency(value), padding.left - 10, y);
  }

  const yearFormatter = new Intl.DateTimeFormat("zh-TW", { year: "numeric" });
  for (let index = 0; index <= 5; index += 1) {
    const ratio = index / 5;
    const timestamp = minX + ratio * (maxX - minX);
    const x = padding.left + ratio * plotWidth;
    context.fillStyle = "#64748b";
    context.textAlign = "center";
    context.fillText(yearFormatter.format(new Date(timestamp)), x, height - 18);
  }

  prepared.forEach((item) => {
    context.strokeStyle = item.color;
    context.lineWidth = item.benchmark ? 2 : 2.5;
    context.setLineDash(item.benchmark ? [6, 5] : []);
    context.beginPath();
    item.points.forEach((point, index) => {
      const x = xPosition(point.x);
      const y = yPosition(point.y);
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    context.stroke();
    context.setLineDash([]);
  });

  dom.chartLegend.replaceChildren(...prepared.map((item) => createElement("span", { className: "legend-item" }, [
    createElement("span", { className: "legend-swatch", attributes: { style: `background:${item.color}` } }),
    createElement("span", { text: item.benchmark ? `${item.name}（基準）` : item.name }),
  ])));
}

function parseTickers(value) {
  return [...new Set(value.split(/[\s,;]+/).map(sanitizeTicker).filter(Boolean))];
}

function buildScanPayload(tickerOverride = null) {
  const tickers = tickerOverride || parseTickers(document.querySelector("#scan-tickers").value);
  if (!tickers.length) throw new Error("請至少輸入一個股票代碼。");
  const start = parsePeriod(document.querySelector("#scan-start-period").value);
  const end = parsePeriod(document.querySelector("#scan-end-period").value);
  if (start.year * 12 + start.month > end.year * 12 + end.month) throw new Error("結束月份必須晚於或等於起始月份。");
  const benchmark = sanitizeTicker(document.querySelector("#scan-benchmark").value);
  if (!benchmark) throw new Error("請指定比較基準，以完整計算 Beta 與 Alpha。");
  return {
    tickers,
    benchmark,
    startYear: start.year,
    startMonth: start.month,
    endYear: end.year,
    endMonth: end.month,
  };
}

function setScanProgress(completed, total, message) {
  const ratio = total ? Math.min(completed / total, 1) : 0;
  dom.scanProgress.classList.remove("hidden");
  dom.scanProgressBar.style.width = `${(ratio * 100).toFixed(1)}%`;
  dom.scanProgressLabel.textContent = message;
  dom.loadingMessage.textContent = message;
}

async function waitWithCancellation(durationMs) {
  const deadline = Date.now() + durationMs;
  while (Date.now() < deadline) {
    if (cancelRequested) throw new Error("請求已取消。");
    await new Promise((resolve) => setTimeout(resolve, Math.min(250, deadline - Date.now())));
  }
}

async function scanChunk(payload, tickers) {
  let lastError;
  for (let attempt = 1; attempt <= SCAN_REQUEST_RETRIES; attempt += 1) {
    if (cancelRequested) throw new Error("請求已取消。");
    try {
      return await apiFetch("/api/scan", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...payload, tickers }),
      }, 250_000);
    } catch (error) {
      lastError = error;
      if (
        cancelRequested
        || error.retryable === false
        || attempt === SCAN_REQUEST_RETRIES
      ) break;
      await waitWithCancellation(SCAN_RETRY_DELAYS_MS[attempt - 1]);
    }
  }
  throw lastError;
}

function scanMatchesLatestScreener(tickers) {
  if (!latestScreener?.candidates?.length) return false;
  const selected = new Set(latestScreener.candidates.map((candidate) => candidate.ticker));
  return tickers.every((ticker) => selected.has(ticker));
}

function createScanJob(payload) {
  const screenerContext = scanMatchesLatestScreener(payload.tickers)
    ? {
      universe: structuredClone(latestScreener.universe),
      fundamentalsAsOf: latestScreener.fundamentalsAsOf,
      funnel: structuredClone(latestScreener.funnel),
    }
    : null;
  return {
    version: 2,
    id: crypto.randomUUID(),
    status: "running",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    payload: structuredClone(payload),
    screenerContext,
    pending: [...payload.tickers],
    results: [],
    attempts: {},
    retryRound: 0,
  };
}

function saveScanJob(job) {
  job.updatedAt = new Date().toISOString();
  try {
    localStorage.setItem(SCAN_JOB_STORAGE_KEY, JSON.stringify(job));
  } catch (error) {
    console.warn("Unable to persist scan progress", error);
  }
}

function loadScanJob() {
  try {
    const job = JSON.parse(localStorage.getItem(SCAN_JOB_STORAGE_KEY));
    if (
      job?.version === 2
      && Array.isArray(job?.payload?.tickers)
      && job.payload.tickers.length
      && Array.isArray(job.pending)
      && Array.isArray(job.results)
    ) {
      const allowed = new Set(job.payload.tickers);
      const resultMap = new Map(
        job.results
          .filter((item) => item?.ticker && allowed.has(item.ticker))
          .map((item) => [item.ticker, item]),
      );
      job.results = job.payload.tickers
        .map((ticker) => resultMap.get(ticker))
        .filter(Boolean);
      const settled = new Set(job.results.map((item) => item.ticker));
      job.pending = job.payload.tickers.filter((ticker) => !settled.has(ticker));
      if (!job.pending.length) job.status = "completed";
      else if (job.status === "completed") job.status = "paused";
      job.attempts = job.attempts && typeof job.attempts === "object" ? job.attempts : {};
      return job;
    }
  } catch (error) {
    console.warn("Unable to restore scan progress", error);
  }
  return null;
}

function clearScanJob() {
  localStorage.removeItem(SCAN_JOB_STORAGE_KEY);
}

function restoreScanControls(payload) {
  document.querySelector("#scan-tickers").value = payload.tickers.join(", ");
  document.querySelector("#scan-start-period").value = `${payload.startYear}-${String(payload.startMonth).padStart(2, "0")}`;
  document.querySelector("#scan-end-period").value = `${payload.endYear}-${String(payload.endMonth).padStart(2, "0")}`;
  document.querySelector("#scan-benchmark").value = payload.benchmark;
}

function orderedJobResults(job, resultMap) {
  return job.payload.tickers.map((ticker) => resultMap.get(ticker)).filter(Boolean);
}

function terminalScanFailure(ticker, reason) {
  return {
    ticker,
    status: "failed",
    retryable: false,
    error_code: "scan_retry_budget_exhausted",
    error: reason,
    metric_definition_version: METRIC_DEFINITION_VERSION,
  };
}

function renderScanJobState(job, message) {
  const total = job.payload.tickers.length;
  const settled = job.results.length;
  latestScan = [...job.results];
  setScanProgress(settled, total, message || `已取得 ${settled} / ${total} 檔，未完成 ${job.pending.length} 檔`);
  renderScanTable();
  renderScanSummary();
  renderScanContext(Boolean(job.screenerContext));
  dom.scanResults.classList.remove("hidden");
}

async function processScanJob(job) {
  const resultMap = new Map(job.results.map((item) => [item.ticker, item]));
  let retryOnlyBatches = 0;

  while (job.pending.length && !cancelRequested) {
    const chunk = job.pending.splice(0, SCAN_CHUNK_SIZE);
    const firstPosition = resultMap.size + 1;
    const lastPosition = Math.min(resultMap.size + chunk.length, job.payload.tickers.length);
    setScanProgress(
      job.results.length,
      job.payload.tickers.length,
      `正在取得第 ${firstPosition}–${lastPosition} 檔；已完成 ${job.results.length} / ${job.payload.tickers.length} 檔`,
    );
    let response = [];
    let requestError = null;
    try {
      response = await scanChunk(job.payload, chunk);
    } catch (error) {
      if (error.retryable === false) throw error;
      requestError = error;
    }

    if (cancelRequested) {
      job.pending.unshift(...chunk);
      break;
    }

    const responseMap = new Map(
      (Array.isArray(response) ? response : [])
        .filter((item) => item?.ticker)
        .map((item) => [item.ticker, item]),
    );
    let newlySettled = 0;
    for (const ticker of chunk) {
      const item = responseMap.get(ticker);
      if (!requestError && item && item.retryable !== true && item.status !== "pending") {
        resultMap.set(ticker, item);
        newlySettled += 1;
        continue;
      }

      const attempts = Number(job.attempts[ticker] || 0) + 1;
      job.attempts[ticker] = attempts;
      if (attempts >= SCAN_MAX_TICKER_ATTEMPTS) {
        const detail = requestError?.message || item?.error || "行情服務未回傳可結算結果。";
        resultMap.set(
          ticker,
          terminalScanFailure(
            ticker,
            `行情服務連續 ${attempts} 輪未完成，已停止重試：${detail}`,
          ),
        );
        newlySettled += 1;
      } else {
        job.pending.push(ticker);
      }
    }

    job.results = orderedJobResults(job, resultMap);
    if (newlySettled) {
      retryOnlyBatches = 0;
      job.retryRound = 0;
    } else {
      retryOnlyBatches += 1;
    }
    job.status = "running";
    saveScanJob(job);
    renderScanJobState(
      job,
      requestError
        ? `行情服務暫時未完整回應；已保存 ${job.results.length} / ${job.payload.tickers.length} 檔，系統持續重試`
        : `已取得 ${job.results.length} / ${job.payload.tickers.length} 檔，未完成 ${job.pending.length} 檔`,
    );

    if (job.pending.length && retryOnlyBatches >= 2) {
      job.retryRound = Number(job.retryRound || 0) + 1;
      const delay = SCAN_RETRY_DELAYS_MS[
        Math.min(job.retryRound - 1, SCAN_RETRY_DELAYS_MS.length - 1)
      ];
      const seconds = Math.ceil(delay / 1000);
      retryOnlyBatches = 0;
      renderScanJobState(
        job,
        `上游暫時未完整回傳，${seconds} 秒後自動繼續；已取得 ${job.results.length} / ${job.payload.tickers.length} 檔`,
      );
      await waitWithCancellation(delay);
    }
  }
}

async function executeScan(payload, existingJob = null) {
  if (scanExecutionRunning) return;
  scanExecutionRunning = true;
  cancelRequested = false;
  setMessage(dom.scanError);
  const job = existingJob || createScanJob(payload);
  activeScanJob = job;
  job.status = "running";
  if (!existingJob) {
    latestScan = [];
    scanPage = 1;
  }
  restoreScanControls(job.payload);
  saveScanJob(job);
  showLoading(`準備循序取得 ${job.payload.tickers.length} 檔完整行情…`);
  renderScanJobState(
    job,
    `準備循序取得 ${job.results.length} / ${job.payload.tickers.length} 檔完整行情…`,
  );
  try {
    await processScanJob(job);
    if (cancelRequested) {
      job.status = "paused";
      saveScanJob(job);
      document.querySelector("#retry-scan").classList.remove("hidden");
      setMessage(dom.scanError, `回測已暫停；已保存 ${job.results.length} / ${job.payload.tickers.length} 檔，按「繼續未完成回測」即可接續。`);
    } else {
      job.status = "completed";
      job.pending = [];
      latestScan = [...job.results];
      saveScanJob(job);
      document.querySelector("#retry-scan").classList.add("hidden");
      renderScanJobState(job, `完整取得 ${job.results.length} / ${job.payload.tickers.length} 檔`);
      setMessage(dom.scanError);
      dom.scanResults.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (error) {
    if (error.retryable === false) {
      clearScanJob();
      activeScanJob = null;
      document.querySelector("#retry-scan").classList.add("hidden");
      setMessage(dom.scanError, error.message);
    } else {
      job.status = "paused";
      saveScanJob(job);
      document.querySelector("#retry-scan").classList.remove("hidden");
      setMessage(dom.scanError, cancelRequested
        ? `回測已暫停；已保存 ${job.results.length} / ${job.payload.tickers.length} 檔。`
        : `進度已保存；系統可由目前的 ${job.results.length} / ${job.payload.tickers.length} 檔接續。`);
    }
  } finally {
    hideLoading();
    scanExecutionRunning = false;
  }
}

async function runScan(event) {
  event.preventDefault();
  try {
    await executeScan(buildScanPayload());
  } catch (error) {
    setMessage(dom.scanError, error.message);
  }
}

async function retryIncompleteScan() {
  const job = activeScanJob?.pending?.length ? activeScanJob : loadScanJob();
  if (!job?.pending?.length) return;
  try {
    await executeScan(job.payload, job);
  } catch (error) {
    setMessage(dom.scanError, error.message);
  }
}

function restorePersistedScan() {
  const job = loadScanJob();
  if (!job) return;
  activeScanJob = job;
  latestScan = [...job.results];
  restoreScanControls(job.payload);
  renderScanJobState(
    job,
    `已還原 ${job.results.length} / ${job.payload.tickers.length} 檔，未完成 ${job.pending.length} 檔`,
  );
  document.querySelector("#retry-scan").classList.toggle("hidden", !job.pending.length);
  if (job.status === "running" && job.pending.length) {
    setTimeout(() => executeScan(job.payload, job), 0);
  }
}

function renderScanTable() {
  const sorted = [...latestScan].sort((left, right) => {
    if (left.error) return 1;
    if (right.error) return -1;
    const a = Number(left[scanSort.key]);
    const b = Number(right[scanSort.key]);
    return scanSort.direction === "asc" ? a - b : b - a;
  });
  const totalPages = Math.max(1, Math.ceil(sorted.length / scanPageSize));
  scanPage = Math.min(Math.max(scanPage, 1), totalPages);
  const pageStart = (scanPage - 1) * scanPageSize;
  const visibleRows = sorted.slice(pageStart, pageStart + scanPageSize);

  const columns = [
    ["ticker", "股票代碼", "text"],
    ...SCAN_METRICS.map(([key, label, type]) => [key, label, type]),
    ["data_range", "資料區間", "text"],
  ];
  const thead = createElement("thead");
  const headerRow = createElement("tr");
  columns.forEach(([key, label]) => {
    const indicator = scanSort.key === key ? (scanSort.direction === "asc" ? " ▲" : " ▼") : "";
    headerRow.append(createElement("th", {
      text: `${label}${indicator}`,
      scope: "col",
      className: ["ticker", "data_range"].includes(key) ? "" : "sortable",
      dataset: ["ticker", "data_range"].includes(key) ? {} : { sortKey: key },
    }));
  });
  thead.append(headerRow);

  const tbody = createElement("tbody");
  visibleRows.forEach((item) => {
    const row = createElement("tr");
    row.append(createElement("th", { text: item.note ? `${item.ticker} ${item.note}` : item.ticker, scope: "row" }));
    SCAN_METRICS.forEach(([key, , type, className], index) => {
      row.append(createElement("td", {
        text: item.error ? (index === 0 ? item.error : "—") : formatMetric(item[key], type),
        className: item.error ? "" : className,
      }));
    });
    row.append(createElement("td", {
      text: item.error ? "—" : `${item.data_start || "—"} ～ ${item.data_end || "—"}`,
    }));
    tbody.append(row);
  });
  dom.scanTable.replaceChildren(thead, tbody);
  dom.scanPagination.classList.toggle("hidden", sorted.length <= scanPageSize);
  dom.scanPageStatus.textContent = `第 ${scanPage.toLocaleString("zh-TW")} / ${totalPages.toLocaleString("zh-TW")} 頁`;
  dom.scanPagePrev.disabled = scanPage <= 1;
  dom.scanPageNext.disabled = scanPage >= totalPages;
}

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function renderScanSummary() {
  const valid = latestScan.filter((item) => !item.error && item.retryable !== true);
  const failed = latestScan.filter((item) => Boolean(item.error));
  const total = activeScanJob?.payload?.tickers?.length || latestScan.length;
  const unfinished = activeScanJob?.status === "completed"
    ? 0
    : Number(activeScanJob?.pending?.length || 0);
  const numeric = (key) => valid.map((item) => Number(item[key])).filter(Number.isFinite);
  const average = (key) => {
    const values = numeric(key);
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  };
  const cards = [
    ["成功標的", `${valid.length} / ${total}`],
    ["失敗標的", failed.length.toLocaleString("zh-TW")],
    ["未完成", unfinished.toLocaleString("zh-TW")],
    ["CAGR 中位數", formatMetric(median(numeric("cagr")), "percent")],
    ["平均波動率", formatMetric(average("volatility"), "percent")],
    ["平均最大回撤", formatMetric(average("mdd"), "percent")],
    ["平均 Sharpe", formatMetric(average("sharpe_ratio"), "number")],
    ["平均資料覆蓋", formatMetric(average("data_coverage"), "percent")],
  ];
  dom.scanSummary.replaceChildren(...cards.map(([label, value]) => createElement(
    "article",
    { className: "summary-card" },
    [
      createElement("span", { text: label }),
      createElement("strong", { text: value }),
    ],
  )));
}

function renderScanContext(showUniverse) {
  const context = activeScanJob?.screenerContext || latestScreener;
  if (!showUniverse || !context) {
    dom.scanContext.classList.add("hidden");
    dom.scanContext.textContent = "";
    return;
  }
  const { universe, fundamentalsAsOf, funnel } = context;
  dom.scanContext.textContent = [
    `Universe：${universe.name}`,
    `版本：${universe.version}`,
    `成分日：${universe.sourceAsOf || "未提供"}`,
    `基本面日：${fundamentalsAsOf || "未提供"}`,
    `漏斗：${funnel.universeCount} → ${funnel.fundamentalsAvailable} → ${funnel.passedFilters} → ${funnel.selectedForScan}`,
  ].join(" · ");
  dom.scanContext.classList.remove("hidden");
}

function selectedUniverse() {
  return universeCatalog.find((universe) => universe.id === dom.screenerIndex.value);
}

function renderUniverseMeta() {
  const universe = selectedUniverse();
  if (!universe) {
    dom.universeMeta.textContent = "目前沒有可用的 Universe；仍可在下方手動輸入股票代碼。";
    return;
  }
  const parts = [
    `來源：${universe.source.label}`,
    `成分日：${universe.sourceAsOf || "未提供"}`,
    `版本：${universe.version || "尚未建立"}`,
    `成分股：${Number(universe.memberCount || 0).toLocaleString("zh-TW")} 檔`,
  ];
  if (universe.warnings?.length) parts.push(...universe.warnings);
  dom.universeMeta.textContent = parts.join(" · ");
}

function renderScreenerFunnel(funnel) {
  const stages = [
    ["Universe", funnel.universeCount],
    ["具基本面", funnel.fundamentalsAvailable],
    ["通過條件", funnel.passedFilters],
    ["納入回測", funnel.selectedForScan],
  ];
  dom.screenerFunnel.replaceChildren(...stages.map(([label, value], index) => createElement(
    "article",
    { className: "funnel-card" },
    [
      createElement("span", { text: `步驟 ${index + 1}` }),
      createElement("strong", { text: Number(value).toLocaleString("zh-TW") }),
      createElement("small", { text: label }),
    ],
  )));
  dom.screenerFunnel.classList.remove("hidden");
}

async function runScreener() {
  setMessage(dom.scanError);
  setMessage(dom.screenerWarning);
  const universe = selectedUniverse();
  if (!universe?.available) {
    setMessage(dom.screenerWarning, "所選 Universe 尚無有效版本，請改用可用股票池或手動輸入代碼。");
    return;
  }
  const filters = {};
  const marketCap = Number(document.querySelector("#screener-market-cap").value);
  const maxPe = Number(document.querySelector("#screener-pe").value);
  if (Number.isFinite(marketCap) && marketCap > 0) filters.marketCap = { min: marketCap * 1e8 };
  if (Number.isFinite(maxPe) && maxPe > 0) filters.trailingPE = { max: maxPe };
  const rawLimit = document.querySelector("#screener-limit").value.trim();
  const limit = rawLimit ? Number(rawLimit) : null;
  if (limit != null && (!Number.isSafeInteger(limit) || limit < 1)) {
    setMessage(dom.scanError, "最多回測檔數必須是大於 0 的整數；留空則回測全部。");
    return;
  }

  showLoading("正在執行基本面預篩選…");
  try {
    latestScreener = await apiFetch("/api/v2/screener", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        universe: universe.id,
        sector: document.querySelector("#screener-sector").value,
        filters,
        limit,
        sort: document.querySelector("#screener-sort").value,
      }),
    });
    const tickers = latestScreener.candidates.map((candidate) => candidate.ticker);
    document.querySelector("#scan-tickers").value = tickers.join(", ");
    renderScreenerFunnel(latestScreener.funnel);
    setMessage(dom.screenerWarning, latestScreener.warnings?.join("\n") || "");
    if (!tickers.length) setMessage(dom.scanError, "沒有符合目前條件的股票。");
  } catch (error) {
    setMessage(dom.scanError, error.message);
  } finally {
    hideLoading();
  }
}

function downloadFile(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = createElement("a", { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function exportConfig() {
  syncSettings();
  downloadFile("backtest-config.json", JSON.stringify(state, null, 2), "application/json");
}

function exportResults() {
  if (!latestBacktest) return;
  downloadFile("backtest-results.json", JSON.stringify(latestBacktest, null, 2), "application/json");
}

function exportScan() {
  if (!latestScan.length) return;
  const headers = [
    "ticker",
    "total_return",
    "cagr",
    "volatility",
    "mdd",
    "sharpe_ratio",
    "sortino_ratio",
    "beta",
    "alpha",
    "data_coverage",
    "trading_days",
    "data_start",
    "data_end",
    "note",
    "error",
  ];
  const escapeCsv = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const lines = [headers.join(","), ...latestScan.map((item) => headers.map((key) => escapeCsv(item[key])).join(","))];
  downloadFile("scan-results.csv", `\ufeff${lines.join("\n")}`, "text/csv;charset=utf-8");
}

function switchTab(tabName) {
  dom.tabButtons.forEach((button) => {
    const active = button.dataset.tab === tabName;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  dom.tabPanels.forEach((panel) => panel.classList.toggle("hidden", panel.id !== `${tabName}-panel`));
}

async function checkHealth() {
  try {
    const result = await apiFetch("/api/health", {}, 8_000);
    dom.statusDot.className = "status-dot online";
    dom.serviceStatus.textContent = result.status === "ok" ? "服務正常" : "服務狀態未知";
  } catch {
    dom.statusDot.className = "status-dot offline";
    dom.serviceStatus.textContent = "後端未連線";
  }
}

async function loadTickerUniverse() {
  try {
    tickerUniverse = await apiFetch("/api/all-tickers", {}, 12_000);
    dom.tickerOptions.replaceChildren(...tickerUniverse.slice(0, 6000).map((ticker) => createElement("option", { value: ticker })));
  } catch {
    tickerUniverse = [];
  }
}

async function loadUniverses() {
  try {
    const response = await apiFetch("/api/v2/universes", {}, 12_000);
    universeCatalog = Array.isArray(response.data) ? response.data : [];
    dom.screenerIndex.replaceChildren(...universeCatalog.map((universe) => createElement(
      "option",
      {
        value: universe.id,
        text: `${universe.name}${universe.available ? ` · ${universe.memberCount} 檔` : " · 尚未更新"}`,
        disabled: !universe.available,
      },
    )));
    const firstAvailable = universeCatalog.find((universe) => universe.available);
    if (firstAvailable) dom.screenerIndex.value = firstAvailable.id;
    dom.universeStatus.textContent = firstAvailable
      ? `${universeCatalog.filter((item) => item.available).length} 個股票池可用`
      : "尚無有效 Universe";
    dom.universeStatus.classList.toggle("ready", Boolean(firstAvailable));
    document.querySelector("#run-screener").disabled = !firstAvailable;
    renderUniverseMeta();
  } catch (error) {
    universeCatalog = [];
    dom.screenerIndex.replaceChildren(createElement("option", {
      value: "",
      text: "Universe 暫時無法讀取",
    }));
    dom.universeStatus.textContent = "Universe 未連線";
    document.querySelector("#run-screener").disabled = true;
    dom.universeMeta.textContent = "Universe 功能暫時不可用；下方手動股票代碼掃描仍可正常使用。";
    setMessage(dom.screenerWarning, error.message);
  }
}

function bindEvents() {
  dom.tabButtons.forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.tab)));
  dom.portfolioList.addEventListener("input", handlePortfolioInput);
  dom.portfolioList.addEventListener("click", handlePortfolioClick);
  dom.backtestForm.addEventListener("submit", runBacktest);
  dom.scanForm.addEventListener("submit", runScan);
  document.querySelector("#run-screener").addEventListener("click", runScreener);
  document.querySelector("#add-portfolio").addEventListener("click", () => {
    if (state.portfolios.length >= 5) {
      setMessage(dom.backtestError, "最多只能建立 5 組投資組合。");
      return;
    }
    state.portfolios.push({
      id: crypto.randomUUID(),
      name: `投組 ${state.portfolios.length + 1}`,
      assets: [{ id: crypto.randomUUID(), ticker: "", weight: 100 }],
    });
    saveState();
    renderPortfolios();
  });
  document.querySelector("#save-config").addEventListener("click", () => {
    syncSettings();
    saveState();
    setMessage(dom.backtestError, "設定已儲存在此瀏覽器。重新整理後仍會保留。");
    dom.backtestError.classList.remove("error");
    setTimeout(() => {
      dom.backtestError.classList.add("error");
      setMessage(dom.backtestError);
    }, 2500);
  });
  document.querySelector("#export-config").addEventListener("click", exportConfig);
  document.querySelector("#export-results").addEventListener("click", exportResults);
  document.querySelector("#export-scan").addEventListener("click", exportScan);
  document.querySelector("#retry-scan").addEventListener("click", retryIncompleteScan);
  dom.screenerIndex.addEventListener("change", renderUniverseMeta);
  document.querySelector("#cancel-request").addEventListener("click", () => {
    cancelRequested = true;
    activeControllers.forEach((controller) => controller.abort("user"));
  });
  dom.chartScale.addEventListener("change", () => latestBacktest && renderBacktestResults(latestBacktest));
  dom.scanTable.addEventListener("click", (event) => {
    const header = event.target.closest("th[data-sort-key]");
    if (!header) return;
    const key = header.dataset.sortKey;
    if (scanSort.key === key) scanSort.direction = scanSort.direction === "asc" ? "desc" : "asc";
    else {
      scanSort.key = key;
      scanSort.direction = ["mdd", "volatility"].includes(key) ? "asc" : "desc";
    }
    scanPage = 1;
    renderScanTable();
  });
  dom.scanPagePrev.addEventListener("click", () => {
    scanPage = Math.max(1, scanPage - 1);
    renderScanTable();
  });
  dom.scanPageNext.addEventListener("click", () => {
    scanPage += 1;
    renderScanTable();
  });
  dom.scanPageSize.addEventListener("change", () => {
    scanPageSize = Number(dom.scanPageSize.value) || 100;
    scanPage = 1;
    renderScanTable();
  });
  window.addEventListener("resize", () => latestBacktest && renderBacktestResults(latestBacktest));
}

initializeControls();
renderPortfolios();
bindEvents();
checkHealth();
loadTickerUniverse();
loadUniverses();
restorePersistedScan();
