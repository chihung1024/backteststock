export const DEFAULT_SCAN_MIN_COVERAGE_PERCENT = 90;

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
    && coverage <= 1 + 1e-12
    && coverage + 1e-12 >= threshold;
}

export function buildScanCoverageStats(items, minimumCoveragePercent) {
  const settled = (Array.isArray(items) ? items : []).filter(isSettledScanResult);
  const shown = settled.filter((item) => (
    hasMinimumScanCoverage(item, minimumCoveragePercent)
  ));
  return {
    settled,
    shown,
    hidden: settled.length - shown.length,
  };
}
