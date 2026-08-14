const SCREENER_RESEARCH_CONTEXT_KEY = "backteststock-screener-research-context-v1";
const CURRENT_MODE = "current";
const PIT_MODE = "pit";
const CURRENT_WARNING = "目前快照會使用當前 Universe 與目前基本面；若把清單用於較早回測區間，屬回溯研究，不是 PIT 歷史選股。";
const PIT_WARNING = "PIT 模式只使用選股基準日當時已取得的成分股證據；目前基本面不會套用。產業、市值、本益比與估值排序在此模式停用。";

let activeController = null;
let contextObserver = null;
let contextRenderScheduled = false;

function localIsoDate(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function validIsoDate(value) {
  const raw = String(value || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return false;
  const [year, month, day] = raw.split("-").map(Number);
  const parsed = new Date(year, month - 1, day);
  return parsed.getFullYear() === year
    && parsed.getMonth() === month - 1
    && parsed.getDate() === day;
}

function sanitizeTicker(value) {
  return String(value || "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9.^=_-]/g, "")
    .slice(0, 20);
}

function parseTickers(value) {
  return [...new Set(String(value || "").split(/[\s,;]+/).map(sanitizeTicker).filter(Boolean))];
}

function setMessage(element, message = "") {
  if (!element) return;
  element.textContent = message;
  element.classList.toggle("hidden", !message);
}

function createControlLabel(labelText, control, helper = null) {
  const label = document.createElement("label");
  const caption = document.createElement("span");
  caption.textContent = labelText;
  label.append(caption, control);
  if (helper) label.append(helper);
  return label;
}

function injectResearchControls() {
  const universeSelect = document.querySelector("#screener-index");
  const grid = universeSelect?.closest(".control-grid");
  const universeLabel = universeSelect?.closest("label");
  if (!grid || !universeLabel) return null;

  let mode = document.querySelector("#screener-selection-mode");
  let selectionAsOf = document.querySelector("#screener-selection-as-of");
  let note = document.querySelector("#screener-mode-note");
  if (!mode) {
    mode = document.createElement("select");
    mode.id = "screener-selection-mode";
    mode.append(
      new Option("目前快照（可用基本面）", CURRENT_MODE, true, true),
      new Option("PIT 歷史成分股（membership only）", PIT_MODE),
    );
    const modeLabel = createControlLabel("選股時間模式", mode);

    selectionAsOf = document.createElement("input");
    selectionAsOf.id = "screener-selection-as-of";
    selectionAsOf.type = "date";
    selectionAsOf.value = localIsoDate();
    selectionAsOf.max = localIsoDate();

    note = document.createElement("small");
    note.id = "screener-mode-note";
    note.textContent = CURRENT_WARNING;
    const dateLabel = createControlLabel("PIT 選股基準日", selectionAsOf, note);

    universeLabel.insertAdjacentElement("afterend", dateLabel);
    universeLabel.insertAdjacentElement("afterend", modeLabel);
  }
  return { mode, selectionAsOf, note };
}

function researchControls() {
  return {
    mode: document.querySelector("#screener-selection-mode"),
    selectionAsOf: document.querySelector("#screener-selection-as-of"),
    sector: document.querySelector("#screener-sector"),
    marketCap: document.querySelector("#screener-market-cap"),
    pe: document.querySelector("#screener-pe"),
    sort: document.querySelector("#screener-sort"),
    limit: document.querySelector("#screener-limit"),
    runButton: document.querySelector("#run-screener"),
  };
}

function applyModeState() {
  const controls = researchControls();
  const pit = controls.mode?.value === PIT_MODE;
  if (controls.selectionAsOf) controls.selectionAsOf.disabled = !pit;
  for (const control of [controls.sector, controls.marketCap, controls.pe, controls.sort]) {
    if (control) control.disabled = pit;
  }
  const note = document.querySelector("#screener-mode-note");
  if (note) note.textContent = pit ? PIT_WARNING : CURRENT_WARNING;
  if (controls.runButton) {
    controls.runButton.textContent = pit
      ? "建立 PIT 成分股回測清單"
      : "篩選並建立回測清單";
  }
}

function readLimit() {
  const raw = String(document.querySelector("#screener-limit")?.value || "").trim();
  if (!raw) return null;
  const limit = Number(raw);
  if (!Number.isSafeInteger(limit) || limit < 1) {
    throw new Error("最多回測檔數必須是大於 0 的整數；留空則回測全部。");
  }
  return limit;
}

function buildCurrentPayload(universeId, limit) {
  const filters = {};
  const marketCap = Number(document.querySelector("#screener-market-cap")?.value);
  const maxPe = Number(document.querySelector("#screener-pe")?.value);
  if (Number.isFinite(marketCap) && marketCap > 0) filters.marketCap = { min: marketCap * 1e8 };
  if (Number.isFinite(maxPe) && maxPe > 0) filters.trailingPE = { max: maxPe };
  return {
    universe: universeId,
    sector: document.querySelector("#screener-sector")?.value || "any",
    filters,
    limit,
    sort: document.querySelector("#screener-sort")?.value || "marketCap-desc",
  };
}

function buildPitPayload(universeId, limit) {
  const selectionAsOf = String(document.querySelector("#screener-selection-as-of")?.value || "").trim();
  const today = localIsoDate();
  if (!validIsoDate(selectionAsOf)) {
    throw new Error("請選擇有效的 PIT 選股基準日。");
  }
  if (selectionAsOf > today) {
    throw new Error("PIT 選股基準日不得晚於今天。");
  }
  return {
    universe: universeId,
    selectionAsOf,
    sector: "any",
    filters: {},
    limit,
    sort: "ticker-asc",
  };
}

function buildScreenerPayload() {
  const universeSelect = document.querySelector("#screener-index");
  const universeId = String(universeSelect?.value || "").trim();
  if (!universeId || universeSelect?.selectedOptions?.[0]?.disabled) {
    throw new Error("所選 Universe 尚無有效版本，請改用可用股票池或手動輸入代碼。");
  }
  const limit = readLimit();
  return document.querySelector("#screener-selection-mode")?.value === PIT_MODE
    ? buildPitPayload(universeId, limit)
    : buildCurrentPayload(universeId, limit);
}

function showLoading(message) {
  const overlay = document.querySelector("#loading-overlay");
  const loadingMessage = document.querySelector("#loading-message");
  if (loadingMessage) loadingMessage.textContent = message;
  overlay?.classList.remove("hidden");
}

function hideLoading() {
  document.querySelector("#loading-overlay")?.classList.add("hidden");
}

async function fetchJson(path, init, controller) {
  const response = await fetch(path, { ...init, signal: controller.signal });
  const contentType = response.headers.get("content-type") || "";
  let payload = null;
  if (contentType.includes("application/json")) {
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    const error = new Error(payload?.error || `API 請求失敗（HTTP ${response.status}）。`);
    error.status = response.status;
    throw error;
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("預篩選服務回傳格式無效。");
  }
  return payload;
}

function funnelValue(value, fallback = "—") {
  return value == null || !Number.isFinite(Number(value))
    ? fallback
    : Number(value).toLocaleString("zh-TW");
}

function renderFunnel(response) {
  const funnel = response?.funnel || {};
  const pit = response?.researchValidity?.selectionMode === "point_in_time_membership_only";
  const stages = pit
    ? [
      ["Universe", funnel.universeCount, "—"],
      ["PIT 成分股", funnel.passedFilters, "—"],
      ["歷史基本面", funnel.fundamentalsAvailable, "未套用"],
      ["納入回測", funnel.selectedForScan, "—"],
    ]
    : [
      ["Universe", funnel.universeCount, "—"],
      ["具基本面", funnel.fundamentalsAvailable, "—"],
      ["通過條件", funnel.passedFilters, "—"],
      ["納入回測", funnel.selectedForScan, "—"],
    ];
  const container = document.querySelector("#screener-funnel");
  if (!container) return;
  const cards = stages.map(([label, value, fallback], index) => {
    const article = document.createElement("article");
    article.className = "funnel-card";
    const step = document.createElement("span");
    step.textContent = `步驟 ${index + 1}`;
    const strong = document.createElement("strong");
    strong.textContent = funnelValue(value, fallback);
    const small = document.createElement("small");
    small.textContent = label;
    article.append(step, strong, small);
    return article;
  });
  container.replaceChildren(...cards);
  container.classList.remove("hidden");
}

function researchContextFrom(response, candidateTickers) {
  return {
    version: 1,
    savedAt: new Date().toISOString(),
    candidateTickers,
    universe: response.universe || null,
    fundamentalsAsOf: response.fundamentalsAsOf ?? null,
    funnel: response.funnel || null,
    warnings: Array.isArray(response.warnings) ? response.warnings : [],
    researchValidity: response.researchValidity || null,
  };
}

function saveResearchContext(context) {
  try {
    localStorage.setItem(SCREENER_RESEARCH_CONTEXT_KEY, JSON.stringify(context));
  } catch (error) {
    console.warn("Unable to persist screener research context", error);
  }
}

function loadResearchContext() {
  try {
    const parsed = JSON.parse(localStorage.getItem(SCREENER_RESEARCH_CONTEXT_KEY));
    return parsed?.version === 1 && Array.isArray(parsed.candidateTickers) ? parsed : null;
  } catch {
    return null;
  }
}

function currentTickerList() {
  return parseTickers(document.querySelector("#scan-tickers")?.value || "");
}

function sameTickerList(left, right) {
  return left.length === right.length && left.every((ticker, index) => ticker === right[index]);
}

function matchingResearchContext() {
  const context = loadResearchContext();
  if (!context) return null;
  return sameTickerList(context.candidateTickers.map(sanitizeTicker), currentTickerList())
    ? context
    : null;
}

function contextText(context) {
  const universe = context.universe || {};
  const validity = context.researchValidity || {};
  const pit = validity.selectionMode === "point_in_time_membership_only";
  if (pit) {
    const authority = validity.membershipAuthoritative
      ? "官方／權威 membership"
      : "代理 membership（非官方歷史成分名單）";
    return [
      "模式：PIT 歷史成分股",
      `Universe：${universe.name || universe.id || "—"}`,
      `版本：${universe.version || "—"}`,
      `選股基準日：${validity.requestedAsOf || universe.requestedAsOf || "—"}`,
      `成分觀測日：${validity.membershipObservationAsOf || universe.sourceAsOf || "—"}`,
      `證據可得日：${validity.membershipEvidenceAvailableAsOf || universe.evidenceAvailableAsOf || "—"}`,
      `成分來源：${authority}`,
      "基本面：未套用",
      "membership 因果性：已驗證",
    ].join(" · ");
  }
  return [
    "模式：目前快照（回溯研究）",
    `Universe：${universe.name || universe.id || "—"}`,
    `版本：${universe.version || "—"}`,
    `成分日：${universe.sourceAsOf || "未提供"}`,
    `基本面日：${context.fundamentalsAsOf || "未提供"}`,
    "歷史選股安全性：否（非 PIT）",
  ].join(" · ");
}

function renderResearchContext() {
  const resultSection = document.querySelector("#scan-results");
  const element = document.querySelector("#scan-context");
  if (!resultSection || !element) return;
  const context = matchingResearchContext();
  if (!context || resultSection.classList.contains("hidden")) {
    if (element.dataset.researchContextOwner === "screener-research") {
      delete element.dataset.researchContextOwner;
      if (element.textContent) element.textContent = "";
      if (!element.classList.contains("hidden")) element.classList.add("hidden");
    }
    return;
  }
  const next = contextText(context);
  element.dataset.researchContextOwner = "screener-research";
  if (element.textContent !== next) element.textContent = next;
  if (element.classList.contains("hidden")) element.classList.remove("hidden");
}

function scheduleContextRender() {
  if (contextRenderScheduled) return;
  contextRenderScheduled = true;
  requestAnimationFrame(() => {
    contextRenderScheduled = false;
    renderResearchContext();
  });
}

async function handleScreenerClick(event) {
  event.preventDefault();
  event.stopImmediatePropagation();
  const scanError = document.querySelector("#scan-error");
  const warning = document.querySelector("#screener-warning");
  setMessage(scanError);
  setMessage(warning);

  let payload;
  try {
    payload = buildScreenerPayload();
  } catch (error) {
    setMessage(scanError, error.message);
    return;
  }

  const button = document.querySelector("#run-screener");
  const controller = new AbortController();
  activeController?.abort();
  activeController = controller;
  if (button) button.disabled = true;
  showLoading(payload.selectionAsOf ? "正在建立 PIT 歷史成分股清單…" : "正在執行基本面預篩選…");
  try {
    const response = await fetchJson("/api/v2/screener", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    }, controller);
    if (activeController !== controller) return;
    const candidates = Array.isArray(response.candidates) ? response.candidates : [];
    const tickers = candidates.map((candidate) => sanitizeTicker(candidate?.ticker)).filter(Boolean);
    const tickerInput = document.querySelector("#scan-tickers");
    if (tickerInput) {
      tickerInput.value = tickers.join(", ");
      tickerInput.dispatchEvent(new Event("input", { bubbles: true }));
    }
    renderFunnel(response);
    setMessage(warning, Array.isArray(response.warnings) ? response.warnings.join("\n") : "");
    saveResearchContext(researchContextFrom(response, tickers));
    scheduleContextRender();
    if (!tickers.length) setMessage(scanError, "沒有符合目前條件的股票。");
  } catch (error) {
    if (controller.signal.aborted) {
      if (activeController === controller) setMessage(scanError, "預篩選已取消。");
    } else {
      setMessage(scanError, error.message || "預篩選失敗。");
    }
  } finally {
    if (activeController === controller) {
      activeController = null;
      hideLoading();
      if (button) button.disabled = false;
    }
  }
}

function handleCancel(event) {
  if (!activeController) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  activeController.abort();
}

function initializeContextObserver() {
  const resultSection = document.querySelector("#scan-results");
  const context = document.querySelector("#scan-context");
  if (!resultSection || !context) return;
  contextObserver = new MutationObserver(scheduleContextRender);
  contextObserver.observe(resultSection, {
    attributes: true,
    attributeFilter: ["class", "data-scan-job-id"],
  });
  contextObserver.observe(context, {
    attributes: true,
    attributeFilter: ["class"],
    childList: true,
    characterData: true,
    subtree: true,
  });
}

function initialize() {
  const injected = injectResearchControls();
  if (!injected) return;
  applyModeState();
  injected.mode.addEventListener("change", applyModeState);
  document.querySelector("#run-screener")?.addEventListener("click", handleScreenerClick, true);
  document.querySelector("#cancel-request")?.addEventListener("click", handleCancel, true);
  document.querySelector("#scan-tickers")?.addEventListener("input", scheduleContextRender);
  document.querySelector("#scan-form")?.addEventListener("submit", () => {
    setTimeout(scheduleContextRender, 0);
  }, true);
  initializeContextObserver();
  scheduleContextRender();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialize, { once: true });
} else {
  initialize();
}
