import { useMemo, useState } from "react";
import type {
  RefineryAnalyzeResponse,
  RefineryCorrelationKey,
  RefineryCorrelationMatrix,
  RefineryCorrelationView,
  RefineryPreflightResponse,
} from "./refineryTypes";
import { RefineryPhase5Results } from "./RefineryPhase5Results";
import { RefineryPhase6Results } from "./RefineryPhase6Results";

const MAX_FULL_CORRELATION_MATRIX_SYMBOLS = 20;
const MAX_CORRELATION_PAIR_ROWS = 30;

const CORRELATION_LABELS: Record<RefineryCorrelationKey, string> = {
  tactical_daily: "戰術 63D",
  medium_daily: "中期 252D",
  structural_weekly: "結構 156W",
  downside: "下跌日",
  stress: "壓力尾端",
};

function formatNumber(value: number | null | undefined, digits = 3): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toLocaleString("zh-TW", { maximumFractionDigits: digits });
}

function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${(value * 100).toLocaleString("zh-TW", { maximumFractionDigits: digits })}%`;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    ready: "可分析",
    ok: "可用",
    incomplete: "資料不完整",
    insufficient_data: "樣本不足",
    insufficient_observations: "樣本不足",
    degenerate_variance: "變異數退化",
    unavailable_benchmark_not_supplied: "未提供基準",
    unavailable_benchmark_failed: "基準資料失敗",
    unavailable_weights_not_supplied: "未提供權重",
  };
  return labels[status] ?? status;
}

function statusClass(status: string): string {
  if (["ready", "ok"].includes(status)) return "ready";
  if (status.includes("unavailable") || status.includes("insufficient")) return "warning";
  return "failed";
}

function hashPrefix(value: string | null | undefined): string {
  return value ? value.slice(0, 12) : "—";
}

export function RefineryPreflightCard({ response }: { response: RefineryPreflightResponse }) {
  const failures = Object.values(response.dataset.failures);
  const requested = response.dataset.requested_symbols.length;
  const resolved = response.dataset.resolved_symbols.length;
  return (
    <section className="workspace-card refinery-preflight-card" aria-labelledby="refinery-preflight-title">
      <div className="section-heading">
        <div>
          <span className="section-index">✓</span>
          <div>
            <h2 id="refinery-preflight-title">Refinery 資料預檢</h2>
            <p>
              Dataset {hashPrefix(response.dataset.candidate_dataset_hash)} · {response.dataset.effective_start ?? "—"} → {response.dataset.effective_end ?? "—"}
            </p>
          </div>
        </div>
        <span className={`status-pill ${statusClass(response.status)}`}>{statusLabel(response.status)}</span>
      </div>

      <div className="refinery-summary-grid compact">
        <article className="summary-metric"><span>Requested</span><strong>{requested}</strong><small>要求持股</small></article>
        <article className="summary-metric"><span>Resolved</span><strong>{resolved}</strong><small>成功取回</small></article>
        <article className="summary-metric"><span>Daily CC</span><strong>{response.dataset.daily_complete_case_observations}</strong><small>日資料共同樣本</small></article>
        <article className="summary-metric"><span>Weekly CC</span><strong>{response.dataset.weekly_complete_case_observations}</strong><small>週資料共同樣本</small></article>
      </div>

      {response.eligibility.reasons.length > 0 && (
        <div className="notice warning">
          <strong>目前不可正式分析</strong>
          <ul>{response.eligibility.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
        </div>
      )}

      {failures.length > 0 && (
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Refinery 失敗持股列表">
          <table className="data-table">
            <thead><tr><th>代碼</th><th>階段</th><th>可重試</th><th>說明</th></tr></thead>
            <tbody>
              {failures.map((failure) => (
                <tr key={failure.symbol}>
                  <th scope="row">{failure.symbol}</th>
                  <td>{failure.stage}</td>
                  <td>{failure.retryable ? "是" : "否"}</td>
                  <td>{failure.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <details className="preflight-details">
        <summary>資料品質與可重現性</summary>
        <div className="refinery-evidence-grid">
          <div><span>Reference observations</span><strong>{response.dataset.reference_observations}</strong></div>
          <div><span>Daily returns</span><strong>{response.dataset.daily_return_observations}</strong></div>
          <div><span>Weekly returns</span><strong>{response.dataset.weekly_return_observations}</strong></div>
          <div><span>Benchmark</span><strong>{response.dataset.benchmark.status}</strong></div>
          <div><span>ResearchDataset</span><strong>{String(response.methodology.research_dataset_contract_version ?? "—")}</strong></div>
          <div><span>Risk Math</span><strong>{String(response.methodology.risk_math_contract_version ?? "—")}</strong></div>
        </div>
        <pre className="refinery-json-evidence">{JSON.stringify(response.dataset.coverage, null, 2)}</pre>
      </details>
    </section>
  );
}

function StructureSummary({ response }: { response: RefineryAnalyzeResponse }) {
  const analysis = response.analysis;
  if (!analysis) return null;
  const portfolio = analysis.portfolio;
  const covariance = analysis.effective_dimensions.covariance;
  const medium = analysis.effective_dimensions.medium_correlation;
  return (
    <section className="workspace-card" aria-labelledby="refinery-structure-title">
      <div className="section-heading">
        <div><span className="section-index">1</span><div><h2 id="refinery-structure-title">結構摘要</h2><p>風險結構，不是選股或推薦分數。</p><p>Historical in-sample research；若 candidate 來自目前 Universe，屬 Current-universe constituents 快照而非 point-in-time 歷史成分。</p></div></div>
      </div>
      <div className="refinery-summary-grid">
        <article className="summary-metric"><span>名目持股</span><strong>{analysis.symbols.length}</strong><small>Requested candidates</small></article>
        <article className="summary-metric"><span>Cov. Effective Rank</span><strong>{formatNumber(covariance.entropy_effective_rank, 2)}</strong><small>熵有效維度</small></article>
        <article className="summary-metric"><span>Medium Corr. Rank</span><strong>{formatNumber(medium?.entropy_effective_rank, 2)}</strong><small>252D 相關有效維度</small></article>
        <article className="summary-metric"><span>Diversification Ratio</span><strong>{formatNumber(portfolio.diversification_ratio, 3)}</strong><small>{portfolio.weights ? "顯式權重" : "未提供權重"}</small></article>
        <article className="summary-metric"><span>LW Shrinkage</span><strong>{formatPercent(analysis.covariance.ledoit_wolf_shrinkage, 1)}</strong><small>Ledoit-Wolf</small></article>
        <article className="summary-metric"><span>Estimator Dispersion</span><strong>{formatNumber(analysis.covariance.estimator_dispersion.maximum_relative_frobenius, 3)}</strong><small>最大相對 Frobenius</small></article>
      </div>
    </section>
  );
}

function RiskContributionTable({ response }: { response: RefineryAnalyzeResponse }) {
  const analysis = response.analysis;
  if (!analysis) return null;
  const portfolio = analysis.portfolio;
  if (!portfolio.weights || !portfolio.signed_component_risk_contribution || !portfolio.volatility) {
    return (
      <section className="workspace-card" aria-labelledby="refinery-risk-title">
        <div className="section-heading"><div><span className="section-index">2</span><div><h2 id="refinery-risk-title">資本 vs 簽名風險貢獻</h2><p>未提供顯式權重，因此不假設等權。</p></div></div></div>
        <div className="notice info"><strong>Portfolio risk unavailable</strong><p>{statusLabel(portfolio.status)}</p></div>
      </section>
    );
  }

  return (
    <section className="workspace-card" aria-labelledby="refinery-risk-title">
      <div className="section-heading"><div><span className="section-index">2</span><div><h2 id="refinery-risk-title">資本 vs 簽名風險貢獻</h2><p>負 RC 保持負號；只描述風險分解，不附加建議。</p></div></div></div>
      <div className="refinery-risk-meta">
        <span>年化波動 <strong>{formatPercent(portfolio.volatility, 2)}</strong></span>
        <span>DR <strong>{formatNumber(portfolio.diversification_ratio, 3)}</strong></span>
        <span>Weight effective <strong>{formatNumber(portfolio.weight_effective_holdings, 2)}</strong></span>
        <span>Gross RC effective <strong>{formatNumber(portfolio.gross_risk_contribution_equivalent_holdings, 2)}</strong></span>
      </div>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="資本與風險貢獻列表">
        <table className="data-table refinery-risk-table">
          <thead><tr><th>代碼</th><th>資本權重</th><th>Signed RC</th><th>RC share</th></tr></thead>
          <tbody>
            {analysis.symbols.map((symbol, index) => {
              const component = portfolio.signed_component_risk_contribution?.[index] ?? null;
              const share = component == null || !portfolio.volatility ? null : component / portfolio.volatility;
              return (
                <tr key={symbol}>
                  <th scope="row">{symbol}</th>
                  <td>{formatPercent(portfolio.weights?.[index], 2)}</td>
                  <td className={component != null && component < 0 ? "signed-negative" : ""}>{formatPercent(component, 2)}</td>
                  <td className={share != null && share < 0 ? "signed-negative" : ""}>{formatPercent(share, 1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CovarianceStability({ response }: { response: RefineryAnalyzeResponse }) {
  const analysis = response.analysis;
  if (!analysis) return null;
  const entries = Object.entries(analysis.covariance.estimators);
  return (
    <section className="workspace-card" aria-labelledby="refinery-cov-title">
      <div className="section-heading"><div><span className="section-index">3</span><div><h2 id="refinery-cov-title">Covariance 穩定度</h2><p>比較估計器敏感度，不把 estimator 差異解讀為 alpha。</p></div></div></div>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Covariance 診斷">
        <table className="data-table">
          <thead><tr><th>Estimator</th><th>Obs.</th><th>PSD</th><th>Rank</th><th>Condition</th><th>Shrinkage</th></tr></thead>
          <tbody>
            {entries.map(([name, estimator]) => (
              <tr key={name}>
                <th scope="row">{name}</th>
                <td>{estimator.observations}</td>
                <td>{estimator.diagnostics.is_psd ? "是" : "否"}</td>
                <td>{estimator.diagnostics.numerical_rank}</td>
                <td>{formatNumber(estimator.diagnostics.condition_number, 2)}</td>
                <td>{formatPercent(estimator.shrinkage, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="refinery-dispersion-list">
        {Object.entries(analysis.covariance.estimator_dispersion.pairwise_relative_frobenius).map(([pair, value]) => (
          <div key={pair}><span>{pair.replace("::", " ↔ ")}</span><strong>{formatNumber(value, 4)}</strong></div>
        ))}
      </div>
    </section>
  );
}

type CorrelationPair = { left: string; right: string; value: number };

function correlationPairs(matrix: RefineryCorrelationMatrix): CorrelationPair[] {
  const pairs: CorrelationPair[] = [];
  for (let row = 0; row < matrix.symbols.length; row += 1) {
    for (let column = row + 1; column < matrix.symbols.length; column += 1) {
      const value = matrix.values[row]?.[column];
      if (value == null || !Number.isFinite(value)) continue;
      pairs.push({ left: matrix.symbols[row]!, right: matrix.symbols[column]!, value });
    }
  }
  return pairs
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value) || a.left.localeCompare(b.left) || a.right.localeCompare(b.right))
    .slice(0, MAX_CORRELATION_PAIR_ROWS);
}

function FullCorrelationMatrix({ matrix }: { matrix: RefineryCorrelationMatrix }) {
  return (
    <div className="refinery-matrix-scroll" tabIndex={0} role="region" aria-label="完整相關矩陣">
      <table className="refinery-correlation-matrix">
        <thead><tr><th scope="col">代碼</th>{matrix.symbols.map((symbol) => <th scope="col" key={symbol}>{symbol}</th>)}</tr></thead>
        <tbody>
          {matrix.symbols.map((symbol, row) => (
            <tr key={symbol}>
              <th scope="row">{symbol}</th>
              {matrix.symbols.map((column, index) => {
                const value = matrix.values[row]?.[index] ?? null;
                return <td key={column} data-diagonal={row === index ? "true" : undefined}>{formatNumber(value, 2)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CorrelationPairSummary({ matrix }: { matrix: RefineryCorrelationMatrix }) {
  const pairs = useMemo(() => correlationPairs(matrix), [matrix]);
  return (
    <div className="refinery-pair-summary">
      <div className="notice info"><strong>大型矩陣摘要</strong><p>{matrix.symbols.length} 檔持股不直接掛載完整 {matrix.symbols.length}×{matrix.symbols.length} DOM；以下只列絕對相關最高的 {Math.min(MAX_CORRELATION_PAIR_ROWS, pairs.length)} 組，屬呈現摘要而非冗餘判定。</p></div>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="大型相關矩陣配對摘要">
        <table className="data-table">
          <thead><tr><th>左側</th><th>右側</th><th>相關係數</th></tr></thead>
          <tbody>{pairs.map((pair) => <tr key={`${pair.left}-${pair.right}`}><th scope="row">{pair.left}</th><td>{pair.right}</td><td>{formatNumber(pair.value, 3)}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

function CorrelationPanel({ view }: { view: RefineryCorrelationView }) {
  return (
    <div className="refinery-correlation-panel">
      <div className="refinery-correlation-meta">
        <span className={`status-pill ${statusClass(view.status)}`}>{statusLabel(view.status)}</span>
        <span>Input {view.input_observations}</span>
        <span>Effective {view.observations}</span>
        <span>Dropped {view.dropped_observations}</span>
        {view.window != null && <span>Window {view.window}</span>}
        {view.threshold != null && <span>Threshold {formatPercent(view.threshold, 2)}</span>}
      </div>
      <p className="muted-inline">Condition: {view.condition}</p>
      {!view.matrix ? (
        <div className="empty-state"><strong>此相關視圖目前不可用</strong><p>{statusLabel(view.status)}；系統不會以 0 或假資料補值。</p></div>
      ) : view.matrix.symbols.length <= MAX_FULL_CORRELATION_MATRIX_SYMBOLS ? (
        <FullCorrelationMatrix matrix={view.matrix} />
      ) : (
        <CorrelationPairSummary matrix={view.matrix} />
      )}
    </div>
  );
}

function Correlations({ response }: { response: RefineryAnalyzeResponse }) {
  const analysis = response.analysis;
  const [active, setActive] = useState<RefineryCorrelationKey>("medium_daily");
  if (!analysis) return null;
  return (
    <section className="workspace-card" aria-labelledby="refinery-corr-title">
      <div className="section-heading"><div><span className="section-index">4</span><div><h2 id="refinery-corr-title">多時域相關</h2><p>戰術、中期、結構、下跌與壓力樣本分開呈現。</p></div></div></div>
      <div className="refinery-tabs" role="tablist" aria-label="相關視圖">
        {(Object.keys(CORRELATION_LABELS) as RefineryCorrelationKey[]).map((key) => (
          <button
            type="button"
            role="tab"
            aria-selected={active === key}
            className={active === key ? "active" : ""}
            key={key}
            onClick={() => setActive(key)}
          >
            {CORRELATION_LABELS[key]}
          </button>
        ))}
      </div>
      <CorrelationPanel view={analysis.correlations[active]} />
    </section>
  );
}

export function RefineryResults({ response }: { response: RefineryAnalyzeResponse }) {
  if (!response.analysis) {
    return (
      <section className="workspace-card" aria-labelledby="refinery-analysis-blocked-title">
        <div className="empty-state"><strong id="refinery-analysis-blocked-title">正式分析未產生</strong><p>{statusLabel(response.status)}；請依預檢 evidence 修正資料後再執行。</p></div>
      </section>
    );
  }
  return (
    <div className="refinery-results-stack">
      <StructureSummary response={response} />
      <RiskContributionTable response={response} />
      <CovarianceStability response={response} />
      <Correlations response={response} />
      <RefineryPhase5Results response={response} />
      <RefineryPhase6Results marginal={response.marginal_experiments} />
    </div>
  );
}
