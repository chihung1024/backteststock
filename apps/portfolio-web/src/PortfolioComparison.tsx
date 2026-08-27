import type { BacktestResult } from "./types";

const COMPARISON_METRICS: Array<[
  string,
  string,
  "money" | "percent" | "number" | "integer"
]> = [
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
    ? new Intl.NumberFormat("zh-TW", {
        style: "currency",
        currency: "TWD",
        maximumFractionDigits: 0,
      }).format(value)
    : "—";
}

function percent(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("zh-TW", {
        style: "percent",
        maximumFractionDigits: 2,
      }).format(value)
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

function formatMetric(
  value: unknown,
  kind: "money" | "percent" | "number" | "integer",
): string {
  if (kind === "money") return money(value);
  if (kind === "percent") return percent(value);
  if (kind === "integer") return integer(value);
  return number(value);
}

function resultWindow(result: BacktestResult): { start: string | null; end: string | null } {
  return {
    start: typeof result.metrics.start === "string" ? result.metrics.start : null,
    end: typeof result.metrics.end === "string" ? result.metrics.end : null,
  };
}

export function PortfolioComparison({ results }: { results: BacktestResult[] }) {
  if (results.length < 2) return null;

  const windows = results.map(resultWindow);
  const first = windows[0]!;
  const comparable = Boolean(
    first.start
      && first.end
      && windows.every((window) => window.start === first.start && window.end === first.end),
  );
  const commonPeriod = comparable ? `${first.start} → ${first.end}` : "期間不一致，禁止直接比較";

  return (
    <article className="subcard" aria-labelledby="portfolio-comparison-title">
      <div className="panel-toolbar">
        <div>
          <h3 id="portfolio-comparison-title">投資組合並排比較</h3>
          <p>
            共同比較期間：<strong>{commonPeriod}</strong>
          </p>
        </div>
      </div>

      {!comparable && (
        <div className="notice warning" role="status">
          <strong>比較已停用</strong>
          <p>後端結果沒有使用完全相同的起訖期間；請勿用這些績效指標做橫向結論。</p>
        </div>
      )}

      <div className="table-scroll" role="region" aria-label="投資組合並排比較" tabIndex={0}>
        <table className="data-table comparison-table">
          <thead>
            <tr>
              <th scope="col">指標</th>
              {results.map((result) => (
                <th scope="col" key={result.name}>{result.name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">共同比較期間</th>
              {results.map((result, index) => (
                <td key={result.name}>
                  {windows[index]!.start && windows[index]!.end
                    ? `${windows[index]!.start} → ${windows[index]!.end}`
                    : "—"}
                </td>
              ))}
            </tr>
            {COMPARISON_METRICS.map(([key, label, kind]) => (
              <tr key={key}>
                <th scope="row">{label}</th>
                {results.map((result) => (
                  <td key={result.name}>{comparable ? formatMetric(result.metrics[key], kind) : "—"}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        <small>
          資料預檢仍保留各投組原始有效期間；本表只呈現後端在共同交集期間重新初始化後的可比較結果。
        </small>
      </p>
    </article>
  );
}
