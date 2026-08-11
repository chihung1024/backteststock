# AI_PROJECT_PLAYBOOK.md

# AI 協作開發最高規範 V3.0

## ChatGPT × Codex × AI Agents × GitHub × CI/CD × Deployment

> **Broad Thinking, Narrow Execution.**  
> **Evidence First, Risk-Proportional Governance.**  
> **獨立審查重點是獨立推理與專業能力，不是不同人頭。**

Status: **GOVERNANCE BASELINE LOCKED**  
Governance Architecture: **FROZEN**  
Further Governance Optimization: **STOPPED**  
Reopen: **ONLY BY DOCUMENTED REOPEN CONDITION**

---

# 0. 文件定位

本文件為本 Repository 的最高層級工程治理規範。

適用於：

- ChatGPT
- Codex
- AI Agent
- Sub-Agent
- Automated Coding Agent
- 人類開發者
- Reviewer

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

回答：專案是什麼？架構是什麼？怎麼開發、執行、測試與部署？

不得拿 README 當即時進度表。

## AI_PROJECT_PLAYBOOK.md

回答：開發、研究、審查、驗證與交接時應遵守什麼工程規則？

屬於穩定治理文件，不應因單一 Feature 或 Bug 任意修改。

## to_do_update_list.md

回答：現在做到哪裡？為什麼？目前 blocker 是什麼？下一步是什麼？

它是 Repository 內的 Live Project Status、Master Plan、Current Phase、Current Batch、Decision Log、Root Cause Log、Risk Register、Technical Debt 與 Handoff Authority。

但 GitHub / CI / Deployment 等 Remote System 的即時狀態仍高於文件快照。執行重要操作前必須重新查證 remote truth。

## docs/

保存 Architecture、Contracts、ADR、Research methodology、API semantics、Deployment runbooks、Historical design records 與 Versioned specifications。

Versioned contract 不得被 live status 任意覆寫。

---

# 2. 最高工程原則

所有工作遵守：

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

不得：看到症狀 → 猜一個原因 → 大量修改 → Bug 好像消失。

---

# 4. Risk-Proportional Governance

所有修改先依 **Impact Radius + Failure Consequence** 分級。

## R0 — Trivial

例如 typo、純文件文字、無語意 formatting、comment、不影響 behavior 的名稱說明。

通常只需 Self Review + 必要的輕量驗證；不機械要求 Independent Review / Full Regression / Release Backup / Production Smoke。

## R1 — Local / Low Risk

例如局部 UI、非核心 helper、isolated bug、小型 validation、低 impact configuration。

需要 Targeted Tests、Relevant Regression、Self Review。Independent Review 建議但非強制，除非實際影響升級。

## R2 — Significant

例如 API behavior、data model、shared library、architecture boundary、quantitative methodology、authentication-adjacent behavior、deployment/runtime、shared state、persistence、portfolio calculation、會改變治理 Gate 的文件。

需要 Targeted Tests、Relevant Broad Regression、Exact-head CI、Rollback/Recovery Point、Independent Review Gate、Documentation/Handoff update。

## R3 — Critical

例如 authentication/authorization、security boundary、secret handling、destructive DB migration、data corruption possibility、critical financial calculation、irreversible migration、production outage recovery、高影響 infrastructure。

需要 R2 全部、Domain-appropriate specialist review、Strong recovery evidence、Full applicable validation、Production verification when deployed；必要時加入第二個獨立觀點、人類 owner decision、security scanner 或 migration rehearsal。

> **Diff Size ≠ Risk Level。**

---

# 5. Risk Classification Gate

每個非 trivial Batch 在 Implementation 前必須先確定 Risk Class：R0 / R1 / R2 / R3。

至少考慮：

- Behavior Impact
- Data Impact
- Security Impact
- Financial / Quant Impact
- Architecture Impact
- Deployment Impact
- Rollback Difficulty
- Blast Radius
- Contract / Governance Impact

## Higher-Risk Default Rule

若合理地落在兩個 Risk Class 之間：

```text
Uncertainty
→ Higher-Risk Default
→ Evidence
→ Optional Downgrade
```

不得先選低風險，只為減少 Gate 再合理化。

Risk 可以依新 evidence 升級或降級；R2/R3 降級必須留下簡短 evidence。

## Final Risk Reclassification

**對 R1 以上 Batch，Risk Class 必須在 final candidate / merge gate 前重新確認一次。**

Final Risk Classification 依據 final diff、actual behavior change、discovered evidence、actual blast radius、contract/governance impact、rollback characteristics 與 current remote state 重新判定。

Initial Risk Class 不因 Batch 已開始而自動延續至 Merge。若 final candidate 實際影響更高，先完成 Risk Upgrade 及新增適用 Gate，再進 Merge。

---

# 6. Gate Applicability Principle

不是每個修改都執行所有 Gate。

每個 Gate 必須回答：

> **這個 Gate 在防止什麼 Failure Mode？**

若答案不明確，不應機械執行。

Docs-only PR 通常不需要 production smoke；Quant methodology change 即使沒有 UI change，也需要 mathematical invariants / methodology review；DB migration 即使 diff 很小也可能是 R3。

---

# 7. Docs Risk Escalation Rule

> **Docs-only ≠ Automatically Low Risk。**

文件風險依「文件實際控制的決策/行為後果」判斷，而不是看副檔名。

## Governance Documents

若修改 `AI_PROJECT_PLAYBOOK.md`、branch/release/review/security/deployment governance，且會改變 Merge Gate、Review Requirement、Security Boundary、Deployment Procedure、Rollback Policy 或 Required Validation，至少視為 R2。

## Versioned Contracts

API/Data/Quant/Research/Persistence/Migration semantics 即使只改 Markdown，只要改變系統應如何實作或解讀，就依 semantic impact 分類 R2，必要時 R3。

## Operational Runbooks

若錯誤文件可能導致 production mis-deploy、data loss、incorrect rollback、security misconfiguration、irreversible command，Risk Class 按最嚴重合理後果判斷。

## Pure Documentation

只有 typo、grammar、formatting、non-semantic wording、navigation/link cleanup 等不改變 contract/decision/operation 的修改，才通常維持 R0。

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

所有新發現分類 NOW / NEXT / BACKLOG / REJECT。

---

# 9. NOW / NEXT / BACKLOG / REJECT

## NOW

不處理就無法安全完成目前 Batch，例如 Root Cause 必需、Critical Risk、Strong Dependency、Correctness blocker。

## NEXT

有高價值，但不需要塞入目前 Batch；建立下一個明確 Batch。

## BACKLOG

有價值但 urgency 低、dependency 未成熟、cost/risk 過高或不影響目前 correctness。

## REJECT

目前沒有足夠 Evidence × Benefit × Relevance，或 Risk / Complexity 明顯高於 Benefit。

---

# 10. Scope Lock

Batch 開始時應定義：

```text
Objective
In Scope
Out of Scope
Allowed Investigation
Expansion Trigger
Risk Class
Verification Plan
```

工作途中擴大範圍前先回答：新工作是 Root Cause 必要條件，還是「順便」？除非屬於 NOW，不得直接塞入目前 Batch。

---

# 11. WIP Limit

原則：

```text
Primary Active Batch = 1
```

允許少量 Supporting Research / Root Cause Investigation / Review / Test investigation，但同一核心實作面必須有唯一 implementation owner。

Blocked Primary Batch 不代表所有研究活動停止，但不得藉 supporting work 開第二條主要 implementation 主線。

---

# 12. Root Cause Protocol

Bug 至少區分：Symptom、Failure Point、Contributing Factor、Root Cause、Systemic Cause。

## Lightweight RCA

R0/R1 可只記 Symptom / Cause / Fix / Regression Protection。

## Full RCA

R2/R3 或反覆 Bug 使用 Reproduce / Evidence / Hypotheses / Failure Point / Root Cause / Systemic Cause / Impact / Fix / Regression / Prevention。

Five Whys 需要時使用，不是固定儀式。

---

# 13. Workaround Policy

Workaround 可用於 production incident、upstream defect、external API failure、temporary platform issue、time-sensitive restoration。

至少記 Root Cause、Workaround、Risk、Removal Condition、Permanent Fix / Decision。

不得把 Workaround 描述成 Root Cause Resolved。

---

# 14. Refactor Gate

Refactor 至少符合一項：architecture blocks requirement、recurring bugs share systemic cause、maintenance cost materially high、testing impossible、security issue、performance bottleneck、scalability limitation、technical debt blocks roadmap。

不能只因 prettier、newer framework、coding preference、theoretical elegance。

若可能，Behavior Change 與 Refactor 分離。

---

# 15. Recovery Policy

不是每個 Commit 前都建立 Tag / Release。

- R0/R1：通常 clean commit / branch 足夠。
- R2：重要修改前確認 Known Good Commit + Rollback Path。
- R3：視情況增加 tag、release、DB backup、deployment snapshot、configuration backup。

> Recovery 成本應與 Failure Consequence 相稱。

---

# 16. Unknown Changes Protection

重要修改前確認 git/working-tree/remote state。

發現未知變更，視為 Potential User / Other Agent Work，不得直接 reset --hard、clean -fd、force checkout、force push，除非已明確辨識來源與後果。

---

# 17. Branch / Main Policy

重要工作避免直接修改 `main`。

`main` 視為 Potential Production Candidate，不得放入 known broken code、unverified experiment、partial migration、knowingly inconsistent contracts。

建議使用 feature/、fix/、refactor/、perf/、docs/、chore/、hotfix/ 等分支命名。

---

# 18. Commit Principle

每個 Commit 應單一目的、能描述 Why、可理解、可 rollback、有驗證意義。

推薦 Conventional Commit 類型：feat / fix / refactor / perf / test / docs / chore。

不要求一個 Batch 一定只有一個 Commit；若多 Commit 提高 auditability，可合理拆分。

---

# 19. Validation Strategy

Validation 必須依 Impact Radius 選擇，可能包含：Static、Unit、Integration、Contract、Invariant、Regression、Build、E2E、Smoke、Deployment Verification。

不要求每一項都執行。

---

# 20. Quantitative / Financial Changes

涉及 return、CAGR、drawdown、covariance、correlation、optimization、factor model、bootstrap、portfolio selection、weighting、risk metrics、backtest methodology，至少考慮：

```text
Reference Test
Invariant Test
Boundary Test
Determinism Test
Sample-Semantics Test
Look-ahead / Leakage Risk
Currency / Calendar Semantics
```

> **程式有跑完，不是充分的 Quant 驗證。**

---

# 21. Testing and Review 不重複做同一件事

CI 適合證明 syntax、type、tests、build、deterministic assertions、contract checks。

Reviewer 主要檢查 requirement fit、assumption validity、architecture、methodology、missing test cases、failure modes、security semantics、data semantics、unintended behavior、rollback feasibility。

Reviewer 不應只重跑一次 CI 然後宣布 PASS。

---

# 22. Independent Review Gate

V3.0 將舊的 Independent Third-Party Review 改為 **Independent Review Gate**。

Independent 的定義是：

> **獨立重新建立判斷，而不是不同 GitHub 帳號。**

---

# 23. Reviewer Independence

Reviewer 不得只接受 Implementer Summary → 同意。

必須重新取得關鍵證據：

```text
Requirement
↓
Relevant Contracts
↓
Exact-head Diff
↓
Tests / CI
↓
Architecture / Methodology
↓
Risk
↓
Decision
```

即使 reviewer 是同一 AI、另一 Agent、Sub-Agent、人類或外部專家，都必須重新判斷。

---

# 24. Reviewer Competence

Reviewer 的價值取決於：

```text
Independence × Relevant Competence
```

不是 Different Person = Valid Reviewer。

Quant PR 應具 statistics / finance / numerical-method / sample-semantics / look-ahead reasoning；Security PR 應具 auth/security/threat reasoning；Deployment PR 應理解 runtime/rollback/infrastructure；Documentation PR 應理解 source of truth、actual architecture、remote state、historical integrity。

不具相關能力的 approval 只能視為一般意見，不能自動提升工程可信度。

## Competence Insufficiency Handling

能力不足時不得「不了解但看起來沒問題 → APPROVE」，而應採以下至少一項：

1. **Narrow the Review Claim**：明確標記 PASS 與 NOT REVIEWED 範圍。
2. **Obtain Specialist Review**：可用 specialist AI、security scanner、external expert、domain reference validation。
3. **Strengthen Objective Evidence**：reference fixture、invariant tests、independent implementation comparison、official specification、reproducible benchmark、migration rehearsal。
4. **Leave Explicit Residual Risk**：再依 residual risk 判斷是否可 Merge。

若 change 為 R3，且 reviewer 無法判斷核心 critical risk：

```text
Competence Insufficient
=
Review Gate Not Satisfied
```

---

# 25. AI Independent Reviewer Mode

對單人 AI-assisted Repository，允許 AI Independent Review。

要求：

1. 不採信 implementer 的 PASS 結論。
2. 從 Repository / diff / contract 重建理解。
3. 明確指出 reviewed exact head。
4. 檢查 requirement 和 actual implementation 是否一致。
5. 尋找反例與 failure mode。
6. 檢查 existing tests 沒覆蓋的地方。
7. 不因自己之前參與設計就自動接受。
8. Findings 必須有 evidence。

## Same-AI Independent Review Isolation Protocol

同一 AI Review 時，至少重新讀 Original Requirement、Applicable Contract/ADR、Exact Candidate Diff、Relevant Source Code、Relevant Tests、CI Evidence、Risk Classification、Rollback/Recovery。

### Blind-to-Conclusion Principle

Review 開始時暫時忽略 implementer 的 PASS / READY / NO ISSUE / recommended merge 結論，重新回答：What can fail? What assumption may be wrong? What evidence is missing? What would falsify this implementation? Does the code actually satisfy the requirement?

### Adversarial Pass

R2/R3 至少執行 Counterexample Search、Boundary Search、Failure-Mode Search、Regression Search、Assumption Challenge。

Quant/Financial 額外檢查 sample semantics、look-ahead、survivorship、currency、calendar、determinism、mathematical invariants。

若能力允許，優先 different Agent / different model / isolated Sub-Agent / fresh review context；否則可由同一 AI 執行，但記錄 Reviewer Type: Same-AI Independent Review 與 isolation method。

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

不得 Review → Silent Fix → Continue Reviewing → PASS。

**任何 material fix 都會產生新的 candidate head；原 review conclusion 不自動繼承。** Material change 包含 behavior、methodology、API/data semantics、security、persistence、architecture、deployment behavior。Non-material typo/formatting 可依 Exact-Head Principle focused re-review。

---

# 26. Review Level

- R0：Self Review 足夠。
- R1：Self Review 必須；Independent Review 視風險選擇。
- R2：Independent Review 必須。
- R3：Independent domain review 必須；必要時 Two independent perspectives。

沒有意義的第二個人頭不得取代能力審查。

---

# 27. Review Findings

只分類：BLOCKER / FOLLOW-UP / BACKLOG / REJECT。

- BLOCKER：不解決不能 Merge。
- FOLLOW-UP：值得改善，但不阻止目前 Merge。
- BACKLOG：未來候選。
- REJECT：Review 建議經評估後不採用。

Review 不得製造 Infinite Improvement Loop。

---

# 28. Review Convergence

Round 1 可廣泛尋找 correctness risk；Round 2 集中於已知 BLOCKER；之後只確認 blocker resolution。

除非出現新的 Critical Evidence，不得每輪重新發明專案。Review round 數量不是固定 KPI。

---

# 29. Exact-Head Principle

對 R2/R3，Review 與 final CI 必須對應 Exact Candidate Head。

Review 後修改程式/方法/契約時，判斷修改是否 material。Non-material 可 focused re-review；material 必須重新驗證受影響部分。

重要 merge 應使用 expected head SHA，避免 reviewed head 與 merged head 不一致。

---

# 30. PR Protocol

重要 PR 至少提供：Objective、Scope、Out of Scope、Root Cause/Context、Solution、Tests/Verification、Risks、Rollback、Known Limitations。

只有真正有價值時才加入 Alternatives、Migration、Performance Benchmark、Security Analysis，不得為填模板而填模板。

---

# 31. Definition of Done 分層

V3.0 分離：

- **IMPLEMENTED**：需求程式已完成。
- **VALIDATED**：適用 tests/regression 已通過。
- **READY TO MERGE**：適用 validation/review/docs/rollback/blocker 都符合。
- **MERGED**：已進入 target branch。
- **DEPLOYED**：需要 deployment 時已部署並驗證。
- **CLOSED**：Batch/Phase 的 required implementation/validation/merge/deploy/documentation/handoff 全部完成。

> **IMPLEMENTED ≠ CLOSED。**

---

# 32. CI Failure Classification

CI fail 不直接等於 code defect。先分類：Code Failure / Test Failure / Environment Failure / Quota or Rate Limit / External Service Failure / Flaky Infrastructure / Configuration Failure / Unknown。

分類為 external failure 不代表可以 bypass required gate；依情況 retry、取得 valid rerun、明確調整 governance 或記錄允許的 exception。

---

# 33. Security / Data Integrity Override

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

Critical security/data issue 可以突破 Scope Lock，但修正仍維持 Minimum Correct Safe Change。

---

# 34. Dependency Policy

不能因「有新版」就大量升級。

升級理由應為 security、compatibility、unsupported version、required functionality、confirmed bug。

Dependency vulnerability 先判斷 Severity、Production/Dev、Direct/Transitive、Reachability、Exploitability、Upgrade Risk。

不得機械執行 force upgrade everything。

---

# 35. Performance Policy

遵守：

```text
Measure
↓
Locate
↓
Hypothesis
↓
Change
↓
Measure Again
```

聲稱效能改善原則上需要 Before/After，例如 latency、execution time、API calls、memory、bundle size。

---

# 36. Documentation Update Policy

文件是工程狀態的一部分，但不要求把每個低價值操作都寫入文件。

`to_do_update_list.md` 只需保存對下一個 Agent 有價值的 current state、stable state、decisions、root causes、blockers、risks、current batch、exact next action、important verification、important commit/PR/release。

不需要保存每個 shell command、temporary hypothesis、微小 formatting、已完全取代且無歷史價值的中間敘述。

避免 Handoff 文件變成比程式更難理解的流水帳。

---

# 37. Decision Log

重大決策至少記：Decision、Context、Evidence、Reason、Trade-off、Status、Reopen Condition。

只有對理解決策有幫助時才詳細列 Alternatives。

Decision 經研究、實作、驗證後保持 Locked，除非有 New Material Evidence / Requirement Change / Critical Defect / Architecture Conflict / External Change / 明顯更優且 Benefit > Migration Risk 的方案。

重新開啟重要既有決策時記錄 Original Decision / Original Reason / New Evidence / Why Existing Decision Is No Longer Adequate / Proposed Change / Migration Risk。

---

# 38. Root Cause Log

只有 meaningful bug、systemic issue、recurring issue、R2/R3 correctness issue 才進長期 Root Cause Log。

小 typo 不需要 RCA archive。

---

# 39. History Compression

隨專案演進：

```text
Active Detail
↓
Close Phase
↓
Compress into Historical Summary
```

保留 result、major decisions、RCA、merge/release、known limitations；移除低價值過程細節。完整歷史由 Git/PR 保留。

---

# 40. Session Startup Protocol

新 AI Session：

```text
1. AI_PROJECT_PLAYBOOK.md
2. README.md
3. to_do_update_list.md
4. Current Git / Remote State
5. Current Phase / Batch / Next Action
6. Relevant Contract / ADR
7. Then Work
```

不是每次從頭重新研究整個 Repository。閱讀深度依任務決定。

新的 AI Session 不代表新的專案；不得因缺少前次聊天就自行重建另一套 Master Plan。

---

# 41. Remote Truth Gate

重要操作前重新確認 target branch、current main SHA、PR head/base/mergeability、CI、required status、review state、deployment/release state when relevant。

Repository 文件是 persistent context；Remote systems 是 Current Operational Truth。

---

# 42. User Intent / Controlled Replanning

若使用者明確要求改方向、暫停、重排、重新審查、回退或修改 requirement，更新 working baseline，但保留原決策歷史。

重新規劃採：

```text
Old Baseline
↓
New Evidence / Requirement
↓
Delta
↓
Revised Baseline
```

不得把舊計畫無聲刪掉，也不得因新 Agent 偏好自行改方向。

---

# 43. AI Authority Boundary

AI 可在已授權範圍內 research、modify、test、commit、branch、create PR、review、document。

但不得自行降低 branch protection、bypass required checks、force push protected history、刪除 recovery points、weakening security gates、把 unverified work 宣稱 safe、無證據擴張 product requirements。

Governance change 本身視為 Governance Batch，不得為了讓目前 PR 過關而臨時改規則。

---

# 44. Governance Transition / Non-Retroactive Rule

新 Governance Rule 原則上 **Prospective-by-Default**，適用於治理變更接受後的操作/Gate。

已 MERGED/CLOSED/RELEASED 的工作不因後來治理規則改變而自動 REOPEN/FAIL/INVALID，除非出現 material correctness evidence、security issue、data-integrity issue、production incident。

## Active Work Transition

治理修改生效時仍 ACTIVE 的 PR/Batch 做一次 Transition Assessment：

- Apply Immediately
- Apply at Next Gate
- Grandfather Current Batch（僅在 retrofitting cost 明顯高於 risk reduction 時；記 Grandfather Reason / Residual Risk / New Rule Effective From）

## Anti-Bypass Rule

若 Governance 修改直接移除目前 PR 唯一 blocker、降低 required validation、security requirement 或 data-integrity protection，不能只因規則修改就 PASS；必須做 Governance Change Review + Current PR/Batch Transition Assessment。

## Grandfather Anti-Bypass

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

> **Grandfather ≠ bypass escape hatch。**

例如把 `Independent Third-Party Review` 修正為 `Independent Review Gate`，可以是合法 governance correction，但仍必須依新規則真正完成 Independent Review；不能只刪掉 Third-Party 字樣就直接 Merge。

---

# 45. Release Policy

不是每個 PR 都需要 Release。

適合建立 Release / Tag / Stable Checkpoint 的情況：user-facing version、major phase closeout、R2/R3 significant stable point、pre/post high-risk migration、production recovery landmark。

Docs-only / trivial PR 通常不需要額外 Release，除非風險分類另有理由。

---

# 46. Deployment Policy

只有修改實際 deployed behavior 時才要求 deployment validation。

一般：

```text
Validated Candidate
↓
Merge
↓
Build if applicable
↓
Deploy if applicable
↓
Smoke
↓
Production Verification
```

Docs-only PR 不需要假裝執行 production smoke。

---

# 47. Deployment Failure

Critical production regression 優先 Rollback / Restore，不是在 Production 持續疊 patch。

恢復後：Evidence → RCA → Fix → Validate → Review → Redeploy。

---

# 48. Phase / Batch Status Vocabulary

統一使用：

```text
PLANNED
ACTIVE
BLOCKED
VALIDATING
READY TO MERGE
MERGED
CLOSED
DEFERRED
REJECTED
```

Validation result 另外記 PASS / FAIL。Status 與 Test Result 分離。

---

# 49. Batch Completion Report

每個重要 Batch 最低必要資訊：Objective / Result / Key Changes / Verification / Risk or Limitations / Git or PR / Next。

Debug 時增加 Root Cause；發現相關新工作時增加 NOW / NEXT / BACKLOG / REJECT。

不要求固定填寫沒有價值的空欄位。

---

# 50. Handoff Minimum

下一個 AI 必須能回答：

1. main 正常嗎？
2. Last Known Good 是什麼？
3. Current Phase？
4. Current Batch？
5. Current head / PR？
6. 現在 blocker？
7. 哪些重要 decision locked？
8. 哪些 risk 尚未解決？
9. 下一個 exact action 是什麼？

若能無歧義回答，Handoff 即具備基本品質。

---

# 51. Optimization Saturation

滿足 requirement、correctness、major regression、acceptable performance、acceptable maintainability、adequate tests、stable deployment when applicable，且下一個改善 Marginal Benefit << Added Cost/Risk，則停止目前方向，加入 BACKLOG。

不追求「永遠可以再優化」。

---

# 52. Stop / Resume Conditions

真正停止 Implementation 的理由包括：unknown user changes may be overwritten、data-loss risk、security critical、root assumption invalidated、R2/R3 no safe rollback、root cause fundamentally unknown、material scope creep、conflicting concurrent implementation。

「找不到另一個普通 GitHub 帳號 reviewer」本身不是技術 Stop Condition。

Resume 前確認 Evidence sufficient、Scope redefined、Recovery point exists、Current Batch clear、Risk acceptable。

---

# 53. Compatibility / Premature-Change Rules

已有使用者使用的功能優先保持 API compatibility、Data compatibility、UI behavior、Existing workflow，除非 Requirement 明確改變。

禁止：No Premature Implementation、No Premature Refactor、No Premature Optimization、No Premature Generalization。

達成需求時優先選 **最小正確修改面積**，不是最少 code 行數，而是最少不必要系統影響。

---

# 54. Failure Transparency

遇到 Test fail、Build fail、Deploy fail、Unknown behavior、Missing permission、Unverified assumption，必須明確記錄。

不得把 Partially Complete 描述成 Complete；未實測則標記 NOT VERIFIED。

---

# 55. Governance Anti-Pattern

禁止：

- **Process Theater**：只是為了有紀錄而產生紀錄。
- **Approval Theater**：沒有能力判斷的人按 Approve。
- **Test Theater**：執行大量與 diff 無關的測試只為增加數字。
- **Backup Theater**：每個小修改都建立 Tag / Release。
- **Documentation Theater**：文件比程式實際狀態更難理解。
- **Review Rabbit Hole**：每輪 review 發明新的 roadmap。
- **Optimization Rabbit Hole**：產品穩定卻永遠不 Close Phase。

---

# 56. Governance Efficiency Test

任何新規則加入天書前回答：

```text
它防止什麼具體 failure mode？
有沒有較低成本的方法？
是否與已有規則重複？
它適用於所有 change，還是特定 risk class？
如果沒有它，實際風險多大？
```

只有 Expected Risk Reduction > Governance Cost 才應加入。

---

# 57. 最終 Merge 判斷

Merge 前不要只問「有沒有另一個人按 Approve？」。

應問：

```text
Requirement fulfilled?
Correctness evidence sufficient?
Applicable tests passed?
Known blockers = 0?
Review level appropriate to risk?
Reviewer competent?
Review based on independent evidence?
Exact head reviewed?
Rollback adequate?
Documentation sufficient for handoff?
```

全部適用項目成立才 READY TO MERGE。

---

# 58. Governance Formula

本專案採：

> **Evidence-Based Engineering**，不是流程越多越安全。

> **Risk-Proportional Governance**，不是所有修改跑同一套 Gate。

> **Independent Reasoning Review**，不是 Different Account Approval。

> **Competence-Based Review**，不是隨便找旁人背書。

> **Broad Thinking, Narrow Execution**，不是發現什麼就改什麼。

> **Persistent Context, Current Remote Truth**，不是只相信聊天紀錄或 stale documentation。

> **Stable Progress**，不是 Infinite Optimization。

---

# 59. 最終判斷問題

修改前：我真的理解目前系統與 remote state 嗎？

Debug 前：我找到的是 symptom、failure point，還是 root cause？

擴大 Scope 前：這是 correctness 必需，還是順便改善？

重構前：Evidence 足以證明需要 refactor 嗎？

測試前：哪些 failure modes 真正需要驗證？

Review 前：Reviewer 是否具備這次 change 所需能力？

Merge 前：Exact candidate 是否已得到與其 risk 相稱的證據？

Deploy 前：如果失敗，可以安全恢復嗎？

Phase close 前：剩下的是必要工作，還是只是可以更好？

Session 結束前：下一個完全沒看過這次聊天的 AI，只看 Repository，能否準確繼續？

---

# 60. V3.0 Governance Freeze

完成本 V3.0 Final Hardening 後，治理模型視為：

```text
OPTIMIZED FOR CURRENT REQUIREMENTS
GOVERNANCE BASELINE LOCKED
Governance Architecture: FROZEN
Further Governance Optimization: STOPPED
```

不得因 wording preference、another AI's preferred workflow、theoretical completeness、enterprise best practice、hypothetical edge case、「再多一條可能更完整」繼續修改天書。

只有以下 Reopen Conditions 才可重新開啟 Governance Architecture：

1. Actual governance-caused failure
2. Repeated workflow friction with evidence
3. Security / data-integrity gap
4. Material project architecture change
5. Multi-maintainer / organization model change
6. CI/CD platform change invalidating existing rules
7. User requirement change

其餘新的 governance idea 預設 BACKLOG 或 REJECT。

長期模式：Use V3 → Execute Real Project Work → Observe → Collect Actual Evidence → only then evaluate a documented Governance Reopen Condition。

---

# 61. Final Constitutional Core

> **Broad Thinking, Narrow Execution.**

> **Evidence First, Risk-Proportional Governance.**

> **獨立審查重點是獨立推理與專業能力，不是不同人頭。**

本專案追求：

```text
Correct
Traceable
Testable
Reviewable
Recoverable
Maintainable
Transferable
```

而不是：

```text
Maximum Process
Maximum Documentation
Maximum Review Count
Maximum Test Count
Maximum Change
```

最終目標是：

> **用最少但足夠的工程控制，持續產出正確、可驗證、可追溯、可回滾、可交接的 Stable State。**
