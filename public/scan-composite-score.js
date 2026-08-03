import {
  SCORE_FORMULAS,
  buildScoreMatrix,
  normalizeScoreTicker,
  scoreRecordFor,
} from "./scan-score-formulas.js?v=20260803.4";
import {
  DEFAULT_SCAN_MIN_COVERAGE_PERCENT,
  buildScanCoverageStats,
  normalizeScanMinCoveragePercent,
} from "./scan-coverage.js?v=20260803.2";

const TABLE_SELECTOR = "#scan-table";
const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v3";
const MANUAL_SELECTION_KEY = "backteststock-optimizer-manual-selection-v2";

let observer;
let updateScheduled = false;
let activeSortKey = "cagr";
let activeSortDirection = "desc";
let backtestDialog = null;
let integratedBacktestButton = null;
let integratedPortfolioRows = [];
let integratedPortfolioSourceJobId = null;
const baseFetch = window.fetch.bind(window);

function readJson(storage, key, fallback = null) {
  try {
    const value = JSON.parse(storage.getItem(key));
    return value == null ? fallback : value;
  } catch {
    return fallback;
  }
}

function requestPath(input) {
  try {
    const value = typeof input === "string" || input instanceof URL ? input : input?.url;
    return new URL(value, window.location.href).pathname;
  } catch {
    return "";
  }
}

function readScanJob() {
  const job = readJson(localStorage, SCAN_JOB_STORAGE_KEY, null);
  return job && Array.isArray(job.results) ? job : null;
}

function currentThreshold() {
  const value = document.querySelector("#scan-min-coverage")?.value;
  return normalizeScanMinCoveragePercent(
    value,
    DEFAULT_SCAN_MIN_COVERAGE_PERCENT,
  );
}

function currentCoverageStats() {
  return buildScanCoverageStats(readScanJob()?.results || [], currentThreshold());
}

function selectedTickers(stats = currentCoverageStats()) {
  const job = readScanJob();
  const selection = readJson(localStorage, MANUAL_SELECTION_KEY, null);
  if (
    !job?.id
    || selection?.sourceJobId !== job.id
    || !Array.isArray(selection?.tickers)
  ) {
    return [];
  }

  const benchmark = normalizeScoreTicker(job.payload?.benchmark);
  const selectable = new Set(
    stats.shown
      .map((item) => normalizeScoreTicker(item?.ticker))
      .filter((ticker) => ticker && ticker !== benchmark),
  );
  return [...new Set(
    selection.tickers
      .map(normalizeScoreTicker)
      .filter((ticker) => selectable.has(ticker)),
  )];
}

function savedPortfolioRows() {
  const currentJobId = readScanJob()?.id || null;
  if (integratedPortfolioSourceJobId !== currentJobId) {
    integratedPortfolioRows = [];
    integratedPortfolioSourceJobId = null;
  }
  return integratedPortfolioRows;
}

function savePortfolioRows(rows) {
  integratedPortfolioRows = Array.isArray(rows) ? rows : [];
  integratedPortfolioSourceJobId = readScanJob()?.id || null;
}

function formatPercent(value) {
  return Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(2)}%` : "—";
}

function formatNumber(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(2) : "—";
}

function formatInteger(value) {
  return Number.isFinite(Number(value))
    ? Math.round(Number(value)).toLocaleString("zh-TW")
    : "—";
}

function median(values) {
  const finite = values.map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (!finite.length) return null;
  const middle = Math.floor(finite.length / 2);
  return finite.length % 2
    ? finite[middle]
    : (finite[middle - 1] + finite[middle]) / 2;
}

function average(values) {
  const finite = values.map(Number).filter(Number.isFinite);
  return finite.length
    ? finite.reduce((sum, value) => sum + value, 0) / finite.length
    : null;
}

function normalizedHeader(value) {
  return String(value || "").replace(/\s+[▲▼]$/u, "").trim();
}

function injectStyles() {
  if (document.querySelector("#unified-performance-styles")) return;
  const style = document.createElement("style");
  style.id = "unified-performance-styles";
  style.textContent = `
    .scan-control-stack { display:grid; gap:.75rem; margin:0 0 1rem; }
    .scan-control-row { display:flex; align-items:center; gap:.65rem; flex-wrap:wrap; padding:.75rem .85rem; border:1px solid var(--border); border-radius:11px; background:var(--surface-subtle); }
    .scan-control-row .scan-coverage-filter { display:flex; align-items:center; grid-template-columns:none; }
    .scan-control-row .scan-coverage-filter-status { flex:1 1 26rem; white-space:normal; }
    .scan-control-row .optimizer-manual-selection-status { margin-right:auto; white-space:normal; }
    .scan-result-export-actions { justify-content:flex-end; }
    .integrated-backtest-dialog { width:min(1480px,96vw); max-width:none; height:min(92vh,1100px); padding:0; border:0; border-radius:16px; background:var(--bg); box-shadow:0 28px 80px rgb(15 23 42 / .32); }
    .integrated-backtest-dialog::backdrop { background:rgb(15 23 42 / .56); }
    .integrated-backtest-shell { height:100%; overflow:auto; padding:1rem; }
    .integrated-backtest-dialog-toolbar { position:sticky; top:0; z-index:20; display:flex; justify-content:flex-end; padding:.25rem 0 .75rem; background:linear-gradient(var(--bg) 75%, transparent); }
    .integrated-backtest-dialog #backtest-panel { display:block !important; }
    .integrated-portfolio-row { background:#eef6ff; }
    .integrated-portfolio-row th:first-child { min-width:190px !important; }
    .integrated-portfolio-name { display:block; font-weight:850; color:var(--primary-dark); }
    .integrated-portfolio-meta { display:block; margin-top:.25rem; font-size:.7rem; color:var(--muted); white-space:normal; }
    .integrated-portfolio-action { margin-top:.4rem; }
    #scan-table th[data-composite-metric], #scan-table td[data-composite-metric] { min-width:132px; }
    #scan-table { min-width:1740px; }
    .coverage-definition-note { margin-top:.55rem; color:var(--muted); font-size:.78rem; }
    @media (max-width:640px) {
      .scan-control-row { align-items:stretch; flex-direction:column; }
      .scan-control-row .button, .scan-control-row a.button { width:100%; text-align:center; }
      .integrated-backtest-dialog { width:100vw; height:100vh; border-radius:0; }
      .integrated-backtest-shell { padding:.75rem; }
    }
  `;
  document.head.append(style);
}

function ensureBacktestDialog() {
  if (backtestDialog?.isConnected) return backtestDialog;
  const backtestPanel = document.querySelector("#backtest-panel");
  if (!backtestPanel) return null;

  backtestDialog = document.createElement("dialog");
  backtestDialog.id = "integrated-backtest-dialog";
  backtestDialog.className = "integrated-backtest-dialog";
  backtestDialog.setAttribute("aria-label", "投資組合回測建立器");

  const shell = document.createElement("div");
  shell.className = "integrated-backtest-shell";
  const toolbar = document.createElement("div");
  toolbar.className = "integrated-backtest-dialog-toolbar";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "button ghost";
  close.textContent = "關閉並返回績效列表";
  close.addEventListener("click", () => backtestDialog.close());
  toolbar.append(close);

  backtestPanel.classList.remove("hidden");
  shell.append(toolbar, backtestPanel);
  backtestDialog.append(shell);
  document.body.append(backtestDialog);
  return backtestDialog;
}

function activateResearchWorkspace() {
  const scannerButton = document.querySelector('.tab-button[data-tab="scanner"]');
  const backtestButton = document.querySelector('.tab-button[data-tab="backtest"]');
  if (scannerButton) {
    scannerButton.textContent = "績效研究（個股掃描）";
    if (!scannerButton.classList.contains("active")) scannerButton.click();
  }

  ensureBacktestDialog();
  if (backtestButton && backtestButton.dataset.integratedLauncher !== "true") {
    backtestButton.dataset.integratedLauncher = "true";
    backtestButton.classList.remove("active");
    backtestButton.setAttribute("aria-selected", "false");
    backtestButton.title = "由績效列表選取股票後開啟，亦可直接使用既有設定。";
    backtestButton.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      openBacktestDialog({ useSelection: false });
    }, true);
  }
}

function dispatchInput(element) {
  element.dispatchEvent(new Event("input", { bubbles: true }));
}

function prepareEqualWeightPortfolio(tickers) {
  if (!tickers.length) return;
  const list = document.querySelector("#portfolio-list");
  if (!list) return;

  while (list.querySelectorAll(".portfolio-card").length > 1) {
    const cards = [...list.querySelectorAll(".portfolio-card")];
    cards.at(-1)?.querySelector('button[data-action="remove-portfolio"]')?.click();
  }

  let card = list.querySelector(".portfolio-card");
  if (!card) return;
  while (card.querySelectorAll(".asset-row").length > 1) {
    card.querySelectorAll('.asset-row button[data-action="remove-asset"]')?.item(
      card.querySelectorAll(".asset-row").length - 1,
    )?.click();
    card = list.querySelector(".portfolio-card");
  }
  while (card.querySelectorAll(".asset-row").length < tickers.length) {
    card.querySelector('button[data-action="add-asset"]')?.click();
    card = list.querySelector(".portfolio-card");
  }

  const nameInput = card.querySelector('input[data-action="portfolio-name"]');
  if (nameInput) {
    nameInput.value = "績效列表已選標的等權組合";
    dispatchInput(nameInput);
  }

  tickers.forEach((ticker, index) => {
    const rows = list.querySelectorAll(".portfolio-card .asset-row");
    const input = rows.item(index)?.querySelector('input[data-action="asset-ticker"]');
    if (input) {
      input.value = ticker;
      dispatchInput(input);
    }
  });

  const baseWeight = Math.floor((100 / tickers.length) * 100) / 100;
  tickers.forEach((ticker, index) => {
    const rows = list.querySelectorAll(".portfolio-card .asset-row");
    const input = rows.item(index)?.querySelector('input[data-action="asset-weight"]');
    if (!input) return;
    const weight = index === tickers.length - 1
      ? Number((100 - baseWeight * (tickers.length - 1)).toFixed(2))
      : baseWeight;
    input.value = String(weight);
    dispatchInput(input);
  });

  const job = readScanJob();
  if (job?.payload) {
    const values = {
      "#start-period": job.payload.startDate,
      "#end-period": job.payload.endDate,
      "#benchmark": job.payload.benchmark,
    };
    for (const [selector, value] of Object.entries(values)) {
      const input = document.querySelector(selector);
      if (input && value) input.value = value;
    }
  }
}

function openBacktestDialog({ useSelection = true } = {}) {
  const dialog = ensureBacktestDialog();
  if (!dialog) return;
  const backtestPanel = document.querySelector("#backtest-panel");
  backtestPanel?.classList.remove("hidden");
  if (useSelection) {
    const tickers = selectedTickers();
    if (!tickers.length) return;
    prepareEqualWeightPortfolio(tickers);
  }
  if (!dialog.open) dialog.showModal();
}

function ensureResultControls() {
  const results = document.querySelector("#scan-results");
  const header = results?.querySelector(":scope > .result-header");
  const toolbar = header?.querySelector(".toolbar");
  if (!results || !header || !toolbar) return;

  header.querySelector("h3")?.replaceChildren(document.createTextNode("績效列表"));
  toolbar.classList.add("scan-result-export-actions");

  let stack = results.querySelector(":scope > .scan-control-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "scan-control-stack";
    header.insertAdjacentElement("afterend", stack);
  }

  let coverageRow = stack.querySelector(".scan-coverage-row");
  if (!coverageRow) {
    coverageRow = document.createElement("div");
    coverageRow.className = "scan-control-row scan-coverage-row";
    stack.append(coverageRow);
  }
  let actionRow = stack.querySelector(".scan-action-row");
  if (!actionRow) {
    actionRow = document.createElement("div");
    actionRow.className = "scan-control-row scan-action-row";
    stack.append(actionRow);
  }

  const exportIds = new Set(["export-scan", "export-scan-audit"]);
  [...toolbar.children].forEach((element) => {
    if (!exportIds.has(element.id)) {
      if (element.matches(".scan-coverage-filter, #scan-coverage-filter-status")) {
        coverageRow.append(element);
      } else {
        actionRow.append(element);
      }
    }
  });

  const coverageFilter = document.querySelector("#scan-min-coverage")?.closest(".scan-coverage-filter");
  const coverageStatus = document.querySelector("#scan-coverage-filter-status");
  if (coverageFilter && coverageFilter.parentElement !== coverageRow) coverageRow.append(coverageFilter);
  if (coverageStatus && coverageStatus.parentElement !== coverageRow) coverageRow.append(coverageStatus);

  for (const id of [
    "optimizer-manual-selection-status",
    "clear-optimizer-selection",
    "open-manual-optimizer",
    "open-optimizer",
  ]) {
    const element = document.querySelector(`#${id}`);
    if (element && element.parentElement !== actionRow) actionRow.append(element);
  }

  integratedBacktestButton = document.querySelector("#open-integrated-backtest");
  if (!integratedBacktestButton) {
    integratedBacktestButton = document.createElement("button");
    integratedBacktestButton.id = "open-integrated-backtest";
    integratedBacktestButton.type = "button";
    integratedBacktestButton.className = "button primary";
    integratedBacktestButton.textContent = "建立投資組合回測";
    integratedBacktestButton.addEventListener("click", () => (
      openBacktestDialog({ useSelection: true })
    ));
    actionRow.insertBefore(integratedBacktestButton, actionRow.querySelector("#open-manual-optimizer"));
  }

  const note = coverageRow.querySelector(".coverage-definition-note") || document.createElement("span");
  note.className = "coverage-definition-note";
  note.textContent = "資料覆蓋率＝個股有效交易日 ÷ 本次掃描成功標的最大交易日。";
  if (!note.isConnected) coverageRow.append(note);
}

function formatScore(record, formula) {
  if (!Number.isFinite(record?.score)) return "—";
  const rank = Number.isInteger(record.rank) ? `#${record.rank}` : "#—";
  return `${rank} · ${Number(record.score).toFixed(formula.digits)}`;
}

function ensureFormulaDetails() {
  const tableWrap = document.querySelector(TABLE_SELECTOR)?.closest(".table-wrap");
  if (!tableWrap) return;
  let details = document.querySelector("#score-formula-comparison");
  if (!details || details.tagName !== "DETAILS") {
    details?.remove();
    details = document.createElement("details");
    details.id = "score-formula-comparison";
    details.className = "result-context score-formula-details";
    tableWrap.insertAdjacentElement("beforebegin", details);
  }
  const summary = document.createElement("summary");
  summary.textContent = "分數公式與排名說明";
  const list = document.createElement("ul");
  SCORE_FORMULAS.forEach((formula) => {
    const item = document.createElement("li");
    item.textContent = `${formula.shortLabel}：${formula.description}`;
    list.append(item);
  });
  const note = document.createElement("p");
  note.textContent = "每格顯示「名次 · 分數」；排名母體為目前符合資料覆蓋率門檻的股票。優化分數已自績效列表移除。";
  details.replaceChildren(summary, list, note);
}

function removeInjectedColumns(table, headerRow) {
  [...headerRow.querySelectorAll("th[data-composite-metric]")].forEach((cell) => cell.remove());
  [...table.querySelectorAll("td[data-composite-metric]")].forEach((cell) => cell.remove());
  [...table.querySelectorAll("tr.integrated-portfolio-row")].forEach((row) => row.remove());
}

function injectScoreColumns(table, stats) {
  const headerRow = table?.tHead?.rows?.[0];
  if (!table || !headerRow) return null;
  removeInjectedColumns(table, headerRow);

  const originalHeaders = [...headerRow.cells];
  const alphaIndex = originalHeaders.findIndex((cell) => normalizedHeader(cell.textContent) === "Alpha");
  if (alphaIndex < 0) return null;

  const matrix = buildScoreMatrix(stats.shown);
  let headerAnchor = originalHeaders[alphaIndex];
  SCORE_FORMULAS.forEach((formula) => {
    const header = document.createElement("th");
    header.scope = "col";
    header.dataset.compositeMetric = formula.key;
    header.dataset.sortKey = formula.key;
    header.className = "sortable";
    const indicator = activeSortKey === formula.key
      ? (activeSortDirection === "asc" ? " ▲" : " ▼")
      : "";
    header.textContent = `${formula.label}${indicator}`;
    header.title = `${formula.description}；點擊依原始分數排序。`;
    header.setAttribute(
      "aria-sort",
      activeSortKey === formula.key
        ? (activeSortDirection === "asc" ? "ascending" : "descending")
        : "none",
    );
    headerAnchor.insertAdjacentElement("afterend", header);
    headerAnchor = header;
  });

  [...(table.tBodies[0]?.rows || [])].forEach((row) => {
    if (row.dataset.scanEmpty === "true") return;
    const originalCells = [...row.cells];
    if (originalCells.length <= alphaIndex) return;
    const ticker = normalizeScoreTicker(
      row.dataset.ticker
      || originalCells[0]?.dataset?.ticker
      || originalCells[0]?.textContent,
    );
    let anchor = originalCells[alphaIndex];
    SCORE_FORMULAS.forEach((formula) => {
      const record = scoreRecordFor(matrix, ticker, formula.key);
      const cell = document.createElement("td");
      cell.dataset.compositeMetric = formula.key;
      cell.textContent = formatScore(record, formula);
      if (Number.isFinite(record?.score)) {
        cell.classList.add(record.score >= 0 ? "positive" : "negative");
      }
      cell.title = record?.reason || formula.description;
      anchor.insertAdjacentElement("afterend", cell);
      anchor = cell;
    });
  });
  return matrix;
}

function portfolioMetricCell(record, label, stats, matrix) {
  const normalized = normalizedHeader(label);
  const mapping = {
    "候選": "投組",
    "區間總報酬": formatPercent(record.total_return),
    "年化報酬率": formatPercent(record.cagr),
    "年化波動率": formatPercent(record.volatility),
    "最大回撤": formatPercent(record.mdd),
    "Sharpe": formatNumber(record.sharpe_ratio),
    "Sortino": formatNumber(record.sortino_ratio),
    "Beta": formatNumber(record.beta),
    "Alpha": formatPercent(record.alpha),
    "資料覆蓋率": formatPercent(
      stats.maximumTradingDays > 0
        ? Math.min(Number(record.trading_days || 0) / stats.maximumTradingDays, 1)
        : null,
    ),
    "交易日": formatInteger(record.trading_days),
    "資料區間": `${record.data_start || "—"} ～ ${record.data_end || "—"}`,
  };
  if (Object.hasOwn(mapping, normalized)) return mapping[normalized];
  const formula = SCORE_FORMULAS.find((item) => item.label === normalized);
  if (formula) {
    const score = scoreRecordFor(matrix, record.ticker, formula.key);
    return Number.isFinite(score?.score) ? Number(score.score).toFixed(formula.digits) : "—";
  }
  return "—";
}

function renderPortfolioRows(table, stats) {
  const records = savedPortfolioRows();
  if (!records.length || !table?.tBodies?.[0] || !table?.tHead?.rows?.[0]) return;
  const headers = [...table.tHead.rows[0].cells];
  const matrix = buildScoreMatrix(records);

  [...records].reverse().forEach((record) => {
    const row = document.createElement("tr");
    row.className = "integrated-portfolio-row";
    row.dataset.ticker = record.ticker;
    headers.forEach((header, index) => {
      if (index === 0) {
        const cell = document.createElement("th");
        cell.scope = "row";
        const name = document.createElement("span");
        name.className = "integrated-portfolio-name";
        name.textContent = `投組｜${record.name}`;
        const meta = document.createElement("small");
        meta.className = "integrated-portfolio-meta";
        meta.textContent = "由績效列表整合回測";
        const action = document.createElement("button");
        action.type = "button";
        action.className = "button ghost compact integrated-portfolio-action";
        action.textContent = "查看走勢與明細";
        action.addEventListener("click", () => openBacktestDialog({ useSelection: false }));
        cell.append(name, meta, action);
        row.append(cell);
      } else {
        const cell = document.createElement("td");
        cell.textContent = portfolioMetricCell(record, header.textContent, stats, matrix);
        row.append(cell);
      }
    });
    table.tBodies[0].prepend(row);
  });
}

function renderSummary(stats) {
  const summary = document.querySelector("#scan-summary");
  const job = readScanJob();
  if (!summary || !job) return;

  const raw = job.results || [];
  const failed = raw.filter((item) => Boolean(item?.error));
  const total = job.payload?.tickers?.length || raw.length;
  const unfinished = job.status === "completed" ? 0 : Number(job.pending?.length || 0);
  const shown = stats.shown;
  const cards = [
    ["成功標的", `${stats.settled.length} / ${total}`],
    ["失敗標的", failed.length.toLocaleString("zh-TW")],
    ["未完成", unfinished.toLocaleString("zh-TW")],
    ["CAGR 中位數", formatPercent(median(shown.map((item) => item.cagr)))],
    ["平均波動率", formatPercent(average(shown.map((item) => item.volatility)))],
    ["平均最大回撤", formatPercent(average(shown.map((item) => item.mdd)))],
    ["平均 Sharpe", formatNumber(average(shown.map((item) => item.sharpe_ratio)))],
    ["覆蓋率中位數", formatPercent(median(shown.map((item) => item.data_coverage)))],
    ["符合覆蓋率門檻", `${stats.shown.length} / ${stats.settled.length}`],
    ["基準交易日", formatInteger(stats.maximumTradingDays)],
  ];
  summary.replaceChildren(...cards.map(([label, value]) => {
    const article = document.createElement("article");
    article.className = "summary-card";
    const span = document.createElement("span");
    span.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = value;
    article.append(span, strong);
    return article;
  }));
  summary.dataset.integratedSummary = "true";

  const status = document.querySelector("#scan-coverage-filter-status");
  if (status) {
    const threshold = Number(currentThreshold()).toLocaleString("zh-TW", { maximumFractionDigits: 1 });
    status.textContent = [
      `顯示 ${stats.shown.length.toLocaleString("zh-TW")} / ${stats.settled.length.toLocaleString("zh-TW")} 檔`,
      `門檻 ≥ ${threshold}%`,
      stats.hidden ? `隱藏 ${stats.hidden.toLocaleString("zh-TW")} 檔` : "沒有低覆蓋率標的",
      `基準交易日 ${formatInteger(stats.maximumTradingDays)}`,
    ].join(" · ");
  }
}

function updateSelectionControls() {
  const count = selectedTickers().length;
  if (integratedBacktestButton) {
    integratedBacktestButton.disabled = count < 1;
    integratedBacktestButton.textContent = count
      ? `使用已選 ${count.toLocaleString("zh-TW")} 檔建立投組回測`
      : "建立投資組合回測";
  }
}

function updateMethodology() {
  const about = document.querySelector("#about-panel");
  if (!about) return;
  const formulaParagraph = [...about.querySelectorAll("p")].find((paragraph) => (
    paragraph.textContent.includes("個股績效列表")
    && paragraph.textContent.includes("Sortino")
  ));
  if (formulaParagraph) {
    formulaParagraph.textContent = [
      "個股績效列表顯示三種可排序分數：",
      "穩健公式 Sortino × √((1 + CAGR) ÷ (1 + Beta))、",
      "成長公式 Sortino × √(1 + CAGR) ÷ (1 + Beta)^0.25，",
      "以及回撤控制公式 Sortino × √((1 + CAGR) ÷ ((1 + Beta) × (1 + |最大回撤|)))。",
      "優化分數已自績效列表移除；Alpha 固定緊接 Beta。",
    ].join("");
  }

  if (!about.querySelector("#coverage-methodology-note")) {
    const panel = about.querySelector(".panel");
    if (panel) {
      const note = document.createElement("p");
      note.id = "coverage-methodology-note";
      note.textContent = "資料覆蓋率以同一次掃描成功標的中的最大有效交易日為分母；不同批次一律在瀏覽器工作層統一重算，不使用個股自身期間或單一 API 批次作分母。";
      panel.append(note);
    }
  }
}

function captureBacktestResult(payload) {
  if (!payload || !Array.isArray(payload.data)) return;
  const capturedAt = new Date().toISOString();
  const rows = payload.data.map((item, index) => {
    const history = Array.isArray(item?.portfolioHistory) ? item.portfolioHistory : [];
    const name = String(item?.name || `投資組合 ${index + 1}`).trim();
    return {
      ticker: `PORTFOLIO-${normalizeScoreTicker(name).replace(/[^A-Z0-9_-]/g, "").slice(0, 24) || index + 1}`,
      name,
      type: "portfolio",
      total_return: item?.total_return,
      cagr: item?.cagr,
      volatility: item?.volatility,
      mdd: item?.mdd,
      sharpe_ratio: item?.sharpe_ratio,
      sortino_ratio: item?.sortino_ratio,
      beta: item?.beta,
      alpha: item?.alpha,
      trading_days: history.length,
      data_start: history[0]?.date || null,
      data_end: history.at(-1)?.date || null,
      captured_at: capturedAt,
    };
  });
  savePortfolioRows(rows);
  scheduleUpdate();
}

window.fetch = async function fetchWithIntegratedPortfolioCapture(input, init) {
  const response = await baseFetch(input, init);
  if (response.ok && requestPath(input) === "/api/backtest") {
    response.clone().json().then(captureBacktestResult).catch(() => {});
  }
  return response;
};

function updatePerformanceList() {
  activateResearchWorkspace();
  ensureResultControls();
  const stats = currentCoverageStats();
  const table = document.querySelector(TABLE_SELECTOR);
  if (table?.tHead?.rows?.[0]) {
    injectScoreColumns(table, stats);
    renderPortfolioRows(table, stats);
    ensureFormulaDetails();
  }
  renderSummary(stats);
  updateSelectionControls();
  updateMethodology();
}

function scheduleUpdate() {
  if (updateScheduled) return;
  updateScheduled = true;
  requestAnimationFrame(() => {
    updateScheduled = false;
    observer?.disconnect();
    try {
      updatePerformanceList();
    } finally {
      observer?.observe(document.body, { childList: true, subtree: true });
    }
  });
}

function handleSortChange(event) {
  const key = String(event.detail?.key || "");
  if (!key) return;
  activeSortKey = key;
  activeSortDirection = event.detail?.direction === "asc" ? "asc" : "desc";
  scheduleUpdate();
}

function initialize() {
  injectStyles();
  activateResearchWorkspace();
  ensureResultControls();
  document.addEventListener("backteststock:scan-sort-change", handleSortChange);
  document.querySelector("#scan-min-coverage")?.addEventListener("input", scheduleUpdate);
  window.addEventListener("storage", scheduleUpdate);
  observer = new MutationObserver(scheduleUpdate);
  observer.observe(document.body, { childList: true, subtree: true });
  scheduleUpdate();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialize, { once: true });
} else {
  initialize();
}
