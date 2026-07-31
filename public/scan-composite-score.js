const TABLE_SELECTOR = "#scan-table";
const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v2";
const SCORE_KEY = "ten_year_quality_score";
const SCORE_LABEL = "十年品質分數";
const SCORE_DESCRIPTION = [
  "合格股票內橫斷面百分位加權幾何平均",
  "CAGR 35%",
  "風險調整品質 30%（Sortino 70%＋Sharpe 30%）",
  "Alpha 20%",
  "低最大回撤 15%",
  "資料覆蓋率 80%～95% 套用四次方可靠度折扣",
].join(" · ");
const REQUIRED_METRICS = [
  "cagr",
  "sharpe_ratio",
  "sortino_ratio",
  "alpha",
  "mdd",
  "data_coverage",
];
const MIN_COVERAGE = 0.80;
const FULL_COVERAGE = 0.95;
const PERCENTILE_FLOOR = 0.05;
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
  "quality_score_status",
  "data_coverage",
  "trading_days",
  "data_start",
  "data_end",
  "note",
  "error",
];

const rawResults = new Map();
const scoreRecords = new Map();
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

function readSavedJob() {
  try {
    const job = JSON.parse(localStorage.getItem(SCAN_JOB_STORAGE_KEY));
    return job && typeof job === "object" ? job : null;
  } catch (error) {
    console.warn("Unable to read saved scan job for quality score", error);
    return null;
  }
}

function synchronizeActiveJob({ restoreResults = false } = {}) {
  const job = readSavedJob();
  if (job?.id && job.id !== activeJobId) {
    activeJobId = job.id;
    rawResults.clear();
    scoreRecords.clear();
  }

  if (restoreResults && Array.isArray(job?.results)) {
    captureRawResults(job.results, { synchronize: false });
  }
  return job;
}

function percentileRanks(candidates, valueGetter) {
  const entries = candidates
    .map((candidate) => ({ ticker: candidate.ticker, value: valueGetter(candidate) }))
    .filter((entry) => Number.isFinite(entry.value))
    .sort((left, right) => left.value - right.value);
  const ranks = new Map();
  if (!entries.length) return ranks;
  if (entries.length === 1) {
    ranks.set(entries[0].ticker, 0.5);
    return ranks;
  }

  let index = 0;
  while (index < entries.length) {
    let end = index;
    while (end + 1 < entries.length && entries[end + 1].value === entries[index].value) {
      end += 1;
    }
    const averageRank = (index + end) / 2;
    const percentile = averageRank / (entries.length - 1);
    for (let cursor = index; cursor <= end; cursor += 1) {
      ranks.set(entries[cursor].ticker, percentile);
    }
    index = end + 1;
  }
  return ranks;
}

function adjustedPercentile(value) {
  return PERCENTILE_FLOOR + (1 - PERCENTILE_FLOOR) * value;
}

function recomputeScores() {
  scoreRecords.clear();
  const candidates = [];

  rawResults.forEach((item, ticker) => {
    if (item?.error) {
      scoreRecords.set(ticker, { score: null, status: "error", reason: String(item.error) });
      return;
    }

    const values = Object.fromEntries(REQUIRED_METRICS.map((key) => [key, rawMetric(item, key)]));
    const missing = REQUIRED_METRICS.filter((key) => values[key] == null);
    if (missing.length) {
      scoreRecords.set(ticker, {
        score: null,
        status: "missing_metrics",
        reason: `缺少必要指標：${missing.join(", ")}`,
      });
      return;
    }

    if (values.data_coverage < MIN_COVERAGE) {
      scoreRecords.set(ticker, {
        score: null,
        status: "insufficient_history",
        reason: `資料覆蓋率 ${(values.data_coverage * 100).toFixed(2)}%，低於 80% 主模型門檻`,
        coverage: values.data_coverage,
      });
      return;
    }

    candidates.push({ ticker, item, values });
  });

  const cagrRanks = percentileRanks(candidates, (candidate) => candidate.values.cagr);
  const sharpeRanks = percentileRanks(candidates, (candidate) => candidate.values.sharpe_ratio);
  const sortinoRanks = percentileRanks(candidates, (candidate) => candidate.values.sortino_ratio);
  const alphaRanks = percentileRanks(candidates, (candidate) => candidate.values.alpha);
  const drawdownRanks = percentileRanks(candidates, (candidate) => -Math.abs(candidate.values.mdd));

  candidates.forEach((candidate) => {
    const cagrPercentile = cagrRanks.get(candidate.ticker);
    const sharpePercentile = sharpeRanks.get(candidate.ticker);
    const sortinoPercentile = sortinoRanks.get(candidate.ticker);
    const alphaPercentile = alphaRanks.get(candidate.ticker);
    const drawdownPercentile = drawdownRanks.get(candidate.ticker);
    const riskAdjustedQuality = 0.7 * sortinoPercentile + 0.3 * sharpePercentile;
    const core = 100
      * adjustedPercentile(cagrPercentile) ** 0.35
      * adjustedPercentile(riskAdjustedQuality) ** 0.30
      * adjustedPercentile(alphaPercentile) ** 0.20
      * adjustedPercentile(drawdownPercentile) ** 0.15;
    const historyReliability = Math.min(1, candidate.values.data_coverage / FULL_COVERAGE) ** 4;
    const score = core * historyReliability;

    scoreRecords.set(candidate.ticker, {
      score,
      status: "ok",
      core,
      historyReliability,
      coverage: candidate.values.data_coverage,
      cagrPercentile,
      sharpePercentile,
      sortinoPercentile,
      riskAdjustedQuality,
      alphaPercentile,
      drawdownPercentile,
    });
  });
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

  if (changed) {
    recomputeScores();
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

window.fetch = async function fetchWithQualityMetricCapture(input, init) {
  const response = await originalFetch(input, init);
  if (response.ok && isScanRequest(input)) {
    response.clone().json().then((payload) => captureRawResults(payload)).catch(() => {});
  }
  return response;
};

function scoreFromItem(item) {
  return scoreRecords.get(normalizeTicker(item?.ticker))?.score ?? null;
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

  if (!record || record.status === "missing_metrics" || record.status === "error") {
    cell.textContent = "—";
    cell.title = record?.reason || "必要數據缺漏，無法計算十年品質分數。";
    return;
  }

  if (record.status === "insufficient_history") {
    cell.textContent = "不合格";
    cell.title = `${record.reason}；不參與百分位計算，排序時固定置底。`;
    return;
  }

  cell.textContent = record.score.toFixed(2);
  cell.classList.add("positive");
  cell.title = [
    SCORE_DESCRIPTION,
    `最終分數 ${record.score.toFixed(4)}`,
    `核心分數 ${record.core.toFixed(4)}`,
    `歷史可靠度 ${(record.historyReliability * 100).toFixed(2)}%`,
    `CAGR 百分位 ${(record.cagrPercentile * 100).toFixed(1)}%`,
    `風險調整品質百分位 ${(record.riskAdjustedQuality * 100).toFixed(1)}%`,
    `Alpha 百分位 ${(record.alphaPercentile * 100).toFixed(1)}%`,
    `低回撤百分位 ${(record.drawdownPercentile * 100).toFixed(1)}%`,
  ].join(" · ");
}

function updateScoreColumn() {
  const table = document.querySelector(TABLE_SELECTOR);
  const headerRow = table?.tHead?.rows?.[0];
  if (!table || !headerRow) return;

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
  scoreHeader.title = `${SCORE_DESCRIPTION}；點擊可依全部掃描結果排序。`;
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
    setScoreCell(scoreCell, scoreRecords.get(ticker));
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
  recomputeScores();
  const lines = [
    EXPORT_HEADERS.join(","),
    ...rows.map((item) => {
      const record = scoreRecords.get(normalizeTicker(item?.ticker));
      return EXPORT_HEADERS.map((key) => {
        if (key === SCORE_KEY) return escapeCsv(record?.score == null ? "" : record.score.toFixed(6));
        if (key === "quality_score_status") return escapeCsv(record?.status || "missing_metrics");
        return escapeCsv(item?.[key]);
      }).join(",");
    }),
  ];
  downloadCsv("scan-results.csv", `\ufeff${lines.join("\n")}`);
}

function updateMethodologyText() {
  const paragraphs = [...document.querySelectorAll("#about-panel .panel p")];
  const oldFormula = paragraphs.find((paragraph) => paragraph.textContent.includes("Sortino × Alpha"));
  if (!oldFormula) return;
  oldFormula.textContent = "個股績效列表的十年品質分數，先在資料覆蓋率至少 80% 的股票中，將 CAGR、Sortino、Sharpe、Alpha 與低最大回撤轉為橫斷面百分位；再以 35%、30%、20%、15% 加權幾何平均，並對未滿 95% 的資料覆蓋率套用四次方可靠度折扣。";
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

function initializeQualityScore() {
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
  document.addEventListener("DOMContentLoaded", initializeQualityScore, { once: true });
} else {
  initializeQualityScore();
}
