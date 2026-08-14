import assert from "node:assert/strict";
import test from "node:test";

import { METRIC_KEYS } from "../public/exhaustive-optimizer-core.js";
import { RETENTION_METRIC_KEYS } from "../public/exhaustive-retention.js";

function snapshot() {
  const dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"];
  return {
    candidateTickers: ["AAA", "BBB", "CCC"],
    benchmark: "SPY",
    dates,
    prices: {
      AAA: [100, 101, 102, 103],
      BBB: [100, 100.5, 102, 101],
      CCC: [100, 99, 100, 104],
      SPY: [100, 100.4, 101, 101.5],
    },
  };
}

const settings = {
  holdingCount: 2,
  rebalanceMode: "never",
  bandRatio: 0.2,
  transactionCostBps: 0,
  executionDelayTradingDays: 1,
};

test("worker streams rank-selection metrics and materializes full compact metrics", async () => {
  const originalSelf = globalThis.self;
  const messages = [];
  let listener;
  globalThis.self = {
    addEventListener(type, callback) {
      if (type === "message") listener = callback;
    },
    postMessage(message) {
      messages.push(message);
    },
  };

  try {
    await import(`../public/exhaustive-optimizer-worker.js?protocol=${Date.now()}`);
    listener({ data: { type: "init", snapshot: snapshot() } });
    assert.equal(messages.at(-1).type, "ready");

    listener({
      data: {
        type: "run-chunk",
        resultMode: "retention",
        chunkIndex: 0,
        startRank: "0",
        count: 3,
        settings,
      },
    });
    const selected = messages.at(-1);
    assert.equal(selected.type, "chunk-complete");
    assert.equal(selected.resultMode, "retention");
    assert.equal(selected.combinations, null);
    assert.deepEqual(selected.metricKeys, RETENTION_METRIC_KEYS);
    assert.equal(selected.metrics.length, 3 * RETENTION_METRIC_KEYS.length);

    listener({
      data: {
        type: "materialize-ranks",
        chunkIndex: 0,
        rowStart: 0,
        ranks: Uint32Array.from([0, 2]),
        settings,
      },
    });
    const materialized = messages.at(-1);
    assert.equal(materialized.type, "materialized");
    assert.equal(materialized.completed, 2);
    assert.ok(materialized.metrics instanceof Float32Array);
    assert.equal(materialized.metrics.length, 2 * METRIC_KEYS.length);

    listener({
      data: {
        type: "calibrate",
        ranks: [0],
        settings: { ...settings, transactionCostBps: 1000.1 },
      },
    });
    const rejected = messages.at(-1);
    assert.equal(rejected.type, "error");
    assert.equal(rejected.requestType, "calibrate");
    assert.match(rejected.error, /0.*1000 bps/u);
  } finally {
    globalThis.self = originalSelf;
  }
});
