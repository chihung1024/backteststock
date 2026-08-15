import assert from "node:assert/strict";
import test from "node:test";

import {
  buildPeriodKeys,
  nextCombination,
  simulateExactPortfolio,
  unrankCombination,
} from "../public/exhaustive-optimizer-core.js";
import {
  authorityIdentity,
  selectBestExhaustivePortfolio,
} from "../scripts/exhaustive_selection_authority.mjs";

function dates(count = 65) {
  const start = Date.UTC(2024, 0, 2);
  return Array.from({ length: count }, (_, index) => (
    new Date(start + index * 86_400_000).toISOString().slice(0, 10)
  ));
}

function snapshot() {
  const calendar = dates();
  return {
    candidateTickers: ["AAA", "BBB", "CCC", "DDD"],
    benchmark: "SPY",
    dates: calendar,
    prices: {
      AAA: calendar.map((_, index) => 100 * (1.0025 ** index)),
      BBB: calendar.map((_, index) => 100 * (1.0012 ** index) * (1 + 0.015 * Math.sin(index / 3))),
      CCC: calendar.map((_, index) => 100 * (1.0018 ** index) * (1 + 0.02 * Math.cos(index / 5))),
      DDD: calendar.map((_, index) => 100 * (1.0005 ** index) * (1 + 0.01 * Math.sin(index / 2))),
      SPY: calendar.map((_, index) => 100 * (1.0010 ** index) * (1 + 0.008 * Math.sin(index / 4))),
    },
    datasetHash: "synthetic-authority-dataset",
    riskFreeRate: 0.03,
    settings: {
      holdingCount: 2,
      rebalanceMode: "never",
      bandRatio: 0.20,
      transactionCostBps: 0,
      executionDelayTradingDays: 1,
    },
  };
}

function directWinner(input) {
  const first = new Date(`${input.dates[0]}T00:00:00Z`).getTime();
  const last = new Date(`${input.dates.at(-1)}T00:00:00Z`).getTime();
  const elapsedYears = Math.max((last - first) / 31_557_600_000, 1 / 365.25);
  const prices = input.candidateTickers.map((ticker) => Float64Array.from(input.prices[ticker]));
  const benchmarkPrices = Float64Array.from(input.prices[input.benchmark]);
  const periodKeys = buildPeriodKeys(input.dates);
  const dailyRiskFreeRate = (1 + input.riskFreeRate) ** (1 / 252) - 1;
  const total = 6;
  let indexes = unrankCombination(input.candidateTickers.length, input.settings.holdingCount, 0n);
  let bestRank = 0;
  let bestScore = Number.NEGATIVE_INFINITY;
  let bestIndexes = Uint16Array.from(indexes);

  for (let rank = 0; rank < total; rank += 1) {
    const metrics = simulateExactPortfolio({
      prices,
      benchmarkPrices,
      periodKeys,
      indexes,
      elapsedYears,
      rebalanceMode: input.settings.rebalanceMode,
      bandRatio: input.settings.bandRatio,
      transactionCostBps: input.settings.transactionCostBps,
      executionDelayTradingDays: input.settings.executionDelayTradingDays,
      riskFreeRate: input.riskFreeRate,
      dailyRiskFreeRate,
      collectEvents: false,
    });
    const score = Number.isFinite(metrics.optimized_score)
      ? metrics.optimized_score
      : Number.NEGATIVE_INFINITY;
    if (rank === 0 || score > bestScore) {
      bestRank = rank;
      bestScore = score;
      bestIndexes = Uint16Array.from(indexes);
    }
    if (rank + 1 < total) assert.equal(nextCombination(indexes, input.candidateTickers.length), true);
  }
  return {
    bestRank,
    selectedConstituents: [...bestIndexes].map((index) => input.candidateTickers[index]),
  };
}

test("walk-forward bridge delegates exact simulation and winner ranking to current Exhaustive core", () => {
  const input = snapshot();
  const expected = directWinner(input);
  const actual = selectBestExhaustivePortfolio(input);

  assert.equal(actual.bestRank, expected.bestRank);
  assert.deepEqual(actual.selectedConstituents, expected.selectedConstituents);
  assert.equal(actual.datasetHash, input.datasetHash);
  assert.equal(actual.combinationCount, 6);
  assert.deepEqual(actual.ranking, {
    field: "optimized_score",
    direction: "desc",
    nonFinite: "negative-infinity",
    tieBreak: "smaller-combination-rank",
  });
  assert.deepEqual(actual.weights, [0.5, 0.5]);
});

test("non-finite optimized scores preserve current smaller-rank tie break", () => {
  const input = snapshot();
  const flat = input.dates.map(() => 100);
  input.prices = {
    AAA: [...flat],
    BBB: [...flat],
    CCC: [...flat],
    DDD: [...flat],
    SPY: input.dates.map((_, index) => 100 + index),
  };
  const actual = selectBestExhaustivePortfolio(input);
  assert.equal(actual.bestRank, 0);
  assert.deepEqual(actual.selectedConstituents, ["AAA", "BBB"]);
  assert.equal(actual.winningMetrics.optimized_score, null);
});

test("bridge identity reports the imported Exhaustive core version", () => {
  const identity = authorityIdentity();
  assert.match(identity.bridgeVersion, /^exhaustive-selection-authority-/u);
  assert.match(identity.authorityVersion, /^exhaustive-band-/u);
});
