# PR 6：Portfolio runtime 技術斬斷

## 正式路徑

- 前端：`/portfolio/`
- Edge API：`/api/v3/portfolio/*`
- 後端：`backteststock` 自有 `BACKEND_ORIGIN`

正式 Portfolio 流程不再依賴原專案、舊 GitHub Pages 或跨專案 API。

## 已移除

- `/api/portfolio-lab/*` 舊代理及 route allowlist。
- `portfolio-backtest-api.vercel.app` 預設來源。
- 舊 GitHub Pages Origin／Referer 偽裝。
- Dialog loader、舊 Portfolio Lab scripts／CSS 與 capture bridge。
- 舊 Portfolio Lab production smoke 與對應 Worker／E2E 測試。

## 不可回退契約

`tests/test_portfolio_runtime_cutover.mjs` 會掃描正式 runtime 與部署設定，禁止重新引入：

- 舊 Portfolio Lab API 路徑。
- 舊 API 網域。
- 舊 GitHub Pages 路徑與 impersonation。
- 舊環境變數。
- Dialog 識別字與退役檔案。

## 正式 production smoke

Cloudflare 部署後執行 `scripts/smoke_test_portfolio_v3.mjs`，驗證：

- 自有 Portfolio v3 health 與 schema。
- 台股資產搜尋。
- `SPY + 2330.TW` 混合市場 Preflight。
- TWD 估值。
- 固定金額定期現金流。
- 配息保留為 TWD 現金。
- 月度再平衡。
- 交易成本。
- 固定比例槓桿與融資利息。
- 正式 `series` 回應、事件、配置歷史、核心指標與 reproducibility metadata。

PR 7 僅處理觀察期、遷移通知及外部舊 repository／Vercel project 下線，不再承擔 runtime 功能切換。
