import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function read(relativePath) {
  return fs.readFileSync(path.join(ROOT, relativePath), "utf8");
}

const appSource = read("apps/portfolio-web/src/App.tsx");
const portfolioApiSource = read("apps/portfolio-web/src/api.ts");
const refineryApiSource = read("apps/portfolio-web/src/refineryApi.ts");
const refineryModelSource = read("apps/portfolio-web/src/refineryModel.ts");
const refineryTypesSource = read("apps/portfolio-web/src/refineryTypes.ts");
const refineryCssSource = read("apps/portfolio-web/src/refinery.css");
const handoffSource = read("apps/portfolio-web/src/handoff.ts");
const mainSource = read("apps/portfolio-web/src/main.tsx");

const PORTFOLIO_MODEL_KEY = "backteststock.portfolio.model.v1";
const REFINERY_MODEL_KEY = "backteststock.refinery.workspace.v1";
const ACTIVE_WORKSPACE_KEY = "backteststock.portfolio.active-workspace.v1";

test("Portfolio and Refinery API clients remain same-origin and namespace-isolated", () => {
  assert.match(portfolioApiSource, /\/api\/v3\/portfolio/u);
  assert.doesNotMatch(portfolioApiSource, /\/api\/v1\/refinery/u);

  assert.match(refineryApiSource, /\/api\/v1\/refinery/u);
  assert.doesNotMatch(refineryApiSource, /\/api\/v3\/portfolio/u);

  assert.doesNotMatch(portfolioApiSource, /https?:\/\//u);
  assert.doesNotMatch(refineryApiSource, /https?:\/\//u);
});

test("Refinery persistence is separate from the existing Portfolio model contract", () => {
  assert.match(appSource, new RegExp(PORTFOLIO_MODEL_KEY.replaceAll(".", "\\."), "u"));
  assert.match(handoffSource, new RegExp(PORTFOLIO_MODEL_KEY.replaceAll(".", "\\."), "u"));
  assert.doesNotMatch(handoffSource, new RegExp(REFINERY_MODEL_KEY.replaceAll(".", "\\."), "u"));

  assert.match(refineryModelSource, new RegExp(REFINERY_MODEL_KEY.replaceAll(".", "\\."), "u"));
  assert.match(refineryModelSource, new RegExp(ACTIVE_WORKSPACE_KEY.replaceAll(".", "\\."), "u"));
  assert.doesNotMatch(refineryModelSource, new RegExp(PORTFOLIO_MODEL_KEY.replaceAll(".", "\\."), "u"));
});

test("shared model and scanner handoff links force the Portfolio workspace", () => {
  assert.match(appSource, /parameters\.has\("model"\) \|\| parameters\.has\("handoff"\)/u);
  assert.match(appSource, /return "portfolio";/u);
  assert.match(appSource, /<RefineryWorkspace \/>/u);
  assert.match(appSource, /className="workspace-switch"/u);
  assert.match(appSource, /投資組合回測/u);
  assert.match(appSource, /持股精煉診斷/u);
});

test("Refinery workspace does not import Portfolio ledger types as a generic data bag", () => {
  assert.doesNotMatch(refineryTypesSource, /from ["']\.\/types["']/u);
  assert.doesNotMatch(refineryModelSource, /from ["']\.\/types["']/u);
  assert.match(refineryModelSource, /RefineryWorkspaceModel/u);
  assert.doesNotMatch(refineryApiSource, /\b(?:BacktestRequest|BacktestResponse|PreflightResponse)\b/u);
});

test("the Refinery stylesheet is additive and loaded after the existing Portfolio stylesheet", () => {
  const portfolioCssIndex = mainSource.indexOf('import "./styles.css"');
  const refineryCssIndex = mainSource.indexOf('import "./refinery.css"');
  assert.ok(portfolioCssIndex >= 0);
  assert.ok(refineryCssIndex > portfolioCssIndex);
});

test("Refinery utility selectors stay scoped away from existing Portfolio classes", () => {
  assert.doesNotMatch(
    refineryCssSource,
    /(?:^|\n)\.(?:autosave-indicator|summary-metric|summary-chip|mobile-row-heading|toggle-row|weight-total|signed-negative|muted-inline|workspace-hint)(?=[\s.#:{,]|$)/u,
  );
});

test("Phase 4 workspace remains a direct page without iframe or modal shell", () => {
  assert.doesNotMatch(appSource, /<iframe/u);
  assert.doesNotMatch(appSource, /<dialog/u);
  assert.doesNotMatch(appSource, /window\.open/u);
});
