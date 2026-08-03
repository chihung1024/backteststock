import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_SCAN_MIN_COVERAGE_PERCENT,
  SCAN_COVERAGE_DEFINITION_VERSION,
  buildScanCoverageStats,
  deriveScanCoverage,
  normalizeScanMinCoveragePercent,
  relativeScanCoverage,
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

test("coverage uses the largest successful trading-day count across the whole job", () => {
  const rows = [
    { ticker: "FULL", status: "ok", trading_days: 2604, data_coverage: 1 },
    { ticker: "MID", status: "ok", trading_days: 1519, data_coverage: 1 },
    { ticker: "SHORT", status: "ok", trading_days: 609, data_coverage: 1 },
    { ticker: "IPO", status: "ok", trading_days: 35, data_coverage: 1 },
    { ticker: "FAILED", status: "failed", error: "unavailable", trading_days: 9999 },
  ];

  const derived = deriveScanCoverage(rows);
  assert.equal(derived.maximumTradingDays, 2604);
  assert.equal(derived.coverageDefinitionVersion, SCAN_COVERAGE_DEFINITION_VERSION);
  assert.equal(derived.settled.length, 4);
  assert.equal(derived.settled[0].data_coverage, 1);
  assert.ok(Math.abs(derived.settled[1].data_coverage - (1519 / 2604)) < 1e-12);
  assert.ok(Math.abs(derived.settled[2].data_coverage - (609 / 2604)) < 1e-12);
  assert.ok(Math.abs(derived.settled[3].data_coverage - (35 / 2604)) < 1e-12);
  assert.equal(derived.settled[0].benchmark_calendar_coverage, 1);
  assert.equal(
    derived.settled[0].coverage_definition_version,
    SCAN_COVERAGE_DEFINITION_VERSION,
  );
});

test("coverage is independent of API batch arrival order", () => {
  const rows = [
    { ticker: "A", status: "ok", trading_days: 35 },
    { ticker: "B", status: "ok", trading_days: 2604 },
    { ticker: "C", status: "ok", trading_days: 1519 },
  ];
  const forward = new Map(
    deriveScanCoverage(rows).settled.map((item) => [item.ticker, item.data_coverage]),
  );
  const reverse = new Map(
    deriveScanCoverage([...rows].reverse()).settled.map((item) => [item.ticker, item.data_coverage]),
  );
  assert.deepEqual([...forward.entries()].sort(), [...reverse.entries()].sort());
});

test("coverage filtering includes the exact threshold and hides invalid histories", () => {
  const rows = [
    { ticker: "FULL", status: "ok", trading_days: 1000 },
    { ticker: "AT90", status: "ok", trading_days: 900 },
    { ticker: "LOW", status: "ok", trading_days: 899 },
    { ticker: "MISSING", status: "ok", trading_days: null },
    { ticker: "ZERO", status: "ok", trading_days: 0 },
    { ticker: "FAILED", error: "unavailable", trading_days: 1000 },
    { ticker: "RETRY", retryable: true, trading_days: 1000 },
  ];

  const defaultStats = buildScanCoverageStats(rows, 90);
  assert.deepEqual(defaultStats.shown.map((item) => item.ticker), ["FULL", "AT90"]);
  assert.equal(defaultStats.settled.length, 5);
  assert.equal(defaultStats.hidden, 3);
  assert.equal(defaultStats.maximumTradingDays, 1000);

  const relaxed = buildScanCoverageStats(rows, 89.9);
  assert.deepEqual(relaxed.shown.map((item) => item.ticker), ["FULL", "AT90", "LOW"]);
  assert.equal(relaxed.hidden, 2);

  const zeroThreshold = buildScanCoverageStats(rows, 0);
  assert.deepEqual(
    zeroThreshold.shown.map((item) => item.ticker),
    ["FULL", "AT90", "LOW"],
  );
  assert.equal(zeroThreshold.hidden, 2);
});

test("relative coverage rejects invalid denominators", () => {
  const row = { ticker: "A", status: "ok", trading_days: 100 };
  assert.equal(relativeScanCoverage(row, 0), null);
  assert.equal(relativeScanCoverage(row, null), null);
  assert.equal(relativeScanCoverage({ ...row, trading_days: 0 }, 100), null);
  assert.equal(relativeScanCoverage(row, 100), 1);
});
