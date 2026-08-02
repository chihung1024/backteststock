import { createHash } from "node:crypto";
import { performance } from "node:perf_hooks";
import { readFile, writeFile } from "node:fs/promises";

import { optimizeSnapshot } from "../public/optimizer-worker.js";
import {
  balancedSearchPlan,
  selectBalancedCombinations,
} from "../public/optimizer-balanced-worker.js";

const snapshot = JSON.parse(
  await readFile("diagnostics/production-snapshot.json", "utf8"),
);
const objectives = ["sortino_ratio", "cagr", "mdd_abs", "beta_abs", "alpha"];
const plan = balancedSearchPlan(30_000);
const expectedPlan = {
  total: 30_000,
  objectives: {
    sortino_ratio: 5_400,
    cagr: 5_400,
    mdd_abs: 5_400,
    beta_abs: 5_400,
    alpha: 5_400,
  },
  pareto_diversity: 3_000,
};
if (JSON.stringify(plan) !== JSON.stringify(expectedPlan)) {
  throw new Error(`balanced plan mismatch: ${JSON.stringify(plan)}`);
}

function hashMasks(masks) {
  const bytes = Buffer.alloc(masks.length * 4);
  masks.forEach((mask, index) => bytes.writeUInt32LE(mask >>> 0, index * 4));
  return createHash("sha256").update(bytes).digest("hex");
}

async function runOnce(label) {
  const started = performance.now();
  const definitions = [
    ...objectives.map((objective) => ({
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
  const childRuns = [];
  for (const definition of definitions) {
    const childStarted = performance.now();
    const result = await optimizeSnapshot({
      snapshot,
      settings: {
        primaryObjective: definition.primaryObjective,
        searchBudget: definition.searchBudget,
      },
    });
    if (result.search.deepCombinationCount !== definition.searchBudget) {
      throw new Error(`${definition.sourceRun} deep budget mismatch`);
    }
    if (new Set(result.search.evaluatedMasks).size !== definition.searchBudget) {
      throw new Error(`${definition.sourceRun} unique deep masks mismatch`);
    }
    childRuns.push({
      ...definition,
      elapsedSeconds: (performance.now() - childStarted) / 1000,
      result,
    });
  }
  const sourceRecords = childRuns.flatMap(({ sourceRun, result }) => (
    result.combinations.map((record) => ({ ...record, sourceRun }))
  ));
  const selected = selectBalancedCombinations(sourceRecords);
  const selectedMasks = selected.records.map((record) => Number(record.mask) >>> 0);
  const evaluatedMasks = [...new Set(
    childRuns.flatMap(({ result }) => result.search.evaluatedMasks),
  )].map((mask) => Number(mask) >>> 0).sort((left, right) => left - right);
  return {
    label,
    elapsedSeconds: (performance.now() - started) / 1000,
    combinations: selected.records.map((record, index) => ({
      combinationId: `optimizer-${String(index + 1).padStart(3, "0")}`,
      mask: Number(record.mask) >>> 0,
      tickers: record.tickers,
      selectionSource: record.selectionSource,
      approximateTrainingMetrics: record.approximateTrainingMetrics,
    })),
    exactAllocation: selected.allocation,
    sourcePoolCount: selected.sourcePoolCount,
    selectedMaskHash: hashMasks(selectedMasks),
    evaluatedMaskHash: hashMasks(evaluatedMasks),
    uniqueEvaluatedMasks: evaluatedMasks.length,
    childRuns: childRuns.map((run) => ({
      sourceRun: run.sourceRun,
      primaryObjective: run.primaryObjective,
      searchBudget: run.searchBudget,
      elapsedSeconds: run.elapsedSeconds,
      evaluatedMaskHash: run.result.search.evaluatedMaskHash,
      randomSeed: run.result.search.randomSeed,
    })),
  };
}

const first = await runOnce("first");
const second = await runOnce("second");
const deterministic = (
  first.selectedMaskHash === second.selectedMaskHash
  && first.evaluatedMaskHash === second.evaluatedMaskHash
  && JSON.stringify(first.combinations.map((item) => item.mask))
    === JSON.stringify(second.combinations.map((item) => item.mask))
  && JSON.stringify(first.childRuns.map((item) => item.randomSeed))
    === JSON.stringify(second.childRuns.map((item) => item.randomSeed))
);
const expectedExact = {
  requested: {
    sortino_ratio: 48,
    cagr: 48,
    mdd_abs: 48,
    beta_abs: 48,
    alpha: 48,
    pareto_diversity: 60,
  },
  actual: {
    sortino_ratio: 48,
    cagr: 48,
    mdd_abs: 48,
    beta_abs: 48,
    alpha: 48,
    pareto_diversity: 60,
  },
};
if (!deterministic) throw new Error("balanced search is not deterministic");
if (
  first.combinations.length !== 300
  || new Set(first.combinations.map((item) => item.mask)).size !== 300
) {
  throw new Error("exact selection is not 300 unique combinations");
}
if (JSON.stringify(first.exactAllocation) !== JSON.stringify(expectedExact)) {
  throw new Error(`exact allocation mismatch: ${JSON.stringify(first.exactAllocation)}`);
}

const report = {
  searchPlan: plan,
  firstElapsedSeconds: first.elapsedSeconds,
  secondElapsedSeconds: second.elapsedSeconds,
  deterministic,
  exactCount: first.combinations.length,
  exactAllocation: first.exactAllocation,
  sourcePoolCount: first.sourcePoolCount,
  selectedMaskHash: first.selectedMaskHash,
  evaluatedMaskHash: first.evaluatedMaskHash,
  uniqueEvaluatedMasks: first.uniqueEvaluatedMasks,
  childRuns: first.childRuns,
};
await writeFile(
  "diagnostics/production-search-output.json",
  `${JSON.stringify({ combinations: first.combinations, report })}\n`,
);
await writeFile(
  "diagnostics/production-search-report.json",
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
