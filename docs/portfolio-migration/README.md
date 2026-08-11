# Portfolio Lab 完全移植計畫

Status: **HISTORICAL MIGRATION EVIDENCE — PR0–PR6 CLOSED. NOT LIVE PROJECT STATUS.**

本目錄保存 `chihung1024/backtest` 移植至 `chihung1024/backteststock` 的 migration/cutover 契約與歷史證據。現行產品/架構請以根 `README.md`、`apps/api/README.md`、相關 contract/ADR 與 `to_do_update_list.md` 為準。

原計畫中的 PR7（外部舊 Pages / Vercel project / repository 下線）**不是目前 Active Batch，也不得由新 Agent 因看到本文件而自行啟動**。只有在 live roadmap 明確重新排入，並重新驗證外部資源/相依性後，才可處理。

本目錄暫時保留，是因 PR2–PR6 仍含部分唯一 Portfolio ledger/API/cutover 設計證據；當這些唯一語意完整被現行 versioned authority 吸收後，可依 `docs/PROJECT_DOCUMENTATION_POLICY.md` 再移除，歷史差異由 Git 保存。

## 原始不可變更目標（歷史）

1. 唯一正式 repository：`chihung1024/backteststock`。
2. 唯一正式前端：`/portfolio/` 全頁式應用，不使用 `<dialog>` 或 iframe 承載主功能。
3. 唯一後端：`backteststock` 自有 API；正式 runtime 不呼叫舊 Portfolio API origin。
4. 唯一資料核心：TWD History、FX、公司行為稽核、指紋與 metric-version 架構。
5. 原專案較完整的現金流、股息、再平衡、交易成本、槓桿、XIRR、完整指標及分析功能，在上述核心上重新實作。
6. Scanner、一般投組回測與 Exhaustive Optimizer 共用 TWD 資料契約，不另建第二套 Yahoo／FX 下載邏輯。

## 歷史執行進度

| 階段 | 歷史狀態 | 已完成內容 |
|---|---|---|
| PR 0 | CLOSED | 凍結來源 commit、核心 blob SHA、能力矩陣、request/response contract、合成行情與 parity scenarios |
| PR 1 | CLOSED | TWD total/price/distribution return components、Yahoo 原始組成欄位、History Service 整合 |
| PR 2 | CLOSED | Portfolio Ledger、現金流、配息策略、成本、再平衡、槓桿、margin liquidation、指標與部分成功服務 |
| PR 3 | CLOSED | FastAPI Portfolio v3、Preflight、嚴格 schema、Edge proxy、因子/FX 分離、analytics 降級 |
| PR 4 | CLOSED | React + TypeScript `/portfolio/` 獨立專頁、設定/結果/儲存分享匯出/RWD |
| PR 5 | CLOSED | 主站與 Scanner 導覽至 `/portfolio/` 並保留 handoff state |
| PR 6 | CLOSED | 刪除舊 Dialog runtime、舊 portfolio-lab API/跨專案代理並切換自有 Portfolio v3 smoke |
| PR 7 | HISTORICAL PLAN / NOT ACTIVE | 原規劃的外部舊資源停用/刪除；未經 live roadmap 重新啟動不得執行 |

## 當時版本化契約快照

以下只作 migration history；目前版本應從實作/現行 contract 查詢：

- `RETURN_COMPONENT_SOURCE_VERSION = yahoo-close-events-2026-08-04.1`
- `RETURN_COMPONENTS_CONTRACT_VERSION = twd-return-components-2026-08-04.1`
- `PORTFOLIO_LEDGER_CONTRACT_VERSION = portfolio-ledger-twd-2026-08-04.1`
- `PORTFOLIO_METRIC_CONTEXT_VERSION = portfolio-metrics-twd-2026-08-04.1`
- `PORTFOLIO_SERVICE_CONTRACT_VERSION = portfolio-service-twd-2026-08-04.1`
- `PORTFOLIO_API_CONTRACT_VERSION = portfolio-v3`
- `PORTFOLIO_API_SCHEMA_VERSION = portfolio-v3-2026-08-04.1`
- `PORTFOLIO_ANALYTICS_CONTRACT_VERSION = portfolio-analytics-twd-2026-08-04.2`

## 凍結來源

原專案行為基準固定於 commit：

`36eab9a380b69f0f3bd86c3906066f4f56e715bc`

詳細 fixture / capability evidence 保存在 `tests/fixtures/portfolio_migration/`。

## 歷史契約索引

- `PR2_LEDGER_METRICS.md` — Portfolio Ledger / metric migration semantics.
- `PR3_PORTFOLIO_V3_API.md` — Portfolio v3 API migration contract.
- `PR4_FULL_PAGE_APP.md` — full-page frontend migration contract.
- `PR5_NAVIGATION_HANDOFF.md` — Scanner/Portfolio handoff migration contract.
- `PR6_RUNTIME_CUTOVER.md` — runtime technical cutover evidence.

這些文件描述 migration 時點的契約/決策，不自動凌駕後續現行 contract、tests 或 implementation。

## 歷史差異治理

移植允許修正舊系統缺陷，但差異必須有 fixture/evidence、版本化語意與書面理由。主要原則包括：

- XIRR 無解/多重解不得偽裝唯一答案；
- partial periods 必須明示；
- VaR/CVaR 語意明示；
- factor/style/FX 分析須保留適當模型範圍；
- 附加 analytics failure 不應無條件抹除有效主回測；
- silent ticker deletion、silent period shrink 或 unavailable-as-zero 禁止。

## 歷史完成定義

PR0–PR6 的技術移植已完成。任何仍涉及外部舊 repository / Pages / Vercel project 的後續清理，必須重新做 current-state dependency audit，並由 live roadmap 明確排入新的 Batch；本歷史文件本身不構成執行授權。
