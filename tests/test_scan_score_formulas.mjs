import assert from "node:assert/strict";
import test from "node:test";

import {
  SCORE_FORMULAS,
  buildScoreMatrix,
  scoreRecordFor,
} from "../public/scan-score-formulas.js";

const SAMPLE = [
  { ticker: "AAA", sortino_ratio: 2, cagr: 0.30, beta: 1.20, mdd: -0.20 },
  { ticker: "BBB", sortino_ratio: 1, cagr: 0.10, beta: 0.80, mdd: -0.10 },
  { ticker: "CCC", sortino_ratio: 0.5, cagr: -0.05, beta: 1.50, mdd: -0.50 },
];

const FORMULA_KEYS = [
  "sortino_growth_beta_score",
  "sortino_growth_beta_quarter_score",
  "sortino_growth_beta_mdd_score",
];

test("three growth-beta formulas use raw unrounded metrics", () => {
  const result = buildScoreMatrix(SAMPLE);
  const stable = scoreRecordFor(result, "AAA", "sortino_growth_beta_score");
  const growth = scoreRecordFor(result, "AAA", "sortino_growth_beta_quarter_score");
  const drawdown = scoreRecordFor(result, "AAA", "sortino_growth_beta_mdd_score");

  assert.equal(SCORE_FORMULAS.length, 3);
  assert.deepEqual(SCORE_FORMULAS.map((formula) => formula.label), [
    "穩健分數",
    "成長分數",
    "回撤控制分數",
  ]);
  assert.equal(stable.status, "ok");
  assert.ok(Math.abs(stable.score - (2 * Math.sqrt(1.30 / 2.20))) < 1e-12);
  assert.equal(stable.rank, 1);

  assert.equal(growth.status, "ok");
  assert.ok(Math.abs(growth.score - (2 * Math.sqrt(1.30) / Math.pow(2.20, 0.25))) < 1e-12);
  assert.equal(growth.rank, 1);

  assert.equal(drawdown.status, "ok");
  assert.ok(Math.abs(drawdown.score - (2 * Math.sqrt(1.30 / (2.20 * 1.20)))) < 1e-12);
  assert.equal(drawdown.rank, 1);
  assert.equal(
    scoreRecordFor(result, "AAA", "sortino_growth_beta_squared_mdd_score"),
    null,
  );
});

test("the three formulas can produce different cross-sectional ranks", () => {
  const result = buildScoreMatrix([
    { ticker: "A", sortino_ratio: 1.90, cagr: 0.04, beta: 1.17, mdd: -0.40 },
    { ticker: "B", sortino_ratio: 1.73, cagr: 0.06, beta: 0.15, mdd: -0.19 },
    { ticker: "C", sortino_ratio: 2.37, cagr: 0.21, beta: 2.26, mdd: -0.75 },
  ]);

  assert.equal(scoreRecordFor(result, "B", "sortino_growth_beta_score").rank, 1);
  assert.equal(scoreRecordFor(result, "C", "sortino_growth_beta_quarter_score").rank, 1);
  assert.equal(scoreRecordFor(result, "A", "sortino_growth_beta_mdd_score").rank, 2);
  assert.equal(
    scoreRecordFor(result, "C", "sortino_growth_beta_quarter_score").rankDeltaVsStable,
    -1,
  );
  assert.equal(
    scoreRecordFor(result, "A", "sortino_growth_beta_mdd_score").rankDeltaVsStable,
    -1,
  );
});

test("negative Sortino remains a valid negative score", () => {
  const result = buildScoreMatrix([
    { ticker: "NEG", sortino_ratio: -1, cagr: 0.10, beta: 0.50, mdd: -0.20 },
  ]);

  for (const key of FORMULA_KEYS) {
    const record = scoreRecordFor(result, "NEG", key);
    assert.equal(record.status, "ok");
    assert.ok(record.score < 0);
    assert.equal(record.rank, 1);
  }
});

test("zero MDD is valid while invalid CAGR or Beta domains remain unranked", () => {
  const result = buildScoreMatrix([
    { ticker: "ZERO", sortino_ratio: 1, cagr: 0.10, beta: 1, mdd: 0 },
    { ticker: "BAD_CAGR", sortino_ratio: 1, cagr: -1.01, beta: 1, mdd: -0.20 },
    { ticker: "BAD_BETA", sortino_ratio: 1, cagr: 0.10, beta: -1, mdd: -0.20 },
  ]);

  const zeroStable = scoreRecordFor(result, "ZERO", "sortino_growth_beta_score");
  const zeroDrawdown = scoreRecordFor(result, "ZERO", "sortino_growth_beta_mdd_score");
  assert.equal(zeroStable.status, "ok");
  assert.equal(zeroDrawdown.status, "ok");
  assert.equal(zeroStable.score, zeroDrawdown.score);

  for (const key of FORMULA_KEYS) {
    assert.equal(scoreRecordFor(result, "BAD_CAGR", key).status, "invalid_cagr_domain");
    assert.equal(scoreRecordFor(result, "BAD_CAGR", key).rank, null);
    assert.equal(scoreRecordFor(result, "BAD_BETA", key).status, "invalid_beta_domain");
    assert.equal(scoreRecordFor(result, "BAD_BETA", key).rank, null);
  }
});

test("MDD is required only for the drawdown-aware formula", () => {
  const result = buildScoreMatrix([
    { ticker: "MISS_MDD", sortino_ratio: 1.2, cagr: 0.20, beta: 1.1, mdd: null },
  ]);

  assert.equal(
    scoreRecordFor(result, "MISS_MDD", "sortino_growth_beta_score").status,
    "ok",
  );
  assert.equal(
    scoreRecordFor(result, "MISS_MDD", "sortino_growth_beta_quarter_score").status,
    "ok",
  );
  assert.equal(
    scoreRecordFor(result, "MISS_MDD", "sortino_growth_beta_mdd_score").status,
    "missing_metrics",
  );
});

test("duplicate ticker keeps the latest scan result", () => {
  const result = buildScoreMatrix([
    { ticker: "DUP", sortino_ratio: 1, cagr: 0.10, beta: 1, mdd: -0.20 },
    { ticker: "dup", sortino_ratio: 2, cagr: 0.30, beta: 1.2, mdd: -0.20 },
  ]);
  const record = scoreRecordFor(result, "DUP", "sortino_growth_beta_score");

  assert.equal(result.total, 1);
  assert.ok(Math.abs(record.score - (2 * Math.sqrt(1.30 / 2.20))) < 1e-12);
});
