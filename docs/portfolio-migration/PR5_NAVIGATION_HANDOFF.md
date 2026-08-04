# PR 5：正常頁面導覽與 Scanner handoff

本階段將主站及個股績效列表的 Portfolio 入口改為正常頁面導覽至 `/portfolio/`。主要操作流程不建立 `<dialog>`、不搬移 `#backtest-panel`，也不在 Scanner 頁面內嵌 Portfolio UI。

## 主站入口

- 原「投資組合回測」Tab 在 runtime 轉換為一般 `<a href="/portfolio/">`。
- Scanner 成為主站預設研究頁面。
- 進入 Portfolio 前建立短效 handoff，使返回路徑與來源可辨識。

## Scanner 選股移交

使用者從績效列表勾選股票後，建立 session-scoped handoff：

- `sourceJobId`
- `selectedTickers`
- `startDate`、`endDate`
- `benchmark`
- `coverageThresholdPercent`
- 排序欄位及方向
- 分頁與每頁筆數
- 捲動位置
- 同源返回 URL

移交資料使用 `sessionStorage`，24 小時後失效，不包含 API 金鑰、認證資料或回測結果。

## 驗證規則

- Selection 必須屬於目前 Scan Job。
- 股票必須通過當下資料覆蓋率門檻。
- Benchmark 不可重複納入投組資產。
- 至少一檔，最多二十檔。
- 股票代碼正規化後去重。

## Portfolio 端

`/portfolio/` 在 React render 前讀取有效 handoff：

- 以已選股票建立單一等權投資組合。
- 套用 Scanner 日期與 Benchmark。
- 顯示來源摘要、覆蓋率門檻與 Scan Job 前綴。
- 提供「返回績效列表」連結。

## 返回狀態

返回主站後：

1. 切換至 Scanner。
2. 從既有 localStorage Scan Job 重建績效列表。
3. 恢復資料覆蓋率門檻。
4. 恢復排序、分頁與每頁筆數。
5. 保留既有勾選股票。
6. 恢復捲動位置或定位至績效列表。

## 階段邊界

PR 5 移除主要 Dialog 操作路徑，但舊 Portfolio Lab scripts、舊 proxy route 及相容程式仍保留至 PR 6。PR 6 必須完成 runtime 技術斬斷，正式程式不得再包含舊 API 網域、`/api/portfolio-lab/` 或 Dialog identifier。
