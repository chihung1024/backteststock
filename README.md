# Backtest Stock

以 TWD 統一估值的多市場投資組合回測、個股掃描、全量歷史搜尋與 Portfolio Research 工具。

## 架構

```text
Browser
  -> Cloudflare Worker + Static Assets
       -> public/                       Scanner / Exhaustive 靜態前端
       -> public/portfolio/             Portfolio v3 React production build
       -> D1 Universe DB                版本化成分股與 last-good pointer
       -> /api/v2/universes             Universe 目錄與版本資訊
       -> /api/v2/screener              D1 成分股 + Python 基本面篩選
       -> /api/optimizer/exhaustive/*   全量歷史研究路徑
       -> /api/v3/portfolio/*           Portfolio v3 固定 allowlist proxy
       -> 其他 /api/*                   相容 API proxy
            -> Vercel Python Functions
                 -> Flask compatibility routes
                 -> FastAPI Portfolio v3 (`api/portfolio_v3.py`)
                      -> `apps/api/app/` shared TWD/data/portfolio core
```

### 各平台的角色

- **Cloudflare Static Assets / Worker**：提供瀏覽器前端、D1 Universe、API request guard、固定路由 allowlist 與 Vercel proxy。
- **Cloudflare D1**：保存 Universe 定義、版本化成分股、來源日期、checksum 與目前有效版本。
- **Vercel Python Functions**：同時承載既有 Flask 相容路徑與已正式上線的 self-owned FastAPI Portfolio v3。
- **`apps/api/app/`**：framework-neutral 共用核心，包含 TWD 估值、FX、return components、Portfolio ledger/metrics/analytics。
- **`apps/portfolio-web/`**：Portfolio v3 React/TypeScript full-page workspace；production build 發布到 `/portfolio/`。
- **GitHub Actions**：測試、Release backup、Universe 更新與部署；不是應用程式執行環境。

目前 runtime/compatibility 權威邊界見 [`docs/PHASE_MINUS1_GOVERNANCE.md`](docs/PHASE_MINUS1_GOVERNANCE.md) 與 [`docs/adr/0001-runtime-and-quant-authority.md`](docs/adr/0001-runtime-and-quant-authority.md)。

## 目錄

```text
api/                         Vercel Python entrypoints / compatibility APIs
apps/api/app/                共用 TWD 資料與 Portfolio 核心
apps/portfolio-web/          Portfolio v3 React/TypeScript source
public/                      Scanner/Optimizer 靜態前端與 production assets
worker/                      Cloudflare Worker / API router
migrations/                  D1 schema 與 Universe 定義
tests/                       Python / Node / Playwright 回歸測試
docs/                        架構、量化契約、部署與維運文件
.github/workflows/           CI、Release backup、Universe 更新與部署
scripts/                     smoke tests / Universe update utilities
wrangler.jsonc               Cloudflare Worker 設定
vercel.json                  Vercel Python Function 路由
```

## 本機執行

### Legacy/compatibility Flask API

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
flask --app api.index_v2 run --port 5000
```

### Portfolio v3 FastAPI

本機可直接執行 `api/portfolio_v3.py` 對應的 ASGI app；正式路徑為 `/api/v3/portfolio/*`，Cloudflare Worker 只代理明確 allowlist 的 Portfolio v3 endpoints。

### Cloudflare Worker

```bash
cp .dev.vars.example .dev.vars
# 將 BACKEND_ORIGIN 改成對應的本機 Python origin
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
npm run check:portfolio
npx playwright install chromium
npm run test:e2e
npx wrangler d1 migrations apply backteststock-universe --local
npx wrangler deploy --dry-run
python scripts/update_universes.py --report /tmp/universe-update-report.json
```

CI 會額外驗證 Python compilation、依賴一致性、Portfolio production assets、Vercel 設定與 Cloudflare dry-run。Production Portfolio smoke 會等待 Vercel health 回報與 GitHub deployment 相同的 SHA，再執行完整 smoke flow，避免 Vercel/Cloudflare deployment race。

## 個股快速績效掃描 v2

- Universe：S&P 500（IVV holdings 代理）、NASDAQ-100（Global Index Watch → Nasdaq API → QQQM 自動備援）、SOXX holdings、Russell 2000（IWM holdings 代理）。
- GitHub Actions 每週一、四自動更新，也可手動執行 `Update Universe Membership`。
- 新版本完整寫入並驗證後才切換 `universe_current`；來源或內容驗證失敗時，舊版本繼續服務。
- 預篩選預設將所有通過條件的股票納入回測；需要縮小範圍時，可手動輸入正整數上限，且不會靜默截斷。
- 手動股票清單沒有整批 100 檔限制；瀏覽器優先以每批 100 檔循序執行，可處理完整 Russell 2000 代理池。
- 所有個股、投組、基準與全量最佳化快照均以「Yahoo 還原股價 × 每日對 TWD 匯率」計價；FX-only 日保留匯率趨勢，且不會用未來匯率回填。
- 行情以多股票批次優先取得，並逐檔驗證及逐檔快取；HTTP 成功但缺少個別股票時，後端批次補抓缺漏，瀏覽器最後只重新排隊仍缺漏的股票。
- 每個掃描工作在瀏覽器持久保存成功結果與未完成佇列；暫時性失敗自動退避重試，重整頁面後只接續未完成股票。
- 結果區明列成功、失敗、未完成數量，並支援大量結果分頁。

詳細資料契約與維運方式見 [`docs/UNIVERSE_SCANNER_V2.md`](docs/UNIVERSE_SCANNER_V2.md)。

## Portfolio v3

Portfolio v3 是 self-owned production path，使用嚴格 request/response contract、TWD Portfolio ledger、現金流、配息、再平衡、槓桿、tail risk、factor/style/regime analytics 與 reproducibility metadata。其正式前端位於 `/portfolio/`。

Portfolio v3 與 Scanner/Exhaustive 共用 `apps/api/app/data/` 的 TWD 資料契約，但 Portfolio ledger/metrics 保有自己的路徑相依 context。後續任何 Portfolio Refinery 開發必須先完成 quant metric authority/parity 階段，不得新增第三套未治理的績效公式。

## 全量歷史搜尋

`api/exhaustive_optimizer.py` 的定位是 **full-period historical research/exploration**。它可用於精確比較指定歷史區間內大量組合，但同一資料同時被用於搜尋與排名，因此結果不得直接視為 out-of-sample 未來績效證據。Portfolio Refinery 後續若與 Exhaustive 串接，必須在 training-only selection 與獨立 OOS/walk-forward validation 之間保持明確邊界。

## 部署

### Vercel 後端

將 repository 匯入 Vercel；`vercel.json` 同時配置 legacy/compatibility Python entrypoints、Exhaustive 與 `api/portfolio_v3.py` FastAPI Portfolio v3。

環境變數：

- `GIST_RAW_URL`：可選；部分 screener/ticker autocomplete 路徑使用。
- `RISK_FREE_RATE`：相容路徑年化無風險利率，小數格式，預設 `0`。
- Portfolio analytics 所需的 FRED key 依對應功能設定。

### Cloudflare Worker

Vercel API origin 放在 `wrangler.jsonc` 的 `vars.BACKEND_ORIGIN`，值不要附加 `/api`。

GitHub Actions secrets：

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

完整部署、production smoke 與 rollback 見 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)。

## Governance

- `.github/workflows/release-backups.yml` 是目前通用 pre/post merge Release backup gate。
- 新 runtime/quant PR 必須走 PR review、CI、對應 backup gate 與明確 contract versioning。
- `main` branch protection 是進入下一階段量化開發前的必要 repository-setting gate；細節見 Phase -1 文件。

## 安全與研究限制

- 不提供會輸出環境變數的 debug endpoint。
- 不將 Cloudflare、Vercel 或資料來源 token 寫進 repository。
- API 有輸入大小、日期與權重驗證；全量最佳化以 100 檔平台邊界、5,000 萬組組合與實際快照容量共同防護。
- Yahoo/yfinance 與目前 Universe 歷史適合研究與教育用途；歷史搜尋不等於未來報酬保證。
- 尚未具備完整 point-in-time Universe/fundamental history 的期間，不應宣稱消除了 survivorship/look-ahead bias。
