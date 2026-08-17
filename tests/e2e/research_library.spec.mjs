import { expect, test } from "@playwright/test";

const CAPABILITY = `rrl_${"A".repeat(43)}`;
const OTHER_CAPABILITY = `rrl_${"B".repeat(43)}`;
const ACTIVE_WORKSPACE_KEY = "backteststock.portfolio.active-workspace.v1";
const CAPABILITY_KEY = "backteststock.research-library.capability.v1";

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

function completedResult(request, jobHash = "0".repeat(64)) {
  const period = request.periods[0];
  return {
    contractVersion: "walk-forward-job-2026-08-15.1",
    jobHash,
    hashAlgorithm: "sha256-canonical-json-v1",
    status: "completed",
    asOfDate: "2026-08-16",
    asOfPolicy: "last_complete_utc_calendar_day-v1",
    selectorPolicy: "exhaustive-gross-buy-and-hold-v1",
    oosPolicy: "decision-transition-cost-only-v1",
    request,
    periods: [{
      period_id: period.periodId,
      pit_member_count: 30,
      exhaustive_combination_count: 142506,
      training_dataset_hash: "training-hash",
      authority_dataset_hash: "authority-hash",
      decision_hash: "decision-hash-1",
      evaluation_dataset_hash: "evaluation-hash",
    }],
    decisions: [{
      contractVersion: "walk-forward-temporal-2026-08-15.1",
      period: { ...period, decisionTiming: "after_close" },
      pitUniverse: {
        universeId: request.selector.universe,
        requestedAsOf: period.decisionDate,
        sourceAsOf: period.decisionDate,
        evidenceAvailableAsOf: period.decisionDate,
        fetchedAt: `${period.decisionDate}T00:00:00Z`,
        version: "pit-v1",
        checksum: "checksum",
        members: ["AMD", "ASX", "MU", "TSM", "UMC"],
        membershipPolicy: "authoritative-test",
        membershipAuthoritative: true,
        sourceLabel: "test",
        sourceUrl: "https://example.test",
        sourceIsProxy: false,
      },
      trainingDataset: { datasetHash: "training-hash", effectiveStart: period.trainingStart, effectiveEnd: period.trainingEnd },
      selector: { contractVersion: "selector-v1", rule: "exhaustive", parameters: {} },
      eligibleCandidates: ["AMD", "ASX", "MU", "TSM", "UMC"],
      selectedConstituents: ["AMD", "ASX", "MU", "TSM", "UMC"],
      weights: [0.2, 0.2, 0.2, 0.2, 0.2],
      decisionHash: "decision-hash-1",
    }],
    oos: {
      contractVersion: "walk-forward-oos-ledger-2026-08-15.1",
      executionPolicy: "target-at-first-effective-oos-close-v1",
      gapPolicy: "carry-last-audited-state-flat-no-invented-return-v1",
      returnComponentPolicy: "research-total-return-reinvested-v1",
      periods: [{
        period_id: period.periodId,
        decision_hash: "decision-hash-1",
        evaluation_dataset_hash: "evaluation-hash",
        requested_start: period.evaluationStart,
        requested_end: period.evaluationEnd,
        effective_start: period.evaluationStart,
        effective_end: period.evaluationEnd,
        selected_constituents: ["AMD", "ASX", "MU", "TSM", "UMC"],
        weights: [0.2, 0.2, 0.2, 0.2, 0.2],
        transition_traded_notional: 0,
        transition_cost: 0,
      }],
      ledger: {
        contractVersion: "portfolio-ledger-v3",
        valuationCurrency: "TWD",
        equity: [{ date: period.evaluationStart, value: 100000 }, { date: period.evaluationEnd, value: 106000 }],
        returnIndex: [{ date: period.evaluationStart, value: 1 }, { date: period.evaluationEnd, value: 1.06 }],
        transactionCosts: 50,
        borrowingCosts: 0,
        rebalanceCount: 0,
        liquidated: false,
        warnings: [],
        events: [],
      },
      metrics: {
        metrics: { initial_balance: 100000, final_balance: 106000, total_return: 0.06, cagr: 0.08, sortino_ratio: 1.4, max_drawdown: -0.04, transaction_costs: 50 },
        xirr: {},
        tail_risk: {},
        drawdown_events: [],
        annual_returns: [],
        monthly_returns: [],
        metadata: {},
      },
    },
  };
}

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

async function openWalkForward(page, capability = null) {
  await page.addInitScript(({ activeKey, capabilityKey, capabilityValue }) => {
    localStorage.setItem(activeKey, "walk-forward");
    if (capabilityValue) localStorage.setItem(capabilityKey, capabilityValue);
    else localStorage.removeItem(capabilityKey);
  }, { activeKey: ACTIVE_WORKSPACE_KEY, capabilityKey: CAPABILITY_KEY, capabilityValue: capability });
  await page.goto("/portfolio/");
  await expect(page.getByRole("heading", { name: "Walk-Forward 研究工作區" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Research Library" })).toBeVisible();
}

function runSummary(runId, name = "Saved baseline", jobHash = "0".repeat(64), sourceRunId = null) {
  return {
    runId,
    sourceRunId,
    name,
    jobHash,
    resultContractVersion: "walk-forward-job-2026-08-15.1",
    decisionCount: 1,
    createdAt: "2026-08-17 05:00:00",
  };
}

test("first save sends only name/request, creates credential, and renders backend-completed result", async ({ page }) => {
  await mockBase(page);
  let capturedBody = null;
  let capturedAuthorization = "unset";
  let savedRequest = null;
  const savedRun = runSummary("run_11111111-1111-4111-8111-111111111111");

  await page.route("**/api/v1/research/runs?limit=100", (route) => route.fulfill({
    json: { contractVersion: "research-run-memory-2026-08-17.1", libraryId: "lib_test", runs: [savedRun] },
  }));
  await page.route("**/api/v1/research/runs", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    capturedBody = route.request().postDataJSON();
    capturedAuthorization = route.request().headers().authorization ?? null;
    savedRequest = capturedBody.request;
    await route.fulfill({
      status: 201,
      json: {
        contractVersion: "research-run-memory-2026-08-17.1",
        libraryId: "lib_test",
        libraryCapability: CAPABILITY,
        run: savedRun,
        result: completedResult(savedRequest),
      },
    });
  });

  await openWalkForward(page);
  await expect(page.getByText("Durable memory 正常")).toBeVisible();
  await page.getByLabel("ResearchRun 研究名稱").fill("Saved baseline");
  await page.getByRole("button", { name: "執行並保存", exact: true }).click();

  await expect(page.getByText("新研究庫已建立：請立即備份復原碼")).toBeVisible();
  await expect(page.getByText(/Saved baseline/u)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Continuous OOS 結果" })).toBeVisible();
  expect(capturedAuthorization).toBeNull();
  expect(Object.keys(capturedBody).sort()).toEqual(["name", "request"]);
  expect(capturedBody.name).toBe("Saved baseline");
  expect(capturedBody.request.selector).toEqual({ universe: "soxx", benchmark: "SPY", holdingCount: 5 });
  expect("result" in capturedBody).toBe(false);
  expect("jobHash" in capturedBody).toBe(false);

  const stored = await page.evaluate((key) => localStorage.getItem(key), CAPABILITY_KEY);
  expect(stored).toBe(CAPABILITY);
  await expect(page.getByLabel("Research Library 復原碼")).not.toContainText(CAPABILITY);
});

test("saved result loads without Walk-Forward rerun and server rerun receives no replacement request", async ({ page }) => {
  await mockBase(page);
  const sourceRun = runSummary("run_22222222-2222-4222-8222-222222222222", "Historical SOXX", "1".repeat(64));
  const rerun = runSummary("run_33333333-3333-4333-8333-333333333333", "Historical SOXX", "1".repeat(64), sourceRun.runId);
  const request = {
    periods: [{ periodId: "period-1", trainingStart: "2024-07-29", trainingEnd: "2026-07-29", decisionDate: "2026-07-29", evaluationStart: "2026-07-30", evaluationEnd: "2026-08-16" }],
    selector: { universe: "soxx", benchmark: "SPY", holdingCount: 5 },
    execution: { initialAmountTwd: 100000, transitionCostBps: 5 },
  };
  let directWalkForwardCalls = 0;
  let rerunBody = "unset";
  let rerunAuthorization = null;

  await page.route("**/api/v1/research/walk-forward", (route) => {
    directWalkForwardCalls += 1;
    return route.fulfill({ status: 500, json: { error: "must not be called" } });
  });
  await page.route("**/api/v1/research/runs?limit=100", (route) => route.fulfill({
    json: { contractVersion: "research-run-memory-2026-08-17.1", libraryId: "lib_existing", runs: [sourceRun] },
  }));
  await page.route(`**/api/v1/research/runs/${sourceRun.runId}`, (route) => route.fulfill({
    json: {
      contractVersion: "research-run-memory-2026-08-17.1",
      libraryId: "lib_existing",
      run: sourceRun,
      executionRequest: request,
      result: completedResult(request, sourceRun.jobHash),
    },
  }));
  await page.route(`**/api/v1/research/runs/${sourceRun.runId}/rerun`, async (route) => {
    rerunBody = route.request().postData();
    rerunAuthorization = route.request().headers().authorization ?? null;
    await route.fulfill({
      status: 201,
      json: {
        contractVersion: "research-run-memory-2026-08-17.1",
        libraryId: "lib_existing",
        run: rerun,
        result: completedResult(request, rerun.jobHash),
      },
    });
  });

  await openWalkForward(page, CAPABILITY);
  await expect(page.getByText("Historical SOXX", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "查看保存結果" }).click();
  await expect(page.getByText(/已從 D1 讀取/u)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Continuous OOS 結果" })).toBeVisible();
  expect(directWalkForwardCalls).toBe(0);

  await page.getByRole("button", { name: "用原 Request 重跑" }).first().click();
  await expect(page.getByText(/使用 D1 保存的原始 request/u)).toBeVisible();
  expect(rerunBody).toBeNull();
  expect(rerunAuthorization).toBe(`Bearer ${CAPABILITY}`);
  expect(directWalkForwardCalls).toBe(0);
  await expect(page.getByText(/rerun of/u)).toBeVisible();
});

test("recovery-code import is validated server-side before browser persistence, and forget-device does not claim deletion", async ({ page }) => {
  await mockBase(page);
  let attempts = 0;
  await page.route("**/api/v1/research/runs?limit=100", async (route) => {
    attempts += 1;
    const authorization = route.request().headers().authorization;
    if (authorization === `Bearer ${OTHER_CAPABILITY}`) {
      return route.fulfill({ status: 401, json: { error: "invalid capability" } });
    }
    return route.fulfill({
      json: { contractVersion: "research-run-memory-2026-08-17.1", libraryId: "lib_test", runs: [] },
    });
  });

  await openWalkForward(page);
  const input = page.getByLabel("匯入 Research Library 復原碼");
  await input.fill(OTHER_CAPABILITY);
  await page.getByRole("button", { name: "連結研究庫" }).click();
  await expect(page.getByText(/復原碼無效/u)).toBeVisible();
  expect(await page.evaluate((key) => localStorage.getItem(key), CAPABILITY_KEY)).toBeNull();

  await input.fill(CAPABILITY);
  await page.getByRole("button", { name: "連結研究庫" }).click();
  await expect(page.getByText(/已連結研究庫/u)).toBeVisible();
  expect(await page.evaluate((key) => localStorage.getItem(key), CAPABILITY_KEY)).toBe(CAPABILITY);

  await page.getByRole("button", { name: "忘記此裝置" }).click();
  await expect(page.getByText(/D1 中的研究沒有刪除/u)).toBeVisible();
  expect(await page.evaluate((key) => localStorage.getItem(key), CAPABILITY_KEY)).toBeNull();
  expect(attempts).toBeGreaterThanOrEqual(2);
});
