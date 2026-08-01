import assert from "node:assert/strict";
import test from "node:test";

import {
  enumerateCombinationMasks,
  optimizeSnapshot,
  popcount20,
  relativeBandBounds,
  serializeMasksLittleEndian,
} from "../public/optimizer-worker.js";


test("20 choose 10 enumeration is complete and canonical", () => {
  const masks = enumerateCombinationMasks();
  assert.equal(masks.length, 184756);
  assert.equal(masks[0], (1 << 10) - 1);
  assert.equal(popcount20(masks[0]), 10);
  assert.equal(popcount20(masks.at(-1)), 10);
  assert.equal(new Set(masks).size, masks.length);
});


test("relative band uses target-weight percentage", () => {
  const bounds = relativeBandBounds(0.10, 0.20);
  assert.ok(Math.abs(bounds.lower - 0.08) < 1e-12);
  assert.ok(Math.abs(bounds.upper - 0.12) < 1e-12);
});


test("mask audit bytes use explicit little-endian uint32 encoding", () => {
  const bytes = serializeMasksLittleEndian(Uint32Array.from([0x01020304, 0xa0b0c0d0]));
  assert.deepEqual(
    [...bytes],
    [0x04, 0x03, 0x02, 0x01, 0xd0, 0xc0, 0xb0, 0xa0],
  );
});


test("optimizer evaluates all proxies and returns deterministic verification set", async () => {
  const candidateTickers = Array.from({ length: 20 }, (_, index) => `T${String(index).padStart(2, "0")}`);
  const dates = [];
  const prices = {};
  const start = new Date("2024-01-02T00:00:00Z");
  for (let day = 0; day < 80; day += 1) {
    const date = new Date(start);
    date.setUTCDate(date.getUTCDate() + day);
    dates.push(date.toISOString().slice(0, 10));
  }
  for (let asset = 0; asset < 20; asset += 1) {
    prices[candidateTickers[asset]] = dates.map((_, day) => (
      100
      * Math.exp((0.00015 + asset * 0.00001) * day)
      * (1 + Math.sin((day + asset) / 7) * 0.006)
    ));
  }
  prices.SPY = dates.map((_, day) => 100 * Math.exp(0.0002 * day));

  const snapshot = {
    optimizerAlgorithmVersion: "optimizer-test-v1",
    metricDefinitionVersion: "metric-test-v1",
    candidateTickers,
    benchmark: "SPY",
    dates,
    prices,
    split: {
      splitIndex: 56,
      trainingStart: dates[0],
      trainingEnd: dates[55],
      validationStart: dates[56],
      validationEnd: dates.at(-1),
    },
  };
  const progressStages = new Set();
  const result = await optimizeSnapshot({
    snapshot,
    settings: {
      primaryObjective: "sortino_ratio",
      searchBudget: 1000,
    },
    progress(stage) {
      progressStages.add(stage);
    },
  });

  assert.equal(result.search.proxyCombinationCount, 184756);
  assert.equal(result.search.deepCombinationCount, 1000);
  assert.equal(result.search.exactVerificationCount, 300);
  assert.equal(result.search.evaluatedMasks.length, 1000);
  assert.equal(result.search.evaluatedMaskHash.length, 64);
  assert.deepEqual(result.search.budgetAllocation, {
    requested: {
      sortino_ratio: 500,
      cagr: 100,
      mdd_abs: 100,
      beta_abs: 100,
      alpha: 100,
      pareto_diversity: 100,
    },
    actual: {
      sortino_ratio: 500,
      cagr: 100,
      mdd_abs: 100,
      beta_abs: 100,
      alpha: 100,
      pareto_diversity: 100,
    },
  });
  assert.equal(result.combinations.length, 300);
  assert.equal(new Set(result.combinations.map((item) => item.mask)).size, 300);
  assert.ok(result.combinations.every((item) => item.tickers.length === 10));
  assert.deepEqual(progressStages, new Set(["proxy", "selected", "deep"]));
});
