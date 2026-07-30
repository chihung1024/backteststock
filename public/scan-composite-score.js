const TABLE_SELECTOR = "#scan-table";
const SCORE_KEY = "sortino_alpha_beta_mdd_score";
const SCORE_LABEL = "Sortino×Alpha/(1+Beta)/|MDD|";
const SCORE_DESCRIPTION = "Sortino × Alpha ÷ (1 + Beta) ÷ |最大回撤|";

let observer;
let updateScheduled = false;

function normalizeHeaderLabel(value) {
  return String(value || "")
    .replace(/\s+[▲▼]$/u, "")
    .trim();
}

function parseMetric(value, percent = false) {
  const text = String(value || "").trim();
  if (!text || text === "—") return null;

  const numeric = Number(text.replaceAll(",", "").replace("%", ""));
  if (!Number.isFinite(numeric)) return null;
  return percent ? numeric / 100 : numeric;
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
    `Alpha ${(inputs.alpha * 100).toFixed(2)}%`,
    `Beta ${inputs.beta}`,
    `MDD ${(inputs.mdd * 100).toFixed(2)}%`,
  ].join(" · ");
}

function updateScoreColumn() {
  const table = document.querySelector(TABLE_SELECTOR);
  const headerRow = table?.tHead?.rows?.[0];
  if (!table || !headerRow) return;

  const originalHeaders = [...headerRow.cells];
  const headerIndexes = new Map(
    originalHeaders.map((cell, index) => [normalizeHeaderLabel(cell.textContent), index]),
  );

  const requiredLabels = ["最大回撤", "Sortino", "Beta", "Alpha"];
  if (!requiredLabels.every((label) => headerIndexes.has(label))) return;

  let scoreHeader = headerRow.querySelector(`th[data-composite-metric="${SCORE_KEY}"]`);
  if (!scoreHeader) {
    scoreHeader = document.createElement("th");
    scoreHeader.scope = "col";
    scoreHeader.textContent = SCORE_LABEL;
    scoreHeader.title = SCORE_DESCRIPTION;
    scoreHeader.dataset.compositeMetric = SCORE_KEY;

    const alphaHeader = originalHeaders[headerIndexes.get("Alpha")];
    alphaHeader.insertAdjacentElement("afterend", scoreHeader);
  }

  const mddIndex = headerIndexes.get("最大回撤");
  const sortinoIndex = headerIndexes.get("Sortino");
  const betaIndex = headerIndexes.get("Beta");
  const alphaIndex = headerIndexes.get("Alpha");

  [...(table.tBodies[0]?.rows || [])].forEach((row) => {
    const originalCells = [...row.cells].filter(
      (cell) => cell.dataset.compositeMetric !== SCORE_KEY,
    );
    if (originalCells.length <= Math.max(mddIndex, sortinoIndex, betaIndex, alphaIndex)) return;

    const inputs = {
      mdd: parseMetric(originalCells[mddIndex].textContent, true),
      sortino: parseMetric(originalCells[sortinoIndex].textContent),
      beta: parseMetric(originalCells[betaIndex].textContent),
      alpha: parseMetric(originalCells[alphaIndex].textContent, true),
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
  scheduleScoreColumnUpdate();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeScoreColumn, { once: true });
} else {
  initializeScoreColumn();
}
