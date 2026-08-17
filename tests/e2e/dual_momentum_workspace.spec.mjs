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
        api_contract_version: "walk-forward-api-2026-08-17.2",
        job_contract_version: "walk-forward-job-2026-08-15.1",
        dual_momentum_job_contract_version: "walk-forward-dual-momentum-job-2026-08-17.1",
        deployment_sha: "test",
      },
    }),
  );
}

function dualMomentumResult(request) {
  const period = request.periods[0];
  const members = [...request.selector.riskySymbols, ...request.selector.defensiveSymbols];
  const riskyRanking = request.selector.riskySymbols.map((symbol, index) => ({
    symbol,
    lookbackMonths: request.selector.lookbackMonths,
    requestedStart: period.trainingStart,
    baselineDate: period.trainingStart,
    endDate: period.trainingEnd,
    baselineLevelTwd: 100,
    endLevelTwd: 155 - index * 8,
    totalReturn: 0.55 - index * 0.08,
    relativeRank: index + 1,
    absolutePass: true,
  }));
  const defensiveRanking = request.selector.defensiveSymbols.map((symbol, index) => ({
    symbol,
    lookbackMonths: request.selector.lookbackMonths,
    requestedStart: period.trainingStart,
    baselineDate: period.trainingStart,
    endDate: period.trainingEnd,
    baselineLevelTwd: 100,
    endLevelTwd: 106 - index,
    totalReturn: 0.06 - index * 0.01,
    relativeRank: index + 1,
  }));
  const selected = request.selector.riskySymbols.slice(0, request.selector.topK);
  const weights = selected.map(() => 1 / selected.length);
  return {
    contractVersion: "walk-forward-dual-momentum-job-2026-08-17.1",
    jobHash: "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
    hashAlgorithm: "sha256-canonical-json-v1",
    status: "completed",
    asOfDate: period.evaluationEnd,
    asOfPolicy: "last_complete_utc_calendar_day-v1",
    selectorPolicy: "dual-momentum-configured-monthly-v1",
    oosPolicy: "decision-transition-cost-only-v1",
    request,
    periods: [
      {
        period_id: period.periodId,
        configured_member_count: members.length,
        training_dataset_hash: "training-dual-hash",
        decision_hash: "decision-dual-hash",
        evaluation_dataset_hash: "evaluation-dual-hash",
      },
    ],
    decisions: [
      {
        contractVersion: "walk-forward-configured-decision-2026-08-17.1",
        hashAlgorithm: "sha256-canonical-json-v1",
        period: { ...period, decisionTiming: "after_close" },
        configuredUniverse: {
          contractVersion: "configured-research-universe-2026-08-17.1",
          provenanceType: "configured-request",
          members,
          universeHash: "configured-universe-hash-0123456789",
        },
        trainingDataset: {
          datasetHash: "training-dual-hash",
          effectiveStart: period.trainingStart,
          effectiveEnd: period.trainingEnd,
        },
        selector: {
          contractVersion: "walk-forward-configured-selection-2026-08-17.1+dual-momentum-selection-2026-08-17.1",
          rule: "absolute-filter-then-relative-top-k-with-defensive-fallback-v1",
          parameters: {
            lookbackMonths: request.selector.lookbackMonths,
            topK: request.selector.topK,
            absoluteThreshold: request.selector.absoluteThreshold,
            weighting: "equal",
          },
        },
        selectionEvidence: {
          contractVersion: "momentum-twd-total-return-2026-08-17.1",
          signalAsOf: period.trainingEnd,
          lookbackMonths: request.selector.lookbackMonths,
          absoluteThreshold: request.selector.absoluteThreshold,
          boundaryToleranceCalendarDays: 7,
          signalAuthority: "ResearchDataset.daily_levels_twd",
          regime: "risk_on",
          fallbackReason: null,
          riskyRanking,
          defensiveRanking,
          selected,
        },
        eligibleCandidates: members,
        selectedConstituents: selected,
        weights,
        decisionHash: "decision-dual-hash",
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
          decision_hash: "decision-dual-hash",
          evaluation_dataset_hash: "evaluation-dual-hash",
          requested_start: period.evaluationStart,
          requested_end: period.evaluationEnd,
          effective_start: period.evaluationStart,
          effective_end: period.evaluationEnd,
          selected_constituents: selected,
          weights,
          transition_traded_notional: 100000,
          transition_cost: 50,
        },
      ],
      ledger: {
        contractVersion: "portfolio-ledger-v3",
        valuationCurrency: "TWD",
        equity: [
          { date: period.evaluationStart, value: 99950 },
          { date: period.evaluationEnd, value: 108500 },
        ],
        returnIndex: [
          { date: period.evaluationStart, value: 0.9995 },
          { date: period.evaluationEnd, value: 1.085 },
        ],
        transactionCosts: 50,
        borrowingCosts: 0,
        rebalanceCount: 0,
        liquidated: false,
        warnings: [],
        events: [],
      },
      metrics: {
        metrics: {
          initial_balance: 100000,
          final_balance: 108500,
          total_return: 0.085,
          cagr: 0.11,
          sortino_ratio: 1.6,
          max_drawdown: -0.06,
          transaction_costs: 50,
          observations: 20,
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

async function openWorkspace(page) {
  await page.goto("/portfolio/");
  await page.locator(".workspace-switch button").filter({ hasText: "Walk-Forward Research" }).click();
  await expect(page.getByRole("heading", { name: "Walk-Forward 研究工作區" })).toBeVisible();
}

test("Dual Momentum workspace builds a causal monthly request and renders signal evidence", async ({ page }) => {
  await mockHealth(page);
  let capturedRequest = null;
  await page.route("**/api/v1/research/walk-forward", async (route) => {
    capturedRequest = route.request().postDataJSON();
    await route.fulfill({ json: dualMomentumResult(capturedRequest) });
  });
  await openWorkspace(page);

  await page.getByRole("button", { name: "載入 Dual Momentum 範例" }).click();
  await expect(page.getByLabel("Walk-Forward Strategy")).toHaveValue("dual_momentum");
  await expect(page.getByLabel("Dual Momentum 風險資產")).toHaveValue("QQQ, SMH, SPY, IWM, VEA, VWO");
  await expect(page.getByLabel("Dual Momentum 防禦資產")).toHaveValue("BIL");
  await expect(page.getByLabel("Dual Momentum Lookback 月數")).toHaveValue("12");
  await expect(page.getByLabel("Dual Momentum Top K")).toHaveValue("3");
  await expect(page.getByLabel("Dual Momentum Absolute Threshold")).toHaveValue("0");
  await expect(page.getByText("因果設定有效")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Period 6" })).toBeVisible();

  await page.getByText("查看標準化 API Request").click();
  const preview = page.locator(".wf-request-preview pre");
  await expect(preview).toContainText('"strategy": "dual_momentum"');
  await expect(preview).toContainText('"lookbackMonths": 12');
  await expect(preview).toContainText('"topK": 3');
  await expect(preview).toContainText('"absoluteThreshold": 0');
  await expect(preview).toContainText('"BIL"');

  await page.getByRole("button", { name: "執行研究" }).click();
  await expect(page.getByRole("heading", { name: "Continuous OOS 結果" })).toBeVisible();

  expect(capturedRequest.selector).toEqual({
    strategy: "dual_momentum",
    riskySymbols: ["QQQ", "SMH", "SPY", "IWM", "VEA", "VWO"],
    defensiveSymbols: ["BIL"],
    lookbackMonths: 12,
    topK: 3,
    absoluteThreshold: 0,
  });
  expect(capturedRequest.periods).toHaveLength(6);
  for (let index = 1; index < capturedRequest.periods.length; index += 1) {
    const previous = capturedRequest.periods[index - 1];
    const current = capturedRequest.periods[index];
    expect(previous.evaluationEnd).toBe(current.decisionDate);
    expect(current.evaluationStart > current.decisionDate).toBe(true);
  }

  await expect(page.getByText("Configured request", { exact: true })).toBeVisible();
  await expect(page.getByText("risk_on", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Risky relative momentum" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Defensive relative momentum" })).toBeVisible();
  await expect(page.getByText("QQQ 33.33% · SMH 33.33% · SPY 33.33%")).toBeVisible();
  await expect(page.getByText("55.00%")).toBeVisible();
  await expect(page.getByText("PASS", { exact: true })).toBeVisible();
  await expect(page.getByText("Dual Momentum authority boundary")).toBeVisible();

  await page.getByText("查看完整 provenance").click();
  const provenance = page.locator(".wf-provenance-detail-grid");
  await expect(provenance.getByText("configured-research-universe-2026-08-17.1", { exact: true })).toBeVisible();
  await expect(provenance.getByText("momentum-twd-total-return-2026-08-17.1", { exact: true })).toBeVisible();
  await expect(provenance.getByText("ResearchDataset.daily_levels_twd", { exact: true })).toBeVisible();
});
