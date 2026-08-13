import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (file) => readFile(path.join(root, file), "utf8");

test("main navigation is replaced by a normal directly addressable Portfolio link", async () => {
  const scanner = await read("public/scan-composite-score.js");
  const index = await read("public/index.html");

  assert.match(scanner, /import "\.\/portfolio-route-bridge\.js\?v=20260814\.1"/u);
  assert.match(index, /scan-composite-score\.js\?v=20260814\.2/u);
  assert.match(scanner, /portfolioLink = document\.createElement\("a"\)/u);
  assert.match(scanner, /portfolioLink\.id = "portfolio-route-link"/u);
  assert.match(scanner, /portfolioLink\.href = "\/portfolio\/"/u);
  assert.match(scanner, /portfolioLink\.dataset\.portfolioRoute = "main"/u);
  assert.match(scanner, /oldBacktestButton\.replaceWith\(portfolioLink\)/u);
  assert.match(scanner, /#backtest-panel/u);
  assert.match(scanner, /#scanner-panel/u);
});

test("scanner handoff preserves source context and enforces the Portfolio asset limit", async () => {
  const bridge = await read("public/portfolio-route-bridge.js");

  assert.match(bridge, /import \{ normalizeScanJob \} from "\.\/scan-job-normalizer\.js\?v=20260812\.1"/u);
  assert.match(bridge, /return normalizeScanJob\(job, scanDateFallbackRange\(\)\)/u);
  for (const required of [
    "sourceJobId",
    "selectedTickers",
    "startDate",
    "endDate",
    "benchmark",
    "coverageThresholdPercent",
    "returnUrl",
    "returnState",
    "pageSize",
    "scrollY",
    "sort",
  ]) {
    assert.match(bridge, new RegExp(required, "u"));
  }
  assert.match(bridge, /MAX_PORTFOLIO_ASSETS = 20/u);
  assert.match(bridge, /coverageQualifiedTickers/u);
  assert.match(bridge, /selection\?\.sourceJobId !== job\.id/u);
  assert.match(bridge, /ticker !== benchmark/u);
  assert.match(bridge, /sessionStorage/u);
  assert.match(bridge, /\/portfolio\//u);
  assert.match(bridge, /restorePortfolioReturn/u);
});

test("Portfolio return preserves a matching rich Optimizer handoff", async () => {
  const bridge = await read("public/portfolio-route-bridge.js");

  assert.match(bridge, /const existingSelection = readJson\(localStorage, MANUAL_SELECTION_STORAGE_KEY, null\)/u);
  assert.match(bridge, /existingSelection\?\.version === 2/u);
  assert.match(bridge, /existingSelection\?\.sourceJobId === record\.sourceJobId/u);
  assert.match(bridge, /existingSelection\?\.selectionMode === "manual_fixed_source_pool"/u);
  assert.match(bridge, /\.\.\.existingSelection/u);
});

test("primary scanner flow no longer creates or opens a Portfolio dialog", async () => {
  const scanner = await read("public/scan-composite-score.js");

  assert.doesNotMatch(scanner, /integrated-backtest-dialog/u);
  assert.doesNotMatch(scanner, /ensureBacktestDialog/u);
  assert.doesNotMatch(scanner, /openBacktestDialog/u);
  assert.doesNotMatch(scanner, /showModal\(/u);
  assert.match(scanner, /integratedBacktestButton = document\.createElement\("a"\)/u);
  assert.match(scanner, /integratedBacktestButton\.href = "\/portfolio\/"/u);
  assert.match(scanner, /integratedBacktestButton\.dataset\.portfolioRoute = "scanner"/u);
  assert.match(scanner, /aria-disabled/u);
  assert.match(scanner, /投組上限 20/u);
});

test("Portfolio app consumes scanner handoff before React render and exposes a return link", async () => {
  const entry = await read("apps/portfolio-web/src/main.tsx");
  const handoff = await read("apps/portfolio-web/src/handoff.ts");

  assert.match(entry, /const handoff = applyPortfolioHandoff\(\);[\s\S]*createRoot/u);
  assert.match(entry, /installPortfolioHandoffUi\(handoff\)/u);
  assert.match(handoff, /績效列表已選 \$\{tickers\.length\} 檔等權組合/u);
  assert.match(handoff, /equalWeights/u);
  assert.match(handoff, /model\.startDate = record\.startDate/u);
  assert.match(handoff, /model\.endDate = record\.endDate/u);
  assert.match(handoff, /model\.benchmark = benchmark/u);
  assert.match(handoff, /portfolio-return-link/u);
  assert.match(handoff, /portfolio-handoff-banner/u);
  assert.match(handoff, /返回績效列表/u);
  assert.doesNotMatch(handoff, /(?:api[_-]?key|access[_-]?token|client[_-]?secret)/iu);
});
