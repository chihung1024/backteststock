import "./portfolio-route-bridge.js?v=20260814.1";

export const METRIC_DEFINITION_VERSION = "2026-08-01.2";

const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v3";
const CACHE_INVALIDATION_SESSION_KEY = "backteststock-metric-cache-invalidated";

function migrateStaleSavedScanJob() {
  if (typeof window === "undefined") return false;

  try {
    const job = JSON.parse(window.localStorage.getItem(SCAN_JOB_STORAGE_KEY));
    const results = Array.isArray(job?.results) ? job.results : [];
    const stale = results.some((item) => (
      item?.metric_definition_version !== METRIC_DEFINITION_VERSION
    ));
    if (!stale) return false;

    if (!Array.isArray(job?.payload?.tickers) || !job.payload.tickers.length) {
      window.localStorage.removeItem(SCAN_JOB_STORAGE_KEY);
      return false;
    }

    const reusableResults = results.filter((item) => (
      item?.ticker
      && item?.metric_definition_version === METRIC_DEFINITION_VERSION
    ));
    const settledTickers = new Set(reusableResults.map((item) => item.ticker));
    job.results = reusableResults;
    job.pending = job.payload.tickers.filter((ticker) => !settledTickers.has(ticker));
    job.status = job.pending.length ? "running" : "completed";
    job.attempts = {};
    job.retryRound = 0;
    job.metricDefinitionVersion = METRIC_DEFINITION_VERSION;
    job.recalculationReason = "metric_definition_changed";
    job.updatedAt = new Date().toISOString();

    window.localStorage.setItem(SCAN_JOB_STORAGE_KEY, JSON.stringify(job));
    window.sessionStorage.setItem(
      CACHE_INVALIDATION_SESSION_KEY,
      METRIC_DEFINITION_VERSION,
    );
    window.location.reload();
    return true;
  } catch (error) {
    console.warn("Unable to migrate saved scan metric version", error);
    window.localStorage.removeItem(SCAN_JOB_STORAGE_KEY);
    return false;
  }
}

export const METRIC_CACHE_MIGRATION_RELOAD_PENDING = migrateStaleSavedScanJob();

export * from "./scan-score-core.js?v=20260803.1";
