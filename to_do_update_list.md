# Project Execution Memory

本文件是 BacktestStock 的持續執行記憶。

原則：CURRENT 要精確；NEXT 要有順序；ROADMAP 可隨新證據調整；歷史持續壓縮。Git / PR / CI / Vercel / Cloudflare / runtime truth 高於本文件中的舊快照。

Last updated: **2026-08-19 Asia/Taipei**

## CURRENT

**Primary Goal**
- 完成 Phase 4B-3 — Optimizer Hub Parameter Optimization V1，提供 bounded automatic parameter tuning，同時維持 PIT / Walk-Forward 因果正確性與既有 Portfolio v3 / ResearchRun authority。

**Current Batch**
- 4B-3 formal release candidate verification / merge gate。

**Stable State**
- `main@b80c7f373587164aa34be40d09cef5535ab20da5` 已包含 Phase 4B-2 Optimizer Hub Allocation（PR #172）。
- PR #177 是 4B-3 clean release candidate；implementation 已完成，未合併。
- PR #147 維持 frozen / deferred，不屬目前 implementation 主線。

**Branch / PR / HEAD**
- Branch: `feat/optimizer-hub-parameter-optimization-v1`
- PR: #177 — OPEN / READY
- Head: `8c2eedc06ca6a557948fd436e5db1517b00d2e0a`
- Base: `main@b80c7f373587164aa34be40d09cef5535ab20da5`

**Verified**
- Exact-head GitHub CI #962 / run `32198984484`: SUCCESS。
- Exact-head Vercel commit status: SUCCESS。
- Exact-head self-review: BLOCKER none；但該 self-review 明確不取代 independent approval。
- `cchung911` 已被 request 作為 reviewer；目前尚未看到 APPROVED review。

**Blocker**
- Product code blocker: NONE known。
- Release gate pending: independent exact-head approval required by PR #177 release plan。不得用本次治理簡化繞過該 candidate 已明確建立的 release gate。

**Exact Next Action**
- 取得 PR #177 對 exact head `8c2eedc...` 的 independent approval；若 head 未移動且 release evidence 仍成立，再依 PR #177 既定 release plan完成 merge 與 post-main exact-SHA Vercel / Cloudflare / Walk-Forward production acceptance。若 reviewer 發現 material issue，回到 First-Principles Debug / smallest correct fix，再產生新的 candidate head 驗證。

## NEXT

1. [ ] 完成 4B-3 merge + post-main exact-SHA production acceptance，確認正式 CLOSED。
2. [ ] 依最新使用者價值與 current evidence，選擇下一個單一 user-facing Optimizer Hub / AI-automation capability；不要因舊 roadmap 自動展開 methodology scope。
3. [ ] 只有實際阻塞功能、correctness、PIT/Walk-Forward causality、data/security 或 deployment 的技術工作才提升為 NOW。

## ROADMAP

### Near Term
- 讓 Optimizer Hub 從 Dual Momentum + Allocation + bounded parameter optimization 形成穩定、可重播、因果正確的使用者研究流程。
- 保持 backend / ResearchDataset / DecisionSnapshot / Portfolio v3 / ResearchRun 為數值與證據 authority；Browser/AI 只負責 request 與呈現。

### Later
- 以直接使用者研究價值為導向擴充 Optimizer Hub / AI automation；每次只引入一個可驗證能力，不為方法論完整性而提前加入大量 optimizer。
- 需要擴大 practical workload ceiling 時，先取得新的 empirical capacity evidence。

### Candidates
- PR #147 edge-perimeter hardening 維持 frozen/deferred；只有未來實際 release/security requirement 需要時才重新評估與 rollout。
- 其他 advanced allocation / optimizer / research ideas 只有在 current evidence 顯示明確產品價值時才進 NEXT。

## DURABLE DECISIONS / RISKS

- PIT / Walk-Forward causality 是不可降低的 correctness boundary：outer Evaluation/OOS 不得影響同一 outer Decision 的 parameter selection。
- ResearchDataset、selection/allocation、DecisionSnapshot、Portfolio v3、ResearchRun 的既有 authority 不得被 Browser/AI 重新計算或建立平行 numerical authority。
- Backtest / research 結果維持 TWD canonical valuation 與版本化 methodology/contracts；「程式跑完」不等於 quantitative correctness。
- 4B-3 V1 accepted ceilings：`MAX_PARAMETER_CANDIDATES=48`、`MAX_INNER_FOLDS=6`、`MAX_TUNING_EVALUATIONS_PER_JOB=216`；提高前需新 capacity evidence。
- `to_do_update_list.md` 不保存完整歷史、每個 CI/tool call 或 transient hypothesis；這些由 Git / PR / Actions / durable contracts/RCA 保存。
- 工作狀態 materially 改變時更新 CURRENT，將近期工作滑動前移並重新排序 NEXT / ROADMAP；不要 append 成 Project Diary。
