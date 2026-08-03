from pathlib import Path


root = Path(__file__).resolve().parents[1]
composite_path = root / "public/scan-composite-score.js"
text = composite_path.read_text(encoding="utf-8")

old_state = '''let backtestDialog = null;
let integratedBacktestButton = null;
let integratedPortfolioRows = [];
const baseFetch = window.fetch.bind(window);
'''
new_state = '''let backtestDialog = null;
let integratedBacktestButton = null;
let integratedPortfolioRows = [];
let integratedPortfolioSourceJobId = null;
const baseFetch = window.fetch.bind(window);
'''
if old_state in text:
    text = text.replace(old_state, new_state, 1)
elif "let integratedPortfolioSourceJobId = null;" not in text:
    raise SystemExit("Unable to add portfolio source job state")

old_rows = '''function savedPortfolioRows() {
  return integratedPortfolioRows;
}

function savePortfolioRows(rows) {
  integratedPortfolioRows = Array.isArray(rows) ? rows : [];
}
'''
new_rows = '''function savedPortfolioRows() {
  const currentJobId = readScanJob()?.id || null;
  if (integratedPortfolioSourceJobId !== currentJobId) {
    integratedPortfolioRows = [];
    integratedPortfolioSourceJobId = null;
  }
  return integratedPortfolioRows;
}

function savePortfolioRows(rows) {
  integratedPortfolioRows = Array.isArray(rows) ? rows : [];
  integratedPortfolioSourceJobId = readScanJob()?.id || null;
}
'''
if old_rows in text:
    text = text.replace(old_rows, new_rows, 1)
elif "integratedPortfolioSourceJobId !== currentJobId" not in text:
    raise SystemExit("Unable to scope portfolio rows to the active scan job")

old_writer = '''function writeJson(storage, key, value) {
  try {
    storage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.warn(`Unable to persist ${key}`, error);
  }
}

'''
if old_writer in text:
    text = text.replace(old_writer, "", 1)

composite_path.write_text(text, encoding="utf-8")

test_path = root / "tests/e2e/integrated_performance_list.spec.mjs"
test_text = test_path.read_text(encoding="utf-8")
old_assertion = '''  await expect(portfolioRow).toContainText("95.00%");
  await expect(portfolioRow).toContainText("950");
});
'''
new_assertion = '''  await expect(portfolioRow).toContainText("95.00%");
  await expect(portfolioRow).toContainText("950");

  await page.getByRole("button", { name: "開始集體回測" }).click();
  await expect(portfolioRow).toHaveCount(0);
});
'''
if old_assertion in test_text:
    test_text = test_text.replace(old_assertion, new_assertion, 1)
elif "await expect(portfolioRow).toHaveCount(0);" not in test_text:
    raise SystemExit("Unable to add stale portfolio row regression guard")
test_path.write_text(test_text, encoding="utf-8")
