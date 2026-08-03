# Backtest Stock

以 TWD 統一估值的多市場投資組合回測、個股掃描與全量最佳化工具。

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
- **Vercel Python Function**：目前保留 Flask、pandas、NumPy、yfinance 作為相容外層；`apps/api/app/` 提供共用 TWD 資料、掃描、投組與全量快照核心，未來可直接接至 FastAPI。

## 目錄

```text
api/                         Python API
apps/api/app/                共用 TWD 估值與回測核心
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
flask --app api.index_v2 run --port 5000
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
ruff check api apps scripts tests
npm run check
npm run test:worker
npx playwright install chromium
npm run test:e2e
npx wrangler d1 migrations apply backteststock-universe --local
npx wrangler deploy --dry-run
python scripts/update_universes.py --report /tmp/universe-update-report.json
```

Playwright 測試會以真實瀏覽器驗證前端初始化、Universe 預篩選與集體回測操作流程。
最後一行是即時來源乾跑，只驗證、不寫入 D1。

## 個股快速績效掃描 v2

- Universe：S&P 500（IVV holdings 代理）、NASDAQ-100（Global Index Watch → Nasdaq API → QQQM 自動備援）、SOXX holdings、Russell 2000（IWM holdings 代理）。
- GitHub Actions 每週一、四自動更新，也可手動執行 `Update Universe Membership`。
- 新版本完整寫入並驗證後才切換 `universe_current`；來源或內容驗證失敗時，舊版本繼續服務。
- 預篩選預設將所有通過條件的股票納入回測；需要縮小範圍時，可手動輸入正整數上限，且不會靜默截斷。
- 手動股票清單沒有整批 100 檔限制；瀏覽器優先以每批 100 檔循序執行，可處理完整 Russell 2000 代理池。
- 所有個股、投組、基準與全量最佳化快照均以「Yahoo 還原股價 × 每日對 TWD 匯率」計價；FX-only 日保留匯率趨勢，且不會用未來匯率回填。
- 行情以多股票批次優先取得，並逐檔驗證及逐檔快取；HTTP 成功但缺少個別股票時，後端批次補抓缺漏，瀏覽器最後只重新排隊仍缺漏的股票，不會把不完整批次當成完成。
- 每個掃描工作在瀏覽器持久保存成功結果與未完成佇列，完成結果也保留到下一次掃描；暫時性失敗自動退避重試，重整頁面後只接續未完成股票。
- 結果區在執行中與完成時都明列成功、失敗、未完成數量，並支援大量結果分頁。
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
- API 有輸入大小、日期與權重驗證；全量最佳化以 5,000 萬組組合與實際快照容量為安全邊界，不另設 60 檔來源清單上限。
- 目前資料來源適合研究與教育用途，不構成投資建議。
