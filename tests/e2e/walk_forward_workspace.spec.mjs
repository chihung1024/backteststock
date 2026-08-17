import { expect, test } from "@playwright/test";

async function mockHealth(page) {
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
}

function completedResult(request) {
  const period = request.periods[0];
  return {
    contractVersion: "walk-forward-job-2026-08-15.1",
    jobHash: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    hashAlgorithm: "sha256-canonical-json-v1",
    status: "completed",
    asOfDate: "2026-08-16",
    asOfPolicy: "last_complete_utc_calendar_day-v1",
    selectorPolicy: "exhaustive-gross-buy-and-hold-v1",
    oosPolicy: "decision-transition-cost-only-v1",
    request,
    periods: [
      {
        period_id: period.periodId,
        pit_member_count: 30,
        exhaustive_combination_count: 435,
        training_dataset_hash: "training-hash",
        authority_dataset_hash: "authority-hash",
        decision_hash: "decision-hash-1",
        evaluation_dataset_hash: "evaluation-hash",
      },
    ],
    decisions: [
      {
        contractVersion: "walk-forward-temporal-2026-08-15.1",
        hashAlgorithm: "sha256-canonical-json-v1",
        period: {
          ...period,
          decisionTiming: "after_close",
        },
        pitUniverse: {
          universeId: request.selector.universe,
          requestedAsOf: period.decisionDate,
          sourceAsOf: period.decisionDate,
          evidenceAvailableAsOf: period.decisionDate,
          fetchedAt: `${period.decisionDate}T00:00:00Z`,
          version: "pit-v1",
          checksum: "checksum",
          members: ["AAA", "BBB", "CCC"],
          membershipPolicy: "authoritative-test",
          membershipAuthoritative: true,
          sourceLabel: "test",
          sourceUrl: "https://example.test",
          sourceIsProxy: false,
        },
        trainingDataset: {
          datasetHash: "training-hash",
          effectiveStart: period.trainingStart,
          effectiveEnd: period.trainingEnd,
        },
        selector: {
          contractVersion: "selector-v1",
          rule: "exhaustive",
          parameters: {},
        },
        eligibleCandidates: ["AAA", "BBB", "CCC"],
        selectedConstituents: ["AAA", "BBB"],
        weights: [0.5, 0.5],
        decisionHash: "decision-hash-1",
      },
    ],
    oos: {
      contractVersion: "walk-forward-oos-ledger-2026-08-15.1",
      executionPolicy: "target-at-first-effective-oos-close-v1",
      gapPolicy: "carry-last-audited-state-flat-no-invented-return-v1",
      returnComponentPolicy: "research-total-return-reinvested-v1",
      periods: [
        {
          period_id: period.periodId,
          decision_hash: "decision-hash-1",
          evaluation_dataset_hash: "evaluation-hash",
          requested_start: period.evaluationStart,
          requested_end: period.evaluationEnd,
          effective_start: period.evaluationStart,
          effective_end: period.evaluationEnd,
          selected_constituents: ["AAA", "BBB"],
          weights: [0.5, 0.5],
          transition_traded_notional: 0,
          transition_cost: 0,
        },
      ],
      ledger: {
        contractVersion: "portfolio-ledger-v3",
        valuationCurrency: "TWD",
        equity: [
          { date: period.evaluationStart, value: 100000 },
          { date: period.evaluationEnd, value: 112500 },
        ],
        returnIndex: [
          { date: period.evaluationStart, value: 1 },
          { date: period.evaluationEnd, value: 1.125 },
        ],
        transactionCosts: 125,
        borrowingCosts: 0,
        rebalanceCount: 0,
        liquidated: false,
        warnings: [],
        events: [],
      },
      metrics: {
        metrics: {
          initial_balance: 100000,
          final_balance: 112500,
          total_return: 0.125,
          cagr: 0.12,
          sortino_ratio: 1.75,
          max_drawdown: -0.08,
          transaction_costs: 125,
          observations: 120,
          start: period.evaluationStart,
          end: period.evaluationEnd,
        },
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

async function openWalkForwardWorkspace(page) {
  await page.goto("/portfolio/");
  await page.locator(".workspace-switch button").filter({ hasText: "Walk-Forward Research" }).click();
  await expect(page.getByRole("heading", { name: "Walk-Forward 研究工作區" })).toBeVisible();
}

async function mockCompletedWalkForward(page) {
  let capturedRequest = null;
  await page.route("**/api/v1/research/walk-forward", async (route) => {
    capturedRequest = route.request().postDataJSON();
    await route.fulfill({ json: completedResult(capturedRequest) });
  });
  return () => capturedRequest;
}

test("Walk-Forward settings expose causal API inputs and fail closed before request generation", async ({ page }) => {
  await mockHealth(page);
  await openWalkForwardWorkspace(page);

  await expect(page.getByText("Walk-Forward API 正常")).toBeVisible();
  await expect(page.getByText("因果設定有效")).toBeVisible();
  await expect(page.getByLabel("Walk-Forward Universe")).toHaveValue("sp500");
  await expect(page.getByLabel("Walk-Forward Benchmark")).toHaveValue("SPY");
  await expect(page.getByLabel("Walk-Forward 持股檔數")).toHaveValue("10");

  await page.getByText("查看標準化 API Request").click();
  const requestPreview = page.locator(".wf-request-preview pre");
  await expect(requestPreview).toContainText('"universe": "sp500"');
  await expect(requestPreview).toContainText('"benchmark": "SPY"');
  await expect(requestPreview).toContainText('"holdingCount": 10');
  await expect(requestPreview).toContainText('"initialAmountTwd": 100000');

  const holdingCount = page.getByLabel("Walk-Forward 持股檔數");
  await holdingCount.fill("21");
  await expect(page.getByText("持股檔數必須是 1–20 的整數。")).toBeVisible();
  await expect(page.getByRole("button", { name: "複製 Request" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "執行研究" })).toBeDisabled();
  await holdingCount.fill("10");

  const decision = page.getByLabel("Period 1 Decision 日期");
  const evaluationStart = page.getByLabel("Period 1 Evaluation 起始日");
  const validEvaluationStart = await evaluationStart.inputValue();
  await evaluationStart.fill(await decision.inputValue());
  await expect(page.getByText("period-1：Evaluation 起始日必須嚴格晚於 Decision 日期。")).toBeVisible();
  await evaluationStart.fill(validEvaluationStart);
  await expect(page.getByText("因果設定有效")).toBeVisible();
});

test("Walk-Forward execution posts the normalized request and renders authoritative OOS results", async ({ page }) => {
  await mockHealth(page);
  const requestSnapshot = await mockCompletedWalkForward(page);
  await openWalkForwardWorkspace(page);

  await page.getByRole("button", { name: "執行研究" }).click();
  await expect(page.getByRole("heading", { name: "Continuous OOS 結果" })).toBeVisible();

  const capturedRequest = requestSnapshot();
  expect(capturedRequest.selector).toEqual({ universe: "sp500", benchmark: "SPY", holdingCount: 10 });
  expect(capturedRequest.execution).toEqual({ initialAmountTwd: 100000, transitionCostBps: 5 });
  expect(capturedRequest.periods).toHaveLength(1);
  expect(capturedRequest.periods[0].evaluationStart > capturedRequest.periods[0].decisionDate).toBe(true);

  await expect(page.getByText("112,500")).toBeVisible();
  await expect(page.getByText("12.00%")).toBeVisible();
  await expect(page.getByText("1.750")).toBeVisible();
  await expect(page.getByText("-8.00%")).toBeVisible();
  await expect(page.getByText("AAA 50.00% · BBB 50.00%")).toBeVisible();
  await expect(page.getByText("job 0123456789…89abcdef")).toBeVisible();
  await expect(page.getByRole("img", { name: "Walk-Forward continuous OOS equity" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Walk-Forward continuous OOS return index" })).toBeVisible();
  await expect(page.getByText("目前 Walk-Forward v1 response 沒有獨立的 continuous OOS benchmark series")).toBeVisible();
  await expect(page.getByText("Authoritative", { exact: true })).toBeVisible();
  await expect(page.getByText("435", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "匯出結果 JSON" })).toBeVisible();

  await page.getByText("查看完整 provenance").click();
  const provenance = page.locator(".wf-provenance-detail-grid");
  await expect(provenance.getByText("pit-v1", { exact: true })).toBeVisible();
  await expect(provenance.getByText("selector-v1", { exact: true })).toBeVisible();
  await expect(provenance.getByText("authority-hash", { exact: true })).toBeVisible();
  await expect(provenance.getByText("evaluation-hash", { exact: true })).toBeVisible();
});

test("Walk-Forward rate limiting is explained without retry loops", async ({ page }) => {
  await mockHealth(page);
  let calls = 0;
  await page.route("**/api/v1/research/walk-forward", async (route) => {
    calls += 1;
    await route.fulfill({
      status: 429,
      json: { detail: "Walk-Forward research rate limit exceeded. Try again in one minute." },
    });
  });
  await openWalkForwardWorkspace(page);

  await page.getByRole("button", { name: "執行研究" }).click();
  await expect(page.getByRole("alert")).toContainText("每分鐘最多 2 次");
  expect(calls).toBe(1);
});

test("cancelling a Walk-Forward request prevents a late response from becoming current evidence", async ({ page }) => {
  await mockHealth(page);
  await page.route("**/api/v1/research/walk-forward", async (route) => {
    const request = route.request().postDataJSON();
    await new Promise((resolve) => setTimeout(resolve, 700));
    await route.fulfill({ json: completedResult(request) });
  });
  await openWalkForwardWorkspace(page);

  await page.getByRole("button", { name: "執行研究" }).click();
  await expect(page.getByRole("button", { name: "取消" })).toBeVisible();
  await expect(page.getByText(/後端正在建立可重現的研究證據/u)).toBeVisible();
  await page.getByRole("button", { name: "取消" }).click();
  await expect(page.getByText(/已取消目前的 Walk-Forward 請求/u)).toBeVisible();
  await page.waitForTimeout(900);
  await expect(page.getByRole("heading", { name: "Continuous OOS 結果" })).toHaveCount(0);
});

test("Walk-Forward workspace persists selection and supports explicit multi-period editing", async ({ page }) => {
  await mockHealth(page);
  await openWalkForwardWorkspace(page);

  await page.getByRole("button", { name: "新增 Period" }).click();
  await expect(page.getByRole("heading", { name: "Period 2" })).toBeVisible();
  await expect(page.getByText("period-2：Training 起始日必須是有效日期。")).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Walk-Forward 研究工作區" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Period 2" })).toBeVisible();
});

test("390px Walk-Forward settings and results stay contained without page-level overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockHealth(page);
  await mockCompletedWalkForward(page);
  await openWalkForwardWorkspace(page);

  await expect(page.getByLabel("Period 1 Training 起始日")).toBeVisible();
  await expect(page.getByLabel("Period 1 Decision 日期")).toBeVisible();
  await expect(page.getByLabel("Period 1 Evaluation 結束日")).toBeVisible();
  await page.getByRole("button", { name: "執行研究" }).click();
  await expect(page.getByRole("heading", { name: "Continuous OOS 結果" })).toBeVisible();
  await expect(page.getByText("AAA 50.00% · BBB 50.00%")).toBeVisible();
  await expect(page.getByRole("img", { name: "Walk-Forward continuous OOS equity" })).toBeVisible();

  const overflows = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflows).toBe(false);
});
