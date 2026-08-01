const TOTAL_COMBINATIONS_20_CHOOSE_10 = 184756;
const CANDIDATE_COUNT = 20;
const HOLDING_COUNT = 10;
const TRADING_DAYS_PER_YEAR = 252;
const OBJECTIVES = Object.freeze([
  "sortino_ratio",
  "cagr",
  "mdd_abs",
  "beta_abs",
  "alpha",
]);

let cancelled = false;

export function relativeBandBounds(targetWeight = 0.1, bandRatio = 0.2) {
  return {
    lower: targetWeight * (1 - bandRatio),
    upper: targetWeight * (1 + bandRatio),
  };
}

export function popcount20(value) {
  let current = value >>> 0;
  let count = 0;
  while (current) {
    current &= current - 1;
    count += 1;
  }
  return count;
}

export function enumerateCombinationMasks() {
  const output = new Uint32Array(TOTAL_COMBINATIONS_20_CHOOSE_10);
  let mask = (1 << HOLDING_COUNT) - 1;
  const limit = 1 << CANDIDATE_COUNT;
  let position = 0;
  while (mask < limit) {
    output[position] = mask >>> 0;
    position += 1;
    const smallest = mask & -mask;
    const ripple = mask + smallest;
    mask = (((ripple ^ mask) >>> 2) / smallest) | ripple;
  }
  if (position !== TOTAL_COMBINATIONS_20_CHOOSE_10) {
    throw new Error(`組合枚舉數量不正確：${position}`);
  }
  return output;
}

function xorshift32(seed) {
  let state = seed >>> 0 || 0x9e3779b9;
  return () => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return state >>> 0;
  };
}

function hashSeed(text) {
  let hash = 2166136261;
  for (const character of String(text)) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function maskIndexes(mask) {
  const indexes = [];
  for (let index = 0; index < CANDIDATE_COUNT; index += 1) {
    if (mask & (1 << index)) indexes.push(index);
  }
  return indexes;
}

function tickerList(mask, tickers) {
  return maskIndexes(mask).map((index) => tickers[index]);
}

function finiteOr(value, fallback) {
  return Number.isFinite(value) ? value : fallback;
}

function objectiveValue(record, objective) {
  switch (objective) {
    case "sortino_ratio":
      return finiteOr(record.sortino_ratio, Number.NEGATIVE_INFINITY);
    case "cagr":
      return finiteOr(record.cagr, Number.NEGATIVE_INFINITY);
    case "mdd_abs":
      return -Math.abs(finiteOr(record.mdd, Number.NEGATIVE_INFINITY));
    case "beta_abs":
      return -Math.abs(finiteOr(record.beta, Number.NEGATIVE_INFINITY));
    case "alpha":
      return finiteOr(record.alpha, Number.NEGATIVE_INFINITY);
    default:
      throw new Error(`不支援的最佳化目標：${objective}`);
  }
}

function compareRecords(left, right, objective) {
  const primary = objectiveValue(right, objective) - objectiveValue(left, objective);
  if (Math.abs(primary) > 1e-12) return primary;
  const secondaryRules = {
    sortino_ratio: ["cagr", "mdd_abs", "alpha", "beta_abs"],
    cagr: ["sortino_ratio", "mdd_abs", "alpha", "beta_abs"],
    mdd_abs: ["sortino_ratio", "cagr", "alpha", "beta_abs"],
    beta_abs: ["alpha", "sortino_ratio", "cagr", "mdd_abs"],
    alpha: ["sortino_ratio", "mdd_abs", "cagr", "beta_abs"],
  };
  for (const secondary of secondaryRules[objective]) {
    const difference = objectiveValue(right, secondary) - objectiveValue(left, secondary);
    if (Math.abs(difference) > 1e-12) return difference;
  }
  return left.mask - right.mask;
}

function mean(values) {
  let sum = 0;
  for (let index = 0; index < values.length; index += 1) sum += values[index];
  return values.length ? sum / values.length : 0;
}

function covariance(left, right, leftMean = mean(left), rightMean = mean(right)) {
  if (left.length !== right.length || left.length < 2) return 0;
  let total = 0;
  for (let index = 0; index < left.length; index += 1) {
    total += (left[index] - leftMean) * (right[index] - rightMean);
  }
  return total / (left.length - 1);
}

function buildReturns(snapshot) {
  const tickers = snapshot.candidateTickers;
  const splitIndex = Number(snapshot.split.splitIndex);
  if (!Array.isArray(tickers) || tickers.length !== CANDIDATE_COUNT) {
    throw new Error("候選池必須包含 20 檔股票。");
  }
  if (!Number.isInteger(splitIndex) || splitIndex < 3) {
    throw new Error("訓練期切割索引無效。");
  }
  const returnCount = splitIndex - 1;
  const assetReturns = tickers.map((ticker) => {
    const prices = snapshot.prices[ticker];
    const output = new Float64Array(returnCount);
    for (let index = 1; index < splitIndex; index += 1) {
      output[index - 1] = prices[index] / prices[index - 1] - 1;
    }
    return output;
  });
  const benchmarkPrices = snapshot.prices[snapshot.benchmark];
  const benchmarkReturns = new Float64Array(returnCount);
  for (let index = 1; index < splitIndex; index += 1) {
    benchmarkReturns[index - 1] = (
      benchmarkPrices[index] / benchmarkPrices[index - 1] - 1
    );
  }
  return { assetReturns, benchmarkReturns, returnCount };
}

function buildProxyContext(assetReturns, benchmarkReturns) {
  const means = new Float64Array(CANDIDATE_COUNT);
  const covarianceMatrix = Array.from(
    { length: CANDIDATE_COUNT },
    () => new Float64Array(CANDIDATE_COUNT),
  );
  const downsideCovariance = Array.from(
    { length: CANDIDATE_COUNT },
    () => new Float64Array(CANDIDATE_COUNT),
  );
  const betas = new Float64Array(CANDIDATE_COUNT);
  const benchmarkMean = mean(benchmarkReturns);
  const benchmarkVariance = covariance(
    benchmarkReturns,
    benchmarkReturns,
    benchmarkMean,
    benchmarkMean,
  );
  const downsideSeries = [];

  for (let asset = 0; asset < CANDIDATE_COUNT; asset += 1) {
    means[asset] = mean(assetReturns[asset]);
    const downside = new Float64Array(assetReturns[asset].length);
    for (let day = 0; day < downside.length; day += 1) {
      downside[day] = Math.min(assetReturns[asset][day], 0);
    }
    downsideSeries.push(downside);
    betas[asset] = benchmarkVariance > 1e-18
      ? covariance(
        assetReturns[asset],
        benchmarkReturns,
        means[asset],
        benchmarkMean,
      ) / benchmarkVariance
      : 0;
  }

  for (let left = 0; left < CANDIDATE_COUNT; left += 1) {
    for (let right = left; right < CANDIDATE_COUNT; right += 1) {
      const value = covariance(
        assetReturns[left],
        assetReturns[right],
        means[left],
        means[right],
      );
      const downsideValue = covariance(
        downsideSeries[left],
        downsideSeries[right],
      );
      covarianceMatrix[left][right] = value;
      covarianceMatrix[right][left] = value;
      downsideCovariance[left][right] = downsideValue;
      downsideCovariance[right][left] = downsideValue;
    }
  }

  return {
    means,
    covarianceMatrix,
    downsideCovariance,
    betas,
    benchmarkMean,
  };
}

function proxyMetrics(mask, context) {
  const indexes = maskIndexes(mask);
  let dailyMean = 0;
  let variance = 0;
  let downsideVariance = 0;
  let beta = 0;
  for (const left of indexes) {
    dailyMean += context.means[left] / HOLDING_COUNT;
    beta += context.betas[left] / HOLDING_COUNT;
    for (const right of indexes) {
      variance += context.covarianceMatrix[left][right] / 100;
      downsideVariance += context.downsideCovariance[left][right] / 100;
    }
  }
  const annualVolatility = Math.sqrt(Math.max(variance, 0) * TRADING_DAYS_PER_YEAR);
  const annualDownside = Math.sqrt(
    Math.max(downsideVariance, 0) * TRADING_DAYS_PER_YEAR,
  );
  const annualReturn = dailyMean * TRADING_DAYS_PER_YEAR;
  const cagr = Math.pow(Math.max(1 + dailyMean, 1e-12), TRADING_DAYS_PER_YEAR) - 1;
  const sortino = annualDownside > 1e-18 ? annualReturn / annualDownside : 0;
  const alpha = (
    dailyMean - beta * context.benchmarkMean
  ) * TRADING_DAYS_PER_YEAR;
  const mddProxy = -Math.min(
    0.99,
    Math.max(annualVolatility * 1.75, annualDownside * 2.25),
  );
  return {
    mask,
    sortino_ratio: sortino,
    cagr,
    mdd: mddProxy,
    beta,
    alpha,
    volatility: annualVolatility,
  };
}

async function enumerateProxyRecords(context, progress) {
  const masks = enumerateCombinationMasks();
  const records = new Array(masks.length);
  const indexByMask = new Int32Array(1 << CANDIDATE_COUNT);
  indexByMask.fill(-1);
  for (let index = 0; index < masks.length; index += 1) {
    const mask = masks[index];
    records[index] = proxyMetrics(mask, context);
    indexByMask[mask] = index;
    if (index % 5000 === 0) {
      progress("proxy", index, masks.length);
      await new Promise((resolve) => setTimeout(resolve, 0));
      if (cancelled) throw new Error("最佳化已取消。");
    }
  }
  progress("proxy", masks.length, masks.length);
  return { records, indexByMask };
}

function sortedIndexes(records, objective) {
  return Array.from({ length: records.length }, (_, index) => index)
    .sort((left, right) => compareRecords(
      records[left],
      records[right],
      objective,
    ));
}

function oneSwapNeighbors(mask) {
  const inside = maskIndexes(mask);
  const outside = [];
  for (let index = 0; index < CANDIDATE_COUNT; index += 1) {
    if (!(mask & (1 << index))) outside.push(index);
  }
  const output = [];
  for (const remove of inside) {
    for (const add of outside) {
      output.push((mask ^ (1 << remove) ^ (1 << add)) >>> 0);
    }
  }
  return output;
}

function sampledTwoSwapNeighbors(mask, random, limit = 160) {
  const inside = maskIndexes(mask);
  const outside = [];
  for (let index = 0; index < CANDIDATE_COUNT; index += 1) {
    if (!(mask & (1 << index))) outside.push(index);
  }
  const output = new Set();
  while (output.size < limit) {
    const leftA = random() % inside.length;
    let leftB = random() % inside.length;
    if (leftB === leftA) leftB = (leftB + 1) % inside.length;
    const rightA = random() % outside.length;
    let rightB = random() % outside.length;
    if (rightB === rightA) rightB = (rightB + 1) % outside.length;
    const next = (
      mask
      ^ (1 << inside[leftA])
      ^ (1 << inside[leftB])
      ^ (1 << outside[rightA])
      ^ (1 << outside[rightB])
    ) >>> 0;
    output.add(next);
  }
  return [...output];
}

function hillClimb({
  seedIndex,
  objective,
  records,
  indexByMask,
  selected,
  trace,
  random,
}) {
  let currentIndex = seedIndex;
  for (let step = 0; step < 30; step += 1) {
    const current = records[currentIndex];
    let bestIndex = currentIndex;
    for (const neighborMask of oneSwapNeighbors(current.mask)) {
      const neighborIndex = indexByMask[neighborMask];
      if (neighborIndex < 0) continue;
      if (
        compareRecords(
          records[neighborIndex],
          records[bestIndex],
          objective,
        ) < 0
      ) {
        bestIndex = neighborIndex;
      }
    }
    if (bestIndex === currentIndex) {
      for (const neighborMask of sampledTwoSwapNeighbors(current.mask, random)) {
        const neighborIndex = indexByMask[neighborMask];
        if (neighborIndex < 0) continue;
        if (
          compareRecords(
            records[neighborIndex],
            records[bestIndex],
            objective,
          ) < 0
        ) {
          bestIndex = neighborIndex;
        }
      }
    }
    if (bestIndex === currentIndex) break;
    selected.add(records[bestIndex].mask);
    trace.push({
      objective,
      step,
      fromMask: current.mask,
      toMask: records[bestIndex].mask,
    });
    currentIndex = bestIndex;
  }
  return currentIndex;
}

function hammingDistance(left, right) {
  return popcount20((left ^ right) >>> 0);
}

function addDiversity({ selected, masks, target, random, anchors }) {
  let attempts = 0;
  while (selected.size < target && attempts < masks.length * 4) {
    const candidate = masks[random() % masks.length];
    attempts += 1;
    if (selected.has(candidate)) continue;
    let minimumDistance = HOLDING_COUNT * 2;
    for (const anchor of anchors) {
      minimumDistance = Math.min(minimumDistance, hammingDistance(candidate, anchor));
    }
    if (minimumDistance >= 6 || attempts > masks.length * 2) {
      selected.add(candidate);
      if (anchors.length < 100) anchors.push(candidate);
    }
  }
}

function searchBudgetPlan(primaryObjective, searchBudget) {
  const primaryQuota = Math.floor(searchBudget * 0.50);
  const secondaryQuota = Math.floor(searchBudget * 0.10);
  const requested = Object.fromEntries(
    OBJECTIVES.map((objective) => [
      objective,
      objective === primaryObjective ? primaryQuota : secondaryQuota,
    ]),
  );
  requested.pareto_diversity = (
    searchBudget
    - primaryQuota
    - secondaryQuota * (OBJECTIVES.length - 1)
  );
  return requested;
}

function selectDeepMasks({
  records,
  indexByMask,
  primaryObjective,
  searchBudget,
  seedText,
}) {
  const rankings = Object.fromEntries(
    OBJECTIVES.map((objective) => [objective, sortedIndexes(records, objective)]),
  );
  const selected = new Set();
  const trace = [];
  const random = xorshift32(hashSeed(seedText));
  const requested = searchBudgetPlan(primaryObjective, searchBudget);
  const actual = Object.fromEntries(
    [...OBJECTIVES, "pareto_diversity"].map((key) => [key, 0]),
  );
  const objectiveOrder = [
    primaryObjective,
    ...OBJECTIVES.filter((objective) => objective !== primaryObjective),
  ];

  for (const objective of objectiveOrder) {
    const ranking = rankings[objective];
    const localCandidates = new Set();
    const seedCount = objective === primaryObjective ? 80 : 30;
    for (let seed = 0; seed < seedCount; seed += 1) {
      const seedIndex = ranking[seed];
      localCandidates.add(records[seedIndex].mask);
      hillClimb({
        seedIndex,
        objective,
        records,
        indexByMask,
        selected: localCandidates,
        trace,
        random,
      });
    }

    const addForObjective = (mask) => {
      if (actual[objective] >= requested[objective] || selected.has(mask)) return;
      selected.add(mask);
      actual[objective] += 1;
    };
    for (const mask of localCandidates) addForObjective(mask);
    for (const recordIndex of ranking) {
      addForObjective(records[recordIndex].mask);
      if (actual[objective] >= requested[objective]) break;
    }
    if (actual[objective] !== requested[objective]) {
      throw new Error(
        `無法滿足 ${objective} 搜尋配額：${actual[objective]} / ${requested[objective]}`,
      );
    }
  }

  const masks = records.map((record) => record.mask);
  const anchors = OBJECTIVES.flatMap(
    (objective) => rankings[objective].slice(0, 5).map((index) => records[index].mask),
  );
  const diversityStart = selected.size;
  addDiversity({
    selected,
    masks,
    target: diversityStart + requested.pareto_diversity,
    random,
    anchors,
  });
  if (selected.size < searchBudget) {
    for (const mask of masks) {
      selected.add(mask);
      if (selected.size >= searchBudget) break;
    }
  }
  actual.pareto_diversity = selected.size - diversityStart;
  if (
    selected.size !== searchBudget
    || actual.pareto_diversity !== requested.pareto_diversity
  ) {
    throw new Error(
      `無法滿足 Pareto／多樣性配額：${actual.pareto_diversity} / ${requested.pareto_diversity}`,
    );
  }

  return {
    masks: Uint32Array.from(selected),
    trace,
    allocation: { requested, actual },
  };
}

function buildSubsetSums(assetReturns, startAsset, assetCount) {
  const days = assetReturns[0].length;
  const subsetCount = 1 << assetCount;
  const output = new Float32Array(subsetCount * days);
  for (let subset = 1; subset < subsetCount; subset += 1) {
    const leastBit = subset & -subset;
    const bitIndex = 31 - Math.clz32(leastBit);
    const previous = subset ^ leastBit;
    const asset = startAsset + bitIndex;
    const base = subset * days;
    const previousBase = previous * days;
    const returns = assetReturns[asset];
    for (let day = 0; day < days; day += 1) {
      output[base + day] = output[previousBase + day] + returns[day];
    }
  }
  return { values: output, days };
}

function exactEqualWeightMetrics({
  mask,
  leftSums,
  rightSums,
  benchmarkReturns,
  elapsedYears,
}) {
  const days = leftSums.days;
  const leftMask = mask & 0x3ff;
  const rightMask = (mask >>> 10) & 0x3ff;
  const leftOffset = leftMask * days;
  const rightOffset = rightMask * days;
  let nav = 1;
  let peak = 1;
  let mdd = 0;
  let sum = 0;
  let sumSquares = 0;
  let downsideSquares = 0;
  let benchmarkSum = 0;
  let benchmarkSquares = 0;
  let crossSum = 0;

  for (let day = 0; day < days; day += 1) {
    const value = (
      leftSums.values[leftOffset + day]
      + rightSums.values[rightOffset + day]
    ) / HOLDING_COUNT;
    const benchmark = benchmarkReturns[day];
    nav *= 1 + value;
    peak = Math.max(peak, nav);
    mdd = Math.min(mdd, nav / peak - 1);
    sum += value;
    sumSquares += value * value;
    downsideSquares += Math.min(value, 0) ** 2;
    benchmarkSum += benchmark;
    benchmarkSquares += benchmark * benchmark;
    crossSum += value * benchmark;
  }

  const dailyMean = sum / days;
  const variance = Math.max(
    (sumSquares - days * dailyMean * dailyMean) / Math.max(days - 1, 1),
    0,
  );
  const benchmarkMean = benchmarkSum / days;
  const benchmarkVariance = Math.max(
    (benchmarkSquares - days * benchmarkMean * benchmarkMean) / Math.max(days - 1, 1),
    0,
  );
  const covarianceValue = (
    crossSum - days * dailyMean * benchmarkMean
  ) / Math.max(days - 1, 1);
  const beta = benchmarkVariance > 1e-18 ? covarianceValue / benchmarkVariance : 0;
  const annualReturn = dailyMean * TRADING_DAYS_PER_YEAR;
  const downsideDeviation = Math.sqrt(
    (downsideSquares / days) * TRADING_DAYS_PER_YEAR,
  );
  return {
    mask,
    total_return: nav - 1,
    cagr: elapsedYears > 0 ? Math.pow(nav, 1 / elapsedYears) - 1 : 0,
    mdd,
    volatility: Math.sqrt(variance * TRADING_DAYS_PER_YEAR),
    sortino_ratio: downsideDeviation > 1e-18 ? annualReturn / downsideDeviation : 0,
    beta,
    alpha: (dailyMean - beta * benchmarkMean) * TRADING_DAYS_PER_YEAR,
  };
}

async function deepEvaluate({ masks, assetReturns, benchmarkReturns, trainingDates, progress }) {
  const leftSums = buildSubsetSums(assetReturns, 0, 10);
  const rightSums = buildSubsetSums(assetReturns, 10, 10);
  const elapsedYears = Math.max(
    (new Date(trainingDates.at(-1)).getTime() - new Date(trainingDates[0]).getTime())
      / (365.25 * 24 * 60 * 60 * 1000),
    1 / 365.25,
  );
  const records = new Array(masks.length);
  for (let index = 0; index < masks.length; index += 1) {
    records[index] = exactEqualWeightMetrics({
      mask: masks[index],
      leftSums,
      rightSums,
      benchmarkReturns,
      elapsedYears,
    });
    if (index % 500 === 0) {
      progress("deep", index, masks.length);
      await new Promise((resolve) => setTimeout(resolve, 0));
      if (cancelled) throw new Error("最佳化已取消。");
    }
  }
  progress("deep", masks.length, masks.length);
  return records;
}

function dominates(left, right) {
  const leftValues = [
    left.sortino_ratio,
    left.cagr,
    left.alpha,
    -Math.abs(left.mdd),
    -Math.abs(left.beta),
  ];
  const rightValues = [
    right.sortino_ratio,
    right.cagr,
    right.alpha,
    -Math.abs(right.mdd),
    -Math.abs(right.beta),
  ];
  let strictlyBetter = false;
  for (let index = 0; index < leftValues.length; index += 1) {
    if (leftValues[index] < rightValues[index] - 1e-12) return false;
    if (leftValues[index] > rightValues[index] + 1e-12) strictlyBetter = true;
  }
  return strictlyBetter;
}

function approximatePareto(records) {
  const candidateMasks = new Set();
  for (const objective of OBJECTIVES) {
    const sorted = [...records].sort(
      (left, right) => compareRecords(left, right, objective),
    );
    sorted.slice(0, 500).forEach((record) => candidateMasks.add(record.mask));
  }
  const candidates = records.filter((record) => candidateMasks.has(record.mask));
  return candidates.filter((candidate, index) => (
    !candidates.some((other, otherIndex) => (
      otherIndex !== index && dominates(other, candidate)
    ))
  ));
}

function addUniqueRanked(output, seen, records, count, source, objective) {
  let added = 0;
  const sorted = [...records].sort(
    (left, right) => compareRecords(left, right, objective),
  );
  for (const record of sorted) {
    if (added >= count) break;
    if (seen.has(record.mask)) continue;
    seen.add(record.mask);
    output.push({ ...record, selectionSource: source });
    added += 1;
  }
}

function selectVerificationRecords(records, primaryObjective) {
  const output = [];
  const seen = new Set();
  addUniqueRanked(
    output,
    seen,
    records,
    120,
    `primary:${primaryObjective}`,
    primaryObjective,
  );
  for (const objective of OBJECTIVES) {
    if (objective === primaryObjective) continue;
    addUniqueRanked(output, seen, records, 30, `secondary:${objective}`, objective);
  }

  const pareto = approximatePareto(records);
  const anchors = output.slice(0, 20).map((record) => record.mask);
  pareto.sort((left, right) => {
    const leftDistance = Math.min(
      ...anchors.map((anchor) => hammingDistance(left.mask, anchor)),
    );
    const rightDistance = Math.min(
      ...anchors.map((anchor) => hammingDistance(right.mask, anchor)),
    );
    return rightDistance - leftDistance || left.mask - right.mask;
  });
  for (const record of pareto) {
    if (output.length >= 300) break;
    if (seen.has(record.mask)) continue;
    seen.add(record.mask);
    output.push({ ...record, selectionSource: "pareto-diversity" });
  }
  if (output.length < 300) {
    addUniqueRanked(
      output,
      seen,
      records,
      300 - output.length,
      "pareto-fill",
      primaryObjective,
    );
  }
  return output.slice(0, 300);
}

export function serializeMasksLittleEndian(masks) {
  const bytes = new Uint8Array(masks.length * 4);
  const view = new DataView(bytes.buffer);
  for (let index = 0; index < masks.length; index += 1) {
    view.setUint32(index * 4, masks[index], true);
  }
  return bytes;
}

async function digestMasks(masks) {
  const bytes = serializeMasksLittleEndian(masks);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

export async function optimizeSnapshot({ snapshot, settings, progress = () => {} }) {
  cancelled = false;
  const primaryObjective = settings.primaryObjective || "sortino_ratio";
  if (!OBJECTIVES.includes(primaryObjective)) {
    throw new Error("主要最佳化目標無效。");
  }
  const searchBudget = Math.min(
    Math.max(Number(settings.searchBudget) || 30000, 1000),
    TOTAL_COMBINATIONS_20_CHOOSE_10,
  );
  const { assetReturns, benchmarkReturns } = buildReturns(snapshot);
  const context = buildProxyContext(assetReturns, benchmarkReturns);
  const { records: proxyRecords, indexByMask } = await enumerateProxyRecords(
    context,
    progress,
  );
  const seedText = [
    snapshot.optimizerAlgorithmVersion,
    snapshot.metricDefinitionVersion,
    snapshot.candidateTickers.join(","),
    snapshot.split.trainingStart,
    snapshot.split.trainingEnd,
    primaryObjective,
    searchBudget,
  ].join("|");
  const selection = selectDeepMasks({
    records: proxyRecords,
    indexByMask,
    primaryObjective,
    searchBudget,
    seedText,
  });
  progress("selected", selection.masks.length, searchBudget);
  const trainingDates = snapshot.dates.slice(0, snapshot.split.splitIndex);
  const deepRecords = await deepEvaluate({
    masks: selection.masks,
    assetReturns,
    benchmarkReturns,
    trainingDates,
    progress,
  });
  const verificationRecords = selectVerificationRecords(deepRecords, primaryObjective);
  const evaluatedMaskHash = await digestMasks(selection.masks);
  return {
    combinations: verificationRecords.map((record, index) => ({
      combinationId: `optimizer-${String(index + 1).padStart(3, "0")}`,
      mask: record.mask,
      tickers: tickerList(record.mask, snapshot.candidateTickers),
      selectionSource: record.selectionSource,
      approximateTrainingMetrics: {
        cagr: record.cagr,
        sortino_ratio: record.sortino_ratio,
        mdd: record.mdd,
        beta: record.beta,
        alpha: record.alpha,
      },
    })),
    search: {
      optimizerAlgorithmVersion: snapshot.optimizerAlgorithmVersion,
      primaryObjective,
      proxyCombinationCount: TOTAL_COMBINATIONS_20_CHOOSE_10,
      deepCombinationCount: selection.masks.length,
      exactVerificationCount: verificationRecords.length,
      requestedSearchBudget: searchBudget,
      evaluatedMaskHash,
      randomSeed: hashSeed(seedText),
      budgetAllocation: selection.allocation,
      localSearchTrace: selection.trace,
      evaluatedMasks: Array.from(selection.masks),
      stopReason: selection.masks.length >= searchBudget
        ? "search_budget_reached"
        : "combination_space_exhausted",
    },
  };
}

async function handleWorkerMessage(event) {
  const message = event.data || {};
  if (message.type === "cancel") {
    cancelled = true;
    return;
  }
  if (message.type !== "optimize") return;
  try {
    const result = await optimizeSnapshot({
      snapshot: message.snapshot,
      settings: message.settings || {},
      progress(stage, completed, total) {
        postMessage({ type: "progress", stage, completed, total });
      },
    });
    postMessage({ type: "complete", result });
  } catch (error) {
    postMessage({
      type: "error",
      error: error instanceof Error ? error.message : String(error),
    });
  }
}

if (typeof self !== "undefined" && typeof self.addEventListener === "function") {
  self.addEventListener("message", handleWorkerMessage);
}
