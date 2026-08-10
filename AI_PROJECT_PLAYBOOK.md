# AI_PROJECT_PLAYBOOK.md

# AI 協作開發最高規範 V3.0

## ChatGPT × Codex × AI Agents × GitHub × CI/CD × Deployment

> **Broad Thinking, Narrow Execution.**  
> **Evidence First, Risk-Proportional Governance.**  
> **獨立審查重點是獨立推理與專業能力，不是不同人頭。**

Status: **GOVERNANCE BASELINE LOCKED**  
Governance Architecture: **FROZEN**  
Reopen: **ONLY BY DOCUMENTED REOPEN CONDITION**

---

# 0. 文件定位

本文件為本 Repository 的最高層級工程治理規範，適用於 ChatGPT、Codex、AI Agent、Sub-Agent、Automated Coding Agent、人類開發者與 Reviewer。

管理範圍包括：Research、Planning、Implementation、Debug、Refactor、Test、Review、Git、PR、CI/CD、Release、Deployment、Rollback、Documentation 與 AI Handoff。

本文件的目的不是增加程序，而是：

> **以最低必要治理成本，取得足夠高的工程可信度。**

任何 Gate 如果沒有實際降低風險，就不應只因「流程上一直這樣做」而存在。

---

# 1. Repository 文件權威

專案至少維護：

```text
README.md
AI_PROJECT_PLAYBOOK.md
to_do_update_list.md
docs/
```

## README.md

回答：專案是什麼、架構是什麼、如何開發、執行、測試與部署。不得當成即時進度表。

## AI_PROJECT_PLAYBOOK.md

回答：開發、研究、審查、驗證與交接時應遵守什麼工程規則。屬於穩定治理文件，不應因單一 Feature/Bug 任意修改。

## to_do_update_list.md

回答：現在做到哪裡、為什麼、blocker 是什麼、下一步是什麼。它是 Repository 內的 Live Project Status / Master Plan / Current Phase / Current Batch / Decision Log / Root Cause Log / Risk Register / Technical Debt / Handoff Authority。

GitHub / CI / Deployment 等 Remote System 的即時狀態高於文件快照；重要操作前必須重新查證 remote truth。

## docs/

保存 Architecture、Contracts、ADR、Research methodology、API semantics、Deployment runbooks、historical design records 與 versioned specifications。

---

# 2. 最高工程原則

1. **先理解，再修改。**
2. **先取得證據，再形成結論。**
3. **先找 Root Cause，再修症狀。**
4. **分析可以廣，Implementation 必須窄。**
5. **發現問題不等於立即修改問題。**
6. **每個 Batch 都要形成 Stable State。**
7. **驗證強度必須與風險相稱。**
8. **能自動驗證的，不靠人工猜測。**
9. **不能自動驗證的，才是 Review 的主要價值。**
10. **Workaround 不等於 Permanent Fix。**
11. **沒有驗證，不宣稱完成。**
12. **沒有充分證據，不重構穩定系統。**
13. **不為了通過自己的工作而降低 Gate。**
14. **不把流程本身當成成果。**
15. **重要決策必須可追溯。**
16. **重要修改必須可恢復。**
17. **下一個 AI 必須能只靠 Repository 接手。**
18. **新方向必須最終 NOW / NEXT / BACKLOG / REJECT。**
19. **專案要能完成 Phase，而不是永久優化。**
20. **最大化有效改善，不最大化修改量。**

---

# 3. 標準工程循環

一般重要工作：

```text
Inspect
↓
Understand
↓
Collect Evidence
↓
Analyze
↓
Discover
↓
Converge
↓
Plan
↓
Implement
↓
Validate
↓
Review
↓
Stabilize
↓
Document
↓
Merge / Deploy when applicable
```

Debug：

```text
Reproduce
↓
Evidence
↓
Hypotheses
↓
Trace
↓
Isolate
↓
Root Cause
↓
Impact
↓
Fix
↓
Regression
↓
Prevention
```

禁止 Shotgun Debugging：不得一次修改多個未證實原因，再以「Bug 好像消失」作為根因證據。

---

# 4. Risk-Proportional Governance

所有修改先依 **Impact Radius + Failure Consequence** 分級。

## R0 — Trivial

Typo、純文件文字、無語意 formatting、comment、不影響 behavior 的說明。通常只需 self review + 必要輕量驗證。

## R1 — Local / Low Risk

局部 UI、isolated bug、小型 validation、非核心 helper、低 impact configuration。需要 targeted tests、relevant regression、self review；Independent Review 視風險選擇。

## R2 — Significant

API behavior、data model、shared library、architecture boundary、quantitative methodology、deployment/runtime、shared state、persistence、portfolio calculation、會改變治理 Gate 的文件。需要 targeted tests、relevant broad regression、exact-head CI、rollback/recovery point、Independent Review Gate、documentation/handoff update。

## R3 — Critical

Authentication/authorization、security boundary、secret handling、destructive DB migration、data corruption risk、critical financial calculation、irreversible migration、production outage recovery、高影響 infrastructure。需要 R2 全部、domain-appropriate specialist review、strong recovery evidence、full applicable validation，必要時 second independent perspective / human owner decision / migration rehearsal。

> **Diff Size ≠ Risk Level。**

---

# 5. Risk Classification Gate

每個非 trivial Batch 在 Implementation 前先確定 R0/R1/R2/R3，至少考慮：Behavior、Data、Security、Financial/Quant、Architecture、Deployment、Rollback Difficulty、Blast Radius、Contract/Governance Impact。

若合理地介於兩級之間：

```text
Uncertainty
→ Higher-Risk Default
→ Evidence
→ Optional Downgrade
```

不得先選低風險，只為減少 Gate 再找理由合理化。

Risk Class 可以升級或降級；R2/R3 降級必須留下簡短 evidence。

### Final Risk Reclassification

**對 R1 以上 Batch，Risk Class 必須在 final candidate / merge gate 前重新確認一次。**

依 final diff、actual behavior、discovered evidence、actual blast radius、contract/governance impact、rollback characteristics 與 current remote state 重新判定。Initial Risk Class 不因 Batch 已開始而自動延續至 Merge。

---

# 6. Gate Applicability Principle

每個 Gate 必須回答：

> **它在防止什麼 Failure Mode？**

答案不明確時，不應機械執行。

Docs-only PR 不一定需要 production smoke；Quant methodology change 即使沒有 UI，也需要 methodology/invariant tests；DB migration 即使 diff 很小也可能是 R3。

---

# 7. Docs Risk Escalation Rule

> **Docs-only ≠ Automatically Low Risk。**

文件風險依其控制的決策/行為後果判斷，而不是依 `.md` 副檔名。

以下文件修改應提高 Risk Class：

- Governance Documents：若改變 Merge Gate、Review Requirement、Security Boundary、Deployment Procedure、Rollback Policy、Required Validation，至少 R2。
- Versioned Contracts：API/Data/Quant/Research/Persistence/Migration semantics 改變時至少依 semantic impact 分類 R2，必要時 R3。
- Operational Runbooks：若錯誤指令可能導致 production mis-deploy、data loss、wrong rollback、security misconfiguration、irreversible mutation，依最嚴重可能後果分類。

Pure typo/grammar/formatting/non-semantic wording 通常才是 R0。

```text
Risk(Document Change)
=
Risk of the Decision / Behavior the Document Controls
```

---

# 8. Controlled Divergence

允許主動發現 architecture issue、bug、security issue、performance bottleneck、technical debt、test gap、methodology weakness、data-integrity risk、deployment risk。

但：

> **Discovery 不等於 Scope Expansion。**

所有新發現最終只能進入：NOW / NEXT / BACKLOG / REJECT。

- NOW：不處理就無法安全完成目前 Batch。
- NEXT：高價值但不需塞入目前 Batch。
- BACKLOG：有價值但 urgency/dependency/cost 不支持現在做。
- REJECT：Evidence × Benefit × Relevance 不足，或 Risk/Complexity 高於 Benefit。

---

# 9. Scope Lock / WIP Limit

Batch 開始時應定義：Objective、In Scope、Out of Scope、Allowed Investigation、Expansion Trigger、Risk Class、Verification Plan。

原則：

```text
Primary Active Batch = 1
```

允許少量 supporting research/review/test/root-cause investigation，但同一核心實作面必須有唯一 implementation owner。

---

# 10. Root Cause Protocol

至少區分：Symptom、Failure Point、Contributing Factor、Root Cause、Systemic Cause。

R0/R1 可用 Lightweight RCA：Symptom / Cause / Fix / Regression Protection。

R2/R3 或反覆 Bug 使用 Full RCA：Reproduce / Evidence / Hypotheses / Failure Point / Root Cause / Systemic Cause / Impact / Fix / Regression / Prevention。

Five Whys 視需要使用，不是固定儀式。

---

# 11. Workaround Policy

Workaround 只在 production incident、upstream defect、external API failure、temporary platform issue、time-sensitive restoration 等情況使用。

至少記錄 Root Cause、Workaround、Risk、Removal Condition、Permanent Fix/Decision。不得把 workaround 描述成 Root Cause Resolved。

---

# 12. Refactor / Dependency / Performance Gate

Refactor 必須有證據：architecture blocks requirement、recurring systemic bugs、material maintenance cost、testing impossible、security/performance/scalability issue、technical debt blocks roadmap。

不能只因 prettier/newer/elegant。

Dependency 不能因「有新版」順便升級；先判斷 severity、prod/dev、direct/transitive、reachability、exploitability、upgrade risk。

Performance 遵守：Measure → Locate → Hypothesis → Change → Measure Again；聲稱改善原則上有 Before/After evidence。

---

# 13. Recovery / Unknown Changes

R0/R1 通常 clean commit/branch 足夠；R2 確認 Known Good Commit + Rollback Path；R3 視情況增加 tag/release/DB backup/deployment snapshot/config backup。

重要修改前確認 git/remote state。未知變更視為 Potential User / Other Agent Work，不得直接 `reset --hard`、`clean -fd`、force checkout 或 force push。

---

# 14. Branch / Main / Commit

重要工作避免直接在 `main` 開發；`main` 視為 Potential Production Candidate，不放 known broken code、unverified experiment、partial migration、knowingly inconsistent contracts。

Commit 應單一目的、能描述 Why、可理解、可 rollback、有驗證意義。多 Commit 若提高 auditability 可以合理拆分。

---

# 15. Validation Strategy

Validation 依 Impact Radius 選擇：Static、Unit、Integration、Contract、Invariant、Regression、Build、E2E、Smoke、Deployment Verification。不要求每項都機械執行。

涉及 return/CAGR/drawdown/covariance/correlation/optimization/factor/bootstrap/selection/weighting/risk metrics/backtest methodology，至少考慮 Reference Test、Invariant、Boundary、Determinism、Sample Semantics、Look-ahead/Leakage、Currency/Calendar Semantics。

> **程式有跑完 ≠ Quant 方法正確。**

---

# 16. CI 與 Review 分工

CI 適合證明 syntax、type、tests、build、deterministic assertions、contract checks。

Reviewer 主要檢查 requirement fit、assumption validity、architecture、methodology、missing cases、failure modes、security/data semantics、unintended behavior、rollback feasibility。

CI green 是 evidence，不是完整 reasoning。

CI failure 先分類 Code/Test/Environment/Quota/External/Flaky/Config/Unknown；external failure 不代表可偷偷 bypass required gate。

---

# 17. Independent Review Gate

V3.0 使用 **Independent Review Gate**，不要求「不同 GitHub 帳號」本身作為 correctness 證據。

Independent 的定義：

> **獨立重新建立判斷，而不是不同人頭。**

Reviewer 必須重新取得 Requirement、Relevant Contracts、Exact-head Diff、Relevant Tests/CI、Architecture/Methodology、Risk、Rollback 等 primary evidence。

Reviewer 的價值取決於：

```text
Independent Reasoning × Relevant Competence
```

不同人但無相關能力的 approval，不自動提升工程可信度。

---

# 18. Same-AI Independent Review Isolation Protocol

同一 AI 可以執行 Independent Review，但必須建立可驗證的 reasoning isolation，而不是換標題後同意自己。

至少重新讀：Original Requirement、Applicable Contract/ADR、Exact Candidate Diff、Relevant Source、Relevant Tests、CI Evidence、Risk Classification、Rollback/Recovery。

### Blind-to-Conclusion

開始 Review 時忽略 Implementer 的 PASS / READY / NO ISSUE / recommended merge 結論，自己回答：What can fail? What assumption may be wrong? What evidence is missing? What would falsify this implementation? Does code actually satisfy requirement?

### Adversarial Pass

R2/R3 至少執行 Counterexample Search、Boundary Search、Failure-Mode Search、Regression Search、Assumption Challenge。Quant/Financial 另外檢查 sample semantics、look-ahead、survivorship、currency、calendar、determinism、mathematical invariants。

若能力允許，優先 different Agent/model/isolated Sub-Agent/fresh context；否則標記 Reviewer Type: Same-AI Independent Review，並記錄 isolation method。

### Reviewer / Implementer Role Separation

Independent Review 期間不得同時修改 reviewed candidate。

若發現 BLOCKER：

```text
Review
↓
Record Finding
↓
Exit Reviewer Mode
↓
Implementation / Fix
↓
Validation
↓
New Exact Candidate Head
↓
Focused Re-Review
```

禁止 Review → Silent Fix → Continue Reviewing → PASS。

**任何 material fix 都會產生新的 candidate head；原 review conclusion 不自動繼承。** Material change 包含 behavior、methodology、API/data semantics、security、persistence、architecture、deployment behavior。Non-material typo/formatting 可依 Exact-Head Principle focused re-review。

---

# 19. Reviewer Competence Insufficiency

Review 前判斷所需能力，例如 Quant / Security / Deployment / Data。

能力不足時不得「看起來沒問題就 APPROVE」，而應採至少一項：

1. Narrow the Review Claim（明確 PASS 與 NOT REVIEWED 範圍）。
2. Obtain Specialist Review。
3. Strengthen Objective Evidence（reference fixture/invariant/independent implementation/spec/migration rehearsal）。
4. Leave Explicit Residual Risk，再依風險決定是否可 Merge。

如果是 R3，且 reviewer 無法判斷核心 critical risk：

```text
Competence Insufficient = Review Gate Not Satisfied
```

---

# 20. Review Findings / Convergence

只分類 BLOCKER / FOLLOW-UP / BACKLOG / REJECT。只有 BLOCKER 阻止 Merge。

Round 1 可廣泛找 correctness risk；Round 2 聚焦既知 BLOCKER；之後只確認 blocker resolution。除非新的 Critical Evidence，不得每輪重啟大型需求。

---

# 21. Exact-Head Principle

R2/R3 的 final review 與 final CI 必須對應 Exact Candidate Head。

Review 後若有 material code/method/contract change，必須重新驗證受影響部分；重要 merge 使用 expected head SHA，避免 reviewed head 與 merged head 不一致。

---

# 22. PR / Definition of Done

重要 PR 至少提供 Objective、Scope、Out of Scope、Root Cause/Context、Solution、Tests/Verification、Risks、Rollback、Known Limitations。只有有價值時才加入 Alternatives/Migration/Benchmark/Security Analysis，不為填模板而填。

狀態分層：

- IMPLEMENTED：需求程式完成。
- VALIDATED：適用 tests/regression 通過。
- READY TO MERGE：validation/review/docs/rollback/blocker 符合。
- MERGED：進入 target branch。
- DEPLOYED：需要 deployment 時已部署並驗證。
- CLOSED：required implementation/validation/merge/deploy/documentation/handoff 全部完成。

**IMPLEMENTED ≠ CLOSED。**

---

# 23. Security / Data Integrity Override

優先級：

```text
Safety
>
Data Integrity
>
Security
>
Production Availability
>
Correctness
>
Current Feature
>
Optimization
```

Critical security/data issue 可以突破 Scope Lock，但修改仍維持 Minimum Correct Safe Change。

---

# 24. Documentation Quality / History Compression

文件是工程狀態的一部分，但不要求把每個低價值操作都寫入文件。

`to_do_update_list.md` 只保留對下一個 Agent 有價值的 current/stable state、decisions、root causes、blockers、risks、current batch、exact next action、important verification、commit/PR/release。

不保存每個 shell command、temporary hypothesis、微小 formatting、已完全取代且無歷史價值的中間敘述。

重大 Decision 至少記 Decision / Context / Evidence / Reason / Trade-off / Status / Reopen Condition。

重大 Root Cause 才進長期 log。舊 Batch 定期壓縮為 historical summary；Git history 保留完整差異，不需要把所有過程永久留在 live docs。

---

# 25. Session Startup / Remote Truth Gate

新 AI Session：

1. AI_PROJECT_PLAYBOOK.md
2. README.md
3. to_do_update_list.md
4. Current Git / Remote State
5. Current Phase / Batch / Next Action
6. Relevant Contract / ADR
7. Then Work

重要操作前重新確認 target branch、main SHA、PR head/base/mergeability、CI/required status、review state、deployment state when relevant。

Repository 文件是 persistent context；Remote systems 是 Current Operational Truth。

---

# 26. AI Authority Boundary

AI 可在已授權範圍內 research/modify/test/commit/branch/create PR/review/document，但不得自行降低 branch protection、bypass required checks、force push protected history、刪除 recovery points、weakening security gates、把 unverified work 宣稱 safe、無證據擴張 product requirements。

Governance change 本身視為 Governance Batch。不得為了讓目前 PR 過關而臨時改規則。

---

# 27. Governance Transition / Non-Retroactive Rule

新 Governance Rule 原則上 **Prospective-by-Default**，不要求歷史已 MERGED/CLOSED/RELEASED 的工作因新規則自動 REOPEN/FAIL/INVALID，除非出現 material correctness/security/data-integrity/production evidence。

治理修改生效時仍 ACTIVE 的工作做一次 Transition Assessment：

- Apply Immediately
- Apply at Next Gate
- Grandfather Current Batch（僅在 retrofitting cost 明顯高於 risk reduction 時，並記 Grandfather Reason / Residual Risk / New Rule Effective From）

### Anti-Bypass Rule

如果治理修改直接移除目前 PR 唯一 blocker、降低 required validation/security/data-integrity protection，不能只因規則修改就 PASS；必須完成 Governance Change Review + Current PR/Batch Transition Assessment。

### Grandfather Anti-Bypass

Grandfather 不得消除 Governance Change 生效前已由證據明確成立的 safety/security/data-integrity/correctness blocker。

```text
Existing Material Blocker
+
Governance Change
≠
Automatic Blocker Removal
```

若 Active Batch 的唯一 blocker 正是本次 Governance Change 所修改的 Gate，必須先完成：

```text
Governance Change Review
↓
Current PR / Batch Transition Assessment
↓
Apply New Governance Rule
↓
Satisfy New Rule
```

**Grandfather ≠ bypass escape hatch。**

---

# 28. Release / Deployment Policy

不是每個 PR 都需要 Release。適合建立 Release/Tag/Stable Checkpoint 的情況：user-facing version、major phase closeout、R2/R3 significant stable point、high-risk migration、production recovery landmark。

只有修改實際 deployed behavior 時才要求 deployment validation。一般：Validated Candidate → Merge → Build if applicable → Deploy if applicable → Smoke → Production Verification。

Critical production regression 優先 Rollback/Restore，再 Evidence → RCA → Fix → Validate → Review → Redeploy。

---

# 29. Status Vocabulary / Batch Report / Handoff

統一狀態：PLANNED / ACTIVE / BLOCKED / VALIDATING / READY TO MERGE / MERGED / CLOSED / DEFERRED / REJECTED。Validation result 另外用 PASS / FAIL。

重要 Batch 最低報告：Objective / Result / Key Changes / Verification / Risk or Limitations / Git or PR / Next。Debug 才加 Root Cause；有新發現才加 NOW/NEXT/BACKLOG/REJECT。

下一個 AI 至少能回答：main 正常嗎、Last Known Good、Current Phase、Current Batch、Current head/PR、blocker、locked decisions、remaining risks、exact next action。

---

# 30. Optimization Saturation / Stop Conditions

滿足 requirement/correctness/major regression/acceptable performance/maintainability/tests/stable deployment（適用時），且下一個改善 marginal benefit 明顯低於 added cost/risk，停止目前方向並進 BACKLOG。

真正停止 Implementation 的理由：unknown user changes、data-loss/security critical、root assumption invalidated、R2/R3 無 safe rollback、root cause fundamentally unknown、material scope creep、conflicting concurrent implementation。

「找不到另一個普通 GitHub 帳號 reviewer」本身不是技術 Stop Condition。

---

# 31. Governance Anti-Pattern / Efficiency Test

禁止：Process Theater、Approval Theater、Test Theater、Backup Theater、Documentation Theater、Review Rabbit Hole、Optimization Rabbit Hole。

任何新治理規則加入前回答：

- 防止什麼具體 failure mode？
- 有沒有更低成本方法？
- 是否與已有規則重複？
- 適用所有 change 還是特定 risk class？
- 沒有它的實際風險多大？

只有 Expected Risk Reduction > Governance Cost 才應加入。

---

# 32. 最終 Merge 判斷

Merge 前問：

- Requirement fulfilled?
- Correctness evidence sufficient?
- Applicable tests passed?
- Known blockers = 0?
- Review level appropriate to risk?
- Reviewer competent?
- Review based on independent evidence?
- Exact head reviewed?
- Rollback adequate?
- Documentation sufficient for handoff?

適用項目全部成立才 READY TO MERGE。

---

# 33. V3.0 Governance Freeze

V3.0 治理模型視為 **OPTIMIZED FOR CURRENT REQUIREMENTS**。

不得因 wording preference、another AI workflow、theoretical completeness、enterprise best practice、hypothetical edge case、「再多一條可能更完整」而重新開啟。

只有以下 Reopen Conditions：

1. Actual governance-caused failure
2. Repeated workflow friction with evidence
3. Security / data-integrity gap
4. Material project architecture change
5. Multi-maintainer / organization model change
6. CI/CD platform change invalidating current rules
7. User requirement change

其餘新的 governance idea 預設 BACKLOG 或 REJECT。

---

# 34. Final Constitutional Core

> **Broad Thinking, Narrow Execution.**

> **Evidence First, Risk-Proportional Governance.**

> **獨立審查重點是獨立推理與專業能力，不是不同人頭。**

V3.0 的目標不是建立最大化流程，而是：

> **用最少但足夠的工程控制，持續產出正確、可驗證、可追溯、可回滾、可交接的 Stable State。**
