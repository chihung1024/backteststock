const OBJECTIVES = Object.freeze([
  "sortino_ratio",
  "cagr",
  "mdd_abs",
  "beta_abs",
  "alpha",
]);
const EXACT_OBJECTIVE_QUOTA = 48;
const EXACT_DIVERSITY_QUOTA = 60;
const CHILD_WORKER_URL = "/optimizer-worker.js?v=20260802.2";

let activeChild = null;
let cancelled = false;

export function balancedSearchPlan(searchBudget = 30000) {
  const total = Math.max(6000, Math.floor(Number(searchBudget) || 30000));
  const diversity = Math.max(1000, Math.floor(total * 0.10));
  const objectivePool = total - diversity;
  const base = Math.floor(objectivePool / OBJECTIVES.length);
  let remainder = objectivePool - base * OBJECTIVES.length;
  const objectives = {};
  for (const objective of OBJECTIVES) {
    objectives[objective] = base + (remainder > 0 ? 1 : 0);
    remainder -= remainder > 0 ? 1 : 0;
  }
  return {
    total,
    objectives,
    pareto_diversity: diversity,
  };
}

function metricValue(record, objective) {
  const metrics = record.approximateTrainingMetrics || {};
  if (objective === "mdd_abs") {
    const value = Number(metrics.mdd);
    return Number.isFinite(value) ? -Math.abs(value) : Number.NEGATIVE_INFINITY;
  }
  if (objective === "beta_abs") {
    const value = Number(metrics.beta);
    return Number.isFinite(value) ? -Math.abs(value) : Number.NEGATIVE_INFINITY;
  }
  const value = Number(metrics[objective]);
  return Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY;
}

function compareForObjective(left, right, objective) {
  const difference = metricValue(right, objective) - metricValue(left, objective);
  if (Math.abs(difference) > 1e-12) return difference;
  return Number(left.mask) - Number(right.mask);
}

function popcount(value) {
  let current = value >>> 0;
  let count = 0;
  while (current) {
    current &= current - 1;
    count += 1;
  }
  return count;
}

function hammingDistance(left, right) {
  return popcount((Number(left) ^ Number(right)) >>> 0);
}

function addObjectiveQuota({ output, seen, records, objective, quota }) {
  let added = 0;
  for (const record of [...records].sort((left, right) => (
    compareForObjective(left, right, objective)
  ))) {
    if (added >= quota) break;
    if (seen.has(record.mask)) continue;
    seen.add(record.mask);
    output.push({ ...record, selectionSource: `objective:${objective}` });
    added += 1;
  }
  return added;
}

export function selectBalancedCombinations(records) {
  const byMask = new Map();
  for (const record of records || []) {
    if (!Number.isInteger(Number(record?.mask))) continue;
    const mask = Number(record.mask) >>> 0;
    const existing = byMask.get(mask);
    if (!existing) {
      byMask.set(mask, { ...record, mask, sourceRuns: [record.sourceRun].filter(Boolean) });
    } else if (record.sourceRun && !existing.sourceRuns.includes(record.sourceRun)) {
      existing.sourceRuns.push(record.sourceRun);
    }
  }
  const pool = [...byMask.values()];
  const output = [];
  const seen = new Set();
  const actual = Object.fromEntries(OBJECTIVES.map((objective) => [objective, 0]));

  for (const objective of OBJECTIVES) {
    actual[objective] = addObjectiveQuota({
      output,
      seen,
      records: pool,
      objective,
      quota: EXACT_OBJECTIVE_QUOTA,
    });
  }

  const remaining = pool.filter((record) => !seen.has(record.mask));
  let diversityAdded = 0;
  while (diversityAdded < EXACT_DIVERSITY_QUOTA && remaining.length) {
    let bestIndex = 0;
    let bestDistance = -1;
    let bestParetoPriority = -1;
    for (let index = 0; index < remaining.length; index += 1) {
      const candidate = remaining[index];
      const minimumDistance = output.length
        ? Math.min(...output.map((anchor) => hammingDistance(candidate.mask, anchor.mask)))
        : 20;
      const paretoPriority = candidate.sourceRuns?.includes("pareto_diversity") ? 1 : 0;
      if (
        minimumDistance > bestDistance
        || (minimumDistance === bestDistance && paretoPriority > bestParetoPriority)
        || (
          minimumDistance === bestDistance
          && paretoPriority === bestParetoPriority
          && candidate.mask < remaining[bestIndex].mask
        )
      ) {
        bestIndex = index;
        bestDistance = minimumDistance;
        bestParetoPriority = paretoPriority;
      }
    }
    const [record] = remaining.splice(bestIndex, 1);
    seen.add(record.mask);
    output.push({ ...record, selectionSource: "pareto-diversity" });
    diversityAdded += 1;
  }

  const requested = Object.fromEntries(
    OBJECTIVES.map((objective) => [objective, EXACT_OBJECTIVE_QUOTA]),
  );
  requested.pareto_diversity = EXACT_DIVERSITY_QUOTA;
  actual.pareto_diversity = diversityAdded;
  const incomplete = [...OBJECTIVES, "pareto_diversity"].filter(
    (key) => actual[key] !== requested[key],
  );
  if (output.length !== 300 || incomplete.length) {
    throw new Error(
      `平衡精確複驗集合不足：${JSON.stringify({ requested, actual, pool: pool.length })}`,
    );
  }
  return {
    records: output,
    allocation: { requested, actual },
    sourcePoolCount: pool.length,
  };
}

function runChild({ snapshot, settings, primaryObjective, searchBudget, runIndex, runCount }) {
  return new Promise((resolve, reject) => {
    if (cancelled) {
      reject(new Error("最佳化已取消。"));
      return;
    }
    const child = new Worker(CHILD_WORKER_URL, { type: "module" });
    activeChild = child;
    child.addEventListener("message", (event) => {
      const message = event.data || {};
      if (message.type === "progress") {
        postMessage({
          type: "progress",
          stage: "balanced",
          completed: runIndex,
          total: runCount,
        });
      } else if (message.type === "complete") {
        activeChild = null;
        child.terminate();
        resolve(message.result);
      } else if (message.type === "error") {
        activeChild = null;
        child.terminate();
        reject(new Error(message.error || "子搜尋 Worker 發生錯誤。"));
      }
    });
    child.addEventListener("error", (event) => {
      activeChild = null;
      child.terminate();
      reject(new Error(event.message || "子搜尋 Worker 無法執行。"));
    });
    child.postMessage({
      type: "optimize",
      snapshot,
      settings: { ...settings, primaryObjective, searchBudget },
    });
  });
}

function serializeMasks(masks) {
  const bytes = new Uint8Array(masks.length * 4);
  const view = new DataView(bytes.buffer);
  masks.forEach((mask, index) => view.setUint32(index * 4, mask >>> 0, true));
  return bytes;
}

async function digestMasks(masks) {
  const digest = await crypto.subtle.digest("SHA-256", serializeMasks(masks));
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

async function runBalanced(snapshot, settings) {
  cancelled = false;
  const plan = balancedSearchPlan(settings.searchBudget);
  const runs = [
    ...OBJECTIVES.map((objective) => ({
      sourceRun: `objective:${objective}`,
      primaryObjective: objective,
      searchBudget: plan.objectives[objective],
    })),
    {
      sourceRun: "pareto_diversity",
      primaryObjective: "sortino_ratio",
      searchBudget: plan.pareto_diversity,
    },
  ];
  const childResults = [];
  for (let index = 0; index < runs.length; index += 1) {
    const run = runs[index];
    postMessage({ type: "progress", stage: "balanced", completed: index, total: runs.length });
    const result = await runChild({
      snapshot,
      settings,
      primaryObjective: run.primaryObjective,
      searchBudget: run.searchBudget,
      runIndex: index,
      runCount: runs.length,
    });
    childResults.push({ ...run, result });
  }
  postMessage({ type: "progress", stage: "balanced", completed: runs.length, total: runs.length });

  const sourceRecords = childResults.flatMap(({ sourceRun, result }) => (
    result.combinations.map((record) => ({ ...record, sourceRun }))
  ));
  const selected = selectBalancedCombinations(sourceRecords);
  const evaluatedMasks = [...new Set(
    childResults.flatMap(({ result }) => result.search.evaluatedMasks || []),
  )].map((mask) => Number(mask) >>> 0).sort((left, right) => left - right);
  const evaluatedMaskHash = await digestMasks(evaluatedMasks);
  const budgetRequested = {
    ...plan.objectives,
    pareto_diversity: plan.pareto_diversity,
  };
  const localSearchTrace = childResults.flatMap(({ sourceRun, result }) => (
    (result.search.localSearchTrace || []).map((item) => ({ ...item, sourceRun }))
  ));

  return {
    combinations: selected.records.map((record, index) => ({
      combinationId: `optimizer-${String(index + 1).padStart(3, "0")}`,
      mask: record.mask,
      tickers: record.tickers,
      selectionSource: record.selectionSource,
      approximateTrainingMetrics: record.approximateTrainingMetrics,
    })),
    search: {
      optimizerAlgorithmVersion: `${snapshot.optimizerAlgorithmVersion}-balanced-v1`,
      optimizationMode: "balanced_multi_objective",
      primaryObjective: null,
      proxyCombinationCount: 184756,
      proxyPassCount: runs.length,
      deepCombinationCount: plan.total,
      uniqueDeepCombinationCount: evaluatedMasks.length,
      exactVerificationCount: 300,
      requestedSearchBudget: plan.total,
      evaluatedMaskHash,
      randomSeed: Object.fromEntries(
        childResults.map(({ sourceRun, result }) => [sourceRun, result.search.randomSeed]),
      ),
      budgetAllocation: {
        requested: budgetRequested,
        actual: budgetRequested,
      },
      exactVerificationAllocation: selected.allocation,
      exactVerificationSourcePoolCount: selected.sourcePoolCount,
      childRuns: childResults.map(({ sourceRun, primaryObjective, searchBudget, result }) => ({
        sourceRun,
        primaryObjective,
        requestedSearchBudget: searchBudget,
        evaluatedMaskHash: result.search.evaluatedMaskHash,
        exactCandidateCount: result.combinations.length,
      })),
      localSearchTrace,
      evaluatedMasks,
      stopReason: "balanced_search_budget_reached",
    },
  };
}

async function handleMessage(event) {
  const message = event.data || {};
  if (message.type === "cancel") {
    cancelled = true;
    activeChild?.terminate();
    activeChild = null;
    return;
  }
  if (message.type !== "optimize") return;
  try {
    const result = await runBalanced(message.snapshot, message.settings || {});
    postMessage({ type: "complete", result });
  } catch (error) {
    postMessage({
      type: "error",
      error: error instanceof Error ? error.message : String(error),
    });
  }
}

if (typeof self !== "undefined" && typeof self.addEventListener === "function") {
  self.addEventListener("message", handleMessage);
}
