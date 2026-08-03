# PR 2：Portfolio Ledger 與完整指標契約

本階段建立 `backteststock` 自有、framework-neutral 的投資組合帳本與指標核心。它只消費 PR 1 的每日 TWD total／price／distribution return components，不呼叫舊 `portfolio-backtest-api.vercel.app`，也不新增第二套 Yahoo 或 FX 下載器。

## 版本

- `PORTFOLIO_LEDGER_CONTRACT_VERSION = portfolio-ledger-twd-2026-08-04.1`
- `PORTFOLIO_METRIC_CONTEXT_VERSION = portfolio-metrics-twd-2026-08-04.1`
- `PORTFOLIO_SERVICE_CONTRACT_VERSION = portfolio-service-twd-2026-08-04.1`

## 每日事件順序

每個估值區間固定依序執行：

1. 期初外部現金流。
2. 價格報酬與現金配發。
3. 借款利息。
4. 期末外部現金流。
5. 期末定期或偏離門檻再平衡與交易成本。
6. 維持保證金檢查與必要的強制平倉。
7. 寫入每日 equity、cash、debt、gross exposure、allocation 與事件稽核。

期初現金流納入當日報酬分母；期末現金流由當日報酬分子扣除，因此外部投入或提領不會被誤認為投資績效。

## 配息政策

- 再投入：資產套用 TWD total return，配發收入另保留為稽核數據，不重複加到現金。
- 保留現金：資產套用 TWD price return，並將 TWD distribution return 形成的現金加入 cash。
- 在配發當日，兩種政策的總權益必須相同；其後才因現金是否參與市場報酬而分歧。

## 再平衡與成本

- 支援 none、monthly、quarterly、semiannual、annual。
- 定期再平衡在已完成期間的最後估值日收盤執行，避免在回測最後一天建立沒有後續經濟意義的交易。
- 偏離門檻以目前資產權重和目標權重的最大絕對差判定，可獨立觸發。
- 交易成本以成交名目金額乘以 basis points 計算，直接降低權益並分開報告。

## 槓桿

- Fixed ratio：外部投入、提領與再平衡會同步維持目標 gross exposure 與 debt ratio。
- Fixed debt：債務本金保持固定，再平衡以 `equity + fixed debt` 建立資產曝險。
- 借款利息按 365.2425 日逐日計提。
- 維持保證金不足時建立 `margin_liquidation` 稽核事件並清算，不將正常模擬結果當成 API 錯誤。

## 指標

所有核心指標由同一 `PortfolioMetricReport` 產生：

- Total Return、CAGR、Volatility、Sharpe、Sortino、Maximum Drawdown、Calmar。
- Beta、Jensen Alpha、Benchmark Correlation；Benchmark 不可用時只留空，不抹除主結果。
- XIRR 回傳 `unique`、`multiple` 或 `no_solution`，多重解時不任選一個數值。
- VaR／CVaR 明示為 95% historical simulation、daily horizon。
- 前五大回撤事件包含 peak、trough、recovery、depth、duration 及是否已復原。
- 年度與月度報酬包含實際起訖日及 `partial` 標記。

## 部分成功

`PortfolioLedgerService` 會保留成功的兄弟投組：

- 個別股票缺資料，只讓依賴該股票的投組失敗。
- Benchmark 缺資料，只使 Beta／Alpha／Correlation 缺值。
- 單一投組的模型或日曆錯誤，不抹除其他投組結果。

## 正式功能影響

此階段仍未切換公開 API 或目前彈出式介面。PR 3 將以此核心建立自有 Portfolio v3 API；PR 4 才建立 `/portfolio/` 全頁式應用。現有 Scanner、一般回測、Optimizer 與舊 Portfolio Lab runtime 路徑在本階段保持相容。
