const TABLE_SELECTOR = "#scan-table";
const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v2";
const SCORE_KEY = "sortino_alpha_mdd_score";
const SCORE_STATUS_KEY = "sortino_alpha_mdd_score_status";
const SCORE_LABEL = "Sortino×Alpha/|MDD|";
const SCORE_DESCRIPTION = "Sortino × Alpha ÷ |最大回撤|";
const REQUIRED_METRICS = ["sortino_ratio", "alpha", "mdd"];
const EXPORT_HEADERS = [
  "ticker",
  "total_return",
  "cagr",
  "volatility",
  "mdd",
  "sharpe_ratio",
  "sortino_ratio",
  "beta",
  "alpha",
  SCORE_KEY,
  SCORE_STATUS_KEY,
  "data_coverage",
  "trading_days",
  "data_start",
  "data_end",
  "note",
  "error",
];

const rawResults = new Map();
const originalFetch = window.fetch.bind(window);
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

function normalizeTicker(value) {
  return String(value || "").trim().split(/\s+/u)[0].toUpperCase();
}

function rawMetric(item, key) {
  if (item?.[key] == null) return null;
  const numeric = Number(item[key]);
  return Number.isFinite(numeric) ? numeric : null;
}

function calculateScoreRecord(item) {
  if (item?.error) {
    return { score: null, status: "error", reason: String(item.error) };
  }

  const values = Object.fromEntries(REQUIRED_METRICS.map((key) => [key, rawMetric(item, key)]));
  const missing = REQUIRED_METRICS.filter((key) => values[key] == null);
  if (missing.length) {
    return {
      score: null,
      status: "missing_metrics",
      reason: `缺少必要指標：${missing.join(", ")}`,
    };
  }

  const absoluteMdd = Math.abs(values.mdd);
  if (absoluteMdd <= Number.EPSILON) {
    return {
      score: null,
      status: "zero_mdd",
      reason: "最大回撤為 0，無法作為除數。",
      ...values,
      absoluteMdd,
    };
  }

  const score = values.sortino_ratio * values.alpha / absoluteMdd;
  if (!Number.isFinite(score)) {
    return {
      score: null,
      status: "invalid_result",
      reason: "計算結果不是有限數值。",
      ...values,
      absoluteMdd,
    };
  }

  return {
    score,
    status: "ok",
    ...values,
    absoluteMdd,
  };
}

function readSavedJob() {
  try {
    const job = JSON.parse(localStorage.getItem(SCAN_JOB_STORAGE_KEY));
    return job && typeof job === "object" ? job : null;
  } catch (error) {
    console.warn("Unable to read saved scan job for composite score", error);
    return null;
  }
}

function synchronizeActiveJob({ restoreResults = false } = {}) {
  const job = readSavedJob();
  if (job?.id && job.id !== activeJobId) {
    activeJobId = job.id;
    rawResults.clear();
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
    const ticker = normalizeTicker(item?.ticker);
    if (!ticker) return;
    rawResults.set(ticker, item);
    changed = true;
  });

  if (changed) scheduleScoreColumnUpdate();
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

window.fetch = async function fetchWithCompositeMetricCapture(input, init) {
  const response = await originalFetch(input, init);
  if (response.ok && isScanRequest(input)) {
    response.clone().json().then((payload) => captureRawResults(payload)).catch(() => {});
  }
  return response;
};

function scoreFromItem(item) {
  return calculateScoreRecord(item).score;
}

function scoreSortGetter() {
  const score = scoreFromItem(this);
  if (score != null) return score;
  return activeSortDirection === "asc" ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
}

function installScoreSortGetter() {
  const descriptor = Object.getOwnPropertyDescriptor(Object.prototype, SCORE_KEY);
  if (descriptor?.get === scoreSortGetter) return;
  if (descriptor) return;

  Object.defineProperty(Object.prototype, SCORE_KEY, {
    configurable: true,
    enumerable: false,
    get: scoreSortGetter,
  });
}

function removeScoreSortGetter() {
  const descriptor = Object.getOwnPropertyDescriptor(Object.prototype, SCORE_KEY);
  if (descriptor?.get === scoreSortGetter) delete Object.prototype[SCORE_KEY];
}

function setScoreCell(cell, record) {
  cell.dataset.compositeMetric = SCORE_KEY;
  cell.classList.remove("positive", "negative");

  if (!record || record.score == null) {
    cell.textContent = "—";
    cell.title = `${record?.reason || "必要數據缺漏，無法計算。"} 排序時固定置底。`;
    return;
  }

  cell.textContent = record.score.toFixed(4);
  cell.classList.add(record.score >= 0 ? "positive" : "negative");
  cell.title = [
    SCORE_DESCRIPTION,
    `計算結果 ${record.score.toFixed(6)}`,
    `Sortino ${record.sortino_ratio}`,
    `Alpha ${(record.alpha * 100).toFixed(4)}%`,
    `|MDD| ${(record.absoluteMdd * 100).toFixed(4)}%`,
  ].join(" · ");
}

function updateScoreColumn() {
  const table = document.querySelector(TABLE_SELECTOR);
  const headerRow = table?.tHead?.rows?.[0];
  if (!table || !headerRow) return;

  const compositeHeaders = [...headerRow.querySelectorAll("th[data-composite-metric]")];
  compositeHeaders.forEach((cell) => {
    if (cell.dataset.compositeMetric !== SCORE_KEY) cell.remove();
  });
  [...table.querySelectorAll("td[data-composite-metric]")].forEach((cell) => {
    if (cell.dataset.compositeMetric !== SCORE_KEY) cell.remove();
  });

  const originalHeaders = [...headerRow.cells].filter(
    (cell) => cell.dataset.compositeMetric !== SCORE_KEY,
  );
  const headerIndexes = new Map(
    originalHeaders.map((cell, index) => [normalizeHeaderLabel(cell.textContent), index]),
  );
  if (!headerIndexes.has("Alpha")) return;

  let scoreHeader = headerRow.querySelector(`th[data-composite-metric="${SCORE_KEY}"]`);
  if (!scoreHeader) {
    scoreHeader = document.createElement("th");
    scoreHeader.scope = "col";
    scoreHeader.dataset.compositeMetric = SCORE_KEY;
    const alphaHeader = originalHeaders[headerIndexes.get("Alpha")];
    alphaHeader.insertAdjacentElement("afterend", scoreHeader);
  }

  const sortIndicator = activeSortKey === SCORE_KEY
    ? (activeSortDirection === "asc" ? " ▲" : " ▼")
    : "";
  scoreHeader.textContent = `${SCORE_LABEL}${sortIndicator}`;
  scoreHeader.title = `${SCORE_DESCRIPTION}；使用原始未四捨五入數值，點擊可依全部掃描結果排序。`;
  scoreHeader.classList.add("sortable");
  scoreHeader.dataset.sortKey = SCORE_KEY;
  scoreHeader.setAttribute(
    "aria-sort",
    activeSortKey === SCORE_KEY
      ? (activeSortDirection === "asc" ? "ascending" : "descending")
      : "none",
  );

  const alphaIndex = headerIndexes.get("Alpha");
  [...(table.tBodies[0]?.rows || [])].forEach((row) => {
    const originalCells = [...row.cells].filter(
      (cell) => cell.dataset.compositeMetric !== SCORE_KEY,
    );
    if (originalCells.length <= alphaIndex) return;

    const ticker = normalizeTicker(originalCells[0].textContent);
    let scoreCell = row.querySelector(`td[data-composite-metric="${SCORE_KEY}"]`);
    if (!scoreCell) {
      scoreCell = document.createElement("td");
      originalCells[alphaIndex].insertAdjacentElement("afterend", scoreCell);
    }
    setScoreCell(scoreCell, calculateScoreRecord(rawResults.get(ticker)));
  });
}

function handleTableSortClick(event) {
  const header = event.target.closest("th[data-sort-key]");
  if (!header) return;

  const key = header.dataset.sortKey;
  if (activeSortKey === key) {
    activeSortDirection = activeSortDirection === "asc" ? "desc" : "asc";
  } else {
    activeSortKey = key;
    activeSortDirection = ["mdd", "volatility"].includes(key) ? "asc" : "desc";
  }

  if (activeSortKey === SCORE_KEY) installScoreSortGetter();
  else removeScoreSortGetter();
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

function handleExportClick(event) {
  event.preventDefault();
  event.stopImmediatePropagation();

  const rows = currentExportRows();
  if (!rows.length) return;
  const lines = [
    EXPORT_HEADERS.join(","),
    ...rows.map((item) => {
      const record = calculateScoreRecord(item);
      return EXPORT_HEADERS.map((key) => {
        if (key === SCORE_KEY) return escapeCsv(record.score == null ? "" : record.score.toFixed(6));
        if (key === SCORE_STATUS_KEY) return escapeCsv(record.status);
        return escapeCsv(item?.[key]);
      }).join(",");
    }),
  ];
  downloadCsv("scan-results.csv", `\ufeff${lines.join("\n")}`);
}

function updateMethodologyText() {
  const paragraphs = [...document.querySelectorAll("#about-panel .panel p")];
  const formulaParagraph = paragraphs.find((paragraph) => (
    paragraph.textContent.includes("十年品質分數")
    || paragraph.textContent.includes("Sortino × Alpha")
  ));
  if (!formulaParagraph) return;
  formulaParagraph.textContent = "個股績效列表另顯示 Sortino × Alpha ÷ |最大回撤|，使用 API 回傳的原始未四捨五入數值計算；必要數據缺漏或最大回撤為 0 時不計算。";
}

function scheduleScoreColumnUpdate() {
  if (updateScheduled) return;
  updateScheduled = true;

  requestAnimationFrame(() => {
    updateScheduled = false;
    observer?.disconnect();
    try {
      updateScoreColumn();
    } finally {
      const table = document.querySelector(TABLE_SELECTOR);
      if (table) observer?.observe(table, { childList: true, subtree: true });
    }
  });
}

function initializeCompositeScore() {
  const table = document.querySelector(TABLE_SELECTOR);
  if (!table) return;

  observer = new MutationObserver(scheduleScoreColumnUpdate);
  observer.observe(table, { childList: true, subtree: true });
  table.addEventListener("click", handleTableSortClick, true);
  document.querySelector("#export-scan")?.addEventListener("click", handleExportClick, true);
  updateMethodologyText();
  restoreSavedRawResults();
  scheduleScoreColumnUpdate();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeCompositeScore, { once: true });
} else {
  initializeCompositeScore();
}
