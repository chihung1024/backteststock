# Project Execution Memory

本文件是 BacktestStock 的持續執行記憶。

原則：CURRENT 要精確；NEXT 要有順序；ROADMAP 可隨新證據調整；歷史持續壓縮。Git / PR / CI / Vercel / Cloudflare / runtime truth 高於本文件中的舊快照。

Last updated: **2026-08-19 Asia/Taipei**

## CURRENT

**Primary Goal**
- 以已 production-accepted 的 Optimizer Hub 4B-3 為穩定基線，從最新使用者價值與 current evidence 選擇下一個單一產品能力；不因舊 roadmap 自動展開方法論或基礎設施。

**Current Batch**
- NONE — Phase 4B-3 Nested Parameter Optimization V1 已 CLOSED / MERGED / PRODUCTION ACCEPTED。

**Stable State**
- Accepted product main: `e58245d153b3ce1c87a6b5cc8abda22743d69a03`。
- PR #177 已 squash-merged；4B-3 bounded nested parameter optimization 已進入 `main`。
- PR #147 維持 frozen / deferred，不屬目前 implementation 主線。

**Branch / PR / HEAD**
- Branch: `main`
- PR #177: MERGED
- Accepted product HEAD: `e58245d153b3ce1c87a6b5cc8abda22743d69a03`

**Verified**
- Candidate exact head `8c2eedc06ca6a557948fd436e5db1517b00d2e0a`：GitHub CI #962 / run `32198984484` SUCCESS。
- Candidate exact-head Vercel status：SUCCESS。
- Fresh first-principles adversarial review：`BLOCKER = 0`；review identity 不再要求另一個 GitHub 帳號，重點是 fresh evidence + independent reasoning。
- Post-main exact SHA `e58245d...`：Vercel SUCCESS。
- Cloudflare deployment #85 / run `32230232134`：SUCCESS；D1 migration、Worker/static deploy、Russell 2000、Portfolio v3、Walk-Forward v1 routing、Refinery v1 production smokes 全部 SUCCESS。

**Blocker**
- NONE known。

**Exact Next Action**
- 下一個產品 Batch 開始前，重新查詢 current `main` / open PR / runtime truth，依使用者直接價值與 evidence 從 roadmap candidates 中選 **一個** user-facing capability；先定義最小可驗證目標，再進入單一 Loop Engineering implementation。

## NEXT

1. [ ] 重新評估 4B-4 Robust Objective / Pareto Lab 是否仍是最高使用者價值；若是，收斂成一個最小 user-facing Batch，而不是一次實作整個 roadmap。
2. [ ] 若有更直接的 Optimizer Hub / AI-automation 使用者需求，以最新需求優先並更新 ROADMAP。
3. [ ] 只有實際阻塞功能、correctness、PIT/Walk-Forward causality、data/security 或 deployment 的技術工作才提升為 NOW。

## ROADMAP

### Near Term
- 保持 Optimizer Hub 的 Dual Momentum + Allocation + bounded parameter optimization 為穩定、可重播、因果正確的研究基線。
- 下一個能力以「使用者能做什麼新的、有價值的研究」為主，不以增加 optimizer / framework / infra 數量為目標。
- 4B-4 Robust Objective / Pareto Lab 保留為優先候選：透明 constraints / Pareto / fold stability，而不是 opaque universal score。

### Later
- Allocation expansion、rebalance/execution optimization、stable ensemble、AI Research Autopilot 依實際需求與 evidence 逐步提升。
- 需要擴大 practical workload ceiling 時，先取得新的 empirical capacity evidence；不預先引入 queue/distributed infrastructure。

### Candidates
- PR #147 edge-perimeter hardening 維持 frozen/deferred；只有未來實際 release/security requirement 需要時才重新評估。
- advanced allocation / optimizer / AI experiment automation 只有在 current evidence 顯示明確產品價值時才進 NEXT。

## DURABLE DECISIONS / RISKS

- PIT / Walk-Forward causality 是不可降低的 correctness boundary：outer Evaluation/OOS 不得影響同一 outer Decision 的 parameter selection。
- ResearchDataset、selection/allocation、DecisionSnapshot、Portfolio v3、ResearchRun 的既有 authority 不得被 Browser/AI 重新計算或建立平行 numerical authority。
- Backtest / research 結果維持 TWD canonical valuation 與版本化 methodology/contracts；「程式跑完」不等於 quantitative correctness。
- 4B-3 V1 accepted ceilings：`MAX_PARAMETER_CANDIDATES=48`、`MAX_INNER_FOLDS=6`、`MAX_TUNING_EVALUATIONS_PER_JOB=216`；提高前需新 capacity evidence。
- Independent review 的價值來自 fresh evidence reconstruction / adversarial reasoning，而不是另一個 GitHub username 或 APPROVE 儀式；高後果工作仍應依實際風險增加驗證。
- `to_do_update_list.md` 不保存完整歷史、每個 CI/tool call 或 transient hypothesis；這些由 Git / PR / Actions / durable contracts/RCA 保存。
- 工作狀態 materially 改變時更新 CURRENT，將近期工作滑動前移並重新排序 NEXT / ROADMAP；不要 append 成 Project Diary。
