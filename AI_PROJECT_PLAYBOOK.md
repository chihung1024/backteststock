# AI_PROJECT_PLAYBOOK.md

# AI 協作開發最高規範 V2.0

## ChatGPT × Codex × GitHub × CI/CD × Deployment 專案工程天書

---

# 0. 文件定位

本文件為本 Repository 的最高層級 AI 開發、維護、Debug、重構、測試、審查、Git、PR、Release、Deployment 與交接規範。

所有參與本專案之：

* ChatGPT
* Codex
* AI Agent
* Sub-Agent
* Automated Coding Agent
* 其他 AI 開發工具
* 人類開發者

在修改專案以前，原則上均應先閱讀並遵守本文件。

本專案至少維護三個核心文件：

```text
Repository Root
│
├─ README.md
│
├─ AI_PROJECT_PLAYBOOK.md
├─ to_do_update_list.md
│
├─ src/
├─ tests/
└─ ...
```

三者職責不同：

### `README.md`

回答：

> 這個專案是什麼？怎麼使用？怎麼部署？

---

### `AI_PROJECT_PLAYBOOK.md`

回答：

> AI 與開發者應該按照什麼工程規則工作？

本文件屬於專案「憲法／天書」。

原則上穩定，不應因每次任務任意改寫。

---

### `to_do_update_list.md`

回答：

> 現在做到哪裡？做過什麼？為什麼這樣做？下一步是什麼？

這是專案持續更新的：

* Master Plan
* Progress Tracker
* Change Log
* Decision Log
* Root Cause Log
* Technical Debt Register
* AI Handoff Document

每次重要 Batch 完成後都必須更新。

---

# 1. 最高工程原則

所有 AI 開發工作遵守：

1. **先理解，再修改。**
2. **先取得證據，再形成結論。**
3. **先找 Root Cause，再修症狀。**
4. **先建立完整方案，再分批執行。**
5. **允許探索，但探索必須受到控制。**
6. **允許發散，但發散後必須重新收斂。**
7. **不因發現更多可能性，就無限制擴張 Scope。**
8. **每個 Batch 必須形成可使用的 Stable State。**
9. **每個 Batch 必須可驗證。**
10. **每個 Batch 原則上必須可回滾。**
11. **能實際驗證的事情，不以推測代替。**
12. **Workaround 不等於 Root Cause Fix。**
13. **修改量不是成果，正確性才是成果。**
14. **沒有驗證完成，不宣稱 DONE。**
15. **沒有充分理由，不改寫已穩定功能。**
16. **所有重要變更必須留下歷史。**
17. **所有重要技術決策必須留下原因。**
18. **所有未完成事項必須可以被下一位 AI 找到。**
19. **所有新方向最終都必須回到專案目標。**
20. **長期方向逐步收斂，而不是持續增加。**

---

# 2. 標準工程循環

所有重要工作原則上遵循：

```text
Inspect
↓
Understand
↓
Analyze
↓
Discover
↓
Diverge
↓
Evaluate
↓
Converge
↓
Plan
↓
Backup
↓
Implement
↓
Test
↓
Review
↓
Document
↓
Commit
↓
Verify
```

簡化為：

```text
Inspect → Analyze → Plan → Backup → Implement
→ Test → Review → Document → Commit
```

其中新增的重要概念為：

```text
Discover → Diverge → Evaluate → Converge
```

這是本專案控制 AI 發散的核心機制。

---

# 3. Controlled Divergence

# 條件式發散原則

本專案**不是禁止發散**。

AI 可以而且應該主動：

* 發現架構問題
* 發現相關 Bug
* 發現技術債
* 發現安全問題
* 發現效能瓶頸
* 發現更適合的實作
* 發現資料模型問題
* 發現測試缺口
* 發現現有計畫可能存在缺陷

但是：

> 發現新問題，不等於立即修改新問題。

發散主要目的為：

**提高目前決策品質。**

不是：

**擴大工程範圍。**

---

# 4. Divergence Funnel

# 發散－收斂漏斗

所有新發現原則上經過：

```text
Discovery
↓
Candidate
↓
Classification
↓
Impact Analysis
↓
Priority
↓
Scope Decision
↓
Convergence
```

不得採用：

```text
看到問題
↓
直接修改
```

---

# 5. 新發現分類制度

任何工作途中發現的新問題，至少分類為以下五級。

---

## Level 0 — Noise

與目前目標沒有實質關係。

例如：

* 個人風格偏好
* 不必要 formatting
* 無影響的小命名差異
* 純 cosmetic cleanup
* 「我覺得另一個 framework 比較漂亮」

處理：

**忽略。**

不要加入目前工作。

---

## Level 1 — Useful but Unrelated

有改善價值，但與目前任務沒有直接關係。

例如：

正在修資料讀取 Bug，卻發現：

* 首頁 UI 可以重新設計
* Dependency 可以升級
* 另一個模組可以重構

處理：

記錄至：

`to_do_update_list.md`

中的：

* Technical Debt
* Deferred
* Future Candidate

但：

**不得打斷目前 Batch。**

---

## Level 2 — Closely Related

與目前 Root Cause、功能或風險高度相關。

例如：

正在修 API timeout，發現：

* retry policy 不一致
* timeout config 散落
* error handling 有相同問題

可以：

進行 Impact Analysis。

如果同步處理能：

* 明顯降低 regression
* 避免相同問題再次發生
* 不顯著提高風險

可以納入：

目前 Batch 或下一個 Batch。

---

## Level 3 — High Impact

雖非原始 Scope，但不處理可能造成：

* 大量 regression
* 架構錯誤
* 嚴重效能問題
* 大規模資料不一致
* Production instability

處理：

暫停直接 Implementation。

先重新評估 Plan。

必要時：

新增一個專門 Batch。

但不得直接把原 Batch 變成大型重構。

---

## Level 4 — Critical

包含：

* Security vulnerability
* Secret exposure
* Data corruption
* Data loss risk
* Authentication bypass
* Production outage
* Critical financial calculation error
* 無法安全 rollback

Critical 可以立即中斷原本 Scope。

優先順序：

```text
Safety
>
Data Integrity
>
Security
>
Production Availability
>
Current Feature
>
Optimization
```

---

# 6. Exploration Budget

# 探索預算

AI 可以探索周邊問題。

但每個 Batch 都應有「探索預算」。

原則：

> 探索深度可以增加，實作 Scope 不應同步無限制增加。

例如：

目前 Batch：

> 修正 Portfolio Backtest 日期處理 Bug。

可以分析：

* frontend date
* backend date
* timezone
* cache
* yfinance response
* chart rendering

但不代表可以順便：

* 重做 Portfolio UI
* 更換 chart library
* 重構整個 backend
* 升級所有 dependencies

探索是為了確認：

**哪一個才是真正 Root Cause。**

---

# 7. Divergence Trigger

# 什麼情況允許主動發散

符合以下任一條件時，可以展開額外分析：

### A. Root Cause 不明

必須擴大調查。

---

### B. 多個模組可能共同造成問題

可以平行追蹤。

---

### C. 原方案可能只是 Workaround

必須找更深層原因。

---

### D. 修改可能造成 Regression

應擴大 Impact Analysis。

---

### E. 發現架構性共因

例如：

三個 Bug 都來自同一份錯誤 state model。

可以提升分析層級。

---

### F. 發現重大風險

安全、資料、Production 問題可以中斷正常 Scope。

---

### G. 原計畫已被新證據推翻

允許重新規劃。

但是必須記錄：

> 為什麼原決策失效？

---

# 8. 不構成發散理由的情況

以下理由本身不足以擴大 Scope：

* 「順便」
* 「看起來比較漂亮」
* 「新版比較新」
* 「另一個 library 比較熱門」
* 「我比較喜歡這個 architecture」
* 「既然改了就一起重做」
* 「以後可能會用到」
* 「可以寫得更 elegant」

必須存在：

**Evidence + Benefit + Relevance**

才有資格成為 Candidate。

---

# 9. Divergence Candidate 評估

每一個新方向至少回答：

### 1. Relevance

與目前目標相關程度？

---

### 2. Evidence

有什麼證據？

---

### 3. Impact

不處理會怎樣？

---

### 4. Benefit

現在處理有什麼具體收益？

---

### 5. Risk

處理本身會增加多少風險？

---

### 6. Cost

會增加多少：

* 修改
* 測試
* 部署
* 回滾
* review

成本？

---

### 7. Urgency

一定要現在處理嗎？

---

# 10. Value × Relevance × Risk

新增工作不得只看：

> 有沒有改善價值。

應至少考慮：

```text
Value
×
Relevance
×
Urgency
÷
Risk
÷
Complexity
```

不是精確數學計算。

而是一種決策框架。

---

# 11. Convergence Protocol

# 強制收斂機制

發散分析完成後，必須進入：

**Convergence Gate**

所有 Candidate 最終只能進入：

```text
NOW
NEXT
BACKLOG
REJECT
```

---

## NOW

現在必須處理。

條件通常為：

* Root Cause 必要
* Critical risk
* 強相依
* 不處理無法安全完成目前 Batch

---

## NEXT

值得處理，但不需要塞進現在 Batch。

建立：

下一 Batch。

---

## BACKLOG

有價值，但目前優先級不足。

加入：

`to_do_update_list.md`

---

## REJECT

目前不值得做。

記錄必要原因後終止。

---

# 12. 禁止無限 Pending

不得出現大量：

> 之後可以考慮……

但永遠沒有決定。

重要 Candidate 必須：

* NOW
* NEXT
* BACKLOG
* REJECT

四選一。

---

# 13. Optimization Funnel

# 專案優化方向收斂模型

專案初期允許較廣探索。

例如：

```text
Architecture
Data
Performance
UX
Testing
Security
Deployment
Observability
Maintainability
```

經過研究後逐步收斂。

例如：

```text
8 個方向
↓
5 個高價值方向
↓
3 個優先方向
↓
Current Phase
↓
Current Batch
↓
Current Task
```

越接近 Implementation：

**Scope 應該越小。**

不是越做越大。

---

# 14. Funnel Rule

每進入下一層：

候選方向原則上只能：

* 減少
* 合併
* 延後
* 淘汰

只有出現：

**新的高品質證據**

才可以重新增加方向。

---

# 15. Project Direction Lock

# 專案方向鎖定

Master Plan 經確認後：

視為：

**Current Working Baseline**

後續 AI 不得因為：

* 模型不同
* Coding style 不同
* 新對話
* 新 Agent
* 個人偏好

就重新設計方向。

---

# 16. 允許解鎖 Master Plan 的條件

只有以下情況：

### Requirement Change

使用者需求改變。

### New Evidence

新證據證明原方案有問題。

### Critical Defect

發現重大缺陷。

### Architecture Conflict

原方案無法與實際架構共存。

### External Change

API、platform、dependency、deployment 發生重大改變。

### Better Solution

存在明顯更好的方案，且：

Benefit > Migration Risk。

---

# 17. Decision Stability

已經：

* 研究
* 比較
* 決策
* 實作
* 驗證

完成的方向：

不得每次重新討論。

除非有：

**New Material Evidence**

否則 Decision 保持 Locked。

---

# 18. Decision Reopen Rule

重新開啟既有決策前必須記錄：

```text
Original Decision:
Original Reason:
New Evidence:
Why Existing Decision Is No Longer Adequate:
Proposed Change:
Migration Risk:
```

避免：

AI 每次換 Session 就重新設計。

---

# 19. Scope Lock

每個 Batch 開始前定義：

## In Scope

這次一定要完成什麼？

## Out of Scope

這次明確不做什麼？

## Allowed Investigation

允許調查哪些相鄰領域？

## Expansion Trigger

發生什麼事情可以擴大 Scope？

---

# 20. Batch 不得偷偷膨脹

例如：

原 Batch：

> 新增資料覆蓋率篩選。

不得無聲變成：

> 重構整個 Universe engine。

如果確實發現 Engine Root Cause：

應停止並重新建立：

```text
Batch A
資料覆蓋率

Batch B
Universe Engine Refactor
```

而不是混在一起。

---

# 21. Batch Size Control

理想 Batch：

* 單一明確目標
* 相關檔案有限
* 修改邏輯一致
* 測試範圍明確
* 一個 Commit 可描述
* 可獨立 Rollback

若很難一句話描述 Commit：

Batch 通常太大。

---

# 22. Parallel Analysis vs Parallel Implementation

這兩件事必須區分。

可以：

**平行分析多種可能 Root Cause。**

例如：

```text
Hypothesis A
Hypothesis B
Hypothesis C
```

但不代表：

同時把 A、B、C 全部改掉。

正確流程：

```text
Parallel Investigation
↓
Evidence
↓
Eliminate Hypotheses
↓
Root Cause
↓
Minimal Correct Fix
```

---

# 23. Debug Root Cause Protocol

Debug 必須區分：

### Symptom

使用者看到什麼。

### Failure Point

錯誤在哪裡爆出。

### Contributing Factor

哪些因素增加問題發生機率。

### Root Cause

系統為什麼會進入錯誤狀態。

### Systemic Cause

為什麼原架構沒有阻止這種問題。

---

# 24. Debug Workflow

依序：

```text
Reproduce
↓
Observe
↓
Collect Evidence
↓
Form Hypotheses
↓
Trace
↓
Isolate
↓
Root Cause
↓
Impact Analysis
↓
Solution Options
↓
Converge
↓
Fix
↓
Regression
↓
Prevention
```

---

# 25. 禁止 Shotgun Debugging

禁止：

一次改多個可能原因，

然後：

> Bug 好像消失了。

這會失去 Root Cause 證據。

優先：

一個 hypothesis 一個 hypothesis 驗證。

---

# 26. Five Whys

必要時執行：

```text
Why 1
↓
Why 2
↓
Why 3
↓
Why 4
↓
Why 5
```

直到找到：

可被工程措施控制的根因。

---

# 27. Workaround Policy

Workaround 可以存在。

但只能在：

* Production incident
* upstream bug
* third-party API issue
* 時間敏感事故
* 暫時無法控制的外部因素

使用。

必須記錄：

* Symptom
* Root Cause
* Workaround
* Risk
* Removal Condition
* Permanent Fix
* Owner
* Follow-up

---

# 28. 根因修正後的平行優化

發現 Root Cause 後，可以評估同步改善：

* validation
* type safety
* retry
* timeout
* state management
* cache
* logging
* monitoring
* error handling
* resource cleanup
* concurrency
* boundary handling

但僅限：

**與 Root Cause 高度相關。**

---

# 29. Architecture Refactor Gate

架構重構必須符合至少一項：

* 現架構阻止需求實現
* 同類 Bug 反覆出現
* Maintenance cost 已顯著提高
* Security risk
* Performance bottleneck
* Testing impossible
* Scalability bottleneck
* 已知技術債開始阻礙主線

不能只因為：

「看起來不漂亮」。

---

# 30. Refactor 必須分離

如果可能：

功能修改：

```text
Feature Batch
```

與：

```text
Refactor Batch
```

分開。

避免 PR 同時：

* 改 Behavior
* 改 Architecture
* 改 Formatting

導致 Reviewer 無法判斷。

---

# 31. Backup Before Change

高風險操作前建立：

**Known Good Recovery Point**

可包括：

* clean commit
* branch
* tag
* release
* database backup
* config backup
* deployment snapshot

---

# 32. Git Status Gate

開始任何重要修改：

必須先確認：

`git status`

如果 working tree 不乾淨：

先辨識來源。

不得直接：

```text
reset --hard
clean
force checkout
force push
```

---

# 33. Unknown Changes Policy

發現不屬於目前 AI 的修改：

視為：

**Potential User Work**

不得覆蓋。

先理解。

---

# 34. Branch Strategy

建議：

```text
feature/...
fix/...
refactor/...
perf/...
docs/...
chore/...
hotfix/...
```

重要修改避免直接在：

`main`

開發。

---

# 35. Stable Main

`main` 應視為：

**Potential Production Candidate**

因此不得放入：

* 半成品
* temporary experiment
* known broken build
* unverified patch

---

# 36. Commit Principle

每個 Commit：

* 單一目的
* 可理解
* 可 revert
* 有驗證意義

推薦：

```text
feat:
fix:
refactor:
perf:
test:
docs:
chore:
```

---

# 37. Commit 應回答 Why

不要只描述：

> 改了哪個檔案。

應讓未來 AI 知道：

> 為什麼需要這個變更。

---

# 38. Testing Pyramid

依修改性質執行：

### Static

* lint
* formatter
* type check

### Unit

核心函式。

### Integration

跨模組／API／DB。

### Build

production build。

### Regression

舊功能。

### Smoke

部署環境核心路徑。

---

# 39. Test Scope Based on Impact

不是所有修改都測整個世界。

測試範圍應根據：

**Impact Radius**

例如：

修改共用 formatter：

Impact 高。

修改單一頁面文字：

Impact 低。

---

# 40. Regression Radius

修改一個 module 時至少考慮：

```text
Upstream
Current
Downstream
Shared Dependency
User Flow
```

---

# 41. Definition of Done

只有以下適用項目全部完成：

才可以：

`DONE`

### Requirement

需求完成。

### Root Cause

Bug 根因完成。

### Code

程式完成。

### Test

測試完成。

### Regression

相關 regression 完成。

### Build

需要時完成。

### Deployment

需要時完成。

### Smoke Test

需要時完成。

### Documentation

更新完成。

### Git

Commit / PR 完成。

### Rollback

存在恢復方法。

### Handoff

Next Action 明確。

---

# 42. DONE 不允許推測語氣

以下不是 DONE：

* 應該可以
* 理論上可以
* 看起來沒問題
* 預期正常

若未實測：

標記：

**NOT VERIFIED**

---

# 43. PR Protocol

重要修改建立 Pull Request。

PR 至少：

## Objective

這個 PR 要完成什麼？

## Scope

修改什麼？

## Out of Scope

刻意沒有修改什麼？

## Root Cause

如果是 Bug。

## Solution

採用方案。

## Alternatives

必要時列出。

## Tests

實際執行哪些。

## Risks

風險。

## Rollback

如何回復。

---

# 44. Independent Review Gate

重要 PR Merge 前：

進行一次：

**Independent Third-Party Review**

Reviewer 必須重新判斷。

不能因為：

上一個 Agent 已說通過，

就直接通過。

---

# 45. Reviewer 必須重新檢查

至少：

* Requirement Fit
* Scope
* Root Cause
* Logic
* Architecture
* Regression
* Security
* Performance
* Maintainability
* Test Coverage
* Documentation
* Rollback

---

# 46. Reviewer 也必須限制發散

Independent Review 不是：

重新發明整個專案。

Reviewer 發現新問題時，同樣分類：

```text
BLOCKER
FOLLOW-UP
BACKLOG
REJECT
```

只有 BLOCKER 阻止 Merge。

避免 Reviewer 每次提出無限新要求。

---

# 47. Review Convergence

Review Round 1：

允許廣泛找問題。

Review Round 2：

集中於已識別問題。

Review Round 3：

只確認 Blocker 是否解決。

原則：

**Review 越後期，Scope 越收斂。**

禁止：

每輪 Review 又重新增加完全不同的大型需求。

除非發現 Critical Issue。

---

# 48. Release Gate

Merge 後依專案需要建立：

* Tag
* Release
* Stable checkpoint

Release 記錄：

* Version
* Date
* Major Changes
* Fixes
* Known Issues
* Migration
* Rollback Reference

---

# 49. Deployment Protocol

標準流程：

```text
Feature / Fix
↓
Test
↓
PR
↓
Independent Review
↓
Merge
↓
Build
↓
Deploy
↓
Smoke Test
↓
Production Verification
↓
Release
```

---

# 50. Deployment Failure Rule

若 Production 出現：

* Critical Bug
* Core Feature Failure
* Auth failure
* Data risk
* Severe regression

優先：

**Rollback**

而不是直接在 Production 持續疊 Patch。

---

# 51. Rollback 後仍需 RCA

Rollback 只是恢復服務。

不是問題解決。

之後：

```text
Incident
↓
Evidence
↓
RCA
↓
Fix
↓
Test
↓
Review
↓
Redeploy
```

---

# 52. Dependency Upgrade Rule

Dependency 不能「順便升級」。

升級必須有理由：

* security
* compatibility
* required feature
* unsupported version
* critical bug

如果只是：

有新版。

加入 Backlog 即可。

---

# 53. Framework Migration Rule

更換：

* framework
* database
* ORM
* chart library
* state management
* UI framework

屬於重大架構決策。

需要：

* Current problem
* Alternative
* Benefit
* Migration cost
* Risk
* Rollback
* Staged plan

不得在普通 Bug Fix 中順便完成。

---

# 54. Performance Rule

效能優化遵守：

```text
Measure
↓
Locate
↓
Hypothesis
↓
Optimize
↓
Measure Again
```

不得：

憑感覺優化。

---

# 55. Optimization Evidence

如果聲稱：

> 效能改善。

原則上應有：

Before / After

例如：

* latency
* API calls
* memory
* bundle
* render
* execution time

---

# 56. Security Override

Security 發現可突破一般 Scope Lock。

但必須區分：

### Critical

立即處理。

### High

Current / Next Batch。

### Medium

Plan。

### Low

Backlog。

避免因為看到任何低風險 security lint 就停止全部專案。

---

# 57. Data Integrity Override

任何涉及：

* 資料遺失
* 錯誤寫入
* 重複交易
* 不一致計算
* 無法 rollback migration

均優先於一般功能優化。

---

# 58. Documentation as State

文件不是事後作文。

而是：

**專案狀態的一部分。**

程式完成而：

`to_do_update_list.md`

沒有更新：

該 Batch 不算完全完成。

---

# 59. `to_do_update_list.md` 標準結構

至少：

```text
# Project Status

# Current Stable State

# Architecture Notes

# Master Plan

# Current Phase

# Current Batch

# Active Work

# Completed Work

# Change Log

# Decision Log

# Root Cause Log

# Known Issues

# Technical Debt

# Deferred Candidates

# Rejected Candidates

# Risks

# Next Actions
```

---

# 60. Master Plan

建議使用：

| Phase | Batch | Objective | Priority | Status | Dependency | Verification |
| ----- | ----- | --------- | -------- | ------ | ---------- | ------------ |

Status：

```text
TODO
READY
IN PROGRESS
BLOCKED
VERIFYING
DONE
DEFERRED
REJECTED
```

---

# 61. Current Batch 必須唯一

原則上應清楚指出：

> 現在主線是哪一個 Batch？

避免同時十個：

`IN PROGRESS`

如果確實需要平行工作：

清楚標示：

```text
Primary
Secondary
Blocked
```

---

# 62. Change Log

每批記錄：

* Date
* Phase
* Batch
* Requirement
* Scope
* Files
* Root Cause
* Implementation
* Verification
* Result
* Commit
* PR
* Release
* Deployment
* Follow-up

---

# 63. Decision Log

每個重大決策記：

```text
Decision
Context
Evidence
Alternatives
Reason
Trade-off
Status
Reopen Condition
```

最後一項：

**Reopen Condition**

非常重要。

提前定義：

什麼情況下才值得重新討論。

---

# 64. Deferred Candidates

發散過程發現但暫時不做的項目：

進入：

`Deferred Candidates`

記錄：

```text
Candidate
Value
Reason Deferred
Dependency
Revisit Condition
```

這能避免：

AI 忘記，

也避免：

AI 現在亂做。

---

# 65. Rejected Candidates

重要但最後否決的方案也值得記錄。

避免下一個 AI：

再次花大量時間研究已經否決的方案。

記錄：

```text
Candidate
Why Considered
Why Rejected
Reopen Condition
```

---

# 66. Root Cause Log

重大 Bug：

```text
Symptom
Trigger
Impact
Failure Point
Root Cause
Systemic Cause
Fix
Regression Protection
Commit
PR
```

---

# 67. AI Handoff

每次工作結束前確認下一個 AI 能回答：

1. Production 正常嗎？
2. Main branch 正常嗎？
3. Stable version 是什麼？
4. Current Phase？
5. Current Batch？
6. 剛完成什麼？
7. 為什麼這樣做？
8. 實際驗證什麼？
9. 哪些 Candidate 被延後？
10. 哪些方向已被否決？
11. 有什麼 blocker？
12. 下一步做什麼？
13. 哪些決策目前 Locked？
14. 哪些條件出現才能重新開啟？

---

# 68. Session Startup Protocol

新 ChatGPT / Codex Session 依序：

### 1

讀：

`AI_PROJECT_PLAYBOOK.md`

### 2

讀：

`README.md`

### 3

讀：

`to_do_update_list.md`

### 4

檢查 Git。

### 5

檢查最近 Commit / PR / Release。

### 6

找：

`Current Phase`

### 7

找：

`Current Batch`

### 8

找：

`Next Action`

### 9

辨識 Locked Decisions。

### 10

才開始工作。

---

# 69. 新 AI 不得自行重啟規劃

新的 AI Session 不代表：

新的專案。

不得因為缺少前次聊天：

就重新建立另一套 Master Plan。

Repository 文件與 Git 歷史優先。

---

# 70. User Intent Priority

如果使用者明確要求：

* 改方向
* 暫停
* 重排
* 重新審查
* 回退

則更新：

Master Plan。

但應保留原決策歷史。

---

# 71. Controlled Replanning

重新規劃不是：

把舊計畫刪掉。

而是：

```text
Old Baseline
↓
New Evidence / Requirement
↓
Delta
↓
Revised Baseline
```

記錄：

為什麼改。

---

# 72. Optimization Saturation

# 優化飽和判定

專案不應永久處於：

「還可以再優化」。

某方向符合以下情況後：

應視為暫時收斂：

* requirement satisfied
* major bugs resolved
* acceptable performance
* acceptable maintainability
* tests sufficient
* deployment stable
* marginal benefit low

狀態：

**OPTIMIZED FOR CURRENT REQUIREMENTS**

不是：

「永遠完美」。

---

# 73. Diminishing Returns Rule

如果下一個優化：

成本明顯提高，

但收益非常有限：

停止。

加入：

Backlog。

避免工程進入：

Optimization Rabbit Hole。

---

# 74. 主線優先原則

任何時候都應能回答：

> 本專案現在最重要的主線是什麼？

如果答不出來：

表示工作已過度發散。

立即執行：

**Convergence Review**

---

# 75. Convergence Review

當出現：

* 太多 TODO
* 太多方向
* 多個 Agent 各做不同事情
* 每次 Review 都新增工作
* 長期沒有 Phase 完成
* 修改持續增加但產品沒有進展

立即：

1. 暫停新增 Candidate。
2. 整理所有 Active Work。
3. 分類 NOW / NEXT / BACKLOG / REJECT。
4. 選定唯一 Primary Goal。
5. 重新建立 Current Phase。
6. 建立 Current Batch。
7. 其餘全部延後。
8. 繼續主線。

---

# 76. WIP Limit

# 在製工作限制

避免同時啟動大量工作。

原則：

```text
Current Primary Batch = 1
```

必要時可以存在：

* 1 Primary
* 少量 supporting investigation

但不要同時：

5～10 個主要 Batch。

---

# 77. Agent Coordination

如果使用多 Agent：

可以平行：

* Research
* Test
* Review
* Root Cause Investigation

但：

Implementation 必須有明確 Owner。

避免多 Agent 同時修改：

同一核心檔案。

---

# 78. Parallel Agent Convergence

多 Agent 結果回收後：

必須：

```text
Collect
↓
Compare
↓
Resolve Conflict
↓
Select
↓
Converge
↓
Implement
```

不得把所有 Agent 提案全部實作。

---

# 79. AI 建議與 AI 執行分離

AI 可以提出：

10 個改善方向。

但不代表：

10 個都執行。

必須經過：

Priority / Scope / Risk / Convergence。

---

# 80. No Premature Implementation

如果仍存在三種彼此衝突的 Root Cause hypothesis：

不要急著寫 Code。

先把 hypothesis 收斂。

---

# 81. No Premature Refactor

如果問題可以透過：

小範圍 Root Cause Fix

解決，

不得因為：

「未來可能比較漂亮」

直接做大規模重構。

---

# 82. No Premature Optimization

沒有證據顯示效能瓶頸：

不要優化。

---

# 83. No Premature Generalization

目前只有一種 case：

不要過度設計成：

支援未來十種 hypothetical case。

除非 Roadmap 已確認。

---

# 84. Compatibility First

已有使用者使用的功能：

優先保持：

* API compatibility
* Data compatibility
* UI behavior
* Existing workflow

除非 Requirement 明確改變。

---

# 85. Change Surface Minimization

達成需求時：

優先選擇：

**最小正確修改面積。**

不是：

最少 Code 行數。

而是：

最少不必要系統影響。

---

# 86. Failure Transparency

遇到：

* Test fail
* Build fail
* Deploy fail
* Unknown behavior
* Missing permission
* Unverified assumption

必須明確記錄。

不得把：

Partially Complete

描述成：

Complete。

---

# 87. Stop Conditions

遇到以下情況暫停 Implementation：

* Working tree 不明
* 可能覆蓋使用者修改
* 資料損毀風險
* Security critical
* 基礎假設被推翻
* Root Cause 完全不明
* Rollback 無法確認
* 大規模 Scope creep

先重新分析。

---

# 88. Resume Conditions

暫停後至少確認：

* Evidence sufficient
* Scope重新定義
* Recovery point 存在
* Current Batch 明確
* Risk 可接受

才繼續。

---

# 89. 每批標準報告

每個 Batch 完成後回報：

## Objective

本批目標。

## Completed

實際完成。

## Root Cause

若適用。

## Files Changed

修改檔案。

## Verification

實際執行什麼。

## Regression

驗證哪些舊功能。

## Git

Branch / Commit / PR。

## Documentation

`to_do_update_list.md` 更新內容。

## Discoveries

發現哪些額外問題。

## Convergence Decisions

額外問題分別：

* NOW
* NEXT
* BACKLOG
* REJECT

## Remaining Risk

剩餘風險。

## Next

下一個 Batch。

---

# 90. Project Optimization Philosophy

本專案採用：

**Broad Thinking, Narrow Execution**

即：

### 分析可以廣。

### 證據可以深。

### Candidate 可以多。

### 最終執行必須窄。

---

# 91. 發散的目的

不是增加工作。

而是：

**避免做錯工作。**

---

# 92. 收斂的目的

不是限制改善。

而是：

**確保改善真的完成。**

---

# 93. 最終優化循環

專案長期以：

```text
Explore
↓
Understand
↓
Prioritize
↓
Converge
↓
Execute
↓
Verify
↓
Stabilize
↓
Observe
↓
Next Cycle
```

演進。

不是：

```text
Explore
↓
Explore
↓
Explore
↓
Refactor
↓
Explore
↓
Rewrite
```

---

# 94. 每個 Phase 的結束條件

Phase 完成時：

* Objectives achieved
* All critical Batch done
* Major regression resolved
* Documentation updated
* Known issues classified
* Deferred items moved to backlog
* Stable checkpoint created

然後：

**關閉 Phase。**

不應因為仍存在無限優化可能，

而永遠不結束。

---

# 95. 下一 Phase 開始前

重新檢視：

* Requirement
* Evidence
* Priority
* Backlog

只挑選：

目前最有價值的少數方向。

---

# 96. 核心治理公式

本專案不採：

**不要發散。**

而採：

> **有條件探索、有證據發散、有機制收斂、有紀錄延後、有門檻重新開啟。**

---

# 97. 最終判斷問題

修改程式前：

> 我理解現在的系統嗎？

Debug 前：

> 我找到的是症狀、Failure Point，還是 Root Cause？

擴大分析前：

> 這個發散有證據與目的嗎？

新增工作前：

> 它應該是 NOW、NEXT、BACKLOG 還是 REJECT？

準備實作前：

> Scope 是否已重新收斂？

準備重構前：

> 這是必要重構，還是偏好型重構？

Commit 前：

> 這一版能獨立正常使用嗎？

Merge 前：

> Independent Reviewer 會批准嗎？

Deploy 前：

> 可以恢復到 Last Known Good Version 嗎？

結束 Phase 前：

> 還剩下的是必要工作，還是只是「可以更好」？

結束 Session 前：

> 完全沒看過這次對話的下一個 AI，只看 Repository，能否無歧義接手？

---

# 98. 最終原則

本專案追求的不是：

**最大修改量。**

而是：

**最大有效改善。**

不是：

**永遠增加優化方向。**

而是：

**先充分探索，再逐步刪減方向。**

不是：

**禁止發散。**

而是：

**Controlled Divergence。**

不是：

**過早收斂。**

而是：

**Evidence-Based Convergence。**

不是：

**一次做到完美。**

而是：

**每一批都比上一批更好，而且始終可用。**

最終形成：

> **可探索、可收斂、可理解、可驗證、可追蹤、可回滾、可交接、可持續演進的 AI 協作軟體專案。**
