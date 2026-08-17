import { expect, test } from "@playwright/test";

const ACTIVE_WORKSPACE_KEY = "backteststock.portfolio.active-workspace.v1";
const CAPABILITY_KEY = "backteststock.research-library.capability.v1";
const CAPABILITY = `rrl_${"C".repeat(43)}`;

const ADMISSION = {
  contractVersion: "walk-forward-admission-2026-08-17.1",
  asOfDate: "2026-08-16",
  limits: { maxCandidates: 100, maxCombinationsPerPeriod: 500000, maxHoldingCount: 20, pitMaxAgeDays: 10 },
  universes: [{
    id: "soxx",
    name: "SOXX",
    status: "eligible",
    earliestDecisionDate: "2026-07-29",
    latestDecisionDate: "2026-08-16",
    recommendedDecisionDate: "2026-07-29",
    recommendedMemberCount: 30,
    recommendedHoldingCount: 5,
    recommendedCombinationCount: 142506,
  }],
  recommended: {
    universe: "soxx",
    decisionDate: "2026-07-29",
    holdingCount: 5,
    memberCount: 30,
    combinationCount: 142506,
  },
};

async function mockBase(page) {
  await page.route("**/api/v3/portfolio/health", (route) => route.fulfill({ json: { status: "ok", service: "backteststock-portfolio-v3" } }));
  await page.route("**/api/v1/research/walk-forward/health", (route) => route.fulfill({
    json: {
      status: "ok",
      service: "backteststock-walk-forward-v1",
      api_contract_version: "walk-forward-api-2026-08-15.1",
      job_contract_version: "walk-forward-job-2026-08-15.1",
      deployment_sha: "test",
    },
  }));
  await page.route("**/api/v1/research/walk-forward/admission", (route) => route.fulfill({ json: ADMISSION }));
  await page.route("**/api/v1/research/runs/health", (route) => route.fulfill({
    json: {
      status: "ok",
      service: "backteststock-research-run-memory-v1",
      contractVersion: "research-run-memory-2026-08-17.1",
      durableStore: "d1",
      schemaReady: true,
    },
  }));
}

test("cancel invalidates a late successful save even when transport ignores AbortSignal", async ({ page }) => {
  await mockBase(page);
  await page.addInitScript(({ activeKey, capability }) => {
    localStorage.setItem(activeKey, "walk-forward");
    const realFetch = window.fetch.bind(window);
    window.__resolveLateResearchRun = null;
    window.fetch = (input, init = {}) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.endsWith("/api/v1/research/runs") && init.method === "POST") {
        return new Promise((resolve) => {
          window.__resolveLateResearchRun = () => resolve(new Response(JSON.stringify({
            contractVersion: "research-run-memory-2026-08-17.1",
            libraryId: "lib_late",
            libraryCapability: capability,
            run: {
              runId: "run_44444444-4444-4444-8444-444444444444",
              sourceRunId: null,
              name: "Late result",
              jobHash: "9".repeat(64),
              resultContractVersion: "walk-forward-job-2026-08-15.1",
              decisionCount: 1,
              createdAt: "2026-08-17 05:30:00",
            },
            result: { status: "completed" },
          }), { status: 201, headers: { "content-type": "application/json" } }));
        });
      }
      return realFetch(input, init);
    };
  }, { activeKey: ACTIVE_WORKSPACE_KEY, capability: CAPABILITY });

  await page.goto("/portfolio/");
  await expect(page.getByRole("heading", { name: "Research Library" })).toBeVisible();
  await expect(page.getByText("Durable memory 正常")).toBeVisible();

  await page.getByLabel("ResearchRun 研究名稱").fill("Late result");
  await page.getByRole("button", { name: "執行並保存", exact: true }).click();
  await expect(page.getByRole("button", { name: "停止等待" })).toBeVisible();

  await page.getByRole("button", { name: "停止等待" }).click();
  await expect(page.getByText(/已停止瀏覽器等待/u)).toBeVisible();
  await page.evaluate(() => window.__resolveLateResearchRun?.());
  await page.waitForTimeout(150);

  expect(await page.evaluate((key) => localStorage.getItem(key), CAPABILITY_KEY)).toBeNull();
  await expect(page.getByText("新研究庫已建立：請立即備份復原碼")).toHaveCount(0);
  await expect(page.getByText("Late result", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "執行並保存", exact: true })).toBeEnabled();
});


test("late Research Library connect cannot persist a credential after workspace unmount", async ({ page }) => {
  await mockBase(page);
  await page.addInitScript(({ activeKey }) => {
    localStorage.setItem(activeKey, "walk-forward");
    const realFetch = window.fetch.bind(window);
    window.__resolveLateLibraryConnect = null;
    window.fetch = (input, init = {}) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.includes("/api/v1/research/runs?limit=100")) {
        return new Promise((resolve) => {
          window.__resolveLateLibraryConnect = () => resolve(new Response(JSON.stringify({
            contractVersion: "research-run-memory-2026-08-17.1",
            libraryId: "lib_late_connect",
            runs: [],
          }), { status: 200, headers: { "content-type": "application/json" } }));
        });
      }
      return realFetch(input, init);
    };
  }, { activeKey: ACTIVE_WORKSPACE_KEY });

  await page.goto("/portfolio/");
  await expect(page.getByRole("heading", { name: "Research Library" })).toBeVisible();
  await expect(page.getByText("Durable memory 正常")).toBeVisible();

  await page.getByLabel("匯入 Research Library 復原碼").fill(CAPABILITY);
  await page.getByRole("button", { name: "連結研究庫", exact: true }).click();
  await expect(page.getByRole("button", { name: "驗證復原碼…", exact: true })).toBeVisible();

  await page.getByRole("button", { name: /投資組合回測/u }).click();
  await expect(page.getByRole("heading", { name: "Research Library" })).toHaveCount(0);
  await page.evaluate(() => window.__resolveLateLibraryConnect?.());
  await page.waitForTimeout(150);

  expect(await page.evaluate((key) => localStorage.getItem(key), CAPABILITY_KEY)).toBeNull();

  await page.getByRole("button", { name: /因果樣本外研究/u }).click();
  await expect(page.getByRole("heading", { name: "Research Library" })).toBeVisible();
  await expect(page.getByLabel("匯入 Research Library 復原碼")).toBeVisible();
  await expect(page.getByText(/尚未連結 Research Library/u)).toBeVisible();
});
