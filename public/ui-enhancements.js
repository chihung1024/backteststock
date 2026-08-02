const STATE_STORAGE_KEY = "backteststock-state-v1";
const SCAN_JOB_STORAGE_KEY = "backteststock-scan-job-v2";
const DATE_MODE_STORAGE_KEY = "backteststock-backtest-date-mode-v1";
const OPTIMIZER_MODE_STORAGE_KEY = "backteststock-optimizer-candidate-mode-v1";
const MANUAL_SELECTION_STORAGE_KEY = "backteststock-optimizer-manual-selection-v1";
const MANUAL_CANDIDATE_COUNT = 20;
const LOOKBACK_YEARS = 10;
const MANUAL_SELECTION_BIAS_WARNING = (
  "手動候選池取自完整期間個股績效列表，可能已參考原定樣本外期間；"
  + "樣本外結果屬事後驗證，不是完全未見資料。"
);

function formatLocalDate(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

function rollingDefaultRange(now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(today);
  end.setDate(end.getDate() - 1);
  const startYear = today.getFullYear() - LOOKBACK_YEARS;
  const maxDay = new Date(startYear, today.getMonth() + 1, 0).getDate();
  const start = new Date(
    startYear,
    today.getMonth(),
    Math.min(today.getDate(), maxDay),
  );
  return { startDate: formatLocalDate(start), endDate: formatLocalDate(end) };
}

function readJson(storage, key) {
  try {
    return JSON.parse(storage.getItem(key));
  } catch {
    return null;
  }
}

function writeJson(storage, key, value) {
  storage.setItem(key, JSON.stringify(value));
}

function recentRollingDefaultMatch(startDate, endDate, days = 31) {
  const reference = new Date();
  for (let offset = 0; offset <= days; offset += 1) {
    const candidate = new Date(
      reference.getFullYear(),
      reference.getMonth(),
      reference.getDate() - offset,
    );
    const range = rollingDefaultRange(candidate);
    if (range.startDate === startDate && range.endDate === endDate) return true;
  }
  return false;
}

function refreshRollingBacktestDates() {
  const startInput = document.querySelector("#start-period");
  const endInput = document.querySelector("#end-period");
  if (!startInput || !endInput) return;

  const current = rollingDefaultRange();
  const storedMode = localStorage.getItem(DATE_MODE_STORAGE_KEY);
  const inferredAutomatic = recentRollingDefaultMatch(startInput.value, endInput.value);
  const automatic = storedMode === "automatic"
    || (storedMode !== "custom" && inferredAutomatic);

  if (automatic) {
    startInput.value = current.startDate;
    endInput.value = current.endDate;
    const state = readJson(localStorage, STATE_STORAGE_KEY);
    if (state?.settings) {
      state.settings.startPeriod = current.startDate;
      state.settings.endPeriod = current.endDate;
      writeJson(localStorage, STATE_STORAGE_KEY, state);
    }
    localStorage.setItem(DATE_MODE_STORAGE_KEY, "automatic");
  } else if (!storedMode) {
    localStorage.setItem(DATE_MODE_STORAGE_KEY, "custom");
  }

  const recordMode = () => {
    const range = rollingDefaultRange();
    const mode = startInput.value === range.startDate && endInput.value === range.endDate
      ? "automatic"
      : "custom";
    localStorage.setItem(DATE_MODE_STORAGE_KEY, mode);
  };
  startInput.addEventListener("change", recordMode);
  endInput.addEventListener("change", recordMode);
}

function injectLayoutAndSelectionStyles() {
  if (document.querySelector("#backteststock-ui-enhancement-styles")) return;
  const style = document.createElement("style");
  style.id = "backteststock-ui-enhancement-styles";
  style.textContent = `
    .site-header, .tab-nav, main { max-width: 1480px; }
    .optimizer-selection-status {
      display: inline-flex;
      align-items: center;
      min-height: 2.1rem;
      padding: 0.35rem 0.7rem;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: var(--surface-subtle);
      color: var(--muted);
      font-size: 0.82rem;
      font-weight: 750;
      white-space: nowrap;
    }
    .optimizer-selection-status.complete {
      border-color: #86efac;
      background: #ecfdf5;
      color: var(--success);
    }
    .optimizer-selection-status.error {
      border-color: #fecdd3;
      background: #fff1f2;
      color: var(--danger);
    }
    .optimizer-select-column {
      width: 4.6rem;
      min-width: 4.6rem;
      text-align: center;
    }
    .optimizer-select-cell { text-align: center; }
    .optimizer-select-cell input { width: 1.05rem; min-height: 1.05rem; }
    #scan-table tr.optimizer-manual-selected { background: #eff6ff; }
    .optimizer-mode-box {
      display: grid;
      grid-template-columns: minmax(15rem, 0.36fr) minmax(0, 1fr);
      gap: 1rem;
      align-items: end;
      margin-bottom: 1rem;
      padding: 0.9rem;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: var(--surface-subtle);
    }
    .optimizer-mode-note { margin: 0; color: var(--muted); }
    .optimizer-mode-note.warning { color: var(--warning); }
    a.disabled { pointer-events: none; opacity: 0.55; }
    @media (max-width: 760px) {
      .optimizer-mode-box { grid-template-columns: 1fr; }
      .optimizer-selection-status { width: 100%; justify-content: center; }
    }
  `;
  document.head.append(style);
}

function updateMethodologyText() {
  const paragraphs = [...document.querySelectorAll("#about-panel .panel p")];
  const formulaParagraph = paragraphs.find((paragraph) => (
    paragraph.textContent.includes("個股績效列表")
    && paragraph.textContent.includes("Sortino")
  ));
  if (!formulaParagraph) return;
  formulaParagraph.textContent = [
    "個股績效列表同時顯示四種可排序分數：",
    "穩健公式 Sortino × √((1 + CAGR) ÷ (1 + Beta))、",
    "成長公式 Sortino × √(1 + CAGR) ÷ (1 + Beta)^0.25、",
    "回撤控制公式 Sortino × √((1 + CAGR) ÷ ((1 + Beta) × (1 + |最大回撤|)))，",
    "以及優化公式 Sortino × √((1 + CAGR) ÷ ((1 + Beta)^2 × (1 + |最大回撤|)))；",
    "每格同步顯示該公式名次。",
  ].join("");
}

function currentScanJob() {
  const job = readJson(localStorage, SCAN_JOB_STORAGE_KEY);
  return job?.version === 2 ? job : null;
}

function resultEligibility(result, benchmark) {
  if (!result) return { eligible: false, reason: "尚無完成結果" };
  if (result.error || result.status !== "ok") {
    return { eligible: false, reason: result.error || "回測未成功" };
  }
  if (String(result.ticker || "").toUpperCase() === String(benchmark || "").toUpperCase()) {
    return { eligible: false, reason: "比較基準不可作為候選股" };
  }
  const coverage = Number(result.data_coverage);
  if (!Number.isFinite(coverage) || coverage < 0.98) {
    return { eligible: false, reason: "資料覆蓋率低於 98%" };
  }
  if (result.corporate_action_status !== "verified_standard_actions") {
    return {
      eligible: false,
      reason: `公司行為稽核=${result.corporate_action_status || "unknown"}`,
    };
  }
  return { eligible: true, reason: "" };
}

function readManualSelection(job) {
  const saved = readJson(localStorage, MANUAL_SELECTION_STORAGE_KEY);
  if (!saved || saved.sourceJobId !== job?.id || !Array.isArray(saved.tickers)) {
    return [];
  }
  const allowed = new Set(job.payload.tickers);
  return [...new Set(saved.tickers.map((ticker) => String(ticker).toUpperCase()))]
    .filter((ticker) => allowed.has(ticker))
    .slice(0, MANUAL_CANDIDATE_COUNT);
}

function saveManualSelection(job, tickers) {
  writeJson(localStorage, MANUAL_SELECTION_STORAGE_KEY, {
    version: 1,
    sourceJobId: job?.id || null,
    selectedAt: new Date().toISOString(),
    tickers: [...tickers],
    startDate: job?.payload?.startDate || null,
    endDate: job?.payload?.endDate || null,
    benchmark: job?.payload?.benchmark || "SPY",
    selectionBasis: "full_period_scan_results",
    selectionBiasWarning: MANUAL_SELECTION_BIAS_WARNING,
  });
}

function enhanceScanSelection() {
  const scanTable = document.querySelector("#scan-table");
  const autoLink = document.querySelector("#open-optimizer");
  if (!scanTable || !autoLink || document.querySelector("#open-manual-optimizer")) return;

  let job = currentScanJob();
  let selected = readManualSelection(job);
  let applying = false;
  let scheduled = false;

  autoLink.textContent = "自動嚴格模式";
  autoLink.addEventListener("click", () => {
    localStorage.setItem(OPTIMIZER_MODE_STORAGE_KEY, "auto");
  });

  const toolbar = autoLink.closest(".toolbar") || autoLink.parentElement;
  const status = document.createElement("span");
  status.id = "optimizer-manual-selection-status";
  status.className = "optimizer-selection-status";

  const clearButton = document.createElement("button");
  clearButton.type = "button";
  clearButton.id = "clear-optimizer-selection";
  clearButton.className = "button ghost compact";
  clearButton.textContent = "清除候選";

  const manualLink = document.createElement("a");
  manualLink.id = "open-manual-optimizer";
  manualLink.className = "button secondary";
  manualLink.href = "/optimizer.html?mode=manual";
  manualLink.target = "_blank";
  manualLink.rel = "noopener";
  manualLink.textContent = "使用已選 20 檔";

  toolbar.insertBefore(status, autoLink);
  toolbar.insertBefore(clearButton, autoLink);
  toolbar.insertBefore(manualLink, autoLink);

  function refreshControls(message = "") {
    const complete = selected.length === MANUAL_CANDIDATE_COUNT;
    status.textContent = message || `手動候選池 ${selected.length} / ${MANUAL_CANDIDATE_COUNT}`;
    status.classList.toggle("complete", complete && !message);
    status.classList.toggle("error", Boolean(message));
    manualLink.setAttribute("aria-disabled", String(!complete));
    manualLink.tabIndex = complete ? 0 : -1;
    manualLink.classList.toggle("disabled", !complete);
    clearButton.disabled = selected.length === 0;
    scanTable.querySelectorAll("input[data-optimizer-ticker]").forEach((checkbox) => {
      const ticker = checkbox.dataset.optimizerTicker;
      checkbox.checked = selected.includes(ticker);
      checkbox.disabled = checkbox.dataset.eligible !== "true"
        || (!checkbox.checked && selected.length >= MANUAL_CANDIDATE_COUNT);
      checkbox.closest("tr")?.classList.toggle(
        "optimizer-manual-selected",
        checkbox.checked,
      );
    });
  }

  function applySelectionCells() {
    scheduled = false;
    if (applying) return;
    applying = true;
    try {
      job = currentScanJob();
      if (!job) {
        selected = [];
        refreshControls();
        return;
      }
      const saved = readJson(localStorage, MANUAL_SELECTION_STORAGE_KEY);
      if (saved?.sourceJobId && saved.sourceJobId !== job.id) {
        localStorage.removeItem(MANUAL_SELECTION_STORAGE_KEY);
        selected = [];
      }
      const resultMap = new Map(
        (job.results || []).map((result) => [String(result.ticker).toUpperCase(), result]),
      );
      const benchmark = job.payload?.benchmark || "SPY";
      const headerRow = scanTable.querySelector("thead tr");
      if (headerRow && !headerRow.querySelector(".optimizer-select-column")) {
        const header = document.createElement("th");
        header.scope = "col";
        header.className = "optimizer-select-column";
        header.textContent = "候選";
        const tickerHeader = headerRow.querySelector("th");
        tickerHeader?.insertAdjacentElement("afterend", header);
      }
      scanTable.querySelectorAll("tbody tr").forEach((row) => {
        if (row.querySelector(".optimizer-select-cell")) return;
        const tickerCell = row.querySelector("th[scope='row']") || row.querySelector("th");
        const ticker = String(row.dataset.ticker || tickerCell?.textContent || "")
          .trim().split(/\s+/u)[0].toUpperCase();
        if (!ticker || !tickerCell) return;
        const eligibility = resultEligibility(resultMap.get(ticker), benchmark);
        const cell = document.createElement("td");
        cell.className = "optimizer-select-cell";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.dataset.optimizerTicker = ticker;
        checkbox.dataset.eligible = String(eligibility.eligible);
        checkbox.setAttribute("aria-label", `選擇 ${ticker} 為最佳化候選股`);
        if (!eligibility.eligible) checkbox.title = eligibility.reason;
        cell.append(checkbox);
        tickerCell.insertAdjacentElement("afterend", cell);
      });
      refreshControls();
    } finally {
      applying = false;
    }
  }

  function scheduleApply() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(applySelectionCells);
  }

  scanTable.addEventListener("change", (event) => {
    const checkbox = event.target.closest("input[data-optimizer-ticker]");
    if (!checkbox) return;
    const ticker = checkbox.dataset.optimizerTicker;
    if (checkbox.checked) {
      if (selected.length >= MANUAL_CANDIDATE_COUNT) {
        checkbox.checked = false;
        refreshControls(`最多只能選擇 ${MANUAL_CANDIDATE_COUNT} 檔。`);
        setTimeout(() => refreshControls(), 1800);
        return;
      }
      selected = [...selected.filter((item) => item !== ticker), ticker];
    } else {
      selected = selected.filter((item) => item !== ticker);
    }
    saveManualSelection(job, selected);
    refreshControls();
  });

  clearButton.addEventListener("click", () => {
    selected = [];
    localStorage.removeItem(MANUAL_SELECTION_STORAGE_KEY);
    refreshControls();
  });

  manualLink.addEventListener("click", (event) => {
    if (selected.length !== MANUAL_CANDIDATE_COUNT) {
      event.preventDefault();
      refreshControls(`請先選滿 ${MANUAL_CANDIDATE_COUNT} 檔。`);
      setTimeout(() => refreshControls(), 1800);
      return;
    }
    saveManualSelection(job, selected);
    localStorage.setItem(OPTIMIZER_MODE_STORAGE_KEY, "manual");
  });

  const observer = new MutationObserver(scheduleApply);
  observer.observe(scanTable, { childList: true, subtree: true });
  scheduleApply();
}

function installOptimizerPrepareMetadataPatch() {
  if (window.__backteststockOptimizerFetchPatched) return;
  window.__backteststockOptimizerFetchPatched = true;
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = typeof input === "string" ? input : input?.url || "";
    if (
      url.includes("/api/optimizer/prepare")
      && localStorage.getItem(OPTIMIZER_MODE_STORAGE_KEY) === "manual"
      && typeof init.body === "string"
    ) {
      try {
        const payload = JSON.parse(init.body);
        payload.candidateSelection = {
          ...(payload.candidateSelection || {}),
          mode: "manual_fixed_20",
          selectionBasis: "full_period_scan_results",
          selectionBiasWarning: MANUAL_SELECTION_BIAS_WARNING,
        };
        init = { ...init, body: JSON.stringify(payload) };
      } catch {
        // Leave malformed requests unchanged; the API returns its normal validation error.
      }
    }
    return nativeFetch(input, init);
  };
}

function enhanceOptimizerMode() {
  const sourceTickers = document.querySelector("#optimizer-source-tickers");
  const rankingField = document.querySelector("#optimizer-ranking-field");
  const sourceStatus = document.querySelector("#optimizer-source-status");
  if (!sourceTickers || !rankingField || !sourceStatus) return;
  if (document.querySelector("#optimizer-candidate-mode")) return;

  const sourcePanel = sourceTickers.closest("section.panel");
  const sourceJob = currentScanJob();
  const automaticTickers = Array.isArray(sourceJob?.payload?.tickers)
    ? sourceJob.payload.tickers
    : sourceTickers.value.split(/[\s,;]+/u).filter(Boolean);
  const manual = readJson(localStorage, MANUAL_SELECTION_STORAGE_KEY);
  const manualTickers = manual?.sourceJobId === sourceJob?.id
    && Array.isArray(manual?.tickers)
    ? [...new Set(manual.tickers)].slice(0, MANUAL_CANDIDATE_COUNT)
    : [];

  const box = document.createElement("div");
  box.className = "optimizer-mode-box";
  const label = document.createElement("label");
  const labelText = document.createElement("span");
  labelText.textContent = "候選池模式";
  const select = document.createElement("select");
  select.id = "optimizer-candidate-mode";
  select.innerHTML = `
    <option value="auto">自動嚴格模式：來源池於訓練期重排前 20</option>
    <option value="manual">手動模式：固定績效列表所選 20 檔</option>
  `;
  label.append(labelText, select);
  const note = document.createElement("p");
  note.id = "optimizer-candidate-mode-note";
  note.className = "optimizer-mode-note";
  box.append(label, note);
  sourcePanel.insertBefore(box, sourceTickers.closest("label"));

  function applyMode(requestedMode) {
    let mode = requestedMode;
    if (mode === "manual" && manualTickers.length !== MANUAL_CANDIDATE_COUNT) {
      mode = "auto";
      note.textContent = `手動模式需要從個股績效列表選滿 ${MANUAL_CANDIDATE_COUNT} 檔；目前沒有有效選取。`;
      note.classList.add("warning");
    }
    select.value = mode;
    localStorage.setItem(OPTIMIZER_MODE_STORAGE_KEY, mode);
    if (mode === "manual") {
      sourceTickers.value = manualTickers.join(", ");
      sourceTickers.readOnly = true;
      rankingField.disabled = true;
      sourceStatus.textContent = `已載入手動候選池 ${manualTickers.length} 檔；將逐檔重算訓練期並執行嚴格覆蓋驗證。`;
      note.textContent = MANUAL_SELECTION_BIAS_WARNING;
      note.classList.add("warning");
    } else {
      sourceTickers.value = automaticTickers.join(", ");
      sourceTickers.readOnly = false;
      rankingField.disabled = false;
      sourceStatus.textContent = automaticTickers.length
        ? `已載入掃描工作 ${automaticTickers.length} 檔；最佳化器會只用訓練期重新掃描與排序。`
        : "未找到既有掃描工作；請貼入至少 20 檔股票代碼。";
      note.textContent = "候選池、排序與參數選擇只使用訓練期資料。";
      note.classList.remove("warning");
    }
  }

  select.addEventListener("change", () => applyMode(select.value));
  const queryMode = new URLSearchParams(window.location.search).get("mode");
  const savedMode = localStorage.getItem(OPTIMIZER_MODE_STORAGE_KEY);
  applyMode(queryMode === "manual" ? "manual" : savedMode === "manual" ? "manual" : "auto");
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  injectLayoutAndSelectionStyles();
  installOptimizerPrepareMetadataPatch();
  setTimeout(() => {
    refreshRollingBacktestDates();
    updateMethodologyText();
    enhanceScanSelection();
    enhanceOptimizerMode();
  }, 0);
}
