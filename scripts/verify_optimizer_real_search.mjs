import { performance } from "node:perf_hooks";
import { gunzipSync } from "node:zlib";
import { readFile, writeFile } from "node:fs/promises";

import { optimizeSnapshot } from "../public/optimizer-worker.js";

const prepared = JSON.parse(
  await readFile("diagnostics/optimizer-prepared.json", "utf8"),
);
const compressed = Buffer.from(prepared.snapshot.data, "base64");
const snapshot = JSON.parse(gunzipSync(compressed).toString("utf8"));
const settings = {
  primaryObjective: "sortino_ratio",
  searchBudget: 30_000,
};

async function runOnce(label) {
  const progressEvents = [];
  const started = performance.now();
  const result = await optimizeSnapshot({
    snapshot,
    settings,
    progress(stage, completed, total) {
      if (completed === total || completed === 0 || completed % 10_000 === 0) {
        progressEvents.push({
          stage,
          completed,
          total,
          elapsedMs: performance.now() - started,
        });
      }
    },
  });
  return {
    label,
    elapsedMs: performance.now() - started,
    result,
    progressEvents,
  };
}

const first = await runOnce("first");
const second = await runOnce("second");
const firstMasks = first.result.combinations.map((item) => item.mask);
const secondMasks = second.result.combinations.map((item) => item.mask);
const deterministic = (
  first.result.search.evaluatedMaskHash === second.result.search.evaluatedMaskHash
  && JSON.stringify(firstMasks) === JSON.stringify(secondMasks)
  && first.result.search.randomSeed === second.result.search.randomSeed
);

const report = {
  firstElapsedSeconds: first.elapsedMs / 1000,
  secondElapsedSeconds: second.elapsedMs / 1000,
  deterministic,
  proxyCombinationCount: first.result.search.proxyCombinationCount,
  deepCombinationCount: first.result.search.deepCombinationCount,
  exactVerificationCount: first.result.search.exactVerificationCount,
  uniqueDeepMasks: new Set(first.result.search.evaluatedMasks).size,
  uniqueVerificationMasks: new Set(firstMasks).size,
  evaluatedMaskHash: first.result.search.evaluatedMaskHash,
  randomSeed: first.result.search.randomSeed,
  budgetAllocation: first.result.search.budgetAllocation,
  localSearchTraceCount: first.result.search.localSearchTrace.length,
  stopReason: first.result.search.stopReason,
  progressEvents: first.progressEvents,
};

await writeFile(
  "diagnostics/optimizer-search-output.json",
  `${JSON.stringify(first.result)}\n`,
);
await writeFile(
  "diagnostics/optimizer-search-report.json",
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
if (!deterministic) {
  throw new Error("Real-data optimizer search was not deterministic");
}
if (
  report.proxyCombinationCount !== 184_756
  || report.deepCombinationCount !== 30_000
  || report.exactVerificationCount !== 300
  || report.uniqueDeepMasks !== 30_000
  || report.uniqueVerificationMasks !== 300
) {
  throw new Error("Real-data optimizer search contract was not satisfied");
}
