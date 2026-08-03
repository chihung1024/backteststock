import assert from "node:assert/strict";
import test from "node:test";
import {
  binomialBigInt,
  buildPeriodKeys,
  nextCombination,
  relativeBandBounds,
  scoreMetrics,
  simulateExactPortfolio,
  unrankCombination,
} from "../public/exhaustive-optimizer-core.js";

test("binomial and lexicographic unranking cover N choose K", () => {
  assert.equal(binomialBigInt(20, 10), 184756n);
  assert.equal(binomialBigInt(25, 7), 480700n);
  const expected = [
    [0, 1, 2],
    [0, 1, 3],
    [0, 1, 4],
    [0, 2, 3],
    [0, 2, 4],
    [0, 3, 4],
    [1, 2, 3],
    [1, 2, 4],
    [1, 3, 4],
    [2, 3, 4],
  ];
  for (let rank = 0; rank < expected.length; rank += 1) {
    assert.deepEqual([...unrankCombination(5, 3, rank)], expected[rank]);
  }
  const cursor = unrankCombination(5, 3, 0);
  const actual = [[...cursor]];
  while (nextCombination(cursor, 5)) actual.push([...cursor]);
  assert.deepEqual(actual, expected);
});

test("relative band scales with dynamic holding count", () => {
  const seven = relativeBandBounds(7, 0.20);
  assert.equal(seven.target, 1 / 7);
  assert.ok(Math.abs(seven.lower - 0.1142857142857143) < 1e-12);
  assert.ok(Math.abs(seven.upper - 0.17142857142857143) < 1e-12);
});

test("score formulas preserve the four requested definitions", () => {
  const metrics = { sortino_ratio: 2, cagr: 0.25, beta: 0.5, mdd: -0.2 };
  const scores = scoreMetrics(metrics);
  assert.ok(Math.abs(scores.stable_score - 2 * Math.sqrt(1.25 / 1.5)) < 1e-12);
  assert.ok(Math.abs(scores.growth_score - 2 * Math.sqrt(1.25) / (1.5 ** 0.25)) < 1e-12);
  assert.ok(Math.abs(scores.drawdown_score - 2 * Math.sqrt(1.25 / (1.5 * 1.2))) < 1e-12);
  assert.ok(Math.abs(scores.optimized_score - 2 * Math.sqrt(1.25 / ((1.5 ** 2) * 1.2))) < 1e-12);
});

test("dynamic-K exact band simulation executes on the next trading day", () => {
  const dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"];
  const prices = Array.from({ length: 7 }, () => Float64Array.from([100, 100, 100, 100]));
  prices[0] = Float64Array.from([100, 200, 160, 180]);
  const benchmark = Float64Array.from([100, 101, 99, 102]);
  const result = simulateExactPortfolio({
    prices,
    benchmarkPrices: benchmark,
    periodKeys: buildPeriodKeys(dates),
    indexes: Uint16Array.from([0, 1, 2, 3, 4, 5, 6]),
    elapsedYears: 3 / 365.25,
    rebalanceMode: "band",
    bandRatio: 0.20,
    transactionCostBps: 0,
    executionDelayTradingDays: 1,
    collectEvents: true,
  });
  assert.equal(result.rebalance_count, 1);
  assert.equal(result.events[0].signalPosition, 1);
  assert.equal(result.events[0].executionPosition, 2);
  assert.deepEqual(result.events[0].triggerIndexes, [0]);
  for (const key of [
    "total_return",
    "cagr",
    "mdd",
    "volatility",
    "annualized_turnover_one_way",
    "rebalance_count",
    "transaction_cost",
  ]) assert.ok(Number.isFinite(result[key]), key);
});

test("Sortino and alpha use the signed snapshot risk-free rate", () => {
  const portfolio = [100, 98, 101, 99];
  const benchmark = [100, 101, 99, 102];
  const riskFreeRate = 0.10;
  const result = simulateExactPortfolio({
    prices: [Float64Array.from(portfolio)],
    benchmarkPrices: Float64Array.from(benchmark),
    periodKeys: buildPeriodKeys(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]),
    indexes: Uint16Array.from([0]),
    elapsedYears: 3 / 365.25,
    rebalanceMode: "never",
    riskFreeRate,
  });
  const returns = portfolio.slice(1).map((value, index) => value / portfolio[index] - 1);
  const benchmarkReturns = benchmark.slice(1).map(
    (value, index) => value / benchmark[index] - 1,
  );
  const dailyRiskFree = (1 + riskFreeRate) ** (1 / 252) - 1;
  const mean = returns.reduce((sum, value) => sum + value, 0) / returns.length;
  const benchmarkMean = benchmarkReturns.reduce((sum, value) => sum + value, 0)
    / benchmarkReturns.length;
  const downside = returns.map((value) => Math.min(value - dailyRiskFree, 0));
  const downsideDeviation = Math.sqrt(
    downside.reduce((sum, value) => sum + (value ** 2), 0) / returns.length * 252,
  );
  const benchmarkVariance = benchmarkReturns.reduce(
    (sum, value) => sum + ((value - benchmarkMean) ** 2),
    0,
  ) / (benchmarkReturns.length - 1);
  const covariance = returns.reduce(
    (sum, value, index) => sum
      + ((value - mean) * (benchmarkReturns[index] - benchmarkMean)),
    0,
  ) / (returns.length - 1);
  const expectedBeta = covariance / benchmarkVariance;
  const expectedAlpha = (
    mean - (dailyRiskFree + expectedBeta * (benchmarkMean - dailyRiskFree))
  ) * 252;

  assert.ok(Math.abs(
    result.sortino_ratio - ((mean - dailyRiskFree) * 252 / downsideDeviation)
  ) < 1e-12);
  assert.ok(Math.abs(result.beta - expectedBeta) < 1e-12);
  assert.ok(Math.abs(result.alpha - expectedAlpha) < 1e-12);
});

test("an undefined downside deviation remains unavailable instead of scoring as zero", () => {
  const result = simulateExactPortfolio({
    prices: [Float64Array.from([100, 101, 102])],
    benchmarkPrices: Float64Array.from([100, 101, 100]),
    periodKeys: buildPeriodKeys(["2024-01-02", "2024-01-03", "2024-01-04"]),
    indexes: Uint16Array.from([0]),
    elapsedYears: 2 / 365.25,
    rebalanceMode: "never",
  });

  assert.ok(Number.isNaN(result.sortino_ratio));
  assert.ok(Number.isNaN(result.optimized_score));
});

test("periodic mode rebalances at calendar boundaries", () => {
  const dates = ["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02"];
  const prices = [
    Float64Array.from([100, 110, 120, 130]),
    Float64Array.from([100, 100, 100, 100]),
  ];
  const result = simulateExactPortfolio({
    prices,
    benchmarkPrices: Float64Array.from([100, 100, 100, 100]),
    periodKeys: buildPeriodKeys(dates),
    indexes: Uint16Array.from([0, 1]),
    elapsedYears: 3 / 365.25,
    rebalanceMode: "monthly",
    bandRatio: 0.20,
    transactionCostBps: 0,
    executionDelayTradingDays: 1,
    collectEvents: true,
  });
  assert.equal(result.rebalance_count, 1);
  assert.equal(result.events[0].signalPosition, 2);
  assert.equal(result.events[0].executionPosition, 3);
  assert.equal(result.events[0].reason, "monthly");
});
