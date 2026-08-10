# BacktestStock

BacktestStock 是一個以 **TWD 統一估值**為核心的多市場投資研究平台，包含 Universe / Scanner、全量歷史搜尋、Portfolio v3 與 Portfolio Refinery。專案的工程目標不是單純產生漂亮的歷史績效，而是建立可重現、可稽核、可版本化、可逐步驗證的研究管線。

> **狀態來源**：README 只描述產品、架構與操作方式，不作為即時開發進度的權威來源。最新 Phase / Batch / PR / Blocker / Resume Point 一律以根目錄 [`to_do_update_list.md`](to_do_update_list.md) 為準；GitHub 遠端 branch / PR / checks 是執行狀態的最終事實來源。

## 1. 系統架構

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
  +-- D1 Universe DB
  +-- request guards / route allowlists
  +-- same-origin proxy
        |
        v
Vercel Python Functions
  |
  +-- legacy / compatibility Flask routes
  +-- Portfolio v3 FastAPI
  +-- Refinery v1 FastAPI
        |
        v
apps/api/app/
  +-- data/       TWD market-data / FX / return authority
  +-- portfolio/  path-dependent portfolio ledger / analytics
  +-- research/   reproducible research datasets / shared research data
  +-- quant/      pure validated quantitative primitives
  +-- refinery/   read-only research composition / evidence policy
```

### 平台角色

- **Cloudflare Static Assets / Worker**：前端、D1 Universe、request guard、固定路由 allowlist、Vercel proxy。
- **Cloudflare D1**：版本化 Universe、來源資訊、checksum 與 current/last-good 指標。
- **Vercel Python Functions**：Python API runtime；包含相容路徑、Portfolio v3、Refinery v1。
- **`apps/api/app/data/`**：市場資料、FX、TWD 估值、return components 的共享權威。
- **`apps/api/app/portfolio/`**：Portfolio v3 ledger 與 path-dependent analytics 權威。
- **`apps/api/app/research/`**：ResearchDataset 與共享 research data provider；不得演化成第二套市場資料 downloader。
- **`apps/api/app/quant/`**：純數學 primitives；不得承擔 API/UI/selection/sizing side effects。
- **`apps/api/app/refinery/`**：Refinery request/service/evidence boundary；不得吸收 Portfolio ledger 或未驗證的選股政策。
- **`apps/portfolio-web/`**：Portfolio / Refinery React + TypeScript full-page workspace。
- **GitHub Actions**：CI、backup gate、Universe 更新、deployment orchestration；不是 runtime。

核心 runtime/quant boundary 請見：

- [`docs/PHASE_MINUS1_GOVERNANCE.md`](docs/PHASE_MINUS1_GOVERNANCE.md)
- [`docs/adr/0001-runtime-and-quant-authority.md`](docs/adr/0001-runtime-and-quant-authority.md)
- [`docs/PROJECT_DOCUMENTATION_POLICY.md`](docs/PROJECT_DOCUMENTATION_POLICY.md)

## 2. 研究資料與量化權威

### TWD canonical valuation

跨市場標的先保留 native price / FX，再形成 TWD valuation。正式的台灣投資人風險與跨市場 portfolio research 不得把不同 quote currency 的 return 直接混用。

主要契約：

- [`docs/UNIFIED_TWD_CONTRACT.md`](docs/UNIFIED_TWD_CONTRACT.md)
- [`docs/quant/RETURN_SEMANTICS.md`](docs/quant/RETURN_SEMANTICS.md)
- [`docs/quant/METRIC_AUTHORITY.md`](docs/quant/METRIC_AUTHORITY.md)
- [`docs/quant/RISK_MODEL_POLICY.md`](docs/quant/RISK_MODEL_POLICY.md)

### ResearchDatasetV1

`ResearchDatasetV1` 是 audited TWD history 與後續 research engine 間的 reproducibility boundary，保存 requested/resolved/failure membership、calendar/coverage、daily/weekly matrices、native/FX/TWD components、audits、fingerprints 與 deterministic dataset hash。

詳見 [`docs/research/RESEARCH_DATASET_V1.md`](docs/research/RESEARCH_DATASET_V1.md)。

### Risk Mathematics

Covariance、correlation、effective dimension、portfolio risk decomposition 等數學 primitives 由 `apps/api/app/quant/` 管理，consumer policy 與 pure mathematics 分離。

詳見 [`docs/quant/RISK_MATHEMATICS_V1.md`](docs/quant/RISK_MATHEMATICS_V1.md)。

## 3. 產品面

### Scanner / Universe

- S&P 500、NASDAQ-100、SOXX、Russell 2000 代理 Universe。
- D1 使用版本化 snapshot 與 current/last-good semantics。
- 大量標的採批次取得、逐檔驗證、retry/resume 與 explicit failure accounting。
- coverage threshold 與 metric versions 可追蹤，不以 arrival order 決定結果。

詳見 [`docs/UNIVERSE_SCANNER_V2.md`](docs/UNIVERSE_SCANNER_V2.md)。

### Exhaustive historical search

`api/exhaustive_optimizer.py` 是 **full-period historical research/exploration**。同一歷史資料可同時被搜尋與排名，因此結果不得直接宣稱為 out-of-sample 未來績效證據。

詳見 [`docs/EXHAUSTIVE_OPTIMIZER_V3.md`](docs/EXHAUSTIVE_OPTIMIZER_V3.md)。

### Portfolio v3

Self-owned TWD portfolio path，提供 cash-flow/ledger、配息、再平衡、槓桿、tail-risk 與 analytics；正式頁面位於 `/portfolio/`。

### Portfolio Refinery

Refinery 是與 Portfolio ledger 分離的 **read-only research/diagnostic domain**。它以 ResearchDataset + Risk Mathematics 為基礎，逐 Phase 增加 evidence，但在完成 walk-forward/OOS 與 selection governance 前，不應輸出帶有未來績效暗示的選股結論。

研究文件索引：[`docs/research/README.md`](docs/research/README.md)。

## 4. 文件權威與閱讀順序

新的 ChatGPT / Codex / Agent 接手時，最少依序閱讀：

1. [`AI_PROJECT_PLAYBOOK.md`](AI_PROJECT_PLAYBOOK.md) — 工程最高規範。
2. `README.md` — 產品、架構、執行與部署概覽。
3. [`to_do_update_list.md`](to_do_update_list.md) — **目前真實進度與 exact resume point**。
4. [`docs/PROJECT_DOCUMENTATION_POLICY.md`](docs/PROJECT_DOCUMENTATION_POLICY.md) — 文件類型、precedence、staleness 規則。
5. 當前 Phase 對應的 contract / ADR / tests。
6. GitHub current `main`、active PR、checks、ruleset、release/deployment 狀態。

若文件與 GitHub 遠端狀態衝突，不可猜測：先以遠端事實確認 drift，再更新 handoff 文件。

## 5. 目錄

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

## 6. 本機安裝與驗證

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
npm ci
```

### Python / quant / API

```bash
python -m compileall -q api apps scripts
ruff check api apps scripts tests
python -m pytest -q
```

### Worker / browser / Portfolio web

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

CI 是正式驗證證據；本機 PASS 不得取代 required GitHub checks。

## 7. 部署

### Vercel

`vercel.json` 定義 compatibility、Exhaustive、Portfolio v3 與 Refinery v1 Python entrypoints。部署相關環境變數、smoke 與 rollback 見 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)。

### Cloudflare

`wrangler.jsonc` 的 `BACKEND_ORIGIN` 指向 Vercel origin；Worker 負責 route guards、D1、static assets 與 same-origin proxy。

## 8. Governance / merge policy

- `main` 視為 potential production candidate。
- runtime / quant methodology 變更走 non-main branch + PR。
- required checks、backup gate、independent review、expected-head merge 與 post-main verification 依 playbook / roadmap 執行。
- 不因 CI quota、preview deployment 限制或方便性而直接移除安全 gate。
- 任何 externally observable methodology/schema change 必須 versioned，並同步 code、tests、contract、roadmap。

## 9. 研究限制

- Yahoo/yfinance 與現有 Universe history 適合研究/教育用途；不是未來報酬保證。
- full-period historical search 不等於 OOS evidence。
- 在 point-in-time Universe / fundamentals 完整前，不宣稱消除了 survivorship / look-ahead bias。
- unavailable evidence 不得轉成有效的 0，也不得 silent fallback 成另一套資料、calendar、currency、membership 或 factor model。
