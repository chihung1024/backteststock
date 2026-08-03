function allResults() { return response ? [...(response.results || []), ...(response.benchmark ? [response.benchmark] : [])] : []; }
const METRICS = [
  ["initial_balance", "初始金額", "money"], ["final_balance", "期末金額", "money"], ["net_profit", "淨利", "money"],
  ["contributions", "投入金額", "money"], ["withdrawals", "提領金額", "money"], ["transaction_costs", "交易成本", "money"], ["borrowing_costs", "借款成本", "money"],
  ["rebalance_count", "再平衡次數", "number"], ["total_return", "總報酬", "percent"], ["cagr", "CAGR", "percent"], ["money_weighted_return", "XIRR", "percent"],
  ["volatility", "年化波動率", "percent"], ["max_drawdown", "最大回撤", "percent"], ["sharpe_ratio", "Sharpe", "number"], ["sortino_ratio", "Sortino", "number"],
  ["calmar_ratio", "Calmar", "number"], ["var_95_daily", "VaR 95%（日）", "percent"], ["cvar_95_daily", "CVaR 95%（日）", "percent"],
  ["best_year", "最佳年度", "percent"], ["worst_year", "最差年度", "percent"], ["positive_month_ratio", "正報酬月份", "percent"],
  ["beta", "Beta", "number"], ["alpha", "Alpha", "percent"], ["benchmark_correlation", "基準相關係數", "number"],
  ["real_total_return", "實質總報酬", "percent"], ["real_cagr", "實質 CAGR", "percent"], ["cumulative_inflation", "累計通膨", "percent"],
];
function formatMetric(value, type) { if (value == null) return "—"; if (type === "money") return formatMoney(value); if (type === "percent") return formatPercent(value); return formatNumber(value); }
function resultTabs() {
  const tabs = [["overview", t("overview")], ["growth", t("growthTab")], ["drawdown", t("drawdownTab")], ["annual", t("annualTab")], ["monthly", t("monthlyTab")], ["income", t("incomeTab")], ["allocation", t("allocationTab")], ["analytics", t("analyticsTab")]];
  return e("div", { className: "pl-result-tabs", attributes: { role: "tablist" } }, tabs.map(([key, label]) => {
    const button = e("button", { className: activeResultTab === key ? "active" : "", text: label, attributes: { type: "button", role: "tab", "aria-selected": String(activeResultTab === key) } });
    button.addEventListener("click", () => { activeResultTab = key; renderResultContent(); }); return button;
  }));
}
function renderResults() {
  const shell = e("section", { className: "pl-results", attributes: { id: "pl-results" } });
  const header = e("div", { className: "pl-results-header" }, [e("div", {}, [e("span", { className: "eyebrow", text: "PORTFOLIO PERFORMANCE" }), e("h2", { text: t("results") }), e("p", { text: `${response.effective_start} → ${response.effective_end} · ${response.base_currency} · data ${response.data_as_of}` })]), e("div", { className: "pl-toolbar-actions" })]);
  const csv = e("button", { className: "button secondary", text: t("exportCsv"), attributes: { type: "button" } }); csv.addEventListener("click", exportCsv);
  const json = e("button", { className: "button ghost", text: t("exportJson"), attributes: { type: "button" } }); json.addEventListener("click", () => download("portfolio-backtest-results.json", JSON.stringify(response, null, 2)));
  header.querySelector(".pl-toolbar-actions").append(csv, json); shell.append(header);
  if (response.warnings?.length) shell.append(e("details", { className: "pl-warning" }, [e("summary", { text: `${t("warnings")} (${response.warnings.length})` }), e("ul", {}, response.warnings.map((warning) => e("li", { text: warning }))) ]));
  shell.append(resultTabs(), e("div", { className: "pl-result-content", attributes: { id: "pl-result-content" } }));
  requestAnimationFrame(renderResultContent); return shell;
}
function renderResultContent() {
  const target = mount?.querySelector("#pl-result-content"); if (!target || !response) return;
  const renderers = { overview: renderOverview, growth: () => renderSeriesChart("value"), drawdown: () => renderSeriesChart("drawdown"), annual: renderAnnual, monthly: renderMonthly, income: renderIncome, allocation: renderAllocation, analytics: renderAnalytics };
  target.replaceChildren(renderers[activeResultTab]?.() || e("p", { text: "—" }));
}
function renderOverview() {
  const results = allResults(); const root = e("div", { className: "pl-overview" });
  root.append(e("div", { className: "pl-summary-grid" }, results.map((result, index) => e("article", { className: "pl-summary", attributes: { style: `--series:${COLORS[index % COLORS.length]}` } }, [e("h3", { text: result.display_name || result.name }), e("strong", { text: formatMoney(result.metrics.final_balance) }), e("div", {}, [e("span", { text: `CAGR ${formatPercent(result.metrics.cagr)}` }), e("span", { text: `MDD ${formatPercent(result.metrics.max_drawdown)}` }), e("span", { text: `Sharpe ${formatNumber(result.metrics.sharpe_ratio)}` })])]))));
  const table = e("table", { className: "pl-metrics-table" }); const head = e("tr", {}, [e("th", { text: state.locale === "en" ? "Metric" : "指標" }), ...results.map((item) => e("th", { text: item.display_name || item.name }))]); table.append(e("thead", {}, [head]));
  const body = e("tbody"); METRICS.filter(([key]) => results.some((item) => item.metrics?.[key] != null)).forEach(([key, label, type]) => body.append(e("tr", {}, [e("th", { text: label }), ...results.map((item) => e("td", { text: formatMetric(item.metrics?.[key], type) }))]))); table.append(body); root.append(e("div", { className: "pl-table-wrap" }, [table])); return root;
}
function mergeSeries(key) {
  const map = new Map(); allResults().forEach((result, index) => (result.series || []).forEach((point) => { if (!map.has(point.date)) map.set(point.date, { date: point.date }); map.get(point.date)[index] = number(point[key]); })); return [...map.values()].sort((a, b) => a.date.localeCompare(b.date));
}
function renderSeriesChart(key) {
  const root = e("div", { className: "pl-chart-shell" });
  let scale = null;
  if (key === "value") {
    const toolbar = e("div", { className: "pl-chart-toolbar" }, [e("strong", { text: state.locale === "en" ? "Y-axis" : "Y 軸尺度" })]);
    scale = select("log", [["linear", state.locale === "en" ? "Linear" : "線性"], ["log", state.locale === "en" ? "Log" : "對數"]], () => {}); toolbar.append(scale); root.append(toolbar);
  }
  const canvas = e("canvas", { className: "pl-chart", attributes: { "aria-label": activeResultTab } });
  if (scale) scale.addEventListener("change", () => drawLineChart(canvas, mergeSeries(key), allResults(), key, scale.value));
  root.append(canvas, renderLegend(allResults())); requestAnimationFrame(() => drawLineChart(canvas, mergeSeries(key), allResults(), key, scale?.value || "linear")); return root;
}
function renderLegend(results) { return e("div", { className: "pl-legend" }, results.map((item, index) => e("span", {}, [e("i", { attributes: { style: `background:${COLORS[index % COLORS.length]}` } }), e("span", { text: item.display_name || item.name })]))); }
function drawLineChart(canvas, rows, results, key, scaleMode) {
  const rect = canvas.getBoundingClientRect(); const dpr = devicePixelRatio || 1; const width = Math.max(640, rect.width); const height = Math.max(360, rect.height || 420); canvas.width = width * dpr; canvas.height = height * dpr;
  const ctx = canvas.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, width, height); const pad = { l: 78, r: 20, t: 20, b: 42 };
  const points = rows.flatMap((row) => results.map((_, index) => ({ x: Date.parse(row.date), y: row[index] })).filter((point) => Number.isFinite(point.y) && (scaleMode !== "log" || point.y > 0)));
  if (!points.length) { ctx.fillText("No data", 20, 30); return; }
  const minX = Math.min(...points.map((p) => p.x)); const maxX = Math.max(...points.map((p) => p.x)); const transform = (value) => scaleMode === "log" ? Math.log10(value) : value; let minY = Math.min(...points.map((p) => transform(p.y))); let maxY = Math.max(...points.map((p) => transform(p.y))); const extra = Math.max((maxY - minY) * .08, .01); minY -= extra; maxY += extra;
  ctx.font = "12px system-ui"; ctx.textBaseline = "middle";
  for (let i = 0; i <= 5; i += 1) { const ratio = i / 5; const y = pad.t + ratio * (height - pad.t - pad.b); ctx.strokeStyle = "#d7e0e8"; ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(width - pad.r, y); ctx.stroke(); const value = scaleMode === "log" ? 10 ** (maxY - ratio * (maxY - minY)) : maxY - ratio * (maxY - minY); ctx.fillStyle = "#64748b"; ctx.textAlign = "right"; ctx.fillText(key === "value" ? formatMoney(value) : formatPercent(value), pad.l - 8, y); }
  results.forEach((_, index) => { ctx.strokeStyle = COLORS[index % COLORS.length]; ctx.lineWidth = 2.5; ctx.beginPath(); let started = false; rows.forEach((row) => { const yValue = row[index]; if (!Number.isFinite(yValue) || (scaleMode === "log" && yValue <= 0)) return; const x = pad.l + ((Date.parse(row.date) - minX) / Math.max(maxX - minX, 1)) * (width - pad.l - pad.r); const y = pad.t + (1 - (transform(yValue) - minY) / Math.max(maxY - minY, 1)) * (height - pad.t - pad.b); if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y); }); ctx.stroke(); });
}
function renderAnnual() {
  const results = allResults();
  const years = [...new Set(results.flatMap((item) => Object.keys(item.annual_returns || {})))].sort();
  const table = e("table", { className: "pl-metrics-table" });
  table.append(e("thead", {}, [e("tr", {}, [e("th", { text: state.locale === "en" ? "Year" : "年度" }), ...results.map((item) => e("th", { text: item.display_name || item.name }))])]));
  table.append(e("tbody", {}, years.map((year) => e("tr", {}, [e("th", { text: year }), ...results.map((item) => e("td", { text: formatPercent(item.annual_returns?.[year]) }))]))));
  return e("div", { className: "pl-table-wrap" }, [table]);
}
function resultSelector(onChange) {
  return select(String(selectedResult), allResults().map((item, index) => [String(index), item.display_name || item.name]), (value) => { selectedResult = Number(value); onChange(); });
}
function renderMonthly() {
  const root = e("div"); root.append(e("div", { className: "pl-chart-toolbar" }, [resultSelector(renderResultContent)]));
  const result = allResults()[selectedResult];
  const years = [...new Set((result?.monthly_returns || []).map((item) => item.year))].sort();
  const values = new Map((result?.monthly_returns || []).map((item) => [`${item.year}-${item.month}`, item.return]));
  const table = e("table", { className: "pl-heatmap" });
  table.append(e("thead", {}, [e("tr", {}, [e("th", { text: "Year" }), ...Array.from({ length: 12 }, (_, index) => e("th", { text: String(index + 1) }))])]));
  table.append(e("tbody", {}, years.map((year) => e("tr", {}, [e("th", { text: String(year) }), ...Array.from({ length: 12 }, (_, index) => { const value = values.get(`${year}-${index + 1}`); return e("td", { text: value == null ? "—" : formatPercent(value), attributes: { "data-heat": value == null ? "" : String(value) } }); })]))));
  root.append(e("div", { className: "pl-table-wrap" }, [table])); return root;
}
function renderIncome() {
  const results = allResults(); const years = [...new Set(results.flatMap((item) => Object.keys(item.income_by_year || {})))].sort();
  const table = e("table", { className: "pl-metrics-table" });
  table.append(e("thead", {}, [e("tr", {}, [e("th", { text: "Year" }), ...results.map((item) => e("th", { text: item.display_name || item.name }))])]));
  table.append(e("tbody", {}, years.map((year) => e("tr", {}, [e("th", { text: year }), ...results.map((item) => e("td", { text: formatMoney(item.income_by_year?.[year]) }))]))));
  return e("div", { className: "pl-table-wrap" }, [table]);
}
function renderAllocation() {
  return e("div", { className: "pl-allocation-grid" }, (response.results || []).map((result) => e("article", { className: "pl-allocation-card" }, [e("h3", { text: result.display_name || result.name }), e("h4", { text: state.locale === "en" ? "Target" : "目標配置" }), allocationBars(result.target_allocation), e("h4", { text: state.locale === "en" ? "Final" : "期末配置" }), allocationBars(result.final_allocation)])));
}
function allocationBars(values = {}) { return e("div", { className: "pl-bars" }, Object.entries(values).sort((a, b) => b[1] - a[1]).map(([symbol, value]) => e("div", {}, [e("span", { text: symbol }), e("i", { attributes: { style: `width:${Math.max(1, value * 100)}%` } }), e("strong", { text: formatPercent(value) })]))); }
function renderAnalytics() {
  const root = e("div", { className: "pl-analytics-grid" }); (response.results || []).forEach((result) => {
    const card = e("article", { className: "pl-analytics-card" }, [e("h3", { text: result.display_name || result.name })]);
    if (result.factor_analysis) card.append(objectPanel("Fama–French", result.factor_analysis));
    if (result.style_analysis) card.append(objectPanel(state.locale === "en" ? "Style" : "風格曝險", result.style_analysis));
    if (result.regime_analysis) card.append(objectPanel(state.locale === "en" ? "Regime" : "環境分析", result.regime_analysis));
    if (!result.factor_analysis && !result.style_analysis && !result.regime_analysis) card.append(e("p", { text: state.locale === "en" ? "No advanced analysis was enabled or available." : "未啟用進階分析，或資料來源暫時無法提供。" })); root.append(card);
  }); return root;
}
function objectPanel(title, value) { return e("details", { className: "pl-object-panel", attributes: { open: "" } }, [e("summary", { text: title }), e("pre", { text: JSON.stringify(value, null, 2) })]); }
function exportCsv() {
  const rows = allResults(); const keys = METRICS.map(([key]) => key); const lines = [["metric", ...rows.map((item) => item.display_name || item.name)].join(","), ...keys.map((key) => [key, ...rows.map((item) => item.metrics?.[key] ?? "")].map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))]; download("portfolio-backtest-results.csv", `\ufeff${lines.join("\n")}`, "text/csv;charset=utf-8");
}

function render() {
  if (!mount) return;
  document.documentElement.dataset.portfolioLabTheme = state.theme;
  mount.replaceChildren(renderHeader());
  const tabs = e("div", { className: "pl-config-tabs", attributes: { role: "tablist" } });
  [["settings", t("settings")], ["assets", t("assets")]].forEach(([key, label]) => { const button = e("button", { className: state.activeConfigTab === key ? "active" : "", text: label, attributes: { type: "button", role: "tab" } }); button.addEventListener("click", () => patch({ activeConfigTab: key })); tabs.append(button); }); mount.append(tabs);
  mount.append(e("div", { className: "pl-config-content" }, [state.activeConfigTab === "settings" ? renderSettings() : renderAssets()]));
  const message = e("div", { className: "pl-message", attributes: { id: "pl-message", role: "alert" } }); message.hidden = true;
  const runBar = e("div", { className: "pl-run-bar" }, [e("p", { text: state.locale === "en" ? "All results use daily TWD valuation. Complete portfolios must total 100%." : "所有資產依每日匯率換算 TWD；有效投組權重須合計 100%。" }), e("button", { className: "button primary", text: t("run"), attributes: { id: "pl-run", type: "button" } })]); runBar.querySelector("button").addEventListener("click", runBacktest); mount.append(message, runBar); if (response) mount.append(renderResults());
}

function prepareEqualWeightPortfolio(tickers, source = {}) {
  const symbols = [...new Set((tickers || []).map((value) => String(value).trim().toUpperCase()).filter(Boolean))].slice(0, MAX_ASSETS);
  if (!symbols.length) return false;
  state.portfolioCount = Math.max(1, Math.min(state.portfolioCount, MAX_PORTFOLIOS));
  state.portfolioNames[0] = state.locale === "en" ? "Selected equal weight" : "績效列表已選標的等權組合";
  const base = Math.floor((100 / symbols.length) * 100) / 100;
  state.assets = symbols.map((symbol, index) => ({ id: id(), symbol, weights: [index === symbols.length - 1 ? Number((100 - base * (symbols.length - 1)).toFixed(2)) : base, ...Array(MAX_PORTFOLIOS - 1).fill("")] }));
  while (state.assets.length < 6) state.assets.push(blankAsset());
  if (source.startDate) state.startDate = source.startDate;
  if (source.endDate) state.endDate = source.endDate;
  if (source.benchmark) state.benchmark = source.benchmark;
  state.activeConfigTab = "assets"; persist(); render(); return true;
}

function initialize() {
  panel = document.querySelector(PANEL_SELECTOR); if (!panel) return;
  panel.replaceChildren(); panel.classList.add("portfolio-lab-panel");
  mount = e("div", { className: "portfolio-lab", attributes: { id: "portfolio-lab" } }); panel.append(mount); render();
  window.PortfolioLab = { prepareEqualWeightPortfolio, getState: () => structuredClone(state), run: runBacktest };
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, { once: true }); else initialize();
