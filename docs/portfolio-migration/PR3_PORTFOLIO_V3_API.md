# PR 3：自有 Portfolio v3 API 與進階分析契約

本階段將 PR 1 的 TWD return components 與 PR 2 的 Portfolio Ledger 封裝成 `backteststock` 自有的 FastAPI API。新路徑只使用 `BACKEND_ORIGIN` 指向本 repository 的 Vercel 後端，不呼叫舊 `portfolio-backtest-api.vercel.app`，也不偽裝舊 GitHub Pages Origin／Referer。

## 版本

- `PORTFOLIO_API_CONTRACT_VERSION = portfolio-v3`
- `PORTFOLIO_API_SCHEMA_VERSION = portfolio-v3-2026-08-04.1`
- `PORTFOLIO_ANALYTICS_CONTRACT_VERSION = portfolio-analytics-twd-2026-08-04.1`

## API

```text
GET  /api/v3/portfolio/health
GET  /api/v3/portfolio/assets/search
POST /api/v3/portfolio/preflight
POST /api/v3/portfolio/backtests
```

Vercel 由 `api/portfolio_v3.py` 提供 ASGI function；Cloudflare Worker 以固定路由、HTTP method、512 KiB 請求限制、240 秒 timeout 與敏感 header 清理轉送至既有 `BACKEND_ORIGIN`。

舊 `/api/portfolio-lab/*` 仍暫時保留供現有介面使用，直到 PR 6 正式切換後才移除。

## 嚴格請求契約

- `extra="forbid"`，未知欄位直接拒絕。
- 最多 5 組投組，每組最多 20 項唯一資產。
- 有效投組權重必須在 0.05 個百分點容差內合計 100%。
- 唯一估值幣別為 TWD。
- 支援現金流、配息策略、定期／門檻再平衡、交易成本、fixed-ratio／fixed-debt 槓桿與進階分析設定。
- 可選 daily／weekly／monthly 輸出；所有指標仍使用完整每日帳本。

## Preflight

預檢不執行完整帳本，但會一次取得所有使用者資產、Benchmark 及必要的風格代理資產，並回傳：

- 每檔資產成功／失敗、stage、detail、retryable。
- 實際報價幣別、有效期間、觀察數。
- 公司行為、FX 與 return-component 稽核。
- Native／FX／TWD 序列指紋。
- 每組投組的共同有效期間與可執行狀態。
- Benchmark 與分析依賴分開呈現。

單一資產或投組失敗不抹除不相依的成功結果。

## Backtest

正式回應包含：

- 每組投組的完整核心指標、XIRR 狀態、VaR／CVaR 方法、回撤事件、年度／月度 partial-period 報酬。
- 每日或抽樣後的 equity、TWR index、flow、income、cash、debt 與 gross exposure。
- 目標及期末配置、事件稽核與可選配置歷史。
- Benchmark、結構化 failures、warnings、timing 與所有合約版本。
- 附加分析失敗只降級為 warning，不抹除有效主回測。

## 因子與 FX 分離

TWD 投組不能偽裝成純 USD Fama–French 回歸。新模型使用：

- 應變數：投資人的每月 TWD 投組報酬。
- 股票因子：Kenneth French 官方 U.S. 5 Factor + Momentum。
- FX 共變數：每種非 TWD 報價幣別對 TWD 的每月報酬。

回應明示 regression currency、factor source currency、樣本、R²、factor betas、FX betas 及限制。這是歷史共同變動分解，不是全球持股因子模型或預測。

## 風格分析

原專案以 OLS 後裁掉負係數再正規化；新版本改為真正受約束最佳化：

```text
weights >= 0
sum(weights) = 1
```

使用 IWD、IWF、IWS、IWP、IWN、IWO 的 TWD 報酬代理，並回傳樣本、R²、代理代碼及限制。

## 市場環境

- Market：Benchmark 10 個月移動平均。
- Volatility：Benchmark 12 個月滾動年化波動率，採所選期間中位數分界。
- Inflation：CPI 年增率，以所選期間中位數及上升／下降方向分類。
- Business cycle：實質 GDP 與 CPI 年增率，以所選期間中位數形成四象限。

結果明示門檻、每個 regime 的月份數、報酬、波動、最佳／最差月份及樣本警告。所有 regime 都是回顧分類，不是預測。

## 通膨調整

FRED-dependent 功能需要 `BACKTEST_FRED_API_KEY` 或 `FRED_API_KEY`。未設定或外部資料失敗時，主回測保留，分析降級為 warning。

目前通膨調整使用 U.S. CPI `CPIAUCSL`，回應會明示它不是台灣 CPI，也不代表使用者實際消費籃子。

## 安全與限制

- Edge 和 FastAPI 都限制 512 KiB 請求。
- 一般 API 每來源 IP 每分鐘 20 次，Backtest 每分鐘 4 次；serverless 多執行個體下屬於個別 instance 限流。
- API 回應使用 `Cache-Control: no-store`、`nosniff`、Referrer Policy 與 Permissions Policy。
- PR 3 尚未切換現有 Portfolio Lab UI；PR 4 建立 `/portfolio/` 全頁式介面，PR 6 才刪除舊代理。
