const PORTFOLIO_LAB_VERSION = "20260803.1";
const PORTFOLIO_LAB_FILES = [
  "portfolio-lab-core.js",
  "portfolio-lab-settings.js",
  "portfolio-lab-assets.js",
  "portfolio-lab-results.js",
];
const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v3";
const MANUAL_SELECTION_STORAGE_KEY = "backteststock-optimizer-manual-selection-v2";

function readJsonStorage(key) {
  try {
    return JSON.parse(localStorage.getItem(key));
  } catch {
    return null;
  }
}

function normalizeTicker(value) {
  return String(value || "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9.^=_-]/g, "")
    .slice(0, 32);
}

function loadPortfolioLabStyles() {
  if (document.querySelector('link[data-portfolio-lab="true"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = `/portfolio-lab.css?v=${PORTFOLIO_LAB_VERSION}`;
  link.dataset.portfolioLab = "true";
  document.head.append(link);
}

function loadPortfolioLabScript(file) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-portfolio-lab="${file}"]`);
    if (existing?.dataset.loaded === "true") {
      resolve();
      return;
    }
    const script = existing || document.createElement("script");
    script.src = `/${file}?v=${PORTFOLIO_LAB_VERSION}`;
    script.dataset.portfolioLab = file;
    script.addEventListener("load", () => {
      script.dataset.loaded = "true";
      resolve();
    }, { once: true });
    script.addEventListener("error", () => {
      reject(new Error(`Unable to load ${file}`));
    }, { once: true });
    if (!existing) document.head.append(script);
  });
}

function selectedPortfolioLabTickers() {
  const job = readJsonStorage(SCAN_JOB_STORAGE_KEY);
  const selection = readJsonStorage(MANUAL_SELECTION_STORAGE_KEY);
  if (
    !job?.id
    || selection?.sourceJobId !== job.id
    || !Array.isArray(selection?.tickers)
  ) return [];

  const benchmark = normalizeTicker(job.payload?.benchmark);
  const selected = new Set(
    selection.tickers
      .map(normalizeTicker)
      .filter((ticker) => ticker && ticker !== benchmark),
  );

  const visibleQualified = new Set(
    [...document.querySelectorAll('#scan-table input[data-optimizer-ticker]')]
      .filter((checkbox) => !checkbox.disabled)
      .map((checkbox) => normalizeTicker(checkbox.dataset.optimizerTicker))
      .filter(Boolean),
  );

  if (visibleQualified.size) {
    return [...selected].filter((ticker) => visibleQualified.has(ticker));
  }
  return [...selected];
}

function installScanSelectionBridge() {
  if (document.documentElement.dataset.portfolioLabSelectionBridge === "true") return;
  document.documentElement.dataset.portfolioLabSelectionBridge = "true";
  document.addEventListener("click", (event) => {
    if (!event.target.closest("#open-integrated-backtest")) return;
    const tickers = selectedPortfolioLabTickers();
    if (!tickers.length || !window.PortfolioLab?.prepareEqualWeightPortfolio) return;
    const job = readJsonStorage(SCAN_JOB_STORAGE_KEY);
    window.PortfolioLab.prepareEqualWeightPortfolio(tickers, {
      startDate: job?.payload?.startDate,
      endDate: job?.payload?.endDate,
      benchmark: job?.payload?.benchmark,
    });
  }, true);
}

function showLoadFailure(error) {
  console.error("Portfolio lab initialization failed", error);
  const panel = document.querySelector("#backtest-panel");
  if (!panel) return;
  panel.replaceChildren();
  const message = document.createElement("p");
  message.className = "message error";
  message.setAttribute("role", "alert");
  message.textContent = "完整投資組合回測介面載入失敗，請重新整理後再試。";
  panel.append(message);
}

async function initializePortfolioLab() {
  loadPortfolioLabStyles();
  try {
    for (const file of PORTFOLIO_LAB_FILES) {
      await loadPortfolioLabScript(file);
    }
    installScanSelectionBridge();
  } catch (error) {
    showLoadFailure(error);
  }
}

void initializePortfolioLab();
