import assert from "node:assert/strict";
import test from "node:test";
import {
  METRIC_KEYS,
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
  prices[0] = Float64Array.from([100, 200, 200, 200]);
  const benchmark = Float64Array.from([100, 100, 100, 100]);
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
  for (const key of METRIC_KEYS) assert.ok(Number.isFinite(result[key]), key);
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
