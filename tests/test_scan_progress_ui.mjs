import assert from "node:assert/strict";
import test from "node:test";

import {
  formatScanChunkPositionRange,
  formatScanSettlement,
  rewriteScanProgressMessage,
  rewriteScanStatusMessage,
  scanSettlementSnapshot,
} from "../public/scan-progress-ui.js";

function success(ticker) {
  return { ticker, status: "ok", retryable: false };
}

function failure(ticker) {
  return {
    ticker,
    status: "failed",
    retryable: false,
    error: "terminal failure",
  };
}

function jobWith({ total = 500, successes = 0, failures = 0 } = {}) {
  const tickers = Array.from({ length: total }, (_, index) => `T${String(index + 1).padStart(4, "0")}`);
  const results = [
    ...tickers.slice(0, successes).map(success),
    ...tickers.slice(successes, successes + failures).map(failure),
  ];
  return {
    payload: { tickers },
    results,
  };
}

test("settlement snapshot separates successful and failed results", () => {
  const snapshot = scanSettlementSnapshot(jobWith({ successes: 300, failures: 100 }));
  assert.deepEqual(snapshot, {
    settled: 400,
    total: 500,
    successful: 300,
    failed: 100,
    unfinished: 100,
  });
  assert.equal(
    formatScanSettlement(snapshot, { includeUnfinished: true }),
    "已結算 400 / 500 檔（成功 300、失敗 100、未完成 100）",
  );
});

test("401-500 progress no longer describes terminal failures as successful completion", () => {
  const job = jobWith({ successes: 300, failures: 100 });
  assert.equal(
    rewriteScanProgressMessage(
      "正在取得第 401–500 檔；已完成 400 / 500 檔",
      job,
    ),
    "正在取得第 401–500 檔；已結算 400 / 500 檔（成功 300、失敗 100）",
  );
});

test("active scan range uses immutable original ticker positions", () => {
  const tickers = Array.from(
    { length: 500 },
    (_, index) => `T${String(index + 1).padStart(4, "0")}`,
  );

  assert.equal(
    formatScanChunkPositionRange(tickers, tickers.slice(400, 500)),
    "401–500",
  );
  assert.equal(
    formatScanChunkPositionRange(tickers, tickers.slice(300, 400)),
    "301–400",
  );
});

test("non-contiguous retry batches do not fabricate a numeric range", () => {
  const tickers = Array.from(
    { length: 500 },
    (_, index) => `T${String(index + 1).padStart(4, "0")}`,
  );

  assert.equal(
    formatScanChunkPositionRange(tickers, [tickers[300], tickers[400]]),
    null,
  );
  assert.equal(
    rewriteScanProgressMessage(
      "正在取得本次批次；已完成 400 / 500 檔",
      jobWith({ successes: 400 }),
    ),
    "正在取得本次批次；已結算 400 / 500 檔（成功 400、失敗 0）",
  );
});

test("final 300-success 200-failure state is explicit", () => {
  const job = jobWith({ successes: 300, failures: 200 });
  assert.equal(
    rewriteScanProgressMessage("完整取得 500 / 500 檔", job),
    "回測結束：已結算 500 / 500 檔（成功 300、失敗 200、未完成 0）",
  );
});

test("stale persisted state cannot rewrite a newer in-memory progress count", () => {
  const staleJob = jobWith({ successes: 300, failures: 0 });
  const message = "正在取得第 401–500 檔；已完成 400 / 500 檔";
  assert.equal(rewriteScanProgressMessage(message, staleJob), message);
});

test("paused and saved status exposes settlement counts", () => {
  const job = jobWith({ successes: 250, failures: 50 });
  assert.equal(
    rewriteScanStatusMessage(
      "回測已暫停；已保存 300 / 500 檔，按「繼續未完成回測」即可接續。",
      job,
    ),
    "回測已暫停；已結算 300 / 500 檔（成功 250、失敗 50、未完成 200），按「繼續未完成回測」即可接續。",
  );
});
