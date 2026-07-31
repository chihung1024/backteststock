import assert from "node:assert/strict";
import test from "node:test";

import {
  buildScoreMatrix,
  scoreRecordFor,
} from "../public/scan-score-formulas.js";

const SAMPLE = [
  { ticker: "AAA", sortino_ratio: 2, alpha: 0.10, mdd: -0.20 },
  { ticker: "BBB", sortino_ratio: 1, alpha: 0.08, mdd: -0.10 },
  { ticker: "CCC", sortino_ratio: 0.5, alpha: 0.15, mdd: -0.50 },
];

test("original and recommended formulas use raw unrounded metrics", () => {
  const result = buildScoreMatrix(SAMPLE);
  const original = scoreRecordFor(result, "AAA", "sortino_alpha_mdd_score");
  const recommended = scoreRecordFor(result, "AAA", "alpha_sqrt_sortino_mdd_score");

  assert.equal(original.status, "ok");
  assert.equal(original.score, 1);
  assert.equal(original.rank, 1);
  assert.equal(recommended.status, "ok");
  assert.ok(Math.abs(recommended.score - (0.10 * Math.sqrt(10))) < 1e-12);
  assert.equal(recommended.rank, 1);
});

test("percentile formula can produce a different cross-sectional ordering", () => {
  const result = buildScoreMatrix(SAMPLE);
  const aaa = scoreRecordFor(result, "AAA", "percentile_composite_score");
  const bbb = scoreRecordFor(result, "BBB", "percentile_composite_score");
  const ccc = scoreRecordFor(result, "CCC", "percentile_composite_score");

  assert.equal(aaa.score, 65);
  assert.equal(ccc.score, 50);
  assert.equal(bbb.score, 35);
  assert.equal(aaa.rank, 1);
  assert.equal(ccc.rank, 2);
  assert.equal(bbb.rank, 3);
  assert.equal(ccc.rankDeltaVsRecommended, -1);
});

test("recommended square-root formula rejects non-positive Sortino", () => {
  const result = buildScoreMatrix([
    { ticker: "NEG", sortino_ratio: -1, alpha: 0.10, mdd: -0.20 },
  ]);
  const original = scoreRecordFor(result, "NEG", "sortino_alpha_mdd_score");
  const recommended = scoreRecordFor(result, "NEG", "alpha_sqrt_sortino_mdd_score");
  const percentile = scoreRecordFor(result, "NEG", "percentile_composite_score");

  assert.equal(original.status, "ok");
  assert.equal(original.score, -0.5);
  assert.equal(recommended.status, "non_positive_sortino");
  assert.equal(recommended.score, null);
  assert.equal(percentile.status, "ok");
  assert.equal(percentile.score, 100);
});

test("missing metrics and zero drawdown remain unranked", () => {
  const result = buildScoreMatrix([
    { ticker: "MISS", sortino_ratio: 1, alpha: null, mdd: -0.20 },
    { ticker: "ZERO", sortino_ratio: 1, alpha: 0.10, mdd: 0 },
  ]);

  for (const formulaKey of [
    "sortino_alpha_mdd_score",
    "alpha_sqrt_sortino_mdd_score",
    "percentile_composite_score",
  ]) {
    const missing = scoreRecordFor(result, "MISS", formulaKey);
    const zero = scoreRecordFor(result, "ZERO", formulaKey);
    assert.equal(missing.status, "missing_metrics");
    assert.equal(missing.rank, null);
    assert.equal(zero.status, "zero_mdd");
    assert.equal(zero.rank, null);
  }
});

test("duplicate ticker keeps the latest scan result", () => {
  const result = buildScoreMatrix([
    { ticker: "DUP", sortino_ratio: 1, alpha: 0.01, mdd: -0.20 },
    { ticker: "dup", sortino_ratio: 2, alpha: 0.10, mdd: -0.20 },
  ]);
  const record = scoreRecordFor(result, "DUP", "sortino_alpha_mdd_score");

  assert.equal(result.total, 1);
  assert.equal(record.score, 1);
});
