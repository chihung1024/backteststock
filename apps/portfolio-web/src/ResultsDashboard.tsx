import { useMemo, useState } from "react";
import { BarChart, LineChart, MonthlyHeatmap } from "./charts";
import { PortfolioComparison } from "./PortfolioComparison";
import type {
  AssetPreflight,
  BacktestResponse,
  BacktestResult,
  PreflightResponse,
  ResultTab,
} from "./types";

const TABS: Array<{ id: ResultTab; label: string }> = [
  { id: "overview", label: "總覽" },
  { id: "growth", label: "資產成長" },
  { id: "drawdown", label: "回撤" },
  { id: "annual", label: "年度報酬" },
  { id: "monthly", label: "月報酬" },
  { id: "income", label: "現金流與收入" },
  { id: "allocation", label: "配置漂移" },
  { id: "analytics", label: "進階分析" },
  { id: "audit", label: "資料稽核" },
];

const CORE_METRICS: Array<[string, string, "money" | "percent" | "number" | "integer"]> = [
  ["final_balance", "期末金額", "money"],
  ["cagr", "CAGR", "percent"],
  ["money_weighted_return", "XIRR", "percent"],
  ["max_drawdown", "最大回撤", "percent"],
  ["sharpe_ratio", "Sharpe", "number"],
  ["sortino_ratio", "Sortino", "number"],
  ["calmar_ratio", "Calmar", "number"],
  ["volatility", "年化波動率", "percent"],
  ["beta", "Beta", "number"],
  ["alpha", "Jensen Alpha", "percent"],
  ["benchmark_correlation", "基準相關係數", "number"],
  ["rebalance_count", "再平衡次數", "integer"],
];

function money(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("zh-TW", { style: "currency", currency: "TWD", maximumFractionDigits: 0 }).format(value)
    : "—";
}

function percent(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("zh-TW", { style: "percent", maximumFractionDigits: 2 }).format(value)
    : "—";
}

function number(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 3 }).format(value)
    : "—";
}

function integer(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 }).format(value)
    : "—";
}

function formatMetric(value: unknown, kind: "money" | "percent" | "number" | "integer"): string {
  if (kind === "money") return money(value);
  if (kind === "percent") return percent(value);
  if (kind === "integer") return integer(value);
  return number(value);
}

function allocationRows(result: BacktestResult) {
  const symbols = new Set([
    ...Object.keys(result.target_allocation),
    ...Object.keys(result.final_allocation),
  ]);
  return [...symbols]
    .map((symbol) => ({
      symbol,
      target: result.target_allocation[symbol] ?? 0,
      final: result.final_allocation[symbol] ?? 0,
    }))
    .sort((left, right) => right.target - left.target);
}

function drawdownSeries(result: BacktestResult) {
  let peak = 0;
  return result.series
    .filter((point): point is typeof point & { return_index: number } => typeof point.return_index === "number")
    .map((point) => {
      peak = Math.max(peak, point.return_index);
      return { date: point.date, value: peak > 0 ? point.return_index / peak - 1 : 0 };
    });
}

function AuditAssetTable({ assets }: { assets: AssetPreflight[] }) {
  return (
    <div className="table-scroll" role="region" aria-label="資產資料稽核" tabIndex={0}>
      <table className="data-table audit-table">
        <thead>
          <tr>
            <th scope="col">代碼</th>
            <th scope="col">狀態</th>
            <th scope="col">報價幣別</th>
            <th scope="col">有效期間</th>
            <th scope="col">觀察數</th>
            <th scope="col">公司行為</th>
            <th scope="col">FX 方法</th>
            <th scope="col">TWD 指紋</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => {
            const corporate = asset.corporate_action_audit as Record<string, unknown> | null | undefined;
            const fx = asset.fx_audit as Record<string, unknown> | null | undefined;
            return (
              <tr key={asset.symbol}>
                <th scope="row">{asset.symbol}</th>
                <td><span className={`status-pill ${asset.status}`}>{asset.status === "ready" ? "可用" : "失敗"}</span></td>
                <td>{asset.quote_currency ?? "—"}</td>
                <td>{asset.effective_start && asset.effective_end ? `${asset.effective_start} → ${asset.effective_end}` : asset.detail ?? "—"}</td>
                <td>{integer(asset.observations)}</td>
                <td>{String(corporate?.status ?? "—")}</td>
                <td>{String(fx?.method ?? "—")}</td>
                <td><code>{asset.fingerprints.adjusted_close_twd?.slice(0, 14) ?? "—"}</code></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Overview({ result }: { result: BacktestResult }) {
  return (
    <div className="result-stack">
      <div className="metric-grid">
        {CORE_METRICS.map(([key, label, kind]) => (
          <article className="metric-card" key={key}>
            <span>{label}</span>
            <strong>{formatMetric(result.metrics[key], kind)}</strong>
            {key === "money_weighted_return" && <small>XIRR：{result.xirr.status}</small>}
          </article>
        ))}
      </div>
      <div className="two-column-results">
        <article className="subcard">
          <h3>成本與現金流</h3>
          <dl className="definition-grid">
            <div><dt>投入</dt><dd>{money(result.metrics.contributions)}</dd></div>
            <div><dt>提領</dt><dd>{money(result.metrics.withdrawals)}</dd></div>
            <div><dt>交易成本</dt><dd>{money(result.metrics.transaction_costs)}</dd></div>
            <div><dt>借款成本</dt><dd>{money(result.metrics.borrowing_costs)}</dd></div>
            <div><dt>累計收入</dt><dd>{money(result.metrics.total_income)}</dd></div>
            <div><dt>淨損益</dt><dd>{money(result.metrics.net_profit)}</dd></div>
          </dl>
        </article>
        <article className="subcard">
          <h3>尾端風險</h3>
          <dl className="definition-grid">
            <div><dt>方法</dt><dd>{String(result.tail_risk.method ?? "—")}</dd></div>
            <div><dt>期間</dt><dd>{String(result.tail_risk.horizon ?? "—")}</dd></div>
            <div><dt>信賴水準</dt><dd>{percent(result.tail_risk.confidence)}</dd></div>
            <div><dt>VaR</dt><dd>{percent(result.tail_risk.var)}</dd></div>
            <div><dt>CVaR</dt><dd>{percent(result.tail_risk.cvar)}</dd></div>
            <div><dt>樣本</dt><dd>{integer(result.tail_risk.observations)}</dd></div>
          </dl>
        </article>
      </div>
    </div>
  );
}

function AnalyticsPanel({ analytics }: { analytics: Record<string, unknown> }) {
  const entries = Object.entries(analytics);
  if (!entries.length) return <div className="empty-state">本次未啟用進階分析，或分析資料不足。</div>;
  return (
    <div className="analytics-grid">
      {entries.map(([name, value]) => (
        <article className="subcard analytics-card" key={name}>
          <h3>{name.replaceAll("_", " ")}</h3>
          <pre>{JSON.stringify(value, null, 2)}</pre>
        </article>
      ))}
    </div>
  );
}

export function ResultsDashboard({
  response,
  preflight,
  onExportJson,
  onExportCsv,
}: {
  response: BacktestResponse;
  preflight: PreflightResponse | null;
  onExportJson: () => void;
  onExportCsv: () => void;
}) {
  const allResults = useMemo(
    () => [...response.results, ...(response.benchmark ? [response.benchmark] : [])],
    [response],
  );
  const [selectedName, setSelectedName] = useState(response.results[0]?.name ?? response.benchmark?.name ?? "");
  const [tab, setTab] = useState<ResultTab>("overview");
  const [logScale, setLogScale] = useState(true);
  const selected = allResults.find((item) => item.name === selectedName) ?? allResults[0];

  if (!selected) {
    return (
      <section className="workspace-card results-card" id="portfolio-results">
        <div className="empty-state">沒有成功的投資組合結果。請查看失敗與警告明細。</div>
      </section>
    );
  }

  const growthSeries = allResults.map((item) => ({
    name: item.display_name,
    points: item.series
      .filter((point): point is typeof point & { value: number } => typeof point.value === "number")
      .map((point) => ({ date: point.date, value: point.value })),
  }));
  const incomeSeries = allResults.map((item) => ({
    name: item.display_name,
    points: item.series
      .filter((point): point is typeof point & { cumulative_income: number } => typeof point.cumulative_income === "number")
      .map((point) => ({ date: point.date, value: point.cumulative_income })),
  }));
  const drawdown = drawdownSeries(selected);
  const allocation = allocationRows(selected);
  const selectedResultStart = selected.series[0]?.date ?? "—";
  const selectedResultEnd = selected.series[selected.series.length - 1]?.date ?? "—";

  return (
    <section className="workspace-card results-card" id="portfolio-results" aria-labelledby="results-title">
      <div className="section-heading result-heading">
        <div>
          <span className="section-index">03</span>
          <div>
            <h2 id="results-title">回測結果</h2>
            <p>要求期間 {response.requested_start} → {response.requested_end} · 有效截止 {response.effective_end} · TWD · {response.schema_version}</p>
          </div>
        </div>
        <div className="section-actions">
          <button type="button" className="secondary" onClick={onExportCsv}>匯出 CSV</button>
          <button type="button" className="secondary" onClick={onExportJson}>匯出 JSON</button>
        </div>
      </div>

      <PortfolioComparison results={response.results} />

      <div className="result-toolbar">
        <label className="field compact-field">
          <span>檢視投組</span>
          <select value={selected.name} onChange={(event) => setSelectedName(event.target.value)}>
            {allResults.map((item) => <option key={item.name} value={item.name}>{item.display_name}</option>)}
          </select>
        </label>
        <div className="result-meta" aria-label="回測執行資訊">
          <span>結果期間 {selectedResultStart} → {selectedResultEnd}</span>
          <span>Request {response.request_id.slice(0, 8)}</span>
          <span>市場資料 {number(response.timing.market_ms)} ms</span>
          <span>計算 {number(response.timing.compute_ms)} ms</span>
        </div>
      </div>

      {(response.warnings.length > 0 || selected.warnings.length > 0) && (
        <div className="notice warning" role="status">
          <strong>警告</strong>
          <ul>{[...new Set([...response.warnings, ...selected.warnings])].map((warning) => <li key={warning}>{warning}</li>)}</ul>
        </div>
      )}

      <div className="result-tabs" role="tablist" aria-label="回測結果頁籤">
        {TABS.map((item) => (
          <button
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-controls={`panel-${item.id}`}
            aria-selected={tab === item.id}
            tabIndex={tab === item.id ? 0 : -1}
            className={tab === item.id ? "active" : ""}
            onClick={() => setTab(item.id)}
            key={item.id}
          >{item.label}</button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="result-panel">
        {tab === "overview" && <Overview result={selected} />}
        {tab === "growth" && (
          <div className="result-stack">
            <div className="panel-toolbar">
              <h3>資產成長曲線</h3>
              <label className="inline-toggle"><input type="checkbox" checked={logScale} onChange={(event) => setLogScale(event.target.checked)} /> 對數尺度</label>
            </div>
            <LineChart series={growthSeries} title="投資組合資產成長曲線" logScale={logScale} />
          </div>
        )}
        {tab === "drawdown" && (
          <div className="result-stack">
            <LineChart series={[{ name: selected.display_name, points: drawdown }]} title={`${selected.display_name} 回撤曲線`} yFormat="percent" />
            <div className="table-scroll" role="region" aria-label="主要回撤事件" tabIndex={0}>
              <table className="data-table">
                <thead><tr><th>高點</th><th>谷底</th><th>復原</th><th>深度</th><th>天數</th><th>狀態</th></tr></thead>
                <tbody>{selected.drawdown_events.map((event) => <tr key={`${event.peak}-${event.trough}`}><td>{event.peak}</td><td>{event.trough}</td><td>{event.recovery ?? "—"}</td><td>{percent(event.depth)}</td><td>{integer(event.duration_days)}</td><td>{event.recovered ? "已復原" : "尚未復原"}</td></tr>)}</tbody>
              </table>
            </div>
          </div>
        )}
        {tab === "annual" && (
          <div className="result-stack">
            <BarChart labels={selected.annual_returns.map((item) => item.period)} values={selected.annual_returns.map((item) => item.return_value)} title="年度報酬" />
            <div className="table-scroll" role="region" aria-label="年度報酬表" tabIndex={0}>
              <table className="data-table"><thead><tr><th>年度</th><th>期間</th><th>報酬</th><th>完整性</th></tr></thead><tbody>{selected.annual_returns.map((item) => <tr key={item.period}><th scope="row">{item.period}</th><td>{item.start} → {item.end}</td><td>{percent(item.return_value)}</td><td>{item.partial ? "部分年度" : "完整年度"}</td></tr>)}</tbody></table>
            </div>
          </div>
        )}
        {tab === "monthly" && <MonthlyHeatmap periods={selected.monthly_returns.map((item) => ({ period: item.period, value: item.return_value, partial: item.partial }))} />}
        {tab === "income" && (
          <div className="result-stack">
            <LineChart series={incomeSeries} title="累計配發收入" />
            <dl className="definition-grid wide"><div><dt>累計配發</dt><dd>{money(selected.metrics.total_income)}</dd></div><div><dt>累計投入</dt><dd>{money(selected.metrics.contributions)}</dd></div><div><dt>累計提領</dt><dd>{money(selected.metrics.withdrawals)}</dd></div><div><dt>借款成本</dt><dd>{money(selected.metrics.borrowing_costs)}</dd></div></dl>
          </div>
        )}
        {tab === "allocation" && (
          <div className="table-scroll" role="region" aria-label="目標與期末配置" tabIndex={0}>
            <table className="data-table"><thead><tr><th>資產</th><th>目標配置</th><th>期末配置</th><th>偏離</th></tr></thead><tbody>{allocation.map((item) => <tr key={item.symbol}><th scope="row">{item.symbol}</th><td>{percent(item.target)}</td><td>{percent(item.final)}</td><td>{percent(item.final - item.target)}</td></tr>)}</tbody></table>
          </div>
        )}
        {tab === "analytics" && <AnalyticsPanel analytics={selected.analytics} />}
        {tab === "audit" && (
          <div className="result-stack">
            <AuditAssetTable assets={response.assets} />
            {preflight?.analysis_dependencies.length ? <><h3>分析依賴</h3><AuditAssetTable assets={preflight.analysis_dependencies} /></> : null}
            <article className="subcard"><h3>可重現性</h3><pre>{JSON.stringify(response.reproducibility, null, 2)}</pre></article>
            {response.failures.length > 0 && <article className="subcard danger-card"><h3>失敗投組</h3><pre>{JSON.stringify(response.failures, null, 2)}</pre></article>}
          </div>
        )}
      </div>
    </section>
  );
}
