# BacktestStock

BacktestStock 是一個以 **TWD 統一估值**為核心的多市場投資研究平台，包含 Universe / Scanner、Exhaustive historical search、Portfolio v3 與 Portfolio Refinery。

> **文件權威**：本 README 回答「專案是什麼、怎麼跑、怎麼測、怎麼部署」。目前 Phase / Batch / PR / blocker / exact resume point 以 [`to_do_update_list.md`](to_do_update_list.md) 為 repository 內的 live handoff；GitHub / Vercel / Cloudflare 的即時遠端狀態是 operational truth。文件分類與衝突處理見 [`docs/PROJECT_DOCUMENTATION_POLICY.md`](docs/PROJECT_DOCUMENTATION_POLICY.md)，完整索引見 [`docs/README.md`](docs/README.md)。

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
  +-- research/   reproducible ResearchDataset / research data
  +-- quant/      pure validated quantitative primitives
  +-- refinery/   read-only research composition / evidence policy
```

### 平台角色

- **Cloudflare Static Assets / Worker**：瀏覽器前端、D1 Universe、request/body/method guard、固定 route allowlist、Vercel proxy。
- **Cloudflare D1**：版本化 Universe、來源日期/metadata、checksum 與 current/last-good pointer。
- **Vercel Python Functions**：相容 API、Exhaustive、Portfolio v3、Refinery v1 Python runtime。
- **`apps/api/app/data/`**：市場資料、FX、TWD 估值、return components 的共享權威。
- **`apps/api/app/portfolio/`**：Portfolio v3 ledger 與 path-dependent analytics 權威。
- **`apps/api/app/research/`**：ResearchDataset 與共享 research-data adapter；不得演化成第二套 candidate-price downloader。
- **`apps/api/app/quant/`**：pure math primitives；不得承擔 API/UI/selection/sizing side effects。
- **`apps/api/app/refinery/`**：Refinery request/service/evidence boundary；不得吸收 Portfolio ledger 或未驗證選股政策。
- **`apps/portfolio-web/`**：Portfolio / Refinery React + TypeScript full-page workspace source；production build 發布到 `/portfolio/`。
- **GitHub Actions**：CI、Release backup、Universe 更新、部署 orchestration；不是應用程式 runtime。

Durable runtime/quant architecture decision 見 [`docs/adr/0001-runtime-and-quant-authority.md`](docs/adr/0001-runtime-and-quant-authority.md)。已完成的早期 phase-governance 快照由 Git history 保存，不再作為 live-tree authority。

## 2. 研究資料與量化權威

### TWD canonical valuation

跨市場標的保留 native price / FX，再形成 TWD valuation：

```text
TWD adjusted close = native adjusted close × (TWD per native currency unit)
```

主要契約：

- [`docs/UNIFIED_TWD_CONTRACT.md`](docs/UNIFIED_TWD_CONTRACT.md)
- [`docs/quant/RETURN_SEMANTICS.md`](docs/quant/RETURN_SEMANTICS.md)
- [`docs/quant/METRIC_AUTHORITY.md`](docs/quant/METRIC_AUTHORITY.md)
- [`docs/quant/RISK_MODEL_POLICY.md`](docs/quant/RISK_MODEL_POLICY.md)
- [`docs/quant/RISK_MATHEMATICS_V1.md`](docs/quant/RISK_MATHEMATICS_V1.md)

### ResearchDataset / Refinery

`ResearchDatasetV1` 是 audited TWD history 與 research engine 間的 reproducibility boundary，保存 requested/resolved/failure membership、calendar/coverage、daily/weekly matrices、native/FX/TWD components、audits、fingerprints 與 deterministic dataset hash。

Research contract 入口：[`docs/research/README.md`](docs/research/README.md)。

## 3. 目錄

```text
api/                         Vercel Python entrypoints / compatibility APIs
apps/api/app/                shared data / portfolio / research / quant / refinery core
apps/portfolio-web/          Portfolio + Refinery React/TypeScript source
public/                      Scanner/Optimizer static frontend + production assets
worker/                      Cloudflare Worker / API router
migrations/                  D1 schema / Universe definitions
tests/                       Python / Node / Playwright regression tests
docs/                        architecture / quant / research / deployment docs
.github/workflows/           CI / backup / Universe update / deployment
scripts/                     smoke tests / Universe utilities
wrangler.jsonc               Cloudflare Worker config
vercel.json                  Vercel route config
```

## 4. 本機安裝與執行

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
npm ci
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

### Legacy / compatibility Flask API

```bash
flask --app api.index_v2 run --port 5000
```

### Self-owned FastAPI entrypoints

```text
api/portfolio_v3.py   -> /api/v3/portfolio/*
api/refinery_v1.py    -> /api/v1/refinery/*
```

正式 production routing 由 `vercel.json` + Cloudflare Worker allowlist 決定。

### Cloudflare Worker + D1

```bash
cp .dev.vars.example .dev.vars
# 將 BACKEND_ORIGIN 設為對應本機 Python origin
npx --yes wrangler@4 dev
```

第一次本機執行：

```bash
npx wrangler d1 migrations apply backteststock-universe --local
```

`.dev.vars` 不提交 repository。

## 5. 驗證

```bash
python -m compileall -q api apps scripts
ruff check api apps scripts tests
python -m pytest -q
npm run check
npm run test:worker
npm run test:score
npm run check:portfolio
npx playwright install chromium
npm run test:e2e
npx wrangler d1 migrations apply backteststock-universe --local
npx wrangler deploy --dry-run
```

本機 PASS 不取代 required GitHub checks。驗證強度與 merge/review gate 依 [`AI_PROJECT_PLAYBOOK.md`](AI_PROJECT_PLAYBOOK.md) 的 V3.0 risk-proportional governance 執行。

## 6. Scanner / Universe

- Universe：S&P 500（IVV holdings 代理）、NASDAQ-100（Global Index Watch → Nasdaq API → QQQM fallback）、SOXX holdings、Russell 2000（IWM holdings 代理）。
- GitHub Actions 定期更新 Universe，也支援手動 workflow。
- 新版本完整寫入/驗證後才切換 current pointer；來源/內容失敗時維持 last-good。
- 預篩選不能 silent truncate；手動清單採批次處理並保存工作進度。
- 股票、投組、基準與 Exhaustive snapshot 使用 TWD valuation contract。

詳見 [`docs/UNIVERSE_SCANNER_V2.md`](docs/UNIVERSE_SCANNER_V2.md)。

## 7. Exhaustive historical search

`api/exhaustive_optimizer.py` 是 **full-period historical research/exploration**。同一歷史資料被搜尋與排名，因此結果不得直接宣稱為 out-of-sample 未來績效證據。

目前 active contract：[`docs/EXHAUSTIVE_OPTIMIZER_V3.md`](docs/EXHAUSTIVE_OPTIMIZER_V3.md)。已停用的 MVP、V2 history 與 rollout status 不再保留在 live documentation tree；需要歷史時由 Git history reconstruct。

## 8. Portfolio v3

Portfolio v3 是 self-owned production path，使用嚴格 request/response contract、TWD Portfolio ledger、現金流、配息、再平衡、槓桿、tail-risk 與 analytics；正式頁面位於 `/portfolio/`。

Portfolio 與 Scanner/Exhaustive 共用 `apps/api/app/data/` 的 TWD 資料契約，但 Portfolio ledger/metrics 保有 path-dependent domain semantics。

`docs/portfolio-migration/README.md` 僅保留 frozen source provenance；`PR2_LEDGER_METRICS.md` 與 `PR3_PORTFOLIO_V3_API.md` 暫留作尚未完全被專屬 current contract 取代的 ledger/API migration semantics。PR4–PR6 rollout/cutover 敘述已由 Git history、現行 implementation 與永久 regression tests 取代。

## 9. Portfolio Refinery

Refinery 是與 Portfolio ledger 分離的 **read-only research/diagnostic domain**，以 ResearchDataset + Risk Mathematics 為基礎逐 Phase 增加 evidence。

在完成 later validation / selection governance 前，不輸出未經驗證的 KEEP/TRIM/REPLACE、selection、sizing 或 forward-performance 結論。

Current main contracts / active review work見 [`docs/research/README.md`](docs/research/README.md) 與 root `to_do_update_list.md`。

## 10. 部署

### Vercel backend

`vercel.json` 配置 compatibility、Exhaustive、Portfolio v3 與 Refinery v1 Python entrypoints。Token/key 不得寫入 repository、README example value 或 client bundle。

### Cloudflare Worker

`wrangler.jsonc` 的 `BACKEND_ORIGIN` 指向 Vercel origin，值不要附加 `/api`。

完整 production smoke / rollback / environment 說明見 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)。

## 11. 文件閱讀順序

新的 ChatGPT / Codex / Agent 接手時：

1. [`AI_PROJECT_PLAYBOOK.md`](AI_PROJECT_PLAYBOOK.md)
2. `README.md`
3. [`to_do_update_list.md`](to_do_update_list.md)
4. [`docs/PROJECT_DOCUMENTATION_POLICY.md`](docs/PROJECT_DOCUMENTATION_POLICY.md)
5. [`docs/README.md`](docs/README.md) / [`docs/research/README.md`](docs/research/README.md)
6. 當前 Phase 對應 contract / ADR / tests
7. 重新查詢 GitHub current main、active PR、checks、ruleset、release/deployment state

若 live roadmap 與 remote state 衝突，先分類 documentation drift 並重新取證，不可猜測。

## 12. Governance

- `AI_PROJECT_PLAYBOOK.md` V3.0 是工程治理 authority，並處於 Governance Freeze。
- `main` 視為 potential production candidate。
- Risk Class 決定 validation/review/backup/deployment gate，不以檔案類型或 diff 大小機械判定。
- Independent Review 的核心是 independent reasoning + relevant competence，不是不同 GitHub 帳號。
- Required check、security/data-integrity gate 不得為了方便或 quota 問題偷偷 bypass。
- Externally observable methodology/schema change 必須 versioned，並同步 code、tests、contract、roadmap。

## 13. 安全與研究限制

- 不提供會輸出環境變數的 debug endpoint。
- 不將 Cloudflare、Vercel 或資料來源 token 寫進 repository。
- API 有 request/date/weight/resource guards；失敗不能 silent delete ticker、shorten period 或把 unavailable 變成 zero。
- Yahoo/yfinance 與目前 Universe history 適合研究/教育用途；歷史搜尋不等於未來報酬保證。
- 尚未具備完整 point-in-time Universe/fundamental history 的期間，不應宣稱消除了 survivorship/look-ahead bias。
