import { normalizeScanJob } from "./scan-job-normalizer.js?v=20260812.1";

const PORTFOLIO_HANDOFF_STORAGE_KEY = "backteststock-portfolio-handoff-v1";
const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v3";
const MANUAL_SELECTION_STORAGE_KEY = "backteststock-optimizer-manual-selection-v2";
const MAX_PORTFOLIO_ASSETS = 20;
const HANDOFF_TTL_MS = 24 * 60 * 60 * 1000;
const DEFAULT_SCAN_LOOKBACK_YEARS = 10;

function formatLocalDate(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

function scanDateFallbackRange(now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(today);
  end.setDate(end.getDate() - 1);
  const startYear = today.getFullYear() - DEFAULT_SCAN_LOOKBACK_YEARS;
  const maxDay = new Date(startYear, today.getMonth() + 1, 0).getDate();
  const start = new Date(
    startYear,
    today.getMonth(),
    Math.min(today.getDate(), maxDay),
  );
  return {
    startDate: formatLocalDate(start),
    endDate: formatLocalDate(end),
  };
}

function readJson(storage, key, fallback = null) {
  try {
    const value = JSON.parse(storage.getItem(key));
    return value == null ? fallback : value;
  } catch {
    return fallback;
  }
}

function writeJson(storage, key, value) {
  try {
    storage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error) {
    console.warn("Unable to persist Portfolio handoff", error);
    return false;
  }
}

function normalizeTicker(value) {
  const ticker = String(value || "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9.^=_-]/g, "")
    .slice(0, 32);
  return /^\d{4,6}$/.test(ticker) ? `${ticker}.TW` : ticker;
}

function normalizedThreshold(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 90;
  return Math.min(100, Math.max(0, numeric));
}

function activateScannerDom() {
  let portfolioLink = document.querySelector("#portfolio-route-link");
  const oldBacktestButton = document.querySelector('.tab-button[data-tab="backtest"]');
  if (!portfolioLink && oldBacktestButton) {
    portfolioLink = document.createElement("a");
    portfolioLink.id = "portfolio-route-link";
    portfolioLink.className = "tab-button portfolio-route-link";
    portfolioLink.href = "/portfolio/";
    portfolioLink.dataset.portfolioRoute = "main";
    portfolioLink.textContent = "投資組合回測";
    portfolioLink.title = "前往完整投資組合研究工作區";
    portfolioLink.setAttribute("aria-label", "投資組合回測（開啟完整頁面）");
    oldBacktestButton.replaceWith(portfolioLink);
  }

  const scannerButton = document.querySelector('.tab-button[data-tab="scanner"]');
  document.querySelectorAll(".tab-button[data-tab]").forEach((button) => {
    const active = button === scannerButton;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  if (scannerButton) scannerButton.textContent = "績效研究（個股掃描）";
  document.querySelector("#backtest-panel")?.classList.add("hidden");
  document.querySelector("#about-panel")?.classList.add("hidden");
  document.querySelector("#scanner-panel")?.classList.remove("hidden");
}

function visibleScanJobId() {
  return String(document.querySelector("#scan-table")?.dataset.scanJobId || "").trim();
}

function hasStaleVisibleScanJob() {
  const pageJobId = visibleScanJobId();
  if (!pageJobId) return false;
  const savedJob = readJson(localStorage, SCAN_JOB_STORAGE_KEY, null);
  return Boolean(savedJob?.id && savedJob.id !== pageJobId);
}

function readScanJob() {
  const job = readJson(localStorage, SCAN_JOB_STORAGE_KEY, null);
  if (!job || typeof job !== "object" || !Array.isArray(job.results)) return null;
  const pageJobId = visibleScanJobId();
  if (pageJobId && job.id !== pageJobId) return null;
  try {
    return normalizeScanJob(job, scanDateFallbackRange());
  } catch {
    return job;
  }
}

function coverageQualifiedTickers(job, thresholdPercent) {
  const successful = (job?.results || []).filter((row) => (
    row?.status === "ok" && Number(row.trading_days) > 0
  ));
  const maximumTradingDays = Math.max(
    0,
    ...successful.map((row) => Number(row.trading_days)),
  );
  if (!maximumTradingDays) return new Set();
  return new Set(successful
    .filter((row) => (Number(row.trading_days) / maximumTradingDays) * 100 >= thresholdPercent)
    .map((row) => normalizeTicker(row.ticker))
    .filter(Boolean));
}

function currentCoverageThreshold() {
  return normalizedThreshold(document.querySelector("#scan-min-coverage")?.value);
}

function selectedPortfolioTickers(job = readScanJob(), threshold = currentCoverageThreshold()) {
  const selection = readJson(localStorage, MANUAL_SELECTION_STORAGE_KEY, null);
  if (
    !job?.id
    || selection?.sourceJobId !== job.id
    || !Array.isArray(selection?.tickers)
  ) return [];

  const benchmark = normalizeTicker(job.payload?.benchmark);
  const qualified = coverageQualifiedTickers(job, threshold);
  return [...new Set(selection.tickers.map(normalizeTicker))]
    .filter((ticker) => ticker && ticker !== benchmark && qualified.has(ticker));
}

function currentPageNumber() {
  const match = String(document.querySelector("#scan-page-status")?.textContent || "")
    .match(/第\s*(\d+)\s*\/\s*(\d+)\s*頁/u);
  return match ? Number(match[1]) : 1;
}

function currentSortState() {
  const header = [...document.querySelectorAll("#scan-table th[data-sort-key]")]
    .find((element) => ["ascending", "descending"].includes(element.getAttribute("aria-sort")));
  if (!header) return { key: "cagr", direction: "desc" };
  return {
    key: String(header.dataset.sortKey || "cagr"),
    direction: header.getAttribute("aria-sort") === "ascending" ? "asc" : "desc",
  };
}

function scannerReturnState() {
  return {
    activeTab: "scanner",
    scrollY: Math.max(0, Math.round(window.scrollY)),
    page: currentPageNumber(),
    pageSize: Number(document.querySelector("#scan-page-size")?.value) || 100,
    coverageThresholdPercent: currentCoverageThreshold(),
    sort: currentSortState(),
  };
}

function createHandoff(source) {
  const job = readScanJob();
  const coverageThresholdPercent = currentCoverageThreshold();
  const tickers = source === "scanner"
    ? selectedPortfolioTickers(job, coverageThresholdPercent)
    : [];
  const id = crypto.randomUUID();
  const now = Date.now();
  const returnUrl = source === "scanner"
    ? `/?tab=scanner&restore=${encodeURIComponent(id)}#scan-results`
    : "/?tab=scanner";
  const record = {
    version: 1,
    id,
    source,
    createdAt: new Date(now).toISOString(),
    expiresAt: new Date(now + HANDOFF_TTL_MS).toISOString(),
    sourceJobId: job?.id || null,
    selectedTickers: tickers,
    startDate: String(job?.payload?.startDate || ""),
    endDate: String(job?.payload?.endDate || ""),
    benchmark: normalizeTicker(job?.payload?.benchmark || "SPY"),
    coverageThresholdPercent,
    returnUrl,
    returnState: scannerReturnState(),
  };
  return writeJson(sessionStorage, PORTFOLIO_HANDOFF_STORAGE_KEY, record)
    ? record
    : null;
}

function portfolioUrl(record) {
  const url = new URL("/portfolio/", window.location.origin);
  if (record?.id) url.searchParams.set("handoff", record.id);
  return `${url.pathname}${url.search}`;
}

function selectionStatus(message) {
  const status = document.querySelector("#optimizer-manual-selection-status");
  if (status) status.textContent = message;
}

function handlePortfolioNavigation(event) {
  if (!event.isTrusted) return;
  const target = event.target instanceof Element ? event.target : null;
  const integrated = target?.closest("#open-integrated-backtest");
  const mainEntry = target?.closest("#portfolio-route-link, [data-portfolio-route='main']");
  if (!integrated && !mainEntry) return;

  event.preventDefault();
  event.stopImmediatePropagation();
  const source = integrated ? "scanner" : "main";
  if (source === "scanner") {
    if (hasStaleVisibleScanJob()) {
      selectionStatus("另一個頁籤已更新最近掃描結果；請重新整理目前頁面後再建立投資組合。");
      return;
    }
    const count = selectedPortfolioTickers().length;
    if (count < 1 || count > MAX_PORTFOLIO_ASSETS) {
      selectionStatus(count > MAX_PORTFOLIO_ASSETS
        ? `已選 ${count} 檔；投組工作區最多接受 ${MAX_PORTFOLIO_ASSETS} 檔，請先減少選取。`
        : "請先從符合資料覆蓋率門檻的股票中選取至少 1 檔。"
      );
      return;
    }
  }

  const record = createHandoff(source);
  if (!record) {
    selectionStatus("無法建立投組移交資料，請確認瀏覽器允許工作階段儲存。 ");
    return;
  }
  window.location.assign(portfolioUrl(record));
}

function desiredSortHeader(key) {
  return [...document.querySelectorAll("#scan-table th[data-sort-key]")]
    .find((header) => header.dataset.sortKey === key) || null;
}

function restoreSort(sort) {
  if (!sort?.key) return;
  const header = desiredSortHeader(sort.key);
  if (!header) return;
  const desired = sort.direction === "asc" ? "ascending" : "descending";
  if (header.getAttribute("aria-sort") === desired) return;
  header.click();
  if (header.getAttribute("aria-sort") !== desired) header.click();
}

function restorePagination(returnState) {
  const size = document.querySelector("#scan-page-size");
  if (size && String(returnState.pageSize) !== size.value) {
    size.value = String(returnState.pageSize || 100);
    size.dispatchEvent(new Event("change", { bubbles: true }));
  }
  const desiredPage = Math.max(1, Math.min(100, Number(returnState.page) || 1));
  let current = currentPageNumber();
  const next = document.querySelector("#scan-page-next");
  const previous = document.querySelector("#scan-page-prev");
  while (current < desiredPage && next && !next.disabled) {
    next.click();
    const updated = currentPageNumber();
    if (updated === current) break;
    current = updated;
  }
  while (current > desiredPage && previous && !previous.disabled) {
    previous.click();
    const updated = currentPageNumber();
    if (updated === current) break;
    current = updated;
  }
}

function restoreSelection(record) {
  if (!record.sourceJobId || !Array.isArray(record.selectedTickers)) return;
  const tickers = [...new Set(record.selectedTickers.map(normalizeTicker).filter(Boolean))];
  const existingSelection = readJson(localStorage, MANUAL_SELECTION_STORAGE_KEY, null);
  const manualSelection = (
    existingSelection?.version === 2
    && existingSelection?.sourceJobId === record.sourceJobId
    && existingSelection?.selectionMode === "manual_fixed_source_pool"
  )
    ? {
      ...existingSelection,
      coverageThresholdPercent: normalizedThreshold(record.coverageThresholdPercent),
      tickers,
    }
    : {
      version: 2,
      sourceJobId: record.sourceJobId,
      coverageThresholdPercent: normalizedThreshold(record.coverageThresholdPercent),
      tickers,
    };
  writeJson(localStorage, MANUAL_SELECTION_STORAGE_KEY, manualSelection);
  const selected = new Set(tickers);
  document.querySelectorAll('#scan-table input[data-optimizer-ticker]').forEach((input) => {
    const ticker = normalizeTicker(input.dataset.optimizerTicker || input.value);
    const shouldBeChecked = selected.has(ticker);
    if (input.checked === shouldBeChecked) return;
    input.checked = shouldBeChecked;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function restoreScannerState(record) {
  activateScannerDom();
  const returnState = record.returnState || {};
  const thresholdInput = document.querySelector("#scan-min-coverage");
  if (thresholdInput) {
    thresholdInput.value = String(
      normalizedThreshold(returnState.coverageThresholdPercent ?? record.coverageThresholdPercent),
    );
    thresholdInput.dispatchEvent(new Event("input", { bubbles: true }));
    thresholdInput.dispatchEvent(new Event("change", { bubbles: true }));
  }

  const results = document.querySelector("#scan-results");
  if (!results || results.classList.contains("hidden")) return false;
  restoreSelection(record);
  restoreSort(returnState.sort);
  restorePagination(returnState);
  window.requestAnimationFrame(() => {
    const y = Number(returnState.scrollY);
    if (Number.isFinite(y) && y > 0) window.scrollTo({ top: y });
    else results.scrollIntoView({ block: "start" });
  });
  return true;
}

function removeRestoreParameter() {
  const url = new URL(window.location.href);
  url.searchParams.delete("restore");
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function restorePortfolioReturn() {
  const parameters = new URLSearchParams(window.location.search);
  if (parameters.get("tab") !== "scanner") return;
  activateScannerDom();

  const restoreId = parameters.get("restore");
  const record = readJson(sessionStorage, PORTFOLIO_HANDOFF_STORAGE_KEY, null);
  if (!restoreId || record?.id !== restoreId) return;
  if (Date.parse(record.expiresAt || "") < Date.now()) {
    removeRestoreParameter();
    return;
  }

  restoreSelection(record);
  let attempts = 0;
  const tryRestore = () => {
    attempts += 1;
    if (restoreScannerState(record)) {
      removeRestoreParameter();
      return;
    }
    if (attempts >= 120) {
      removeRestoreParameter();
      return;
    }
    window.setTimeout(tryRestore, 50);
  };
  tryRestore();
}

function initializePortfolioRouteBridge() {
  activateScannerDom();
  document.addEventListener("click", handlePortfolioNavigation, true);
  restorePortfolioReturn();
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  window.PortfolioRouteBridge = Object.freeze({
    createHandoff,
    selectedPortfolioTickers,
    restorePortfolioReturn,
    activateScannerDom,
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializePortfolioRouteBridge, { once: true });
  } else {
    initializePortfolioRouteBridge();
  }
}
