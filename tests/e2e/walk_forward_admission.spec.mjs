import { expect, test } from "@playwright/test";

const ADMISSION = {
  contractVersion: "walk-forward-admission-2026-08-17.1",
  asOfDate: "2026-08-16",
  limits: {
    maxCandidates: 100,
    maxCombinationsPerPeriod: 500000,
    maxHoldingCount: 20,
    pitMaxAgeDays: 10,
  },
  universes: [
    { id: "sp500", name: "S&P 500 proxy", status: "blocked", reason: "proxy_membership_only" },
    { id: "nasdaq100", name: "NASDAQ-100", status: "blocked", reason: "candidate_limit", minimumMemberCount: 102 },
    {
      id: "soxx",
      name: "SOXX",
      status: "eligible",
      earliestDecisionDate: "2026-07-29",
      latestDecisionDate: "2026-08-06",
      recommendedDecisionDate: "2026-07-29",
      recommendedMemberCount: 30,
      recommendedHoldingCount: 5,
      recommendedCombinationCount: 142506,
    },
  ],
  recommended: {
    universe: "soxx",
    decisionDate: "2026-07-29",
    holdingCount: 5,
    memberCount: 30,
    combinationCount: 142506,
  },
};

async function mockServices(page) {
  await page.route("**/api/v3/portfolio/health", (route) =>
    route.fulfill({ json: { status: "ok", service: "backteststock-portfolio-v3" } }),
  );
  await page.route("**/api/v1/research/walk-forward/health", (route) =>
    route.fulfill({
      json: {
        status: "ok",
        service: "backteststock-walk-forward-v1",
        api_contract_version: "walk-forward-api-2026-08-15.1",
        job_contract_version: "walk-forward-job-2026-08-15.1",
        deployment_sha: "test",
      },
    }),
  );
  await page.route("**/api/v1/research/walk-forward/admission", (route) =>
    route.fulfill({ json: ADMISSION }),
  );
}

function legacyImpossibleModel() {
  return {
    schemaVersion: 1,
    universe: "sp500",
    benchmark: "SPY",
    holdingCount: 10,
    initialAmountTwd: 100000,
    transitionCostBps: 5,
    periods: [
      {
        id: "legacy-period",
        periodId: "period-1",
        trainingStart: "2024-02-15",
        trainingEnd: "2026-02-15",
        decisionDate: "2026-02-15",
        evaluationStart: "2026-02-16",
        evaluationEnd: "2026-08-16",
      },
    ],
  };
}

test("admission upgrades the legacy impossible first-run model before Walk-Forward mounts", async ({ page }) => {
  await mockServices(page);
  await page.addInitScript((model) => {
    localStorage.setItem("backteststock.walk-forward.workspace.v1", JSON.stringify(model));
    localStorage.setItem("backteststock.portfolio.active-workspace.v1", "walk-forward");
  }, legacyImpossibleModel());

  await page.goto("/portfolio/");

  await expect(page.getByRole("heading", { name: "目前可執行範圍" })).toBeVisible();
  await expect(page.getByText("建議：SOXX · Decision 2026-07-29 · 5 檔")).toBeVisible();
  await expect(page.getByText(/SP500：目前只有 proxy 成分證據/u)).toBeVisible();
  await expect(page.getByText(/NASDAQ100：PIT candidates 超過同步研究上限/u)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Walk-Forward 研究工作區" })).toBeVisible();
  await expect(page.getByLabel("Walk-Forward Universe")).toHaveValue("soxx");
  await expect(page.getByLabel("Walk-Forward 持股檔數")).toHaveValue("5");
  await expect(page.getByLabel("Period 1 Decision 日期")).toHaveValue("2026-07-29");
  await expect(page.getByLabel("Period 1 Evaluation 起始日")).toHaveValue("2026-07-30");
  await expect(page.getByLabel("Period 1 Evaluation 結束日")).toHaveValue("2026-08-16");

  await page.getByText("查看標準化 API Request").click();
  const preview = page.locator(".wf-request-preview pre");
  await expect(preview).toContainText('"universe": "soxx"');
  await expect(preview).toContainText('"holdingCount": 5');
  await expect(preview).toContainText('"decisionDate": "2026-07-29"');
});

test("explicit admission action restores an executable model after manual edits", async ({ page }) => {
  await mockServices(page);
  await page.addInitScript(() => {
    localStorage.setItem("backteststock.portfolio.active-workspace.v1", "walk-forward");
  });
  await page.goto("/portfolio/");

  await expect(page.getByRole("heading", { name: "Walk-Forward 研究工作區" })).toBeVisible();
  const universe = page.getByLabel("Walk-Forward Universe");
  await universe.fill("sp500");
  await expect(universe).toHaveValue("sp500");

  await page.getByRole("button", { name: "套用可執行預設" }).click();
  await expect(universe).toHaveValue("soxx");
  await expect(page.getByLabel("Walk-Forward 持股檔數")).toHaveValue("5");
  await expect(page.getByLabel("Period 1 Decision 日期")).toHaveValue("2026-07-29");
});
