export const EXHAUSTIVE_ENGINE_VERSION = "exhaustive-band-v2-2026-08-02.1";
export const MAX_EXHAUSTIVE_COMBINATIONS = 5_000_000;
export const METRIC_KEYS = Object.freeze([
  "total_return",
  "cagr",
  "mdd",
  "volatility",
  "sortino_ratio",
  "beta",
  "alpha",
  "annualized_turnover_one_way",
  "rebalance_count",
  "transaction_cost",
  "stable_score",
  "growth_score",
  "drawdown_score",
  "optimized_score",
]);

const EPSILON = 1e-12;
const TRADING_DAYS_PER_YEAR = 252;

export function binomialBigInt(n, k) {
  const nn = Number(n);
  const kk = Number(k);
  if (!Number.isInteger(nn) || !Number.isInteger(kk) || nn < 0 || kk < 0 || kk > nn) {
    return 0n;
  }
  const reduced = Math.min(kk, nn - kk);
  let result = 1n;
  for (let index = 1; index <= reduced; index += 1) {
    result = result * BigInt(nn - reduced + index) / BigInt(index);
  }
  return result;
}

export function combinationCountNumber(n, k) {
  const count = binomialBigInt(n, k);
  if (count > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new RangeError("組合數超過 JavaScript 安全整數範圍。");
  }
  return Number(count);
}

export function unrankCombination(n, k, rankValue) {
  let rank = typeof rankValue === "bigint" ? rankValue : BigInt(rankValue);
  const total = binomialBigInt(n, k);
  if (rank < 0n || rank >= total) throw new RangeError("組合排名超出範圍。");
  const output = new Uint16Array(k);
  let minimum = 0;
  for (let position = 0; position < k; position += 1) {
    const remaining = k - position - 1;
    const maximum = n - (k - position);
    for (let candidate = minimum; candidate <= maximum; candidate += 1) {
      const block = binomialBigInt(n - candidate - 1, remaining);
      if (rank < block) {
        output[position] = candidate;
        minimum = candidate + 1;
        break;
      }
      rank -= block;
    }
  }
  return output;
}

export function nextCombination(combination, n) {
  const k = combination.length;
  for (let position = k - 1; position >= 0; position -= 1) {
    const maximum = n - k + position;
    if (combination[position] >= maximum) continue;
    combination[position] += 1;
    for (let cursor = position + 1; cursor < k; cursor += 1) {
      combination[cursor] = combination[cursor - 1] + 1;
    }
    return true;
  }
  return false;
}

export function relativeBandBounds(holdingCount, bandRatio) {
  const target = 1 / Number(holdingCount);
  const ratio = Number(bandRatio);
  return {
    target,
    lower: target * (1 - ratio),
    upper: target * (1 + ratio),
  };
}

export function scoreMetrics({ sortino_ratio: sortino, cagr, beta, mdd }) {
  const onePlusCagr = 1 + Number(cagr);
  const onePlusBeta = 1 + Number(beta);
  const absoluteMdd = Math.abs(Number(mdd));
  if (
    ![sortino, cagr, beta, mdd].every(Number.isFinite)
    || onePlusCagr < 0
    || onePlusBeta <= EPSILON
  ) {
    return {
      stable_score: Number.NaN,
      growth_score: Number.NaN,
      drawdown_score: Number.NaN,
      optimized_score: Number.NaN,
    };
  }
  return {
    stable_score: sortino * Math.sqrt(onePlusCagr / onePlusBeta),
    growth_score: sortino * Math.sqrt(onePlusCagr) / Math.pow(onePlusBeta, 0.25),
    drawdown_score: sortino * Math.sqrt(
      onePlusCagr / (onePlusBeta * (1 + absoluteMdd)),
    ),
    optimized_score: sortino * Math.sqrt(
      onePlusCagr / (onePlusBeta ** 2 * (1 + absoluteMdd)),
    ),
  };
}

export function estimateResultBytes(combinations, holdingCount) {
  const count = Number(combinations);
  const packedCombinationBytes = count * holdingCount * 2;
  const metricBytes = count * METRIC_KEYS.length * 8;
  const indexBytes = count * 8;
  const indexedDbOverhead = count * 12;
  return packedCombinationBytes + metricBytes + indexBytes + indexedDbOverhead;
}

export function estimateSnapshotBytes(assetCount, observations) {
  return (assetCount + 1) * observations * 8;
}

export function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "無法估算";
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))} 秒`;
  if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const remainder = Math.round(seconds % 60);
    return remainder ? `${minutes} 分 ${remainder} 秒` : `${minutes} 分`;
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return minutes ? `${hours} 小時 ${minutes} 分` : `${hours} 小時`;
}

export function formatBytes(bytes) {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value < 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount.toFixed(index < 2 ? 0 : 1)} ${units[index]}`;
}

function periodicBoundary(mode, periodKeys, index) {
  if (index <= 0 || mode === "never" || mode === "band") return false;
  if (mode === "monthly") return periodKeys.month[index] !== periodKeys.month[index - 1];
  if (mode === "quarterly") return periodKeys.quarter[index] !== periodKeys.quarter[index - 1];
  if (mode === "annually") return periodKeys.year[index] !== periodKeys.year[index - 1];
  return false;
}

function solvePostCostTargetNav(preValues, cash, targetWeight, costRate) {
  let preNav = cash;
  for (let index = 0; index < preValues.length; index += 1) preNav += preValues[index];
  if (!(preNav > 0)) throw new Error("投組淨值小於或等於 0。");
  let targetNav = preNav;
  let gross = 0;
  for (let iteration = 0; iteration < 40; iteration += 1) {
    gross = 0;
    const targetValue = targetNav * targetWeight;
    for (let index = 0; index < preValues.length; index += 1) {
      gross += Math.abs(targetValue - preValues[index]);
    }
    const updated = preNav - gross * costRate;
    if (!(updated > 0)) throw new Error("交易成本使投組淨值歸零。");
    if (Math.abs(updated - targetNav) <= 1e-12 * Math.max(1, preNav)) {
      targetNav = updated;
      break;
    }
    targetNav = updated;
  }
  const targetValue = targetNav * targetWeight;
  gross = 0;
  for (let index = 0; index < preValues.length; index += 1) {
    gross += Math.abs(targetValue - preValues[index]);
  }
  return { preNav, targetNav, gross, cost: gross * costRate };
}

export function buildPeriodKeys(dates) {
  const month = new Int32Array(dates.length);
  const quarter = new Int32Array(dates.length);
  const year = new Int32Array(dates.length);
  for (let index = 0; index < dates.length; index += 1) {
    const [yyyy, mm] = String(dates[index]).split("-").map(Number);
    year[index] = yyyy;
    month[index] = yyyy * 12 + mm;
    quarter[index] = yyyy * 4 + Math.floor((mm - 1) / 3);
  }
  return { month, quarter, year };
}

export function simulateExactPortfolio({
  prices,
  benchmarkPrices,
  periodKeys,
  indexes,
  elapsedYears,
  rebalanceMode = "band",
  bandRatio = 0.20,
  transactionCostBps = 0,
  executionDelayTradingDays = 1,
  collectEvents = false,
}) {
  const k = indexes.length;
  const observations = benchmarkPrices.length;
  if (!k || observations < 2) throw new Error("回測資料不足。");
  const targetWeight = 1 / k;
  const { lower, upper } = relativeBandBounds(k, bandRatio);
  const costRate = Number(transactionCostBps) / 10_000;
  const delay = Math.max(0, Math.floor(Number(executionDelayTradingDays) || 0));
  const shares = new Float64Array(k);
  const preValues = new Float64Array(k);
  const triggerIndexes = [];
  const events = [];
  let cash = 1;
  let pending = null;
  let totalRebalanceGross = 0;
  let totalCost = 0;
  let rebalanceCount = 0;
  let navSum = 0;

  const initial = solvePostCostTargetNav(preValues, cash, targetWeight, costRate);
  for (let item = 0; item < k; item += 1) {
    shares[item] = (initial.targetNav * targetWeight) / prices[indexes[item]][0];
  }
  cash = initial.targetNav;
  for (let item = 0; item < k; item += 1) {
    cash -= shares[item] * prices[indexes[item]][0];
  }
  totalCost += initial.cost;
  let previousNav = initial.targetNav;
  let peak = 1;
  let mdd = Math.min(0, initial.targetNav - 1);
  let sum = 0;
  let sumSquares = 0;
  let downsideSquares = 0;
  let benchmarkSum = 0;
  let benchmarkSquares = 0;
  let crossSum = 0;
  navSum += previousNav;

  const executeRebalance = (position, signalPosition, reason, triggers) => {
    for (let item = 0; item < k; item += 1) {
      preValues[item] = shares[item] * prices[indexes[item]][position];
    }
    const solved = solvePostCostTargetNav(preValues, cash, targetWeight, costRate);
    const targetValue = solved.targetNav * targetWeight;
    for (let item = 0; item < k; item += 1) {
      shares[item] = targetValue / prices[indexes[item]][position];
    }
    cash = solved.targetNav;
    for (let item = 0; item < k; item += 1) {
      cash -= shares[item] * prices[indexes[item]][position];
    }
    totalRebalanceGross += solved.gross;
    totalCost += solved.cost;
    rebalanceCount += 1;
    if (collectEvents) {
      events.push({
        signalPosition,
        executionPosition: position,
        reason,
        triggerIndexes: [...triggers],
        grossTradedNotional: solved.gross,
        transactionCost: solved.cost,
        preTradeNav: solved.preNav,
        postTradeNav: solved.targetNav,
      });
    }
    return solved.targetNav;
  };

  for (let position = 1; position < observations; position += 1) {
    let nav = cash;
    for (let item = 0; item < k; item += 1) {
      preValues[item] = shares[item] * prices[indexes[item]][position];
      nav += preValues[item];
    }

    let executed = false;
    if (pending && position >= pending.executePosition) {
      nav = executeRebalance(
        position,
        pending.signalPosition,
        pending.reason,
        pending.triggerIndexes,
      );
      pending = null;
      executed = true;
    }

    if (!executed && !pending) {
      let signal = false;
      let reason = "";
      triggerIndexes.length = 0;
      if (rebalanceMode === "band") {
        for (let item = 0; item < k; item += 1) {
          const weight = preValues[item] / nav;
          if (weight < lower || weight > upper) {
            triggerIndexes.push(item);
            signal = true;
          }
        }
        reason = "relative_band";
      } else if (periodicBoundary(rebalanceMode, periodKeys, position)) {
        signal = true;
        reason = rebalanceMode;
      }

      if (signal) {
        if (delay === 0) {
          nav = executeRebalance(position, position, reason, triggerIndexes);
          executed = true;
        } else if (position + delay < observations) {
          pending = {
            signalPosition: position,
            executePosition: position + delay,
            reason,
            triggerIndexes: [...triggerIndexes],
          };
        }
      }
    }

    const portfolioReturn = nav / previousNav - 1;
    const benchmarkReturn = benchmarkPrices[position] / benchmarkPrices[position - 1] - 1;
    sum += portfolioReturn;
    sumSquares += portfolioReturn * portfolioReturn;
    downsideSquares += Math.min(portfolioReturn, 0) ** 2;
    benchmarkSum += benchmarkReturn;
    benchmarkSquares += benchmarkReturn * benchmarkReturn;
    crossSum += portfolioReturn * benchmarkReturn;
    previousNav = nav;
    peak = Math.max(peak, nav);
    mdd = Math.min(mdd, nav / peak - 1);
    navSum += nav;
  }

  const days = observations - 1;
  const dailyMean = sum / days;
  const variance = Math.max(
    (sumSquares - days * dailyMean * dailyMean) / Math.max(days - 1, 1),
    0,
  );
  const benchmarkMean = benchmarkSum / days;
  const benchmarkVariance = Math.max(
    (benchmarkSquares - days * benchmarkMean * benchmarkMean) / Math.max(days - 1, 1),
    0,
  );
  const covariance = (
    crossSum - days * dailyMean * benchmarkMean
  ) / Math.max(days - 1, 1);
  const beta = benchmarkVariance > EPSILON ? covariance / benchmarkVariance : 0;
  const annualReturn = dailyMean * TRADING_DAYS_PER_YEAR;
  const downsideDeviation = Math.sqrt((downsideSquares / days) * TRADING_DAYS_PER_YEAR);
  const years = Math.max(Number(elapsedYears) || days / TRADING_DAYS_PER_YEAR, 1 / 365.25);
  const totalReturn = previousNav - 1;
  const cagr = Math.pow(Math.max(previousNav, EPSILON), 1 / years) - 1;
  const averageNav = navSum / observations;
  const turnoverOneWay = averageNav > 0 ? totalRebalanceGross / (2 * averageNav) : 0;
  const base = {
    total_return: totalReturn,
    cagr,
    mdd,
    volatility: Math.sqrt(variance * TRADING_DAYS_PER_YEAR),
    sortino_ratio: downsideDeviation > EPSILON ? annualReturn / downsideDeviation : 0,
    beta,
    alpha: (dailyMean - beta * benchmarkMean) * TRADING_DAYS_PER_YEAR,
    annualized_turnover_one_way: turnoverOneWay / years,
    rebalance_count: rebalanceCount,
    transaction_cost: totalCost,
  };
  return {
    ...base,
    ...scoreMetrics(base),
    final_nav: previousNav,
    events,
    pending_signal: pending,
  };
}

export function metricsToArray(metrics) {
  const output = new Float64Array(METRIC_KEYS.length);
  METRIC_KEYS.forEach((key, index) => {
    output[index] = Number(metrics[key]);
  });
  return output;
}
