import {
  EXHAUSTIVE_ENGINE_VERSION,
  MAX_EXHAUSTIVE_COMBINATIONS,
  METRIC_KEYS,
  binomialBigInt,
  combinationCountNumber,
  estimateResultBytes,
  estimateSnapshotBytes,
  formatBytes,
  formatDuration,
  relativeBandBounds,
  unrankCombination,
} from "./exhaustive-optimizer-core.js?v=20260803.2";
import {
  CompactResultRetention,
  MAX_PERSISTED_RESULTS,
  RETENTION_METRIC_KEYS,
  createRetentionPlan,
  estimateCompactResultBytes,
  estimateRetentionWorkingBytes,
} from "./exhaustive-retention.js?v=20260803.2";
import {
  deleteJob,
  getChunk,
  getJob,
  getRetainedChunk,
  listChunks,
  listJobs,
  saveChunk,
  saveJob,
  saveRetainedChunk,
} from "./exhaustive-optimizer-storage.js?v=20260803.2";

const SCAN_JOB_KEY = "backteststock-scan-job-v3";
const MANUAL_SELECTION_KEY = "backteststock-optimizer-manual-selection-v2";
const DATE_MODE_KEY = "backteststock-exhaustive-date-mode-v1";
const CUSTOM_RANGE_KEY = "backteststock-exhaustive-custom-range-v1";
const WORKER_URL = "/exhaustive-optimizer-worker.js?v=20260803.2";
const SORT_WORKER_URL = "/exhaustive-sort-worker.js?v=20260803.2";
const PAGE_SIZE = 100;
const CALIBRATION_SAMPLE = 160;
const SOFT_WARNING_COMBINATIONS = 1_000_000;
const LEGACY_FULL_RESULT_LIMIT = MAX_PERSISTED_RESULTS;
const RETAINED_CHUNK_SIZE = 25_000;
const VALUATION_CURRENCY = "TWD";

const METRIC_LABELS = Object.freeze({
  total_return: "總報酬",
  cagr: "CAGR",
  mdd: "|MDD|",
  volatility: "波動率",
  sortino_ratio: "Sortino",
  beta: "Beta",
  alpha: "Alpha",
  annualized_turnover_one_way: "年化單邊換手",
  rebalance_count: "再平衡次數",
  transaction_cost: "累計交易成本",
  stable_score: "穩健分數",
  growth_score: "成長分數",
  drawdown_score: "回撤控制分數",
  optimized_score: "優化分數",
});

const dom = Object.fromEntries([
  "source", "start", "end", "benchmark", "holdingCount", "rebalanceMode",
  "bandRatio", "bandPreview", "costBps", "executionDelay", "workerCount",
  "combinationCount", "staticEstimate", "preflightButton", "preflightProgress",
  "preflightError", "confirmation", "confirmationSummary", "startButton",
  "cancelConfirmation", "runPanel", "runProgressBar", "runProgressLabel",
  "pauseButton", "resumeButton", "discardButton", "resultPanel", "sortField",
  "sortDirection", "filterSortino", "filterCagr", "filterMdd", "applySort",
  "resultSummary", "resultBody", "previousPage", "nextPage", "pageLabel",
  "exportPage", "exportAll", "detailPanel", "detailTitle", "detailBody",
  "closeDetail", "jobHistory", "resetDates",
].map((id) => [id, document.querySelector(`#optimizer-${id.replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`)}`)]));

let prepared = null;
let activeJob = null;
let activeWorkers = [];
let runResolve = null;
let stopRequested = false;
let sortedIds = null;
let currentPage = 0;
let currentSortConfig = { field: "optimized_score", direction: "desc" };
let activeRetention = null;

function parseTickers(value) {
  return [...new Set(
    String(value || "")
      .toUpperCase()
      .split(/[\s,;]+/u)
      .map((ticker) => ticker.trim())
      .filter(Boolean),
  )];
}

function readJson(key) {
  try {
    return JSON.parse(localStorage.getItem(key));
  } catch {
    return null;
  }
}

function formatDate(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

function rollingRange(now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(today);
  end.setDate(end.getDate() - 1);
  const startYear = today.getFullYear() - 10;
  const maxDay = new Date(startYear, today.getMonth() + 1, 0).getDate();
  const start = new Date(startYear, today.getMonth(), Math.min(today.getDate(), maxDay));
  return { startDate: formatDate(start), endDate: formatDate(end) };
}

function initializeDates() {
  const current = rollingRange();
  const mode = localStorage.getItem(DATE_MODE_KEY);
  const custom = readJson(CUSTOM_RANGE_KEY);
  if (mode === "custom" && custom?.startDate && custom?.endDate) {
    dom.start.value = custom.startDate;
    dom.end.value = custom.endDate;
  } else {
    dom.start.value = current.startDate;
    dom.end.value = current.endDate;
    localStorage.setItem(DATE_MODE_KEY, "automatic");
    localStorage.removeItem(CUSTOM_RANGE_KEY);
  }
  const record = () => {
    const latest = rollingRange();
    if (dom.start.value === latest.startDate && dom.end.value === latest.endDate) {
      localStorage.setItem(DATE_MODE_KEY, "automatic");
      localStorage.removeItem(CUSTOM_RANGE_KEY);
    } else {
      localStorage.setItem(DATE_MODE_KEY, "custom");
      localStorage.setItem(CUSTOM_RANGE_KEY, JSON.stringify({
        startDate: dom.start.value,
        endDate: dom.end.value,
      }));
    }
  };
  dom.start.addEventListener("change", record);
  dom.end.addEventListener("change", record);
}

function initializeSource() {
  const scanJob = readJson(SCAN_JOB_KEY);
  const manual = readJson(MANUAL_SELECTION_KEY);
  const queryMode = new URLSearchParams(location.search).get("mode");
  let tickers = [];
  if (
    queryMode === "manual"
    && manual?.sourceJobId === scanJob?.id
    && Array.isArray(manual?.tickers)
  ) {
    tickers = manual.tickers;
  } else if (Array.isArray(scanJob?.payload?.tickers)) {
    tickers = scanJob.payload.tickers;
  }
  dom.source.value = [...new Set(tickers)].join(", ");
  dom.benchmark.value = scanJob?.payload?.benchmark || "SPY";
}

function defaultWorkers() {
  const available = Math.max(1, Number(navigator.hardwareConcurrency) || 4);
  return Math.min(8, Math.max(1, available - 1));
}

function getSettings() {
  return {
    holdingCount: Number(dom.holdingCount.value),
    rebalanceMode: dom.rebalanceMode.value,
    bandRatio: Number(dom.bandRatio.value) / 100,
    transactionCostBps: Number(dom.costBps.value),
    executionDelayTradingDays: Number(dom.executionDelay.value),
    workerCount: Number(dom.workerCount.value),
  };
}

function validateInputs() {
  const tickers = parseTickers(dom.source.value);
  const settings = getSettings();
  if (tickers.length < 2) throw new Error("來源股票至少需要 2 檔。");
  if (!Number.isInteger(settings.holdingCount) || settings.holdingCount < 1) {
    throw new Error("每組持股數必須是正整數。");
  }
  if (settings.holdingCount > tickers.length) {
    throw new Error("每組持股數不可大於來源股票數。");
  }
  if (!dom.start.value || !dom.end.value || dom.start.value > dom.end.value) {
    throw new Error("請提供有效的起訖日期。");
  }
  if (!Number.isFinite(settings.bandRatio) || settings.bandRatio <= 0 || settings.bandRatio >= 1) {
    throw new Error("權重相對偏移必須介於 0% 與 100% 之間。");
  }
  if (!Number.isFinite(settings.transactionCostBps) || settings.transactionCostBps < 0) {
    throw new Error("交易成本不得小於 0 bps。");
  }
  if (!Number.isInteger(settings.workerCount) || settings.workerCount < 1 || settings.workerCount > 16) {
    throw new Error("Worker 數必須介於 1 與 16。");
  }
  const total = combinationCountNumber(tickers.length, settings.holdingCount);
  if (total > MAX_EXHAUSTIVE_COMBINATIONS) {
    throw new Error(
      `完整組合共 ${total.toLocaleString()} 組，超過目前安全上限 `
      + `${MAX_EXHAUSTIVE_COMBINATIONS.toLocaleString()} 組。請減少來源股票或調整持股數。`,
    );
  }
  return { tickers, settings, total };
}

function updateBandPreview() {
  const tickers = parseTickers(dom.source.value);
  const k = Math.max(1, Math.min(Number(dom.holdingCount.value) || 1, Math.max(tickers.length, 1)));
  const ratio = Number(dom.bandRatio.value) / 100;
  const bounds = relativeBandBounds(k, Number.isFinite(ratio) ? ratio : 0.2);
  dom.bandPreview.textContent = [
    `每檔目標 ${(bounds.target * 100).toFixed(4)}%`,
    `允許區間 ${(bounds.lower * 100).toFixed(4)}%～${(bounds.upper * 100).toFixed(4)}%`,
  ].join("；");
  dom.bandRatio.disabled = dom.rebalanceMode.value !== "band";
}

function refreshStaticEstimate() {
  try {
    const tickers = parseTickers(dom.source.value);
    const k = Number(dom.holdingCount.value);
    if (!tickers.length || !Number.isInteger(k) || k < 1 || k > tickers.length) {
      dom.combinationCount.textContent = "—";
      dom.staticEstimate.textContent = "輸入股票池與每組持股數後計算。";
      return;
    }
    const count = binomialBigInt(tickers.length, k);
    dom.combinationCount.textContent = count.toLocaleString("en-US");
    const numeric = count <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(count) : Number.POSITIVE_INFINITY;
    if (!Number.isFinite(numeric)) {
      dom.staticEstimate.textContent = "組合數超過瀏覽器安全整數範圍。";
    } else if (numeric <= LEGACY_FULL_RESULT_LIMIT) {
      dom.staticEstimate.textContent = `完整結果估計約 ${formatBytes(estimateResultBytes(numeric, k))}；執行前會以本機實測校準時間。`;
    } else {
      const plan = createRetentionPlan(numeric);
      dom.staticEstimate.textContent = [
        `完整計算 ${numeric.toLocaleString()} 組`,
        `精簡保存最多 ${plan.target.toLocaleString()} 組約 ${formatBytes(estimateCompactResultBytes(plan.target))}`,
        `暫存選取緩衝約 ${formatBytes(estimateRetentionWorkingBytes(plan))}`,
      ].join("；");
    }
  } catch (error) {
    dom.staticEstimate.textContent = error.message;
  }
  updateBandPreview();
}

async function apiFetch(path, payload, timeoutMs = 260_000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
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
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  } finally {
    clearTimeout(timeout);
  }
}

async function decodeSnapshot(envelope) {
  const bytes = Uint8Array.from(atob(envelope.data), (character) => character.charCodeAt(0));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(stream).text());
}

function workerRequest(worker, request, expectedType, timeoutMs = 300_000) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      cleanup();
      reject(new Error(`Worker ${request.type} 逾時。`));
    }, timeoutMs);
    const onMessage = (event) => {
      const message = event.data || {};
      if (message.type === "error") {
        cleanup();
        reject(new Error(message.error || "Worker 執行失敗。"));
      } else if (message.type === expectedType) {
        cleanup();
        resolve(message);
      }
    };
    const onError = (event) => {
      cleanup();
      reject(new Error(event.message || "Worker 無法執行。"));
    };
    const cleanup = () => {
      clearTimeout(timeout);
      worker.removeEventListener("message", onMessage);
      worker.removeEventListener("error", onError);
    };
    worker.addEventListener("message", onMessage);
    worker.addEventListener("error", onError);
    worker.postMessage(request);
  });
}

async function createInitializedWorker(snapshot) {
  const worker = new Worker(WORKER_URL, { type: "module" });
  await workerRequest(worker, { type: "init", snapshot }, "ready", 60_000);
  return worker;
}

function calibrationRanks(total) {
  const count = Math.min(CALIBRATION_SAMPLE, total);
  if (count <= 1) return ["0"];
  const output = [];
  const maximum = BigInt(total - 1);
  for (let index = 0; index < count; index += 1) {
    output.push(String(maximum * BigInt(index) / BigInt(count - 1)));
  }
  return output;
}

async function runPreflight() {
  dom.preflightError.textContent = "";
  dom.confirmation.classList.add("hidden");
  dom.preflightButton.disabled = true;
  try {
    const input = validateInputs();
    dom.preflightProgress.textContent = "下載並驗證完整期間行情…";
    const response = await apiFetch("/api/optimizer/exhaustive/prepare", {
      sourceTickers: input.tickers,
      benchmark: String(dom.benchmark.value || "SPY").trim().toUpperCase(),
      startDate: dom.start.value,
      endDate: dom.end.value,
    });
    const snapshot = await decodeSnapshot(response.snapshot);
    snapshot.datasetHash = response.snapshot.datasetHash;
    if (snapshot.valuationCurrency !== VALUATION_CURRENCY) {
      throw new Error("資料預檢未提供 TWD 估值快照，已停止全量回測。");
    }
    dom.preflightProgress.textContent = "以目前電腦執行精確回測校準…";
    const worker = await createInitializedWorker(snapshot);
    const calibration = await workerRequest(
      worker,
      {
        type: "calibrate",
        ranks: calibrationRanks(input.total),
        settings: input.settings,
      },
      "calibrated",
    );
    worker.terminate();
    const singleRate = calibration.completed / Math.max(calibration.elapsedMs / 1000, 0.001);
    const effectiveRate = singleRate * input.settings.workerCount * 0.72;
    const estimateSeconds = input.total / Math.max(effectiveRate, 0.01);
    const low = estimateSeconds * 0.85;
    const high = estimateSeconds * 1.35;
    const chunkSize = Math.max(25, Math.min(1000, Math.round(singleRate * 2.2)));
    const observations = response.summary.observations;
    const compactPlan = input.total > LEGACY_FULL_RESULT_LIMIT
      ? createRetentionPlan(input.total)
      : null;
    const resultBytes = compactPlan
      ? estimateCompactResultBytes(compactPlan.target)
      : estimateResultBytes(input.total, input.settings.holdingCount);
    const snapshotBytes = estimateSnapshotBytes(input.tickers.length, observations);
    prepared = {
      ...input,
      response,
      snapshot,
      calibration: {
        ...calibration,
        singleRate,
        effectiveRate,
        estimateSeconds,
        chunkSize,
      },
    };
    const bounds = relativeBandBounds(input.settings.holdingCount, input.settings.bandRatio);
    const warning = input.total >= SOFT_WARNING_COMBINATIONS
      ? "這是大型工作，建議保持電源與分頁開啟；進度會分批保存，可中止後續跑。"
      : "工作會分批保存，可在中止後從已完成批次繼續。";
    dom.confirmationSummary.innerHTML = `
      <dl class="estimate-grid">
        <div><dt>固定來源池</dt><dd>${input.tickers.length.toLocaleString()} 檔</dd></div>
        <div><dt>每組持股</dt><dd>${input.settings.holdingCount} 檔等權</dd></div>
        <div><dt>完整組合</dt><dd>${input.total.toLocaleString()} 組</dd></div>
        <div><dt>共同交易日</dt><dd>${observations.toLocaleString()} 日</dd></div>
        <div><dt>估值幣別</dt><dd>${snapshot.valuationCurrency}</dd></div>
        <div><dt>目標權重</dt><dd>${(bounds.target * 100).toFixed(4)}%</dd></div>
        <div><dt>再平衡區間</dt><dd>${input.settings.rebalanceMode === "band" ? `${(bounds.lower * 100).toFixed(4)}%～${(bounds.upper * 100).toFixed(4)}%` : input.settings.rebalanceMode}</dd></div>
        <div><dt>本機單 Worker</dt><dd>${singleRate.toFixed(1)} 組／秒</dd></div>
        <div><dt>預估時間</dt><dd>${formatDuration(low)}～${formatDuration(high)}</dd></div>
        <div><dt>快照記憶體</dt><dd>${formatBytes(snapshotBytes * input.settings.workerCount)}</dd></div>
        <div><dt>${compactPlan ? "精簡保存結果" : "結果摘要"}</dt><dd>${formatBytes(resultBytes)}</dd></div>
        ${compactPlan ? `<div><dt>選取工作暫存</dt><dd>${formatBytes(estimateRetentionWorkingBytes(compactPlan))}</dd></div>` : ""}
      </dl>
      <p class="message warning">${warning}</p>
      <p class="form-note">本模式使用完整期間做歷史排名，不宣稱為未見資料預測；全部 ${input.total.toLocaleString()} 組都使用同一份簽章 TWD 還原股價快照與相同精確再平衡規則。${compactPlan ? ` 完整計算後會保留最多 ${compactPlan.target.toLocaleString()} 組代表性結果供排序與匯出。` : ""}</p>`;
    dom.confirmation.classList.remove("hidden");
    dom.preflightProgress.textContent = "預檢與實機校準完成，等待確認。";
  } catch (error) {
    dom.preflightError.textContent = error instanceof Error ? error.message : String(error);
    dom.preflightProgress.textContent = "預檢失敗。";
  } finally {
    dom.preflightButton.disabled = false;
  }
}

async function hashText(text) {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
}

async function buildJob(preflight) {
  const settings = preflight.settings;
  const signature = await hashText(JSON.stringify({
    datasetHash: preflight.response.snapshot.datasetHash,
    tickers: preflight.tickers,
    settings,
    engineVersion: EXHAUSTIVE_ENGINE_VERSION,
  }));
  const chunkSize = preflight.calibration.chunkSize;
  const totalChunks = Math.ceil(preflight.total / chunkSize);
  const existing = await getJob(signature);
  if (existing && existing.total === preflight.total && existing.status !== "discarded") {
    return existing;
  }
  const job = {
    id: signature,
    status: "ready",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    engineVersion: EXHAUSTIVE_ENGINE_VERSION,
    datasetHash: preflight.response.snapshot.datasetHash,
    snapshotEnvelope: preflight.response.snapshot,
    snapshotSummary: preflight.response.summary,
    sourceTickers: preflight.tickers,
    benchmark: preflight.snapshot.benchmark,
    settings,
    total: preflight.total,
    storageMode: preflight.total > LEGACY_FULL_RESULT_LIMIT ? "compact" : "full",
    chunkSize,
    totalChunks,
    completedChunks: [],
    completedCombinations: 0,
    elapsedMs: 0,
    measuredSingleWorkerRate: preflight.calibration.singleRate,
  };
  await saveJob(job);
  return job;
}

function setRunProgress(job, label = "") {
  const ratio = job.total ? job.completedCombinations / job.total : 0;
  dom.runProgressBar.style.width = `${Math.min(100, ratio * 100).toFixed(2)}%`;
  const speed = job.elapsedMs > 0 ? job.completedCombinations / (job.elapsedMs / 1000) : 0;
  const remaining = speed > 0 ? (job.total - job.completedCombinations) / speed : Number.NaN;
  dom.runProgressLabel.textContent = label || [
    `${job.completedCombinations.toLocaleString()} / ${job.total.toLocaleString()} 組`,
    `${(ratio * 100).toFixed(2)}%`,
    speed > 0 ? `${speed.toFixed(1)} 組／秒` : "測速中",
    Number.isFinite(remaining) ? `約剩 ${formatDuration(remaining)}` : "",
  ].filter(Boolean).join(" · ");
}

function terminateActiveWorkers() {
  for (const worker of activeWorkers) worker.terminate();
  activeWorkers = [];
}

async function runFullResultJob(job, snapshot) {
  stopRequested = false;
  activeJob = { ...job, status: "running", startedAt: job.startedAt || new Date().toISOString() };
  await saveJob(activeJob);
  dom.runPanel.classList.remove("hidden");
  dom.pauseButton.classList.remove("hidden");
  dom.resumeButton.classList.add("hidden");
  dom.resultPanel.classList.add("hidden");
  setRunProgress(activeJob, "初始化平行 Worker…");

  const completed = new Set(activeJob.completedChunks || []);
  const queue = [];
  for (let chunkIndex = 0; chunkIndex < activeJob.totalChunks; chunkIndex += 1) {
    if (!completed.has(chunkIndex)) queue.push(chunkIndex);
  }
  let inFlight = 0;
  let finished = false;
  let failed = null;

  await new Promise((resolve, reject) => {
    runResolve = resolve;
    const maybeFinish = async () => {
      if (failed) {
        terminateActiveWorkers();
        reject(failed);
        return;
      }
      if (stopRequested && inFlight === 0) {
        terminateActiveWorkers();
        activeJob.status = "paused";
        await saveJob(activeJob);
        finished = true;
        resolve();
        return;
      }
      if (!queue.length && inFlight === 0 && !finished) {
        terminateActiveWorkers();
        activeJob.status = "completed";
        activeJob.completedAt = new Date().toISOString();
        await saveJob(activeJob);
        finished = true;
        resolve();
      }
    };

    const dispatch = (worker) => {
      if (failed || finished || stopRequested) {
        maybeFinish();
        return;
      }
      const chunkIndex = queue.shift();
      if (chunkIndex == null) {
        maybeFinish();
        return;
      }
      const startRank = chunkIndex * activeJob.chunkSize;
      const count = Math.min(activeJob.chunkSize, activeJob.total - startRank);
      inFlight += 1;
      worker.postMessage({
        type: "run-chunk",
        chunkIndex,
        startRank: String(startRank),
        count,
        settings: activeJob.settings,
      });
    };

    const onWorkerMessage = async (worker, event) => {
      const message = event.data || {};
      if (message.type === "error") {
        failed = new Error(message.error || "Worker 執行失敗。");
        inFlight = Math.max(0, inFlight - 1);
        maybeFinish();
        return;
      }
      if (message.type !== "chunk-complete") return;
      inFlight -= 1;
      await saveChunk(activeJob.id, {
        ...message,
        holdingCount: activeJob.settings.holdingCount,
        metricCount: METRIC_KEYS.length,
      });
      if (!completed.has(message.chunkIndex)) {
        completed.add(message.chunkIndex);
        activeJob.completedChunks = [...completed].sort((a, b) => a - b);
        activeJob.completedCombinations += message.completed;
        activeJob.elapsedMs += message.elapsedMs;
      }
      await saveJob(activeJob);
      setRunProgress(activeJob);
      dispatch(worker);
    };

    Promise.all(
      Array.from({ length: activeJob.settings.workerCount }, async () => {
        const worker = await createInitializedWorker(snapshot);
        activeWorkers.push(worker);
        worker.addEventListener("message", (event) => {
          onWorkerMessage(worker, event).catch((error) => {
            failed = error;
            maybeFinish();
          });
        });
        worker.addEventListener("error", (event) => {
          failed = new Error(event.message || "Worker 無法執行。");
          maybeFinish();
        });
        dispatch(worker);
      }),
    ).catch((error) => {
      failed = error;
      maybeFinish();
    });
  });
  runResolve = null;

  if (activeJob.status === "completed") {
    dom.pauseButton.classList.add("hidden");
    dom.resumeButton.classList.add("hidden");
    setRunProgress(activeJob, "全量精確回測完成，建立排序索引…");
    await showResults(activeJob);
  } else {
    dom.pauseButton.classList.add("hidden");
    dom.resumeButton.classList.remove("hidden");
    setRunProgress(activeJob, "工作已中止並保留完成批次，可稍後繼續。" );
  }
  await renderJobHistory();
}

function restoreOrRestartCompactRetention(job) {
  if (
    job.retentionState
    && job.retentionStateCompleted === job.completedCombinations
  ) {
    return CompactResultRetention.fromState(job.retentionState);
  }
  if (job.completedCombinations > 0) {
    // A completed-chunk list without its rank/score checkpoint cannot be used
    // safely: retaining only the later chunks would distort the global top set.
    // Recompute is deterministic and preserves correctness after an unplanned
    // browser reload rather than silently returning a biased subset.
    job.completedChunks = [];
    job.completedCombinations = 0;
    job.elapsedMs = 0;
  }
  return new CompactResultRetention(job.total);
}

async function materializeRetainedResults(job, snapshot, selection) {
  const retained = selection || job.retainedSelection;
  if (!retained?.ranks || !retained?.reasons) {
    throw new Error("找不到精簡保存結果的選取清單。");
  }
  const ranks = retained.ranks instanceof Uint32Array
    ? retained.ranks
    : Uint32Array.from(retained.ranks);
  const reasons = retained.reasons instanceof Uint8Array
    ? retained.reasons
    : Uint8Array.from(retained.reasons);
  if (ranks.length !== reasons.length) throw new Error("精簡保存結果的選取清單損毀。");

  activeJob = {
    ...job,
    status: "materializing",
    resumePhase: "materializing",
    retainedSelection: { ranks, reasons },
    retainedTotal: ranks.length,
    retainedCount: ranks.length,
    resultChunkSize: RETAINED_CHUNK_SIZE,
    materializedChunks: job.materializedChunks || [],
    materializedCombinations: job.materializedCombinations || 0,
  };
  await saveJob(activeJob);
  dom.runPanel.classList.remove("hidden");
  dom.pauseButton.classList.remove("hidden");
  dom.resumeButton.classList.add("hidden");
  dom.resultPanel.classList.add("hidden");

  const completed = new Set(activeJob.materializedChunks);
  const totalChunks = Math.ceil(ranks.length / RETAINED_CHUNK_SIZE);
  const queue = [];
  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex += 1) {
    if (!completed.has(chunkIndex)) queue.push(chunkIndex);
  }
  let inFlight = 0;
  let finished = false;
  let failed = null;
  stopRequested = false;
  setRunProgress(
    activeJob,
    `完整計算完成，正精簡保存 ${activeJob.materializedCombinations.toLocaleString()} / ${ranks.length.toLocaleString()} 組…`,
  );

  await new Promise((resolve, reject) => {
    runResolve = resolve;
    const maybeFinish = async () => {
      if (failed) {
        terminateActiveWorkers();
        reject(failed);
        return;
      }
      if (stopRequested && inFlight === 0) {
        terminateActiveWorkers();
        activeJob.status = "paused";
        await saveJob(activeJob);
        finished = true;
        resolve();
        return;
      }
      if (!queue.length && inFlight === 0 && !finished) {
        terminateActiveWorkers();
        activeJob.status = "completed";
        activeJob.completedAt = new Date().toISOString();
        activeJob.retainedCount = ranks.length;
        delete activeJob.retainedSelection;
        delete activeJob.resumePhase;
        await saveJob(activeJob);
        finished = true;
        resolve();
      }
    };

    const dispatch = (worker) => {
      if (failed || finished || stopRequested) {
        maybeFinish();
        return;
      }
      const chunkIndex = queue.shift();
      if (chunkIndex == null) {
        maybeFinish();
        return;
      }
      const rowStart = chunkIndex * RETAINED_CHUNK_SIZE;
      const batchRanks = ranks.slice(
        rowStart,
        Math.min(ranks.length, rowStart + RETAINED_CHUNK_SIZE),
      );
      inFlight += 1;
      worker.postMessage({
        type: "materialize-ranks",
        chunkIndex,
        rowStart,
        ranks: batchRanks,
        settings: activeJob.settings,
      });
    };

    const onWorkerMessage = async (worker, event) => {
      const message = event.data || {};
      if (message.type === "error") {
        failed = new Error(message.error || "Worker 精簡保存失敗。");
        inFlight = Math.max(0, inFlight - 1);
        maybeFinish();
        return;
      }
      if (message.type !== "materialized") return;
      inFlight -= 1;
      const expected = Math.min(
        RETAINED_CHUNK_SIZE,
        ranks.length - Number(message.rowStart),
      );
      if (message.completed !== expected) {
        failed = new Error("Worker 未完成精簡保存批次，結果沒有被靜默截斷。");
        maybeFinish();
        return;
      }
      await saveRetainedChunk(activeJob.id, {
        chunkIndex: message.chunkIndex,
        rowStart: message.rowStart,
        count: message.completed,
        ranks: ranks.slice(message.rowStart, message.rowStart + message.completed),
        reasons: reasons.slice(message.rowStart, message.rowStart + message.completed),
        metricCount: METRIC_KEYS.length,
        metrics: message.metrics,
      });
      if (!completed.has(message.chunkIndex)) {
        completed.add(message.chunkIndex);
        activeJob.materializedChunks = [...completed].sort((left, right) => left - right);
        activeJob.materializedCombinations += message.completed;
      }
      await saveJob(activeJob);
      setRunProgress(
        activeJob,
        `完整計算完成，正精簡保存 ${activeJob.materializedCombinations.toLocaleString()} / ${ranks.length.toLocaleString()} 組…`,
      );
      dispatch(worker);
    };

    Promise.all(
      Array.from({ length: activeJob.settings.workerCount }, async () => {
        const worker = await createInitializedWorker(snapshot);
        activeWorkers.push(worker);
        worker.addEventListener("message", (event) => {
          onWorkerMessage(worker, event).catch((error) => {
            failed = error;
            maybeFinish();
          });
        });
        worker.addEventListener("error", (event) => {
          failed = new Error(event.message || "Worker 無法精簡保存結果。");
          maybeFinish();
        });
        dispatch(worker);
      }),
    ).catch((error) => {
      failed = error;
      maybeFinish();
    });
  });
  runResolve = null;

  if (activeJob.status === "completed") {
    dom.pauseButton.classList.add("hidden");
    dom.resumeButton.classList.add("hidden");
    setRunProgress(activeJob, `完整計算與 ${ranks.length.toLocaleString()} 組精簡保存結果已完成。`);
    await showResults(activeJob);
  } else {
    dom.pauseButton.classList.add("hidden");
    dom.resumeButton.classList.remove("hidden");
    setRunProgress(activeJob, "精簡保存已中止；可稍後從已保存結果繼續。");
  }
  await renderJobHistory();
}

async function runCompactJob(job, snapshot) {
  if (job.resumePhase === "materializing" && job.retainedSelection) {
    await materializeRetainedResults(job, snapshot, job.retainedSelection);
    return;
  }
  stopRequested = false;
  activeJob = {
    ...job,
    status: "running",
    startedAt: job.startedAt || new Date().toISOString(),
  };
  activeRetention = restoreOrRestartCompactRetention(activeJob);
  delete activeJob.retentionState;
  delete activeJob.retentionStateCompleted;
  await saveJob(activeJob);
  dom.runPanel.classList.remove("hidden");
  dom.pauseButton.classList.remove("hidden");
  dom.resumeButton.classList.add("hidden");
  dom.resultPanel.classList.add("hidden");
  setRunProgress(activeJob, "初始化平行 Worker，完整計算後精簡保存…");

  const completed = new Set(activeJob.completedChunks || []);
  const queue = [];
  for (let chunkIndex = 0; chunkIndex < activeJob.totalChunks; chunkIndex += 1) {
    if (!completed.has(chunkIndex)) queue.push(chunkIndex);
  }
  let inFlight = 0;
  let finished = false;
  let failed = null;

  await new Promise((resolve, reject) => {
    runResolve = resolve;
    const maybeFinish = async () => {
      if (failed) {
        terminateActiveWorkers();
        reject(failed);
        return;
      }
      if (stopRequested && inFlight === 0) {
        terminateActiveWorkers();
        activeJob.status = "paused";
        activeJob.retentionState = activeRetention.toState();
        activeJob.retentionStateCompleted = activeJob.completedCombinations;
        await saveJob(activeJob);
        finished = true;
        resolve();
        return;
      }
      if (!queue.length && inFlight === 0 && !finished) {
        terminateActiveWorkers();
        activeJob.status = "materializing";
        finished = true;
        resolve();
      }
    };

    const dispatch = (worker) => {
      if (failed || finished || stopRequested) {
        maybeFinish();
        return;
      }
      const chunkIndex = queue.shift();
      if (chunkIndex == null) {
        maybeFinish();
        return;
      }
      const startRank = chunkIndex * activeJob.chunkSize;
      const count = Math.min(activeJob.chunkSize, activeJob.total - startRank);
      inFlight += 1;
      worker.postMessage({
        type: "run-chunk",
        resultMode: "retention",
        chunkIndex,
        startRank: String(startRank),
        count,
        settings: activeJob.settings,
      });
    };

    const onWorkerMessage = async (worker, event) => {
      const message = event.data || {};
      if (message.type === "error") {
        failed = new Error(message.error || "Worker 執行失敗。");
        inFlight = Math.max(0, inFlight - 1);
        maybeFinish();
        return;
      }
      if (message.type !== "chunk-complete") return;
      inFlight -= 1;
      if (message.resultMode !== "retention") {
        failed = new Error("Worker 未回傳精簡保存所需的結果格式。");
        maybeFinish();
        return;
      }
      if (message.completed !== message.requestedCount) {
        failed = new Error("Worker 未完成計算批次，結果沒有被靜默截斷。");
        maybeFinish();
        return;
      }
      activeRetention.acceptMetricArray(
        Number(message.startRank),
        new Float64Array(message.metrics),
        message.metricKeys || RETENTION_METRIC_KEYS,
      );
      if (!completed.has(message.chunkIndex)) {
        completed.add(message.chunkIndex);
        activeJob.completedChunks = [...completed].sort((left, right) => left - right);
        activeJob.completedCombinations += message.completed;
        activeJob.elapsedMs += message.elapsedMs;
      }
      await saveJob(activeJob);
      setRunProgress(activeJob);
      dispatch(worker);
    };

    Promise.all(
      Array.from({ length: activeJob.settings.workerCount }, async () => {
        const worker = await createInitializedWorker(snapshot);
        activeWorkers.push(worker);
        worker.addEventListener("message", (event) => {
          onWorkerMessage(worker, event).catch((error) => {
            failed = error;
            maybeFinish();
          });
        });
        worker.addEventListener("error", (event) => {
          failed = new Error(event.message || "Worker 無法執行。");
          maybeFinish();
        });
        dispatch(worker);
      }),
    ).catch((error) => {
      failed = error;
      maybeFinish();
    });
  });
  runResolve = null;

  if (activeJob.status === "materializing") {
    const selection = activeRetention.finalize();
    activeRetention = null;
    await materializeRetainedResults(activeJob, snapshot, selection);
    return;
  }
  dom.pauseButton.classList.add("hidden");
  dom.resumeButton.classList.remove("hidden");
  setRunProgress(activeJob, "工作已中止並保存選取狀態，可稍後繼續。");
  await renderJobHistory();
}

async function runJob(job, snapshot) {
  const storageMode = job.storageMode || (
    job.total > LEGACY_FULL_RESULT_LIMIT ? "compact" : "full"
  );
  if (storageMode === "compact") {
    await runCompactJob({ ...job, storageMode }, snapshot);
    return;
  }
  await runFullResultJob({ ...job, storageMode: "full" }, snapshot);
}

async function startPreparedJob() {
  if (!prepared) return;
  dom.startButton.disabled = true;
  try {
    const job = await buildJob(prepared);
    dom.confirmation.classList.add("hidden");
    await runJob(job, prepared.snapshot);
  } catch (error) {
    dom.preflightError.textContent = error instanceof Error ? error.message : String(error);
    terminateActiveWorkers();
  } finally {
    dom.startButton.disabled = false;
  }
}

async function pauseJob() {
  if (!activeJob || !["running", "materializing"].includes(activeJob.status)) return;
  stopRequested = true;
  terminateActiveWorkers();
  activeJob.status = "paused";
  if (
    activeJob.storageMode === "compact"
    && activeJob.resumePhase !== "materializing"
    && activeRetention
  ) {
    activeJob.retentionState = activeRetention.toState();
    activeJob.retentionStateCompleted = activeJob.completedCombinations;
  }
  await saveJob(activeJob);
  if (runResolve) runResolve();
  dom.pauseButton.classList.add("hidden");
  dom.resumeButton.classList.remove("hidden");
  setRunProgress(activeJob, "已中止；已完成批次均已保存。" );
}

async function resumeJob(jobId = activeJob?.id) {
  const job = await getJob(jobId);
  if (!job) return;
  assertTwdJob(job);
  const snapshot = await decodeSnapshot(job.snapshotEnvelope);
  snapshot.datasetHash = job.datasetHash;
  await runJob(job, snapshot);
}

async function discardActiveJob() {
  if (!activeJob) return;
  terminateActiveWorkers();
  await deleteJob(activeJob.id);
  activeJob = null;
  activeRetention = null;
  sortedIds = null;
  dom.runPanel.classList.add("hidden");
  dom.resultPanel.classList.add("hidden");
  await renderJobHistory();
}

function metricIndex(field) {
  return METRIC_KEYS.indexOf(field);
}

function passesFilters(metrics, offset) {
  const minSortino = Number(dom.filterSortino.value);
  const minCagr = Number(dom.filterCagr.value) / 100;
  const maxMdd = Number(dom.filterMdd.value) / 100;
  const sortino = metrics[offset + metricIndex("sortino_ratio")];
  const cagr = metrics[offset + metricIndex("cagr")];
  const mdd = Math.abs(metrics[offset + metricIndex("mdd")]);
  if (dom.filterSortino.value !== "" && (!Number.isFinite(sortino) || sortino < minSortino)) return false;
  if (dom.filterCagr.value !== "" && (!Number.isFinite(cagr) || cagr < minCagr)) return false;
  if (dom.filterMdd.value !== "" && (!Number.isFinite(mdd) || mdd > maxMdd)) return false;
  return true;
}

async function buildSortedIndex(job, field, direction) {
  if (job.storageMode === "compact") {
    return buildCompactSortedIndex(job, field, direction);
  }
  const index = metricIndex(field);
  if (index < 0) throw new Error("不支援的排序欄位。");
  dom.resultSummary.textContent = "讀取結果摘要並建立排序索引…";
  const values = new Float64Array(job.total);
  const ids = new Uint32Array(job.total);
  let accepted = 0;
  for (let chunkIndex = 0; chunkIndex < job.totalChunks; chunkIndex += 1) {
    const chunk = await getChunk(job.id, chunkIndex);
    if (!chunk) throw new Error(`缺少結果批次 ${chunkIndex}。`);
    const metrics = new Float64Array(chunk.metrics);
    for (let row = 0; row < chunk.count; row += 1) {
      const offset = row * METRIC_KEYS.length;
      if (!passesFilters(metrics, offset)) continue;
      ids[accepted] = Number(chunk.startRank) + row;
      values[accepted] = metrics[offset + index];
      accepted += 1;
    }
  }
  const compactValues = values.slice(0, accepted);
  const compactIds = ids.slice(0, accepted);
  const worker = new Worker(SORT_WORKER_URL);
  const absolute = field === "mdd" || field === "beta";
  const result = await workerRequest(
    worker,
    {
      type: "sort",
      values: compactValues.buffer,
      ids: compactIds.buffer,
      direction,
      absolute,
    },
    "sorted",
    600_000,
  );
  worker.terminate();
  return new Uint32Array(result.indexes);
}

async function buildCompactSortedIndex(job, field, direction) {
  const index = metricIndex(field);
  if (index < 0) throw new Error("不支援的排序欄位。");
  const retainedCount = Number(job.retainedCount || job.retainedTotal || 0);
  if (!retainedCount) throw new Error("找不到精簡保存的回測結果。");
  dom.resultSummary.textContent = "讀取精簡保存結果並建立排序索引…";
  const values = new Float32Array(retainedCount);
  const ids = new Uint32Array(retainedCount);
  let accepted = 0;
  const chunkSize = Number(job.resultChunkSize || RETAINED_CHUNK_SIZE);
  const totalChunks = Math.ceil(retainedCount / chunkSize);
  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex += 1) {
    const chunk = await getRetainedChunk(job.id, chunkIndex);
    if (!chunk) throw new Error(`缺少精簡保存結果批次 ${chunkIndex + 1}。`);
    const metrics = new Float32Array(chunk.metrics);
    for (let row = 0; row < chunk.count; row += 1) {
      const offset = row * METRIC_KEYS.length;
      if (!passesFilters(metrics, offset)) continue;
      ids[accepted] = Number(chunk.rowStart) + row;
      values[accepted] = metrics[offset + index];
      accepted += 1;
    }
  }
  const worker = new Worker(SORT_WORKER_URL);
  const result = await workerRequest(
    worker,
    {
      type: "sort",
      values: values.slice(0, accepted).buffer,
      ids: ids.slice(0, accepted).buffer,
      valueType: "float32",
      direction,
      absolute: field === "mdd" || field === "beta",
    },
    "sorted",
    600_000,
  );
  worker.terminate();
  return new Uint32Array(result.indexes);
}

function formatMetric(key, value) {
  if (!Number.isFinite(value)) return "—";
  if (["total_return", "cagr", "mdd", "volatility", "alpha", "annualized_turnover_one_way", "transaction_cost"].includes(key)) {
    return `${(value * 100).toFixed(2)}%`;
  }
  if (key === "rebalance_count") return Math.round(value).toLocaleString();
  return value.toFixed(4);
}

async function rowFromGlobalId(job, id, cache) {
  if (job.storageMode === "compact") return rowFromRetainedId(job, id, cache);
  const chunkIndex = Math.floor(id / job.chunkSize);
  let chunk = cache.get(chunkIndex);
  if (!chunk) {
    chunk = await getChunk(job.id, chunkIndex);
    cache.set(chunkIndex, chunk);
    if (cache.size > 16) cache.delete(cache.keys().next().value);
  }
  const row = id - Number(chunk.startRank);
  const combinations = new Uint16Array(chunk.combinations);
  const metrics = new Float64Array(chunk.metrics);
  const comboOffset = row * job.settings.holdingCount;
  const metricOffset = row * METRIC_KEYS.length;
  return {
    id,
    indexes: [...combinations.slice(comboOffset, comboOffset + job.settings.holdingCount)],
    metrics: Object.fromEntries(
      METRIC_KEYS.map((key, index) => [key, metrics[metricOffset + index]]),
    ),
  };
}

async function rowFromRetainedId(job, id, cache) {
  const chunkSize = Number(job.resultChunkSize || RETAINED_CHUNK_SIZE);
  const chunkIndex = Math.floor(id / chunkSize);
  let chunk = cache.get(chunkIndex);
  if (!chunk) {
    chunk = await getRetainedChunk(job.id, chunkIndex);
    if (!chunk) throw new Error(`缺少精簡保存結果批次 ${chunkIndex + 1}。`);
    cache.set(chunkIndex, chunk);
    if (cache.size > 16) cache.delete(cache.keys().next().value);
  }
  const row = id - Number(chunk.rowStart);
  if (row < 0 || row >= chunk.count) throw new Error("精簡保存結果列索引無效。");
  const ranks = new Uint32Array(chunk.ranks);
  const metrics = new Float32Array(chunk.metrics);
  const rank = ranks[row];
  const metricOffset = row * METRIC_KEYS.length;
  return {
    id,
    rank,
    indexes: [...unrankCombination(
      job.sourceTickers.length,
      job.settings.holdingCount,
      BigInt(rank),
    )],
    metrics: Object.fromEntries(
      METRIC_KEYS.map((key, index) => [key, metrics[metricOffset + index]]),
    ),
  };
}

async function renderResultPage() {
  if (!activeJob || !sortedIds) return;
  const pageCount = Math.max(1, Math.ceil(sortedIds.length / PAGE_SIZE));
  currentPage = Math.max(0, Math.min(currentPage, pageCount - 1));
  const start = currentPage * PAGE_SIZE;
  const ids = sortedIds.slice(start, Math.min(sortedIds.length, start + PAGE_SIZE));
  const cache = new Map();
  const rows = [];
  for (const id of ids) rows.push(await rowFromGlobalId(activeJob, id, cache));
  dom.resultBody.innerHTML = rows.map((row, index) => `
    <tr>
      <td>${(start + index + 1).toLocaleString()}</td>
      <td class="optimizer-holdings">${row.indexes.map((asset) => activeJob.sourceTickers[asset]).join(", ")}</td>
      <td>${formatMetric("optimized_score", row.metrics.optimized_score)}</td>
      <td>${formatMetric("sortino_ratio", row.metrics.sortino_ratio)}</td>
      <td>${formatMetric("cagr", row.metrics.cagr)}</td>
      <td>${formatMetric("mdd", row.metrics.mdd)}</td>
      <td>${formatMetric("beta", row.metrics.beta)}</td>
      <td>${formatMetric("alpha", row.metrics.alpha)}</td>
      <td>${formatMetric("annualized_turnover_one_way", row.metrics.annualized_turnover_one_way)}</td>
      <td>${formatMetric("rebalance_count", row.metrics.rebalance_count)}</td>
      <td><button class="button ghost compact" type="button" data-detail-id="${row.id}">詳情</button></td>
    </tr>`).join("");
  dom.pageLabel.textContent = `第 ${currentPage + 1} / ${pageCount.toLocaleString()} 頁`;
  dom.previousPage.disabled = currentPage <= 0;
  dom.nextPage.disabled = currentPage >= pageCount - 1;
  const resultScope = activeJob.storageMode === "compact"
    ? `完整計算 ${activeJob.total.toLocaleString()} 組，精簡保存 ${activeJob.retainedCount.toLocaleString()} 組`
    : `完整結果 ${activeJob.total.toLocaleString()} 組`;
  dom.resultSummary.textContent = [
    resultScope,
    `篩選後 ${sortedIds.length.toLocaleString()} 組`,
    `依 ${METRIC_LABELS[currentSortConfig.field]} ${currentSortConfig.direction === "asc" ? "由低到高" : "由高到低"}`,
  ].join(" · ");
}

async function showResults(job) {
  assertTwdJob(job);
  activeJob = job;
  dom.resultPanel.classList.remove("hidden");
  currentSortConfig = {
    field: dom.sortField.value || "optimized_score",
    direction: dom.sortDirection.value || "desc",
  };
  sortedIds = await buildSortedIndex(job, currentSortConfig.field, currentSortConfig.direction);
  currentPage = 0;
  await renderResultPage();
}

async function applySortAndFilters() {
  if (!activeJob || activeJob.status !== "completed") return;
  dom.applySort.disabled = true;
  try {
    currentSortConfig = { field: dom.sortField.value, direction: dom.sortDirection.value };
    sortedIds = await buildSortedIndex(activeJob, currentSortConfig.field, currentSortConfig.direction);
    currentPage = 0;
    await renderResultPage();
  } finally {
    dom.applySort.disabled = false;
  }
}

async function showDetail(globalId) {
  if (!activeJob) return;
  assertTwdJob(activeJob);
  const row = await rowFromGlobalId(activeJob, Number(globalId), new Map());
  const snapshot = await decodeSnapshot(activeJob.snapshotEnvelope);
  snapshot.datasetHash = activeJob.datasetHash;
  const worker = await createInitializedWorker(snapshot);
  const result = await workerRequest(
    worker,
    { type: "detail", indexes: row.indexes, settings: activeJob.settings },
    "detail-complete",
  );
  worker.terminate();
  dom.detailTitle.textContent = row.indexes.map((asset) => activeJob.sourceTickers[asset]).join(" · ");
  const metrics = result.metrics;
  dom.detailBody.innerHTML = `
    <dl class="estimate-grid">
      ${METRIC_KEYS.map((key) => `<div><dt>${METRIC_LABELS[key]}</dt><dd>${formatMetric(key, metrics[key])}</dd></div>`).join("")}
    </dl>
    <h4>再平衡事件（${metrics.events.length.toLocaleString()} 次）</h4>
    <div class="table-wrap"><table><thead><tr><th>訊號日序</th><th>執行日序</th><th>原因</th><th>觸發股票</th><th>交易成本</th></tr></thead><tbody>
      ${metrics.events.slice(0, 500).map((event) => `<tr>
        <td>${event.signalPosition}</td><td>${event.executionPosition}</td><td>${event.reason}</td>
        <td>${event.triggerIndexes.map((index) => activeJob.sourceTickers[row.indexes[index]]).join(", ") || "排程"}</td>
        <td>${formatMetric("transaction_cost", event.transactionCost)}</td>
      </tr>`).join("")}
    </tbody></table></div>
    ${metrics.events.length > 500 ? "<p class='form-note'>畫面僅顯示前 500 筆事件；摘要指標已使用完整事件。</p>" : ""}`;
  dom.detailPanel.classList.remove("hidden");
}

function csvCell(value) {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

function csvHeader() {
  return ["rank", "tickers", ...METRIC_KEYS].map(csvCell).join(",") + "\n";
}

async function csvLineForId(job, id, rank, cache) {
  const row = await rowFromGlobalId(job, id, cache);
  return [
    rank,
    row.indexes.map((asset) => job.sourceTickers[asset]).join("|"),
    ...METRIC_KEYS.map((key) => row.metrics[key]),
  ].map(csvCell).join(",") + "\n";
}

async function writeCsv(ids, filename) {
  const cache = new Map();
  if (window.showSaveFilePicker) {
    const handle = await window.showSaveFilePicker({
      suggestedName: filename,
      types: [{ description: "CSV", accept: { "text/csv": [".csv"] } }],
    });
    const writable = await handle.createWritable();
    await writable.write(new TextEncoder().encode(csvHeader()));
    for (let index = 0; index < ids.length; index += 1) {
      await writable.write(new TextEncoder().encode(
        await csvLineForId(activeJob, ids[index], index + 1, cache),
      ));
    }
    await writable.close();
    return;
  }
  const parts = [csvHeader()];
  for (let index = 0; index < ids.length; index += 1) {
    parts.push(await csvLineForId(activeJob, ids[index], index + 1, cache));
  }
  const url = URL.createObjectURL(new Blob(parts, { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function exportCurrentPage() {
  const start = currentPage * PAGE_SIZE;
  await writeCsv(sortedIds.slice(start, Math.min(sortedIds.length, start + PAGE_SIZE)), "optimizer-current-page.csv");
}

async function exportAllResults() {
  if (!sortedIds) return;
  if (sortedIds.length > 1_000_000 && !window.showSaveFilePicker) {
    throw new Error("此瀏覽器不支援串流檔案儲存；超過 100 萬列時請使用最新版 Chromium。" );
  }
  await writeCsv(sortedIds, "optimizer-all-results.csv");
}

async function renderJobHistory() {
  const jobs = await listJobs();
  if (!jobs.length) {
    dom.jobHistory.innerHTML = "<p class='form-note'>目前沒有保存中的全量工作。</p>";
    return;
  }
  dom.jobHistory.innerHTML = jobs.slice(0, 8).map((job) => {
    const compatible = isTwdJob(job);
    const action = !compatible
      ? "<span class='form-note'>舊版非 TWD 工作，請刪除後重新預檢。</span>"
      : job.status === "completed"
        ? `<button type="button" class="button ghost compact" data-job-results="${job.id}">查看結果</button>`
        : `<button type="button" class="button ghost compact" data-job-resume="${job.id}">繼續</button>`;
    return `
    <article class="saved-job">
      <div><strong>${job.sourceTickers.length} 選 ${job.settings.holdingCount}</strong>
      <span>${job.completedCombinations.toLocaleString()} / ${job.total.toLocaleString()} 組 · ${job.status}</span></div>
      <div class="toolbar">
        ${action}
        <button type="button" class="button ghost compact" data-job-delete="${job.id}">刪除</button>
      </div>
    </article>`;
  }).join("");
}

function isTwdJob(job) {
  return job?.engineVersion === EXHAUSTIVE_ENGINE_VERSION
    && job?.snapshotSummary?.valuationCurrency === VALUATION_CURRENCY;
}

function assertTwdJob(job) {
  if (!isTwdJob(job)) {
    throw new Error("此工作使用舊版或非 TWD 資料快照，請刪除後重新預檢。");
  }
}

function installMetricOptions() {
  dom.sortField.innerHTML = METRIC_KEYS.map((key) => (
    `<option value="${key}" ${key === "optimized_score" ? "selected" : ""}>${METRIC_LABELS[key]}</option>`
  )).join("");
}

function installEvents() {
  [dom.source, dom.holdingCount, dom.bandRatio, dom.rebalanceMode].forEach((element) => {
    element.addEventListener("input", refreshStaticEstimate);
    element.addEventListener("change", refreshStaticEstimate);
  });
  dom.resetDates.addEventListener("click", () => {
    const latest = rollingRange();
    dom.start.value = latest.startDate;
    dom.end.value = latest.endDate;
    localStorage.setItem(DATE_MODE_KEY, "automatic");
    localStorage.removeItem(CUSTOM_RANGE_KEY);
  });
  dom.preflightButton.addEventListener("click", runPreflight);
  dom.startButton.addEventListener("click", startPreparedJob);
  dom.cancelConfirmation.addEventListener("click", () => dom.confirmation.classList.add("hidden"));
  dom.pauseButton.addEventListener("click", pauseJob);
  dom.resumeButton.addEventListener("click", () => resumeJob());
  dom.discardButton.addEventListener("click", discardActiveJob);
  dom.applySort.addEventListener("click", applySortAndFilters);
  dom.previousPage.addEventListener("click", async () => { currentPage -= 1; await renderResultPage(); });
  dom.nextPage.addEventListener("click", async () => { currentPage += 1; await renderResultPage(); });
  dom.resultBody.addEventListener("click", (event) => {
    const button = event.target.closest("[data-detail-id]");
    if (button) showDetail(button.dataset.detailId).catch((error) => alert(error.message));
  });
  dom.closeDetail.addEventListener("click", () => dom.detailPanel.classList.add("hidden"));
  dom.exportPage.addEventListener("click", () => exportCurrentPage().catch((error) => alert(error.message)));
  dom.exportAll.addEventListener("click", () => exportAllResults().catch((error) => alert(error.message)));
  dom.jobHistory.addEventListener("click", async (event) => {
    const resume = event.target.closest("[data-job-resume]");
    const results = event.target.closest("[data-job-results]");
    const remove = event.target.closest("[data-job-delete]");
    if (resume) await resumeJob(resume.dataset.jobResume);
    if (results) {
      const job = await getJob(results.dataset.jobResults);
      await showResults(job);
    }
    if (remove) {
      await deleteJob(remove.dataset.jobDelete);
      await renderJobHistory();
    }
  });
  window.addEventListener("beforeunload", (event) => {
    if (!activeJob || activeJob.status !== "running") return;
    event.preventDefault();
    event.returnValue = "";
  });
}

async function initialize() {
  initializeSource();
  initializeDates();
  dom.workerCount.value = String(defaultWorkers());
  installMetricOptions();
  installEvents();
  refreshStaticEstimate();
  await renderJobHistory();
}

initialize().catch((error) => {
  dom.preflightError.textContent = error instanceof Error ? error.message : String(error);
});
