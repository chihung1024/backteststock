from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one literal match, found {count}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str, *, flags: int = 0) -> None:
    text = read(path)
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, found {count}: {pattern[:100]!r}")
    write(path, updated)


replace_once(
    "public/app.js",
    '''import {
  METRIC_CACHE_MIGRATION_RELOAD_PENDING,
  METRIC_DEFINITION_VERSION,
} from "./scan-score-formulas.js?v=20260803.3";''',
    '''import {
  METRIC_CACHE_MIGRATION_RELOAD_PENDING,
  METRIC_DEFINITION_VERSION,
  SCORE_FORMULAS,
  buildScoreMatrix,
  scoreRecordFor,
} from "./scan-score-formulas.js?v=20260803.4";''',
)
replace_once(
    "public/app.js",
    '''} from "./scan-coverage.js?v=20260803.1";''',
    '''} from "./scan-coverage.js?v=20260803.2";''',
)
regex_once(
    "public/app.js",
    r'''const SCAN_METRICS = \[
.*?
\];
const SCAN_CHUNK_SIZE''',
    '''const SCORE_FORMULA_BY_KEY = new Map(
  SCORE_FORMULAS.map((formula) => [formula.key, formula]),
);
const SCAN_METRICS = [
  ["total_return", "區間總報酬", "percent", "positive"],
  ["cagr", "年化報酬率", "percent", "positive"],
  ["volatility", "年化波動率", "percent", "negative"],
  ["mdd", "最大回撤", "percent", "negative"],
  ["sharpe_ratio", "Sharpe", "number", "positive"],
  ["sortino_ratio", "Sortino", "number", "positive"],
  ["beta", "Beta", "number", ""],
  ["alpha", "Alpha", "percent", "positive"],
  ...SCORE_FORMULAS.map((formula) => [
    formula.key,
    formula.label,
    "score",
    "",
  ]),
  ["data_coverage", "資料覆蓋率", "percent", ""],
  ["trading_days", "交易日", "integer", ""],
];
const SCAN_CHUNK_SIZE''',
    flags=re.S,
)
replace_once(
    "public/app.js",
    '''  openManualOptimizer: document.querySelector("#open-manual-optimizer"),''',
    '''  openManualOptimizer: document.querySelector("#open-manual-optimizer"),
  openIntegratedBacktest: document.querySelector("#open-integrated-backtest"),
  integratedBacktestDialog: document.querySelector("#integrated-backtest-dialog"),
  closeIntegratedBacktest: document.querySelector("#close-integrated-backtest"),''',
)

regex_once(
    "public/app.js",
    r'''function renderManualOptimizerSelectionControls\(selection\) \{
.*?
\}

function renderScanCoverageFilterStatus''',
    '''function renderManualOptimizerSelectionControls(selection) {
  const count = selection.tickers.length;
  const optimizerReady = count >= MIN_MANUAL_OPTIMIZER_TICKERS;
  const backtestReady = count >= 1;
  dom.optimizerManualSelectionStatus.textContent = [
    `已選 ${count.toLocaleString("zh-TW")} / ${MAX_MANUAL_OPTIMIZER_TICKERS} 檔`,
    optimizerReady ? "可建立固定來源池" : `最佳化器至少選 ${MIN_MANUAL_OPTIMIZER_TICKERS} 檔`,
  ].join(" · ");
  dom.clearOptimizerSelection.disabled = count === 0;
  dom.openIntegratedBacktest.disabled = !backtestReady;
  dom.openIntegratedBacktest.textContent = backtestReady
    ? `建立 ${count.toLocaleString("zh-TW")} 檔投資組合回測`
    : "建立投資組合回測";
  dom.openManualOptimizer.textContent = `使用已選 ${count.toLocaleString("zh-TW")} 檔開啟最佳化器`;
  dom.openManualOptimizer.setAttribute("aria-disabled", String(!optimizerReady));
  dom.openManualOptimizer.tabIndex = optimizerReady ? 0 : -1;
  dom.openManualOptimizer.classList.toggle("disabled", !optimizerReady);
}

function renderScanCoverageFilterStatus''',
    flags=re.S,
)
regex_once(
    "public/app.js",
    r'''function renderScanCoverageFilterStatus\(stats = scanCoverageStats\(\)\) \{
.*?
\}

function updateScanMinCoverage''',
    '''function renderScanCoverageFilterStatus(stats = scanCoverageStats()) {
  const threshold = `${formatScanCoveragePercent(scanMinCoveragePercent)}%`;
  const reference = stats.maximumTradingDays
    ? `基準交易日 ${stats.maximumTradingDays.toLocaleString("zh-TW")}`
    : "尚無基準交易日";
  dom.scanCoverageFilterStatus.textContent = [
    `符合 ${stats.shown.length.toLocaleString("zh-TW")} / ${stats.settled.length.toLocaleString("zh-TW")} 檔`,
    `門檻 ≥ ${threshold}`,
    stats.hidden ? `隱藏 ${stats.hidden.toLocaleString("zh-TW")} 檔` : "沒有低覆蓋率標的",
    reference,
  ].join(" · ");
}

function updateScanMinCoverage''',
    flags=re.S,
)

new_render_scan_table = r'''function formatScanTableMetric(item, key, type) {
  if (type !== "score") return formatMetric(item[key], type);
  const formula = SCORE_FORMULA_BY_KEY.get(key);
  const score = Number(item[key]);
  const rank = Number(item[formula?.rankKey]);
  if (!formula || !Number.isFinite(score) || !Number.isInteger(rank)) return "—";
  return `#${rank} · ${score.toFixed(formula.digits)}`;
}

function scorePortfolioRows(rows) {
  const matrix = buildScoreMatrix(rows);
  return rows.map((item) => {
    const scored = { ...item };
    for (const formula of SCORE_FORMULAS) {
      const record = scoreRecordFor(matrix, item.ticker, formula.key);
      scored[formula.key] = Number.isFinite(record?.score) ? record.score : null;
      scored[formula.rankKey] = Number.isInteger(record?.rank) ? record.rank : null;
      scored[formula.statusKey] = record?.status || "missing";
    }
    return scored;
  });
}

function portfolioPerformanceRows(referenceTradingDays) {
  if (!Array.isArray(latestBacktest?.data)) return [];
  const rows = latestBacktest.data.map((item) => {
    const history = Array.isArray(item.portfolioHistory) ? item.portfolioHistory : [];
    const first = history.at(0);
    const last = history.at(-1);
    const tradingDays = history.length;
    return {
      ...item,
      row_type: "portfolio",
      ticker: item.name,
      status: "ok",
      retryable: false,
      trading_days: tradingDays,
      data_start: first?.date || null,
      data_end: last?.date || null,
      data_coverage: referenceTradingDays > 0
        ? Math.min(tradingDays / referenceTradingDays, 1)
        : null,
    };
  });
  return scorePortfolioRows(rows);
}

function renderScanTable() {
  const coverage = scanCoverageStats();
  const { shown, settled, hidden } = coverage;
  const manualSelection = reconcileManualOptimizerSelection(coverage);
  const sortedSuccessful = [...shown].sort((left, right) => {
    const a = Number(left[scanSort.key]);
    const b = Number(right[scanSort.key]);
    const safeA = Number.isFinite(a)
      ? a
      : (scanSort.direction === "asc" ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY);
    const safeB = Number.isFinite(b)
      ? b
      : (scanSort.direction === "asc" ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY);
    return scanSort.direction === "asc" ? safeA - safeB : safeB - safeA;
  });
  const failures = latestScan.filter((item) => Boolean(item?.error));
  const portfolioRows = portfolioPerformanceRows(coverage.maximumTradingDays);
  const sorted = [...portfolioRows, ...sortedSuccessful, ...failures];
  const totalPages = Math.max(1, Math.ceil(sorted.length / scanPageSize));
  scanPage = Math.min(Math.max(scanPage, 1), totalPages);
  const pageStart = (scanPage - 1) * scanPageSize;
  const visibleRows = sorted.slice(pageStart, pageStart + scanPageSize);

  const columns = [
    ["row_type", "類型", "text"],
    ["ticker", "股票／投組", "text"],
    ["optimizer_selection", "選取", "selection"],
    ...SCAN_METRICS.map(([key, label, type]) => [key, label, type]),
    ["data_range", "資料區間", "text"],
    ["actions", "操作", "action"],
  ];
  const thead = createElement("thead");
  const headerRow = createElement("tr");
  columns.forEach(([key, label]) => {
    const indicator = scanSort.key === key ? (scanSort.direction === "asc" ? " ▲" : " ▼") : "";
    const sortable = SCAN_METRICS.some(([metricKey]) => metricKey === key);
    const formula = SCORE_FORMULA_BY_KEY.get(key);
    const options = {
      text: `${label}${indicator}`,
      scope: "col",
      className: key === "optimizer_selection"
        ? "optimizer-select-column"
        : (sortable ? "sortable" : ""),
      dataset: {
        ...(sortable ? { sortKey: key } : {}),
        ...(formula ? { compositeMetric: key } : {}),
      },
      title: formula?.description || "",
    };
    if (sortable) {
      options.attributes = {
        "aria-sort": scanSort.key === key
          ? (scanSort.direction === "asc" ? "ascending" : "descending")
          : "none",
      };
    }
    headerRow.append(createElement("th", options));
  });
  thead.append(headerRow);

  const tbody = createElement("tbody");
  if (!visibleRows.length) {
    const row = createElement("tr", { dataset: { scanEmpty: "true" } });
    row.append(createElement("td", {
      text: `目前沒有符合資料覆蓋率 ≥ ${formatScanCoveragePercent(scanMinCoveragePercent)}% 的已完成回測結果。`,
      colSpan: columns.length,
      className: "scan-empty-state",
    }));
    tbody.append(row);
  } else {
    visibleRows.forEach((item) => {
      const portfolio = item.row_type === "portfolio";
      const ticker = sanitizeTicker(item.ticker);
      const failed = Boolean(item.error);
      const selected = !portfolio && manualSelection.tickers.includes(ticker);
      const selectable = !portfolio && !failed && manualSelection.selectable.has(ticker);
      const row = createElement("tr", {
        dataset: { ticker, rowType: portfolio ? "portfolio" : "stock" },
        className: portfolio
          ? "performance-portfolio-row"
          : (selected ? "optimizer-manual-selected" : ""),
      });
      row.append(createElement("td", {
        text: portfolio ? "投組" : "個股",
        className: "performance-type-cell",
      }));
      row.append(createElement("th", {
        text: item.note ? `${item.ticker} ${item.note}` : item.ticker,
        scope: "row",
      }));
      const selectionCell = createElement("td", { className: "optimizer-select-cell" });
      if (selectable) {
        selectionCell.append(createElement("input", {
          type: "checkbox",
          checked: selected,
          disabled: !selected && manualSelection.tickers.length >= MAX_MANUAL_OPTIMIZER_TICKERS,
          dataset: { optimizerTicker: ticker },
          ariaLabel: `選擇 ${ticker} 作為回測或最佳化來源股票`,
        }));
      } else {
        selectionCell.textContent = "—";
        if (!portfolio) {
          selectionCell.title = failed
            ? "回測失敗的標的不可列入投資組合或最佳化來源池。"
            : "比較基準不可同時列入來源股票池。";
        }
      }
      row.append(selectionCell);
      SCAN_METRICS.forEach(([key, , type, className], index) => {
        const formula = SCORE_FORMULA_BY_KEY.get(key);
        row.append(createElement("td", {
          text: failed
            ? (index === 0 ? item.error : "—")
            : formatScanTableMetric(item, key, type),
          className: failed
            ? ""
            : (formula
              ? (Number(item[key]) >= 0 ? "positive" : "negative")
              : className),
          dataset: formula ? { compositeMetric: key } : {},
          title: formula?.description || "",
        }));
      });
      row.append(createElement("td", {
        text: failed ? "—" : `${item.data_start || "—"} ～ ${item.data_end || "—"}`,
      }));
      const actionCell = createElement("td", { className: "performance-action-cell" });
      if (portfolio) {
        actionCell.append(createElement("button", {
          type: "button",
          className: "button ghost compact",
          text: "查看走勢",
          dataset: { action: "view-portfolio-result" },
        }));
      } else {
        actionCell.textContent = "—";
      }
      row.append(actionCell);
      tbody.append(row);
    });
  }
  dom.scanTable.replaceChildren(thead, tbody);
  dom.scanTable.dataset.minCoveragePercent = String(scanMinCoveragePercent);
  dom.scanPagination.classList.toggle("hidden", sorted.length <= scanPageSize);
  dom.scanPageStatus.textContent = `第 ${scanPage.toLocaleString("zh-TW")} / ${totalPages.toLocaleString("zh-TW")} 頁`;
  dom.scanPagePrev.disabled = scanPage <= 1;
  dom.scanPageNext.disabled = scanPage >= totalPages;
  renderScanCoverageFilterStatus({ ...coverage, shown, settled, hidden });
  renderManualOptimizerSelectionControls(manualSelection);
}
'''
regex_once(
    "public/app.js",
    r'''function renderScanTable\(\) \{
.*?
\}

function median''',
    new_render_scan_table + "\nfunction median",
    flags=re.S,
)

regex_once(
    "public/app.js",
    r'''function renderScanSummary\(\) \{
.*?
\}

function renderScanContext''',
    '''function renderScanSummary() {
  const coverage = scanCoverageStats();
  const valid = coverage.shown;
  const failed = latestScan.filter((item) => Boolean(item.error));
  const total = activeScanJob?.payload?.tickers?.length || latestScan.length;
  const unfinished = activeScanJob?.status === "completed"
    ? 0
    : Number(activeScanJob?.pending?.length || 0);
  const numeric = (key) => valid
    .map((item) => Number(item[key]))
    .filter(Number.isFinite);
  const average = (key) => {
    const values = numeric(key);
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  };
  const cards = [
    ["成功標的", `${coverage.settled.length} / ${total}`],
    ["失敗標的", failed.length.toLocaleString("zh-TW")],
    ["未完成", unfinished.toLocaleString("zh-TW")],
    ["符合覆蓋門檻", `${coverage.shown.length} / ${coverage.settled.length}`],
    ["CAGR 中位數", formatMetric(median(numeric("cagr")), "percent")],
    ["平均波動率", formatMetric(average("volatility"), "percent")],
    ["平均最大回撤", formatMetric(average("mdd"), "percent")],
    ["平均 Sharpe", formatMetric(average("sharpe_ratio"), "number")],
    ["覆蓋率中位數", formatMetric(median(numeric("data_coverage")), "percent")],
    ["最大基準交易日", coverage.maximumTradingDays
      ? coverage.maximumTradingDays.toLocaleString("zh-TW")
      : "—"],
  ];
  dom.scanSummary.replaceChildren(...cards.map(([label, value]) => createElement(
    "article",
    { className: "summary-card" },
    [
      createElement("span", { text: label }),
      createElement("strong", { text: value }),
    ],
  )));
}

function equalWeightAssets(tickers) {
  const count = tickers.length;
  const rounded = Number((100 / count).toFixed(2));
  let assigned = 0;
  return tickers.map((ticker, index) => {
    const weight = index === count - 1
      ? Number((100 - assigned).toFixed(2))
      : rounded;
    assigned += weight;
    return {
      id: crypto.randomUUID(),
      ticker,
      weight,
    };
  });
}

function openIntegratedBacktestBuilder() {
  const selection = reconcileManualOptimizerSelection();
  if (!selection.tickers.length) {
    setMessage(dom.scanError, "請先在績效列表勾選至少 1 檔股票。");
    return;
  }
  const payload = activeScanJob?.payload || {};
  state.settings.startPeriod = payload.startDate || defaultRange.startDate;
  state.settings.endPeriod = payload.endDate || defaultRange.endDate;
  state.settings.benchmark = scanBenchmarkTicker();
  state.portfolios = [{
    id: crypto.randomUUID(),
    name: "績效列表選股",
    assets: equalWeightAssets(selection.tickers),
  }];
  saveState();
  document.querySelector("#start-period").value = state.settings.startPeriod;
  document.querySelector("#end-period").value = state.settings.endPeriod;
  document.querySelector("#benchmark").value = state.settings.benchmark;
  renderPortfolios();
  setMessage(dom.backtestError);
  if (typeof dom.integratedBacktestDialog.showModal === "function") {
    dom.integratedBacktestDialog.showModal();
  } else {
    dom.integratedBacktestDialog.setAttribute("open", "");
  }
}

function closeIntegratedBacktestDialog() {
  if (typeof dom.integratedBacktestDialog.close === "function") {
    dom.integratedBacktestDialog.close();
  } else {
    dom.integratedBacktestDialog.removeAttribute("open");
  }
}

function viewIntegratedPortfolioResults() {
  if (!latestBacktest) return;
  if (!dom.integratedBacktestDialog.open) {
    if (typeof dom.integratedBacktestDialog.showModal === "function") {
      dom.integratedBacktestDialog.showModal();
    } else {
      dom.integratedBacktestDialog.setAttribute("open", "");
    }
  }
  renderBacktestResults(latestBacktest);
  requestAnimationFrame(() => {
    dom.backtestResults.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function renderScanContext''',
    flags=re.S,
)

replace_once(
    "public/app.js",
    '''    renderBacktestResults(latestBacktest);
    dom.backtestResults.classList.remove("hidden");''',
    '''    renderBacktestResults(latestBacktest);
    renderScanTable();
    renderScanSummary();
    dom.backtestResults.classList.remove("hidden");''',
)

replace_once(
    "public/app.js",
    '''  dom.openManualOptimizer.addEventListener("click", (event) => {''',
    '''  dom.openIntegratedBacktest.addEventListener("click", openIntegratedBacktestBuilder);
  dom.closeIntegratedBacktest.addEventListener("click", closeIntegratedBacktestDialog);
  dom.integratedBacktestDialog.addEventListener("click", (event) => {
    if (event.target === dom.integratedBacktestDialog) closeIntegratedBacktestDialog();
  });
  dom.openManualOptimizer.addEventListener("click", (event) => {''',
)
replace_once(
    "public/app.js",
    '''  dom.scanTable.addEventListener("click", (event) => {
    const header = event.target.closest("th[data-sort-key]");
    if (!header) return;''',
    '''  dom.scanTable.addEventListener("click", (event) => {
    const action = event.target.closest("button[data-action='view-portfolio-result']");
    if (action) {
      viewIntegratedPortfolioResults();
      return;
    }
    const header = event.target.closest("th[data-sort-key]");
    if (!header) return;''',
)

replace_once(
    "public/index.html",
    '''  <link rel="stylesheet" href="/styles.css?v=20260803.5">
  <script type="module" src="/app.js?v=20260803.6"></script>
  <script type="module" src="/scan-output-ui.js?v=20260803.4"></script>
  <script type="module" src="/scan-composite-score.js?v=20260803.4"></script>''',
    '''  <link rel="stylesheet" href="/styles.css?v=20260803.7">
  <script type="module" src="/app.js?v=20260803.7"></script>
  <script type="module" src="/scan-output-ui.js?v=20260803.5"></script>''',
)
replace_once(
    "public/index.html",
    '''  <nav class="tab-nav" aria-label="主要功能">
    <button class="tab-button active" type="button" data-tab="backtest" aria-selected="true">投資組合回測</button>
    <button class="tab-button" type="button" data-tab="scanner" aria-selected="false">個股掃描</button>
    <button class="tab-button" type="button" data-tab="about" aria-selected="false">方法與限制</button>
  </nav>''',
    '''  <nav class="tab-nav" aria-label="主要功能">
    <button class="tab-button active" type="button" data-tab="scanner" aria-selected="true">績效研究</button>
    <button class="tab-button" type="button" data-tab="about" aria-selected="false">方法與限制</button>
  </nav>''',
)
replace_once(
    "public/index.html",
    '''    <section id="backtest-panel" class="tab-panel" aria-labelledby="backtest-title">''',
    '''    <dialog id="integrated-backtest-dialog" class="integrated-backtest-dialog">
      <section id="backtest-panel" class="integrated-backtest-panel" aria-labelledby="backtest-title">
        <button id="close-integrated-backtest" class="dialog-close button ghost compact" type="button" aria-label="關閉投資組合回測">關閉</button>''',
)
replace_once(
    "public/index.html",
    '''    </section>

    <section id="scanner-panel" class="tab-panel hidden" aria-labelledby="scanner-title">''',
    '''      </section>
    </dialog>

    <section id="scanner-panel" class="tab-panel" aria-labelledby="scanner-title">''',
)
replace_once(
    "public/index.html",
    '''          <p class="eyebrow">SCANNER</p>
          <h2 id="scanner-title">個股績效掃描</h2>''',
    '''          <p class="eyebrow">PERFORMANCE RESEARCH</p>
          <h2 id="scanner-title">績效研究工作區</h2>''',
)
regex_once(
    "public/index.html",
    r'''        <div class="result-header">
.*?
        </div>
        <div id="scan-context"''',
    '''        <div class="scan-results-heading">
          <div>
            <p class="eyebrow">SCAN RESULTS</p>
            <h3>績效列表</h3>
          </div>
          <div class="scan-export-actions">
            <button id="export-scan" class="button ghost" type="button">匯出精簡 CSV</button>
            <button id="export-scan-audit" class="button ghost" type="button">匯出稽核 CSV</button>
          </div>
        </div>
        <div class="scan-coverage-row">
          <label class="inline-control scan-coverage-filter" for="scan-min-coverage">
            <span>最低資料覆蓋率</span>
            <input id="scan-min-coverage" type="number" min="0" max="100" step="0.1" value="90" inputmode="decimal" aria-describedby="scan-coverage-filter-status">
            <span aria-hidden="true">%</span>
          </label>
          <span id="scan-coverage-filter-status" class="scan-coverage-filter-status" aria-live="polite"></span>
        </div>
        <div class="scan-selection-row">
          <span id="optimizer-manual-selection-status" class="optimizer-manual-selection-status" aria-live="polite"></span>
          <div class="scan-selection-actions">
            <button id="clear-optimizer-selection" class="button ghost compact" type="button">清除已選</button>
            <button id="open-integrated-backtest" class="button primary" type="button" disabled>建立投資組合回測</button>
            <a id="open-manual-optimizer" class="button secondary" href="/optimizer.html?mode=manual" target="_blank" rel="noopener" aria-disabled="true">使用已選 0 檔開啟最佳化器</a>
            <a id="open-optimizer" class="button secondary" href="/optimizer.html" target="_blank" rel="noopener">開啟完整最佳化器</a>
          </div>
        </div>
        <div id="scan-context"''',
    flags=re.S,
)
replace_once(
    "public/index.html",
    '''        <div id="scan-summary" class="summary-grid"></div>
        <div class="table-wrap">''',
    '''        <div id="scan-summary" class="summary-grid"></div>
        <details id="score-formula-comparison" class="result-context score-formula-details">
          <summary>分數公式與排名說明</summary>
          <ul>
            <li>穩健：Sortino × √((1 + CAGR) ÷ (1 + Beta))</li>
            <li>成長：Sortino × √(1 + CAGR) ÷ (1 + Beta)^0.25</li>
            <li>回撤：Sortino × √((1 + CAGR) ÷ ((1 + Beta) × (1 + |MDD|)))</li>
          </ul>
          <p>每格顯示「名次 · 分數」；Alpha 固定緊接在 Beta 後方，分數以符合目前資料覆蓋率門檻的標的為母體。</p>
        </details>
        <div class="table-wrap">''',
)

css_append = r'''

/* Unified performance workspace v20260803.7 */
.scan-results-heading,
.scan-coverage-row,
.scan-selection-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}
.scan-results-heading { margin-bottom: 0.9rem; }
.scan-export-actions,
.scan-selection-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  align-items: center;
}
.scan-coverage-row,
.scan-selection-row {
  border: 1px solid var(--border);
  border-radius: 11px;
  padding: 0.75rem 0.85rem;
  background: var(--surface-subtle);
}
.scan-selection-row { margin-top: 0.65rem; }
.integrated-backtest-dialog {
  width: min(1380px, calc(100vw - 2rem));
  max-height: calc(100vh - 2rem);
  border: 0;
  border-radius: 16px;
  padding: 0;
  background: transparent;
  box-shadow: 0 24px 80px rgb(15 23 42 / 0.28);
}
.integrated-backtest-dialog::backdrop { background: rgb(15 23 42 / 0.58); }
.integrated-backtest-panel {
  position: relative;
  overflow: auto;
  max-height: calc(100vh - 2rem);
  padding: 1.25rem;
  border-radius: 16px;
  background: var(--bg);
}
.dialog-close {
  position: sticky;
  top: 0;
  z-index: 8;
  float: right;
  background: var(--surface);
}
.performance-portfolio-row {
  background: #eef6ff;
  border-top: 2px solid #bfdbfe;
}
.performance-type-cell {
  color: var(--muted);
  font-size: 0.76rem;
  font-weight: 800;
  text-align: center;
}
.performance-action-cell { text-align: center; }
#scan-table { min-width: 2050px; }
#scan-table th:first-child,
#scan-table td:first-child {
  position: sticky;
  left: 0;
  width: 68px;
  min-width: 68px;
  max-width: 68px;
  text-align: center;
  z-index: 3;
}
#scan-table th:nth-child(2),
#scan-table td:nth-child(2) {
  position: sticky;
  left: 68px;
  width: 160px;
  min-width: 160px;
  max-width: 190px;
  text-align: left;
  background: inherit;
  z-index: 2;
}
#scan-table thead th:nth-child(2) { z-index: 4; }

@media (max-width: 900px) {
  .scan-results-heading,
  .scan-coverage-row,
  .scan-selection-row {
    align-items: stretch;
    flex-direction: column;
  }
  .scan-export-actions,
  .scan-selection-actions { width: 100%; }
  .scan-export-actions .button,
  .scan-selection-actions .button,
  .scan-selection-actions a { flex: 1 1 220px; text-align: center; }
}
'''
write("public/styles.css", read("public/styles.css") + css_append)

replace_once(
    "public/scan-output-ui.js",
    '''} from "./scan-score-formulas.js?v=20260803.3";''',
    '''} from "./scan-score-formulas.js?v=20260803.4";
import { deriveScanCoverage } from "./scan-coverage.js?v=20260803.2";''',
)
replace_once(
    "public/scan-output-ui.js",
    '''  "data_coverage",
  "trading_days",''',
    '''  "data_coverage",
  "benchmark_calendar_coverage",
  "coverage_reference_trading_days",
  "coverage_definition_version",
  "trading_days",''',
)
replace_once(
    "public/scan-output-ui.js",
    '''function currentRows() {
  const saved = readSavedJob()?.results;
  if (Array.isArray(saved) && saved.length) return saved;
  return [...rawResults.values()];
}''',
    '''function currentRows() {
  const saved = readSavedJob()?.results;
  const rows = Array.isArray(saved) && saved.length ? saved : [...rawResults.values()];
  const derived = deriveScanCoverage(rows);
  const prepared = new Map(derived.settled.map((item) => [normalizeScoreTicker(item.ticker), item]));
  return rows.map((item) => prepared.get(normalizeScoreTicker(item?.ticker)) || item);
}''',
)

package = json.loads(read("package.json"))
package["scripts"]["check"] = package["scripts"]["check"].replace(
    " && node --check public/scan-composite-score.js", ""
)
write("package.json", json.dumps(package, ensure_ascii=False, indent=2) + "\n")
Path(ROOT / "public/scan-composite-score.js").unlink(missing_ok=True)

write(
    "tests/test_scan_coverage.mjs",
    r'''import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_SCAN_MIN_COVERAGE_PERCENT,
  SCAN_COVERAGE_DEFINITION_VERSION,
  buildScanCoverageStats,
  deriveScanCoverage,
  normalizeScanMinCoveragePercent,
  relativeScanCoverage,
} from "../public/scan-coverage.js";

test("coverage threshold defaults to 90% and normalizes manual input safely", () => {
  assert.equal(DEFAULT_SCAN_MIN_COVERAGE_PERCENT, 90);
  assert.equal(normalizeScanMinCoveragePercent(null), 90);
  assert.equal(normalizeScanMinCoveragePercent(""), 90);
  assert.equal(normalizeScanMinCoveragePercent("89.94"), 89.9);
  assert.equal(normalizeScanMinCoveragePercent("120"), 100);
  assert.equal(normalizeScanMinCoveragePercent("-1"), 0);
  assert.equal(normalizeScanMinCoveragePercent("not-a-number", 85), 85);
});

test("coverage uses the maximum successful trading-day count as one global denominator", () => {
  const rows = [
    { ticker: "FULL", status: "ok", trading_days: 2604, data_coverage: 1 },
    { ticker: "MID", status: "ok", trading_days: 1519, data_coverage: 1 },
    { ticker: "SHORT", status: "ok", trading_days: 609, data_coverage: 1 },
    { ticker: "NEW", status: "ok", trading_days: 35, data_coverage: 1 },
    { ticker: "FAILED", status: "failed", error: "unavailable", trading_days: 3000 },
  ];
  const derived = deriveScanCoverage(rows);
  assert.equal(derived.maximumTradingDays, 2604);
  assert.equal(derived.coverageDefinitionVersion, SCAN_COVERAGE_DEFINITION_VERSION);
  assert.equal(derived.settled[0].data_coverage, 1);
  assert.ok(Math.abs(derived.settled[1].data_coverage - 1519 / 2604) < 1e-12);
  assert.ok(Math.abs(derived.settled[2].data_coverage - 609 / 2604) < 1e-12);
  assert.ok(Math.abs(derived.settled[3].data_coverage - 35 / 2604) < 1e-12);
  assert.equal(derived.settled[1].benchmark_calendar_coverage, 1);
  assert.equal(derived.settled[1].coverage_reference_trading_days, 2604);
  assert.equal(derived.settled[1].coverage_definition_version, SCAN_COVERAGE_DEFINITION_VERSION);
});

test("coverage is deterministic regardless of API batch arrival order", () => {
  const rows = [
    { ticker: "A", status: "ok", trading_days: 100 },
    { ticker: "B", status: "ok", trading_days: 80 },
    { ticker: "C", status: "ok", trading_days: 20 },
  ];
  const forward = deriveScanCoverage(rows).settled
    .map((item) => [item.ticker, item.data_coverage])
    .sort();
  const reverse = deriveScanCoverage([...rows].reverse()).settled
    .map((item) => [item.ticker, item.data_coverage])
    .sort();
  assert.deepEqual(forward, reverse);
  assert.equal(relativeScanCoverage(rows[1], 100), 0.8);
});

test("coverage filtering includes the exact threshold and rejects invalid histories", () => {
  const rows = [
    { ticker: "FULL", status: "ok", trading_days: 1000 },
    { ticker: "AT90", status: "ok", trading_days: 900 },
    { ticker: "LOW", status: "ok", trading_days: 899 },
    { ticker: "MISSING", status: "ok", trading_days: null },
    { ticker: "FAILED", status: "failed", error: "unavailable", trading_days: 1000 },
    { ticker: "RETRY", status: "pending", retryable: true, trading_days: 1000 },
  ];
  const stats = buildScanCoverageStats(rows, 90);
  assert.deepEqual(stats.shown.map((item) => item.ticker), ["FULL", "AT90"]);
  assert.equal(stats.settled.length, 4);
  assert.equal(stats.hidden, 2);
  assert.equal(stats.maximumTradingDays, 1000);
});
''',
)

score_test = read("tests/test_scan_score_formulas.mjs")
score_test = score_test.replace(
    '''const FORMULA_KEYS = [
  "sortino_growth_beta_score",
  "sortino_growth_beta_quarter_score",
  "sortino_growth_beta_mdd_score",
  "sortino_growth_beta_squared_mdd_score",
];''',
    '''const FORMULA_KEYS = [
  "sortino_growth_beta_score",
  "sortino_growth_beta_quarter_score",
  "sortino_growth_beta_mdd_score",
];''',
)
write("tests/test_scan_score_formulas.mjs", score_test)
regex_once(
    "tests/test_scan_score_formulas.mjs",
    r'''test\("four growth-beta formulas use raw unrounded metrics", \(\) => \{
.*?
\}\);''',
    '''test("three growth-beta formulas use raw unrounded metrics", () => {
  const result = buildScoreMatrix(SAMPLE);
  const stable = scoreRecordFor(result, "AAA", "sortino_growth_beta_score");
  const growth = scoreRecordFor(result, "AAA", "sortino_growth_beta_quarter_score");
  const drawdown = scoreRecordFor(result, "AAA", "sortino_growth_beta_mdd_score");

  assert.equal(SCORE_FORMULAS.length, 3);
  assert.ok(Math.abs(stable.score - (2 * Math.sqrt(1.30 / 2.20))) < 1e-12);
  assert.ok(Math.abs(growth.score - (2 * Math.sqrt(1.30) / Math.pow(2.20, 0.25))) < 1e-12);
  assert.ok(Math.abs(drawdown.score - (2 * Math.sqrt(1.30 / (2.20 * 1.20)))) < 1e-12);
  assert.equal(stable.rank, 1);
  assert.equal(growth.rank, 1);
  assert.equal(drawdown.rank, 1);
});''',
    flags=re.S,
)
score_test = read("tests/test_scan_score_formulas.mjs")
score_test = score_test.replace(
    'test("the four formulas can produce different cross-sectional ranks", () => {',
    'test("the three formulas can produce different cross-sectional ranks", () => {',
)
score_test = re.sub(
    r'''\n  assert\.equal\(\n    scoreRecordFor\(result, "B", "sortino_growth_beta_squared_mdd_score"\)\.rank,\n    1,\n  \);''',
    "",
    score_test,
)
score_test = re.sub(
    r'''  const zeroOptimized = scoreRecordFor\(
    result,
    "ZERO",
    "sortino_growth_beta_squared_mdd_score",
  \);
''',
    "",
    score_test,
)
score_test = score_test.replace(
    '''  assert.equal(zeroOptimized.status, "ok");
  assert.equal(zeroStable.score, zeroDrawdown.score);
  assert.ok(zeroOptimized.score < zeroDrawdown.score);''',
    '''  assert.equal(zeroStable.score, zeroDrawdown.score);''',
)
score_test = score_test.replace(
    'test("MDD is required for both drawdown-aware formulas", () => {',
    'test("MDD is required for the drawdown-aware formula", () => {',
)
score_test = score_test.replace(
    '''  assert.equal(
    scoreRecordFor(result, "MISS_MDD", "sortino_growth_beta_squared_mdd_score").status,
    "missing_metrics",
  );
''',
    "",
)
write("tests/test_scan_score_formulas.mjs", score_test)

score_e2e = read("tests/e2e/scan_composite_score.spec.mjs")
score_e2e = score_e2e.replace(
    '''  await expect(page.locator('#scan-table th[data-composite-metric="percentile_composite_score"]')).toHaveCount(0);''',
    '''  await expect(page.locator('#scan-table th[data-composite-metric="percentile_composite_score"]')).toHaveCount(0);
  await expect(page.locator('#scan-table th[data-composite-metric="sortino_growth_beta_squared_mdd_score"]')).toHaveCount(0);
  const labels = await page.locator("#scan-table thead th").allTextContents();
  const betaIndex = labels.findIndex((label) => label.startsWith("Beta"));
  const alphaIndex = labels.findIndex((label) => label.startsWith("Alpha"));
  const stableIndex = labels.findIndex((label) => label.startsWith("穩健分數"));
  expect(alphaIndex).toBe(betaIndex + 1);
  expect(stableIndex).toBe(alphaIndex + 1);''',
)
write("tests/e2e/scan_composite_score.spec.mjs", score_e2e)

Path(ROOT / ".github/workflows/release-pr39-backups.yml").unlink(missing_ok=True)
write(
    ".github/workflows/release-backups.yml",
    r'''name: Release Backup Gates

on:
  pull_request:
    types: [labeled, synchronize, reopened, ready_for_review, closed]

permissions:
  contents: write

jobs:
  create-pre-merge-backup:
    if: >-
      github.event.action != 'closed'
      && github.event.pull_request.head.repo.full_name == github.repository
      && contains(github.event.pull_request.labels.*.name, 'release-backup')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - name: Create and verify pre-merge release
        env:
          GH_TOKEN: ${{ github.token }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          PRE_SHA: ${{ github.event.pull_request.base.sha }}
        run: |
          set -euo pipefail
          tag="backup-pre-pr${PR_NUMBER}-${PRE_SHA:0:12}"
          if ! gh release view "$tag" >/dev/null 2>&1; then
            gh release create "$tag" \
              --target "$PRE_SHA" \
              --title "Backup before PR #${PR_NUMBER}" \
              --notes "Backup of main before PR #${PR_NUMBER}. Target: $PRE_SHA"
          fi
          git fetch --force origin "refs/tags/$tag:refs/tags/$tag"
          test "$(git rev-list -n 1 "$tag")" = "$PRE_SHA"

  create-post-merge-backup:
    if: >-
      github.event.action == 'closed'
      && github.event.pull_request.merged == true
      && github.event.pull_request.head.repo.full_name == github.repository
      && contains(github.event.pull_request.labels.*.name, 'release-backup')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          ref: ${{ github.event.pull_request.merge_commit_sha }}
          fetch-depth: 0
      - name: Verify pre-release and create post-merge release
        env:
          GH_TOKEN: ${{ github.token }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          PRE_SHA: ${{ github.event.pull_request.base.sha }}
          MERGE_SHA: ${{ github.event.pull_request.merge_commit_sha }}
        run: |
          set -euo pipefail
          pre_tag="backup-pre-pr${PR_NUMBER}-${PRE_SHA:0:12}"
          post_tag="backup-post-pr${PR_NUMBER}-${MERGE_SHA:0:12}"
          gh release view "$pre_tag" >/dev/null
          git fetch --force origin "refs/tags/$pre_tag:refs/tags/$pre_tag"
          test "$(git rev-list -n 1 "$pre_tag")" = "$PRE_SHA"
          if ! gh release view "$post_tag" >/dev/null 2>&1; then
            gh release create "$post_tag" \
              --target "$MERGE_SHA" \
              --title "Backup after PR #${PR_NUMBER}" \
              --notes "Backup of main after PR #${PR_NUMBER}. Target: $MERGE_SHA"
          fi
          git fetch --force origin "refs/tags/$post_tag:refs/tags/$post_tag"
          test "$(git rev-list -n 1 "$post_tag")" = "$MERGE_SHA"
''',
)

Path(ROOT / "scripts/implement_unified_performance.py").unlink(missing_ok=True)
Path(ROOT / ".github/workflows/implement-unified-performance.yml").unlink(missing_ok=True)
