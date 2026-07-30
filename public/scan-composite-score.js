const TABLE_SELECTOR = "#scan-table";
const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v2";
const SCORE_KEY = "sortino_alpha_beta_mdd_score";
const SCORE_LABEL = "Sortino×Alpha/(1+Beta)/|MDD|";
const SCORE_DESCRIPTION = "Sortino × Alpha ÷ (1 + Beta) ÷ |最大回撤|";
const REQUIRED_METRICS = ["sortino_ratio", "alpha", "beta", "mdd"];

const rawResults = new Map();
const originalFetch = window.fetch.bind(window);
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

function parseMetric(value, percent = false) {
  const text = String(value || "").trim();
  if (!text || text === "—") return null;

  const numeric = Number(text.replaceAll(",", "").replace("%", ""));
  if (!Number.isFinite(numeric)) return null;
  return percent ? numeric / 100 : numeric;
}

function rawMetric(item, key) {
  if (item?.[key] == null) return null;
  const numeric = Number(item[key]);
  return Number.isFinite(numeric) ? numeric : null;
}

function calculateScore(sortino, alpha, beta, mdd) {
  if (![sortino, alpha, beta, mdd].every(Number.isFinite)) return null;

  const betaDenominator = 1 + beta;
  const drawdownDenominator = Math.abs(mdd);
  if (Math.abs(betaDenominator) <= Number.EPSILON || drawdownDenominator <= Number.EPSILON) {
    return null;
  }

  const score = (sortino * alpha) / betaDenominator / drawdownDenominator;
  return Number.isFinite(score) ? score : null;
}

function scoreFromItem(item) {
  return calculateScore(
    rawMetric(item, "sortino_ratio"),
    rawMetric(item, "alpha"),
    rawMetric(item, "beta"),
    rawMetric(item, "mdd"),
  );
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

function captureRawResults(payload) {
  if (!Array.isArray(payload)) return;

  let changed = false;
  payload.forEach((item) => {
    const ticker = normalizeTicker(item?.ticker);
    if (!ticker) return;

    const hasMetric = REQUIRED_METRICS.some((key) => rawMetric(item, key) != null);
    if (!hasMetric) return;

    rawResults.set(ticker, item);
    changed = true;
  });

  if (changed) scheduleScoreColumnUpdate();
}

function restoreSavedRawResults() {
  try {
    const job = JSON.parse(localStorage.getItem(SCAN_JOB_STORAGE_KEY));
    captureRawResults(job?.results);
  } catch (error) {
    console.warn("Unable to restore raw scan metrics", error);
  }
}

function isScanRequest(input) {
  try {
    const requestUrl = typeof input === "string" || input instanceof URL ? input : input?.url;
    return new URL(requestUrl, window.location.href).pathname === "/api/scan";
  } catch {
    return false;
  }
}

window.fetch = async function fetchWithScanMetricCapture(input, init) {
  const response = await originalFetch(input, init);

  if (response.ok && isScanRequest(input)) {
    response.clone().json().then(captureRawResults).catch(() => {});
  }

  return response;
};

function setScoreCell(cell, score, inputs) {
  cell.dataset.compositeMetric = SCORE_KEY;
  cell.classList.remove("positive", "negative");

  if (score == null) {
    cell.textContent = "—";
    cell.title = `${SCORE_DESCRIPTION}；必要數據缺漏、Beta = -1 或最大回撤為 0 時不計算。`;
    return;
  }

  cell.textContent = score.toFixed(4);
  cell.classList.add(score >= 0 ? "positive" : "negative");
  cell.title = [
    SCORE_DESCRIPTION,
    `Sortino ${inputs.sortino}`,
    `Alpha ${(inputs.alpha * 100).toFixed(4)}%`,
    `Beta ${inputs.beta}`,
    `MDD ${(inputs.mdd * 100).toFixed(4)}%`,
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

  const requiredLabels = ["最大回撤", "Sortino", "Beta", "Alpha"];
  if (!requiredLabels.every((label) => headerIndexes.has(label))) return;

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

  const mddIndex = headerIndexes.get("最大回撤");
  const sortinoIndex = headerIndexes.get("Sortino");
  const betaIndex = headerIndexes.get("Beta");
  const alphaIndex = headerIndexes.get("Alpha");

  [...(table.tBodies[0]?.rows || [])].forEach((row) => {
    const originalCells = [...row.cells].filter(
      (cell) => cell.dataset.compositeMetric !== SCORE_KEY,
    );
    if (originalCells.length <= Math.max(mddIndex, sortinoIndex, betaIndex, alphaIndex)) return;

    const ticker = normalizeTicker(originalCells[0].textContent);
    const rawItem = rawResults.get(ticker);
    const inputs = {
      mdd: rawMetric(rawItem, "mdd") ?? parseMetric(originalCells[mddIndex].textContent, true),
      sortino: rawMetric(rawItem, "sortino_ratio") ?? parseMetric(originalCells[sortinoIndex].textContent),
      beta: rawMetric(rawItem, "beta") ?? parseMetric(originalCells[betaIndex].textContent),
      alpha: rawMetric(rawItem, "alpha") ?? parseMetric(originalCells[alphaIndex].textContent, true),
    };
    const score = calculateScore(inputs.sortino, inputs.alpha, inputs.beta, inputs.mdd);

    let scoreCell = row.querySelector(`td[data-composite-metric="${SCORE_KEY}"]`);
    if (!scoreCell) {
      scoreCell = document.createElement("td");
      const alphaCell = originalCells[alphaIndex];
      alphaCell.insertAdjacentElement("afterend", scoreCell);
    }
    setScoreCell(scoreCell, score, inputs);
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

function initializeScoreColumn() {
  const table = document.querySelector(TABLE_SELECTOR);
  if (!table) return;

  observer = new MutationObserver(scheduleScoreColumnUpdate);
  observer.observe(table, { childList: true, subtree: true });
  table.addEventListener("click", handleTableSortClick, true);
  restoreSavedRawResults();
  scheduleScoreColumnUpdate();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeScoreColumn, { once: true });
} else {
  initializeScoreColumn();
}
