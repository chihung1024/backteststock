# AGENTS.md — First-Principles Engineering

本檔是本 Repository 唯一的 Active Governance。

目標：用最少流程，持續產出正確、可驗證、可恢復、對使用者有價值的產品。

## 1. Reality & Product

以使用者目標、目前 code/contracts 與 Git/PR/CI/runtime truth 為準。

Product / UX 與 Correctness / Data Integrity / Security / Quant & Financial Correctness 優先；必要技術工作其次；optional cleanup / refactor / process 最後。

Governance 只以最新 remote default branch 的 `AGENTS.md` 為準；feature/PR branch copy 可能過期，不需要只為讀規則而 merge/rebase。

新 Session：`AGENTS.md → to_do_update_list.md → relevant code/contracts/docs → current truth → work`。

同一工作鏈直接 resume，不因新回合、新模型或「繼續」而重新研究整個 Repository。

## 2. Loop Engineering

`Observe → Understand → Decide → Smallest Useful Change → Verify → Learn → Continue`

每一圈必須增加可信資訊或產生已驗證改善。

一次只維持一條 Primary Implementation。分析可以廣，實作保持最小；證據足以支持決策後停止額外調查並行動。

## 3. First-Principles Debug

`Observed Fact → Expected Invariant → Smallest Reproduction → Failure Point → Root Cause → Minimum Correct Fix → Regression`

- Symptom ≠ Root Cause。
- 沒有足夠證據時：`Root Cause = NOT VERIFIED`。
- 優先取得能證明或反證假設的 evidence。
- 多個症狀若來自同一原因，修共同原因；問題確實局部時，不為了「系統性」強迫重構。
- Workaround ≠ Permanent Fix。

修改前問：如果 Root Cause 判斷正確，為什麼這個修改應該修好問題？

修改後問：什麼 evidence 能證明它不是偶然通過？

## 4. Verify & Self Review

沒有驗證，不宣稱完成。

一般修改：targeted verification + relevant regression + build/CI when applicable。

完成前反問：

- Requirement 真的滿足了嗎？
- Diff 有沒有不必要修改？
- 哪個核心假設最可能錯？
- 最可能的 regression / edge case 是什麼？
- Tests 驗證 behavior，還是只讓 CI green？

只有高後果修改才增加 broader verification、rollback/recovery、independent review 或 production verification。高後果包括 security/auth、data corruption/loss、quant or financial methodology、PIT/Walk-Forward causality、destructive migration、major production recovery 或 difficult rollback。

## 5. Protect the System

不要覆蓋未知 Git / other-agent work；不要無理由 destructive reset、clean、force push 或破壞 recovery point。

Security、Data Integrity、Quant/Financial Correctness 與 PIT/Walk-Forward 因果正確性採保守處理。重要修改必須知道失敗後如何恢復。

## 6. Continue & Handoff

有合理、已授權、可執行的下一步就直接執行；不要用「下一步我會……」取代工作，也不要把 Owner 當 Continue 按鈕。

遇到障礙先嘗試合理、直接相關的替代方法，但不要無限探索工具。

平台 turn / quota / session 結束不是 Project Blocker；保存 checkpoint，下一個環境直接 resume。

真正無法繼續時只需留下：`Blocker / Evidence / Tried / Minimum Human Action / Resume Point`。

`to_do_update_list.md` 是唯一持續執行記憶；保持 CURRENT 精確、NEXT 有順序、ROADMAP 可調整、歷史持續壓縮。

不得自行建立新的 Active Governance、Playbook、Governance Gate、流程矩陣或 governance prose test。

本檔如需語意修改，先提出最小具體變更並取得 Repository Owner 明確「特別同意治理修改」。一般開發、PR、merge 或「給你所有權限」不等於治理修改授權。
