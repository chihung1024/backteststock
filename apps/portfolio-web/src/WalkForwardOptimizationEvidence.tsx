import type { WalkForwardParameterOptimizationEvidence } from "./walkForwardTypes";

function shortHash(value: string | null | undefined): string {
  if (!value) return "—";
  return value.length > 20 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value;
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function formatRatio(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return value.toFixed(3);
}

function formatCurrency(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("zh-TW", {
    style: "currency",
    currency: "TWD",
    maximumFractionDigits: 0,
  }).format(value);
}

function parameterLabel(parameters: Record<string, unknown>): string {
  const lookback = parameters.lookbackMonths;
  const topK = parameters.topK;
  const threshold = parameters.absoluteThreshold;
  const allocation = parameters.allocationMethod;
  const thresholdLabel = typeof threshold === "number" && Number.isFinite(threshold)
    ? `${(threshold * 100).toFixed(2)}%`
    : "—";
  return `LB ${String(lookback ?? "—")}m · K ${String(topK ?? "—")} · Hurdle ${thresholdLabel} · ${String(allocation ?? "—")}`;
}

export function WalkForwardOptimizationEvidence({
  evidence,
  refit,
}: {
  evidence: WalkForwardParameterOptimizationEvidence;
  refit?: {
    policy: string;
    outerTrainingDatasetHash: string;
    winnerParameterHash: string;
  };
}) {
  const winner = evidence.candidates.find((candidate) => candidate.parameterHash === evidence.winnerParameterHash);
  const failedCount = evidence.candidates.filter((candidate) => candidate.status !== "eligible").length;

  return (
    <div className="wf-optimization-evidence">
      <h4>Nested parameter optimization evidence</h4>
      <div className="notice info wf-optimization-boundary">
        <strong>Winner 由後端 inner-OOS authority 決定</strong>
        <p>下表保留後端 canonical candidate order，瀏覽器不重新排序或重算 objective。正式 winner 只認 `winnerParameterHash`；winner 之後會在完整 Outer Training refit，再凍結為 outer Decision。</p>
      </div>

      <dl className="wf-provenance-grid">
        <div><dt>Candidates</dt><dd>{evidence.candidateCount}</dd></div>
        <div><dt>Failed candidates</dt><dd>{failedCount}</dd></div>
        <div><dt>Inner folds</dt><dd>{evidence.innerFoldSchedule.periods.length}</dd></div>
        <div><dt>Objective</dt><dd>{evidence.objectivePolicyVersion}</dd></div>
        <div><dt>Winner rank</dt><dd>{evidence.winnerRank}</dd></div>
        <div><dt>Winner</dt><dd title={evidence.winnerParameterHash}>{shortHash(evidence.winnerParameterHash)}</dd></div>
        <div><dt>Winner Sortino</dt><dd>{formatRatio(winner?.innerOosMetricSummary.sortino)}</dd></div>
        <div><dt>Winner MDD</dt><dd>{formatPercent(winner?.innerOosMetricSummary.maxDrawdown)}</dd></div>
        <div><dt>Winner CAGR</dt><dd>{formatPercent(winner?.innerOosMetricSummary.cagr)}</dd></div>
        <div><dt>Winner costs</dt><dd>{formatCurrency(winner?.innerOosMetricSummary.transactionCosts)}</dd></div>
        <div><dt>Search plan</dt><dd title={evidence.searchPlanHash}>{shortHash(evidence.searchPlanHash)}</dd></div>
        <div><dt>Tuning result</dt><dd title={evidence.resultHash}>{shortHash(evidence.resultHash)}</dd></div>
      </dl>

      <p className="wf-selected-assets"><strong>Winner parameters:</strong> {parameterLabel(evidence.winnerParameters)}</p>

      <div className="table-scroll wf-optimization-candidates">
        <table>
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Status</th>
              <th>Parameters</th>
              <th>Folds</th>
              <th>Sortino</th>
              <th>MDD</th>
              <th>CAGR</th>
              <th>Costs</th>
            </tr>
          </thead>
          <tbody>
            {evidence.candidates.map((candidate) => {
              const isWinner = candidate.parameterHash === evidence.winnerParameterHash;
              return (
                <tr key={candidate.parameterHash} className={isWinner ? "wf-optimization-winner" : undefined}>
                  <td title={candidate.parameterHash}><strong>{isWinner ? "Winner · " : ""}{shortHash(candidate.parameterHash)}</strong></td>
                  <td>{candidate.status}{candidate.failureReason ? ` · ${candidate.failureReason}` : ""}</td>
                  <td>{parameterLabel(candidate.parameters)}</td>
                  <td>{candidate.completedFoldCount}{candidate.failedFold ? ` · failed ${candidate.failedFold}` : ""}</td>
                  <td>{formatRatio(candidate.innerOosMetricSummary.sortino)}</td>
                  <td>{formatPercent(candidate.innerOosMetricSummary.maxDrawdown)}</td>
                  <td>{formatPercent(candidate.innerOosMetricSummary.cagr)}</td>
                  <td>{formatCurrency(candidate.innerOosMetricSummary.transactionCosts)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <details className="wf-evidence-details">
        <summary>查看 inner-fold / refit identity</summary>
        <div className="wf-provenance-detail-grid">
          <p><strong>Tuning contract</strong><span>{evidence.tuningContractVersion}</span></p>
          <p><strong>Result contract</strong><span>{evidence.contractVersion}</span></p>
          <p><strong>Calendar policy</strong><span>{evidence.innerFoldSchedule.calendarPolicy}</span></p>
          <p><strong>Inner schedule hash</strong><span>{evidence.innerFoldSchedule.innerFoldScheduleHash}</span></p>
          <p><strong>Outer Training hash</strong><span>{evidence.outerTrainingDatasetHash}</span></p>
          <p><strong>Refit policy</strong><span>{refit?.policy ?? "—"}</span></p>
          <p><strong>Refit Training hash</strong><span>{refit?.outerTrainingDatasetHash ?? "—"}</span></p>
          <p><strong>Refit winner hash</strong><span>{refit?.winnerParameterHash ?? "—"}</span></p>
        </div>
        <div className="wf-optimization-folds">
          {evidence.innerFoldSchedule.periods.map((period) => (
            <p key={period.periodId}>
              <strong>{period.periodId}</strong>
              <span>Training {period.trainingStart} → {period.trainingEnd} · Decision {period.decisionDate} · Inner OOS {period.evaluationStart} → {period.evaluationEnd}</span>
            </p>
          ))}
        </div>
      </details>
    </div>
  );
}
