function tickerSearchInput(asset) {
  const wrap = e("div", { className: "pl-ticker-search" });
  const node = input("text", asset.symbol, (value) => {
    asset.symbol = value.trim().toUpperCase().replace(/[^A-Z0-9.^=_-]/g, "").slice(0, 32);
    persist();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => searchTickers(asset, node, wrap), 300);
  }, { autocomplete: "off", spellcheck: "false", placeholder: t("ticker") });
  wrap.append(node, e("div", { className: "pl-search-results hidden" }));
  return wrap;
}
async function searchTickers(asset, node, wrap) {
  const query = node.value.trim(); const box = wrap.querySelector(".pl-search-results");
  if (!query) { box.classList.add("hidden"); return; }
  try {
    const result = await fetch(`/api/portfolio-lab/assets/search?q=${encodeURIComponent(query)}&limit=8`);
    if (!result.ok) return;
    const rows = await result.json();
    box.replaceChildren(...rows.map((item) => {
      const button = e("button", { className: "pl-search-option", attributes: { type: "button" } }, [e("strong", { text: item.symbol }), e("span", { text: `${item.name || item.symbol}${item.currency ? ` · ${item.currency}` : ""}` })]);
      button.addEventListener("click", () => { asset.symbol = item.symbol; node.value = item.symbol; persist(); box.classList.add("hidden"); });
      return button;
    }));
    box.classList.toggle("hidden", !rows.length);
  } catch { box.classList.add("hidden"); }
}

function totals() { return Array.from({ length: state.portfolioCount }, (_, index) => state.assets.reduce((sum, asset) => sum + number(asset.weights[index]), 0)); }
function renderAssets() {
  const root = e("div", { className: "pl-assets" });
  const toolbar = e("div", { className: "pl-asset-toolbar" }, [
    field(t("benchmark"), input("text", state.benchmark, (value) => patch({ benchmark: value.toUpperCase() }, false), { autocomplete: "off" })),
    e("div", { className: "pl-toolbar-actions" }),
  ]);
  const actions = toolbar.querySelector(".pl-toolbar-actions");
  const addPortfolio = e("button", { className: "button secondary", text: `＋ ${t("addPortfolio")}`, attributes: { type: "button" } });
  addPortfolio.disabled = state.portfolioCount >= MAX_PORTFOLIOS;
  addPortfolio.addEventListener("click", () => patch({ portfolioCount: Math.min(MAX_PORTFOLIOS, state.portfolioCount + 1) }));
  const removePortfolio = e("button", { className: "button ghost", text: `− ${t("removePortfolio")}`, attributes: { type: "button" } });
  removePortfolio.disabled = state.portfolioCount <= 1;
  removePortfolio.addEventListener("click", () => patch({ portfolioCount: Math.max(1, state.portfolioCount - 1) }));
  actions.append(addPortfolio, removePortfolio); root.append(toolbar);

  const tableWrap = e("div", { className: "pl-matrix-wrap" });
  const table = e("table", { className: "pl-matrix" });
  const head = e("thead"); const row = e("tr", {}, [e("th", { text: t("ticker") })]);
  for (let index = 0; index < state.portfolioCount; index += 1) {
    const name = input("text", state.portfolioNames[index], (value) => { state.portfolioNames[index] = value; persist(); }, { "aria-label": `${t("portfolio")} ${index + 1}` });
    row.append(e("th", {}, [e("span", { text: `${t("portfolio")} #${index + 1}` }), name]));
  }
  row.append(e("th", { text: "" })); head.append(row); table.append(head);
  const body = e("tbody");
  state.assets.forEach((asset, assetIndex) => {
    const tr = e("tr"); tr.append(e("td", {}, [e("span", { className: "pl-row-index", text: String(assetIndex + 1) }), tickerSearchInput(asset)]));
    for (let index = 0; index < state.portfolioCount; index += 1) {
      tr.append(e("td", {}, [input("number", asset.weights[index], (value) => { asset.weights[index] = value === "" ? "" : number(value); persist(); renderWeightStatus(); }, { min: "0", max: "100", step: "0.1", "aria-label": `${asset.symbol || t("ticker")} ${t("portfolio")} ${index + 1}` })]));
    }
    const remove = e("button", { className: "button danger compact", text: "×", attributes: { type: "button", "aria-label": `${t("clear")} ${assetIndex + 1}` } });
    remove.addEventListener("click", () => { state.assets = state.assets.length <= 1 ? [blankAsset()] : state.assets.filter((item) => item.id !== asset.id); persist(); render(); });
    tr.append(e("td", {}, [remove])); body.append(tr);
  });
  const totalRow = e("tr", { className: "pl-total-row" }, [e("th", { text: t("total") })]);
  totals().forEach((total, index) => totalRow.append(e("td", { className: Math.abs(total - 100) <= 0.05 ? "complete" : "", attributes: { "data-total-index": String(index) } }, [e("strong", { text: `${total.toFixed(1)}%` }), e("small", { text: Math.abs(total - 100) <= 0.05 ? t("ready") : t("adjust") })])));
  totalRow.append(e("td")); body.append(totalRow); table.append(body); tableWrap.append(table); root.append(tableWrap);
  const addAsset = e("button", { className: "button dashed", text: `＋ ${t("addAsset")} (${state.assets.length}/${MAX_ASSETS})`, attributes: { type: "button" } });
  addAsset.disabled = state.assets.length >= MAX_ASSETS;
  addAsset.addEventListener("click", () => { state.assets.push(blankAsset()); persist(); render(); });
  root.append(addAsset); return root;
}
function renderWeightStatus() {
  totals().forEach((total, index) => {
    const cell = mount?.querySelector(`[data-total-index="${index}"]`); if (!cell) return;
    cell.classList.toggle("complete", Math.abs(total - 100) <= 0.05);
    cell.querySelector("strong").textContent = `${total.toFixed(1)}%`;
    cell.querySelector("small").textContent = Math.abs(total - 100) <= 0.05 ? t("ready") : t("adjust");
  });
}

function portfolioDraft(index) {
  const weighted = state.assets
    .map((asset) => ({
      symbol: asset.symbol.trim().toUpperCase(),
      weight: number(asset.weights[index]),
    }))
    .filter((asset) => asset.weight > 0);
  return {
    name: state.portfolioNames[index]?.trim() || `${t("portfolio")} ${index + 1}`,
    assets: weighted,
    total: weighted.reduce((sum, asset) => sum + asset.weight, 0),
  };
}

function validate() {
  const errors = [];
  const portfolios = [];
  if (!state.startDate || !state.endDate || state.startDate >= state.endDate) {
    errors.push(state.locale === "en" ? "Start date must be before end date." : "起始日期必須早於結束日期。");
  }
  if (number(state.initialAmount) <= 0) {
    errors.push(state.locale === "en" ? "Initial amount must be greater than zero." : "初始金額必須大於零。");
  }

  for (let index = 0; index < state.portfolioCount; index += 1) {
    const draft = portfolioDraft(index);
    if (draft.total <= 0.05) continue;
    let valid = true;
    if (Math.abs(draft.total - 100) > 0.05) {
      errors.push(state.locale === "en"
        ? `Portfolio ${index + 1} totals ${draft.total.toFixed(2)}%; it must equal 100%.`
        : `投資組合 ${index + 1} 權重目前為 ${draft.total.toFixed(2)}%，必須等於 100%。`);
      valid = false;
    }
    if (draft.assets.some((asset) => !asset.symbol)) {
      errors.push(state.locale === "en"
        ? `Portfolio ${index + 1} has a weighted row without a ticker.`
        : `投資組合 ${index + 1} 有權重但尚未填寫資產代碼。`);
      valid = false;
    }
    const symbols = draft.assets.map((asset) => asset.symbol).filter(Boolean);
    if (new Set(symbols).size !== symbols.length) {
      errors.push(state.locale === "en"
        ? `Portfolio ${index + 1} contains duplicate tickers.`
        : `投資組合 ${index + 1} 有重複股票代碼。`);
      valid = false;
    }
    if (valid) portfolios.push({ name: draft.name, assets: draft.assets });
  }

  if (!portfolios.length) {
    errors.push(state.locale === "en" ? "At least one complete portfolio is required." : "至少需要一組權重合計 100% 的投資組合。");
  }
  if (state.cashflowType !== "none" && state.cashflowFrequency === "none") {
    errors.push(state.locale === "en" ? "Enabled cash flows require a frequency." : "啟用現金流時必須選擇頻率。");
  }
  if (state.leverageType === "fixed_ratio" && number(state.leverageRatio) <= 1) {
    errors.push(state.locale === "en" ? "Fixed leverage ratio must be greater than 1." : "固定槓桿倍數必須大於 1。");
  }
  return { errors, portfolios };
}
function requestPayload(portfolios) {
  return {
    portfolios, benchmark: state.benchmark.trim().toUpperCase() || null, start_date: state.startDate, end_date: state.endDate,
    initial_amount: state.initialAmount, base_currency: "TWD", include_ytd: state.includeYtd,
    reinvest_dividends: state.reinvestDividends, display_income: state.displayIncome, transaction_cost_bps: state.transactionCostBps,
    cashflow: { type: state.cashflowType, amount: state.cashflowAmount, frequency: state.cashflowType === "none" ? "none" : state.cashflowFrequency, timing: state.cashflowTiming, annual_growth_rate: state.cashflowGrowthRate },
    rebalancing: { frequency: state.rebalanceFrequency, threshold_percent: state.rebalanceThreshold },
    leverage: { type: state.leverageType, ratio: state.leverageRatio, debt_amount: state.debtAmount, annual_interest_rate: state.interestRate, maintenance_margin: state.maintenanceMargin },
    analytics: { style_analysis: state.styleAnalysis, factor_regression: state.factorRegression, regime: state.regime, risk_free_rate: state.riskFreeRate, inflation_adjusted: state.inflationAdjusted },
    output_frequency: state.outputFrequency,
  };
}
function publishPortfolioLabResult(payload) {
  window.dispatchEvent(new CustomEvent("portfolio-lab:result", { detail: payload }));
}
async function runBacktest() {
  const { errors, portfolios } = validate();
  if (errors.length) { state.activeConfigTab = "assets"; render(); requestAnimationFrame(() => announce(errors.join("\n"), "error")); return; }
  const button = mount.querySelector("#pl-run"); button.disabled = true; button.textContent = t("running"); announce("");
  abortController?.abort(); abortController = new AbortController();
  try {
    const result = await fetch("/api/portfolio-lab/backtests", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(requestPayload(portfolios)), signal: abortController.signal });
    const payload = await result.json().catch(() => ({}));
    if (!result.ok) {
      const detail = Array.isArray(payload.detail) ? payload.detail.map((item) => item.msg).join("；") : payload.detail || payload.error || `HTTP ${result.status}`;
      throw new Error(detail);
    }
    response = payload; activeResultTab = "overview"; selectedResult = 0; render();
    publishPortfolioLabResult(payload);
    requestAnimationFrame(() => mount.querySelector("#pl-results")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  } catch (error) { if (error.name !== "AbortError") announce(error.message, "error"); }
  finally { const next = mount.querySelector("#pl-run"); if (next) { next.disabled = false; next.textContent = t("run"); } }
}
function announce(message = "", kind = "") { const node = mount?.querySelector("#pl-message"); if (!node) return; node.textContent = message; node.className = `pl-message ${kind}`; node.hidden = !message; }
