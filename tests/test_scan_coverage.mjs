import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_SCAN_MIN_COVERAGE_PERCENT,
  buildScanCoverageStats,
  normalizeScanMinCoveragePercent,
} from "../public/scan-coverage.js";

test("coverage threshold defaults to 90% and normalizes manual input safely", () => {
  assert.equal(DEFAULT_SCAN_MIN_COVERAGE_PERCENT, 90);
  assert.equal(normalizeScanMinCoveragePercent(null), 90);
  assert.equal(normalizeScanMinCoveragePercent(""), 90);
  assert.equal(normalizeScanMinCoveragePercent("89.94"), 89.9);
  assert.equal(normalizeScanMinCoveragePercent("120"), 100);
  assert.equal(normalizeScanMinCoveragePercent("-1"), 0);
  assert.equal(normalizeScanMinCoveragePercent("not-a-number", 85), 85);
});

test("coverage filtering includes the exact threshold and hides incomplete data", () => {
  const rows = [
    { ticker: "FULL", status: "ok", data_coverage: 1 },
    { ticker: "AT90", status: "ok", data_coverage: 0.9 },
    { ticker: "ROUNDING", status: "ok", data_coverage: 0.8999999999999 },
    { ticker: "LOW", status: "ok", data_coverage: 0.899 },
    { ticker: "MISSING", status: "ok", data_coverage: null },
    { ticker: "FAILED", error: "unavailable", data_coverage: 1 },
    { ticker: "RETRY", retryable: true, data_coverage: 1 },
  ];

  const defaultStats = buildScanCoverageStats(rows, 90);
  assert.deepEqual(defaultStats.shown.map((item) => item.ticker), ["FULL", "AT90", "ROUNDING"]);
  assert.equal(defaultStats.settled.length, 5);
  assert.equal(defaultStats.hidden, 2);

  const relaxed = buildScanCoverageStats(rows, 89.9);
  assert.deepEqual(relaxed.shown.map((item) => item.ticker), ["FULL", "AT90", "ROUNDING", "LOW"]);
  assert.equal(relaxed.hidden, 1);
});
