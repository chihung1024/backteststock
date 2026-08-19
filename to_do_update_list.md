# Project Execution Memory

本文件是 BacktestStock 的持續執行記憶。Git / PR / CI / Vercel / Cloudflare / runtime truth 高於舊快照。

Last updated: **2026-08-19 Asia/Taipei**

## CURRENT

**Primary Goal**
- 以已 production-accepted 的 Optimizer Hub 4B-3 為穩定產品基線；完成 first-principles repository simplification 後，下一個 implementation 只從 current evidence 選一個直接 user-facing capability。

**Current Batch**
- Repository simplification — consolidate duplicated technical contracts, remove stale process artifacts, close stale active PR/roadmap state, preserve runtime/quant/PIT behavior.

**Stable State**
- 4B-3 Nested Parameter Optimization V1 已 merged / production accepted。
- Product/runtime baseline before cleanup: `main@85071b4c46e0a75f472a2dacb2703ba050c2ff8f`。
- PR #147 已 closed / not merged；歷史 implementation/evidence 保留於 Git/PR history，不再是 active candidate。
- Issue #173 stale master roadmap 已 closed；未來 product planning 回到本文件與 current user/evidence。

**Branch / PR / HEAD**
- Cleanup branch: `cleanup/first-principles-repository-simplification`
- Base: `85071b4c46e0a75f472a2dacb2703ba050c2ff8f`
- Cleanup PR: #180 `chore: first-principles repository simplification`
- Current cleanup head before this checkpoint update: `879eb9539e884c86948f9be04e66ff3d4d5a026f`.

**Verified**
- 4B-3 production acceptance evidence remains preserved in Git/PR/Actions history.
- Cleanup is intentionally documentation/process/test-reference only; application runtime methodology is out of scope unless dead-code reachability is independently proven.

**Blocker**
- NONE known.

**Exact Next Action**
- Complete cleanup diff → run CI → inspect any failure evidence → merge only after relevant verification → verify new main → resume product selection.

## NEXT

1. [ ] Finish and merge first-principles repository simplification without changing runtime/quant/PIT semantics.
2. [ ] Re-evaluate the highest-value user-facing Optimizer Hub / AI-automation capability from current product evidence.
3. [ ] Keep 4B-4 Robust Objective / Pareto concepts as a candidate, not an automatic roadmap commitment.
4. [ ] Elevate technical work only when it materially blocks functionality, UX, correctness, data/security, PIT/Walk-Forward causality or deployment.

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
