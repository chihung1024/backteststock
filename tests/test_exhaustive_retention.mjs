import assert from "node:assert/strict";
import test from "node:test";

import {
  CompactResultRetention,
  MAX_EXHAUSTIVE_COMBINATIONS,
  MAX_PERSISTED_RESULTS,
  RETENTION_REASON,
  TopRankBuffer,
  createRetentionPlan,
  deterministicRankHash,
  estimateCompactResultBytes,
  estimateRetentionWorkingBytes,
} from "../public/exhaustive-retention.js";

test("50M plan reserves compact storage rather than raw result storage", () => {
  const plan = createRetentionPlan(MAX_EXHAUSTIVE_COMBINATIONS);
  assert.equal(plan.target, MAX_PERSISTED_RESULTS);
  assert.equal(plan.primaryGuaranteed, 3_000_000);
  assert.equal(plan.primaryCapacity, 5_000_000);
  assert.equal(plan.secondary.length, 6);
  assert.ok(plan.secondary.every((item) => item.capacity === 250_000));
  assert.equal(plan.diversityCapacity, 500_000);
  assert.ok(estimateCompactResultBytes(plan.target) < 310_000_000);
  assert.ok(estimateRetentionWorkingBytes(plan) < 130_000_000);
  assert.equal(
    createRetentionPlan(MAX_EXHAUSTIVE_COMBINATIONS, { maxPersisted: 9_000_000 }).target,
    MAX_PERSISTED_RESULTS,
  );
});

test("top-rank buffer retains only the highest deterministic scores", () => {
  const buffer = new TopRankBuffer(3);
  for (const [rank, score] of [[0, 1], [1, 6], [2, 2], [3, 8], [4, 7]]) {
    buffer.offer(rank, score);
  }
  assert.deepEqual([...buffer.ranksDescending()], [3, 4, 1]);
});

test("top-rank ties retain the same lowest ranks regardless of arrival order", () => {
  const ascending = new TopRankBuffer(3);
  const descending = new TopRankBuffer(3);
  for (const rank of [0, 1, 2, 3, 4, 5]) ascending.offer(rank, 7);
  for (const rank of [5, 4, 3, 2, 1, 0]) descending.offer(rank, 7);

  assert.deepEqual([...ascending.ranksDescending()], [0, 1, 2]);
  assert.deepEqual([...descending.ranksDescending()], [0, 1, 2]);
});

test("retention keeps primary leaders, secondary outliers, diversity, and no duplicates", () => {
  const retention = new CompactResultRetention(10, {
    maxPersisted: 5,
    secondarySpecs: [{ key: "stable_score", reason: RETENTION_REASON.stable }],
    primaryFraction: 0.60,
    secondaryFraction: 0.20,
  });
  for (let rank = 0; rank < 10; rank += 1) {
    retention.accept(rank, {
      optimized_score: rank,
      stable_score: rank === 0 ? 100 : rank,
    });
  }

  const result = retention.finalize();
  assert.equal(result.totalComputed, 10);
  assert.equal(result.ranks.length, 5);
  assert.equal(new Set(result.ranks).size, 5);
  assert.ok(result.ranks.includes(9));
  assert.ok(result.ranks.includes(8));
  assert.ok(result.ranks.includes(0));
  assert.equal(result.reasons[0], RETENTION_REASON.primary);
});

test("invalid score values do not prevent a complete bounded retained set", () => {
  const retention = new CompactResultRetention(8, { maxPersisted: 5 });
  for (let rank = 0; rank < 8; rank += 1) {
    retention.accept(rank, { optimized_score: Number.NaN });
  }
  const result = retention.finalize();
  assert.equal(result.ranks.length, 5);
  assert.equal(new Set(result.ranks).size, 5);
});

test("a compact retention checkpoint restores the exact candidate set", () => {
  const original = new CompactResultRetention(20, { maxPersisted: 8 });
  for (let rank = 0; rank < 12; rank += 1) {
    original.accept(rank, {
      optimized_score: rank % 5,
      stable_score: rank,
      growth_score: rank / 2,
      drawdown_score: rank / 3,
      sortino_ratio: rank / 4,
      cagr: rank / 100,
      mdd: -rank / 100,
    });
  }
  const restored = CompactResultRetention.fromState(original.toState());
  for (let rank = 12; rank < 20; rank += 1) {
    restored.accept(rank, {
      optimized_score: rank % 5,
      stable_score: rank,
      growth_score: rank / 2,
      drawdown_score: rank / 3,
      sortino_ratio: rank / 4,
      cagr: rank / 100,
      mdd: -rank / 100,
    });
  }
  const expected = new CompactResultRetention(20, { maxPersisted: 8 });
  for (let rank = 0; rank < 20; rank += 1) {
    expected.accept(rank, {
      optimized_score: rank % 5,
      stable_score: rank,
      growth_score: rank / 2,
      drawdown_score: rank / 3,
      sortino_ratio: rank / 4,
      cagr: rank / 100,
      mdd: -rank / 100,
    });
  }
  assert.deepEqual([...restored.finalize().ranks], [...expected.finalize().ranks]);
});

test("rank diversity hash is reproducible and differentiates ordinary ranks", () => {
  assert.equal(deterministicRankHash(42), deterministicRankHash(42));
  assert.notEqual(deterministicRankHash(42), deterministicRankHash(43));
});
