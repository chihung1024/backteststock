# BacktestStock

BacktestStock 是一個以 **TWD 統一估值**為核心的多市場投資研究平台，包含 Universe / Scanner、全量歷史搜尋、Portfolio v3 與 Portfolio Refinery。工程目標不是只產生漂亮的歷史績效，而是建立可重現、可稽核、可版本化、可逐步驗證的研究管線。

> **文件權威**：README 回答「這個專案是什麼、怎麼跑、怎麼部署」。最新 Phase / Batch / PR / Blocker / Resume Point 一律以根目錄 [`to_do_update_list.md`](to_do_update_list.md) 為 repository 內的 live handoff；GitHub / Vercel / Cloudflare 的即時遠端狀態是 operational truth。文件分類與衝突處理見 [`docs/PROJECT_DOCUMENTATION_POLICY.md`](docs/PROJECT_DOCUMENTATION_POLICY.md)，完整文件索引見 [`docs/README.md`](docs/README.md)。

## 1. 架構

```text
Browser
  |
  +-- Scanner / Universe
  +-- Exhaustive historical search
  +-- Portfolio v3
  +-- Portfolio Refinery
        |
        v
Cloudflare Worker + Static Assets
  |
  +-- public/                     Scanner / Exhaustive static frontend
  +-- public/portfolio/           Portfolio + Refinery production bundle
  +-- D1 Universe DB              versioned membership / last-good pointer
  +-- request guards / allowlists
  +-- same-origin API proxy
        |
        v
Vercel Python Functions
  |
  +-- Flask compatibility routes
  +-- FastAPI Portfolio v3        api/portfolio_v3.py
  +-- FastAPI Refinery v1         api/refinery_v1.py
        |
        v
apps/api/app/
  +-- data/       TWD market-data / FX / return authority
  +-- portfolio/  path-dependent Portfolio ledger / analytics
  +-- research/   reproducible ResearchDataset / shared research data
  +-- quant/      pure validated quantitative primitives
  +-- refinery/   read-only research composition / evidence policy
```

### 平台角色

- **Cloudflare Static Assets / Worker**：瀏覽器前端、D1 Universe、request/body/method guard、固定 route allowlist、Vercel proxy。
- **Cloudflare D1**：版本化 Universe、來源日期/metadata、checksum 與 current/last-good 指標。
- **Vercel Python Functions**：相容 API、Exhaustive、Portfolio v3、Refinery v1 Python runtime。
- **`apps/api/app/data/`**：市場資料、FX、TWD 估值、return components 的共享權威。
- **`apps/api/app/portfolio/`**：Portfolio v3 ledger 與 path-dependent analytics 權威。
- **`apps/api/app/research/`**：ResearchDataset 與共享 research-data adapter；不得演化成第二套 candidate-price downloader。
- **`apps/api/app/quant/`**：pure math primitives；不得承擔 API/UI/selection/sizing side effects。
- **`apps/api/app/refinery/`**：Refinery request/service/evidence boundary；不得吸收 Portfolio ledger 或未驗證的選股政策。
- **`apps/portfolio-web/`**：Portfolio / Refinery React + TypeScript full-page workspace source；production build 發布到 `/portfolio/`。
- **GitHub Actions**：CI、Release backup、Universe 更新、部署 orchestration；不是應用程式 runtime。

Runtime / quant authority 基線：

- [`docs/PHASE_MINUS1_GOVERNANCE.md`](docs/PHASE_MINUS1_GOVERNANCE.md)
- [`docs/adr/0001-runtime-and-quant-authority.md`](docs/adr/0001-runtime-and-quant-authority.md)

## 2. 研究資料與量化權威

### TWD canonical valuation

跨市場標的保留 native price / FX，再形成 TWD valuation：

```text
TWD adjusted close = native adjusted close × (TWD per native currency unit)
```

正式的台灣投資人風險與跨市場 portfolio research 不得把不同 quote currency 的 return 直接混用。

主要契約：

- [`docs/UNIFIED_TWD_CONTRACT.md`](docs/UNIFIED_TWD_CONTRACT.md)
- [`docs/quant/RETURN_SEMANTICS.md`](docs/quant/RETURN_SEMANTICS.md)
- [`docs/quant/METRIC_AUTHORITY.md`](docs/quant/METRIC_AUTHORITY.md)
- [`docs/quant/RISK_MODEL_POLICY.md`](docs/quant/RISK_MODEL_POLICY.md)

### ResearchDatasetV1

`ResearchDatasetV1` 是 audited TWD history 與後續 research engine 間的 reproducibility boundary，保存 requested/resolved/failure membership、calendar/coverage、daily/weekly matrices、native/FX/TWD components、audits、fingerprints 與 deterministic dataset hash。

詳見 [`docs/research/RESEARCH_DATASET_V1.md`](docs/research/RESEARCH_DATASET_V1.md)。

### Risk Mathematics / Refinery

Covariance、correlation、effective dimension、portfolio risk decomposition、Phase 5 clustering/factor primitives 等 canonical mathematics 位於 `apps/api/app/quant/`；consumer policy 與 pure mathematics 分離。

Research 文件入口：[`docs/research/README.md`](docs/research/README.md)。

## 3. 目錄

```text
api/                         Vercel Python entrypoints / compatibility APIs
apps/api/app/                shared data / portfolio / research / quant / refinery core
apps/portfolio-web/          Portfolio + Refinery React/TypeScript source
public/                      Scanner/Optimizer static frontend + production assets
worker/                      Cloudflare Worker / API router
migrations/                  D1 schema / Universe definitions
tests/                       Python / Node / Playwright regression tests
docs/                        governance / architecture / quant / research / deployment docs
.github/workflows/           CI / backup / Universe update / deployment
scripts/                     smoke tests / Universe utilities
wrangler.jsonc               Cloudflare Worker config
vercel.json                  Vercel route config
```

`apps/api/app/` 目前的 domain 邊界另見 [`apps/api/README.md`](apps/api/README.md)。

## 4. 本機安裝與執行

### 建立 Python / Node 環境

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
npm ci
```

Windows PowerShell 啟用 venv 時可使用：

```powershell
.\.venv\Scripts\Activate.ps1
```

### Legacy / compatibility Flask API

```bash
flask --app api.index_v2 run --port 5000
```

### Portfolio v3 / Refinery v1 FastAPI

Self-owned ASGI entrypoints：

```text
api/portfolio_v3.py   -> /api/v3/portfolio/*
api/refinery_v1.py    -> /api/v1/refinery/*
```

本機可由支援 ASGI 的開發 runtime 匯入對應 `app`；正式 production routing 由 `vercel.json` + Cloudflare Worker allowlist 決定。不要為本機方便新增第三套 API route 或改用 legacy generic endpoint。

### Cloudflare Worker + D1

```bash
cp .dev.vars.example .dev.vars
# 將 BACKEND_ORIGIN 設為對應本機 Python origin
npx --yes wrangler@4 dev
```

第一次本機執行先建立 D1 schema：

```bash
npx wrangler d1 migrations apply backteststock-universe --local
```

`.dev.vars` 不提交 repository。

## 5. 驗證

### Python / quant / API

```bash
python -m compileall -q api apps scripts
ruff check api apps scripts tests
python -m pytest -q
```

### Worker / score / Portfolio web / browser

```bash
npm run check
npm run test:worker
npm run test:score
npm run check:portfolio
npx playwright install chromium
npm run test:e2e
```

### Cloudflare / D1 dry validation

```bash
npx wrangler d1 migrations apply backteststock-universe --local
npx wrangler deploy --dry-run
```

### Universe updater（需要時）

```bash
python scripts/update_universes.py --report /tmp/universe-update-report.json
```

CI 會額外驗證依賴一致性、production assets、Vercel configuration、D1 migration、Cloudflare bundle 等。**本機 PASS 不取代 required GitHub checks。** Production smoke 會依既有部署契約驗證實際 runtime，而不是以「build 理論上可過」代替。

## 6. 個股快速績效掃描 v2

- Universe：S&P 500（IVV holdings 代理）、NASDAQ-100（Global Index Watch → Nasdaq API → QQQM fallback）、SOXX holdings、Russell 2000（IWM holdings 代理）。
- GitHub Actions 定期更新 Universe，也支援手動 workflow。
- 新版本完整寫入/驗證後才切換 current pointer；來源/內容失敗時維持 last-good。
- 預篩選預設納入全部通過條件標的；使用者可再限制數量，不能 silent truncate。
- 手動清單不以 100 檔作整批上限；瀏覽器採批次處理並保存工作進度。
- 股票、投組、基準與 Exhaustive snapshot 以 Yahoo adjusted price × FX-to-TWD 計價；FX-only 日與 no-backfill policy 依 TWD contract。
- 行情採多股票批次優先、逐檔驗證/快取，缺漏再補抓；暫時失敗採 bounded retry/resume。
- 工作狀態保存成功/失敗/未完成，重整後只接續未完成部分。
- coverage/metric version 是明確 evidence，不依 API batch arrival order 決定結果。

詳見 [`docs/UNIVERSE_SCANNER_V2.md`](docs/UNIVERSE_SCANNER_V2.md)。

## 7. Exhaustive historical search

`api/exhaustive_optimizer.py` 是 **full-period historical research/exploration**。同一歷史資料可被搜尋與排名，因此結果不得直接宣稱為 out-of-sample 未來績效證據。

目前 active contract 見 [`docs/EXHAUSTIVE_OPTIMIZER_V3.md`](docs/EXHAUSTIVE_OPTIMIZER_V3.md)。`docs/OPTIMIZER_IMPLEMENTATION_STATUS.md` 僅保留為 rollout 歷史快照，不是 live status authority。

## 8. Portfolio v3

Portfolio v3 是 self-owned production path，使用嚴格 request/response contract、TWD Portfolio ledger、現金流、配息、再平衡、槓桿、tail-risk 與 analytics；正式頁面位於 `/portfolio/`。

Portfolio 與 Scanner/Exhaustive 共用 `apps/api/app/data/` 的 TWD 資料契約，但 Portfolio ledger/metrics 保有 path-dependent domain semantics，不可被 Refinery 當成 generic data bag。

## 9. Portfolio Refinery

Refinery 是與 Portfolio ledger 分離的 **read-only research/diagnostic domain**。它以 ResearchDataset + Risk Mathematics 為基礎，逐 Phase 增加 evidence：

```text
ResearchDataset
  -> Risk Mathematics
      -> Refinery API
          -> risk / covariance / correlation diagnostics
          -> clustering / redundancy / factor / theme evidence
```

在完成 walk-forward/OOS 與 selection governance 前，不輸出帶有未來績效暗示的 KEEP/TRIM/REPLACE、selection 或 sizing 結論。

Current contracts / review status 見 [`docs/research/README.md`](docs/research/README.md)；**即時 Phase 狀態仍以 `to_do_update_list.md` 為準。**

## 10. 部署

### Vercel backend

`vercel.json` 配置 legacy/compatibility、Exhaustive、Portfolio v3 與 Refinery v1 Python entrypoints。

常見環境設定依對應功能/部署文件為準；既有相容路徑可能使用：

- `GIST_RAW_URL`：部分 screener/ticker autocomplete 路徑可選來源。
- `RISK_FREE_RATE`：相容 metric path 的年化無風險利率，小數格式，預設依程式/部署契約。
- Portfolio analytics 所需外部資料 key 依 `docs/DEPLOYMENT.md` 與實際 feature contract 設定。

不要把 token/key 寫入 repository、README example value 或 client bundle。

### Cloudflare Worker

`wrangler.jsonc` 的 `BACKEND_ORIGIN` 指向 Vercel origin，值不要附加 `/api`。

部署所需 GitHub secrets 依現有 workflow / deployment 文件配置，例如 Cloudflare account/token credentials。

完整 production smoke / rollback / environment 說明見 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)。

## 11. 文件閱讀順序

新的 ChatGPT / Codex / Agent 接手時：

1. [`AI_PROJECT_PLAYBOOK.md`](AI_PROJECT_PLAYBOOK.md) — 工程最高規範。
2. `README.md` — 產品、架構、run/test/deploy 概覽。
3. [`to_do_update_list.md`](to_do_update_list.md) — **目前真實進度與 exact resume point**。
4. [`docs/PROJECT_DOCUMENTATION_POLICY.md`](docs/PROJECT_DOCUMENTATION_POLICY.md) — 文件 precedence / freshness / version discipline。
5. [`docs/README.md`](docs/README.md) / [`docs/research/README.md`](docs/research/README.md) — deeper contract navigation。
6. 當前 Phase 對應 contract / ADR / tests。
7. 重新查詢 GitHub current `main`、active PR、checks、ruleset、release/deployment state。

若 live roadmap 與遠端狀態衝突，不可猜測；先把它視為 documentation drift 並重新取證。

## 12. Governance / merge policy

- `main` 視為 potential production candidate。
- runtime / quant methodology 變更走 non-main branch + PR。
- required checks、backup gate、independent review、expected-head merge、post-main verification 依 playbook / live roadmap 執行。
- 不因 CI quota、preview deployment 限制或方便性移除 safety gate。
- externally observable methodology/schema change 必須 versioned，並同步 code、tests、contract、roadmap。
- GitHub ruleset 的**實際設定**是遠端 operational state，合併前需重新查詢；README 不硬編碼會變動的 approvals/strictness 數值。

## 13. 安全與研究限制

- 不提供會輸出環境變數/secret 的 debug endpoint。
- 不將 Cloudflare、Vercel 或資料來源 token 寫入 repository。
- API 使用 input/date/weight/body/response/resource guards；超限或資料不完整時 fail closed，而不是 silent fallback。
- Yahoo/yfinance 與目前 Universe history 適合研究/教育用途；歷史搜尋不等於未來報酬保證。
- full-period historical search / descriptive Refinery evidence 不等於 OOS evidence。
- 在 point-in-time Universe / fundamentals 完整前，不宣稱消除了 survivorship / look-ahead bias。
- unavailable evidence 不得轉成有效的 0，也不得 silent fallback 成另一套資料、calendar、currency、membership 或 factor model。
