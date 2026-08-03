import {
  EXHAUSTIVE_ENGINE_VERSION,
  METRIC_KEYS,
  buildPeriodKeys,
  metricsToArray,
  nextCombination,
  simulateExactPortfolio,
  unrankCombination,
} from "./exhaustive-optimizer-core.js?v=20260803.2";
import { RETENTION_METRIC_KEYS } from "./exhaustive-retention.js?v=20260803.2";

let state = null;
let cancelled = false;

function normalizeSnapshot(snapshot) {
  const tickers = [...snapshot.candidateTickers];
  const dates = [...snapshot.dates];
  const prices = tickers.map((ticker) => Float64Array.from(snapshot.prices[ticker]));
  const benchmarkPrices = Float64Array.from(snapshot.prices[snapshot.benchmark]);
  const first = new Date(`${dates[0]}T00:00:00Z`).getTime();
  const last = new Date(`${dates.at(-1)}T00:00:00Z`).getTime();
  return {
    tickers,
    dates,
    prices,
    benchmarkPrices,
    periodKeys: buildPeriodKeys(dates),
    elapsedYears: Math.max((last - first) / 31_557_600_000, 1 / 365.25),
    datasetHash: snapshot.datasetHash || snapshot.priceDatasetHash || "",
  };
}

function evaluate(indexes, settings, collectEvents = false) {
  return simulateExactPortfolio({
    prices: state.prices,
    benchmarkPrices: state.benchmarkPrices,
    periodKeys: state.periodKeys,
    indexes,
    elapsedYears: state.elapsedYears,
    rebalanceMode: settings.rebalanceMode,
    bandRatio: settings.bandRatio,
    transactionCostBps: settings.transactionCostBps,
    executionDelayTradingDays: settings.executionDelayTradingDays,
    collectEvents,
  });
}

function processRanks(ranks, settings) {
  const started = performance.now();
  let completed = 0;
  for (const rank of ranks) {
    if (cancelled) break;
    const indexes = unrankCombination(state.tickers.length, settings.holdingCount, BigInt(rank));
    evaluate(indexes, settings, false);
    completed += 1;
  }
  return {
    completed,
    elapsedMs: performance.now() - started,
  };
}

function processChunk(message) {
  const { chunkIndex, count, settings } = message;
  const n = state.tickers.length;
  const k = settings.holdingCount;
  const retentionMode = message.resultMode === "retention";
  const metricKeys = retentionMode ? RETENTION_METRIC_KEYS : METRIC_KEYS;
  const metricIndexes = metricKeys.map((key) => METRIC_KEYS.indexOf(key));
  const combinations = retentionMode ? null : new Uint16Array(count * k);
  const metrics = new Float64Array(count * metricKeys.length);
  let indexes = unrankCombination(n, k, BigInt(message.startRank));
  const started = performance.now();
  let completed = 0;

  for (let row = 0; row < count; row += 1) {
    if (cancelled) break;
    if (combinations) combinations.set(indexes, row * k);
    const result = evaluate(indexes, settings, false);
    const values = metricsToArray(result);
    const offset = row * metricKeys.length;
    for (let index = 0; index < metricIndexes.length; index += 1) {
      metrics[offset + index] = values[metricIndexes[index]];
    }
    completed += 1;
    if (row + 1 < count && !nextCombination(indexes, n)) break;
  }

  return {
    chunkIndex,
    startRank: String(message.startRank),
    requestedCount: count,
    completed,
    elapsedMs: performance.now() - started,
    resultMode: retentionMode ? "retention" : "full",
    metricKeys,
    combinations: combinations && (completed === count
      ? combinations
      : combinations.slice(0, completed * k)),
    metrics: completed === count
      ? metrics
      : metrics.slice(0, completed * metricKeys.length),
  };
}

function materializeRanks(message) {
  const ranks = Uint32Array.from(message.ranks || []);
  const metrics = new Float32Array(ranks.length * METRIC_KEYS.length);
  const started = performance.now();
  let completed = 0;
  for (let row = 0; row < ranks.length; row += 1) {
    if (cancelled) break;
    const indexes = unrankCombination(
      state.tickers.length,
      message.settings.holdingCount,
      BigInt(ranks[row]),
    );
    metrics.set(metricsToArray(evaluate(indexes, message.settings, false)), row * METRIC_KEYS.length);
    completed += 1;
  }
  return {
    chunkIndex: message.chunkIndex,
    rowStart: message.rowStart,
    completed,
    elapsedMs: performance.now() - started,
    metrics: completed === ranks.length
      ? metrics
      : metrics.slice(0, completed * METRIC_KEYS.length),
  };
}

self.addEventListener("message", (event) => {
  const message = event.data || {};
  try {
    if (message.type === "init") {
      cancelled = false;
      state = normalizeSnapshot(message.snapshot);
      self.postMessage({
        type: "ready",
        engineVersion: EXHAUSTIVE_ENGINE_VERSION,
        observations: state.dates.length,
        candidateCount: state.tickers.length,
      });
      return;
    }
    if (message.type === "cancel") {
      cancelled = true;
      return;
    }
    if (!state) throw new Error("Worker 尚未初始化。");
    if (message.type === "calibrate") {
      cancelled = false;
      const result = processRanks(message.ranks || [], message.settings || {});
      self.postMessage({ type: "calibrated", ...result });
      return;
    }
    if (message.type === "run-chunk") {
      cancelled = false;
      const result = processChunk(message);
      const transfer = [result.metrics.buffer];
      if (result.combinations) transfer.push(result.combinations.buffer);
      self.postMessage(
        { type: "chunk-complete", ...result },
        transfer,
      );
      return;
    }
    if (message.type === "materialize-ranks") {
      cancelled = false;
      const result = materializeRanks(message);
      self.postMessage(
        { type: "materialized", ...result },
        [result.metrics.buffer],
      );
      return;
    }
    if (message.type === "detail") {
      const indexes = Uint16Array.from(message.indexes || []);
      const metrics = evaluate(indexes, message.settings || {}, true);
      self.postMessage({ type: "detail-complete", indexes: [...indexes], metrics });
    }
  } catch (error) {
    self.postMessage({
      type: "error",
      requestType: message.type,
      chunkIndex: message.chunkIndex,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});
