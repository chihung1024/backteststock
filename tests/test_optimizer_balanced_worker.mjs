import assert from "node:assert/strict";
import test from "node:test";

import {
  balancedSearchPlan,
  selectBalancedCombinations,
} from "../public/optimizer-balanced-worker.js";

function masks20Choose10(limit) {
  const output = [];
  let mask = (1 << 10) - 1;
  const end = 1 << 20;
  while (mask < end && output.length < limit) {
    output.push(mask >>> 0);
    const smallest = mask & -mask;
    const ripple = mask + smallest;
    mask = (((ripple ^ mask) >>> 2) / smallest) | ripple;
  }
  return output;
}

test("balanced 30000 search uses five equal objective pools and diversity", () => {
  assert.deepEqual(balancedSearchPlan(30000), {
    total: 30000,
    objectives: {
      sortino_ratio: 5400,
      cagr: 5400,
      mdd_abs: 5400,
      beta_abs: 5400,
      alpha: 5400,
    },
    pareto_diversity: 3000,
  });
});

test("balanced exact verification returns 48 per objective plus 60 diverse records", () => {
  const masks = masks20Choose10(900);
  const records = masks.map((mask, index) => ({
    combinationId: `source-${index}`,
    mask,
    tickers: Array.from({ length: 10 }, (_, tickerIndex) => `T${tickerIndex}`),
    sourceRun: index % 7 === 0 ? "pareto_diversity" : `objective:${index % 5}`,
    approximateTrainingMetrics: {
      sortino_ratio: Math.sin(index / 17) + index / 5000,
      cagr: Math.cos(index / 19) / 10 + index / 10000,
      mdd: -(0.1 + (index % 100) / 1000),
      beta: 0.5 + (index % 80) / 100,
      alpha: Math.sin(index / 23) / 20,
    },
  }));
  const selected = selectBalancedCombinations(records);

  assert.equal(selected.records.length, 300);
  assert.equal(new Set(selected.records.map((record) => record.mask)).size, 300);
  assert.deepEqual(selected.allocation, {
    requested: {
      sortino_ratio: 48,
      cagr: 48,
      mdd_abs: 48,
      beta_abs: 48,
      alpha: 48,
      pareto_diversity: 60,
    },
    actual: {
      sortino_ratio: 48,
      cagr: 48,
      mdd_abs: 48,
      beta_abs: 48,
      alpha: 48,
      pareto_diversity: 60,
    },
  });
});
