import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function read(relativePath) {
  return fs.readFileSync(path.join(ROOT, relativePath), "utf8");
}

const editorSource = read("apps/portfolio-web/src/RefineryExperimentPlanEditor.tsx");
const workspaceSource = read("apps/portfolio-web/src/RefineryWorkspace.tsx");
const resultsSource = read("apps/portfolio-web/src/RefineryResults.tsx");
const phase6Source = read("apps/portfolio-web/src/RefineryPhase6Results.tsx");
const modelSource = read("apps/portfolio-web/src/refineryModel.ts");
const typesSource = read("apps/portfolio-web/src/refineryTypes.ts");
const mainSource = read("apps/portfolio-web/src/main.tsx");
const cssSource = read("apps/portfolio-web/src/refineryPhase6.css");

test("Phase 6 plan is optional, explicit, normalized by the shared Refinery authority, and bounded", () => {
  assert.match(typesSource, /RefineryExperimentOperationType = "remove_one" \| "add_one" \| "replace_one"/u);
  assert.match(typesSource, /experiment_plan\?: RefineryExperimentOperation\[\]/u);
  assert.match(modelSource, /MAX_REFINERY_EXPERIMENT_OPERATIONS = 12/u);
  assert.match(modelSource, /MAX_REFINERY_EXPERIMENT_UNION_SYMBOLS = 24/u);
  assert.match(modelSource, /validateRefineryExperimentPlan/u);
  assert.match(
    modelSource,
    /if \(plan\.length === 0\) return \[\];/u,
    "an empty Phase 6 plan must preserve the established 2–100 candidate workflow",
  );
  assert.match(modelSource, /toRefineryExperimentPlan/u);
  assert.match(modelSource, /normalizeRefinerySymbol\(draft\.remove\)/u);
  assert.match(modelSource, /normalizeRefinerySymbol\(draft\.add\)/u);
  assert.match(modelSource, /request\.experiment_plan = toRefineryExperimentPlan\(experimentPlan\)/u);
  assert.match(editorSource, /MAX_REFINERY_EXPERIMENT_OPERATIONS/u);
  assert.match(editorSource, /不會自動產生 Cartesian 組合/u);
});

test("Phase 6 plan state is page-scoped and does not change Refinery workspace persistence", () => {
  assert.doesNotMatch(typesSource, /experimentPlan/u);
  assert.match(workspaceSource, /useState<RefineryExperimentDraft\[\]>\(\[\]\)/u);
  assert.match(workspaceSource, /JSON\.stringify\(model\)/u);
  assert.match(
    workspaceSource,
    /function setExperimentPlan\(plan: RefineryExperimentDraft\[\]\) \{[\s\S]*?setExperimentPlanState\(plan\);[\s\S]*?invalidateEvidence\(\);/u,
  );
  assert.doesNotMatch(editorSource, /localStorage/u);
  assert.doesNotMatch(phase6Source, /localStorage/u);
  assert.match(workspaceSource, /setExperimentPlanState\(\[\]\)/u);
});

test("Phase 6 UI uses the existing preflight and analyze boundaries without a third endpoint", () => {
  assert.match(workspaceSource, /toRefineryApiRequest\(model, experimentPlan\)/u);
  assert.match(workspaceSource, /<RefineryExperimentPlanEditor/u);
  assert.match(workspaceSource, /<RefineryPhase6Preflight marginal=\{preflight\.marginal_experiments\} \/>/u);
  assert.match(resultsSource, /import \{ RefineryPhase6Results \} from "\.\/RefineryPhase6Results";/u);
  assert.match(resultsSource, /<RefineryPhase6Results marginal=\{response\.marginal_experiments\} \/>/u);
  assert.match(typesSource, /marginal_experiments\?: RefineryMarginalExperiments/u);
});

test("Phase 6 browser presentation exposes common samples and operation order without becoming a quant or ranking authority", () => {
  assert.match(phase6Source, /Phase 6 共同實驗樣本預檢/u);
  assert.match(phase6Source, /in-sample historical diagnostic \/ not OOS/u);
  assert.match(phase6Source, /marginal\.results\.map/u);
  assert.match(phase6Source, /shared_pair_invariant/u);
  assert.doesNotMatch(phase6Source, /fetch\s*\(/u);
  assert.doesNotMatch(phase6Source, /\/api\/v[13]\//u);
  assert.doesNotMatch(phase6Source, /\.sort\s*\(/u);
  assert.doesNotMatch(phase6Source, /best_experiment|winner|optimizer|exhaustive/iu);
  assert.doesNotMatch(phase6Source, /Math\.sqrt\s*\(|ledoit_wolf_covariance\s*\(|hierarchical_clustering\s*\(/iu);
});

test("Phase 6 stylesheet is additive, scoped, and contains wide tables on mobile", () => {
  const phase5Index = mainSource.indexOf('import "./refineryPhase5.css"');
  const phase6Index = mainSource.indexOf('import "./refineryPhase6.css"');
  assert.ok(phase5Index >= 0);
  assert.ok(phase6Index > phase5Index);

  const concreteClassLines = cssSource
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("."));
  assert.ok(concreteClassLines.length > 0);
  for (const line of concreteClassLines) {
    assert.match(line, /^\.refinery-workspace\b/u, `unscoped Phase 6 selector: ${line}`);
  }
  assert.match(
    cssSource,
    /\.refinery-workspace \.refinery-phase6-result-scroll,[\s\S]*?overflow-x:\s*auto;/su,
  );
  assert.match(cssSource, /\.refinery-workspace \.refinery-phase6-result-table\s*\{[^}]*min-width:\s*1280px;/su);
  assert.match(cssSource, /@media \(max-width: 560px\)/u);
});
