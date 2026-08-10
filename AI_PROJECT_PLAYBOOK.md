## V3.0 Final Hardening — Final Patch

### 1. Final Risk Reclassification

在 `Risk Classification Gate` 補充：

> **對 R1 以上 Batch，Risk Class 必須在 final candidate / merge gate 前重新確認一次。**
>
> Final Risk Classification 應依據：
>
> * final diff
> * actual behavior change
> * discovered evidence
> * actual blast radius
> * contract / governance impact
> * rollback characteristics
> * current remote state
>
> 重新判定。
>
> Initial Risk Class 不因 Batch 已開始而自動延續至 Merge。
>
> 若 final candidate 的實際影響高於初始判斷，應先完成 Risk Upgrade 及其新增適用 Gate，再進入 Merge。
>
> 若介於兩級之間且缺乏充分降級證據，仍適用：
>
> ```text
> Uncertainty
> ↓
> Higher-Risk Default
> ```

---

### 2. Reviewer / Implementer Role Separation

在 `Same-AI Independent Review Isolation Protocol` 補充：

## Reviewer / Implementer Role Separation

Independent Review 期間，Reviewer 不得同時修改正在被審查的 candidate。

如果 Review 發現 BLOCKER：

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

禁止：

```text
Review
↓
Discover Problem
↓
Silent Fix
↓
Continue Same Review
↓
PASS
```

Reviewer 必須讓：

* finding
* fix
* validation
* reviewed candidate

之間保持清楚的 audit trail。

> **任何 material fix 都會產生新的 candidate head；原 review conclusion 不自動繼承。**

Material change 包括但不限於：

* behavior
* methodology
* API semantics
* data semantics
* security behavior
* persistence
* architecture
* deployment behavior

Non-material change，例如純 typo 或不改語意的 formatting，可依 `Exact-Head Principle` 執行 focused re-review，而不需要重新進行完整 Review。

Same-AI Independent Review 的 `independence` 來自：

```text
Role Separation
+
Fresh Evidence Reconstruction
+
Adversarial Reasoning
+
Exact-Head Discipline
```

不是單純宣告進入 Reviewer Mode。

---

### 3. Grandfather Anti-Bypass

在 `Grandfather Current Batch` 補充：

## Grandfather Anti-Bypass

Grandfather 機制的目的，是避免 Governance evolution 對已進行中的工作造成不成比例的 retrofitting cost。

它不得被用來消除在 Governance Change 生效前，已經由證據明確成立的：

* safety blocker
* security blocker
* data-integrity blocker
* correctness blocker

因此：

```text
Existing Material Blocker
+
Governance Change
≠
Automatic Blocker Removal
```

若 Active Batch 的唯一 blocker 正是本次 Governance Change 所修改的 Gate：

必須先完成：

```text
Governance Change Review
↓
Current PR / Batch Transition Assessment
↓
Apply New Governance Rule
↓
Satisfy New Rule
```

不得單靠：

```text
Grandfather Current Batch
```

宣告 blocker 已解除。

> **Grandfather ≠ bypass escape hatch。**

Governance Change 可以修正錯誤或低價值的舊流程，但不能使尚未取得的 correctness / safety evidence 被視為已經取得。

---

### 4. R0 Text Correction

`Current Example Principle` 統一修正為：

* repository 為單人維護；
* 不同帳號本身沒有 correctness value；
* 真正需求是 independent reasoning + competence；

---

# V3.0 Governance Lock

完成上述 Final Patch 後：

```text
AI_PROJECT_PLAYBOOK V3.0

Status:
GOVERNANCE BASELINE LOCKED

Governance Architecture:
FROZEN

Further Governance Optimization:
STOPPED

Reopen:
ONLY BY DOCUMENTED REOPEN CONDITION
```

此後不得因：

* wording preference
* another AI's preferred workflow
* theoretical completeness
* enterprise best practice
* hypothetical edge case
* 「再多一條可能更完整」

重新開啟治理設計。

新的 governance idea 預設：

```text
BACKLOG
或
REJECT
```

只有出現 V3.0 已定義之 Reopen Condition 與實際 evidence，才允許重新開啟。

長期循環正式改為：

```text
Use V3
↓
Execute Real Project Work
↓
Observe
↓
Collect Actual Evidence
↓
Governance Works?
├─ YES → Keep Frozen
└─ NO  → Check Reopen Condition
          ↓
        Evidence-Based Governance Reopen
```

而不再採：

```text
Governance
↓
More Governance
↓
More Edge Cases
↓
More Rules
```

---

# Final Constitutional Core

> **Broad Thinking, Narrow Execution.**

> **Evidence First, Risk-Proportional Governance.**

> **獨立審查重點是獨立推理與專業能力，不是不同人頭。**

V3.0 的目標不是建立最大化流程，而是：

> **用最少但足夠的工程控制，持續產出正確、可驗證、可追溯、可回滾、可交接的 Stable State。**
