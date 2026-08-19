# Project Execution Memory

本文件是 BacktestStock 的持續執行記憶。Git / PR / CI / Vercel / Cloudflare / runtime truth 高於舊快照。

Last updated: **2026-08-19 Asia/Taipei**

## CURRENT

**Primary Goal**
- 以已 production-accepted 的 Optimizer Hub 4B-3 為穩定產品基線；Repository simplification 收斂後，下一個 implementation 只從 current evidence 選一個直接 user-facing capability。

**Current Batch**
- Repository simplification closeout — PR #180 是唯一 cleanup candidate；沒有 application implementation batch 與本批並行。

**Stable State**
- 4B-3 Nested Parameter Optimization V1 已 merged / production accepted。
- Cleanup baseline: `main@85071b4c46e0a75f472a2dacb2703ba050c2ff8f`。
- PR #147 已 closed / not merged；歷史 implementation/evidence 保留於 Git/PR history，不再是 active candidate。
- Issue #173 stale master roadmap 已 closed；未來 product planning 回到本文件與 current user/evidence。
- Cleanup 將 phase-oriented/stale documents 收斂為 domain contracts，並移除 redundant release-backup workflow / redeploy marker；不改 application runtime、quant methodology、PIT/Walk-Forward causality 或 schema。

**Branch / PR**
- `cleanup/first-principles-repository-simplification`
- PR #180 `chore: first-principles repository simplification`

**Blocker**
- NONE known. Exact-head checks/runtime truth 決定是否可 merge。

**Exact Next Action**
- 若 PR #180 尚未 merge：只處理 exact-head verification 的真實 blocker，通過後 merge；若已 merge：重新讀 current main/runtime truth，直接選下一個高價值 user-facing batch。

## NEXT

1. [ ] 從 current product evidence 選下一個最高價值 Optimizer Hub / AI-automation user-facing capability。
2. [ ] 4B-4 Robust Objective / Pareto 保留為 candidate，不因舊 roadmap 自動成為 commitment。
3. [ ] 技術工作只有在 materially blocking functionality、UX、correctness、data/security、PIT/Walk-Forward causality 或 deployment 時才升級為主線。

## ROADMAP

### Near term
- Preserve Dual Momentum + Allocation + bounded nested parameter optimization as stable, replayable and causally correct research.
- Prefer capabilities that let the user perform materially better research rather than adding frameworks, phases or infrastructure.

### Later candidates
- transparent robust/Pareto objective constraints and fold stability;
- allocation expansion;
- rebalance/execution optimization;
- stable ensembles;
- AI Research Autopilot.

Capacity/runtime infrastructure expands only after measured product evidence requires it.

## DURABLE DECISIONS / RISKS

- PIT / Walk-Forward causality is a correctness boundary: outer Evaluation/OOS must not affect the same outer Decision's parameter selection.
- ResearchDataset, selection/allocation, DecisionSnapshot, Portfolio v3 and ResearchRun remain distinct numerical/data authorities; Browser/AI does not recreate them.
- Backtest/research results retain TWD canonical valuation and versioned methodology semantics.
- Current 4B-3 accepted ceilings remain `MAX_PARAMETER_CANDIDATES=48`, `MAX_INNER_FOLDS=6`, `MAX_TUNING_EVALUATIONS_PER_JOB=216`; raising them requires new capacity evidence.
- Stale PRs/issues/docs are not execution memory. Closed history stays in GitHub; current state stays here.
- This file stays compact: no complete project diary, repeated CI logs or transient hypotheses.
