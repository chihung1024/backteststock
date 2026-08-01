from pathlib import Path


def replace_once(path, old, new):
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


optimizer_path = Path("api/optimizer.py")
text = optimizer_path.read_text(encoding="utf-8")
start = text.index("def _download_common_prices(")
end = text.index("\n\n@app.route(\"/api/optimizer/calendar\"", start)
replacement = '''def _download_common_prices(
    tickers: list[str],
    start_text: str,
    end_text: str,
    reference_ticker: str | None = None,
):
    prices, failures = market_data.download_data_reliably(
        tickers,
        start_text,
        end_text,
        attempts=legacy.MARKET_DATA_ATTEMPTS,
        backoff_seconds=legacy.MARKET_DATA_BACKOFF_SECONDS,
        timeout_seconds=legacy.MARKET_DATA_TIMEOUT_SECONDS,
        download_threads=legacy.MARKET_DATA_DOWNLOAD_THREADS,
        batch_size=legacy.MARKET_DATA_BATCH_SIZE,
    )
    failed = [
        ticker
        for ticker in tickers
        if ticker in failures
        or ticker not in prices.columns
        or prices[ticker].dropna().empty
    ]
    if failed:
        raise legacy.DataSourceError(
            "行情資料尚未完整取得：" + ", ".join(sorted(failed))
        )

    reference = reference_ticker or tickers[0]
    if reference not in prices.columns or prices[reference].dropna().empty:
        raise legacy.DataSourceError("比較基準行情無法建立共同交易日曆。")
    reference_index = pd.DatetimeIndex(prices[reference].dropna().index)
    if len(reference_index) < 60:
        raise legacy.ValidationError("比較基準共同交易日不足 60 日。")
    availability_masks = {
        ticker: prices[ticker].reindex(reference_index).notna().to_numpy(dtype=bool)
        for ticker in tickers
    }
    common = prices[tickers].reindex(reference_index).dropna().astype(float)
    if len(common) < 60:
        raise legacy.ValidationError("沒有足夠共同交易日建立最佳化資料。")
    audits = dict(prices.attrs.get("corporate_action_audits", {}))
    for ticker in tickers:
        audits.setdefault(ticker, audit_from_series(prices[ticker]))
    common.attrs["optimizer_reference_index"] = reference_index
    common.attrs["optimizer_availability_masks"] = availability_masks
    return common, audits


def _strict_period_coverage(
    common: pd.DataFrame,
    candidate_tickers: list[str],
    benchmark: str,
    training_end: pd.Timestamp,
    minimum_coverage: float = 0.98,
) -> dict:
    reference_index = common.attrs.get("optimizer_reference_index")
    availability_masks = common.attrs.get("optimizer_availability_masks")
    if reference_index is None or not isinstance(availability_masks, dict):
        reference_index = pd.DatetimeIndex(common.index)
        availability_masks = {
            ticker: np.ones(len(reference_index), dtype=bool)
            for ticker in [*candidate_tickers, benchmark]
        }
    reference_index = pd.DatetimeIndex(reference_index)
    training_selector = np.asarray(reference_index <= training_end, dtype=bool)
    validation_selector = ~training_selector
    if training_selector.sum() < 30 or validation_selector.sum() < 20:
        raise legacy.ValidationError(
            "比較基準切割後的訓練或樣本外交易日不足。"
        )

    diagnostics = {}
    failures = []
    required = [*candidate_tickers, benchmark]
    for ticker in required:
        mask = np.asarray(
            availability_masks.get(ticker, np.zeros(len(reference_index), dtype=bool)),
            dtype=bool,
        )
        if len(mask) != len(reference_index):
            raise legacy.ValidationError(f"行情覆蓋稽核長度不一致：{ticker}")
        training_coverage = float(mask[training_selector].mean())
        validation_coverage = float(mask[validation_selector].mean())
        overall_coverage = float(mask.mean())
        diagnostics[ticker] = {
            "overall": overall_coverage,
            "training": training_coverage,
            "validation": validation_coverage,
            "missing_training_days": int((~mask[training_selector]).sum()),
            "missing_validation_days": int((~mask[validation_selector]).sum()),
        }
        if ticker != benchmark and (
            training_coverage < minimum_coverage
            or validation_coverage < minimum_coverage
        ):
            failures.append(
                f"{ticker}(訓練 {training_coverage:.2%}、樣本外 {validation_coverage:.2%})"
            )

    common_mask = np.logical_and.reduce(
        [np.asarray(availability_masks[ticker], dtype=bool) for ticker in required]
    )
    global_training = float(common_mask[training_selector].mean())
    global_validation = float(common_mask[validation_selector].mean())
    diagnostics["_global_complete_case"] = {
        "training": global_training,
        "validation": global_validation,
        "minimum_required": minimum_coverage,
    }
    if global_training < minimum_coverage or global_validation < minimum_coverage:
        failures.append(
            "全體共同交易日"
            f"(訓練 {global_training:.2%}、樣本外 {global_validation:.2%})"
        )

    common_positions = reference_index.get_indexer(common.index)
    if (
        len(common_positions) == 0
        or common_positions[0] < 0
        or common_positions[-1] < 0
        or common_positions[0] > 5
        or common_positions[-1] < len(reference_index) - 6
    ):
        failures.append("共同期間起訖與比較基準相差超過 5 個交易日")
    if failures:
        raise legacy.ValidationError(
            "最佳化不得靜默縮短訓練或樣本外期間；行情覆蓋不足："
            + "；".join(failures)
        )
    return diagnostics
'''
text = text[:start] + replacement + text[end:]
text = text.replace(
    '''        common, audits = _download_common_prices(
            [benchmark],
            start_date.strftime("%Y-%m-%d"),
            end_exclusive.strftime("%Y-%m-%d"),
        )''',
    '''        common, audits = _download_common_prices(
            [benchmark],
            start_date.strftime("%Y-%m-%d"),
            end_exclusive.strftime("%Y-%m-%d"),
            benchmark,
        )''',
    1,
)
text = text.replace(
    '''        common, audits = _download_common_prices(
            required,
            start_date.strftime("%Y-%m-%d"),
            end_exclusive.strftime("%Y-%m-%d"),
        )''',
    '''        common, audits = _download_common_prices(
            required,
            start_date.strftime("%Y-%m-%d"),
            end_exclusive.strftime("%Y-%m-%d"),
            benchmark,
        )''',
    1,
)
text = text.replace(
    '''        review = sorted(
            ticker
            for ticker in required
            if audits[ticker].get("status") != "verified_standard_actions"
        )''',
    '''        coverage_audit = _strict_period_coverage(
            common,
            candidates,
            benchmark,
            pd.Timestamp(split["trainingEnd"]),
        )

        review = sorted(
            ticker
            for ticker in required
            if audits[ticker].get("status") != "verified_standard_actions"
        )''',
    1,
)
text = text.replace(
    '''            "commonCalendarPolicy": "global_complete_case_candidates_and_benchmark",
            "candidateSelection": data.get("candidateSelection") or {},''',
    '''            "commonCalendarPolicy": "global_complete_case_candidates_and_benchmark",
            "dataCoverageAudit": coverage_audit,
            "minimumPeriodCoverage": 0.98,
            "candidateSelection": data.get("candidateSelection") or {},''',
    1,
)
text = text.replace(
    '''                    "corporateActionStatus": {
                        ticker: audits[ticker].get("status") for ticker in required
                    },
                    "optimizerAlgorithmVersion": OPTIMIZER_ALGORITHM_VERSION,''',
    '''                    "corporateActionStatus": {
                        ticker: audits[ticker].get("status") for ticker in required
                    },
                    "dataCoverageAudit": coverage_audit,
                    "optimizerAlgorithmVersion": OPTIMIZER_ALGORITHM_VERSION,''',
    1,
)
optimizer_path.write_text(text, encoding="utf-8")

ui_path = Path("public/optimizer.js")
ui = ui_path.read_text(encoding="utf-8")
ui = ui.replace(
    '''function rankingValue(row, field) {
  const rawField = field === "mdd_abs" ? "mdd" : field === "beta_abs" ? "beta" : field;
  const numeric = Number(row?.[rawField]);
  if (!Number.isFinite(numeric)) return null;''',
    '''function rankingValue(row, field) {
  const rawField = field === "mdd_abs" ? "mdd" : field === "beta_abs" ? "beta" : field;
  const rawValue = row?.[rawField];
  if (rawValue == null || rawValue === "") return null;
  const numeric = Number(rawValue);
  if (!Number.isFinite(numeric)) return null;''',
    1,
)
ui = ui.replace(
    '''    if (row.status !== "ok" || row.error) reasons.push(row.error || "回測失敗");
    if (Number(row.data_coverage) < 0.98) reasons.push("資料覆蓋率低於 98%");''',
    '''    if (row.status !== "ok" || row.error) reasons.push(row.error || "回測失敗");
    const coverage = Number(row.data_coverage);
    if (!Number.isFinite(coverage) || coverage < 0.98) {
      reasons.push("資料覆蓋率缺漏或低於 98%");
    }''',
    1,
)
ui = ui.replace(
    '''function formatMetric(value, type = "number") {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";''',
    '''function formatMetric(value, type = "number") {
  if (value == null || value === "") return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";''',
    1,
)
ui = ui.replace(
    '''  let metadata = null;
  const chunks = [];''',
    '''  let metadata = null;
  const verificationBatches = [];
  const chunks = [];''',
    1,
)
ui = ui.replace(
    '''    results.push(...response.results);
    metadata = response.metadata;''',
    '''    results.push(...response.results);
    metadata = response.metadata;
    verificationBatches.push({
      batch: index + 1,
      requested: chunks[index].length,
      returned: response.results.length,
      backendVerifiedCombinations: response.metadata?.verified_combinations ?? null,
    });''',
    1,
)
ui = ui.replace(
    '''  return { results, metadata };
}''',
    '''  return {
    results,
    metadata: {
      ...(metadata || {}),
      verified_combinations: results.length,
      verification_batch_count: chunks.length,
      verification_batches: verificationBatches,
    },
  };
}''',
    1,
)
ui = ui.replace(
    '''function metricObjectiveValue(result, objective, period = "training") {
  const row = result[period] || {};
  switch (objective) {
    case "sortino_ratio": return Number(row.sortino_ratio);
    case "cagr": return Number(row.cagr);
    case "mdd_abs": return -Math.abs(Number(row.mdd));
    case "beta_abs": return -Math.abs(Number(row.beta));
    case "alpha": return Number(row.alpha);
    default: return Number.NEGATIVE_INFINITY;
  }
}''',
    '''function metricObjectiveValue(result, objective, period = "training") {
  const row = result[period] || {};
  const rawField = objective === "mdd_abs" ? "mdd" : objective === "beta_abs" ? "beta" : objective;
  const rawValue = row[rawField];
  if (rawValue == null || rawValue === "") return Number.NEGATIVE_INFINITY;
  const numeric = Number(rawValue);
  if (!Number.isFinite(numeric)) return Number.NEGATIVE_INFINITY;
  if (objective === "mdd_abs" || objective === "beta_abs") return -Math.abs(numeric);
  return numeric;
}''',
    1,
)
old_compact = '''    results: output.results,
    verificationMetadata: output.verificationMetadata,'''
new_compact = '''    results: output.results.map((row) => ({
      combinationId: row.combinationId,
      mask: row.mask,
      tickers: row.tickers,
      selectionSource: row.selectionSource,
      training: {
        ...row.training,
        rebalanceEvents: undefined,
        unexecutedFinalSignal: undefined,
      },
      validation: {
        ...row.validation,
        rebalanceEvents: undefined,
        unexecutedFinalSignal: undefined,
      },
    })),
    verificationMetadata: output.verificationMetadata,'''
if ui.count(old_compact) != 1:
    raise SystemExit(f"compact result matches={ui.count(old_compact)}")
ui_path.write_text(ui.replace(old_compact, new_compact, 1), encoding="utf-8")

test_path = Path("tests/test_optimizer.py")
tests = test_path.read_text(encoding="utf-8")
tests = tests.replace(
    '''        lambda tickers, _start, _end: (common[tickers], audits),''',
    '''        lambda tickers, _start, _end, _reference=None: (common[tickers], audits),''',
    1,
)
tests += '''\n\ndef test_strict_period_coverage_rejects_silent_validation_truncation():
    tickers = [f"T{index:02d}" for index in range(20)]
    benchmark = "SPY"
    reference = pd.bdate_range("2024-01-02", periods=100)
    common = pd.DataFrame(
        {ticker: np.linspace(100, 120, 70) for ticker in [*tickers, benchmark]},
        index=reference[:70],
    )
    masks = {
        ticker: np.ones(100, dtype=bool) for ticker in [*tickers, benchmark]
    }
    masks["T00"][70:] = False
    common.attrs["optimizer_reference_index"] = reference
    common.attrs["optimizer_availability_masks"] = masks

    with pytest.raises(optimizer.legacy.ValidationError, match="不得靜默縮短"):
        optimizer._strict_period_coverage(
            common,
            tickers,
            benchmark,
            reference[69],
        )


def test_strict_period_coverage_records_training_and_validation_ratios():
    tickers = [f"T{index:02d}" for index in range(20)]
    benchmark = "SPY"
    reference = pd.bdate_range("2024-01-02", periods=100)
    common = pd.DataFrame(
        {ticker: np.linspace(100, 120, 100) for ticker in [*tickers, benchmark]},
        index=reference,
    )
    common.attrs["optimizer_reference_index"] = reference
    common.attrs["optimizer_availability_masks"] = {
        ticker: np.ones(100, dtype=bool) for ticker in [*tickers, benchmark]
    }
    audit = optimizer._strict_period_coverage(
        common,
        tickers,
        benchmark,
        reference[69],
    )
    assert audit["T00"]["training"] == 1.0
    assert audit["T00"]["validation"] == 1.0
    assert audit["_global_complete_case"]["training"] == 1.0
    assert audit["_global_complete_case"]["validation"] == 1.0
'''
test_path.write_text(tests, encoding="utf-8")

playwright = Path("tests/e2e/optimizer.spec.mjs")
e2e = playwright.read_text(encoding="utf-8")
e2e = e2e.replace(
    '''  await expect(page.locator("#optimizer-reproducibility")).toContainText("dataset-hash");''',
    '''  await expect(page.locator("#optimizer-reproducibility")).toContainText("dataset-hash");
  await expect(page.locator("#optimizer-reproducibility")).toContainText(
    '"verified_combinations": 300',
  );''',
    1,
)
playwright.write_text(e2e, encoding="utf-8")

for path in ("docs/PORTFOLIO_OPTIMIZER_MVP.md", "docs/OPTIMIZER_IMPLEMENTATION_STATUS.md"):
    file = Path(path)
    content = file.read_text(encoding="utf-8")
    if path.endswith("PORTFOLIO_OPTIMIZER_MVP.md"):
        content += '''\n## 樣本外資料完整性\n\n候選池仍只依訓練期資訊選擇；準備完整資料快照時，則按 benchmark 交易日曆分別稽核訓練與樣本外覆蓋率。任一候選股或全體 complete-case 在任一期間低於 98%，或共同期間起訖相差超過 5 個交易日，工作直接停止並列出標的，不得透過 `dropna()` 靜默縮短樣本外期間，也不得用樣本外資訊遞補另一檔股票。\n'''
    else:
        content += '''\nThe final implementation rejects silent out-of-sample truncation, treats null metrics as unavailable rather than zero, aggregates all three exact-verification batches to 300, and persists only compact summaries in localStorage while retaining full events in the audit JSON export.\n'''
    file.write_text(content, encoding="utf-8")

Path("scripts/apply_optimizer_correctness_hardening.py").unlink()
