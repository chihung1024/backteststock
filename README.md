# BacktestStock

BacktestStock 是以 **TWD 統一估值**為核心的多市場投資研究平台，包含 Universe / Scanner、Exhaustive historical search、Portfolio v3、Portfolio Refinery、Walk-Forward Research 與 Optimizer Hub。

工程工作原則以 [`AGENTS.md`](AGENTS.md) 為唯一 Active Governance；目前 Goal / Batch / blocker / resume point 以 [`to_do_update_list.md`](to_do_update_list.md) 為持續執行記憶；GitHub / Vercel / Cloudflare / runtime 是 operational truth。技術文件索引見 [`docs/README.md`](docs/README.md)。

## 1. 架構

```text
Browser
  ├─ Scanner / Universe
  ├─ Exhaustive historical search
  └─ /portfolio/
       ├─ Portfolio v3
       ├─ Portfolio Refinery
       └─ Walk-Forward / Optimizer Hub
            |
            v
Cloudflare Worker + Static Assets
  ├─ D1 Universe / PIT / ResearchRun
  ├─ request guards / route allowlists
  └─ same-origin proxy
            |
            v
Vercel Functions
  ├─ compatibility APIs
  ├─ Exhaustive authority placement
  ├─ Walk-Forward v1
  ├─ Portfolio v3
  └─ Refinery v1
            |
            v
apps/api/app/
  ├─ data/       market data / FX / TWD authority
  ├─ portfolio/  path-dependent ledger / analytics
  ├─ research/   ResearchDataset / Walk-Forward / Optimizer Hub
  ├─ quant/      pure validated quantitative primitives
  └─ refinery/   read-only diagnostic composition
```

主要責任：

- **Cloudflare Worker / Static Assets**：瀏覽器入口、D1、same-origin routing、request guards。
- **Cloudflare D1**：版本化 Universe/PIT evidence 與 ResearchRun memory。
- **Vercel**：Python/Node serverless API/authority placement。
- **`apps/api/app/data/`**：市場資料、FX、TWD 估值與 return components。
- **`apps/api/app/portfolio/`**：Portfolio v3 ledger 與 path-dependent analytics。
- **`apps/api/app/research/`**：ResearchDataset、Walk-Forward、configured strategy / tuning orchestration。
- **`apps/api/app/quant/`**：pure math；不得承擔 HTTP/UI/storage/hidden selection policy。
- **`apps/api/app/refinery/`**：read-only diagnostic/evidence domain。
- **`apps/portfolio-web/`**：Portfolio / Refinery / Walk-Forward React + TypeScript source。
- **GitHub Actions**：CI、Universe update、Cloudflare deploy、Walk-Forward production verification。

Durable architecture decision：[`docs/adr/0001-runtime-and-quant-authority.md`](docs/adr/0001-runtime-and-quant-authority.md)。

## 2. Quant / data authorities

### TWD canonical valuation

```text
TWD adjusted close = native adjusted close × (TWD per native currency unit)
```

核心契約：

- [`docs/UNIFIED_TWD_CONTRACT.md`](docs/UNIFIED_TWD_CONTRACT.md)
- [`docs/quant/METRIC_AUTHORITY.md`](docs/quant/METRIC_AUTHORITY.md)
- [`docs/quant/RETURN_SEMANTICS.md`](docs/quant/RETURN_SEMANTICS.md)
- [`docs/quant/RISK_MODEL_POLICY.md`](docs/quant/RISK_MODEL_POLICY.md)
- [`docs/quant/RISK_MATHEMATICS_V1.md`](docs/quant/RISK_MATHEMATICS_V1.md)

`ResearchDatasetV1` 是 audited TWD history 與 research engines 間的 reproducibility boundary；它保存 requested/resolved/failure membership、calendar/coverage、native/FX/TWD evidence、audits、fingerprints 與 deterministic dataset identity。

Research contracts：

- [`docs/research/RESEARCH_DATASET_V1.md`](docs/research/RESEARCH_DATASET_V1.md)
- [`docs/research/WALK_FORWARD_CONTRACT.md`](docs/research/WALK_FORWARD_CONTRACT.md)
- [`docs/research/OPTIMIZER_HUB_CONTRACT.md`](docs/research/OPTIMIZER_HUB_CONTRACT.md)
- [`docs/research/REFINERY_CONTRACT.md`](docs/research/REFINERY_CONTRACT.md)
- [`docs/research/RESEARCH_RUN_MEMORY_V1.md`](docs/research/RESEARCH_RUN_MEMORY_V1.md)

## 3. 目錄

```text
api/                         Vercel entrypoints / compatibility APIs
apps/api/app/                shared data / portfolio / research / quant / refinery core
apps/portfolio-web/          Portfolio + Refinery + Walk-Forward React source
public/                      Scanner/Exhaustive static frontend + built Portfolio assets
worker/                      Cloudflare Worker / D1 / API router
migrations/                  D1 schema history
tests/                       Python / Node / Playwright regressions
docs/                        durable architecture / contract / runbook documentation
.github/workflows/           CI / Universe update / deployment verification
scripts/                     smoke tests / Universe utilities
wrangler.jsonc               Cloudflare config
vercel.json                  Vercel route/build config
```

## 4. 本機安裝

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

Compatibility Flask API：

```bash
flask --app api.index_v2 run --port 5000
```

Cloudflare Worker + D1：

```bash
cp .dev.vars.example .dev.vars
npx --yes wrangler@4 dev
npx wrangler d1 migrations apply backteststock-universe --local
```

`.dev.vars` 不提交 repository。

## 5. 驗證

Broad integration baseline：

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

實際修改依風險先做 targeted verification，再做 relevant integration checks。沒有驗證不宣稱完成。

## 6. Scanner / Universe

Universe publishing 使用 versioned D1 data、publish-after-validation 與 last-good pointer。Current-snapshot 與 PIT historical membership 是不同研究語意；PIT 不會用 current membership/fundamentals 冒充歷史 evidence。

Scanner 大清單採 bounded batching，但不把 batching 當成語意截斷。失敗 ticker、benchmark failure、coverage 與 pending work均明示。

詳見 [`docs/SCANNER_CONTRACT.md`](docs/SCANNER_CONTRACT.md)。

## 7. Exhaustive historical search

`api/exhaustive_optimizer.py` / existing JavaScript exact authority 是 **full-period historical research/search**。

同一段歷史資料被搜尋與排名，因此 full-period winner 不得直接宣稱為 out-of-sample 未來績效證據。

契約：[`docs/EXHAUSTIVE_OPTIMIZER_V3.md`](docs/EXHAUSTIVE_OPTIMIZER_V3.md)。

## 8. Portfolio v3

Portfolio v3 是 path-dependent TWD portfolio authority，涵蓋 ledger、cash flow、distribution、rebalance、leverage、transaction costs、tail risk 與 analytics。

契約：[`docs/PORTFOLIO_V3_CONTRACT.md`](docs/PORTFOLIO_V3_CONTRACT.md)。

## 9. Walk-Forward / Optimizer Hub

Walk-Forward 的核心因果關係：

```text
Training → frozen Decision → Evaluation/OOS
```

Evaluation/OOS 不得影響同一 Decision 的 selection/allocation/tuning。

Optimizer Hub 在同一 causal boundary 上提供 configured Dual Momentum、Equal / Inverse Volatility / ERC allocation 與 bounded nested parameter optimization。所有 accepted numerical results 由 backend authorities 產生；Browser/AI 不成為第二套計算權威。

詳見：

- [`docs/research/WALK_FORWARD_CONTRACT.md`](docs/research/WALK_FORWARD_CONTRACT.md)
- [`docs/research/OPTIMIZER_HUB_CONTRACT.md`](docs/research/OPTIMIZER_HUB_CONTRACT.md)

## 10. Portfolio Refinery

Refinery 是與 Portfolio ledger 分離的 **read-only diagnostic/research domain**。

目前可提供 covariance/correlation/risk、clustering/redundancy、factor/theme availability 與 explicit marginal structural experiments；它不把 HIGH/MEDIUM/LOW evidence 轉成 BUY/SELL/KEEP/TRIM/REPLACE，也不在 browser 重算 quantitative evidence。

契約：[`docs/research/REFINERY_CONTRACT.md`](docs/research/REFINERY_CONTRACT.md)。

## 11. Deployment

`vercel.json` 定義 serverless builds/routes；Cloudflare Worker 負責 production edge/static/D1 routing。

完整部署、smoke、secrets、rollback：[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)。

## 12. AI 接手順序

```text
AGENTS.md
→ to_do_update_list.md
→ only relevant README/contracts/tests
→ current main / active PR / CI / runtime truth
→ resume exact work
```

不要為接手而重建整個歷史 Master Plan。

## 13. Research / security limitations

- 不提供會輸出環境變數的 debug endpoint。
- 不把 Cloudflare、Vercel 或資料來源 token 寫進 repository/client bundle。
- API failure 不得 silent delete ticker、shorten period 或把 unavailable 變成 zero。
- Yahoo/yfinance/public Universe data 適合研究用途，但上游資料可能事後修訂。
- `Adj Close`/公司行為調整不等於已消除 survivorship、look-ahead 或 delisting bias。
- 沒有完整 PIT fundamentals 的期間，不宣稱已消除該類歷史選股偏誤。
