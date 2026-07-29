# Universe Scanner v2

## Scope

第一階段以 additive design 實作；既有 `/api/backtest`、`/api/scan`、`/api/screener`
契約不變。新功能位於 `/api/v2/*`，D1 或 Universe 更新故障不會阻斷手動代碼掃描與投資組合回測。

## Universe sources

| Universe ID | 顯示名稱 | 機器來源 | 合理數量 | 說明 |
| --- | --- | --- | ---: | --- |
| `sp500` | S&P 500（IVV holdings） | iShares IVV official holdings CSV | 480–530 | ETF 公開持股代理池 |
| `nasdaq100` | NASDAQ-100 | Nasdaq official JSON API | 95–110 | 同公司多股別可能使證券數超過 100 |
| `soxx` | SOXX holdings | iShares SOXX official holdings CSV | 25–40 | ETF 股票持股 |
| `russell2000` | Russell 2000（IWM holdings 代理） | iShares IWM official holdings CSV | 1,750–2,100 | 非 FTSE Russell 授權名單 |

來源網址集中於 `scripts/update_universes.py`，並可用
`UNIVERSE_SP500_URL`、`UNIVERSE_NASDAQ100_URL`、`UNIVERSE_SOXX_URL`、
`UNIVERSE_RUSSELL2000_URL` 暫時覆寫。

## Update and last-good behavior

1. 擷取官方 CSV／JSON，重試暫時性 429 與 5xx。
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
- `universe_versions`：來源日、擷取日、checksum、筆數與狀態。
- `universe_members`：正規化 ticker、原始 ticker、名稱、產業、權重與市值。
- `universe_current`：每個 Universe 目前可服務的完整版本。

Schema 位於 `migrations/0001_universe_versions.sql`。

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
    "selectedForScan": 100
  },
  "candidates": [],
  "truncated": true,
  "warnings": []
}
```

`passedFilters > limit` 時，API 依明示的排序取前 `limit` 檔並回傳警示；不是靜默截斷。

## Scanner execution

- 整批最多 100 檔。
- 瀏覽器每 25 檔呼叫一次既有 `/api/scan`。
- 最大併發數 2。
- 失敗批次自動重試一次，仍失敗者顯示錯誤並提供重試按鈕。
- 每檔結果包含總報酬、CAGR、波動、MDD、Sharpe、Sortino、Beta、Alpha、
  實際資料起訖日、交易日與資料覆蓋率。
- 群組摘要包含成功數、CAGR 中位數、平均波動、平均回撤、平均 Sharpe 與平均資料覆蓋。
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
