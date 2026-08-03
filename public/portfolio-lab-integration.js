const PORTFOLIO_LAB_INTEGRATED_ROW_CLASS = "integrated-portfolio-row";
let lastIntegratedPortfolioRequestId = "";

function integratedPortfolioValue(headerText, result) {
  const label = headerText.trim();
  const metrics = result.metrics || {};
  if (label.includes("股票代碼")) return `投組｜${result.display_name || result.name}`;
  if (label.includes("候選")) return "投組";
  if (label.includes("區間總報酬")) return formatPercent(metrics.total_return);
  if (label.includes("年化報酬率")) return formatPercent(metrics.cagr);
  if (label.includes("年化波動率")) return formatPercent(metrics.volatility);
  if (label.includes("最大回撤")) return formatPercent(metrics.max_drawdown);
  if (label === "Sharpe") return formatNumber(metrics.sharpe_ratio);
  if (label === "Sortino") return formatNumber(metrics.sortino_ratio);
  if (label === "Beta") return formatNumber(metrics.beta);
  if (label === "Alpha") return formatPercent(metrics.alpha);
  if (label.includes("資料覆蓋率")) return "100.00%";
  if (label.includes("交易日")) return String(result.series?.length || 0);
  if (label.includes("資料區間")) {
    const first = result.series?.[0]?.date;
    const last = result.series?.at?.(-1)?.date || result.series?.[result.series.length - 1]?.date;
    return first && last ? `${first} ～ ${last}` : "—";
  }
  return "—";
}

function removeIntegratedPortfolioRows() {
  document.querySelectorAll(`.${PORTFOLIO_LAB_INTEGRATED_ROW_CLASS}`).forEach((row) => row.remove());
  lastIntegratedPortfolioRequestId = "";
}

function openIntegratedPortfolioResult() {
  const dialog = document.querySelector("#integrated-backtest-dialog");
  if (dialog && !dialog.open) dialog.showModal();
  document.querySelector("#pl-results")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function synchronizeIntegratedPortfolioRows() {
  if (typeof response === "undefined" || !response?.results?.length) return;
  const requestId = String(response.request_id || response.generated_at || "portfolio-result");
  if (requestId === lastIntegratedPortfolioRequestId) return;
  const table = document.querySelector("#scan-table");
  const body = table?.querySelector("tbody");
  const headers = [...(table?.querySelectorAll("thead th") || [])];
  if (!body || !headers.length) return;

  removeIntegratedPortfolioRows();
  for (const result of response.results) {
    const row = document.createElement("tr");
    row.className = PORTFOLIO_LAB_INTEGRATED_ROW_CLASS;
    row.tabIndex = 0;
    row.setAttribute("role", "button");
    row.setAttribute("aria-label", `開啟投資組合結果：${result.display_name || result.name}`);
    for (const header of headers) {
      const cell = document.createElement("td");
      cell.textContent = integratedPortfolioValue(header.textContent, result);
      row.append(cell);
    }
    row.addEventListener("click", openIntegratedPortfolioResult);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openIntegratedPortfolioResult();
      }
    });
    body.prepend(row);
  }
  lastIntegratedPortfolioRequestId = requestId;
}

function installPortfolioLabResultIntegration() {
  const root = document.querySelector("#portfolio-lab");
  if (!root) return;
  const observer = new MutationObserver(() => synchronizeIntegratedPortfolioRows());
  observer.observe(root, { childList: true, subtree: true });
  document.addEventListener("submit", (event) => {
    if (event.target?.id === "scan-form") removeIntegratedPortfolioRows();
  }, true);
  synchronizeIntegratedPortfolioRows();
}

installPortfolioLabResultIntegration();
