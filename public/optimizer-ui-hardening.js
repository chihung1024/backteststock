const DATE_MODE_KEY = "backteststock-optimizer-date-mode-v1";
const CUSTOM_RANGE_KEY = "backteststock-optimizer-custom-range-v1";
const LOOKBACK_YEARS = 10;
const BALANCED_WORKER_URL = "/optimizer-balanced-worker.js?v=20260802.2";

let verifiedRows = new Map();
let currentSort = { field: "training.sortino_ratio", direction: "desc" };
let renderingResults = false;

const SORT_FIELDS = Object.freeze([
  ["training.sortino_ratio", "訓練 Sortino", "desc"],
  ["training.cagr", "訓練 CAGR", "desc"],
  ["training.mdd", "訓練 |MDD|", "asc-abs"],
  ["training.beta", "訓練 |Beta|", "asc-abs"],
  ["training.alpha", "訓練 Alpha", "desc"],
  ["training.annualizedTurnoverOneWay", "訓練年化單邊換手", "asc"],
  ["training.rebalanceCount", "訓練再平衡次數", "asc"],
  ["validation.sortino_ratio", "樣本外 Sortino", "desc"],
  ["validation.cagr", "樣本外 CAGR", "desc"],
  ["validation.mdd", "樣本外 |MDD|", "asc-abs"],
  ["validation.beta", "樣本外 |Beta|", "asc-abs"],
  ["validation.alpha", "樣本外 Alpha", "desc"],
  ["validation.annualizedTurnoverOneWay", "樣本外年化單邊換手", "asc"],
  ["validation.rebalanceCount", "樣本外再平衡次數", "asc"],
]);

function installBalancedWorkerRedirect() {
  if (window.__backteststockBalancedWorkerInstalled) return;
  window.__backteststockBalancedWorkerInstalled = true;
  const NativeWorker = window.Worker;
  if (typeof NativeWorker !== "function") return;
  const WorkerProxy = function WorkerProxy(url, options) {
    const requested = String(url || "");
    return new NativeWorker(
      requested.includes("/optimizer-worker.js") ? BALANCED_WORKER_URL : url,
      options,
    );
  };
  WorkerProxy.prototype = NativeWorker.prototype;
  Object.setPrototypeOf(WorkerProxy, NativeWorker);
  window.Worker = WorkerProxy;
}

function formatLocalDate(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

export function rollingOptimizerRange(now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(today);
  end.setDate(end.getDate() - 1);
  const year = today.getFullYear() - LOOKBACK_YEARS;
  const maxDay = new Date(year, today.getMonth() + 1, 0).getDate();
  const start = new Date(year, today.getMonth(), Math.min(today.getDate(), maxDay));
  return { startDate: formatLocalDate(start), endDate: formatLocalDate(end) };
}

function recentAutomaticMatch(startDate, endDate, days = 31) {
  const now = new Date();
  for (let offset = 0; offset <= days; offset += 1) {
    const candidate = new Date(now.getFullYear(), now.getMonth(), now.getDate() - offset);
    const range = rollingOptimizerRange(candidate);
    if (range.startDate === startDate && range.endDate === endDate) return true;
  }
  return false;
}

function readJson(key) {
  try {
    return JSON.parse(localStorage.getItem(key));
  } catch {
    return null;
  }
}

function installRollingDates() {
  const start = document.querySelector("#optimizer-start-date");
  const end = document.querySelector("#optimizer-end-date");
  if (!start || !end) return;
  const current = rollingOptimizerRange();
  const mode = localStorage.getItem(DATE_MODE_KEY);
  const custom = readJson(CUSTOM_RANGE_KEY);
  const inferredAutomatic = recentAutomaticMatch(start.value, end.value);

  if (mode === "custom" && custom?.startDate && custom?.endDate) {
    start.value = custom.startDate;
    end.value = custom.endDate;
  } else if (mode === "automatic" || (!mode && inferredAutomatic)) {
    start.value = current.startDate;
    end.value = current.endDate;
    localStorage.setItem(DATE_MODE_KEY, "automatic");
    localStorage.removeItem(CUSTOM_RANGE_KEY);
  } else if (!mode) {
    localStorage.setItem(DATE_MODE_KEY, "custom");
    localStorage.setItem(CUSTOM_RANGE_KEY, JSON.stringify({
      startDate: start.value,
      endDate: end.value,
    }));
  }

  const record = () => {
    const latest = rollingOptimizerRange();
    if (start.value === latest.startDate && end.value === latest.endDate) {
      localStorage.setItem(DATE_MODE_KEY, "automatic");
      localStorage.removeItem(CUSTOM_RANGE_KEY);
    } else {
      localStorage.setItem(DATE_MODE_KEY, "custom");
      localStorage.setItem(CUSTOM_RANGE_KEY, JSON.stringify({
        startDate: start.value,
        endDate: end.value,
      }));
    }
  };
  start.addEventListener("change", record);
  end.addEventListener("change", record);

  const endLabel = end.closest("label");
  if (endLabel && !document.querySelector("#optimizer-reset-rolling-dates")) {
    const button = document.createElement("button");
    button.type = "button";
    button.id = "optimizer-reset-rolling-dates";
    button.className = "button ghost compact optimizer-date-reset";
    button.textContent = "恢復每日自動日期";
    button.addEventListener("click", () => {
      const latest = rollingOptimizerRange();
      start.value = latest.startDate;
      end.value = latest.endDate;
      localStorage.setItem(DATE_MODE_KEY, "automatic");
      localStorage.removeItem(CUSTOM_RANGE_KEY);
    });
    endLabel.append(button);
  }
}

function valueAt(row, path) {
  return path.split(".").reduce((value, key) => value?.[key], row);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function format(value, type = "number") {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  if (type === "percent") return `${(numeric * 100).toFixed(2)}%`;
  if (type === "integer") return String(Math.round(numeric));
  return numeric.toFixed(3);
}

function sortRows(rows) {
  const definition = SORT_FIELDS.find(([field]) => field === currentSort.field);
  const absolute = definition?.[2] === "asc-abs";
  const direction = currentSort.direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    let leftValue = Number(valueAt(left, currentSort.field));
    let rightValue = Number(valueAt(right, currentSort.field));
    const leftFinite = Number.isFinite(leftValue);
    const rightFinite = Number.isFinite(rightValue);
    if (leftFinite !== rightFinite) return leftFinite ? -1 : 1;
    if (!leftFinite) return Number(left.mask) - Number(right.mask);
    if (absolute) {
      leftValue = Math.abs(leftValue);
      rightValue = Math.abs(rightValue);
    }
    const difference = (leftValue - rightValue) * direction;
    return Math.abs(difference) > 1e-12
      ? difference
      : Number(left.mask) - Number(right.mask);
  });
}

function header(label, field) {
  const active = currentSort.field === field;
  const arrow = active ? (currentSort.direction === "asc" ? " ▲" : " ▼") : "";
  return `<button type="button" class="optimizer-sort-header" data-sort-field="${field}">${label}${arrow}</button>`;
}

function renderSortableResults() {
  if (renderingResults) return;
  const table = document.querySelector("#optimizer-result-table");
  if (!table || verifiedRows.size === 0) return;
  const signature = `${verifiedRows.size}:${currentSort.field}:${currentSort.direction}`;
  if (
    table.dataset.hardeningSignature === signature
    && table.querySelector(".optimizer-sort-header")
  ) return;
  renderingResults = true;
  try {
    const rows = sortRows([...verifiedRows.values()]);
    let controls = document.querySelector("#optimizer-result-sort-controls");
    if (!controls) {
      controls = document.createElement("div");
      controls.id = "optimizer-result-sort-controls";
      controls.className = "optimizer-result-sort-controls";
      table.closest(".table-wrap")?.before(controls);
    }
    controls.innerHTML = `
      <label><span>顯示排序</span><select id="optimizer-result-sort-field">
        ${SORT_FIELDS.map(([field, label]) => `<option value="${field}" ${field === currentSort.field ? "selected" : ""}>${label}</option>`).join("")}
      </select></label>
      <label><span>方向</span><select id="optimizer-result-sort-direction">
        <option value="desc" ${currentSort.direction === "desc" ? "selected" : ""}>由高到低</option>
        <option value="asc" ${currentSort.direction === "asc" ? "selected" : ""}>由低到高</option>
      </select></label>
      <p>排序只改變顯示順序，不回頭改變候選池、搜尋或樣本外驗證。</p>`;
    controls.querySelector("#optimizer-result-sort-field")?.addEventListener("change", (event) => {
      const field = event.target.value;
      const preferred = SORT_FIELDS.find(([key]) => key === field)?.[2] || "desc";
      currentSort = { field, direction: preferred.startsWith("asc") ? "asc" : "desc" };
      renderSortableResults();
    });
    controls.querySelector("#optimizer-result-sort-direction")?.addEventListener("change", (event) => {
      currentSort.direction = event.target.value;
      renderSortableResults();
    });

    table.dataset.hardeningSignature = signature;
    table.innerHTML = `
      <thead><tr>
        <th>顯示排名</th><th>持股</th>
        <th>${header("訓練 Sortino", "training.sortino_ratio")}</th>
        <th>${header("訓練 CAGR", "training.cagr")}</th>
        <th>${header("訓練 MDD", "training.mdd")}</th>
        <th>${header("訓練 Beta", "training.beta")}</th>
        <th>${header("訓練 Alpha", "training.alpha")}</th>
        <th>${header("樣本外 Sortino", "validation.sortino_ratio")}</th>
        <th>${header("樣本外 CAGR", "validation.cagr")}</th>
        <th>${header("樣本外 MDD", "validation.mdd")}</th>
        <th>${header("樣本外 Beta", "validation.beta")}</th>
        <th>${header("樣本外 Alpha", "validation.alpha")}</th>
        <th>${header("訓練換手", "training.annualizedTurnoverOneWay")}</th>
        <th>${header("樣本外換手", "validation.annualizedTurnoverOneWay")}</th>
        <th>${header("訓練再平衡", "training.rebalanceCount")}</th>
        <th>${header("樣本外再平衡", "validation.rebalanceCount")}</th>
      </tr></thead>
      <tbody>${rows.map((row, index) => `<tr>
        <td>${index + 1}</td><td class="optimizer-holdings">${escapeHtml(row.tickers.join(", "))}</td>
        <td>${format(row.training.sortino_ratio)}</td><td>${format(row.training.cagr, "percent")}</td>
        <td>${format(row.training.mdd, "percent")}</td><td>${format(row.training.beta)}</td>
        <td>${format(row.training.alpha, "percent")}</td><td>${format(row.validation.sortino_ratio)}</td>
        <td>${format(row.validation.cagr, "percent")}</td><td>${format(row.validation.mdd, "percent")}</td>
        <td>${format(row.validation.beta)}</td><td>${format(row.validation.alpha, "percent")}</td>
        <td>${format(row.training.annualizedTurnoverOneWay, "percent")}</td>
        <td>${format(row.validation.annualizedTurnoverOneWay, "percent")}</td>
        <td>${format(row.training.rebalanceCount, "integer")}</td>
        <td>${format(row.validation.rebalanceCount, "integer")}</td>
      </tr>`).join("")}</tbody>`;
  } finally {
    renderingResults = false;
  }
}

function installFetchCapture() {
  if (window.__backteststockOptimizerResultCaptureInstalled) return;
  window.__backteststockOptimizerResultCaptureInstalled = true;
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input?.url || "";
    if (url.includes("/api/optimizer/prepare")) verifiedRows = new Map();
    const response = await nativeFetch(input, init);
    if (url.includes("/api/optimizer/verify") && response.ok) {
      try {
        const payload = await response.clone().json();
        for (const row of payload.results || []) verifiedRows.set(row.combinationId, row);
        queueMicrotask(renderSortableResults);
      } catch {
        // Keep the original response untouched when diagnostics cannot be decoded.
      }
    }
    return response;
  };
}

function installStyles() {
  const style = document.createElement("style");
  style.textContent = `
    .optimizer-date-reset { margin-top: .45rem; width: max-content; }
    .optimizer-result-sort-controls { display:grid; grid-template-columns:minmax(12rem,1fr) minmax(9rem,.45fr) minmax(18rem,2fr); gap:.75rem; align-items:end; margin:0 0 .8rem; }
    .optimizer-result-sort-controls p { margin:0 0 .55rem; color:var(--muted); }
    .optimizer-sort-header { appearance:none; border:0; padding:0; background:transparent; color:inherit; font:inherit; font-weight:800; cursor:pointer; white-space:nowrap; }
    @media (max-width:760px) { .optimizer-result-sort-controls { grid-template-columns:1fr; } }
  `;
  document.head.append(style);
}

installBalancedWorkerRedirect();
installFetchCapture();
installStyles();
window.addEventListener("DOMContentLoaded", () => {
  installRollingDates();
  const budget = document.querySelector("#optimizer-search-budget");
  if (budget) budget.min = "6000";
  const table = document.querySelector("#optimizer-result-table");
  if (table) {
    const observer = new MutationObserver(() => {
      if (verifiedRows.size) renderSortableResults();
    });
    observer.observe(table, { childList: true, subtree: true });
    table.addEventListener("click", (event) => {
      const button = event.target.closest("[data-sort-field]");
      if (!button) return;
      const field = button.dataset.sortField;
      if (currentSort.field === field) {
        currentSort.direction = currentSort.direction === "asc" ? "desc" : "asc";
      } else {
        const preferred = SORT_FIELDS.find(([key]) => key === field)?.[2] || "desc";
        currentSort = { field, direction: preferred.startsWith("asc") ? "asc" : "desc" };
      }
      renderSortableResults();
    });
  }
}, { once: true });
