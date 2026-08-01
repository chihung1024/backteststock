# 績效指標、還原權值與再現性規格

本文件定義個股掃描與投資組合回測共用的底層數據契約。正式 API 以 `api/metrics.py` 為唯一績效計算核心，定義版本為 `2026-08-01.2`；公司行為稽核版本為 `2026-08-01.2`。

## 行情與總報酬契約

所有正式路徑固定使用 Yahoo Finance 日線，並透過同一版 yfinance 下載：

- `interval="1d"`
- `auto_adjust=false`
- `repair=true`
- `actions=true`
- `keepna=false`
- 起始日包含，結束日不包含

`auto_adjust=false` 不代表績效使用未還原價格。系統刻意保留兩種價格：

- `Close`：Yahoo 原始收盤價，用於稽核調整因子。
- `Adj Close`：Yahoo 調整收盤價，為**所有績效公式與投資組合模擬唯一使用的價格序列**。

這比 `auto_adjust=true` 更可稽核：後者會把 `Adj Close` 改名成 `Close` 並丟棄原始收盤價，雖然計算數值通常相同，卻無法再檢查公司行為調整是否合理。

本系統的報酬基礎識別碼為：

```text
yahoo_adjusted_close_total_return_gross_reinvestment
```

其經濟意義是：把 Yahoo `Adj Close` 視為股利與資本利得配發在除權息時以未扣稅金額再投入的總報酬序列。它不包含交易成本、滑價、所得稅、股利預扣稅、ADR 保管費或基金申購贖回費。

## 公司行為涵蓋範圍

### 標準事件：在 Yahoo 正確回報且 yfinance 正確修復的前提下納入

| 公司行為 | 績效處理 | 稽核資料 |
|---|---|---|
| 一般現金股利 | 透過 `Adj Close` 視為總額再投入 | `Dividends` |
| 特別股利／資本返還 | Yahoo 若以 distribution/dividend 回報則納入 | `Dividends` 與調整因子 |
| 股票分割 | 納入 | `Stock Splits` |
| 反向分割 | 納入 | `Stock Splits` |
| 股票股利 | Yahoo 若編碼為 split 或調整事件則納入 | `Stock Splits`／調整因子 |
| 共同基金／ETF 資本利得配發 | 納入 | `Capital Gains` |
| Yahoo 價格、股利、拆股或幣別異常 | `repair=true` 嘗試修復 | `Repaired?` 與事件明細 |

每檔標的都會保存：

- 公司行為事件數量。
- 被 yfinance 修復的列數。
- `Adj Close / Close` 調整因子的異常變化。
- 宣告配發與實際調整因子的差異。
- 疑似未宣告拆股的倍數跳動。
- 無已知事件可解釋的極端單日總報酬。
- 需要人工覆核的日期。

正常狀態為：

```text
verified_standard_actions
```

發現不能由 Yahoo 標準事件解釋的異常時，狀態為：

```text
review_required
```

`review_required` 不會自動竄改價格；系統仍回傳 Yahoo `Adj Close` 計算結果，但在畫面、API 與稽核 CSV 明確警示，避免把猜測當成已確認的公司行為。

### 非標準事件：不能只靠 Yahoo Adjusted Close 保證完整還原

下列事件若 Yahoo 沒有正確反映在 `Adj Close`，本系統無法僅靠行情資料可靠重建其經濟價值：

- spin-off／分拆新股配發。
- 權利發行、認股權或 warrant 配發。
- 現金併購、換股併購或混合對價。
- 股票代碼、交易所或 share class 變更前後的歷史串接。
- ADR 比例變更但未被編碼為 split。
- 下市清算、破產分配或最後一筆現金對價。
- 稅負、股利預扣稅、ADR fee、交易成本與滑價。

對這些事件，正確做法需要具備 security master、事件條款、舊新證券映射與實際持有人應收對價。Yahoo/yfinance 的公開價格資料沒有提供足夠的完整契約資料，因此系統不得宣稱「任何公司行為皆已百分之百還原」。

## 價格指數與總報酬基準

以 `^` 開頭的 Yahoo 指數代碼通常是價格指數。即使欄位名稱為 `Adj Close`，也不代表指數成分股股利已再投入。因此：

- 個股或 ETF 的總報酬，不宜直接與價格指數比較後解讀為純超額報酬。
- 需要總報酬比較時，優先使用可投資且含配息調整的 ETF，例如以 `SPY` 代替 `^GSPC`。
- 使用價格指數時 API 會回傳警示，但不會擅自替換使用者指定的 benchmark。

## yfinance 價格修復

`repair=true` 會使用 yfinance 的價格修復功能，涵蓋 Yahoo 缺漏或錯誤的股利調整、拆股調整、100 倍幣別錯誤、缺漏價格、股利事件錯誤，以及資本利得重複計入等已知問題。

`requirements.txt` 精確鎖定 NumPy、pandas、SciPy 與 yfinance 版本。由於 `repair=true` 的部分修復使用 SciPy，SciPy 是正式環境必要依賴。資料契約或 yfinance 版本變更時，必須同步提升指標版本並重跑公司行為契約測試。

## 日期與樣本規則

### 個股掃描

個股與比較基準先放到比較基準的實際交易日曆。只有資產與基準在相鄰基準交易日都具有效調整價格時，該日報酬才納入 Sharpe、Sortino、Beta 與 Alpha。缺漏日後的跨多日報酬不會被誤當成單日報酬。

總報酬、CAGR 與最大回撤使用個股與基準共同有效的調整價格日期。資料覆蓋率定義為：

```text
個股與基準共同有效價格日數 / 基準有效價格日數
```

### 投資組合回測

同一次比較中的所有投組、全部資產與比較基準使用同一個 complete-case 交易日曆。因此所有 CAGR、回撤與風險指標具有相同起訖期間。

每個部位的股數由 `Adj Close` 建立及再平衡。因為 `Adj Close` 已將標準現金配發反映為總報酬，模擬不會再額外把 `Dividends` 加入現金，避免股利重複計算。

月、季、年再平衡在新期間第一個交易日之前的上一個收盤價執行，使新權重承擔新期間第一個交易日的報酬。未計交易成本、滑價與稅負。

## 公式

令日報酬為 `r_t`，日無風險利率為：

```text
r_f,d = (1 + 年化無風險利率)^(1/252) - 1
```

### 總報酬

```text
AdjClose_end / AdjClose_start - 1
```

### CAGR

```text
(AdjClose_end / AdjClose_start)^(365.25 / 實際經過日數) - 1
```

### 最大回撤

```text
min(AdjClose_t / running_max(AdjClose_t) - 1)
```

### 年化波動率

```text
sample_std(r_t) × sqrt(252)
```

### Sharpe

```text
mean(r_t - r_f,d) × 252 / 年化波動率
```

### Sortino

```text
mean(r_t - r_f,d) × 252
/
[sqrt(mean(min(r_t - r_f,d, 0)^2)) × sqrt(252)]
```

### Beta

```text
cov(r_asset, r_benchmark) / var(r_benchmark)
```

### Jensen Alpha

```text
252 × [mean(r_asset) - (r_f,d + Beta × (mean(r_benchmark) - r_f,d))]
```

Beta 與 Alpha 使用完全相同的成對日報酬樣本。

## 回傳的再現與稽核資訊

主要欄位包括：

- `metric_definition_version`
- `data_source_version`
- `data_source_settings`
- `return_basis`
- `return_price_column`
- `dividend_reinvestment_assumption`
- `corporate_action_policy_version`
- `standard_action_coverage`
- `nonstandard_action_limitations`
- `corporate_action_status`
- `dividend_events`
- `stock_split_events`
- `capital_gain_events`
- `price_repaired_rows`
- `unexplained_adjustment_changes`
- `distribution_adjustment_mismatches`
- `split_like_unreported_changes`
- `large_unexplained_returns`
- `corporate_action_warning_dates`
- `requested_start` / `requested_end_exclusive`
- `metric_start` / `metric_end`
- `metric_price_observations` / `metric_return_observations`
- `fingerprint_algorithm`
- `price_fingerprint`
- `aligned_price_fingerprint`

完整版本、參數、公司行為稽核與 SHA-256 指紋放在稽核 CSV；互動畫面及精簡 CSV 只保留人類可讀警示。

Yahoo Finance 仍可能事後修訂歷史行情或公司行為。指紋能判斷兩次計算是否使用完全相同輸入，但若上游已修改且本系統未保存舊行情，指紋不能自行還原舊版本。

## 不屬於還原權值、但仍會影響回測可信度的偏誤

公司行為調整正確，不代表回測已消除所有偏誤。現行系統仍需分別揭露：

- survivorship bias：使用今天的指數成分股回測過去，會漏掉已被剔除或下市公司。
- look-ahead bias：成分股名單、財務資料或篩選條件若使用事後資訊。
- delisting bias：Yahoo 缺乏完整下市報酬與最後清算對價。
- universe history：ETF 或指數目前成分不等於歷史各期成分。

這些問題不能由 `Adj Close` 解決，必須以 point-in-time universe 與 delisting return 資料另行處理。
