from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise SystemExit(f"Unable to patch {description}")


def split_score_core() -> None:
    formula_path = PUBLIC / "scan-score-formulas.js"
    core_path = PUBLIC / "scan-score-core.js"
    formula_text = formula_path.read_text(encoding="utf-8")
    marker = "export const SCORE_FORMULAS = Object.freeze(["
    if marker in formula_text:
        prefix, suffix = formula_text.split(marker, 1)
        core_path.write_text(marker + suffix, encoding="utf-8")
        formula_path.write_text(
            prefix.rstrip()
            + '\n\nexport * from "./scan-score-core.js?v=20260803.1";\n',
            encoding="utf-8",
        )
    elif not core_path.exists():
        raise SystemExit("Unable to locate score formula split marker")


def enrich_coverage_with_scores() -> None:
    path = PUBLIC / "scan-coverage.js"
    text = path.read_text(encoding="utf-8")
    core_import = '''import {
  SCORE_FORMULAS,
  buildScoreMatrix,
  scoreRecordFor,
} from "./scan-score-core.js?v=20260803.1";

'''
    if "./scan-score-core.js?v=20260803.1" not in text:
        text = core_import + text

    old = '''  const settled = settledSource.map((item) => ({
    ...item,
    benchmark_calendar_coverage: item?.benchmark_calendar_coverage ?? item?.data_coverage ?? null,
    data_coverage: relativeScanCoverage(item, maximumTradingDays),
    coverage_reference_trading_days: maximumTradingDays || null,
    coverage_definition_version: SCAN_COVERAGE_DEFINITION_VERSION,
  }));

  return {'''
    new = '''  const prepared = settledSource.map((item) => ({
    ...item,
    benchmark_calendar_coverage: item?.benchmark_calendar_coverage ?? item?.data_coverage ?? null,
    data_coverage: relativeScanCoverage(item, maximumTradingDays),
    coverage_reference_trading_days: maximumTradingDays || null,
    coverage_definition_version: SCAN_COVERAGE_DEFINITION_VERSION,
  }));

  const scoreMatrix = buildScoreMatrix(prepared);
  const settled = prepared.map((item) => {
    const scored = { ...item };
    for (const formula of SCORE_FORMULAS) {
      const record = scoreRecordFor(scoreMatrix, item.ticker, formula.key);
      scored[formula.key] = Number.isFinite(record?.score) ? record.score : null;
      scored[formula.rankKey] = Number.isInteger(record?.rank) ? record.rank : null;
      scored[formula.statusKey] = record?.status || "missing";
    }
    return scored;
  });

  return {'''
    text = replace_once(text, old, new, "coverage score enrichment")
    path.write_text(text, encoding="utf-8")


def align_module_versions() -> None:
    for path in PUBLIC.glob("*.js"):
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "scan-coverage.js?v=20260803.1",
            "scan-coverage.js?v=20260803.2",
        )
        text = text.replace(
            "scan-score-formulas.js?v=20260803.3",
            "scan-score-formulas.js?v=20260803.4",
        )
        path.write_text(text, encoding="utf-8")

    index_path = PUBLIC / "index.html"
    index_text = index_path.read_text(encoding="utf-8")
    index_text = index_text.replace(
        "/app.js?v=20260803.6",
        "/app.js?v=20260803.7",
    ).replace(
        "/scan-composite-score.js?v=20260803.4",
        "/scan-composite-score.js?v=20260803.5",
    )
    index_path.write_text(index_text, encoding="utf-8")

    optimizer_path = PUBLIC / "optimizer.html"
    optimizer_text = optimizer_path.read_text(encoding="utf-8")
    optimizer_text = optimizer_text.replace(
        "/exhaustive-optimizer.js?v=20260803.4",
        "/exhaustive-optimizer.js?v=20260803.5",
    )
    optimizer_path.write_text(optimizer_text, encoding="utf-8")


def validate_integrated_selection() -> None:
    path = PUBLIC / "scan-composite-score.js"
    text = path.read_text(encoding="utf-8")
    old = '''function selectedTickers() {
  const selection = readJson(localStorage, MANUAL_SELECTION_KEY, null);
  return Array.isArray(selection?.tickers)
    ? selection.tickers.map(normalizeScoreTicker).filter(Boolean)
    : [];
}'''
    new = '''function selectedTickers(stats = currentCoverageStats()) {
  const job = readScanJob();
  const selection = readJson(localStorage, MANUAL_SELECTION_KEY, null);
  if (
    !job?.id
    || selection?.sourceJobId !== job.id
    || !Array.isArray(selection?.tickers)
  ) {
    return [];
  }

  const benchmark = normalizeScoreTicker(job.payload?.benchmark);
  const selectable = new Set(
    stats.shown
      .map((item) => normalizeScoreTicker(item?.ticker))
      .filter((ticker) => ticker && ticker !== benchmark),
  );
  return [...new Set(
    selection.tickers
      .map(normalizeScoreTicker)
      .filter((ticker) => selectable.has(ticker)),
  )];
}'''
    text = replace_once(text, old, new, "integrated selection validation")
    path.write_text(text, encoding="utf-8")


def add_coverage_sort_guard() -> None:
    path = ROOT / "tests/test_scan_coverage.mjs"
    text = path.read_text(encoding="utf-8")
    if "coverage derivation exposes sortable score fields" in text:
        return
    text += '''

test("coverage derivation exposes sortable score fields", () => {
  const rows = [
    {
      ticker: "HIGH",
      status: "ok",
      trading_days: 1000,
      sortino_ratio: 2,
      cagr: 0.25,
      beta: 0.8,
      mdd: -0.15,
    },
    {
      ticker: "LOW",
      status: "ok",
      trading_days: 950,
      sortino_ratio: 1,
      cagr: 0.10,
      beta: 1.1,
      mdd: -0.25,
    },
  ];

  const derived = deriveScanCoverage(rows);
  const high = derived.settled.find((item) => item.ticker === "HIGH");
  const low = derived.settled.find((item) => item.ticker === "LOW");
  assert.ok(Number.isFinite(high.sortino_growth_beta_score));
  assert.ok(Number.isFinite(high.sortino_growth_beta_quarter_score));
  assert.ok(Number.isFinite(high.sortino_growth_beta_mdd_score));
  assert.ok(high.sortino_growth_beta_score > low.sortino_growth_beta_score);
  assert.equal(high.sortino_growth_beta_rank, 1);
  assert.equal(low.sortino_growth_beta_rank, 2);
});
'''
    path.write_text(text, encoding="utf-8")


def add_integrated_selection_guards() -> None:
    path = ROOT / "tests/e2e/integrated_performance_list.spec.mjs"
    text = path.read_text(encoding="utf-8")
    if "ignores a stale optimizer selection from another scan job" in text:
        return
    text += '''

test("integrated backtest ignores a stale optimizer selection from another scan job", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-scan-job-v3", JSON.stringify({
      version: 3,
      id: "current-scan",
      status: "completed",
      payload: {
        tickers: ["AAA"],
        benchmark: "SPY",
        startDate: "2022-01-01",
        endDate: "2025-12-31",
      },
      pending: [],
      results: [{
        ticker: "AAA",
        status: "ok",
        retryable: false,
        trading_days: 1000,
        metric_definition_version: "2026-08-01.2",
      }],
    }));
    localStorage.setItem("backteststock-optimizer-manual-selection-v2", JSON.stringify({
      version: 2,
      sourceJobId: "old-scan",
      coverageThresholdPercent: 90,
      tickers: ["AAA"],
    }));
  });
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));

  await page.goto("/");
  await expect(page.locator("#scanner-panel")).toBeVisible();
  await expect(page.locator("#open-integrated-backtest")).toBeDisabled();
});

test("integrated backtest rejects a saved ticker below the current coverage threshold", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("backteststock-scan-job-v3", JSON.stringify({
      version: 3,
      id: "current-scan",
      status: "completed",
      payload: {
        tickers: ["AAA", "LOW"],
        benchmark: "SPY",
        startDate: "2022-01-01",
        endDate: "2025-12-31",
      },
      pending: [],
      results: [
        {
          ticker: "AAA",
          status: "ok",
          retryable: false,
          trading_days: 1000,
          metric_definition_version: "2026-08-01.2",
        },
        {
          ticker: "LOW",
          status: "ok",
          retryable: false,
          trading_days: 800,
          metric_definition_version: "2026-08-01.2",
        },
      ],
    }));
    localStorage.setItem("backteststock-optimizer-manual-selection-v2", JSON.stringify({
      version: 2,
      sourceJobId: "current-scan",
      coverageThresholdPercent: 90,
      tickers: ["LOW"],
    }));
  });
  await page.route("**/api/health", (route) => fulfillJson(route, { status: "ok" }));
  await page.route("**/api/all-tickers", (route) => fulfillJson(route, []));
  await page.route("**/api/v2/universes", (route) => fulfillJson(route, { data: [] }));

  await page.goto("/");
  await expect(page.locator("#scanner-panel")).toBeVisible();
  await expect(page.locator("#open-integrated-backtest")).toBeDisabled();
});
'''
    path.write_text(text, encoding="utf-8")


def harden_release_backup_lookup() -> None:
    path = ROOT / ".github/workflows/release-backups.yml"
    text = path.read_text(encoding="utf-8")
    old = '''          pre_sha="$(git rev-parse "${POST_SHA}^1")"
          pre_tag="backup-pre-pr${PR_NUMBER}-${pre_sha:0:12}"
          post_tag="backup-post-pr${PR_NUMBER}-${POST_SHA:0:12}"

          gh release view "$pre_tag" >/dev/null
          git fetch --force origin "refs/tags/$pre_tag:refs/tags/$pre_tag"
          resolved_pre_sha="$(git rev-list -n 1 "$pre_tag")"
          if [ "$resolved_pre_sha" != "$pre_sha" ]; then
            echo "Pre-merge backup tag points to $resolved_pre_sha instead of $pre_sha." >&2
            exit 1
          fi
'''
    new = '''          mapfile -t pre_tags < <(
            gh api --paginate "repos/${GITHUB_REPOSITORY}/releases?per_page=100" \\
              --jq '.[].tag_name' \\
              | grep -E "^backup-pre-pr${PR_NUMBER}-[0-9a-f]{12}$" \\
              || true
          )

          pre_tag=""
          pre_sha=""
          best_distance=""
          for candidate_tag in "${pre_tags[@]}"; do
            git fetch --force origin "refs/tags/${candidate_tag}:refs/tags/${candidate_tag}"
            candidate_sha="$(git rev-list -n 1 "$candidate_tag")"
            if ! git merge-base --is-ancestor "$candidate_sha" "$POST_SHA"; then
              continue
            fi
            distance="$(git rev-list --count "${candidate_sha}..${POST_SHA}")"
            if [ -z "$best_distance" ] || [ "$distance" -lt "$best_distance" ]; then
              pre_tag="$candidate_tag"
              pre_sha="$candidate_sha"
              best_distance="$distance"
            fi
          done

          if [ -z "$pre_tag" ]; then
            echo "No verified pre-merge backup release is an ancestor of $POST_SHA." >&2
            exit 1
          fi
          expected_pre_tag="backup-pre-pr${PR_NUMBER}-${pre_sha:0:12}"
          if [ "$pre_tag" != "$expected_pre_tag" ]; then
            echo "Pre-merge backup tag $pre_tag does not match target $pre_sha." >&2
            exit 1
          fi
          gh release view "$pre_tag" >/dev/null
          resolved_pre_sha="$(git rev-list -n 1 "$pre_tag")"
          if [ "$resolved_pre_sha" != "$pre_sha" ]; then
            echo "Pre-merge backup tag points to $resolved_pre_sha instead of $pre_sha." >&2
            exit 1
          fi

          post_tag="backup-post-pr${PR_NUMBER}-${POST_SHA:0:12}"
'''
    text = replace_once(text, old, new, "release backup discovery")
    path.write_text(text, encoding="utf-8")


def reject_mixed_cache_versions() -> None:
    remaining: list[str] = []
    for path in PUBLIC.rglob("*"):
        if path.suffix not in {".js", ".html"}:
            continue
        text = path.read_text(encoding="utf-8")
        if "scan-coverage.js?v=20260803.1" in text:
            remaining.append(f"{path}: old coverage URL")
        if "scan-score-formulas.js?v=20260803.3" in text:
            remaining.append(f"{path}: old score URL")
    if remaining:
        raise SystemExit("\n".join(remaining))


def main() -> None:
    split_score_core()
    enrich_coverage_with_scores()
    align_module_versions()
    validate_integrated_selection()
    add_coverage_sort_guard()
    add_integrated_selection_guards()
    harden_release_backup_lookup()
    reject_mixed_cache_versions()


if __name__ == "__main__":
    main()
