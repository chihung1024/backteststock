import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  buildPeriodKeys,
  simulateExactPortfolio,
} from "../public/exhaustive-optimizer-core.js";

const fixture = JSON.parse(
  readFileSync(new URL("./fixtures/quant_authority_v1.json", import.meta.url), "utf8"),
);

function close(actual, expected, tolerance = 1e-12) {
  assert.ok(
    Math.abs(actual - expected) <= tolerance * Math.max(1, Math.abs(expected)),
    `expected ${actual} to match ${expected}`,
  );
}

test("exhaustive exact engine matches the canonical shared golden fixture", () => {
  const { dates, portfolioLevels, benchmarkLevels, riskFreeRate, canonical } = fixture;
  const first = new Date(`${dates[0]}T00:00:00Z`).getTime();
  const last = new Date(`${dates.at(-1)}T00:00:00Z`).getTime();
  const elapsedYears = (last - first) / 31_557_600_000;

  const result = simulateExactPortfolio({
    prices: [Float64Array.from(portfolioLevels)],
    benchmarkPrices: Float64Array.from(benchmarkLevels),
    periodKeys: buildPeriodKeys(dates),
    indexes: Uint16Array.from([0]),
    elapsedYears,
    rebalanceMode: "never",
    transactionCostBps: 0,
    executionDelayTradingDays: 1,
    riskFreeRate,
  });

  close(result.total_return, canonical.totalReturn);
  close(result.cagr, canonical.cagr);
  close(result.mdd, canonical.maxDrawdown);
  close(result.volatility, canonical.volatility);
  close(result.sortino_ratio, canonical.sortinoRatio);
  close(result.beta, canonical.beta);
  close(result.alpha, canonical.alpha);
  assert.equal(result.rebalance_count, 0);
  assert.equal(result.transaction_cost, 0);
});
