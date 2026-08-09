import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function read(relativePath) {
  return fs.readFileSync(path.join(ROOT, relativePath), "utf8");
}

const resultsSource = read("apps/portfolio-web/src/RefineryResults.tsx");
const phase5Source = read("apps/portfolio-web/src/RefineryPhase5Results.tsx");
const typesSource = read("apps/portfolio-web/src/refineryTypes.ts");
const mainSource = read("apps/portfolio-web/src/main.tsx");
const phase5CssSource = read("apps/portfolio-web/src/refineryPhase5.css");

test("Phase 5 panels are wired into the existing isolated Refinery results stack", () => {
  assert.match(resultsSource, /import \{ RefineryPhase5Results \} from "\.\/RefineryPhase5Results";/u);
  assert.match(resultsSource, /<RefineryPhase5Results response=\{response\} \/>/u);
  assert.match(typesSource, /clustering\?: RefineryClusteringEvidence/u);
  assert.match(typesSource, /redundancy\?: RefineryRedundancyEvidence/u);
  assert.match(typesSource, /factor_relationships\?: RefineryFactorRelationships/u);
  assert.match(typesSource, /theme_relationships\?: RefineryThemeRelationships/u);
});

test("Phase 5 browser code remains presentation-only and does not become a second quant authority", () => {
  assert.doesNotMatch(phase5Source, /fetch\s*\(/u);
  assert.doesNotMatch(phase5Source, /\/api\/v[13]\//u);
  assert.doesNotMatch(phase5Source, /Math\.sqrt\s*\(/u);
  assert.doesNotMatch(phase5Source, /scipy|linkage\s*\(|fcluster\s*\(/iu);
  assert.doesNotMatch(phase5Source, /redundancy_verdict|redundancyVerdict|computeVerdict/u);
  assert.doesNotMatch(phase5Source, /onClick\s*=|<button/u);
  assert.match(phase5Source, /response\.analysis\?\.redundancy/u);
  assert.match(phase5Source, /response\.analysis\?\.factor_relationships/u);
});

test("Phase 5 renders verdict evidence without action recommendation controls", () => {
  assert.match(phase5Source, /HIGH \/ MEDIUM \/ LOW \/ UNCERTAIN/u);
  assert.match(phase5Source, /不是 KEEP \/ TRIM \/ REPLACE/u);
  assert.doesNotMatch(phase5Source, /name=["'](?:KEEP|TRIM|REPLACE)["']/u);
  assert.doesNotMatch(phase5Source, /execute|optimizer|exhaustive/iu);
});

test("Phase 5 stylesheet is loaded after the Phase 4 Refinery stylesheet", () => {
  const phase4Index = mainSource.indexOf('import "./refinery.css"');
  const phase5Index = mainSource.indexOf('import "./refineryPhase5.css"');
  assert.ok(phase4Index >= 0);
  assert.ok(phase5Index > phase4Index);
});

test("Phase 5 CSS keeps every concrete class selector inside the Refinery workspace", () => {
  const concreteClassLines = phase5CssSource
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("."));
  assert.ok(concreteClassLines.length > 0);
  for (const line of concreteClassLines) {
    assert.match(line, /^\.refinery-workspace\b/u, `unscoped Phase 5 selector: ${line}`);
  }
});

test("large Phase 5 evidence tables have explicit presentation-only DOM guards", () => {
  assert.match(phase5Source, /MAX_REDUNDANCY_ROWS = 80/u);
  assert.match(phase5Source, /slice\(0, MAX_REDUNDANCY_ROWS\)/u);
  assert.match(phase5Source, /這是呈現限制，不是篩選或排名/u);
});
