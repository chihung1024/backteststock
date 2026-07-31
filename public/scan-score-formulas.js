export const SCORE_FORMULAS = Object.freeze([
  Object.freeze({
    key: "sortino_alpha_mdd_score",
    rankKey: "sortino_alpha_mdd_rank",
    statusKey: "sortino_alpha_mdd_score_status",
    label: "原始分數",
    shortLabel: "原始",
    description: "Sortino × Alpha ÷ |最大回撤|",
    digits: 4,
  }),
  Object.freeze({
    key: "alpha_sqrt_sortino_mdd_score",
    rankKey: "alpha_sqrt_sortino_mdd_rank",
    statusKey: "alpha_sqrt_sortino_mdd_score_status",
    label: "建議分數",
    shortLabel: "建議",
    description: "Alpha × √(Sortino ÷ |最大回撤|)",
    digits: 4,
  }),
  Object.freeze({
    key: "percentile_composite_score",
    rankKey: "percentile_composite_rank",
    statusKey: "percentile_composite_score_status",
    label: "百分位分數",
    shortLabel: "百分位",
    description: "50% Alpha 百分位 + 30% Sortino 百分位 + 20% 低回撤百分位",
    digits: 2,
  }),
]);

const REQUIRED_METRICS = Object.freeze(["sortino_ratio", "alpha", "mdd"]);
const SCORE_EPSILON = 1e-12;

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

  const values = Object.fromEntries(REQUIRED_METRICS.map((key) => [key, rawMetric(item, key)]));
  const missing = REQUIRED_METRICS.filter((key) => values[key] == null);
  if (missing.length) {
    return unavailable(
      "missing_metrics",
      `缺少必要指標：${missing.join(", ")}`,
      values,
    );
  }

  const absoluteMdd = Math.abs(values.mdd);
  if (absoluteMdd <= SCORE_EPSILON) {
    return unavailable(
      "zero_mdd",
      "最大回撤為 0，無法作為除數。",
      { ...values, absoluteMdd },
    );
  }

  return {
    score: null,
    rank: null,
    status: "metrics_ready",
    reason: "",
    ...values,
    absoluteMdd,
  };
}

function calculateOriginalRecord(metrics) {
  if (metrics.status !== "metrics_ready") return { ...metrics };
  const score = metrics.sortino_ratio * metrics.alpha / metrics.absoluteMdd;
  if (!Number.isFinite(score)) {
    return unavailable("invalid_result", "原始公式計算結果不是有限數值。", metrics);
  }
  return { ...metrics, score, status: "ok" };
}

function calculateRecommendedRecord(metrics) {
  if (metrics.status !== "metrics_ready") return { ...metrics };
  if (metrics.sortino_ratio <= 0) {
    return unavailable(
      "non_positive_sortino",
      "Sortino 必須大於 0 才能套用平方根公式。",
      metrics,
    );
  }
  const score = metrics.alpha * Math.sqrt(metrics.sortino_ratio / metrics.absoluteMdd);
  if (!Number.isFinite(score)) {
    return unavailable("invalid_result", "建議公式計算結果不是有限數值。", metrics);
  }
  return { ...metrics, score, status: "ok" };
}

function sameNumber(left, right) {
  return Math.abs(left - right) <= SCORE_EPSILON * Math.max(1, Math.abs(left), Math.abs(right));
}

function percentileByTicker(entries) {
  const sorted = [...entries].sort((left, right) => (
    left.value - right.value || left.ticker.localeCompare(right.ticker)
  ));
  const result = new Map();
  const denominator = sorted.length - 1;

  for (let start = 0; start < sorted.length;) {
    let end = start;
    while (end + 1 < sorted.length && sameNumber(sorted[end + 1].value, sorted[start].value)) {
      end += 1;
    }
    const averageIndex = (start + end) / 2;
    const percentile = denominator > 0 ? 100 * averageIndex / denominator : 100;
    for (let index = start; index <= end; index += 1) {
      result.set(sorted[index].ticker, percentile);
    }
    start = end + 1;
  }
  return result;
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
  const percentileEligible = [];
  for (const [ticker, item] of uniqueItems) {
    const metrics = prepareMetrics(item);
    matrix.set(ticker, {
      ticker,
      formulas: {
        sortino_alpha_mdd_score: calculateOriginalRecord(metrics),
        alpha_sqrt_sortino_mdd_score: calculateRecommendedRecord(metrics),
        percentile_composite_score: unavailable(
          metrics.status,
          metrics.reason,
          metrics,
        ),
      },
    });
    if (metrics.status === "metrics_ready") {
      percentileEligible.push({ ticker, metrics });
    }
  }

  const alphaPercentiles = percentileByTicker(
    percentileEligible.map(({ ticker, metrics }) => ({ ticker, value: metrics.alpha })),
  );
  const sortinoPercentiles = percentileByTicker(
    percentileEligible.map(({ ticker, metrics }) => ({ ticker, value: metrics.sortino_ratio })),
  );
  const drawdownPercentiles = percentileByTicker(
    percentileEligible.map(({ ticker, metrics }) => ({ ticker, value: -metrics.absoluteMdd })),
  );

  for (const { ticker, metrics } of percentileEligible) {
    const alphaPercentile = alphaPercentiles.get(ticker);
    const sortinoPercentile = sortinoPercentiles.get(ticker);
    const drawdownPercentile = drawdownPercentiles.get(ticker);
    const score = (
      0.50 * alphaPercentile
      + 0.30 * sortinoPercentile
      + 0.20 * drawdownPercentile
    );
    matrix.get(ticker).formulas.percentile_composite_score = {
      ...metrics,
      score,
      rank: null,
      status: "ok",
      alphaPercentile,
      sortinoPercentile,
      drawdownPercentile,
    };
  }

  const validCounts = Object.fromEntries(
    SCORE_FORMULAS.map((formula) => [formula.key, assignRanks(matrix, formula.key)]),
  );

  const recommendedKey = "alpha_sqrt_sortino_mdd_score";
  for (const row of matrix.values()) {
    const recommendedRank = row.formulas[recommendedKey]?.rank;
    for (const formula of SCORE_FORMULAS) {
      const record = row.formulas[formula.key];
      record.rankDeltaVsRecommended = (
        Number.isInteger(record.rank) && Number.isInteger(recommendedRank)
          ? record.rank - recommendedRank
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
