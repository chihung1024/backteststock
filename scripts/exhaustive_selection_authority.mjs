import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  EXHAUSTIVE_ENGINE_VERSION,
  MAX_EXHAUSTIVE_COMBINATIONS,
  buildPeriodKeys,
  combinationCountNumber,
  nextCombination,
  simulateExactPortfolio,
  unrankCombination,
} from "../public/exhaustive-optimizer-core.js";

export const EXHAUSTIVE_SELECTION_BRIDGE_VERSION =
  "exhaustive-selection-authority-2026-08-15.1";

const MAX_SOURCE_TICKERS = 100;
const MAX_TRANSACTION_COST_BPS = 1000;
const ALLOWED_REBALANCE_MODES = new Set([
  "band",
  "monthly",
  "quarterly",
  "annually",
  "never",
]);

function requiredArray(value, label) {
  if (!Array.isArray(value) || !value.length) throw new TypeError(`${label} must be a non-empty array`);
  return value;
}

function canonicalSymbols(values, label) {
  const symbols = requiredArray(values, label).map((value) => String(value));
  if (symbols.some((symbol) => !symbol || symbol !== symbol.trim().toUpperCase())) {
    throw new TypeError(`${label} must already contain canonical symbols`);
  }
  if (new Set(symbols).size !== symbols.length) throw new TypeError(`${label} must be unique`);
  return symbols;
}

function finiteNumber(value, label) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) throw new TypeError(`${label} must be finite`);
  return numeric;
}

function normalizeInput(input) {
  const candidateTickers = canonicalSymbols(input?.candidateTickers, "candidateTickers");
  if (candidateTickers.length < 2 || candidateTickers.length > MAX_SOURCE_TICKERS) {
    throw new RangeError(`candidateTickers must contain 2-${MAX_SOURCE_TICKERS} symbols`);
  }
  const benchmark = String(input?.benchmark || "");
  if (!benchmark || benchmark !== benchmark.trim().toUpperCase()) {
    throw new TypeError("benchmark must already be a canonical symbol");
  }
  if (candidateTickers.includes(benchmark)) throw new RangeError("benchmark cannot be a candidate");

  const dates = requiredArray(input?.dates, "dates").map((value) => String(value));
  if (dates.some((value) => !/^\d{4}-\d{2}-\d{2}$/u.test(value))) {
    throw new TypeError("dates must be ISO calendar dates");
  }
  if (new Set(dates).size !== dates.length) throw new RangeError("dates must be unique");
  for (let index = 1; index < dates.length; index += 1) {
    if (dates[index] <= dates[index - 1]) throw new RangeError("dates must be strictly increasing");
  }

  const required = [...candidateTickers, benchmark];
  const rawPrices = input?.prices;
  if (!rawPrices || typeof rawPrices !== "object" || Array.isArray(rawPrices)) {
    throw new TypeError("prices must be an object keyed by symbol");
  }
  const prices = required.map((symbol) => {
    const values = requiredArray(rawPrices[symbol], `prices.${symbol}`).map((value) => finiteNumber(value, `prices.${symbol}`));
    if (values.length !== dates.length) throw new RangeError(`prices.${symbol} length must equal dates length`);
    if (values.some((value) => value <= 0)) throw new RangeError(`prices.${symbol} must stay positive`);
    return Float64Array.from(values);
  });
  const benchmarkPrices = prices.at(-1);
  const candidatePrices = prices.slice(0, -1);

  const settings = input?.settings || {};
  const holdingCount = Number(settings.holdingCount);
  if (!Number.isInteger(holdingCount) || holdingCount < 1 || holdingCount > candidateTickers.length) {
    throw new RangeError("holdingCount must be an integer within the candidate count");
  }
  const combinationCount = combinationCountNumber(candidateTickers.length, holdingCount);
  if (combinationCount > MAX_EXHAUSTIVE_COMBINATIONS) {
    throw new RangeError(`combination count exceeds ${MAX_EXHAUSTIVE_COMBINATIONS}`);
  }
  const rebalanceMode = String(settings.rebalanceMode || "never");
  if (!ALLOWED_REBALANCE_MODES.has(rebalanceMode)) throw new RangeError("unsupported rebalanceMode");
  const bandRatio = finiteNumber(settings.bandRatio ?? 0.2, "bandRatio");
  if (bandRatio <= 0 || bandRatio >= 1) throw new RangeError("bandRatio must be between zero and one");
  const transactionCostBps = finiteNumber(settings.transactionCostBps ?? 0, "transactionCostBps");
  if (transactionCostBps < 0 || transactionCostBps > MAX_TRANSACTION_COST_BPS) {
    throw new RangeError(`transactionCostBps must be between 0 and ${MAX_TRANSACTION_COST_BPS}`);
  }
  const executionDelayTradingDays = Number(settings.executionDelayTradingDays ?? 1);
  if (!Number.isInteger(executionDelayTradingDays) || executionDelayTradingDays < 0) {
    throw new RangeError("executionDelayTradingDays must be a non-negative integer");
  }
  const riskFreeRate = finiteNumber(input?.riskFreeRate ?? 0, "riskFreeRate");
  if (riskFreeRate <= -1) throw new RangeError("riskFreeRate must be greater than -1");

  const first = new Date(`${dates[0]}T00:00:00Z`).getTime();
  const last = new Date(`${dates.at(-1)}T00:00:00Z`).getTime();
  const elapsedYears = Math.max((last - first) / 31_557_600_000, 1 / 365.25);

  return {
    candidateTickers,
    benchmark,
    dates,
    candidatePrices,
    benchmarkPrices,
    periodKeys: buildPeriodKeys(dates),
    holdingCount,
    combinationCount,
    rebalanceMode,
    bandRatio,
    transactionCostBps,
    executionDelayTradingDays,
    riskFreeRate,
    dailyRiskFreeRate: (1 + riskFreeRate) ** (1 / 252) - 1,
    elapsedYears,
    datasetHash: String(input?.datasetHash || ""),
  };
}

function normalizedDescendingScore(value) {
  return Number.isFinite(value) ? Number(value) : Number.NEGATIVE_INFINITY;
}

export function selectBestExhaustivePortfolio(input) {
  const state = normalizeInput(input);
  let indexes = unrankCombination(state.candidateTickers.length, state.holdingCount, 0n);
  let bestRank = 0;
  let bestIndexes = Uint16Array.from(indexes);
  let bestMetrics = null;
  let bestScore = Number.NEGATIVE_INFINITY;

  for (let rank = 0; rank < state.combinationCount; rank += 1) {
    const metrics = simulateExactPortfolio({
      prices: state.candidatePrices,
      benchmarkPrices: state.benchmarkPrices,
      periodKeys: state.periodKeys,
      indexes,
      elapsedYears: state.elapsedYears,
      rebalanceMode: state.rebalanceMode,
      bandRatio: state.bandRatio,
      transactionCostBps: state.transactionCostBps,
      executionDelayTradingDays: state.executionDelayTradingDays,
      riskFreeRate: state.riskFreeRate,
      dailyRiskFreeRate: state.dailyRiskFreeRate,
      collectEvents: false,
    });
    const score = normalizedDescendingScore(metrics.optimized_score);
    if (bestMetrics === null || score > bestScore || (score === bestScore && rank < bestRank)) {
      bestRank = rank;
      bestIndexes = Uint16Array.from(indexes);
      bestMetrics = metrics;
      bestScore = score;
    }
    if (rank + 1 < state.combinationCount && !nextCombination(indexes, state.candidateTickers.length)) {
      throw new Error("combination enumeration ended before the declared count");
    }
  }

  const selectedConstituents = [...bestIndexes].map((index) => state.candidateTickers[index]);
  const weight = 1 / selectedConstituents.length;
  return {
    bridgeVersion: EXHAUSTIVE_SELECTION_BRIDGE_VERSION,
    authorityVersion: EXHAUSTIVE_ENGINE_VERSION,
    datasetHash: state.datasetHash,
    ranking: {
      field: "optimized_score",
      direction: "desc",
      nonFinite: "negative-infinity",
      tieBreak: "smaller-combination-rank",
    },
    combinationCount: state.combinationCount,
    bestRank,
    selectedConstituents,
    weights: selectedConstituents.map(() => weight),
    winningMetrics: Object.fromEntries(
      Object.entries(bestMetrics || {}).map(([key, value]) => [
        key,
        Number.isFinite(value) ? Number(value) : null,
      ]),
    ),
  };
}

export function authorityIdentity() {
  return {
    bridgeVersion: EXHAUSTIVE_SELECTION_BRIDGE_VERSION,
    authorityVersion: EXHAUSTIVE_ENGINE_VERSION,
  };
}

function runCli() {
  const requestText = readFileSync(0, "utf8");
  const request = JSON.parse(requestText || "{}");
  const response = request.type === "version"
    ? authorityIdentity()
    : selectBestExhaustivePortfolio(request);
  process.stdout.write(`${JSON.stringify(response)}\n`);
}

const currentFile = fileURLToPath(import.meta.url);
const invokedFile = process.argv[1] ? path.resolve(process.argv[1]) : "";
if (invokedFile && currentFile === invokedFile) {
  try {
    runCli();
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}
