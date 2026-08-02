import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { performance } from "node:perf_hooks";
import {
  METRIC_KEYS,
  binomialBigInt,
  buildPeriodKeys,
  nextCombination,
  relativeBandBounds,
  simulateExactPortfolio,
  unrankCombination,
} from "../public/exhaustive-optimizer-core.js";

const snapshot = JSON.parse(readFileSync("diagnostics/snapshot.json", "utf8"));
const prices = snapshot.candidateTickers.map((ticker) => Float64Array.from(snapshot.prices[ticker]));
const benchmarkPrices = Float64Array.from(snapshot.prices[snapshot.benchmark]);
const periodKeys = buildPeriodKeys(snapshot.dates);
const first = Date.parse(`${snapshot.dates[0]}T00:00:00Z`);
const last = Date.parse(`${snapshot.dates.at(-1)}T00:00:00Z`);
const elapsedYears = (last - first) / 31_557_600_000;
const n = snapshot.candidateTickers.length;
const k = 5;
const total = Number(binomialBigInt(n, k));
assert.equal(total, 252);
assert.equal(binomialBigInt(25, 7), 480700n);
const bounds = relativeBandBounds(k, 0.20);
assert.ok(Math.abs(bounds.target - 0.20) < 1e-12);
assert.ok(Math.abs(bounds.lower - 0.16) < 1e-12);
assert.ok(Math.abs(bounds.upper - 0.24) < 1e-12);

const settings = {
  rebalanceMode: "band",
  bandRatio: 0.20,
  transactionCostBps: 10,
  executionDelayTradingDays: 1,
};
const rows = [];
let combination = unrankCombination(n, k, 0);
const started = performance.now();
for (let rank = 0; rank < total; rank += 1) {
  const indexes = Uint16Array.from(combination);
  const metrics = simulateExactPortfolio({
    prices,
    benchmarkPrices,
    periodKeys,
    indexes,
    elapsedYears,
    ...settings,
  });
  for (const key of METRIC_KEYS) assert.ok(Number.isFinite(metrics[key]), `${rank}:${key}`);
  rows.push({
    rank,
    indexes: [...indexes],
    tickers: [...indexes].map((index) => snapshot.candidateTickers[index]),
    metrics: Object.fromEntries(METRIC_KEYS.map((key) => [key, metrics[key]])),
  });
  if (rank + 1 < total) assert.equal(nextCombination(combination, n), true);
}
const elapsedMs = performance.now() - started;
assert.equal(new Set(rows.map((row) => row.indexes.join(","))).size, total);
const optimized = [...rows].sort((a, b) => b.metrics.optimized_score - a.metrics.optimized_score);
const cagr = [...rows].sort((a, b) => b.metrics.cagr - a.metrics.cagr);
assert.equal(optimized.length, total);
assert.equal(cagr.length, total);

const replayIndexes = Uint16Array.from(optimized[0].indexes);
const firstReplay = simulateExactPortfolio({
  prices, benchmarkPrices, periodKeys, indexes: replayIndexes, elapsedYears, ...settings,
});
const secondReplay = simulateExactPortfolio({
  prices, benchmarkPrices, periodKeys, indexes: replayIndexes, elapsedYears, ...settings,
});
for (const key of METRIC_KEYS) assert.equal(firstReplay[key], secondReplay[key], key);

const summary = {
  combinations: total,
  elapsed_seconds: elapsedMs / 1000,
  combinations_per_second: total / Math.max(elapsedMs / 1000, 0.001),
  holding_count: k,
  target_weight: bounds.target,
  lower_weight: bounds.lower,
  upper_weight: bounds.upper,
  optimized_champion: optimized[0],
  cagr_champion: cagr[0],
  deterministic_replay: true,
  metric_keys: METRIC_KEYS,
};
writeFileSync("diagnostics/exhaustive-results.json", JSON.stringify(summary, null, 2));
console.log(JSON.stringify({
  combinations: total,
  elapsed_seconds: Number(summary.elapsed_seconds.toFixed(3)),
  combinations_per_second: Number(summary.combinations_per_second.toFixed(1)),
  optimized_champion: optimized[0].tickers,
}));
