from pathlib import Path


path = Path(__file__).resolve().parents[1] / "public/scan-composite-score.js"
text = path.read_text(encoding="utf-8")

old_constants = '''const MANUAL_SELECTION_KEY = "backteststock-optimizer-manual-selection-v2";
const PORTFOLIO_RESULT_KEY = "backteststock-integrated-portfolio-results-v1";
const BACKTEST_STATE_KEY = "backteststock-state-v2";
const MAX_SAVED_PORTFOLIO_ROWS = 20;
'''
new_constants = '''const MANUAL_SELECTION_KEY = "backteststock-optimizer-manual-selection-v2";
'''
if old_constants in text:
    text = text.replace(old_constants, new_constants, 1)
elif "PORTFOLIO_RESULT_KEY" in text:
    raise SystemExit("Unable to remove persistent portfolio result constants")

old_state = '''let backtestDialog = null;
let integratedBacktestButton = null;
const baseFetch = window.fetch.bind(window);
'''
new_state = '''let backtestDialog = null;
let integratedBacktestButton = null;
let integratedPortfolioRows = [];
const baseFetch = window.fetch.bind(window);
'''
if old_state in text:
    text = text.replace(old_state, new_state, 1)
elif "let integratedPortfolioRows = [];" not in text:
    raise SystemExit("Unable to add in-memory portfolio result state")

old_storage = '''function savedPortfolioRows() {
  const rows = readJson(localStorage, PORTFOLIO_RESULT_KEY, []);
  return Array.isArray(rows) ? rows : [];
}

function savePortfolioRows(rows) {
  writeJson(localStorage, PORTFOLIO_RESULT_KEY, rows.slice(0, MAX_SAVED_PORTFOLIO_ROWS));
}
'''
new_storage = '''function savedPortfolioRows() {
  return integratedPortfolioRows;
}

function savePortfolioRows(rows) {
  integratedPortfolioRows = Array.isArray(rows) ? rows : [];
}
'''
if old_storage in text:
    text = text.replace(old_storage, new_storage, 1)
elif "return integratedPortfolioRows;" not in text:
    raise SystemExit("Unable to replace portfolio result storage")

old_merge = '''  const existing = savedPortfolioRows();
  const byName = new Map(existing.map((item) => [item.name, item]));
  rows.forEach((item) => byName.set(item.name, item));
  savePortfolioRows([...byName.values()].sort((a, b) => (
    String(b.captured_at).localeCompare(String(a.captured_at))
  )));
'''
new_merge = '''  savePortfolioRows(rows);
'''
if old_merge in text:
    text = text.replace(old_merge, new_merge, 1)
elif "savePortfolioRows(rows);" not in text:
    raise SystemExit("Unable to make integrated rows correspond to latest backtest")

path.write_text(text, encoding="utf-8")
