# Backtest Stock

重新整理後的美股投資組合回測與個股掃描工具。

## 架構

```text
Browser
  -> Cloudflare Worker + Static Assets
       -> public/                   靜態 HTML / CSS / JavaScript
       -> D1 Universe DB            版本化成分股與 last-good pointer
       -> /api/v2/universes         Universe 目錄與版本資訊
       -> /api/v2/screener          D1 成分股 + Python 基本面篩選
       -> 其他 /api/* proxy         既有 API 代理、限制與安全標頭
            -> Vercel Python API   Flask + pandas + yfinance
```

### 各平台的角色

- **靜態 HTML/CSS/JavaScript**：實際使用者介面。不是單一巨型 HTML，而是分離的 `index.html`、`styles.css`、`app.js`。
- **Cloudflare Worker**：提供靜態資產，並將 `/api/*` 安全地代理到 Python 後端。
- **Cloudflare D1**：保存 Universe 定義、版本化成分股、來源日期、checksum 與目前有效版本。
- **GitHub Actions**：只負責測試與部署，不是應用程式執行環境。
- **Vercel Python Function**：第一階段保留 Flask、pandas、NumPy、yfinance。後續可比較 Cloudflare Container 或預處理資料後的 Worker-native 引擎。

## 目錄

```text
api/                         Python API
public/                      靜態前端
worker/                      Cloudflare Worker
tests/                       Python 回歸測試
docs/                        部署與維運文件
.github/workflows/           CI 與 Cloudflare 部署
migrations/                  D1 schema 與 Universe 定義
scripts/update_universes.py  官方來源擷取、驗證與 D1 發布
wrangler.jsonc               Cloudflare Worker 設定
vercel.json                  Python API 設定
```

## 本機執行

### Python API

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
flask --app api.index run --port 5000
```

### Cloudflare 前端與代理

```bash
cp .dev.vars.example .dev.vars
# 將 BACKEND_ORIGIN 改成 http://127.0.0.1:5000
npx --yes wrangler@4 dev
```

第一次本機執行先建立 D1 schema：

```bash
npm ci
npx wrangler d1 migrations apply backteststock-universe --local
```

## 測試

```bash
python -m pytest -q
ruff check api scripts tests
npm run check
npm run test:worker
npx wrangler d1 migrations apply backteststock-universe --local
npx wrangler deploy --dry-run
python scripts/update_universes.py --report /tmp/universe-update-report.json
```

最後一行是即時來源乾跑，只驗證、不寫入 D1。

## 個股快速績效掃描 v2

- Universe：S&P 500（IVV holdings 代理）、NASDAQ-100（Nasdaq API，失敗時自動改用 QQQM holdings 代理）、SOXX holdings、Russell 2000（IWM holdings 代理）。
- GitHub Actions 每週一、四自動更新，也可手動執行 `Update Universe Membership`。
- 新版本完整寫入並驗證後才切換 `universe_current`；來源或內容驗證失敗時，舊版本繼續服務。
- 預篩選結果顯示完整漏斗與明確的 25／50／100 檔取樣規則，不會靜默截斷。
- 集體回測以每批 25 檔、最多兩批並行執行；失敗批次自動重試一次，仍失敗者可單獨重試。
- 舊 `/api/scan`、`/api/screener` 與手動股票代碼輸入皆保留。

詳細資料契約與維運方式見 [`docs/UNIVERSE_SCANNER_V2.md`](docs/UNIVERSE_SCANNER_V2.md)。

## 部署

### Vercel 後端

將此 repository 匯入 Vercel，設定：

- `GIST_RAW_URL`：預處理股票清單 JSON，可選；screener 與 ticker autocomplete 需要。
- `RISK_FREE_RATE`：年化無風險利率，小數格式，預設 `0`。

部署後記下 API origin，例如：

```text
https://backteststock-api.example.vercel.app
```

### Cloudflare Worker

Vercel API origin 是非敏感設定，放在 `wrangler.jsonc` 的
`vars.BACKEND_ORIGIN`，值不要附加 `/api`。若部署到不同環境，請改成該環境的
公開 HTTPS origin。

GitHub Actions secrets：

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

第一次部署請在 GitHub Actions 手動執行 `Deploy Cloudflare Worker`。工作流程會依名稱尋找
`backteststock-universe` D1；若不存在就建立於 APAC、套用 migrations，再部署 Worker。
部署後手動執行一次 `Update Universe Membership`，讓四個 Universe 產生首個有效版本。

完整步驟、Smoke Test 與 rollback 請見 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)。

## 安全注意事項

- 不提供任何會輸出環境變數的 debug endpoint。
- 不將 Cloudflare、Vercel 或資料來源 token 寫進 repository。
- API 有輸入大小、股票數量、日期與權重驗證。
- 目前資料來源適合研究與教育用途，不構成投資建議。
