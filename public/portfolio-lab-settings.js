function renderHeader() {
  const header = e("header", { className: "pl-header" }, [
    e("div", { className: "pl-brand" }, [e("span", { className: "pl-mark", text: "B" }), e("div", {}, [e("strong", { text: t("title") }), e("span", { text: t("subtitle") })])]),
    e("div", { className: "pl-header-actions" }),
  ]);
  const actions = header.querySelector(".pl-header-actions");
  const theme = e("button", { className: "button ghost compact", text: state.theme === "dark" ? "☀" : "◐", attributes: { type: "button", title: "Theme" } });
  theme.addEventListener("click", () => patch({ theme: state.theme === "dark" ? "light" : "dark" }));
  const locale = e("button", { className: "button ghost compact", text: state.locale === "en" ? "繁中" : "EN", attributes: { type: "button" } });
  locale.addEventListener("click", () => patch({ locale: state.locale === "en" ? "zh-TW" : "en" }));
  const save = e("button", { className: "button ghost compact", text: t("save"), attributes: { type: "button" } });
  save.addEventListener("click", () => { persist(); announce(state.locale === "en" ? "Saved." : "設定已儲存。", "success"); });
  const share = e("button", { className: "button ghost compact", text: t("share"), attributes: { type: "button" } });
  share.addEventListener("click", async () => {
    const url = new URL(location.href); url.hash = `${SHARE_PREFIX}${encodeShare()}`;
    try { await navigator.clipboard.writeText(url.toString()); announce(t("copied"), "success"); }
    catch { prompt("Copy URL", url.toString()); }
  });
  const exportButton = e("button", { className: "button ghost compact", text: t("exportConfig"), attributes: { type: "button" } });
  exportButton.addEventListener("click", () => download("portfolio-lab-config.json", JSON.stringify(state, null, 2)));
  const reset = e("button", { className: "button ghost compact", text: t("reset"), attributes: { type: "button" } });
  reset.addEventListener("click", () => { state = defaults(); persist(); response = null; render(); });
  actions.append(theme, locale, save, share, exportButton, reset);
  return header;
}

function renderSettings() {
  const layout = e("div", { className: "pl-settings-grid" });
  const periodGrid = e("div", { className: "pl-form-grid" }, [
    field(t("start"), input("date", state.startDate, (value) => patch({ startDate: value }, false))),
    field(t("end"), input("date", state.endDate, (value) => patch({ endDate: value }, false), { max: isoDate(new Date()) })),
    field(t("initial"), input("number", state.initialAmount, (value) => patch({ initialAmount: number(value) }, false), { min: "1", step: "1000" })),
    field(t("currency"), select("TWD", [["TWD", "TWD · 新台幣"]], () => {}, { disabled: "" })),
    field(t("output"), select(state.outputFrequency, [["daily", state.locale === "en" ? "Daily" : "每日"], ["weekly", state.locale === "en" ? "Weekly" : "每週"], ["monthly", t("monthly")]], (value) => patch({ outputFrequency: value }, false))),
    toggle(t("includeYtd"), state.includeYtd, (value) => patch({ includeYtd: value }, false)),
  ]);
  layout.append(section(t("period"), periodGrid));

  const cashGrid = e("div", { className: "pl-form-grid" }, [
    field(state.locale === "en" ? "Cash-flow type" : "現金流方式", select(state.cashflowType, [["none", t("none")], ["fixed", t("fixed")], ["percent", t("percent")]], (value) => patch({ cashflowType: value, cashflowFrequency: value === "none" ? "none" : (state.cashflowFrequency === "none" ? "monthly" : state.cashflowFrequency) }))),
  ]);
  if (state.cashflowType !== "none") {
    cashGrid.append(
      field(t("amount"), input("number", state.cashflowAmount, (value) => patch({ cashflowAmount: number(value) }, false), { step: state.cashflowType === "percent" ? "0.1" : "100" })),
      field(t("frequency"), select(state.cashflowFrequency, [["monthly", t("monthly")], ["quarterly", t("quarterly")], ["annual", t("annual")]], (value) => patch({ cashflowFrequency: value }, false))),
      field(t("timing"), select(state.cashflowTiming, [["beginning", t("beginning")], ["end", t("ending")]], (value) => patch({ cashflowTiming: value }, false))),
      field(t("growth"), input("number", state.cashflowGrowthRate, (value) => patch({ cashflowGrowthRate: number(value) }, false), { step: "0.1" })),
    );
  }
  layout.append(section(t("cashflows"), cashGrid));

  layout.append(section(t("rebalancing"), e("div", { className: "pl-form-grid" }, [
    field(t("frequency"), select(state.rebalanceFrequency, [["none", t("none")], ["monthly", t("monthly")], ["quarterly", t("quarterly")], ["semiannual", t("semiannual")], ["annual", t("annual")]], (value) => patch({ rebalanceFrequency: value }, false))),
    field(t("threshold"), input("number", state.rebalanceThreshold ?? "", (value) => patch({ rebalanceThreshold: value === "" ? null : number(value) }, false), { min: "0.1", max: "100", step: "0.1", placeholder: "—" })),
  ])));

  const leverageGrid = e("div", { className: "pl-form-grid" }, [
    field(t("leverageType"), select(state.leverageType, [["none", t("none")], ["fixed_ratio", t("fixedRatio")], ["fixed_debt", t("fixedDebt")]], (value) => patch({ leverageType: value }))),
  ]);
  if (state.leverageType === "fixed_ratio") leverageGrid.append(field(t("ratio"), input("number", state.leverageRatio, (value) => patch({ leverageRatio: number(value) }, false), { min: "1.01", max: "5", step: "0.1" })));
  if (state.leverageType === "fixed_debt") leverageGrid.append(field(t("debt"), input("number", state.debtAmount, (value) => patch({ debtAmount: number(value) }, false), { min: "0", step: "1000" })));
  if (state.leverageType !== "none") leverageGrid.append(
    field(t("interest"), input("number", state.interestRate, (value) => patch({ interestRate: number(value) }, false), { min: "0", step: "0.1" })),
    field(t("maintenance"), input("number", state.maintenanceMargin, (value) => patch({ maintenanceMargin: number(value) }, false), { min: "0", max: "100" })),
  );
  layout.append(section(t("leverage"), leverageGrid));

  layout.append(section(t("dividends"), e("div", {}, [
    e("div", { className: "pl-toggle-grid" }, [
      toggle(t("reinvest"), state.reinvestDividends, (value) => patch({ reinvestDividends: value }, false)),
      toggle(t("income"), state.displayIncome, (value) => patch({ displayIncome: value }, false)),
    ]),
    e("div", { className: "pl-form-grid pl-spaced" }, [field(`${t("cost")} (bps)`, input("number", state.transactionCostBps, (value) => patch({ transactionCostBps: number(value) }, false), { min: "0", step: "0.1" }))]),
  ])));

  layout.append(section(t("analytics"), e("div", {}, [
    e("div", { className: "pl-toggle-grid" }, [
      toggle(t("style"), state.styleAnalysis, (value) => patch({ styleAnalysis: value }, false)),
      toggle(t("factors"), state.factorRegression, (value) => patch({ factorRegression: value }, false)),
      toggle(t("inflation"), state.inflationAdjusted, (value) => patch({ inflationAdjusted: value }, false)),
    ]),
    e("div", { className: "pl-form-grid pl-spaced" }, [
      field(t("regime"), select(state.regime, [["none", t("none")], ["market", state.locale === "en" ? "Market trend" : "市場趨勢"], ["volatility", state.locale === "en" ? "Volatility" : "波動環境"], ["inflation", state.locale === "en" ? "Inflation" : "通膨環境"], ["business_cycle", state.locale === "en" ? "Business cycle" : "景氣循環"]], (value) => patch({ regime: value }, false))),
      field(`${t("riskFree")} (%)`, input("number", state.riskFreeRate, (value) => patch({ riskFreeRate: number(value) }, false), { step: "0.1" })),
    ]),
  ])));
  return layout;
}
