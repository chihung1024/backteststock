# BacktestStock Documentation Index

`docs/` 保存解決實際工程問題時才需要的知識：architecture、contracts、runbooks、RCA、research methodology、closeouts 與歷史證據。它不是第二套治理系統。

## Active work

目前工作只需要依序取得：

`AGENTS.md → to_do_update_list.md → relevant code/contracts/docs → current Git/PR/CI/runtime truth`

- `../AGENTS.md` — 唯一 Active Governance。
- `../to_do_update_list.md` — 唯一持續執行記憶：CURRENT / NEXT / ROADMAP / durable decisions-risks。
- `../README.md` — 產品、架構、開發、測試與部署導覽。
- `DEPLOYMENT.md` — deployment / production 操作需要時才讀的 runbook。
- `research/README.md` — research / Walk-Forward / Refinery contracts 導覽。

Remote/runtime truth 高於 stale status prose；versioned contracts/tests/code 共同定義 semantic truth。若三者漂移，視為工程缺陷，不以舊文件猜測。

## Canonical technical documents

- `adr/0001-runtime-and-quant-authority.md` — durable runtime/quant architecture decision。
- `UNIFIED_TWD_CONTRACT.md` — cross-market TWD valuation contract。
- `METRICS_REPRODUCIBILITY.md` — metric reproducibility/provenance。
- `PORTFOLIO_V3_CONTRACT.md` — Portfolio v3 ledger/API/analytics semantics。
- `UNIVERSE_SCANNER_V2.md` — Scanner/Universe behavior。
- `EXHAUSTIVE_OPTIMIZER_V3.md` — exhaustive historical-search contract。
- `quant/` — metric/return/risk mathematics contracts。
- `research/` — ResearchDataset / Walk-Forward / Refinery / Optimizer Hub contracts and evidence。

## Documentation rule

優先更新既有權威文件。只有內容具有獨立長期價值時才新增 durable document，例如 contract/specification、architecture decision、reusable runbook、material RCA、methodology evidence 或重要 closeout evidence。

不要為 transient hypothesis、單次 CI、每個 shell command、一般 formatting 或重複摘要建立新文件。

歷史紀錄保留其當時事實，不為了配合現在架構而重寫；current execution state 回到 `to_do_update_list.md`，即時事實回到 Git/PR/CI/runtime。

Machine-readable tests、deployment controls、security/data/quant invariants 不因 prose governance 簡化而移除。