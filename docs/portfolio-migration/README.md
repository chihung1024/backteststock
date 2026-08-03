# Portfolio Lab 完全移植計畫

本目錄是 `chihung1024/backtest` 完全移植至 `chihung1024/backteststock` 的不可省略驗收契約。最終產品必須是 `backteststock` 內的單一獨立 `/portfolio/` 專頁，並移除舊 repository、舊 GitHub Pages、舊 Vercel project 與跨專案 API 代理。

## 不可變更的目標

1. 唯一正式 repository：`chihung1024/backteststock`。
2. 唯一正式前端：`/portfolio/` 全頁式應用，不使用 `<dialog>` 或 iframe 承載主功能。
3. 唯一後端：`backteststock` 自有 API；正式 runtime 不得呼叫 `portfolio-backtest-api.vercel.app`。
4. 唯一資料核心：現有 TWD History、FX、公司行為稽核、指紋與 metric-version 架構。
5. 原專案較完整的現金流、股息、再平衡、交易成本、槓桿、XIRR、完整指標及分析功能，必須在上述核心上重新實作。
6. Scanner、一般投組回測與 Exhaustive Optimizer 必須共享同一 TWD 資料契約，不另建第二套 Yahoo／FX 下載邏輯。
7. 每個遷移 PR 必須完成測試、合併 `main`、正式部署驗證與 post-merge Release 後，才進入下一階段。

## 執行進度

| 階段 | 狀態 | 已完成內容 |
|---|---|---|
| PR 0 | 已完成 | 凍結來源 commit、核心 blob SHA、35 項能力矩陣、完整 request／response contract、合成行情與 parity scenarios |
| PR 1 | 已完成 | TWD total／price／distribution return components、Yahoo 原始組成欄位保留、History Service 整合、相容性與全套 CI 驗證 |
| PR 2 | 已完成 | 自有 Portfolio Ledger、現金流、配息策略、成本、定期／門檻再平衡、fixed-ratio／fixed-debt 槓桿、margin liquidation、完整指標與部分成功服務 |
| PR 3 | 已完成 | 自有 FastAPI Portfolio v3、Preflight、嚴格 schema、Edge proxy、因子／FX 分離、受約束風格、環境分析與 FRED 降級 |
| PR 4～PR 7 | 未開始 | 依本文件順序執行 |

目前版本化契約：

- `RETURN_COMPONENT_SOURCE_VERSION = yahoo-close-events-2026-08-04.1`
- `RETURN_COMPONENTS_CONTRACT_VERSION = twd-return-components-2026-08-04.1`
- `PORTFOLIO_LEDGER_CONTRACT_VERSION = portfolio-ledger-twd-2026-08-04.1`
- `PORTFOLIO_METRIC_CONTEXT_VERSION = portfolio-metrics-twd-2026-08-04.1`
- `PORTFOLIO_SERVICE_CONTRACT_VERSION = portfolio-service-twd-2026-08-04.1`
- `PORTFOLIO_API_CONTRACT_VERSION = portfolio-v3`
- `PORTFOLIO_API_SCHEMA_VERSION = portfolio-v3-2026-08-04.1`
- `PORTFOLIO_ANALYTICS_CONTRACT_VERSION = portfolio-analytics-twd-2026-08-04.1`

## 凍結來源

原專案行為基準固定於 commit：

`36eab9a380b69f0f3bd86c3906066f4f56e715bc`

詳細檔案 blob SHA、功能清單及契約 fixture 見：

- `tests/fixtures/portfolio_migration/source_manifest.json`
- `tests/fixtures/portfolio_migration/capability_matrix.json`
- `tests/fixtures/portfolio_migration/legacy_request.json`
- `tests/fixtures/portfolio_migration/legacy_response_shape.json`
- `tests/fixtures/portfolio_migration/synthetic_market_data.csv`
- `tests/fixtures/portfolio_migration/scenarios.json`

## 分階段執行

| 階段 | 交付內容 | 正式功能影響 |
|---|---|---|
| PR 0 | 凍結來源、能力矩陣、請求／回應 fixture、合成行情與測試契約 | 無 |
| PR 1 | TWD 報酬組成資料層：價格、配發、公司行為與 FX 可稽核分解 | 資料模型擴充，既有流程保持相容 |
| PR 2 | Portfolio Ledger、現金流、配息策略、成本、再平衡、槓桿與完整指標 | 新自有回測核心 |
| PR 3 | FastAPI Portfolio v3、Preflight、進階分析及型別契約 | 新自有 API |
| PR 4 | React + TypeScript `/portfolio/` 單一獨立專頁 | 新正式介面 |
| PR 5 | Scanner → Portfolio 正常頁面導覽與狀態保留 | 移除主要 Dialog 流程 |
| PR 6 | 切換正式 API、刪除舊代理與舊網域 runtime 依賴 | 完成技術斬斷 |
| PR 7 | 遷移通知、觀察期、停用並刪除原專案與舊 Vercel project | 完成下線 |

## PR 1 報酬組成契約

原有 Adjusted Close 總報酬仍是 Scanner、一般回測與 Optimizer 的既有真值；新增組成層不改寫其歷史結果。

在原生報價幣別中：

```text
Total Return = Price Return + Distribution Return
```

其中 Distribution Return 由 Yahoo 報告的現金股利與資本利得配發，以前一有效 Raw Close 換算。Price Return 定義為總報酬扣除配發報酬，確保加法恆等式精確成立，並避免將拆股造成的 Raw Close 尺度跳變誤認為投資損益。

換算 TWD 時：

```text
TWD Total Return = (1 + Native Total Return) × (1 + FX Return) - 1
TWD Distribution Return = Native Distribution Return × (1 + FX Return)
TWD Price Return = TWD Total Return - TWD Distribution Return
```

資產與 FX 使用聯集日曆，只在各自已有真實觀察後向前填補，禁止 backward fill。這使 Portfolio Ledger 能正確比較「股息再投入」與「配息保留 TWD 現金」，而不重複計入 Adjusted Close 已內含的總報酬。

## PR 2 Portfolio Ledger 契約

完整事件順序、TWR 現金流處理、配息政策、再平衡、交易成本、槓桿、XIRR、VaR／CVaR、回撤事件與 partial-period 定義見：

- `docs/portfolio-migration/PR2_LEDGER_METRICS.md`

PR 2 僅建立自有 framework-neutral 核心，尚未切換公開 API 或目前的 Portfolio Lab 介面。

## PR 3 Portfolio v3 API 契約

新 API、Preflight、Edge allowlist、回應版本、因子／FX 分離、受約束風格、環境分類及 FRED 降級規則見：

- `docs/portfolio-migration/PR3_PORTFOLIO_V3_API.md`

PR 3 建立 `GET /api/v3/portfolio/health`、資產搜尋、Preflight 與 Backtests。Cloudflare 只轉送至 `backteststock` 自有 `BACKEND_ORIGIN`，不偽裝舊 GitHub Pages。現有舊 Portfolio Lab 路徑仍保留到 PR 6，避免在新全頁式介面完成前破壞正式功能。

## 差異治理

「移植」不是要求複製原專案的缺陷。下列改良允許產生與舊版不同的結果，但必須：

1. 在 capability matrix 標記 `improved`。
2. 建立固定 fixture 或合成行情證明差異原因。
3. 在 PR 說明列出舊行為、新行為與財務意義。
4. 變更 metric／valuation contract version。

預先核准的改良方向包括：

- XIRR 無解或多重解明確回報，不假裝存在唯一答案。
- 第一個不完整年度／月份明確標記 partial。
- VaR／CVaR 明示為歷史模擬每日風險值。
- 風格分析採真正的非負、合計 100% 受約束回歸。
- 因子分析區分資產因子與 TWD 投資人的 FX 曝險。
- 主回測、Benchmark 與進階分析採分級失敗，不因附加分析失敗抹除有效主結果。

## 完成定義

原專案只能在以下條件全部成立後刪除：

- capability matrix 所有 `required` 項目均為 `implemented` 或經核准的 `improved`。
- 正式 runtime code 不含舊 API、舊 Pages 路徑、`/api/portfolio-lab/` 或 `integrated-backtest-dialog`。
- `/portfolio/` 可直接開啟、重新整理、分享與從 Scanner 導入。
- 新 API production smoke 涵蓋混合市場、現金流、股息、再平衡、成本及槓桿。
- 新舊平行對照完成，差異均有書面解釋。
- 至少兩次正式發布或 30 天觀察期內無舊 API 依賴。