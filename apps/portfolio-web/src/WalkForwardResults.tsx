import { LineChart } from "./charts";
import type {
  WalkForwardDecisionResponse,
  WalkForwardMetricValue,
  WalkForwardOosPeriodResponse,
  WalkForwardPeriodAuditResponse,
  WalkForwardResultResponse,
} from "./walkForwardTypes";

function formatCurrency(value: WalkForwardMetricValue | number | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("zh-TW", {
    style: "currency",
    currency: "TWD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercent(value: WalkForwardMetricValue | number | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function formatRatio(value: WalkForwardMetricValue | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return value.toFixed(3);
}

function formatInteger(value: number | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 }).format(value);
}

function shortHash(value: string): string {
  return value.length > 20 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value;
}

function downloadJson(result: WalkForwardResultResponse): void {
  const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `walk-forward-${result.jobHash.slice(0, 12)}.json`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function weightLabel(symbols: string[], weights: number[]): string {
  return symbols.map((symbol, index) => {
    const weight = weights[index];
    return `${symbol} ${typeof weight === "number" ? formatPercent(weight) : "—"}`;
  }).join(" · ");
}

function DecisionEvidence({
  decision,
  audit,
  oosPeriod,
}: {
  decision: WalkForwardDecisionResponse;
  audit: WalkForwardPeriodAuditResponse | undefined;
  oosPeriod: WalkForwardOosPeriodResponse | undefined;
}) {
  return (
    <article className="wf-evidence-card">
      <div className="wf-decision-heading">
        <div>
          <h3>{decision.period.periodId}</h3>
          <p>Decision {decision.period.decisionDate} · {decision.selector.rule}</p>
        </div>
        <span className="status-pill ready">Frozen</span>
      </div>

      <div className="wf-evidence-flow" aria-label={`${decision.period.periodId} 因果證據`}>
        <div>
          <span>Training</span>
          <strong>{decision.period.trainingStart} → {decision.period.trainingEnd}</strong>
          <small>effective {decision.trainingDataset.effectiveStart} → {decision.trainingDataset.effectiveEnd}</small>
        </div>
        <i aria-hidden="true">→</i>
        <div>
          <span>Decision</span>
          <strong>{decision.period.decisionDate}</strong>
          <small>{decision.pitUniverse.members.length} PIT members · {decision.eligibleCandidates.length} eligible</small>
        </div>
        <i aria-hidden="true">→</i>
        <div>
          <span>Evaluation / OOS</span>
          <strong>{oosPeriod?.effective_start ?? decision.period.evaluationStart} → {oosPeriod?.effective_end ?? decision.period.evaluationEnd}</strong>
          <small>{decision.selectedConstituents.length} selected · {formatCurrency(oosPeriod?.transition_cost ?? 0)} transition cost</small>
        </div>
      </div>

      <p className="wf-selected-assets">{weightLabel(decision.selectedConstituents, decision.weights)}</p>

      <dl className="wf-provenance-grid">
        <div><dt>PIT requested</dt><dd>{decision.pitUniverse.requestedAsOf}</dd></div>
        <div><dt>PIT source</dt><dd>{decision.pitUniverse.sourceAsOf}</dd></div>
        <div><dt>Evidence available</dt><dd>{decision.pitUniverse.evidenceAvailableAsOf}</dd></div>
        <div><dt>Membership</dt><dd>{decision.pitUniverse.membershipAuthoritative && !decision.pitUniverse.sourceIsProxy ? "Authoritative" : "Non-authoritative"}</dd></div>
        <div><dt>Training hash</dt><dd title={decision.trainingDataset.datasetHash}>{shortHash(decision.trainingDataset.datasetHash)}</dd></div>
        <div><dt>Decision hash</dt><dd title={decision.decisionHash}>{shortHash(decision.decisionHash)}</dd></div>
        <div><dt>Evaluation hash</dt><dd title={audit?.evaluation_dataset_hash}>{audit ? shortHash(audit.evaluation_dataset_hash) : "—"}</dd></div>
        <div><dt>Combinations</dt><dd>{formatInteger(audit?.exhaustive_combination_count)}</dd></div>
      </dl>

      <details className="wf-evidence-details">
        <summary>查看完整 provenance</summary>
        <div className="wf-provenance-detail-grid">
          <p><strong>PIT version</strong><span>{decision.pitUniverse.version}</span></p>
          <p><strong>PIT checksum</strong><span>{decision.pitUniverse.checksum}</span></p>
          <p><strong>Membership policy</strong><span>{decision.pitUniverse.membershipPolicy}</span></p>
          <p><strong>Fetched at</strong><span>{decision.pitUniverse.fetchedAt}</span></p>
          <p><strong>Source</strong><span>{decision.pitUniverse.sourceLabel}</span></p>
          <p><strong>Selector contract</strong><span>{decision.selector.contractVersion}</span></p>
          <p><strong>Authority dataset hash</strong><span>{audit?.authority_dataset_hash ?? "—"}</span></p>
          <p><strong>Evaluation dataset hash</strong><span>{audit?.evaluation_dataset_hash ?? "—"}</span></p>
        </div>
      </details>
    </article>
  );
}

export function WalkForwardResults({ result }: { result: WalkForwardResultResponse }) {
  const metrics = result.oos.metrics.metrics;
  const auditByDecision = new Map(result.periods.map((period) => [period.decision_hash, period]));
  const oosByDecision = new Map(result.oos.periods.map((period) => [period.decision_hash, period]));

  return (
    <section className="workspace-card wf-result-card" aria-labelledby="wf-result-title">
      <div className="section-heading result-heading">
        <div>
          <span className="section-index">5</span>
          <div>
            <h2 id="wf-result-title">Continuous OOS 結果</h2>
            <p>績效、交易成本與曲線全部直接來自後端 continuous OOS ledger。Training 與 Decision evidence 只用於解釋研究，不重新計入 OOS 績效。</p>
          </div>
        </div>
        <div className="section-actions">
          <button type="button" className="secondary" onClick={() => downloadJson(result)}>匯出結果 JSON</button>
        </div>
      </div>

      <div className="result-meta wf-result-meta">
        <span>Status <strong>{result.status}</strong></span>
        <span>as-of <strong>{result.asOfDate}</strong></span>
        <span>Decisions <strong>{result.decisions.length}</strong></span>
        <span title={result.jobHash}>job <strong>{shortHash(result.jobHash)}</strong></span>
      </div>

      <div className="metric-grid wf-metric-grid">
        <article className="metric-card"><span>期末資產</span><strong>{formatCurrency(metrics.final_balance)}</strong><small>TWD continuous ledger</small></article>
        <article className="metric-card"><span>CAGR</span><strong>{formatPercent(metrics.cagr)}</strong><small>後端 metric authority</small></article>
        <article className="metric-card"><span>Sortino</span><strong>{formatRatio(metrics.sortino_ratio)}</strong><small>後端 metric authority</small></article>
        <article className="metric-card"><span>最大回撤</span><strong>{formatPercent(metrics.max_drawdown)}</strong><small>Continuous OOS</small></article>
        <article className="metric-card"><span>交易成本</span><strong>{formatCurrency(metrics.transaction_costs)}</strong><small>Decision transitions</small></article>
        <article className="metric-card"><span>觀察數</span><strong>{typeof metrics.observations === "number" ? formatInteger(metrics.observations) : "—"}</strong><small>{String(metrics.start ?? "—")} → {String(metrics.end ?? "—")}</small></article>
      </div>

      <div className="wf-chart-grid">
        <article className="subcard wf-chart-card">
          <div className="subcard-heading">
            <div><h3>Continuous OOS 資產曲線</h3><p>跨 Period 不重置 NAV；Decision transition 已反映成本。</p></div>
          </div>
          <LineChart title="Walk-Forward continuous OOS equity" series={[{ name: "OOS Equity (TWD)", points: result.oos.ledger.equity }]} height={320} />
        </article>
        <article className="subcard wf-chart-card">
          <div className="subcard-heading">
            <div><h3>Continuous OOS 累積指數</h3><p>直接使用 ledger returnIndex，不從日報酬重新累乘。</p></div>
          </div>
          <LineChart title="Walk-Forward continuous OOS return index" series={[{ name: "OOS Return Index", points: result.oos.ledger.returnIndex }]} height={320} />
        </article>
      </div>

      <div className="notice info wf-benchmark-boundary">
        <strong>Benchmark 證據邊界</strong>
        <p>目前 Walk-Forward v1 response 沒有獨立的 continuous OOS benchmark series，因此此工作區不會用瀏覽器自行下載或拼接 benchmark 曲線。等後端正式提供同一 OOS contract 的 benchmark authority 後再加入比較。</p>
      </div>

      {result.oos.ledger.warnings.length > 0 && (
        <div className="notice warning"><strong>OOS ledger 提醒</strong><ul>{result.oos.ledger.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></div>
      )}

      <div className="section-heading wf-evidence-section-heading">
        <div>
          <span className="section-index">6</span>
          <div>
            <h2>Decision 與因果證據</h2>
            <p>每張卡片把 Training、PIT Decision 與 Evaluation 串在一起，並保留 dataset / decision identity。</p>
          </div>
        </div>
      </div>

      <div className="wf-evidence-list">
        {result.decisions.map((decision) => (
          <DecisionEvidence
            key={decision.decisionHash}
            decision={decision}
            audit={auditByDecision.get(decision.decisionHash)}
            oosPeriod={oosByDecision.get(decision.decisionHash)}
          />
        ))}
      </div>

      <details className="wf-job-contracts">
        <summary>查看 Job / OOS contract</summary>
        <dl className="wf-provenance-grid">
          <div><dt>Job contract</dt><dd>{result.contractVersion}</dd></div>
          <div><dt>Hash algorithm</dt><dd>{result.hashAlgorithm}</dd></div>
          <div><dt>As-of policy</dt><dd>{result.asOfPolicy}</dd></div>
          <div><dt>Selector policy</dt><dd>{result.selectorPolicy}</dd></div>
          <div><dt>OOS policy</dt><dd>{result.oosPolicy}</dd></div>
          <div><dt>OOS contract</dt><dd>{result.oos.contractVersion}</dd></div>
          <div><dt>Execution policy</dt><dd>{result.oos.executionPolicy}</dd></div>
          <div><dt>Gap policy</dt><dd>{result.oos.gapPolicy}</dd></div>
        </dl>
      </details>
    </section>
  );
}
