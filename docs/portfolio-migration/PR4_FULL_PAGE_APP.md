# PR 4：`/portfolio/` 單一獨立專頁

本階段建立 `backteststock` 內真正可直接開啟、重新整理與分享的 Portfolio Research 頁面。主功能由 React + TypeScript 應用承載，正式輸出位於 `public/portfolio/`，不使用 `<dialog>`、iframe 或舊 Portfolio Lab script 作為主介面。

## 路徑與架構

- 正式路徑：`/portfolio/`
- 原始碼：`apps/portfolio-web/`
- Production bundle：`public/portfolio/`
- API：同源 `/api/v3/portfolio/*`
- 建置：Vite，base 固定為 `/portfolio/`

Cloudflare static assets 直接提供 `public/portfolio/index.html` 及 hashed assets，因此 `/portfolio/` 可直接開啟及重新整理，不依賴主頁先建立 JavaScript 狀態。

## 資產配置

- 最多五組投資組合。
- 全域最多二十列唯一資產；每組可對各列設定不同權重。
- 桌機採資產 × 投組矩陣。
- 手機採「目前編輯投組」選擇器及單一投組聚焦編輯，避免五欄矩陣在 390px 螢幕失去可用性。
- 支援股票搜尋、等權、正規化至 100%、複製、清空、刪除及即時總權重驗證。
- 空白或 0% 投組不送出；有效投組必須在 0.05 個百分點容差內合計 100%。

## 模擬設定

完整呈現 Portfolio v3 契約：

- 日期、初始 TWD 金額、Benchmark、YTD、圖表輸出頻率。
- 配息再投入或保留 TWD 現金、交易成本。
- 固定或淨值比例現金流、月／季／年、期初／期末、年度成長率。
- 月／季／半年／年再平衡與偏離門檻。
- Fixed ratio／fixed debt、借款利率與維持保證金。
- 無風險利率、Fama–French + FX、受約束風格、環境及通膨分析。
- 可選事件及每日配置歷史。

## 兩階段執行

固定底部執行列提供：

1. 資料預檢：逐檔行情、幣別、期間、稽核及每組可執行狀態。
2. 完整回測：只要至少一組通過預檢即可執行，兄弟投組或附加分析失敗不抹除成功結果。

請求可取消；錯誤、警告與成功狀態使用 `role=alert`／`aria-live` 呈現。

## 完整結果儀表板

同一頁面內提供九個可鍵盤操作的頁籤：

- 總覽
- 資產成長
- 回撤
- 年度報酬
- 月報酬
- 現金流與收入
- 配置漂移
- 進階分析
- 資料稽核

內容包括線性／對數成長曲線、主要回撤事件、partial-period 標記、月報酬熱圖、成本與配發、目標／期末配置、因子與環境結果，以及 quote currency、FX、公司行為、指紋與所有 reproducibility contract versions。

## 狀態、分享與匯出

- 模型可儲存於目前瀏覽器 localStorage。
- 分享網址將完整模型做 UTF-8 base64url 編碼；不包含金鑰或回測結果。
- 支援模型 JSON 匯入／匯出。
- 支援結果 JSON 與核心指標 CSV 匯出。
- 一般空白模型與範例模型均可一鍵載入。

## 響應式與無障礙

- 320px 起可用，390px 為自動化驗收基準。
- 所有主要按鈕及表單至少約 44px 觸控高度。
- 支援 iPhone safe-area、鍵盤焦點、skip link、表格 region、結果 tab semantics、reduced motion、high contrast 及 forced colors。
- 圖表使用具備可存取名稱的 SVG；重要數字同時以表格或文字呈現，不只依賴顏色。

## 階段邊界

PR 4 建立獨立專頁，但主網站目前的「投資組合回測」入口及 Scanner 選股 handoff 尚未切換。PR 5 將把這些入口改為正常導覽至 `/portfolio/` 並保留來源工作狀態；PR 6 才刪除舊 Dialog、舊 scripts 與舊 API proxy。
