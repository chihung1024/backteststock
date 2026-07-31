# 績效指標與再現性規格

本文件定義個股掃描與投資組合回測共用的底層數據契約。正式 API 以 `api/metrics.py` 為唯一績效計算核心，定義版本為 `2026-08-01.1`。

## 行情契約

所有路徑固定使用 Yahoo Finance 日線，並透過同一版 yfinance 下載：

- `interval="1d"`
- `auto_adjust=true`
- `repair=true`
- `actions=false`
- `keepna=false`
- 起始日包含，結束日不包含

`requirements.txt` 精確鎖定 NumPy、pandas、SciPy 與 yfinance 版本。由於 `repair=true` 會使用 yfinance 的價格修復功能，SciPy 是正式環境的必要依賴，不得只在開發環境安裝。每筆掃描結果另回傳資料源版本、參數與 SHA-256 指紋；CSV 的 `note` 欄也保存同一份精簡再現資訊。

Yahoo Finance 仍可能事後修訂歷史資料。指紋能判斷兩次計算是否使用完全相同輸入，但若上游已修改且本系統未保存舊行情，指紋本身不能還原舊價格。

## 日期與樣本規則

### 個股掃描

個股與比較基準先放到比較基準的實際交易日曆。只有資產與基準在相鄰基準交易日都具有效價格時，該日報酬才納入 Sharpe、Sortino、Beta 與 Alpha。缺漏日後的跨多日報酬不會被誤當成單日報酬。

總報酬、CAGR 與最大回撤使用個股與基準共同有效的價格日期。資料覆蓋率定義為：

```text
個股與基準共同有效價格日數 / 基準有效價格日數
```

不再使用單純星期一至星期五作為分母。

### 投資組合回測

同一次比較中的所有投組、全部資產與比較基準使用同一個 complete-case 交易日曆。因此所有 CAGR、回撤與風險指標具有相同起訖期間。API 會回傳 requested/effective dates 與共同觀測數。

月、季、年再平衡在新期間第一個交易日之前的上一個收盤價執行，使新權重承擔新期間第一個交易日的報酬。未計交易成本、滑價與稅負。

## 公式

令日報酬為 `r_t`，日無風險利率為：

```text
r_f,d = (1 + 年化無風險利率)^(1/252) - 1
```

### 總報酬

```text
P_end / P_start - 1
```

### CAGR

```text
(P_end / P_start)^(365.25 / 實際經過日數) - 1
```

### 最大回撤

```text
min(P_t / running_max(P_t) - 1)
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

## 回傳的再現資訊

主要欄位包括：

- `metric_definition_version`
- `data_source_version`
- `numpy_version`
- `pandas_version`
- `scipy_version`
- `risk_free_rate`
- `data_source_settings`
- `requested_start` / `requested_end_exclusive`
- `metric_start` / `metric_end`
- `metric_price_observations` / `metric_return_observations`
- `price_fingerprint`
- `aligned_price_fingerprint`

兩次結果只有在定義版本、依賴版本、參數、有效期間與指紋均相同時，才可視為同一底層輸入的再現計算。
