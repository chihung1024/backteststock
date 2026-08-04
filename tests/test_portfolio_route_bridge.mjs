import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (file) => readFile(path.join(root, file), "utf8");

test("main navigation exposes Portfolio as a normal directly addressable page", async () => {
  const html = await read("public/index.html");

  assert.match(html, /id="portfolio-route-link"/u);
  assert.match(html, /href="\/portfolio\/"/u);
  assert.match(html, /data-portfolio-route="main"/u);
  assert.match(html, /portfolio-route\.css/u);
  assert.match(html, /portfolio-route-bridge\.js/u);
  assert.match(html, /data-tab="scanner" aria-selected="true"/u);
  assert.match(html, /id="backtest-panel" class="tab-panel hidden"/u);
  assert.match(html, /id="scanner-panel" class="tab-panel"/u);
});

test("scanner handoff preserves source context and enforces the Portfolio asset limit", async () => {
  const bridge = await read("public/portfolio-route-bridge.js");

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
  assert.doesNotMatch(handoff, /localStorage.*(?:token|key|secret)/iu);
});
