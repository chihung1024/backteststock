# 日級回測區間與 Edge 快取規格

## 預設日期

瀏覽器以使用者本地日期計算預設區間：

- 今天定義為 `day 0`，不納入預設回測。
- 結束日期為昨天，且為包含端點。
- 起始日期為今天往前十年的同月同日，且為包含端點。
- 例如在 2026-08-01 開啟網站時，預設為 2016-08-01 至 2026-07-31。
- 2 月 29 日往前十年遇到非閏年時，起始日期收斂至 2 月 28 日。
- 這只是新回測與新掃描的預設值；使用者可以自行修改起訖日期。
- 還原權值與再現性契約不因預設期間變更而調整。

API 新契約使用：

```json
{
  "startDate": "2016-08-01",
  "endDate": "2026-07-31"
}
```

後端將包含端點的 `endDate` 轉換為行情來源使用的 exclusive end。舊版 `startYear`、`startMonth`、`endYear`、`endMonth` 仍可使用，避免舊掃描工作與外部呼叫中斷。

## 效能策略

資料正確性優先於單純縮短時間，因此維持：

- `Adj Close` 總報酬基礎。
- `actions=true`。
- `repair=true`。
- 公司行為稽核。
- 同一請求中的標的一次大批下載。

本階段不建立持久化日線資料層，也不增加每日預抓行情流程；首次遇到全新日期與標的組合時，仍由正式行情來源即時取得最新資料。

Cloudflare Worker 對未攜帶 Authorization 或 Cookie、且成功回傳 JSON 的 `/api/backtest` 與 `/api/scan` POST 請求，依路徑及完整 request body 的 SHA-256 建立 15 分鐘 Edge 快取。不同日期、權重、標的、基準或再平衡設定不會共用結果。

回應標頭：

- `X-Edge-Cache: MISS`：本次送至後端即時計算。
- `X-Edge-Cache: HIT`：本次直接使用完全相同請求的 Edge 結果。
- `Server-Timing`／`X-Backend-Server-Timing`：包含 `market`、`compute`、`serialize` 與 `total` 階段。

Edge HIT 回應會產生新的 request ID；快取內不保存原請求的 request ID。非 200、非 JSON、帶驗證資訊或 Cookie 的請求不快取。
