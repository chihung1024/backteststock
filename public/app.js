const STORAGE_KEY = "backteststock-state-v1";
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
const SCAN_CHUNK_SIZE = 25;
const SCAN_CONCURRENCY = 2;

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
let lastFailedScanTickers = [];
let universeCatalog = [];
let activeControllers = new Set();
let cancelRequested = false;
let scanSort = { key: "cagr", direction: "desc" };
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
  if (value == null || !Number.isFinite(Number(value))) return "N/A";
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
      throw new Error(payload.error || `HTTP ${response.status}`);
    }
    return payload;
  } catch (error) {
    if (controller.signal.aborted) {
      if (controller.signal.reason === "timeout") throw new Error("請求逾時，請縮小日期或股票範圍後重試。");
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
  if (tickers.length > 100) throw new Error("整批最多掃描 100 檔股票。");
  const start = parsePeriod(document.querySelector("#scan-start-period").value);
  const end = parsePeriod(document.querySelector("#scan-end-period").value);
  if (start.year * 12 + start.month > end.year * 12 + end.month) throw new Error("結束月份必須晚於或等於起始月份。");
  return {
    tickers,
    benchmark: sanitizeTicker(document.querySelector("#scan-benchmark").value),
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

async function scanChunk(payload, tickers) {
  let lastError;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    if (cancelRequested) throw new Error("請求已取消。");
    try {
      return await apiFetch("/api/scan", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...payload, tickers }),
      }, 70_000);
    } catch (error) {
      lastError = error;
      if (cancelRequested || attempt === 2) break;
    }
  }
  throw lastError;
}

async function scanInBatches(payload) {
  const chunks = [];
  for (let index = 0; index < payload.tickers.length; index += SCAN_CHUNK_SIZE) {
    chunks.push(payload.tickers.slice(index, index + SCAN_CHUNK_SIZE));
  }

  const results = [];
  const failedTickers = [];
  let nextChunk = 0;
  let completedTickers = 0;

  async function worker() {
    while (!cancelRequested) {
      const chunkIndex = nextChunk;
      nextChunk += 1;
      if (chunkIndex >= chunks.length) return;
      const chunk = chunks[chunkIndex];
      try {
        results.push(...await scanChunk(payload, chunk));
      } catch (error) {
        if (cancelRequested) return;
        failedTickers.push(...chunk);
        results.push(...chunk.map((ticker) => ({
          ticker,
          error: `批次重試失敗：${error.message}`,
        })));
      } finally {
        completedTickers += chunk.length;
        setScanProgress(
          completedTickers,
          payload.tickers.length,
          `已完成 ${completedTickers} / ${payload.tickers.length} 檔`,
        );
      }
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(SCAN_CONCURRENCY, chunks.length) }, () => worker()),
  );
  if (cancelRequested) throw new Error("請求已取消。");
  return { results, failedTickers };
}

function scanMatchesLatestScreener(tickers) {
  if (!latestScreener?.candidates?.length) return false;
  const selected = new Set(latestScreener.candidates.map((candidate) => candidate.ticker));
  return tickers.every((ticker) => selected.has(ticker));
}

async function executeScan(payload, mergeResults = false) {
  cancelRequested = false;
  setMessage(dom.scanError);
  showLoading(`準備分批掃描 ${payload.tickers.length} 檔股票…`);
  setScanProgress(0, payload.tickers.length, `準備分批掃描 ${payload.tickers.length} 檔股票…`);
  try {
    const { results, failedTickers } = await scanInBatches(payload);
    lastFailedScanTickers = failedTickers;
    document.querySelector("#retry-scan").classList.toggle("hidden", !failedTickers.length);

    if (mergeResults) {
      const byTicker = new Map(latestScan.map((item) => [item.ticker, item]));
      results.forEach((item) => byTicker.set(item.ticker, item));
      latestScan = [...byTicker.values()];
    } else {
      latestScan = results;
    }
    renderScanTable();
    renderScanSummary();
    renderScanContext(scanMatchesLatestScreener(payload.tickers));
    dom.scanResults.classList.remove("hidden");
    if (failedTickers.length) {
      setMessage(
        dom.scanError,
        `${failedTickers.length} 檔所在批次重試後仍失敗，可使用「重試失敗標的」。`,
      );
    }
    dom.scanResults.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setMessage(dom.scanError, error.message);
    if (!mergeResults) dom.scanResults.classList.add("hidden");
  } finally {
    hideLoading();
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

async function retryFailedScan() {
  if (!lastFailedScanTickers.length) return;
  try {
    await executeScan(buildScanPayload(lastFailedScanTickers), true);
  } catch (error) {
    setMessage(dom.scanError, error.message);
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
  sorted.forEach((item) => {
    const row = createElement("tr");
    row.append(createElement("th", { text: item.note ? `${item.ticker} ${item.note}` : item.ticker, scope: "row" }));
    SCAN_METRICS.forEach(([key, , type, className], index) => {
      row.append(createElement("td", {
        text: item.error ? (index === 0 ? item.error : "—") : formatMetric(item[key], type),
        className: item.error ? "" : className,
      }));
    });
    row.append(createElement("td", {
      text: item.error ? "—" : `${item.data_start || "N/A"} ～ ${item.data_end || "N/A"}`,
    }));
    tbody.append(row);
  });
  dom.scanTable.replaceChildren(thead, tbody);
}

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function renderScanSummary() {
  const valid = latestScan.filter((item) => !item.error);
  const numeric = (key) => valid.map((item) => Number(item[key])).filter(Number.isFinite);
  const average = (key) => {
    const values = numeric(key);
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  };
  const cards = [
    ["成功標的", `${valid.length} / ${latestScan.length}`],
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
  if (!showUniverse || !latestScreener) {
    dom.scanContext.classList.add("hidden");
    dom.scanContext.textContent = "";
    return;
  }
  const { universe, fundamentalsAsOf, funnel } = latestScreener;
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

  showLoading("正在執行基本面預篩選…");
  try {
    latestScreener = await apiFetch("/api/v2/screener", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        universe: universe.id,
        sector: document.querySelector("#screener-sector").value,
        filters,
        limit: Number(document.querySelector("#screener-limit").value),
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
  document.querySelector("#retry-scan").addEventListener("click", retryFailedScan);
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
