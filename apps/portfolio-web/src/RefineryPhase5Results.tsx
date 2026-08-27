import type {
  RefineryAnalyzeResponse,
  RefineryClusteringEvidence,
  RefineryRedundancyPair,
} from "./refineryTypes";

const MAX_REDUNDANCY_ROWS = 80;
const MAX_FACTOR_ASSET_ROWS = 100;

function formatNumber(value: number | null | undefined, digits = 3): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toLocaleString("zh-TW", { maximumFractionDigits: digits });
}

function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${(value * 100).toLocaleString("zh-TW", { maximumFractionDigits: digits })}%`;
}

function yesNo(value: boolean | null | undefined): string {
  if (value == null) return "—";
  return value ? "是" : "否";
}

function evidenceStatusClass(status: string): string {
  if (status === "ok" || status === "ready") return "ready";
  if (status.includes("unavailable") || status.includes("insufficient")) return "warning";
  return "failed";
}

function ClusterPanel({ clustering }: { clustering: RefineryClusteringEvidence | undefined }) {
  if (!clustering || clustering.status !== "ok" || !clustering.primary || !clustering.sensitivity) {
    return (
      <section className="workspace-card refinery-phase5-card" aria-labelledby="refinery-cluster-title">
        <div className="section-heading">
          <div><span className="section-index">5</span><div><h2 id="refinery-cluster-title">群聚結構</h2><p>結構週資料的描述性分群，不是持股建議。</p></div></div>
        </div>
        <div className="empty-state"><strong>群聚證據目前不可用</strong><p>{clustering?.reason ?? clustering?.status ?? "backend_evidence_unavailable"}</p></div>
      </section>
    );
  }

  const windows = clustering.multi_window?.windows ?? [];
  const bootstrap = clustering.bootstrap;
  return (
    <section className="workspace-card refinery-phase5-card" aria-labelledby="refinery-cluster-title">
      <div className="section-heading">
        <div><span className="section-index">5</span><div><h2 id="refinery-cluster-title">群聚結構</h2><p>Average linkage 為主要描述；Complete linkage 僅作敏感度證據。</p></div></div>
        <span className={`status-pill ${evidenceStatusClass(clustering.status)}`}>{clustering.status}</span>
      </div>

      <div className="refinery-summary-grid compact refinery-phase5-summary">
        <article className="summary-metric"><span>Primary</span><strong>{clustering.primary.method}</strong><small>average linkage</small></article>
        <article className="summary-metric"><span>Sensitivity</span><strong>{clustering.sensitivity.method}</strong><small>complete linkage</small></article>
        <article className="summary-metric"><span>Flat cut</span><strong>{formatNumber(clustering.flat_cut_distance, 2)}</strong><small>versioned descriptive cut</small></article>
        <article className="summary-metric"><span>Clusters</span><strong>{clustering.clusters.length}</strong><small>canonical groups</small></article>
        <article className="summary-metric"><span>Bootstrap</span><strong>{bootstrap ? `${bootstrap.usable_replicates}/${bootstrap.requested_replicates}` : "—"}</strong><small>{clustering.bootstrap_block_weeks}W moving block</small></article>
        <article className="summary-metric"><span>Contract</span><strong className="refinery-small-strong">{clustering.contract_version}</strong><small>Phase 5 methodology</small></article>
      </div>

      <div className="refinery-window-strip" aria-label="群聚穩定度視窗">
        {windows.map((window) => (
          <span key={window.window_weeks} className={`refinery-window-chip ${window.status === "ok" ? "ready" : "warning"}`}>
            {window.window_weeks}W · {window.status} · {window.observations} obs
          </span>
        ))}
      </div>

      <div className="table-scroll" tabIndex={0} role="region" aria-label="群聚群組摘要">
        <table className="data-table refinery-cluster-table">
          <thead><tr><th>Cluster</th><th>成員</th><th>數量</th><th>結構相關 Min / Mean / Max</th><th>Bootstrap stability</th><th>Complete 一致</th></tr></thead>
          <tbody>
            {clustering.clusters.map((cluster) => (
              <tr key={cluster.cluster_id}>
                <th scope="row">{cluster.cluster_id}</th>
                <td className="refinery-members-cell">{cluster.members.join(" · ")}</td>
                <td>{cluster.member_count}</td>
                <td>{cluster.structural_correlation ? `${formatNumber(cluster.structural_correlation.minimum, 2)} / ${formatNumber(cluster.structural_correlation.mean, 2)} / ${formatNumber(cluster.structural_correlation.maximum, 2)}` : "—"}</td>
                <td>{formatPercent(cluster.bootstrap_stability, 1)}</td>
                <td>{yesNo(cluster.complete_linkage_agreement)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="refinery-method-note">群聚 ID、cut、bootstrap 與 window 都是可重現的歷史結構證據；不代表群內任兩檔都具有相同經濟曝險，也不構成刪除持股的理由。</p>
    </section>
  );
}

function RedundancyPairRow({ pair }: { pair: RefineryRedundancyPair }) {
  return (
    <tr>
      <th scope="row">{pair.symbol_a} ↔ {pair.symbol_b}</th>
      <td><span className={`refinery-verdict refinery-verdict-${pair.verdict.toLowerCase()}`}>{pair.verdict}</span></td>
      <td>{pair.confidence}</td>
      <td>{formatNumber(pair.structural_correlation, 2)}</td>
      <td>{formatNumber(pair.medium_correlation, 2)}</td>
      <td>{formatNumber(pair.downside_correlation, 2)}</td>
      <td>{formatNumber(pair.stress_correlation, 2)}</td>
      <td>{formatNumber(pair.factor_implied_correlation, 2)}</td>
      <td title={pair.factor_corroboration_reason ?? undefined}>{yesNo(pair.factor_corroboration_eligible)}</td>
      <td>{yesNo(pair.same_average_cluster)}</td>
      <td>{yesNo(pair.same_complete_cluster)}</td>
      <td>{formatPercent(pair.window_cocluster_agreement, 0)}</td>
      <td>{formatPercent(pair.bootstrap_cocluster_probability, 0)}</td>
    </tr>
  );
}

function RedundancyPanel({ response }: { response: RefineryAnalyzeResponse }) {
  const redundancy = response.analysis?.redundancy;
  if (!redundancy || redundancy.status !== "ok") {
    return (
      <section className="workspace-card refinery-phase5-card" aria-labelledby="refinery-redundancy-title">
        <div className="section-heading"><div><span className="section-index">6</span><div><h2 id="refinery-redundancy-title">重複曝險證據</h2><p>多證據 verdict，不是交易指令。</p></div></div></div>
        <div className="empty-state"><strong>重複曝險證據目前不可用</strong><p>{redundancy?.status ?? "backend_evidence_unavailable"}</p></div>
      </section>
    );
  }

  const visiblePairs = redundancy.pairs.slice(0, MAX_REDUNDANCY_ROWS);
  return (
    <section className="workspace-card refinery-phase5-card" aria-labelledby="refinery-redundancy-title">
      <div className="section-heading">
        <div><span className="section-index">6</span><div><h2 id="refinery-redundancy-title">重複曝險證據</h2><p>HIGH / MEDIUM / LOW / UNCERTAIN 只描述歷史曝險相似度，不是 KEEP / TRIM / REPLACE。</p></div></div>
      </div>

      <div className="refinery-verdict-counts" aria-label="重複曝險 verdict 統計">
        {(["HIGH", "MEDIUM", "LOW", "UNCERTAIN"] as const).map((verdict) => (
          <div key={verdict}><span>{verdict}</span><strong>{redundancy.counts[verdict] ?? 0}</strong></div>
        ))}
      </div>

      {redundancy.pairs.length > MAX_REDUNDANCY_ROWS && (
        <div className="notice info"><strong>大型 pair table 呈現限制</strong><p>API 保留 {redundancy.pairs.length} 組完整證據；UI 僅掛載前 {MAX_REDUNDANCY_ROWS} 組 deterministic pair rows 以控制 DOM。這是呈現限制，不是篩選或排名。</p></div>
      )}

      <div className="table-scroll refinery-phase5-pair-scroll" tabIndex={0} role="region" aria-label="重複曝險 pair evidence">
        <table className="data-table refinery-redundancy-table">
          <thead><tr><th>Pair</th><th>Verdict</th><th>Confidence</th><th>156W</th><th>252D</th><th>Downside</th><th>Stress</th><th>Factor diagnostic</th><th>Factor 可作 verdict</th><th>Avg cluster</th><th>Complete</th><th>Window</th><th>Bootstrap</th></tr></thead>
          <tbody>{visiblePairs.map((pair) => <RedundancyPairRow key={`${pair.symbol_a}-${pair.symbol_b}`} pair={pair} />)}</tbody>
        </table>
      </div>
      <p className="refinery-method-note">Verdict semantics: {redundancy.verdict_semantics}. Numeric magic score: {redundancy.magic_numeric_score ? "unexpected" : "disabled"}.</p>
    </section>
  );
}

function FactorPanel({ response }: { response: RefineryAnalyzeResponse }) {
  const factors = response.analysis?.factor_relationships;
  if (!factors) return null;
  const assets = Object.entries(factors.assets).slice(0, MAX_FACTOR_ASSET_ROWS);
  return (
    <section className="workspace-card refinery-phase5-card" aria-labelledby="refinery-factor-title">
      <div className="section-heading">
        <div><span className="section-index">7</span><div><h2 id="refinery-factor-title">因子關係</h2><p>{factors.scope}；僅作次要 corroboration，不覆蓋結構價格證據。</p></div></div>
        <span className={`status-pill ${evidenceStatusClass(factors.status)}`}>{factors.status}</span>
      </div>
      <div className="refinery-evidence-grid">
        <div><span>Source</span><strong>{factors.source}</strong></div>
        <div><span>Return currency</span><strong>{factors.return_currency}</strong></div>
        <div><span>Model scope</span><strong>{factors.factor_model_scope}</strong></div>
        <div><span>Minimum months</span><strong>{factors.minimum_monthly_observations}</strong></div>
        <div><span>Factor sample</span><strong>{factors.factor_sample?.observations ?? "—"}</strong></div>
      </div>

      <div className="table-scroll" tabIndex={0} role="region" aria-label="因子曝險適用範圍">
        <table className="data-table">
          <thead><tr><th>代碼</th><th>Status</th><th>Quote CCY</th><th>Computable</th><th>Verdict eligible</th><th>Obs.</th><th>R²</th></tr></thead>
          <tbody>
            {assets.map(([symbol, asset]) => (
              <tr key={symbol}>
                <th scope="row">{symbol}</th>
                <td>{asset.status}</td>
                <td>{asset.quote_currency ?? "—"}</td>
                <td>{yesNo(asset.factor_computable)}</td>
                <td title={asset.factor_corroboration_reason ?? undefined}>{yesNo(asset.factor_corroboration_eligible)}</td>
                <td>{asset.observations}</td>
                <td>{formatNumber(asset.r_squared, 3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="refinery-method-note">Factor-implied correlation 是 U.S.-factor co-movement diagnostic。沒有可追溯的 instrument/model applicability authority 時，診斷仍可顯示，但 factor_corroboration_eligible=false，不能升級 redundancy verdict。</p>
    </section>
  );
}

function ThemePanel({ response }: { response: RefineryAnalyzeResponse }) {
  const theme = response.analysis?.theme_relationships;
  return (
    <section className="workspace-card refinery-phase5-card" aria-labelledby="refinery-theme-title">
      <div className="section-heading"><div><span className="section-index">8</span><div><h2 id="refinery-theme-title">主題關係</h2><p>只有具 traceable provenance 的 taxonomy 才能進入證據層。</p></div></div></div>
      {!theme || theme.status === "unavailable_no_traceable_theme_source" ? (
        <div className="notice info"><strong>目前刻意不產生主題判定</strong><p>{theme?.status ?? "unavailable_no_traceable_theme_source"}。系統不會從 ticker 名稱、即時網頁文字或未版本化 AI 分類自動推測經濟主題。</p></div>
      ) : (
        <div className="refinery-evidence-grid">
          <div><span>Status</span><strong>{theme.status}</strong></div>
          <div><span>Source</span><strong>{theme.source ?? "—"}</strong></div>
          <div><span>Taxonomy</span><strong>{theme.taxonomy_version ?? "—"}</strong></div>
        </div>
      )}
    </section>
  );
}

export function RefineryPhase5Results({ response }: { response: RefineryAnalyzeResponse }) {
  if (!response.analysis) return null;
  return (
    <>
      <ClusterPanel clustering={response.analysis.clustering} />
      <RedundancyPanel response={response} />
      <FactorPanel response={response} />
      <ThemePanel response={response} />
    </>
  );
}
