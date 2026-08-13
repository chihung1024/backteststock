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
import "./portfolio-route-bridge.js?v=20260804.1";

const TABLE_SELECTOR = "#scan-table";
const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v3";
const MANUAL_SELECTION_KEY = "backteststock-optimizer-manual-selection-v2";
const MIN_PORTFOLIO_ASSETS = 1;
const MAX_PORTFOLIO_ASSETS = 20;
const MIN_OPTIMIZER_TICKERS = 2;
const MAX_OPTIMIZER_TICKERS = 100;

let observer;
let updateScheduled = false;
let activeSortKey = "cagr";
let activeSortDirection = "desc";
let integratedBacktestButton = null;

function readJson(storage, key, fallback = null) {
  try {
    const value = JSON.parse(storage.getItem(key));
    return value == null ? fallback : value;
  } catch {
    return fallback;
  }
}

function visibleScanJobId() {
  return String(document.querySelector(TABLE_SELECTOR)?.dataset.scanJobId || "").trim();
}

function readScanJob() {
  const job = readJson(localStorage, SCAN_JOB_STORAGE_KEY, null);
  if (!job || !Array.isArray(job.results)) return null;
  const pageJobId = visibleScanJobId();
  return pageJobId && job.id !== pageJobId ? null : job;
}

function currentThreshold() {
  return normalizeScanMinCoveragePercent(
    document.querySelector("#scan-min-coverage")?.value,
    DEFAULT_SCAN_MIN_COVERAGE_PERCENT,
  );
}

function currentCoverageStats(job = readScanJob()) {
  return buildScanCoverageStats(job?.results || [], currentThreshold());
}

function selectedTickers(stats = currentCoverageStats()) {
  const job = readScanJob();
  const selection = readJson(localStorage, MANUAL_SELECTION_KEY, null);
  if (
    !job?.id
    || selection?.sourceJobId !== job.id
    || !Array.isArray(selection?.tickers)
  ) return [];

  const benchmark = normalizeScoreTicker(job.payload?.benchmark);
  const selectable = new Set(
    stats.shown
      .map((item) => normalizeScoreTicker(item?.ticker))
      .filter((ticker) => ticker && ticker !== benchmark),
  );
  return [...new Set(selection.tickers.map(normalizeScoreTicker))]
    .filter((ticker) => selectable.has(ticker));
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
  const finite = values.map(Number).filter(Number.isFinite).sort((left, right) => left - right);
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
    .tab-nav a.tab-button { display:inline-flex; align-items:center; justify-content:center; text-decoration:none; }
    .scan-control-stack { display:grid; gap:.75rem; margin:0 0 1rem; }
    .scan-control-row { display:flex; align-items:center; gap:.65rem; flex-wrap:wrap; padding:.75rem .85rem; border:1px solid var(--border); border-radius:11px; background:var(--surface-subtle); }
    .scan-control-row .scan-coverage-filter { display:flex; align-items:center; grid-template-columns:none; }
    .scan-control-row .scan-coverage-filter-status { flex:1 1 26rem; white-space:normal; }
    .scan-control-row .optimizer-manual-selection-status { margin-right:auto; white-space:normal; }
    .scan-destination-capacity-status { flex:1 1 100%; color:var(--muted); font-size:.8rem; line-height:1.45; }
    .scan-result-export-actions { justify-content:flex-end; }
    #open-integrated-backtest[aria-disabled="true"] { pointer-events:none; opacity:.52; cursor:not-allowed; }
    #scan-table th[data-composite-metric], #scan-table td[data-composite-metric] { min-width:132px; }
    #scan-table { min-width:1740px; }
    .coverage-definition-note { margin-top:.55rem; color:var(--muted); font-size:.78rem; }
    @media (max-width:640px) {
      .scan-control-row { align-items:stretch; flex-direction:column; }
      .scan-control-row .button, .scan-control-row a.button { width:100%; text-align:center; }
    }
  `;
  document.head.append(style);
}

function activateResearchWorkspace() {
  const oldBacktestButton = document.querySelector('.tab-button[data-tab="backtest"]');
  let portfolioLink = document.querySelector("#portfolio-route-link");
  if (!portfolioLink && oldBacktestButton) {
    portfolioLink = document.createElement("a");
    portfolioLink.id = "portfolio-route-link";
    portfolioLink.className = "tab-button portfolio-route-link";
    portfolioLink.href = "/portfolio/";
    portfolioLink.dataset.portfolioRoute = "main";
    portfolioLink.textContent = "投資組合回測";
    portfolioLink.title = "前往完整投資組合研究工作區";
    portfolioLink.setAttribute("aria-label", "投資組合回測（開啟完整頁面）");
    oldBacktestButton.replaceWith(portfolioLink);
  }

  const scannerButton = document.querySelector('.tab-button[data-tab="scanner"]');
  if (scannerButton) {
    scannerButton.textContent = "績效研究（個股掃描）";
    if (!scannerButton.classList.contains("active")) scannerButton.click();
  }
  document.querySelector("#backtest-panel")?.classList.add("hidden");
  document.querySelector("#scanner-panel")?.classList.remove("hidden");
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
    if (exportIds.has(element.id)) return;
    if (element.matches(".scan-coverage-filter, #scan-coverage-filter-status")) {
      coverageRow.append(element);
    } else {
      actionRow.append(element);
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
    integratedBacktestButton = document.createElement("a");
    integratedBacktestButton.id = "open-integrated-backtest";
    integratedBacktestButton.href = "/portfolio/";
    integratedBacktestButton.dataset.portfolioRoute = "scanner";
    integratedBacktestButton.className = "button primary";
    integratedBacktestButton.textContent = "建立投資組合回測";
    integratedBacktestButton.setAttribute("aria-disabled", "true");
    actionRow.insertBefore(
      integratedBacktestButton,
      actionRow.querySelector("#open-manual-optimizer"),
    );
  }

  let destinationCapacity = actionRow.querySelector("#scan-destination-capacity-status");
  if (!destinationCapacity) {
    destinationCapacity = document.createElement("span");
    destinationCapacity.id = "scan-destination-capacity-status";
    destinationCapacity.className = "scan-destination-capacity-status";
    destinationCapacity.setAttribute("role", "status");
    destinationCapacity.setAttribute("aria-live", "polite");
    destinationCapacity.setAttribute("aria-atomic", "true");
    actionRow.insertBefore(destinationCapacity, actionRow.firstChild);
  }

  let note = coverageRow.querySelector(".coverage-definition-note");
  if (!note) {
    note = document.createElement("span");
    note.className = "coverage-definition-note";
    note.textContent = "資料覆蓋率＝個股有效交易日 ÷ 本次掃描成功標的最大交易日。";
    coverageRow.append(note);
  }
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
}

function injectScoreColumns(table, stats) {
  const headerRow = table?.tHead?.rows?.[0];
  if (!table || !headerRow) return;
  removeInjectedColumns(table, headerRow);

  const originalHeaders = [...headerRow.cells];
  const alphaIndex = originalHeaders.findIndex(
    (cell) => normalizedHeader(cell.textContent) === "Alpha",
  );
  if (alphaIndex < 0) return;

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
    const threshold = Number(currentThreshold()).toLocaleString("zh-TW", {
      maximumFractionDigits: 1,
    });
    status.textContent = [
      `顯示 ${stats.shown.length.toLocaleString("zh-TW")} / ${stats.settled.length.toLocaleString("zh-TW")} 檔`,
      `門檻 ≥ ${threshold}%`,
      stats.hidden ? `隱藏 ${stats.hidden.toLocaleString("zh-TW")} 檔` : "沒有低覆蓋率標的",
      `基準交易日 ${formatInteger(stats.maximumTradingDays)}`,
    ].join(" · ");
  }
}

function destinationCapacityText(label, count, minimum, maximum) {
  if (count > maximum) return `${label} ${count.toLocaleString("zh-TW")} / ${maximum}（超過上限）`;
  if (count < minimum) return `${label} ${count.toLocaleString("zh-TW")} / ${maximum}（至少 ${minimum} 檔）`;
  return `${label} ${count.toLocaleString("zh-TW")} / ${maximum}（可使用）`;
}

function updateSelectionControls() {
  const count = selectedTickers().length;
  const destinationCapacity = document.querySelector("#scan-destination-capacity-status");
  if (destinationCapacity) {
    destinationCapacity.textContent = [
      destinationCapacityText("投組", count, MIN_PORTFOLIO_ASSETS, MAX_PORTFOLIO_ASSETS),
      destinationCapacityText("最佳化器", count, MIN_OPTIMIZER_TICKERS, MAX_OPTIMIZER_TICKERS),
    ].join(" · ");
  }
  if (!integratedBacktestButton) return;
  const enabled = count >= MIN_PORTFOLIO_ASSETS && count <= MAX_PORTFOLIO_ASSETS;
  integratedBacktestButton.setAttribute("aria-disabled", String(!enabled));
  integratedBacktestButton.classList.toggle("disabled", !enabled);
  integratedBacktestButton.tabIndex = enabled ? 0 : -1;
  integratedBacktestButton.href = "/portfolio/";
  integratedBacktestButton.textContent = count > MAX_PORTFOLIO_ASSETS
    ? `已選 ${count.toLocaleString("zh-TW")} 檔（投組上限 20）`
    : count
      ? `使用已選 ${count.toLocaleString("zh-TW")} 檔建立投組回測`
      : "建立投資組合回測";
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

function updatePerformanceList() {
  activateResearchWorkspace();
  ensureResultControls();
  const job = readScanJob();
  // The core scanner keeps its active job in this tab. A newer result saved by
  // another tab must not overwrite this page's visible table, summary, or handoff.
  if (visibleScanJobId() && !job) return;
  const stats = currentCoverageStats(job);
  const table = document.querySelector(TABLE_SELECTOR);
  if (table?.tHead?.rows?.[0]) {
    injectScoreColumns(table, stats);
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
  observer = new MutationObserver(scheduleUpdate);
  observer.observe(document.body, { childList: true, subtree: true });
  scheduleUpdate();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialize, { once: true });
} else {
  initialize();
}
