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
        api_contract_version: "walk-forward-api-2026-08-18.4",
        job_contract_version: "walk-forward-job-2026-08-15.1",
        dual_momentum_job_contract_version: "walk-forward-dual-momentum-job-2026-08-17.1",
        dual_momentum_allocation_job_contract_version: "walk-forward-dual-momentum-allocation-job-2026-08-17.1",
        dual_momentum_parameter_optimization_job_contract_version: "walk-forward-dual-momentum-parameter-optimization-job-2026-08-18.1",
        deployment_sha: "test",
      },
    }),
  );
}

function tuningEvidence(period) {
  const folds = [1, 2, 3].map((index) => ({
    periodId: `inner-${index}`,
    trainingStart: "2024-01-01",
    trainingEnd: `2026-0${index + 2}-31`,
    decisionDate: `2026-0${index + 2}-31`,
    evaluationStart: `2026-0${index + 3}-01`,
    evaluationEnd: `2026-0${index + 3}-30`,
    decisionTiming: "after_close",
  }));
  return {
    contractVersion: "optimizer-hub-parameter-tuning-result-2026-08-18.1",
    tuningContractVersion: "optimizer-hub-parameter-optimization-2026-08-18.1",
    objectivePolicyVersion: "inner-oos-sortino-lexicographic-v1",
    outerTrainingDatasetHash: "outer-training-auto-hash",
    innerFoldSchedule: {
      contractVersion: "optimizer-hub-inner-fold-schedule-2026-08-18.1",
      calendarPolicy: "completed-calendar-month-buckets-v1",
      periods: folds,
      innerFoldScheduleHash: "inner-fold-schedule-hash",
    },
    searchPlanHash: "search-plan-hash-0123456789abcdef",
    candidateCount: 2,
    candidates: [
      {
        parameterHash: "winner-parameter-hash-0123456789abcdef",
        parameters: {
          lookbackMonths: 12,
          topK: 1,
          absoluteThreshold: 0,
          allocationMethod: "equal",
        },
        status: "eligible",
        completedFoldCount: 3,
        failedFold: null,
        failureReason: null,
        innerOosMetricSummary: {
          sortino: 1.82,
          maxDrawdown: -0.07,
          cagr: 0.16,
          transactionCosts: 120,
        },
        innerOosIdentity: "winner-inner-oos-hash",
        decisionHashes: ["inner-decision-1", "inner-decision-2", "inner-decision-3"],
        evaluationDatasetHashes: ["inner-eval-1", "inner-eval-2", "inner-eval-3"],
      },
      {
        parameterHash: "failed-parameter-hash-0123456789abcdef",
        parameters: {
          lookbackMonths: 6,
          topK: 3,
          absoluteThreshold: 0,
          allocationMethod: "risk_parity_erc",
        },
        status: "failed",
        completedFoldCount: 1,
        failedFold: "inner-2",
        failureReason: "insufficient complete-case covariance evidence",
        innerOosMetricSummary: {
          sortino: null,
          maxDrawdown: null,
          cagr: null,
          transactionCosts: null,
        },
        innerOosIdentity: null,
        decisionHashes: ["inner-failed-decision-1"],
        evaluationDatasetHashes: ["inner-failed-eval-1"],
      },
    ],
    winnerParameterHash: "winner-parameter-hash-0123456789abcdef",
    winnerParameters: {
      lookbackMonths: 12,
      topK: 1,
      absoluteThreshold: 0,
      allocationMethod: "equal",
    },
    winnerRank: 1,
    resultHash: "tuning-result-hash-0123456789abcdef",
    period,
  };
}

function autoResult(request) {
  const period = request.periods[0];
  const members = [...request.selector.riskySymbols, ...request.selector.defensiveSymbols];
  const tuning = tuningEvidence(period);
  const selected = [request.selector.riskySymbols[0]];
  return {
    contractVersion: "walk-forward-dual-momentum-parameter-optimization-job-2026-08-18.1",
    jobHash: "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
    hashAlgorithm: "sha256-canonical-json-v1",
    status: "completed",
    asOfDate: period.evaluationEnd,
    asOfPolicy: "last_complete_utc_calendar_day-v1",
    selectorPolicy: "dual-momentum-nested-parameter-optimization-v1",
    oosPolicy: "decision-transition-cost-only-v1",
    request,
    periods: [{
      period_id: period.periodId,
      configured_member_count: members.length,
      training_dataset_hash: "outer-training-auto-hash",
      decision_hash: "outer-decision-auto-hash",
      evaluation_dataset_hash: "outer-evaluation-auto-hash",
      tuning_result_hash: tuning.resultHash,
      search_plan_hash: tuning.searchPlanHash,
      winner_parameter_hash: tuning.winnerParameterHash,
    }],
    decisions: [{
      contractVersion: "walk-forward-configured-decision-2026-08-17.1",
      hashAlgorithm: "sha256-canonical-json-v1",
      period: { ...period, decisionTiming: "after_close" },
      configuredUniverse: {
        contractVersion: "configured-research-universe-2026-08-17.1",
        provenanceType: "configured-request",
        members,
        universeHash: "configured-auto-universe-hash",
      },
      trainingDataset: {
        datasetHash: "outer-training-auto-hash",
        effectiveStart: period.trainingStart,
        effectiveEnd: period.trainingEnd,
      },
      selector: {
        contractVersion: "walk-forward-configured-selection-2026-08-17.1+optimizer-hub-parameter-optimization-2026-08-18.1",
        rule: "nested-parameter-optimization-then-full-outer-training-refit-v1",
        parameters: tuning.winnerParameters,
      },
      selectionEvidence: {
        contractVersion: "momentum-twd-total-return-2026-08-17.1",
        signalAsOf: period.trainingEnd,
        lookbackMonths: 12,
        absoluteThreshold: 0,
        signalAuthority: "ResearchDataset.daily_levels_twd",
        regime: "risk_on",
        fallbackReason: null,
        riskyRanking: [{
          symbol: selected[0],
          lookbackMonths: 12,
          requestedStart: period.trainingStart,
          baselineDate: period.trainingStart,
          endDate: period.trainingEnd,
          baselineLevelTwd: 100,
          endLevelTwd: 140,
          totalReturn: 0.4,
          relativeRank: 1,
          absolutePass: true,
        }],
        defensiveRanking: [],
        selected,
        allocation: {
          contractVersion: "optimizer-hub-allocation-twd-2026-08-17.1",
          riskMathContractVersion: "risk-math-twd-2026-08-09.1",
          method: "equal",
          symbols: selected,
          weights: [1],
          status: "single_asset",
          inputObservations: 0,
          completeCaseObservations: 0,
          minimumCompleteCaseObservations: 60,
          returnFrequency: "daily",
          valuationCurrency: "TWD",
          covariance: null,
          portfolioVolatility: null,
          componentRisk: null,
          riskBudgetShares: null,
          solver: null,
        },
        parameterOptimization: tuning,
        parameterOptimizationRefit: {
          policy: "winner-parameters-refit-on-full-outer-training-v1",
          outerTrainingDatasetHash: "outer-training-auto-hash",
          winnerParameterHash: tuning.winnerParameterHash,
        },
      },
      eligibleCandidates: members,
      selectedConstituents: selected,
      weights: [1],
      decisionHash: "outer-decision-auto-hash",
    }],
    oos: {
      contractVersion: "walk-forward-oos-ledger-2026-08-15.1",
      executionPolicy: "target-at-first-effective-oos-close-v1",
      gapPolicy: "carry-last-audited-state-flat-no-invented-return-v1",
      returnComponentPolicy: "research-total-return-reinvested-v1",
      periods: [{
        period_id: period.periodId,
        decision_hash: "outer-decision-auto-hash",
        evaluation_dataset_hash: "outer-evaluation-auto-hash",
        requested_start: period.evaluationStart,
        requested_end: period.evaluationEnd,
        effective_start: period.evaluationStart,
        effective_end: period.evaluationEnd,
        selected_constituents: selected,
        weights: [1],
        transition_traded_notional: 100000,
        transition_cost: 50,
      }],
      ledger: {
        contractVersion: "portfolio-ledger-v3",
        valuationCurrency: "TWD",
        equity: [
          { date: period.evaluationStart, value: 99950 },
          { date: period.evaluationEnd, value: 105000 },
        ],
        returnIndex: [
          { date: period.evaluationStart, value: 0.9995 },
          { date: period.evaluationEnd, value: 1.05 },
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
          final_balance: 105000,
          total_return: 0.05,
          cagr: 0.08,
          sortino_ratio: 1.4,
          max_drawdown: -0.04,
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

test("Auto Optimize sends only nested tuning authority and renders backend winner evidence", async ({ page }) => {
  await mockHealth(page);
  let capturedRequest = null;
  await page.route("**/api/v1/research/walk-forward", async (route) => {
    capturedRequest = route.request().postDataJSON();
    await route.fulfill({ json: autoResult(capturedRequest) });
  });

  await openWorkspace(page);
  await page.getByRole("button", { name: "載入 Dual Momentum 範例" }).click();
  await page.getByLabel("Dual Momentum Optimization Mode").selectOption("auto");

  await expect(page.getByLabel("Dual Momentum Lookback 月數")).toBeDisabled();
  await expect(page.getByLabel("Dual Momentum Top K")).toBeDisabled();
  await expect(page.getByLabel("Dual Momentum Allocation Method")).toBeDisabled();
  await expect(page.getByLabel("Dual Momentum Absolute Threshold")).toBeDisabled();
  await expect(page.getByText("12 candidates × 3 folds × 6 outer periods = 216 tuning evaluations")).toBeVisible();

  await page.getByRole("button", { name: "產生最近 6 個月" }).click();
  await expect(page.getByText("因果設定有效")).toBeVisible();
  await page.getByText("查看標準化 API Request").click();
  const preview = page.locator(".wf-request-preview pre");
  await expect(preview).toContainText('"parameterOptimization"');
  await expect(preview).toContainText('"lookbackMonths": [');
  await expect(preview).toContainText('"allocationMethods": [');
  await expect(preview).not.toContainText('"allocationMethod":');
  await expect(preview).not.toContainText('"absoluteThreshold":');

  await page.getByRole("button", { name: "執行研究" }).click();
  await expect(page.getByRole("heading", { name: "Continuous OOS 結果" })).toBeVisible();

  expect(capturedRequest.selector.strategy).toBe("dual_momentum");
  expect(capturedRequest.selector.parameterOptimization).toEqual({
    searchSpace: {
      lookbackMonths: [6, 12],
      topK: [1, 3],
      absoluteThresholds: [0],
      allocationMethods: ["equal", "inverse_volatility", "risk_parity_erc"],
    },
    innerValidation: { foldCount: 3, evaluationMonths: 1, stepMonths: 1 },
  });
  expect("lookbackMonths" in capturedRequest.selector).toBe(false);
  expect("topK" in capturedRequest.selector).toBe(false);
  expect("absoluteThreshold" in capturedRequest.selector).toBe(false);
  expect("allocationMethod" in capturedRequest.selector).toBe(false);

  const tuningPanel = page.locator(".wf-optimization-evidence");
  await expect(tuningPanel.getByRole("heading", { name: "Nested parameter optimization evidence" })).toBeVisible();
  await expect(tuningPanel.getByText("Winner 由後端 inner-OOS authority 決定")).toBeVisible();
  await expect(tuningPanel.getByText("1.820", { exact: true })).toBeVisible();
  await expect(tuningPanel.getByText("-7.00%", { exact: true })).toBeVisible();
  await expect(tuningPanel.getByText("insufficient complete-case covariance evidence", { exact: false })).toBeVisible();
  await expect(tuningPanel.getByText("LB 12m · K 1 · Hurdle 0.00% · equal", { exact: false })).toBeVisible();

  await tuningPanel.getByText("查看 inner-fold / refit identity").click();
  await expect(tuningPanel.getByText("completed-calendar-month-buckets-v1", { exact: true })).toBeVisible();
  await expect(tuningPanel.getByText("winner-parameters-refit-on-full-outer-training-v1", { exact: true })).toBeVisible();
});
