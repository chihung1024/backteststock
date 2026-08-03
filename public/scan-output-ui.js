import {
  SCORE_FORMULAS,
  buildScoreMatrix,
  normalizeScoreTicker,
  scoreRecordFor,
} from "./scan-score-formulas.js?v=20260803.4";
import {
  deriveScanCoverage,
} from "./scan-coverage.js?v=20260803.2";

const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v3";
const timingHistory = [];
const baseFetch = window.fetch.bind(window);
let timingScheduled = false;

const BASE_RESULT_HEADERS = [
  "ticker",
  "total_return",
  "cagr",
  "volatility",
  "mdd",
  "sharpe_ratio",
  "sortino_ratio",
  "beta",
  "alpha",
];
const SCORE_RANK_HEADERS = SCORE_FORMULAS.flatMap((formula) => [
  formula.key,
  formula.rankKey,
]);
const SCORE_AUDIT_HEADERS = SCORE_FORMULAS.flatMap((formula) => [
  formula.key,
  formula.rankKey,
  formula.statusKey,
]);
const RESULT_TAIL_HEADERS = [
  "data_coverage",
  "coverage_reference_trading_days",
  "coverage_definition_version",
  "benchmark_calendar_coverage",
  "trading_days",
  "data_start",
  "data_end",
  "note",
  "error",
];
const CONCISE_HEADERS = [
  ...BASE_RESULT_HEADERS,
  ...SCORE_RANK_HEADERS,
  ...RESULT_TAIL_HEADERS,
];
const AUDIT_HEADERS = [
  "ticker",
  "status",
  "retryable",
  "error_code",
  ...BASE_RESULT_HEADERS.slice(1),
  ...SCORE_AUDIT_HEADERS,
  ...RESULT_TAIL_HEADERS.slice(0, -2),
  "metric_start",
  "metric_end",
  "metric_price_observations",
  "metric_return_observations",
  "metric_definition_version",
  "data_source",
  "data_source_version",
  "numpy_version",
  "pandas_version",
  "scipy_version",
  "fingerprint_algorithm",
  "risk_free_rate",
  "trading_days_per_year",
  "benchmark",
  "benchmark_available",
  "requested_start",
  "requested_end_exclusive",
  "valuation_currency",
  "twd_valuation_contract_version",
  "calendar_policy",
  "quote_currency",
  "fx_audit",
  "return_basis",
  "return_price_column",
  "dividend_reinvestment_assumption",
  "market_data_contract_version",
  "corporate_action_policy_version",
  "corporate_action_status",
  "benchmark_corporate_action_status",
  "dividend_events",
  "stock_split_events",
  "capital_gain_events",
  "price_repaired_rows",
  "unexplained_adjustment_changes",
  "distribution_adjustment_mismatches",
  "split_like_unreported_changes",
  "large_unexplained_returns",
  "corporate_action_warning_dates",
  "standard_action_coverage",
  "nonstandard_action_limitations",
  "auto_adjust",
  "repair",
  "interval",
  "actions",
  "keepna",
  "price_fingerprint",
  "native_price_fingerprint",
  "fx_price_fingerprint",
  "aligned_price_fingerprint",
  "benchmark_price_fingerprint",
  "reproducibility",
  "valuation_metadata",
  "note",
  "error",
];

function readSavedJob() {
  try {
    const job = JSON.parse(localStorage.getItem(SCAN_JOB_STORAGE_KEY));
    return job && typeof job === "object" ? job : null;
  } catch {
    return null;
  }
}

function currentRows() {
  const rows = readSavedJob()?.results;
  return Array.isArray(rows) ? rows : [];
}

function rowsWithDerivedCoverage() {
  const source = currentRows();
  const derived = deriveScanCoverage(source);
  const derivedMap = new Map(derived.settled.map((item) => [normalizeScoreTicker(item.ticker), item]));
  return source.map((item) => (
    derivedMap.get(normalizeScoreTicker(item?.ticker)) || item
  ));
}

function humanNote(item) {
  const raw = String(item?.note || "")
    .trim()
    .replace(/^[（(]\s*/u, "")
    .replace(/\s*[）)]$/u, "");
  if (!raw) return "";
  return raw
    .split(/；?\s*再現資訊/u)[0]
    .replace(/[；;\s]+$/u, "")
    .trim();
}

function requestPath(input) {
  try {
    const value = typeof input === "string" || input instanceof URL ? input : input?.url;
    return new URL(value, window.location.href).pathname;
  } catch {
    return "";
  }
}

function requestTickerCount(init) {
  try {
    const payload = JSON.parse(String(init?.body || "{}"));
    return Array.isArray(payload.tickers) ? payload.tickers.length : null;
  } catch {
    return null;
  }
}

function parseServerTiming(value) {
  const timings = {};
  String(value || "").split(",").forEach((entry) => {
    const [name, ...parameters] = entry.trim().split(";");
    const duration = parameters.find((parameter) => parameter.trim().startsWith("dur="));
    const numeric = Number(duration?.split("=")[1]);
    if (name && Number.isFinite(numeric)) timings[name] = numeric;
  });
  return timings;
}

function formatSeconds(milliseconds) {
  return Number.isFinite(milliseconds) ? `${(milliseconds / 1000).toFixed(1)} 秒` : "—";
}

function scheduleTiming() {
  if (timingScheduled) return;
  timingScheduled = true;
  requestAnimationFrame(() => {
    timingScheduled = false;
    const summary = document.querySelector("#scan-summary");
    if (!summary) return;
    let panel = document.querySelector("#scan-batch-timing");
    if (!panel) {
      panel = document.createElement("div");
      panel.id = "scan-batch-timing";
      panel.className = "result-context scan-batch-timing";
      summary.insertAdjacentElement("afterend", panel);
    }
    const latest = timingHistory.at(-1);
    const successful = timingHistory.filter((item) => item.status === 200);
    const averageMs = successful.length
      ? successful.reduce((sum, item) => sum + item.elapsedMs, 0) / successful.length
      : null;
    if (!latest) {
      panel.textContent = "批次效能：尚無批次耗時資料。";
      return;
    }
    const parts = [
      `本批 ${latest.count ?? "—"} 檔`,
      `前端等待 ${formatSeconds(latest.elapsedMs)}`,
    ];
    if (Number.isFinite(latest.phases.market)) {
      parts.push(`行情下載與修復 ${formatSeconds(latest.phases.market)}`);
    }
    if (Number.isFinite(latest.phases.compute)) {
      parts.push(`指標與稽核計算 ${formatSeconds(latest.phases.compute)}`);
    }
    parts.push(Number.isFinite(averageMs)
      ? `平均成功批次 ${formatSeconds(averageMs)}`
      : "尚無成功批次平均值");
    panel.textContent = `批次效能：${parts.join(" · ")}`;
  });
}

window.fetch = async function fetchWithScanTiming(input, init) {
  const isScan = requestPath(input) === "/api/scan";
  const startedAt = isScan ? performance.now() : null;
  const count = isScan ? requestTickerCount(init) : null;
  try {
    const response = await baseFetch(input, init);
    if (isScan) {
      timingHistory.push({
        count,
        elapsedMs: performance.now() - startedAt,
        status: response.status,
        phases: parseServerTiming(
          response.headers.get("server-timing")
          || response.headers.get("x-backend-server-timing")
          || "",
        ),
      });
      if (timingHistory.length > 30) timingHistory.shift();
      scheduleTiming();
    }
    return response;
  } catch (error) {
    if (isScan) {
      timingHistory.push({ count, elapsedMs: performance.now() - startedAt, status: 0, phases: {} });
      scheduleTiming();
    }
    throw error;
  }
};

function formulaValue(matrixResult, item, key) {
  const formula = SCORE_FORMULAS.find((entry) => (
    entry.key === key || entry.rankKey === key || entry.statusKey === key
  ));
  if (!formula) return undefined;
  const record = scoreRecordFor(matrixResult, item?.ticker, formula.key);
  if (key === formula.key) return record?.score == null ? "" : Number(record.score).toFixed(6);
  if (key === formula.rankKey) return record?.rank ?? "";
  return record?.status || "missing";
}

function exportValue(matrixResult, item, key) {
  if (SCORE_RANK_HEADERS.includes(key) || SCORE_AUDIT_HEADERS.includes(key)) {
    return formulaValue(matrixResult, item, key);
  }
  if (key === "note") return humanNote(item);
  if (["auto_adjust", "repair", "interval", "actions", "keepna"].includes(key)) {
    return item?.data_source_settings?.[key];
  }
  if (key === "benchmark_corporate_action_status") {
    return item?.benchmark_corporate_action_audit?.status;
  }
  if (["standard_action_coverage", "nonstandard_action_limitations"].includes(key)) {
    const values = item?.[key];
    return Array.isArray(values) ? values.join(" | ") : values;
  }
  const value = item?.[key];
  if (value && typeof value === "object") return JSON.stringify(value);
  return value;
}

function escapeCsv(value) {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

function downloadCsv(filename, headers) {
  const rows = rowsWithDerivedCoverage();
  if (!rows.length) return;
  const matrixResult = buildScoreMatrix(rows.filter((item) => !item?.error));
  const lines = [
    headers.join(","),
    ...rows.map((item) => headers.map((key) => (
      escapeCsv(exportValue(matrixResult, item, key))
    )).join(",")),
  ];
  const blob = new Blob([`\ufeff${lines.join("\n")}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function handleConciseExport(event) {
  event.preventDefault();
  event.stopImmediatePropagation();
  downloadCsv("scan-results.csv", CONCISE_HEADERS);
}

function handleAuditExport(event) {
  event.preventDefault();
  event.stopImmediatePropagation();
  downloadCsv("scan-results-audit.csv", AUDIT_HEADERS);
}

function initialize() {
  document.querySelector("#export-scan")?.addEventListener("click", handleConciseExport, true);
  document.querySelector("#export-scan-audit")?.addEventListener("click", handleAuditExport, true);
  scheduleTiming();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialize, { once: true });
} else {
  initialize();
}
