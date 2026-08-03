import "./portfolio-lab-capture-bridge.js?v=20260803.1";
import {
  SCORE_FORMULAS,
  buildScoreMatrix,
  scoreRecordFor,
} from "./scan-score-core.js?v=20260803.1";

export const DEFAULT_SCAN_MIN_COVERAGE_PERCENT = 90;
export const SCAN_COVERAGE_DEFINITION_VERSION = "relative-max-trading-days-v1";

const EPSILON = 1e-12;

export function normalizeScanMinCoveragePercent(
  value,
  fallback = DEFAULT_SCAN_MIN_COVERAGE_PERCENT,
) {
  const raw = String(value ?? "").trim();
  if (!raw) return fallback;
  const numeric = Number(raw);
  if (!Number.isFinite(numeric)) return fallback;
  return Math.round(Math.min(100, Math.max(0, numeric)) * 10) / 10;
}

export function isSettledScanResult(item) {
  return Boolean(item) && !item.error && item.retryable !== true;
}

function validTradingDays(item) {
  if (!isSettledScanResult(item)) return null;
  const numeric = Number(item?.trading_days);
  return Number.isSafeInteger(numeric) && numeric > 0 ? numeric : null;
}

export function relativeScanCoverage(item, maximumTradingDays) {
  const tradingDays = validTradingDays(item);
  const denominator = Number(maximumTradingDays);
  if (
    tradingDays == null
    || !Number.isSafeInteger(denominator)
    || denominator <= 0
  ) {
    return null;
  }
  return Math.min(tradingDays / denominator, 1);
}

export function deriveScanCoverage(items) {
  const settledSource = (Array.isArray(items) ? items : []).filter(isSettledScanResult);
  const maximumTradingDays = settledSource.reduce((maximum, item) => (
    Math.max(maximum, validTradingDays(item) || 0)
  ), 0);

  const prepared = settledSource.map((item) => ({
    ...item,
    benchmark_calendar_coverage: item?.benchmark_calendar_coverage ?? item?.data_coverage ?? null,
    data_coverage: relativeScanCoverage(item, maximumTradingDays),
    coverage_reference_trading_days: maximumTradingDays || null,
    coverage_definition_version: SCAN_COVERAGE_DEFINITION_VERSION,
  }));

  const scoreMatrix = buildScoreMatrix(prepared);
  const settled = prepared.map((item) => {
    const scored = { ...item };
    for (const formula of SCORE_FORMULAS) {
      const record = scoreRecordFor(scoreMatrix, item.ticker, formula.key);
      scored[formula.key] = Number.isFinite(record?.score) ? record.score : null;
      scored[formula.rankKey] = Number.isInteger(record?.rank) ? record.rank : null;
      scored[formula.statusKey] = record?.status || "missing";
    }
    return scored;
  });

  return {
    settled,
    maximumTradingDays,
    coverageDefinitionVersion: SCAN_COVERAGE_DEFINITION_VERSION,
  };
}

export function hasMinimumScanCoverage(item, minimumCoveragePercent) {
  if (!isSettledScanResult(item)) return false;
  const rawCoverage = item.data_coverage;
  if (
    rawCoverage == null
    || typeof rawCoverage === "boolean"
    || String(rawCoverage).trim() === ""
  ) {
    return false;
  }
  const coverage = Number(rawCoverage);
  const threshold = normalizeScanMinCoveragePercent(minimumCoveragePercent) / 100;
  return Number.isFinite(coverage)
    && coverage >= 0
    && coverage <= 1 + EPSILON
    && coverage + EPSILON >= threshold;
}

export function buildScanCoverageStats(items, minimumCoveragePercent) {
  const derived = deriveScanCoverage(items);
  const shown = derived.settled.filter((item) => (
    hasMinimumScanCoverage(item, minimumCoveragePercent)
  ));
  return {
    ...derived,
    shown,
    hidden: derived.settled.length - shown.length,
  };
}
