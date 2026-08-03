/**
 * Streaming result retention for the 50-million-combination exhaustive engine.
 *
 * Every combination is still evaluated.  This module retains only enough rank
 * identifiers to later materialize a compact, sortable result set.  It avoids
 * writing every intermediate combination to IndexedDB and deliberately stores
 * no JavaScript objects per result.
 */

export const MAX_EXHAUSTIVE_COMBINATIONS = 50_000_000;
export const MAX_PERSISTED_RESULTS = 5_000_000;
export const COMPACT_RESULT_METRIC_COUNT = 14;
export const COMPACT_RESULT_BYTES_PER_ROW = 4 + (COMPACT_RESULT_METRIC_COUNT * 4) + 1;
export const RETENTION_METRIC_KEYS = Object.freeze([
  "optimized_score",
  "stable_score",
  "growth_score",
  "drawdown_score",
  "sortino_ratio",
  "cagr",
  "mdd",
]);

export const RETENTION_REASON = Object.freeze({
  primary: 1,
  stable: 2,
  growth: 4,
  drawdown: 8,
  sortino: 16,
  cagr: 32,
  mdd: 64,
  diversity: 128,
});

const SECONDARY_SPECS = Object.freeze([
  { key: "stable_score", reason: RETENTION_REASON.stable },
  { key: "growth_score", reason: RETENTION_REASON.growth },
  { key: "drawdown_score", reason: RETENTION_REASON.drawdown },
  { key: "sortino_ratio", reason: RETENTION_REASON.sortino },
  { key: "cagr", reason: RETENTION_REASON.cagr },
  { key: "mdd", reason: RETENTION_REASON.mdd },
]);

function boundedInteger(value, fallback) {
  const numeric = Number(value);
  return Number.isInteger(numeric) && numeric > 0 ? numeric : fallback;
}

/**
 * Build the default 60/30/10 retention plan.
 *
 * The primary buffer keeps a full `target` candidates rather than only 60%.
 * That rank-only reserve fills places released by overlaps between score
 * leaders, so the final set can still reach the requested maximum.
 */
export function createRetentionPlan(totalCombinations, options = {}) {
  const total = boundedInteger(totalCombinations, 0);
  if (!total || total > MAX_EXHAUSTIVE_COMBINATIONS) {
    throw new RangeError("完整組合數必須介於 1 與 50,000,000 之間。");
  }
  const maxPersisted = Math.min(
    total,
    boundedInteger(options.maxPersisted, MAX_PERSISTED_RESULTS),
  );
  const primaryFraction = Number.isFinite(options.primaryFraction)
    ? Number(options.primaryFraction)
    : 0.60;
  const secondaryFraction = Number.isFinite(options.secondaryFraction)
    ? Number(options.secondaryFraction)
    : 0.30;
  if (primaryFraction <= 0 || secondaryFraction < 0 || primaryFraction + secondaryFraction > 1) {
    throw new RangeError("結果保留比例無效。");
  }
  const secondarySpecs = options.secondarySpecs || SECONDARY_SPECS;
  const primaryGuaranteed = Math.floor(maxPersisted * primaryFraction);
  const secondaryBudget = Math.floor(maxPersisted * secondaryFraction);
  const secondaryEach = secondarySpecs.length
    ? Math.floor(secondaryBudget / secondarySpecs.length)
    : 0;
  const diversityBudget = maxPersisted - primaryGuaranteed - (secondaryEach * secondarySpecs.length);

  return Object.freeze({
    total,
    target: maxPersisted,
    primaryGuaranteed,
    primaryCapacity: maxPersisted,
    secondary: secondarySpecs.map((spec) => Object.freeze({
      key: spec.key,
      reason: spec.reason,
      capacity: secondaryEach,
    })),
    diversityCapacity: diversityBudget,
  });
}

/** Estimate durable storage after selected rows are materialized as Float32. */
export function estimateCompactResultBytes(retainedRows) {
  const rows = Math.max(0, Math.floor(Number(retainedRows) || 0));
  const chunkCount = Math.ceil(rows / 50_000);
  return (rows * COMPACT_RESULT_BYTES_PER_ROW) + (chunkCount * 1024);
}

/** Estimate transient rank/score buffers used while all combinations run. */
export function estimateRetentionWorkingBytes(plan) {
  const bufferEntries = plan.primaryCapacity
    + plan.diversityCapacity
    + plan.secondary.reduce((sum, item) => sum + item.capacity, 0);
  const rankAndScoreBytes = bufferEntries * (Uint32Array.BYTES_PER_ELEMENT + Float64Array.BYTES_PER_ELEMENT);
  const membershipBytes = Math.ceil(plan.total / 8);
  const finalizedRankBytes = plan.target * (Uint32Array.BYTES_PER_ELEMENT + Uint8Array.BYTES_PER_ELEMENT);
  return rankAndScoreBytes + membershipBytes + finalizedRankBytes;
}

/**
 * A fixed-size min-heap of rank/score pairs.  Scores are typed arrays, so a
 * 5-million-rank reserve does not create millions of GC-tracked objects.
 */
export class TopRankBuffer {
  constructor(capacity) {
    this.capacity = Math.max(0, Math.floor(Number(capacity) || 0));
    this.ranks = new Uint32Array(this.capacity);
    this.scores = new Float64Array(this.capacity);
    this.count = 0;
    this.heapified = this.capacity === 0;
  }

  offer(rankValue, scoreValue) {
    if (!this.capacity) return false;
    const rank = Number(rankValue);
    if (!Number.isInteger(rank) || rank < 0 || rank > 0xffff_ffff) {
      throw new RangeError("組合 rank 必須為可表示的非負整數。");
    }
    const score = Number.isFinite(scoreValue) ? Number(scoreValue) : Number.NEGATIVE_INFINITY;
    if (this.count < this.capacity) {
      this.ranks[this.count] = rank;
      this.scores[this.count] = score;
      this.count += 1;
      if (this.count === this.capacity) this.#heapify();
      return true;
    }
    if (score <= this.scores[0]) return false;
    this.ranks[0] = rank;
    this.scores[0] = score;
    this.#siftDown(0);
    return true;
  }

  ranksDescending(limit = this.count) {
    const length = Math.min(this.count, Math.max(0, Math.floor(Number(limit) || 0)));
    const positions = new Uint32Array(this.count);
    for (let index = 0; index < this.count; index += 1) positions[index] = index;
    positions.sort((left, right) => {
      const leftScore = this.scores[left];
      const rightScore = this.scores[right];
      if (leftScore !== rightScore) return rightScore > leftScore ? 1 : -1;
      return this.ranks[left] - this.ranks[right];
    });
    const result = new Uint32Array(length);
    for (let index = 0; index < length; index += 1) result[index] = this.ranks[positions[index]];
    return result;
  }

  ranksUnordered() {
    return this.ranks.slice(0, this.count);
  }

  toState() {
    return {
      capacity: this.capacity,
      count: this.count,
      ranks: this.ranks.slice(0, this.count),
      scores: this.scores.slice(0, this.count),
    };
  }

  static fromState(state) {
    const capacity = Math.max(0, Math.floor(Number(state?.capacity) || 0));
    const count = Math.max(0, Math.floor(Number(state?.count) || 0));
    if (count > capacity) throw new RangeError("保留緩衝區狀態無效。");
    const ranks = state?.ranks instanceof Uint32Array ? state.ranks : Uint32Array.from(state?.ranks || []);
    const scores = state?.scores instanceof Float64Array ? state.scores : Float64Array.from(state?.scores || []);
    if (ranks.length !== count || scores.length !== count) {
      throw new RangeError("保留緩衝區狀態長度無效。");
    }
    const buffer = new TopRankBuffer(capacity);
    buffer.ranks.set(ranks);
    buffer.scores.set(scores);
    buffer.count = count;
    buffer.heapified = count === capacity;
    return buffer;
  }

  #heapify() {
    for (let index = Math.floor(this.count / 2) - 1; index >= 0; index -= 1) {
      this.#siftDown(index);
    }
    this.heapified = true;
  }

  #siftDown(root) {
    let index = root;
    while (true) {
      const left = (index * 2) + 1;
      const right = left + 1;
      let smallest = index;
      if (left < this.count && this.scores[left] < this.scores[smallest]) smallest = left;
      if (right < this.count && this.scores[right] < this.scores[smallest]) smallest = right;
      if (smallest === index) return;
      this.#swap(index, smallest);
      index = smallest;
    }
  }

  #swap(left, right) {
    const score = this.scores[left];
    this.scores[left] = this.scores[right];
    this.scores[right] = score;
    const rank = this.ranks[left];
    this.ranks[left] = this.ranks[right];
    this.ranks[right] = rank;
  }
}

/**
 * Collect rank-only candidates while worker chunks stream through the main
 * thread.  Selected ranks are materialized in a second, bounded parallel pass
 * once all 50M calculations finish, which avoids a multi-gigabyte raw result
 * database and preserves Float64 calculation accuracy for the final rows.
 */
export class CompactResultRetention {
  constructor(totalCombinations, options = {}) {
    this.plan = createRetentionPlan(totalCombinations, options);
    this.primary = new TopRankBuffer(this.plan.primaryCapacity);
    this.secondary = this.plan.secondary.map((spec) => ({
      ...spec,
      buffer: new TopRankBuffer(spec.capacity),
    }));
    this.diversity = new TopRankBuffer(this.plan.diversityCapacity);
    this.accepted = 0;
  }

  accept(rank, metrics) {
    if (rank < 0 || rank >= this.plan.total) throw new RangeError("組合 rank 超出工作範圍。");
    const values = metrics || {};
    this.primary.offer(rank, values.optimized_score);
    for (const item of this.secondary) {
      item.buffer.offer(rank, retentionScore(item.key, values[item.key]));
    }
    this.diversity.offer(rank, deterministicRankHash(rank));
    this.accepted += 1;
  }

  acceptMetricArray(startRank, metrics, metricKeys) {
    const keys = metricKeys || [];
    const width = keys.length;
    if (!width || metrics.length % width) throw new RangeError("指標陣列長度無法對齊。");
    const keyIndexes = new Map(keys.map((key, index) => [key, index]));
    const primaryIndex = keyIndexes.get("optimized_score");
    const secondaryIndexes = this.secondary.map((item) => keyIndexes.get(item.key));
    if (primaryIndex == null || secondaryIndexes.some((index) => index == null)) {
      throw new RangeError("指標陣列缺少結果保留所需欄位。");
    }
    for (let row = 0; row < metrics.length / width; row += 1) {
      const offset = row * width;
      const rank = Number(startRank) + row;
      if (rank < 0 || rank >= this.plan.total) throw new RangeError("組合 rank 超出工作範圍。");
      this.primary.offer(rank, metrics[offset + primaryIndex]);
      for (let index = 0; index < this.secondary.length; index += 1) {
        const metricIndex = secondaryIndexes[index];
        this.secondary[index].buffer.offer(
          rank,
          retentionScore(this.secondary[index].key, metrics[offset + metricIndex]),
        );
      }
      this.diversity.offer(rank, deterministicRankHash(rank));
      this.accepted += 1;
    }
  }

  finalize() {
    const membership = new Uint8Array(Math.ceil(this.plan.total / 8));
    const ranks = new Uint32Array(this.plan.target);
    const reasons = new Uint8Array(this.plan.target);
    let count = 0;
    const add = (rank, reason) => {
      if (count >= this.plan.target) return;
      const byte = rank >>> 3;
      const bit = 1 << (rank & 7);
      if (membership[byte] & bit) return;
      membership[byte] |= bit;
      ranks[count] = rank;
      reasons[count] = reason;
      count += 1;
    };

    const primaryRanks = this.primary.ranksDescending();
    for (let index = 0; index < this.plan.primaryGuaranteed; index += 1) {
      if (index >= primaryRanks.length) break;
      add(primaryRanks[index], RETENTION_REASON.primary);
    }
    for (const item of this.secondary) {
      const selected = item.buffer.ranksDescending();
      for (const rank of selected) add(rank, item.reason);
    }
    for (const rank of this.diversity.ranksUnordered()) add(rank, RETENTION_REASON.diversity);
    for (const rank of primaryRanks) add(rank, RETENTION_REASON.primary);

    return Object.freeze({
      totalComputed: this.accepted,
      target: this.plan.target,
      ranks: ranks.slice(0, count),
      reasons: reasons.slice(0, count),
      plan: this.plan,
    });
  }

  toState() {
    return {
      plan: this.plan,
      accepted: this.accepted,
      primary: this.primary.toState(),
      secondary: this.secondary.map((item) => ({
        key: item.key,
        reason: item.reason,
        capacity: item.capacity,
        buffer: item.buffer.toState(),
      })),
      diversity: this.diversity.toState(),
    };
  }

  static fromState(state) {
    const plan = state?.plan;
    if (!plan || !Number.isInteger(plan.total) || !Number.isInteger(plan.target)) {
      throw new RangeError("結果保留檢查點無效。");
    }
    const output = Object.create(CompactResultRetention.prototype);
    output.plan = plan;
    output.primary = TopRankBuffer.fromState(state.primary);
    output.secondary = (state.secondary || []).map((item) => ({
      key: item.key,
      reason: item.reason,
      capacity: item.capacity,
      buffer: TopRankBuffer.fromState(item.buffer),
    }));
    output.diversity = TopRankBuffer.fromState(state.diversity);
    output.accepted = Math.max(0, Math.floor(Number(state.accepted) || 0));
    if (output.primary.capacity !== plan.primaryCapacity || output.diversity.capacity !== plan.diversityCapacity) {
      throw new RangeError("結果保留檢查點容量不符。");
    }
    if (output.secondary.length !== plan.secondary.length || output.secondary.some((item, index) => (
      item.key !== plan.secondary[index].key
      || item.reason !== plan.secondary[index].reason
      || item.capacity !== plan.secondary[index].capacity
    ))) {
      throw new RangeError("結果保留檢查點指標不符。");
    }
    return output;
  }
}

export function retentionScore(key, value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return Number.NEGATIVE_INFINITY;
  return key === "mdd" ? -Math.abs(numeric) : numeric;
}

/** A reproducible uniform rank score; high values form the diversity sample. */
export function deterministicRankHash(rankValue) {
  let value = Number(rankValue) >>> 0;
  value = Math.imul(value ^ (value >>> 16), 0x45d9f3b);
  value = Math.imul(value ^ (value >>> 16), 0x45d9f3b);
  return (value ^ (value >>> 16)) >>> 0;
}
