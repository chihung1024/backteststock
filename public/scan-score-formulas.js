export const METRIC_DEFINITION_VERSION = "2026-07-31.1";

const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v2";
const CACHE_INVALIDATION_SESSION_KEY = "backteststock-metric-cache-invalidated";

function invalidateStaleSavedScanJob() {
  if (typeof window === "undefined") return;

  try {
    const job = JSON.parse(window.localStorage.getItem(SCAN_JOB_STORAGE_KEY));
    const completedResults = Array.isArray(job?.results)
      ? job.results.filter((item) => item?.status === "ok")
      : [];
    const stale = completedResults.some((item) => (
      item?.metric_definition_version !== METRIC_DEFINITION_VERSION
    ));
    if (!stale) return;

    window.localStorage.removeItem(SCAN_JOB_STORAGE_KEY);
    if (
      window.sessionStorage.getItem(CACHE_INVALIDATION_SESSION_KEY)
      !== METRIC_DEFINITION_VERSION
    ) {
      window.sessionStorage.setItem(
        CACHE_INVALIDATION_SESSION_KEY,
        METRIC_DEFINITION_VERSION,
      );
      window.location.reload();
    }
  } catch (error) {
    console.warn("Unable to validate saved scan metric version", error);
    window.localStorage.removeItem(SCAN_JOB_STORAGE_KEY);
  }
}

invalidateStaleSavedScanJob();

export const SCORE_FORMULAS = Object.freeze([
  Object.freeze({
    key: "sortino_growth_beta_score",
    rankKey: "sortino_growth_beta_rank",
    statusKey: "sortino_growth_beta_score_status",
    label: "穩健分數",
    shortLabel: "穩健",
    description: "Sortino × √((1 + CAGR) ÷ (1 + Beta))",
    digits: 4,
  }),
  Object.freeze({
    key: "sortino_growth_beta_quarter_score",
    rankKey: "sortino_growth_beta_quarter_rank",
    statusKey: "sortino_growth_beta_quarter_score_status",
    label: "成長分數",
    shortLabel: "成長",
    description: "Sortino × √(1 + CAGR) ÷ (1 + Beta)^0.25",
    digits: 4,
  }),
  Object.freeze({
    key: "sortino_growth_beta_mdd_score",
    rankKey: "sortino_growth_beta_mdd_rank",
    statusKey: "sortino_growth_beta_mdd_score_status",
    label: "回撤控制分數",
    shortLabel: "回撤",
    description: "Sortino × √((1 + CAGR) ÷ ((1 + Beta) × (1 + |MDD|)))",
    digits: 4,
  }),
]);

const SCORE_EPSILON = 1e-12;
const BASE_REQUIRED_METRICS = Object.freeze(["sortino_ratio", "cagr", "beta"]);

export function normalizeScoreTicker(value) {
  return String(value || "").trim().split(/\s+/u)[0].toUpperCase();
}

function rawMetric(item, key) {
  if (item?.[key] == null) return null;
  const numeric = Number(item[key]);
  return Number.isFinite(numeric) ? numeric : null;
}

function unavailable(status, reason, values = {}) {
  return {
    ...values,
    score: null,
    rank: null,
    status,
    reason,
  };
}

function prepareMetrics(item) {
  if (item?.error) {
    return unavailable("error", String(item.error));
  }

  return {
    score: null,
    rank: null,
    status: "metrics_ready",
    reason: "",
    sortino_ratio: rawMetric(item, "sortino_ratio"),
    cagr: rawMetric(item, "cagr"),
    beta: rawMetric(item, "beta"),
    mdd: rawMetric(item, "mdd"),
  };
}

function requireMetrics(metrics, required) {
  if (metrics.status !== "metrics_ready") return { ...metrics };
  const missing = required.filter((key) => metrics[key] == null);
  if (missing.length) {
    return unavailable(
      "missing_metrics",
      `缺少必要指標：${missing.join(", ")}`,
      metrics,
    );
  }
  return { ...metrics };
}

function prepareGrowthBetaTerms(metrics, { requireMdd = false } = {}) {
  const ready = requireMetrics(
    metrics,
    requireMdd ? [...BASE_REQUIRED_METRICS, "mdd"] : BASE_REQUIRED_METRICS,
  );
  if (ready.status !== "metrics_ready") return ready;

  const onePlusCagr = 1 + ready.cagr;
  if (onePlusCagr < 0) {
    return unavailable(
      "invalid_cagr_domain",
      "CAGR 小於 -100%，無法套用平方根公式。",
      { ...ready, onePlusCagr },
    );
  }

  const onePlusBeta = 1 + ready.beta;
  if (onePlusBeta <= SCORE_EPSILON) {
    return unavailable(
      "invalid_beta_domain",
      "Beta 必須大於 -1，才能作為公式分母。",
      { ...ready, onePlusCagr, onePlusBeta },
    );
  }

  return {
    ...ready,
    onePlusCagr,
    onePlusBeta,
    absoluteMdd: ready.mdd == null ? null : Math.abs(ready.mdd),
  };
}

function finiteResult(metrics, score, formulaName) {
  if (!Number.isFinite(score)) {
    return unavailable(
      "invalid_result",
      `${formulaName}計算結果不是有限數值。`,
      metrics,
    );
  }
  return { ...metrics, score, status: "ok" };
}

function calculateStableRecord(metrics) {
  const ready = prepareGrowthBetaTerms(metrics);
  if (ready.status !== "metrics_ready") return ready;
  const score = ready.sortino_ratio * Math.sqrt(ready.onePlusCagr / ready.onePlusBeta);
  return finiteResult(ready, score, "穩健公式");
}

function calculateGrowthRecord(metrics) {
  const ready = prepareGrowthBetaTerms(metrics);
  if (ready.status !== "metrics_ready") return ready;
  const score = (
    ready.sortino_ratio
    * Math.sqrt(ready.onePlusCagr)
    / Math.pow(ready.onePlusBeta, 0.25)
  );
  return finiteResult(ready, score, "成長公式");
}

function calculateDrawdownRecord(metrics) {
  const ready = prepareGrowthBetaTerms(metrics, { requireMdd: true });
  if (ready.status !== "metrics_ready") return ready;
  const score = ready.sortino_ratio * Math.sqrt(
    ready.onePlusCagr / (ready.onePlusBeta * (1 + ready.absoluteMdd)),
  );
  return finiteResult(ready, score, "回撤控制公式");
}

function sameNumber(left, right) {
  return Math.abs(left - right) <= SCORE_EPSILON * Math.max(1, Math.abs(left), Math.abs(right));
}

function assignRanks(matrix, formulaKey) {
  const scored = [...matrix.values()]
    .map((row) => ({ ticker: row.ticker, record: row.formulas[formulaKey] }))
    .filter(({ record }) => Number.isFinite(record?.score))
    .sort((left, right) => (
      right.record.score - left.record.score || left.ticker.localeCompare(right.ticker)
    ));

  let previousScore = null;
  let currentRank = 0;
  scored.forEach(({ record }, index) => {
    if (previousScore == null || !sameNumber(record.score, previousScore)) {
      currentRank = index + 1;
      previousScore = record.score;
    }
    record.rank = currentRank;
  });
  return scored.length;
}

export function buildScoreMatrix(items) {
  const uniqueItems = new Map();
  for (const item of Array.isArray(items) ? items : []) {
    const ticker = normalizeScoreTicker(item?.ticker);
    if (ticker) uniqueItems.set(ticker, item);
  }

  const matrix = new Map();
  for (const [ticker, item] of uniqueItems) {
    const metrics = prepareMetrics(item);
    matrix.set(ticker, {
      ticker,
      formulas: {
        sortino_growth_beta_score: calculateStableRecord(metrics),
        sortino_growth_beta_quarter_score: calculateGrowthRecord(metrics),
        sortino_growth_beta_mdd_score: calculateDrawdownRecord(metrics),
      },
    });
  }

  const validCounts = Object.fromEntries(
    SCORE_FORMULAS.map((formula) => [formula.key, assignRanks(matrix, formula.key)]),
  );

  const stableKey = "sortino_growth_beta_score";
  for (const row of matrix.values()) {
    const stableRank = row.formulas[stableKey]?.rank;
    for (const formula of SCORE_FORMULAS) {
      const record = row.formulas[formula.key];
      record.rankDeltaVsStable = (
        Number.isInteger(record.rank) && Number.isInteger(stableRank)
          ? record.rank - stableRank
          : null
      );
    }
  }

  return { matrix, validCounts, total: matrix.size };
}

export function scoreRecordFor(matrixResult, ticker, formulaKey) {
  const normalized = normalizeScoreTicker(ticker);
  return matrixResult?.matrix?.get(normalized)?.formulas?.[formulaKey] || null;
}
