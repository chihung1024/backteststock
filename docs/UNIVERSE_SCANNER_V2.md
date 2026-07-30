# Universe Scanner v2

## Scope

第一階段以 additive design 實作；新功能位於 `/api/v2/*`，D1 或 Universe 更新故障不會
阻斷手動代碼掃描與投資組合回測。第二階段保留既有成功結果欄位，並為 `/api/scan`
增加 `status`、`retryable` 與暫時缺漏契約，避免把不完整上游回傳誤判成最終結果。

## Universe sources

| Universe ID | 顯示名稱 | 機器來源 | 合理數量 | 說明 |
| --- | --- | --- | ---: | --- |
| `sp500` | S&P 500（IVV holdings） | iShares IVV official holdings CSV | 480–530 | ETF 公開持股代理池 |
| `nasdaq100` | NASDAQ-100（自動備援） | Nasdaq Global Index Watch；失敗時 Nasdaq official JSON API；再失敗時 Invesco QQQM official holdings JSON | 95–110 | GIW 是官方成分資料；QQQM 備援版本會明確標示 ETF 代理池；同公司多股別可能使證券數超過 100 |
| `soxx` | SOXX holdings | iShares SOXX official holdings CSV | 25–40 | ETF 股票持股 |
| `russell2000` | Russell 2000（IWM holdings 代理） | iShares IWM official holdings CSV | 1,750–2,100 | 非 FTSE Russell 授權名單 |

來源網址集中於 `scripts/update_universes.py`，並可用
`UNIVERSE_SP500_URL`、`UNIVERSE_NASDAQ100_URL`、
`UNIVERSE_NASDAQ100_GIW_URL`、`UNIVERSE_NASDAQ100_FALLBACK_URL`、
`UNIVERSE_SOXX_URL`、
`UNIVERSE_RUSSELL2000_URL` 暫時覆寫。

## Update and last-good behavior

1. 擷取官方 CSV／JSON，重試暫時性 429 與 5xx。NASDAQ-100 先查詢 Nasdaq Global Index Watch 最近 7 個工作日的官方 NDX 成分；GIW 失敗時依序嘗試舊 Nasdaq 公開 API 與 QQQM 公開持股代理池。
2. 僅保留股票資產，正規化 Yahoo 相容 ticker；例如 `BRKB` 對應 `BRK-B`，同時保存原始 ticker。
3. 驗證資料日期、ticker 格式、重複值、合理數量、相對前版數量變動與成分更替率。
4. 先建立 `staging` version，分批寫入 members，再回查筆數。
5. 所有檢查通過後，以單一 `universe_current` pointer 更新作為正式切換點。
6. 新版失敗時不修改 pointer；API 繼續讀取最後一個完整版本。
7. 每個 Universe 保留最近 12 個版本；目前版本絕不在重建或清理時刪除。

排程位於 `.github/workflows/update-universes.yml`：

- UTC 每週一、四 06:17 自動執行。
- `workflow_dispatch` 可手動執行。
- `dry_run=true` 只驗證來源並上傳 JSON report，不寫入 D1。
- 四個來源獨立處理；成功來源可完成發布，任一失敗會讓 workflow 標示失敗並保留各自 last-good。

## D1 model

- `universes`：穩定 ID、顯示名稱、資料來源與 proxy disclosure。
- `universe_versions`：實際使用的來源、代理池標記、來源日、擷取日、checksum、筆數與狀態。
- `universe_members`：正規化 ticker、原始 ticker、名稱、產業、權重與市值。
- `universe_current`：每個 Universe 目前可服務的完整版本。

Schema 位於 `migrations/0001_universe_versions.sql`，來源版本欄位擴充位於
`migrations/0002_versioned_source_metadata.sql`，Nasdaq GIW 來源說明更新位於
`migrations/0003_nasdaq_giw_metadata.sql`。

## API contracts

### `GET /api/v2/universes`

回傳所有已啟用的 Universe、來源、目前版本、成分日、更新日、筆數、可用狀態與警示。
尚未有版本的 Universe 仍會列出但 `available=false`。

### `GET /api/v2/universes/:id`

回傳目前完整快照與成分 ticker。若 D1 實際筆數不等於 version 宣告筆數，API fail closed，
回傳 `503`，不會交給預篩選器。

### `POST /api/v2/screener`

瀏覽器只提供 Universe ID、基本面條件、排序與上限。Cloudflare Worker 從 D1 取得可信快照，
覆寫任何客戶端偽造的 `_universe` 後，才轉送 Python API。

主要 response：

```json
{
  "universe": {
    "id": "sp500",
    "version": "2026-07-27-24d7d38843ff",
    "sourceAsOf": "2026-07-27"
  },
  "fundamentalsAsOf": "2026-07-28",
  "funnel": {
    "universeCount": 504,
    "fundamentalsAvailable": 500,
    "sectorMatches": 500,
    "passedFilters": 132,
    "selectedForScan": 132
  },
  "candidates": [],
  "limit": null,
  "truncated": false,
  "warnings": []
}
```

`limit` 留空或為 `null` 時納入所有通過條件的股票。只有使用者輸入正整數上限，且
`passedFilters > limit` 時，API 才依明示的排序取前 `limit` 檔並回傳截斷說明。

## Scanner execution

- 使用者的整批清單不設檔數上限；手動輸入超過 100 檔仍會完整執行。
- 瀏覽器每 100 檔循序呼叫 `/api/scan`。API 保留單一 HTTP request 的防護上限，但不限制
  整個瀏覽器掃描工作的總數。
- Python 行情層優先使用多股票 `download()`，每次最多 100 檔、16 個下載執行緒；每次
  回傳後逐檔驗證，最多嘗試 3 輪且每輪只補抓尚未解析的股票。只有非空且通過正規化的
  成功序列會逐檔快取，批次 HTTP 200 不再等同整批成功。
- 每批回應逐檔核對。暫時缺漏以 `status=pending`、`retryable=true` 回傳，瀏覽器只將
  該股票重新排隊；比較基準缺漏時整批重試，避免產生 Beta／Alpha 空值。
- HTTP 暫時性錯誤每批先重試 3 次；仍未完整時持續以最高 60 秒退避，不把暫時缺漏
  寫成最終失敗。
- 工作的 payload、已完成結果及未完成佇列保存在 `localStorage`，完整完成結果會保留到
  下一次掃描。使用者取消時暫停；頁面重整或重新開啟後，只接續未完成股票，不重跑成功結果。
- 完成條件是 `pending` 佇列為空；結果區持續明列成功、失敗與未完成數量。
- 結果表預設每頁 100 筆，支援 50／100／250 筆分頁，避免完整 Russell 2000 結果造成
  大量 DOM 節點。
- 每檔結果包含總報酬、CAGR、波動、MDD、Sharpe、Sortino、Beta、Alpha、
  實際資料起訖日、交易日與資料覆蓋率。
- 群組摘要包含成功、失敗、未完成、CAGR 中位數、平均波動、平均回撤、平均 Sharpe
  與平均資料覆蓋。
- CSV 匯出包含所有上述欄位與個別錯誤。

## Fundamental data

V2 在 D1 Universe 與 `GIST_RAW_URL` 基本面資料間做 ticker join。Gist 可維持舊版 JSON array，
也可改用：

```json
{
  "asOf": "2026-07-28",
  "warning": null,
  "data": []
}
```

漏斗會揭露無基本面資料的成分股數，不會把 missing value 當成通過條件。

## Rollback

- 程式版本：使用 Release `backup-2026-07-29-5e841f1` 還原第一階段前版本。
- Universe 資料：將 `universe_current.version_id` 指回仍保留的舊 version。
- Cloudflare：回滾 Worker deployment；Vercel API 不需因 v2 回滾而修改。
