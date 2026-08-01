# 候選池投資組合最佳化器 MVP

## 固定研究契約

- 來源 Universe：既有掃描工作的股票清單，或使用者手動輸入的股票清單。
- 候選池：只使用 70% 訓練期重新掃描與排序，取前 20 名。
- 持股：20 選 10，每檔目標權重 10%。
- 再平衡：實際權重相對目標權重偏移 ±20%。10% 目標的容許區間為 8%～12%。
- 訊號：第 t 個共同交易日收盤後判斷；任一檔突破門檻即建立 pending signal。
- 執行：第 t+1 個共同交易日收盤，全投組恢復至各 10%。
- 交易成本：預設 0 bps，可修改；初始建倉與再平衡均納入成本。
- 搜尋：20 選 10 的 184,756 組全部先做快速評分，30,000 組進入深度搜尋。
- 搜尋方法：確定性多起點、一換一交換、受限二換二交換。
- 精確複驗：主要目標 120、其餘四目標各 30、Pareto／多樣性 60，共 300 組。
- 驗證：70% 訓練、30% 樣本外；候選池、搜尋與參數選擇只能使用訓練期。
- 樣本外：重新以各 10% 建倉；樣本外排序只作事後描述，不回頭改變策略。

## 最佳化目標

- 最大化 Sortino。
- 最大化 CAGR。
- 最小化 |MDD|。
- 最小化 |Beta|。
- 最大化 Alpha。

## 資料與再現性

- 使用明確 Yahoo Adjusted Close。
- `auto_adjust=false`、`actions=true`、`repair=true`。
- 候選股與 benchmark 使用 global complete-case 共同交易日。
- 只有 `verified_standard_actions` 可進入嚴格候選池。
- `/api/optimizer/prepare` 一次取得 20 檔與 benchmark，產生 gzip JSON 快照、資料雜湊與 HMAC 簽章。
- `/api/optimizer/verify` 使用同一份簽章快照複驗，不重新下載行情。
- 若設定 `OPTIMIZER_SIGNING_SECRET`，使用私密 HMAC key；未設定時以部署識別衍生完整性 key。後者可防止意外不一致，但不應宣稱為私密防偽。

## 搜尋層級

1. 184,756 組全體 proxy：均值、協方差、下行協方差、Beta 與 Alpha 的矩陣近似。
2. 30,000 組 deep proxy：以 meet-in-the-middle subset sums 建立完整訓練期等權日報酬路徑，計算 CAGR、Sortino、MDD、Beta 與 Alpha。
3. 300 組 Python exact：真實權重漂移、8%～12% band、次一交易日收盤執行、成本、換手率與再平衡事件。

快速與 deep 結果只用於搜尋；正式輸出以 Python exact 結果為準。

## 輸出

- 五項目標的訓練期冠軍及其樣本外表現。
- 300 組精確訓練與樣本外結果。
- 訓練期六維 Pareto：Sortino、CAGR、Alpha 最大化；|MDD|、|Beta|、年化單邊換手率最小化。
- 描述性樣本外 Pareto。
- 再平衡日期、觸發股票、交易名目金額、成本與換手率。
- candidate pool、dataset、價格、公式、公司行為、演算法、random seed、搜尋預算與搜尋軌跡。

## 最終工程邊界

- 30,000 組實際唯一貢獻必須等於：主要目標 15,000、其餘四目標各 3,000、Pareto／多樣性 3,000。輸出同時保存 requested 與 actual；不允許只報名義配額。
- 搜尋 bitmask 雜湊固定使用 little-endian unsigned 32-bit 序列，不依賴瀏覽器或 CPU 原生位元組序。
- 後端壓縮快照上限 2 MiB；Base64 膨脹與 300 組複驗設定納入後，Cloudflare optimizer 專用請求上限為 3 MiB。普通 API 仍為 256 KiB。

## 樣本外資料完整性

候選池仍只依訓練期資訊選擇；準備完整資料快照時，則按 benchmark 交易日曆分別稽核訓練與樣本外覆蓋率。任一候選股或全體 complete-case 在任一期間低於 98%，或共同期間起訖相差超過 5 個交易日，工作直接停止並列出標的，不得透過 `dropna()` 靜默縮短樣本外期間，也不得用樣本外資訊遞補另一檔股票。

精確複驗輸出必須同時保存 requested 與 actual 配額；Pareto 點不足 60 時，以對既有入選組合成分差異最大的未入選組合補足，仍歸類為 Pareto／多樣性，不得改由主要目標排名補足。
