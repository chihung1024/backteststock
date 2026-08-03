import {
  SCORE_FORMULAS,
  buildScoreMatrix,
  normalizeScoreTicker,
  scoreRecordFor,
} from "./scan-score-formulas.js?v=20260803.2";
import {
  DEFAULT_SCAN_MIN_COVERAGE_PERCENT,
  buildScanCoverageStats,
  normalizeScanMinCoveragePercent,
} from "./scan-coverage.js?v=20260803.1";

const TABLE_SELECTOR = "#scan-table";
const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v3";
const BASELINE_FORMULA_KEY = SCORE_FORMULAS[0].key;
const FORMULA_KEYS = new Set(SCORE_FORMULAS.map((formula) => formula.key));
const BASE_EXPORT_HEADERS = [
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
  "valuation_currency",
  "note",
  "error",
];
const FORMULA_EXPORT_HEADERS = SCORE_FORMULAS.flatMap((formula) => [
  formula.key,
  formula.rankKey,
  formula.statusKey,
]);
const EXPORT_HEADERS = [
  ...BASE_EXPORT_HEADERS.slice(0, 9),
  ...FORMULA_EXPORT_HEADERS,
  ...BASE_EXPORT_HEADERS.slice(9),
];

const rawResults = new Map();
const scoreSortGetters = new Map();
const originalFetch = window.fetch.bind(window);
let scoreMatrixResult = buildScoreMatrix([]);
let scoreMatrixDirty = false;
let activeJobId = null;
let observer;
let updateScheduled = false;
let activeSortKey = "cagr";
let activeSortDirection = "desc";

function normalizeHeaderLabel(value) {
  return String(value || "")
    .replace(/\s+[▲▼]$/u, "")
    .trim();
}

function markScoreMatrixDirty() {
  scoreMatrixDirty = true;
}

function ensureScoreMatrix() {
  if (scoreMatrixDirty) {
    scoreMatrixResult = buildScoreMatrix([...rawResults.values()]);
    scoreMatrixDirty = false;
  }
  return scoreMatrixResult;
}

function readSavedJob() {
  try {
    const job = JSON.parse(localStorage.getItem(SCAN_JOB_STORAGE_KEY));
    return job && typeof job === "object" ? job : null;
  } catch (error) {
    console.warn("Unable to read saved scan job for score comparison", error);
    return null;
  }
}

function synchronizeActiveJob({ restoreResults = false } = {}) {
  const job = readSavedJob();
  if (job?.id && job.id !== activeJobId) {
    activeJobId = job.id;
    rawResults.clear();
    markScoreMatrixDirty();
  }

  if (restoreResults && Array.isArray(job?.results)) {
    captureRawResults(job.results, { synchronize: false });
  }
  return job;
}

function captureRawResults(payload, { synchronize = true } = {}) {
  if (!Array.isArray(payload)) return;
  if (synchronize) synchronizeActiveJob();

  let changed = false;
  payload.forEach((item) => {
    const ticker = normalizeScoreTicker(item?.ticker);
    if (!ticker) return;
    rawResults.set(ticker, item);
    changed = true;
  });

  if (changed) {
    markScoreMatrixDirty();
    scheduleScoreColumnUpdate();
  }
}

function restoreSavedRawResults() {
  synchronizeActiveJob({ restoreResults: true });
}

function isScanRequest(input) {
  try {
    const requestUrl = typeof input === "string" || input instanceof URL ? input : input?.url;
    return new URL(requestUrl, window.location.href).pathname === "/api/scan";
  } catch {
    return false;
  }
}

window.fetch = async function fetchWithScoreComparisonCapture(input, init) {
  const response = await originalFetch(input, init);
  if (response.ok && isScanRequest(input)) {
    response.clone().json().then((payload) => captureRawResults(payload)).catch(() => {});
  }
  return response;
};

function missingSortValue() {
  return activeSortDirection === "asc"
    ? Number.POSITIVE_INFINITY
    : Number.NEGATIVE_INFINITY;
}

function installScoreSortGetters() {
  SCORE_FORMULAS.forEach((formula) => {
    const existing = Object.getOwnPropertyDescriptor(Object.prototype, formula.key);
    if (existing) return;

    const getter = function scoreComparisonGetter() {
      const ticker = normalizeScoreTicker(this?.ticker);
      const score = scoreRecordFor(ensureScoreMatrix(), ticker, formula.key)?.score;
      return Number.isFinite(score) ? score : missingSortValue();
    };
    scoreSortGetters.set(formula.key, getter);
    Object.defineProperty(Object.prototype, formula.key, {
      configurable: true,
      enumerable: false,
      get: getter,
    });
  });
}

function removeScoreSortGetters() {
  scoreSortGetters.forEach((getter, key) => {
    const descriptor = Object.getOwnPropertyDescriptor(Object.prototype, key);
    if (descriptor?.get === getter) delete Object.prototype[key];
  });
  scoreSortGetters.clear();
}

function rankComparisonText(record, formula) {
  if (formula.key === BASELINE_FORMULA_KEY) return "穩健版基準排名";
  const delta = record?.rankDeltaVsStable;
  if (!Number.isInteger(delta)) return "無法與穩健版比較排名";
  if (delta === 0) return "與穩健版同名次";
  return delta > 0
    ? `相較穩健版落後 ${delta} 名`
    : `相較穩健版領先 ${Math.abs(delta)} 名`;
}

function formatScore(record, formula) {
  return Number(record.score).toFixed(formula.digits);
}

function setScoreCell(cell, record, formula) {
  cell.dataset.compositeMetric = formula.key;
  cell.classList.remove("positive", "negative");

  if (!record || record.score == null) {
    cell.textContent = "—";
    cell.title = `${record?.reason || "必要數據缺漏，無法計算。"} 排序時固定置底。`;
    return;
  }

  const rankText = Number.isInteger(record.rank) ? `#${record.rank}` : "#—";
  cell.textContent = `${rankText} · ${formatScore(record, formula)}`;
  cell.classList.add(record.score >= 0 ? "positive" : "negative");

  const details = [
    formula.description,
    `名次 ${record.rank ?? "—"}`,
    `分數 ${Number(record.score).toFixed(6)}`,
    rankComparisonText(record, formula),
    `Sortino ${record.sortino_ratio}`,
    `CAGR ${(record.cagr * 100).toFixed(4)}%`,
    `Beta ${record.beta}`,
  ];
  if (record.absoluteMdd != null) {
    details.push(`|MDD| ${(record.absoluteMdd * 100).toFixed(4)}%`);
  }
  cell.title = details.join(" · ");
}

function ensureFormulaComparisonNote() {
  const table = document.querySelector(TABLE_SELECTOR);
  const tableWrap = table?.closest(".table-wrap");
  if (!tableWrap) return;

  let details = document.querySelector("#score-formula-comparison");
  if (details && details.tagName !== "DETAILS") {
    details.remove();
    details = null;
  }
  if (details) return;

  details = document.createElement("details");
  details.id = "score-formula-comparison";
  details.className = "result-context score-formula-details";

  const summary = document.createElement("summary");
  summary.textContent = "分數公式與排名說明";
  const list = document.createElement("ul");
  SCORE_FORMULAS.forEach((formula) => {
    const item = document.createElement("li");
    item.textContent = `${formula.shortLabel}：${formula.description}`;
    list.append(item);
  });
  const note = document.createElement("p");
  note.textContent = "每格顯示「名次 · 分數」；排名以目前符合資料覆蓋率門檻且可計算的標的為母體，掃描進行中或門檻調整時會動態更新。";
  details.append(summary, list, note);
  tableWrap.insertAdjacentElement("beforebegin", details);
}


function removeInjectedColumns(table, headerRow) {
  [...headerRow.querySelectorAll("th[data-composite-metric]")].forEach((cell) => cell.remove());
  [...table.querySelectorAll("td[data-composite-metric]")].forEach((cell) => cell.remove());
}

function currentCoverageFilteredRows(table) {
  const threshold = normalizeScanMinCoveragePercent(
    table?.dataset?.minCoveragePercent,
    DEFAULT_SCAN_MIN_COVERAGE_PERCENT,
  );
  const saved = readSavedJob()?.results;
  const rows = Array.isArray(saved) && saved.length ? saved : [...rawResults.values()];
  return buildScanCoverageStats(rows, threshold).shown;
}

function updateScoreColumns() {
  const table = document.querySelector(TABLE_SELECTOR);
  const headerRow = table?.tHead?.rows?.[0];
  if (!table || !headerRow) return;

  removeInjectedColumns(table, headerRow);
  const originalHeaders = [...headerRow.cells];
  const headerIndexes = new Map(
    originalHeaders.map((cell, index) => [normalizeHeaderLabel(cell.textContent), index]),
  );
  if (!headerIndexes.has("Beta")) return;

  const matrixResult = buildScoreMatrix(currentCoverageFilteredRows(table));
  const betaIndex = headerIndexes.get("Beta");
  let headerAnchor = originalHeaders[betaIndex];
  SCORE_FORMULAS.forEach((formula) => {
    const header = document.createElement("th");
    header.scope = "col";
    header.dataset.compositeMetric = formula.key;
    header.dataset.sortKey = formula.key;
    header.className = "sortable";
    const sortIndicator = activeSortKey === formula.key
      ? (activeSortDirection === "asc" ? " ▲" : " ▼")
      : "";
    header.textContent = `${formula.label}${sortIndicator}`;
    header.title = `${formula.description}；每格顯示名次與分數。符合目前覆蓋率門檻的有效樣本 ${matrixResult.validCounts[formula.key] || 0} 檔，點擊可排序目前顯示結果。`;
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
    const originalCells = [...row.cells];
    if (originalCells.length <= betaIndex) return;
    const ticker = normalizeScoreTicker(row.dataset.ticker || originalCells[0].dataset.ticker || originalCells[0].textContent);
    let cellAnchor = originalCells[betaIndex];
    SCORE_FORMULAS.forEach((formula) => {
      const cell = document.createElement("td");
      setScoreCell(cell, scoreRecordFor(matrixResult, ticker, formula.key), formula);
      cellAnchor.insertAdjacentElement("afterend", cell);
      cellAnchor = cell;
    });
  });

  ensureFormulaComparisonNote();
}

function handleScanSortChange(event) {
  const key = String(event.detail?.key || "");
  if (!key) return;
  activeSortKey = key;
  activeSortDirection = event.detail?.direction === "asc" ? "asc" : "desc";
  scheduleScoreColumnUpdate();
}

function currentExportRows() {
  const job = synchronizeActiveJob({ restoreResults: true });
  if (Array.isArray(job?.results) && job.results.length) return job.results;
  return [...rawResults.values()];
}

function escapeCsv(value) {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

function downloadCsv(filename, content) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  link.download = filename;
  document.body.append(link);
  link.click();
  setTimeout(() => {
    URL.revokeObjectURL(link.href);
    link.remove();
  }, 0);
}

function formulaExportValue(matrixResult, item, key) {
  const formula = SCORE_FORMULAS.find((entry) => (
    entry.key === key || entry.rankKey === key || entry.statusKey === key
  ));
  if (!formula) return undefined;
  const record = scoreRecordFor(matrixResult, item?.ticker, formula.key);
  if (key === formula.key) return record?.score == null ? "" : Number(record.score).toFixed(6);
  if (key === formula.rankKey) return record?.rank ?? "";
  return record?.status || "missing";
}

function handleExportClick(event) {
  event.preventDefault();
  event.stopImmediatePropagation();

  const rows = currentExportRows();
  if (!rows.length) return;
  const matrixResult = buildScoreMatrix(rows);
  const lines = [
    EXPORT_HEADERS.join(","),
    ...rows.map((item) => EXPORT_HEADERS.map((key) => {
      if (FORMULA_KEYS.has(key) || FORMULA_EXPORT_HEADERS.includes(key)) {
        return escapeCsv(formulaExportValue(matrixResult, item, key));
      }
      return escapeCsv(item?.[key]);
    }).join(",")),
  ];
  downloadCsv("scan-results.csv", `\ufeff${lines.join("\n")}`);
}

function updateMethodologyText() {
  const paragraphs = [...document.querySelectorAll("#about-panel .panel p")];
  const formulaParagraph = paragraphs.find((paragraph) => (
    paragraph.textContent.includes("個股績效列表")
    && paragraph.textContent.includes("Sortino")
  ));
  if (!formulaParagraph) return;
  formulaParagraph.textContent = [
    "個股績效列表同時顯示三種可排序分數：",
    "穩健公式 Sortino × √((1 + CAGR) ÷ (1 + Beta))、",
    "成長公式 Sortino × √(1 + CAGR) ÷ (1 + Beta)^0.25，",
    "以及回撤控制公式 Sortino × √((1 + CAGR) ÷ ((1 + Beta) × (1 + |最大回撤|)))；",
    "每格同步顯示該公式名次。",
  ].join("");
}

function scheduleScoreColumnUpdate() {
  if (updateScheduled) return;
  updateScheduled = true;

  requestAnimationFrame(() => {
    updateScheduled = false;
    observer?.disconnect();
    try {
      updateScoreColumns();
    } finally {
      const table = document.querySelector(TABLE_SELECTOR);
      if (table) observer?.observe(table, { childList: true, subtree: true });
    }
  });
}

function initializeScoreComparison() {
  const table = document.querySelector(TABLE_SELECTOR);
  if (!table) return;

  installScoreSortGetters();
  observer = new MutationObserver(scheduleScoreColumnUpdate);
  observer.observe(table, { childList: true, subtree: true });
  document.addEventListener("backteststock:scan-sort-change", handleScanSortChange);
  document.querySelector("#export-scan")?.addEventListener("click", handleExportClick, true);
  updateMethodologyText();
  restoreSavedRawResults();
  scheduleScoreColumnUpdate();
  window.addEventListener("pagehide", removeScoreSortGetters, { once: true });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeScoreComparison, { once: true });
} else {
  initializeScoreComparison();
}
