import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";
import path from "node:path";

const root = process.cwd();
const sourceRoot = path.join(root, "apps", "portfolio-web", "src");

async function sourceText() {
  const files = (await readdir(sourceRoot)).filter((name) => /\.(?:ts|tsx|css)$/u.test(name));
  const entries = await Promise.all(files.map(async (name) => [name, await readFile(path.join(sourceRoot, name), "utf8")]));
  return Object.fromEntries(entries);
}

test("Portfolio app is standalone and uses only the self-owned v3 API", async () => {
  const sources = await sourceText();
  const combined = Object.values(sources).join("\n");

  assert.match(combined, /\/api\/v3\/portfolio/u);
  assert.doesNotMatch(combined, /portfolio-backtest-api\.vercel\.app/u);
  assert.doesNotMatch(combined, /chihung1024\.github\.io\/backtest/u);
  assert.doesNotMatch(combined, /\/api\/portfolio-lab\//u);
  assert.doesNotMatch(combined, /<dialog\b|showModal\(|<iframe\b/iu);
  assert.match(sources["App.tsx"], /id="portfolio-main"/u);
  assert.match(sources["App.tsx"], /這是一個可直接開啟與重新整理的獨立專頁/u);
});

test("Portfolio app exposes the complete dashboard and persistence actions", async () => {
  const results = await readFile(path.join(sourceRoot, "ResultsDashboard.tsx"), "utf8");
  const comparison = await readFile(path.join(sourceRoot, "PortfolioComparison.tsx"), "utf8");
  const app = await readFile(path.join(sourceRoot, "App.tsx"), "utf8");

  for (const label of ["總覽", "資產成長", "回撤", "年度報酬", "月報酬", "現金流與收入", "配置漂移", "進階分析", "資料稽核"]) {
    assert.match(results, new RegExp(label, "u"));
  }
  for (const action of ["儲存", "分享", "匯入", "匯出模型", "匯出 CSV", "匯出 JSON"]) {
    assert.match(`${app}\n${results}`, new RegExp(action, "u"));
  }
  assert.match(results, /<PortfolioComparison results=\{response\.results\}/u);
  assert.match(comparison, /投資組合並排比較/u);
  assert.match(comparison, /共同比較期間/u);
  assert.match(comparison, /期間不一致，禁止直接比較/u);
  assert.match(comparison, /result\.metrics\.start/u);
  assert.match(comparison, /result\.metrics\.end/u);
  assert.doesNotMatch(comparison, /cagr\s*=|sharpe\s*=|sortino\s*=/iu);
});

test("Portfolio allocation and responsive limits are encoded in the model and UI", async () => {
  const model = await readFile(path.join(sourceRoot, "model.ts"), "utf8");
  const allocation = await readFile(path.join(sourceRoot, "AllocationEditor.tsx"), "utf8");
  const styles = await readFile(path.join(sourceRoot, "styles.css"), "utf8");

  assert.match(model, /const MAX_PORTFOLIOS = 5/u);
  assert.match(model, /const MAX_ASSETS = 20/u);
  assert.match(allocation, /desktop-matrix/u);
  assert.match(allocation, /mobile-allocation/u);
  assert.match(styles, /@media \(max-width: 820px\)/u);
  assert.match(styles, /env\(safe-area-inset-bottom\)/u);
  assert.match(styles, /prefers-reduced-motion/u);
  assert.match(styles, /forced-colors/u);
});

test("Vite emits the directly addressable application under public portfolio", async () => {
  const config = await readFile(path.join(root, "apps", "portfolio-web", "vite.config.ts"), "utf8");
  const entry = await readFile(path.join(root, "apps", "portfolio-web", "index.html"), "utf8");

  assert.match(config, /base: "\/portfolio\/"/u);
  assert.match(config, /public\/portfolio/u);
  assert.match(entry, /id="root"/u);
  assert.match(entry, /skip-link/u);
});
