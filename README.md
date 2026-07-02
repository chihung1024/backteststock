# Backtest Stock

重新整理後的美股投資組合回測與個股掃描工具。

## 架構

```text
Browser
  -> Cloudflare Worker + Static Assets
       -> public/                   靜態 HTML / CSS / JavaScript
       -> /api/* proxy             同網域 API 代理、限制與安全標頭
            -> Vercel Python API   Flask + pandas + yfinance
```

### 各平台的角色

- **靜態 HTML/CSS/JavaScript**：實際使用者介面。不是單一巨型 HTML，而是分離的 `index.html`、`styles.css`、`app.js`。
- **Cloudflare Worker**：提供靜態資產，並將 `/api/*` 安全地代理到 Python 後端。
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

## 測試

```bash
python -m pytest -q
ruff check api tests
node --check public/app.js
node --check worker/index.js
npx --yes wrangler@4 deploy --dry-run
```

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

在 Cloudflare Worker 設定 secret：

```bash
npx --yes wrangler@4 secret put BACKEND_ORIGIN
```

值填入 Vercel API origin，不要附加 `/api`。

GitHub Actions secrets：

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

第一次部署請在 GitHub Actions 手動執行 `Deploy Cloudflare Worker`。完成 smoke test 後，再考慮改為合併至 `main` 自動部署。

完整步驟、Smoke Test 與 rollback 請見 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)。

## 安全注意事項

- 不提供任何會輸出環境變數的 debug endpoint。
- 不將 Cloudflare、Vercel 或資料來源 token 寫進 repository。
- API 有輸入大小、股票數量、日期與權重驗證。
- 目前資料來源適合研究與教育用途，不構成投資建議。
