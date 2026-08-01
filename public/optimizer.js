import {
  SCORE_FORMULAS,
  buildScoreMatrix,
  scoreRecordFor,
} from "./scan-score-formulas.js?v=20260801.2";

const SOURCE_JOB_KEY = "backteststock-scan-job-v2";
const OPTIMIZER_JOB_KEY = "backteststock-optimizer-job-v1";
const CANDIDATE_COUNT = 20;
const HOLDING_COUNT = 10;
const SCAN_BATCH_SIZE = 100;
const EXACT_VERIFY_COUNT = 300;
const OBJECTIVES = Object.freeze([
  ["sortino_ratio", "最高 Sortino"],
  ["cagr", "最高 CAGR"],
  ["mdd_abs", "最低 |MDD|"],
  ["beta_abs", "最低 |Beta|"],
  ["alpha", "最高 Alpha"],
]);
const RANKING_FIELDS = Object.freeze([
  ["sortino_ratio", "Sortino"],
  ["cagr", "CAGR"],
  ["mdd_abs", "最低 |MDD|"],
  ["beta_abs", "最低 |Beta|"],
  ["alpha", "Alpha"],
  ...SCORE_FORMULAS.map((formula) => [formula.key, formula.label]),
]);

const dom = {
  sourceStatus: document.querySelector("#optimizer-source-status"),
  sourceTickers: document.querySelector("#optimizer-source-tickers"),
  startDate: document.querySelector("#optimizer-start-date"),
  endDate: document.querySelector("#optimizer-end-date"),
  benchmark: document.querySelector("#optimizer-benchmark"),
  rankingField: document.querySelector("#optimizer-ranking-field"),
  primaryObjective: document.querySelector("#optimizer-primary-objective"),
  bandRatio: document.querySelector("#optimizer-band-ratio"),
  bandPreview: document.querySelector("#optimizer-band-preview"),
  transactionCost: document.querySelector("#optimizer-cost-bps"),
  trainingRatio: document.querySelector("#optimizer-training-ratio"),
  searchBudget: document.querySelector("#optimizer-search-budget"),
  runButton: document.querySelector("#run-optimizer"),
  cancelButton: document.querySelector("#cancel-optimizer"),
  error: document.querySelector("#optimizer-error"),
  warning: document.querySelector("#optimizer-warning"),
  progress: document.querySelector("#optimizer-progress"),
  progressBar: document.querySelector("#optimizer-progress-bar"),
  progressLabel: document.querySelector("#optimizer-progress-label"),
  candidatePanel: document.querySelector("#optimizer-candidate-panel"),
  candidateSummary: document.querySelector("#optimizer-candidate-summary"),
  candidateTable: document.querySelector("#optimizer-candidate-table"),
  results: document.querySelector("#optimizer-results"),
  championGrid: document.querySelector("#optimizer-champions"),
  resultTable: document.querySelector("#optimizer-result-table"),
  paretoChart: document.querySelector("#optimizer-pareto-chart"),
  reproducibility: document.querySelector("#optimizer-reproducibility"),
  exportJson: document.querySelector("#export-optimizer-json"),
  exportCsv: document.querySelector("#export-optimizer-csv"),
};

let sourceJob = null;
let activeWorker = null;
let activeController = null;
let running = false;
let latestOutput = null;

function parseTickers(value) {
  return [...new Set(
    String(value || "")
      .toUpperCase()
      .split(/[\s,;]+/u)
      .map((item) => item.trim())
      .filter(Boolean),
  )];
}

function readSourceJob() {
  try {
    const parsed = JSON.parse(localStorage.getItem(SOURCE_JOB_KEY));
    return parsed && Array.isArray(parsed?.payload?.tickers) ? parsed : null;
  } catch {
    return null;
  }
}

function tenYearDefaultRange(now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(today);
  end.setDate(end.getDate() - 1);
  const startYear = today.getFullYear() - 10;
  const maxDay = new Date(startYear, today.getMonth() + 1, 0).getDate();
  const start = new Date(
    startYear,
    today.getMonth(),
    Math.min(today.getDate(), maxDay),
  );
  const format = (date) => [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
  return { startDate: format(start), endDate: format(end) };
}

function setError(message = "") {
  dom.error.textContent = message;
  dom.error.classList.toggle("hidden", !message);
}

function setWarning(message = "") {
  dom.warning.textContent = message;
  dom.warning.classList.toggle("hidden", !message);
}

function setProgress(stage, completed = 0, total = 1, detail = "") {
  const ratio = total > 0 ? Math.max(0, Math.min(completed / total, 1)) : 0;
  dom.progress.classList.remove("hidden");
  dom.progressBar.style.width = `${(ratio * 100).toFixed(1)}%`;
  dom.progressLabel.textContent = detail || `${stage} ${completed} / ${total}`;
}

function rankingLabel(value) {
  return RANKING_FIELDS.find(([key]) => key === value)?.[1] || value;
}

function initializeControls() {
  for (const [value, label] of RANKING_FIELDS) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    dom.rankingField.append(option);
  }
  for (const [value, label] of OBJECTIVES) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    dom.primaryObjective.append(option);
  }
  dom.rankingField.value = "sortino_ratio";
  dom.primaryObjective.value = "sortino_ratio";

  sourceJob = readSourceJob();
  const defaults = tenYearDefaultRange();
  const source = sourceJob?.payload || {};
  const tickers = Array.isArray(source.tickers) ? source.tickers : [];
  dom.sourceTickers.value = tickers.join(", ");
  dom.startDate.value = source.startDate || defaults.startDate;
  dom.endDate.value = source.endDate || defaults.endDate;
  dom.benchmark.value = source.benchmark || "SPY";
  dom.sourceStatus.textContent = tickers.length
    ? `已載入掃描工作 ${tickers.length} 檔；最佳化器會只用訓練期重新掃描與排序。`
    : "未找到既有掃描工作；請貼入至少 20 檔股票代碼。";
  updateBandPreview();
}

function updateBandPreview() {
  const ratio = Number(dom.bandRatio.value) / 100;
  const lower = 10 * (1 - ratio);
  const upper = 10 * (1 + ratio);
  dom.bandPreview.textContent = Number.isFinite(ratio)
    ? `10% 目標權重的允許區間：${lower.toFixed(2)}%～${upper.toFixed(2)}%`
    : "請輸入有效偏移比例。";
}

async function apiFetch(path, payload, timeoutMs = 260_000) {
  const controller = new AbortController();
  activeController = controller;
  const timeout = setTimeout(() => controller.abort("timeout"), timeoutMs);
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text.slice(0, 500) || `HTTP ${response.status}` };
    }
    if (!response.ok) {
      const error = new Error(data.error || `HTTP ${response.status}`);
      error.status = response.status;
      error.retryable = data.retryable !== false && response.status >= 500;
      throw error;
    }
    return data;
  } finally {
    clearTimeout(timeout);
    if (activeController === controller) activeController = null;
  }
}

async function decodeSnapshot(envelope) {
  const binary = Uint8Array.from(atob(envelope.data), (character) => (
    character.charCodeAt(0)
  ));
  if (typeof DecompressionStream !== "function") {
    throw new Error("目前瀏覽器不支援 gzip 資料快照，請使用最新版瀏覽器。");
  }
  const stream = new Blob([binary])
    .stream()
    .pipeThrough(new DecompressionStream("gzip"));
  const text = await new Response(stream).text();
  return JSON.parse(text);
}

async function scanTrainingBatch(payload, tickers) {
  let lastError;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      return await apiFetch("/api/scan", { ...payload, tickers });
    } catch (error) {
      lastError = error;
      if (!error.retryable || attempt === 2) break;
      await new Promise((resolve) => setTimeout(resolve, 1500 * attempt));
    }
  }
  throw lastError;
}

function addScoreFields(rows) {
  const matrix = buildScoreMatrix(rows);
  return rows.map((row) => {
    const next = { ...row };
    for (const formula of SCORE_FORMULAS) {
      const record = scoreRecordFor(matrix, row.ticker, formula.key);
      next[formula.key] = record?.status === "ok" ? record.score : null;
    }
    return next;
  });
}

function rankingValue(row, field) {
  const rawField = field === "mdd_abs" ? "mdd" : field === "beta_abs" ? "beta" : field;
  const rawValue = row?.[rawField];
  if (rawValue == null || rawValue === "") return null;
  const numeric = Number(rawValue);
  if (!Number.isFinite(numeric)) return null;
  return field === "mdd_abs" || field === "beta_abs"
    ? Math.abs(numeric)
    : numeric;
}

function rankCandidates(rows, field, benchmark) {
  const excluded = [];
  const eligible = [];
  for (const row of addScoreFields(rows)) {
    const reasons = [];
    if (row.ticker === benchmark) reasons.push("與比較基準相同");
    if (row.status !== "ok" || row.error) reasons.push(row.error || "回測失敗");
    const coverage = Number(row.data_coverage);
    if (!Number.isFinite(coverage) || coverage < 0.98) {
      reasons.push("資料覆蓋率缺漏或低於 98%");
    }
    if (row.corporate_action_status !== "verified_standard_actions") {
      reasons.push(`公司行為稽核=${row.corporate_action_status || "unknown"}`);
    }
    if (rankingValue(row, field) == null) reasons.push("排序指標缺漏");
    if (reasons.length) excluded.push({ ticker: row.ticker, reasons });
    else eligible.push(row);
  }

  const ascending = field === "mdd_abs" || field === "beta_abs";
  eligible.sort((left, right) => {
    const difference = rankingValue(left, field) - rankingValue(right, field);
    if (Math.abs(difference) > 1e-12) return ascending ? difference : -difference;
    return left.ticker.localeCompare(right.ticker);
  });
  return {
    candidates: eligible.slice(0, CANDIDATE_COUNT),
    eligible,
    excluded,
  };
}

function formatMetric(value, type = "number") {
  if (value == null || value === "") return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  if (type === "percent") return `${(numeric * 100).toFixed(2)}%`;
  return numeric.toFixed(3);
}

function renderCandidates(selection, field, calendar) {
  dom.candidatePanel.classList.remove("hidden");
  dom.candidateSummary.textContent = [
    `訓練期 ${calendar.trainingStart}～${calendar.trainingEnd}`,
    `以「${rankingLabel(field)}」排序`,
    `合格 ${selection.eligible.length} 檔`,
    `取前 ${selection.candidates.length} 檔`,
    `排除 ${selection.excluded.length} 檔`,
  ].join(" · ");
  dom.candidateTable.innerHTML = `
    <thead>
      <tr><th>排名</th><th>股票</th><th>排序值</th><th>Sortino</th><th>CAGR</th><th>MDD</th><th>Beta</th><th>Alpha</th></tr>
    </thead>
    <tbody>
      ${selection.candidates.map((row, index) => `
        <tr>
          <td>${index + 1}</td>
          <td>${row.ticker}</td>
          <td>${formatMetric(
            rankingValue(row, field),
            ["cagr", "mdd_abs", "alpha"].includes(field) ? "percent" : "number",
          )}</td>
          <td>${formatMetric(row.sortino_ratio)}</td>
          <td>${formatMetric(row.cagr, "percent")}</td>
          <td>${formatMetric(row.mdd, "percent")}</td>
          <td>${formatMetric(row.beta)}</td>
          <td>${formatMetric(row.alpha, "percent")}</td>
        </tr>
      `).join("")}
    </tbody>
  `;
}

function workerProgressLabel(stage) {
  return {
    proxy: "全體 184,756 組快速評分",
    selected: "建立 30,000 組深度搜尋集合",
    deep: "深度等權路徑評分",
  }[stage] || stage;
}

function runSearchWorker(snapshot, settings) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(
      "/optimizer-worker.js?v=20260801.1",
      { type: "module" },
    );
    activeWorker = worker;
    worker.addEventListener("message", (event) => {
      const message = event.data || {};
      if (message.type === "progress") {
        setProgress(
          message.stage,
          message.completed,
          message.total,
          `${workerProgressLabel(message.stage)}：${message.completed.toLocaleString()} / ${message.total.toLocaleString()}`,
        );
      } else if (message.type === "complete") {
        activeWorker = null;
        worker.terminate();
        resolve(message.result);
      } else if (message.type === "error") {
        activeWorker = null;
        worker.terminate();
        reject(new Error(message.error || "最佳化 Worker 發生錯誤。"));
      }
    });
    worker.addEventListener("error", (event) => {
      activeWorker = null;
      worker.terminate();
      reject(new Error(event.message || "最佳化 Worker 無法執行。"));
    });
    worker.postMessage({ type: "optimize", snapshot, settings });
  });
}

async function verifyCombinations(snapshotEnvelope, combinations, settings) {
  const results = [];
  let metadata = null;
  const verificationBatches = [];
  const chunks = [];
  for (let offset = 0; offset < combinations.length; offset += 100) {
    chunks.push(combinations.slice(offset, offset + 100));
  }
  for (let index = 0; index < chunks.length; index += 1) {
    setProgress(
      "verify",
      index,
      chunks.length,
      `Python 精確複驗：第 ${index + 1} / ${chunks.length} 批`,
    );
    const response = await apiFetch(
      "/api/optimizer/verify",
      {
        snapshot: snapshotEnvelope,
        combinations: chunks[index],
        settings,
      },
      260_000,
    );
    results.push(...response.results);
    metadata = response.metadata;
    verificationBatches.push({
      batch: index + 1,
      requested: chunks[index].length,
      returned: response.results.length,
      backendVerifiedCombinations: response.metadata?.verified_combinations ?? null,
    });
  }
  setProgress("verify", chunks.length, chunks.length, "300 組精確複驗完成");
  return {
    results,
    metadata: {
      ...(metadata || {}),
      verified_combinations: results.length,
      verification_batch_count: chunks.length,
      verification_batches: verificationBatches,
    },
  };
}

function metricObjectiveValue(result, objective, period = "training") {
  const row = result[period] || {};
  const rawField = objective === "mdd_abs" ? "mdd" : objective === "beta_abs" ? "beta" : objective;
  const rawValue = row[rawField];
  if (rawValue == null || rawValue === "") return Number.NEGATIVE_INFINITY;
  const numeric = Number(rawValue);
  if (!Number.isFinite(numeric)) return Number.NEGATIVE_INFINITY;
  if (objective === "mdd_abs" || objective === "beta_abs") return -Math.abs(numeric);
  return numeric;
}

function compareExact(left, right, objective, period = "training") {
  const difference = (
    metricObjectiveValue(right, objective, period)
    - metricObjectiveValue(left, objective, period)
  );
  if (Math.abs(difference) > 1e-12) return difference;
  return left.mask - right.mask;
}

function exactPareto(results, period = "training") {
  const dimensions = (result) => {
    const row = result[period];
    return [
      Number(row.sortino_ratio),
      Number(row.cagr),
      Number(row.alpha),
      -Math.abs(Number(row.mdd)),
      -Math.abs(Number(row.beta)),
      -Number(row.annualizedTurnoverOneWay),
    ];
  };
  return results.filter((candidate, index) => {
    const candidateValues = dimensions(candidate);
    return !results.some((other, otherIndex) => {
      if (index === otherIndex) return false;
      const values = dimensions(other);
      let strict = false;
      for (let dimension = 0; dimension < values.length; dimension += 1) {
        if (values[dimension] < candidateValues[dimension] - 1e-12) return false;
        if (values[dimension] > candidateValues[dimension] + 1e-12) strict = true;
      }
      return strict;
    });
  });
}

function renderChampions(results) {
  dom.championGrid.innerHTML = OBJECTIVES.map(([objective, label]) => {
    const champion = [...results].sort(
      (left, right) => compareExact(left, right, objective),
    )[0];
    return `
      <article class="optimizer-champion">
        <p class="eyebrow">${label}</p>
        <h4>${champion.tickers.join(" · ")}</h4>
        <dl>
          <div><dt>訓練 Sortino</dt><dd>${formatMetric(champion.training.sortino_ratio)}</dd></div>
          <div><dt>訓練 CAGR</dt><dd>${formatMetric(champion.training.cagr, "percent")}</dd></div>
          <div><dt>訓練 MDD</dt><dd>${formatMetric(champion.training.mdd, "percent")}</dd></div>
          <div><dt>樣本外 Sortino</dt><dd>${formatMetric(champion.validation.sortino_ratio)}</dd></div>
          <div><dt>樣本外 CAGR</dt><dd>${formatMetric(champion.validation.cagr, "percent")}</dd></div>
          <div><dt>樣本外 MDD</dt><dd>${formatMetric(champion.validation.mdd, "percent")}</dd></div>
        </dl>
      </article>
    `;
  }).join("");
}

function renderResultTable(results, primaryObjective) {
  const sorted = [...results].sort(
    (left, right) => compareExact(left, right, primaryObjective),
  );
  dom.resultTable.innerHTML = `
    <thead>
      <tr>
        <th>訓練排名</th><th>持股</th><th>訓練 Sortino</th><th>訓練 CAGR</th>
        <th>訓練 MDD</th><th>訓練 Beta</th><th>訓練 Alpha</th>
        <th>樣本外 Sortino</th><th>樣本外 CAGR</th><th>樣本外 MDD</th>
        <th>年化單邊換手</th><th>再平衡次數</th>
      </tr>
    </thead>
    <tbody>
      ${sorted.map((row, index) => `
        <tr>
          <td>${index + 1}</td>
          <td class="optimizer-holdings">${row.tickers.join(", ")}</td>
          <td>${formatMetric(row.training.sortino_ratio)}</td>
          <td>${formatMetric(row.training.cagr, "percent")}</td>
          <td>${formatMetric(row.training.mdd, "percent")}</td>
          <td>${formatMetric(row.training.beta)}</td>
          <td>${formatMetric(row.training.alpha, "percent")}</td>
          <td>${formatMetric(row.validation.sortino_ratio)}</td>
          <td>${formatMetric(row.validation.cagr, "percent")}</td>
          <td>${formatMetric(row.validation.mdd, "percent")}</td>
          <td>${formatMetric(row.training.annualizedTurnoverOneWay, "percent")}</td>
          <td>${row.training.rebalanceCount}</td>
        </tr>
      `).join("")}
    </tbody>
  `;
}

function renderPareto(results) {
  const pareto = exactPareto(results);
  const width = 900;
  const height = 420;
  const padding = 55;
  const xValues = pareto.map((row) => Math.abs(Number(row.training.mdd)));
  const yValues = pareto.map((row) => Number(row.training.cagr));
  const xMax = Math.max(...xValues, 0.01);
  const yMin = Math.min(...yValues, 0);
  const yMax = Math.max(...yValues, 0.01);
  const x = (value) => padding + (value / xMax) * (width - padding * 2);
  const y = (value) => (
    height - padding
    - ((value - yMin) / Math.max(yMax - yMin, 1e-9)) * (height - padding * 2)
  );
  dom.paretoChart.setAttribute("viewBox", `0 0 ${width} ${height}`);
  dom.paretoChart.innerHTML = `
    <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" class="chart-axis"/>
    <line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}" class="chart-axis"/>
    <text x="${width / 2}" y="${height - 12}" class="chart-label">訓練期 |MDD|（越左越低）</text>
    <text x="18" y="${height / 2}" transform="rotate(-90 18 ${height / 2})" class="chart-label">訓練期 CAGR（越上越高）</text>
    ${pareto.map((row) => `
      <circle
        cx="${x(Math.abs(Number(row.training.mdd)))}"
        cy="${y(Number(row.training.cagr))}"
        r="5"
        tabindex="0"
      >
        <title>${row.tickers.join(", ")}｜CAGR ${formatMetric(row.training.cagr, "percent")}｜MDD ${formatMetric(row.training.mdd, "percent")}</title>
      </circle>
    `).join("")}
  `;
}

function renderReproducibility(output) {
  const summary = {
    sourceScanJobId: output.sourceJobId,
    candidateSelection: output.candidateSelection,
    snapshot: {
      datasetHash: output.snapshotEnvelope.datasetHash,
      signature: output.snapshotEnvelope.signature,
      signatureMode: output.snapshotEnvelope.signatureMode,
      compressedBytes: output.snapshotEnvelope.compressedBytes,
    },
    search: {
      ...output.search,
      evaluatedMasks: `[${output.search.evaluatedMasks.length} masks; included in JSON export]`,
    },
    verificationMetadata: output.verificationMetadata,
  };
  dom.reproducibility.textContent = JSON.stringify(summary, null, 2);
}

function download(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function csvCell(value) {
  const text = value == null ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function exportCsv() {
  if (!latestOutput) return;
  const headers = [
    "training_rank",
    "tickers",
    "training_sortino",
    "training_cagr",
    "training_mdd",
    "training_beta",
    "training_alpha",
    "validation_sortino",
    "validation_cagr",
    "validation_mdd",
    "validation_beta",
    "validation_alpha",
    "training_annualized_turnover_one_way",
    "validation_annualized_turnover_one_way",
    "training_rebalance_count",
    "validation_rebalance_count",
    "training_transaction_cost",
    "validation_transaction_cost",
    "portfolio_value_fingerprint_training",
    "portfolio_value_fingerprint_validation",
  ];
  const rows = [...latestOutput.results]
    .sort((left, right) => compareExact(
      left,
      right,
      latestOutput.settings.primaryObjective,
    ))
    .map((row, index) => [
      index + 1,
      row.tickers.join("|"),
      row.training.sortino_ratio,
      row.training.cagr,
      row.training.mdd,
      row.training.beta,
      row.training.alpha,
      row.validation.sortino_ratio,
      row.validation.cagr,
      row.validation.mdd,
      row.validation.beta,
      row.validation.alpha,
      row.training.annualizedTurnoverOneWay,
      row.validation.annualizedTurnoverOneWay,
      row.training.rebalanceCount,
      row.validation.rebalanceCount,
      row.training.transactionCost,
      row.validation.transactionCost,
      row.training.portfolioValueFingerprint,
      row.validation.portfolioValueFingerprint,
    ]);
  download(
    "optimizer-results.csv",
    [headers, ...rows].map((row) => row.map(csvCell).join(",")).join("\n"),
    "text/csv;charset=utf-8",
  );
}

function exportJson() {
  if (!latestOutput) return;
  download(
    "optimizer-audit.json",
    JSON.stringify(latestOutput, null, 2),
    "application/json;charset=utf-8",
  );
}

function saveCompactJob(output) {
  const compact = {
    completedAt: output.completedAt,
    sourceJobId: output.sourceJobId,
    candidateSelection: output.candidateSelection,
    settings: output.settings,
    snapshotSummary: output.snapshotSummary,
    search: {
      ...output.search,
      evaluatedMasks: undefined,
    },
    results: output.results.map((row) => ({
      combinationId: row.combinationId,
      mask: row.mask,
      tickers: row.tickers,
      selectionSource: row.selectionSource,
      training: {
        ...row.training,
        rebalanceEvents: undefined,
        unexecutedFinalSignal: undefined,
      },
      validation: {
        ...row.validation,
        rebalanceEvents: undefined,
        unexecutedFinalSignal: undefined,
      },
    })),
    verificationMetadata: output.verificationMetadata,
  };
  try {
    localStorage.setItem(OPTIMIZER_JOB_KEY, JSON.stringify(compact));
  } catch (error) {
    console.warn("Unable to persist optimizer summary", error);
  }
}

async function executeOptimizer() {
  if (running) return;
  setError();
  setWarning();
  dom.results.classList.add("hidden");
  dom.candidatePanel.classList.add("hidden");

  const sourceTickers = parseTickers(dom.sourceTickers.value);
  if (sourceTickers.length < CANDIDATE_COUNT) {
    setError(`來源股票至少需要 ${CANDIDATE_COUNT} 檔。`);
    return;
  }
  const startDate = dom.startDate.value;
  const endDate = dom.endDate.value;
  const benchmark = String(dom.benchmark.value || "SPY").trim().toUpperCase();
  if (!startDate || !endDate || startDate > endDate) {
    setError("請提供有效的起訖日期。");
    return;
  }

  const bandRatio = Number(dom.bandRatio.value) / 100;
  const transactionCostBps = Number(dom.transactionCost.value);
  const trainingRatio = Number(dom.trainingRatio.value) / 100;
  const searchBudget = Number(dom.searchBudget.value);
  if (!Number.isFinite(bandRatio) || bandRatio <= 0 || bandRatio >= 1) {
    setError("偏移比例必須大於 0% 且小於 100%。");
    return;
  }
  if (!Number.isFinite(transactionCostBps) || transactionCostBps < 0) {
    setError("交易成本不得小於 0 bps。");
    return;
  }

  running = true;
  dom.runButton.disabled = true;
  dom.cancelButton.classList.remove("hidden");
  const rankingField = dom.rankingField.value;
  const primaryObjective = dom.primaryObjective.value;

  try {
    setProgress("calendar", 0, 1, "建立 70% 訓練期與 30% 樣本外期間");
    const calendar = await apiFetch("/api/optimizer/calendar", {
      startDate,
      endDate,
      benchmark,
      trainingRatio,
    });
    if (
      calendar.benchmarkCorporateActionAudit?.status
      !== "verified_standard_actions"
    ) {
      throw new Error("比較基準未通過公司行為稽核，不能執行嚴格最佳化。");
    }

    const trainingRows = [];
    const batchCount = Math.ceil(sourceTickers.length / SCAN_BATCH_SIZE);
    for (let offset = 0; offset < sourceTickers.length; offset += SCAN_BATCH_SIZE) {
      const batchIndex = Math.floor(offset / SCAN_BATCH_SIZE);
      const batch = sourceTickers.slice(offset, offset + SCAN_BATCH_SIZE);
      setProgress(
        "candidate-scan",
        batchIndex,
        batchCount,
        `訓練期重新掃描：第 ${batchIndex + 1} / ${batchCount} 批`,
      );
      const rows = await scanTrainingBatch(
        {
          benchmark,
          startDate,
          endDate: calendar.trainingEnd,
        },
        batch,
      );
      trainingRows.push(...rows);
    }
    setProgress(
      "candidate-scan",
      batchCount,
      batchCount,
      "訓練期掃描完成，建立前 20 名候選池",
    );
    const selection = rankCandidates(trainingRows, rankingField, benchmark);
    if (selection.candidates.length < CANDIDATE_COUNT) {
      const sample = selection.excluded
        .slice(0, 10)
        .map((item) => `${item.ticker}: ${item.reasons.join("、")}`)
        .join("；");
      throw new Error(
        `嚴格條件下只有 ${selection.candidates.length} 檔合格，無法建立 20 檔候選池。${sample ? ` ${sample}` : ""}`,
      );
    }
    renderCandidates(selection, rankingField, calendar);

    const candidateSelection = {
      mode: "strict_training_only",
      sourceTickerCount: sourceTickers.length,
      rankingField,
      rankingLabel: rankingLabel(rankingField),
      trainingStart: calendar.trainingStart,
      trainingEnd: calendar.trainingEnd,
      minimumDataCoverage: 0.98,
      requiredCorporateActionStatus: "verified_standard_actions",
      eligibleCount: selection.eligible.length,
      excludedCount: selection.excluded.length,
      candidateTickers: selection.candidates.map((row) => row.ticker),
    };

    setProgress("prepare", 0, 1, "一次取得 20 檔候選股與基準的簽章資料快照");
    const prepared = await apiFetch(
      "/api/optimizer/prepare",
      {
        startDate,
        endDate,
        benchmark,
        trainingRatio,
        trainingEnd: calendar.trainingEnd,
        candidateTickers: candidateSelection.candidateTickers,
        candidateSelection,
      },
      260_000,
    );
    const snapshot = prepared.snapshotData || await decodeSnapshot(prepared.snapshot);
    setProgress("prepare", 1, 1, "簽章資料快照完成");

    const settings = {
      primaryObjective,
      searchBudget,
      bandRatio,
      transactionCostBps,
      targetWeight: 0.1,
      holdings: HOLDING_COUNT,
      exactVerificationCount: EXACT_VERIFY_COUNT,
      executionDelayTradingDays: 1,
      executionPrice: "next_common_trading_day_adjusted_close",
    };
    const searchResult = await runSearchWorker(snapshot, settings);
    const verified = await verifyCombinations(
      prepared.snapshot,
      searchResult.combinations,
      settings,
    );
    const selectionById = new Map(
      searchResult.combinations.map((item) => [item.combinationId, item]),
    );
    const results = verified.results.map((result) => ({
      ...result,
      selectionSource: selectionById.get(result.combinationId)?.selectionSource,
      approximateTrainingMetrics: (
        selectionById.get(result.combinationId)?.approximateTrainingMetrics
      ),
    }));

    latestOutput = {
      completedAt: new Date().toISOString(),
      sourceJobId: sourceJob?.id || null,
      candidateSelection,
      excludedCandidates: selection.excluded,
      settings,
      snapshotEnvelope: prepared.snapshot,
      snapshotSummary: prepared.summary,
      search: searchResult.search,
      results,
      verificationMetadata: verified.metadata,
      trainingParetoMasks: exactPareto(results, "training").map((row) => row.mask),
      validationDescriptiveParetoMasks: exactPareto(results, "validation")
        .map((row) => row.mask),
      disclaimer: "樣本外排序僅作事後描述；正式策略候選由訓練期預先選定。",
    };
    renderChampions(results);
    renderResultTable(results, primaryObjective);
    renderPareto(results);
    renderReproducibility(latestOutput);
    dom.results.classList.remove("hidden");
    saveCompactJob(latestOutput);
    setProgress("complete", 1, 1, "最佳化、精確複驗與樣本外驗證全部完成");
  } catch (error) {
    if (String(error?.name) === "AbortError" || String(error?.message).includes("取消")) {
      setWarning("最佳化已取消；尚未完成的結果不會列為正式輸出。");
    } else {
      setError(error instanceof Error ? error.message : String(error));
    }
  } finally {
    running = false;
    dom.runButton.disabled = false;
    dom.cancelButton.classList.add("hidden");
    activeController = null;
    if (activeWorker) {
      activeWorker.terminate();
      activeWorker = null;
    }
  }
}

function cancelOptimizer() {
  activeController?.abort("cancelled");
  activeWorker?.postMessage({ type: "cancel" });
  setWarning("正在取消目前工作…");
}

dom.bandRatio.addEventListener("input", updateBandPreview);
dom.runButton.addEventListener("click", executeOptimizer);
dom.cancelButton.addEventListener("click", cancelOptimizer);
dom.exportJson.addEventListener("click", exportJson);
dom.exportCsv.addEventListener("click", exportCsv);
window.addEventListener("beforeunload", (event) => {
  if (!running) return;
  event.preventDefault();
  event.returnValue = "";
});

initializeControls();
