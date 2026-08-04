import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join } from "node:path";
import test from "node:test";

const retiredFiles = [
  "public/backtest-workspace.js",
  "public/backtest-workspace.css",
  "public/portfolio-lab.css",
  "public/portfolio-lab-core.js",
  "public/portfolio-lab-settings.js",
  "public/portfolio-lab-assets.js",
  "public/portfolio-lab-results.js",
  "public/portfolio-lab-integration.js",
  "public/portfolio-lab-capture-bridge.js",
  "scripts/smoke_test_portfolio_lab.mjs",
  "tests/e2e/backtest_workspace_layout.spec.mjs",
];

const forbiddenRuntimeText = [
  "/api/portfolio-lab/",
  "portfolio-backtest-api.vercel.app",
  "https://chihung1024.github.io/backtest/",
  "PORTFOLIO_LAB_API_ORIGIN",
  "integrated-backtest-dialog",
];

const searchableExtensions = new Set([
  ".css",
  ".html",
  ".js",
  ".json",
  ".jsonc",
  ".mjs",
  ".ts",
  ".tsx",
  ".yml",
  ".yaml",
]);

function runtimeFiles(path) {
  if (!existsSync(path)) return [];
  if (!statSync(path).isDirectory()) return [path];
  return readdirSync(path).flatMap((entry) => runtimeFiles(join(path, entry)));
}

test("old Portfolio Lab runtime assets are deleted", () => {
  for (const path of retiredFiles) {
    assert.equal(existsSync(path), false, `${path} must be deleted`);
  }
});

test("production runtime contains no old API, Pages impersonation or dialog identifier", () => {
  const roots = [
    "public",
    "worker",
    "scripts",
    ".github/workflows",
    "vercel.json",
    "wrangler.jsonc",
  ];
  const violations = [];
  for (const path of roots.flatMap(runtimeFiles)) {
    if (!searchableExtensions.has(extname(path))) continue;
    const content = readFileSync(path, "utf8");
    for (const forbidden of forbiddenRuntimeText) {
      if (content.includes(forbidden)) violations.push(`${path}: ${forbidden}`);
    }
  }
  assert.deepEqual(violations, []);
});

test("only the self-owned Portfolio v3 route remains in edge and deployment smoke", () => {
  const router = readFileSync("worker/router.js", "utf8");
  const deploy = readFileSync(".github/workflows/deploy-cloudflare.yml", "utf8");
  assert.match(router, /\/api\/v3\/portfolio\//);
  assert.doesNotMatch(router, /proxyPortfolioLab|PORTFOLIO_LAB/);
  assert.match(deploy, /smoke_test_portfolio_v3\.mjs/);
  assert.doesNotMatch(deploy, /smoke_test_portfolio_lab\.mjs/);
});

test("Portfolio v3 production smoke validates the actual series response and advanced ledger path", () => {
  const smoke = readFileSync("scripts/smoke_test_portfolio_v3.mjs", "utf8");
  assert.match(smoke, /portfolio\.series/);
  assert.doesNotMatch(smoke, /portfolio\.history|results\[0\]\.history/);
  assert.match(smoke, /reinvest_distributions:\s*false/);
  assert.match(smoke, /type:\s*"fixed"/);
  assert.match(smoke, /frequency:\s*"monthly"/);
  assert.match(smoke, /transaction_cost_bps:\s*5/);
  assert.match(smoke, /type:\s*"fixed_ratio"/);
  assert.match(smoke, /include_events:\s*true/);
  assert.match(smoke, /include_allocation_history:\s*true/);
  assert.match(smoke, /ledger_contract_version/);
  assert.match(smoke, /twd_valuation_contract_version/);
});

test("Cloudflare smoke waits for the Vercel deployment serving the same Git SHA", () => {
  const smoke = readFileSync("scripts/smoke_test_portfolio_v3.mjs", "utf8");
  const deploy = readFileSync(".github/workflows/deploy-cloudflare.yml", "utf8");
  const api = readFileSync("api/portfolio_v3.py", "utf8");
  const packageJson = readFileSync("package.json", "utf8");

  assert.match(api, /VERCEL_GIT_COMMIT_SHA/);
  assert.match(api, /"deployment_sha"/);
  assert.match(smoke, /EXPECTED_DEPLOYMENT_SHA/);
  assert.match(smoke, /health\.deployment_sha/);
  assert.match(smoke, /waitForExpectedDeployment/);
  assert.match(smoke, /PORTFOLIO_READINESS_TIMEOUT_MS/);
  assert.match(smoke, /PORTFOLIO_READINESS_POLL_MS/);
  assert.match(deploy, /EXPECTED_DEPLOYMENT_SHA:\s*\$\{\{ github\.sha \}\}/);
  assert.match(packageJson, /test_portfolio_smoke_readiness\.mjs/);
});
