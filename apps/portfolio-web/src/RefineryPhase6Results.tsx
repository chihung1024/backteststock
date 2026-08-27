import type {
  RefineryMarginalExperiments,
  RefineryMarginalPairEvidence,
  RefineryMarginalResult,
  RefineryMarginalSnapshot,
  RefineryScalarDelta,
} from "./refineryTypes";

function formatNumber(value: number | null | undefined, digits = 3): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toLocaleString("zh-TW", { maximumFractionDigits: digits });
}

function formatDelta(value: number | null | undefined, digits = 3): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${formatNumber(value, digits)}`;
}

function hashPrefix(value: string | null | undefined): string {
  return value ? value.slice(0, 12) : "—";
}

function statusClass(status: string): string {
  if (["ready", "ok"].includes(status)) return "ready";
  if (status.includes("unavailable") || status.includes("incomplete") || status.includes("insufficient")) {
    return "warning";
  }
  return "failed";
}

function operationLabel(result: RefineryMarginalResult): string {
  const { operation } = result;
  if (operation.type === "remove_one") return `移除 ${operation.remove ?? "—"}`;
  if (operation.type === "add_one") return `新增 ${operation.add ?? "—"}`;
  return `替換 ${operation.remove ?? "—"} → ${operation.add ?? "—"}`;
}

function snapshotMetric(snapshot: RefineryMarginalSnapshot | null, metric: "entropy" | "participation"): number | null {
  if (!snapshot) return null;
  return metric === "entropy"
    ? snapshot.effective_dimensions.covariance.entropy_effective_rank
    : snapshot.effective_dimensions.covariance.participation_ratio;
}

function deltaCell(delta: RefineryScalarDelta | undefined, digits = 3) {
  return (
    <>
      <span>{formatNumber(delta?.baseline, digits)}</span>
      <span>{formatNumber(delta?.variant, digits)}</span>
      <strong>{formatDelta(delta?.delta, digits)}</strong>
    </>
  );
}

function SampleEvidence({ marginal }: { marginal: RefineryMarginalExperiments }) {
  const { common_sample: sample } = marginal;
  return (
    <div className="refinery-phase6-sample-grid">
      <article>
        <span>Union ResearchDataset</span>
        <strong title={sample.experiment_union_dataset_hash}>{hashPrefix(sample.experiment_union_dataset_hash)}</strong>
        <small>provenance only</small>
      </article>
      <article>
        <span>Daily common sample</span>
        <strong>{sample.daily?.observations ?? "—"}</strong>
        <small>{sample.daily ? `${sample.daily.effective_start} → ${sample.daily.effective_end} · ${hashPrefix(sample.daily.fingerprint_sha256)}` : "unavailable"}</small>
      </article>
      <article>
        <span>Weekly common sample</span>
        <strong>{sample.weekly?.observations ?? "—"}</strong>
        <small>{sample.weekly ? `${sample.weekly.effective_start} → ${sample.weekly.effective_end} · ${hashPrefix(sample.weekly.fingerprint_sha256)}` : "unavailable"}</small>
      </article>
      <article>
        <span>Experiment union</span>
        <strong>{sample.experiment_union_symbols.length}</strong>
        <small>{sample.experiment_union_symbols.join(" · ") || "—"}</small>
      </article>
    </div>
  );
}

function MarginalFailures({ marginal }: { marginal: RefineryMarginalExperiments }) {
  const failures = Object.values(marginal.failures);
  if (failures.length === 0) return null;
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Phase 6 實驗資料失敗">
      <table className="data-table refinery-phase6-failure-table">
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
  );
}

function PairEvidenceTable({
  title,
  pairs,
}: {
  title: string;
  pairs: RefineryMarginalPairEvidence[];
}) {
  if (pairs.length === 0) return <p className="workspace-hint">{title}：無。</p>;
  const horizons = Object.keys(pairs[0]?.correlations ?? {});
  return (
    <div className="table-scroll refinery-phase6-pair-scroll" tabIndex={0} role="region" aria-label={title}>
      <table className="data-table refinery-phase6-pair-table">
        <thead><tr><th>Pair</th>{horizons.map((horizon) => <th key={horizon}>{horizon}</th>)}</tr></thead>
        <tbody>
          {pairs.map((pair) => (
            <tr key={`${pair.symbol_a}-${pair.symbol_b}`}>
              <th scope="row">{pair.symbol_a} ↔ {pair.symbol_b}</th>
              {horizons.map((horizon) => <td key={horizon}>{formatNumber(pair.correlations[horizon])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResultEvidence({ result }: { result: RefineryMarginalResult }) {
  const pairImpacts = result.deltas.pair_impacts;
  return (
    <details className="refinery-phase6-result-details">
      <summary>{operationLabel(result)} 的共同樣本與 pair-impact evidence</summary>
      <div className="refinery-evidence-grid">
        <div><span>Daily fingerprint</span><strong title={result.common_sample.daily.fingerprint_sha256}>{hashPrefix(result.common_sample.daily.fingerprint_sha256)}</strong></div>
        <div><span>Weekly fingerprint</span><strong title={result.common_sample.weekly.fingerprint_sha256}>{hashPrefix(result.common_sample.weekly.fingerprint_sha256)}</strong></div>
        <div><span>Removed pairs</span><strong>{pairImpacts.removed_pairs.length}</strong></div>
        <div><span>Added pairs</span><strong>{pairImpacts.added_pairs.length}</strong></div>
      </div>
      <div className="refinery-phase6-invariant-list">
        {Object.entries(pairImpacts.shared_pair_invariant).map(([horizon, evidence]) => (
          <span key={horizon}>{horizon}: {evidence.compared_pairs}/{evidence.shared_pairs} shared pairs · max Δ {formatNumber(evidence.maximum_absolute_delta, 12)} ≤ {formatNumber(evidence.tolerance, 12)}</span>
        ))}
      </div>
      <PairEvidenceTable title="移除 pair evidence" pairs={pairImpacts.removed_pairs} />
      <PairEvidenceTable title="新增 pair evidence" pairs={pairImpacts.added_pairs} />
    </details>
  );
}

export function RefineryPhase6Preflight({
  marginal,
}: {
  marginal: RefineryMarginalExperiments | undefined;
}) {
  if (!marginal) return null;
  return (
    <section className="workspace-card refinery-phase6-card" aria-labelledby="refinery-phase6-preflight-title">
      <div className="section-heading">
        <div>
          <span className="section-index">P6</span>
          <div>
            <h2 id="refinery-phase6-preflight-title">Phase 6 共同實驗樣本預檢</h2>
            <p>此層與既有 baseline 分開；外部實驗資料失敗不會讓既有 Phase 3–5 baseline 偷偷變更或失效。</p>
          </div>
        </div>
        <span className={`status-pill ${statusClass(marginal.status)}`}>{marginal.status}</span>
      </div>
      <SampleEvidence marginal={marginal} />
      {marginal.eligibility.reasons.length > 0 && (
        <div className="notice warning"><strong>邊際實驗目前不產生正式結果</strong><ul>{marginal.eligibility.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></div>
      )}
      <MarginalFailures marginal={marginal} />
      <p className="refinery-method-note">共同樣本狀態：{marginal.common_sample.status}。日／週 fingerprint 代表實際凍結的有限 complete-case 矩陣，不等同於 ResearchDataset provenance hash。</p>
    </section>
  );
}

export function RefineryPhase6Results({
  marginal,
}: {
  marginal: RefineryMarginalExperiments | undefined;
}) {
  if (!marginal) return null;
  const baseline = marginal.experiment_baseline;
  return (
    <section className="workspace-card refinery-phase6-card" aria-labelledby="refinery-phase6-results-title">
      <div className="section-heading">
        <div>
          <span className="section-index">9</span>
          <div>
            <h2 id="refinery-phase6-results-title">Phase 6 邊際結構實驗</h2>
            <p>每一列都使用同一份 frozen common sample；數字是 in-sample historical diagnostic / not OOS，不是排序、推薦或交易指令。</p>
          </div>
        </div>
        <span className={`status-pill ${statusClass(marginal.status)}`}>{marginal.status}</span>
      </div>
      <SampleEvidence marginal={marginal} />

      {!baseline || marginal.results.length === 0 ? (
        <>
          <div className="notice warning"><strong>沒有正式邊際實驗結果</strong><p>Baseline 分析可維持有效；此層在共同樣本、membership 或資料品質不符合條件時 fail closed，不會用不一致期間補算。</p></div>
          <MarginalFailures marginal={marginal} />
        </>
      ) : (
        <>
          <div className="refinery-summary-grid compact refinery-phase6-baseline-summary">
            <article className="summary-metric"><span>Experiment baseline</span><strong>{baseline.symbols.join(" · ")}</strong><small>{baseline.covariance.observations} daily obs</small></article>
            <article className="summary-metric"><span>Covariance effective rank</span><strong>{formatNumber(snapshotMetric(baseline, "entropy"))}</strong><small>Ledoit-Wolf point estimate</small></article>
            <article className="summary-metric"><span>Participation ratio</span><strong>{formatNumber(snapshotMetric(baseline, "participation"))}</strong><small>covariance eigen structure</small></article>
            <article className="summary-metric"><span>Primary / sensitivity clusters</span><strong>{baseline.clustering.primary?.cluster_count ?? "—"} / {baseline.clustering.sensitivity?.cluster_count ?? "—"}</strong><small>average / complete linkage</small></article>
          </div>

          <div className="table-scroll refinery-phase6-result-scroll" tabIndex={0} role="region" aria-label="Phase 6 baseline 與 variant 比較">
            <table className="data-table refinery-phase6-result-table">
              <thead>
                <tr>
                  <th>Requested operation</th>
                  <th>Variant symbols</th>
                  <th>Covariance ER<br />B / V / Δ</th>
                  <th>Participation<br />B / V / Δ</th>
                  <th>Medium correlation ER<br />B / V / Δ</th>
                  <th>Average clusters<br />B / V / Δ</th>
                  <th>Complete clusters<br />B / V / Δ</th>
                  <th>Pair impacts</th>
                </tr>
              </thead>
              <tbody>
                {marginal.results.map((result) => {
                  const dimensions = result.deltas.effective_dimensions;
                  const pairImpacts = result.deltas.pair_impacts;
                  return (
                    <tr key={result.id}>
                      <th scope="row">{operationLabel(result)}</th>
                      <td className="refinery-phase6-symbol-cell">{result.variant_symbols.join(" · ")}</td>
                      <td className="refinery-phase6-delta-cell">{deltaCell(dimensions.covariance?.entropy_effective_rank)}</td>
                      <td className="refinery-phase6-delta-cell">{deltaCell(dimensions.covariance?.participation_ratio)}</td>
                      <td className="refinery-phase6-delta-cell">{deltaCell(dimensions.medium_correlation?.entropy_effective_rank)}</td>
                      <td className="refinery-phase6-delta-cell">{deltaCell(result.deltas.clusters.primary, 0)}</td>
                      <td className="refinery-phase6-delta-cell">{deltaCell(result.deltas.clusters.sensitivity, 0)}</td>
                      <td>{pairImpacts.removed_pairs.length} removed · {pairImpacts.added_pairs.length} added</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="refinery-phase6-result-evidence-list">
            {marginal.results.map((result) => <ResultEvidence result={result} key={result.id} />)}
          </div>
        </>
      )}
      <p className="refinery-method-note">不執行 per-variant Phase 5 bootstrap／redundancy verdict，也不會根據 delta 對結果排序。完整 Phase 5 證據仍只屬於既有 baseline；本表僅呈現共享樣本上的描述性結構擾動。</p>
    </section>
  );
}
