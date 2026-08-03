const DIALOG_SELECTOR = "#integrated-backtest-dialog";
const ENHANCED_FLAG = "originalLayoutEnhanced";

function element(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text) node.textContent = options.text;
  if (options.id) node.id = options.id;
  for (const [name, value] of Object.entries(options.attributes || {})) {
    node.setAttribute(name, value);
  }
  children.forEach((child) => child && node.append(child));
  return node;
}

function fact(value, label) {
  return element("div", { className: "backtest-workspace-fact" }, [
    element("strong", { text: value }),
    element("span", { text: label }),
  ]);
}

function buildAppBar(dialog) {
  const brand = element("div", { className: "backtest-workspace-brand" }, [
    element("span", {
      className: "backtest-workspace-brand-mark",
      text: "B",
      attributes: { "aria-hidden": "true" },
    }),
    element("div", { className: "backtest-workspace-brand-copy" }, [
      element("strong", { text: "Portfolio Backtest" }),
      element("span", { text: "多市場每日 TWD 投資組合研究" }),
    ]),
  ]);

  const actions = element("div", { className: "backtest-workspace-appbar-actions" });
  for (const id of ["save-config", "export-config"]) {
    const button = document.querySelector(`#${id}`);
    if (!button) continue;
    button.classList.add("backtest-appbar-action");
    actions.append(button);
  }

  const existingClose = dialog.querySelector(".integrated-backtest-dialog-toolbar button");
  const close = existingClose || element("button", {
    className: "button ghost",
    text: "關閉",
    attributes: { type: "button" },
  });
  close.classList.add("backtest-close-button");
  close.textContent = "關閉";
  close.setAttribute("aria-label", "關閉並返回績效列表");
  if (!existingClose) close.addEventListener("click", () => dialog.close());
  actions.append(close);

  return element("header", { className: "backtest-workspace-appbar" }, [brand, actions]);
}

function buildHero() {
  const copy = element("div", { className: "backtest-workspace-hero-copy" }, [
    element("span", { className: "backtest-section-kicker", text: "Portfolio Performance" }),
    element("h2", { id: "backtest-workspace-title", text: "投資組合回測與風險比較" }),
    element("p", {
      text: "沿用原版回測介面的資訊層級，集中設定期間、基準、再平衡與多組資產配置，再於同一工作區檢視績效曲線及風險指標。",
    }),
  ]);
  const facts = element("div", {
    className: "backtest-workspace-facts",
    attributes: { "aria-label": "投資組合回測能力" },
  }, [
    fact("5", "Portfolios"),
    fact("20", "Assets each"),
    fact("TWD · Daily", "Global valuation"),
  ]);
  return element("section", { className: "backtest-workspace-hero" }, [copy, facts]);
}

function sectionHeading(step, title, description) {
  return element("div", { className: "backtest-settings-heading-copy" }, [
    element("span", { className: "backtest-step-number", text: step }),
    element("div", {}, [
      element("h3", { text: title }),
      element("p", { text: description }),
    ]),
  ]);
}

function enhanceConfiguration(panel) {
  const nativeHeading = panel.querySelector(":scope > .section-heading");
  if (nativeHeading) {
    nativeHeading.querySelector(".eyebrow")?.replaceChildren(document.createTextNode("MODEL CONFIGURATION"));
    nativeHeading.querySelector("h2")?.replaceChildren(document.createTextNode("投資組合模型設定"));
    if (!nativeHeading.querySelector(".backtest-research-badge")) {
      nativeHeading.append(element("span", {
        className: "backtest-research-badge",
        text: "✓ 個人研究工具",
      }));
    }
  }

  const form = panel.querySelector("#backtest-form");
  const controls = form?.querySelector(":scope > .control-grid");
  if (controls && !controls.querySelector(".backtest-settings-heading")) {
    controls.classList.add("backtest-settings-card");
    controls.prepend(element("div", { className: "backtest-settings-heading" }, [
      sectionHeading("01", "回測基本設定", "設定投資金額、資料期間、再平衡方式與比較基準。"),
    ]));
  }

  const list = form?.querySelector("#portfolio-list");
  if (list && !list.closest(".backtest-assets-section")) {
    const section = element("section", { className: "backtest-assets-section" });
    const headingCopy = sectionHeading("02", "投資組合與資產配置", "可同時比較多組投資組合；每組有效權重須合計為 100%。");
    headingCopy.classList.remove("backtest-settings-heading-copy");
    headingCopy.classList.add("backtest-assets-heading-copy");

    const actions = element("div", { className: "backtest-assets-actions" });
    const addPortfolio = document.querySelector("#add-portfolio");
    if (addPortfolio) {
      addPortfolio.classList.add("backtest-add-portfolio");
      addPortfolio.textContent = "＋ 新增投資組合";
      actions.append(addPortfolio);
    }
    const heading = element("div", { className: "backtest-assets-heading" }, [headingCopy, actions]);
    list.before(section);
    section.append(heading, list);
  }

  const runBar = form?.querySelector(":scope > .submit-row");
  runBar?.classList.add("backtest-run-bar");
}

function enhanceResults(panel) {
  const results = panel.querySelector("#backtest-results");
  if (!results) return;
  results.classList.add("backtest-results-shell");
  if (!results.querySelector(".backtest-methodology-note")) {
    const note = element("p", {
      className: "backtest-methodology-note",
      text: "所有金額以 TWD 逐日估值；圖表尺度只影響顯示，不改變底層報酬、波動率、回撤與風險指標計算。",
    });
    results.querySelector(".result-header")?.insertAdjacentElement("afterend", note);
  }
}

function synchronizeOpenState(dialog) {
  document.body.classList.toggle("backtest-workspace-open", dialog.open);
}

function enhanceDialog(dialog) {
  if (!dialog || dialog.dataset[ENHANCED_FLAG] === "true") return;
  const shell = dialog.querySelector(".integrated-backtest-shell");
  const panel = dialog.querySelector("#backtest-panel");
  if (!shell || !panel) return;

  dialog.dataset[ENHANCED_FLAG] = "true";
  dialog.classList.add("backtest-workspace-dialog");
  dialog.setAttribute("aria-labelledby", "backtest-workspace-title");

  const appBar = buildAppBar(dialog);
  const hero = buildHero();
  shell.insertBefore(appBar, shell.firstChild);
  panel.before(hero);

  enhanceConfiguration(panel);
  enhanceResults(panel);
  synchronizeOpenState(dialog);

  const openObserver = new MutationObserver(() => synchronizeOpenState(dialog));
  openObserver.observe(dialog, { attributes: true, attributeFilter: ["open"] });
  dialog.addEventListener("close", () => synchronizeOpenState(dialog));
  dialog.addEventListener("cancel", () => synchronizeOpenState(dialog));
}

function initialize() {
  const run = () => {
    const dialog = document.querySelector(DIALOG_SELECTOR);
    if (dialog) {
      enhanceDialog(dialog);
      return true;
    }
    return false;
  };

  if (run()) return;
  const observer = new MutationObserver(() => {
    if (run()) observer.disconnect();
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialize, { once: true });
} else {
  initialize();
}
