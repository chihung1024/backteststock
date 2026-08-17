import { expect, test } from "@playwright/test";

const ACTIVE_WORKSPACE_KEY = "backteststock.portfolio.active-workspace.v1";

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

async function openWalkForward(page) {
  await page.addInitScript((key) => localStorage.setItem(key, "walk-forward"), ACTIVE_WORKSPACE_KEY);
  await page.goto("/portfolio/");
  await expect(page.getByRole("heading", { name: "Walk-Forward 研究工作區" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Research Library" })).toBeVisible();
  await expect(page.getByText("Durable memory 正常")).toBeVisible();
}

test("pending durable save locks admission remount and research inputs until browser waiting stops", async ({ page }) => {
  await mockBase(page);

  let releaseSave;
  let markStarted;
  const saveStarted = new Promise((resolve) => { markStarted = resolve; });
  const release = new Promise((resolve) => { releaseSave = resolve; });
  await page.route("**/api/v1/research/runs", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    markStarted();
    await release;
    await route.fulfill({ status: 503, json: { error: "test released after browser cancellation" } });
  });

  await openWalkForward(page);
  const admissionButton = page.getByRole("button", { name: "套用可執行預設" });
  const universe = page.getByLabel("Walk-Forward Universe");
  const decision = page.getByLabel("Period 1 Decision 日期");
  const directRun = page.getByRole("button", { name: "執行研究", exact: true });

  await page.getByRole("button", { name: "執行並保存", exact: true }).click();
  await saveStarted;

  await expect(admissionButton).toBeDisabled();
  await expect(universe).toBeDisabled();
  await expect(decision).toBeDisabled();
  await expect(directRun).toBeDisabled();
  await expect(page.getByRole("button", { name: "停止等待" })).toBeVisible();

  await page.getByRole("button", { name: "停止等待" }).click();
  releaseSave();

  await expect(page.getByText(/伺服器端研究可能仍已完成並保存/u)).toBeVisible();
  await expect(admissionButton).toBeEnabled();
  await expect(universe).toBeEnabled();
  await expect(decision).toBeEnabled();
  await expect(directRun).toBeEnabled();
});

test("Research Library remains usable without horizontal overflow at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockBase(page);
  await openWalkForward(page);

  await expect(page.getByRole("button", { name: "執行並保存", exact: true })).toBeVisible();
  await expect(page.getByLabel("匯入 Research Library 復原碼")).toBeVisible();
  await expect(page.getByText(/尚未連結 Research Library/u)).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
