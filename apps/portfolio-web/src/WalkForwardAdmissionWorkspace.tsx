import { useEffect, useState } from "react";
import { getWalkForwardAdmission } from "./walkForwardApi";
import {
  WALK_FORWARD_WORKSPACE_STORAGE_KEY,
  createWalkForwardModelFromAdmission,
  migrateWalkForwardModel,
} from "./walkForwardModel";
import { WalkForwardWorkspace } from "./WalkForwardWorkspace";
import type { WalkForwardAdmissionResponse, WalkForwardWorkspaceModel } from "./walkForwardTypes";

type AdmissionState = "loading" | "ready" | "unavailable";

function readSavedModel(): WalkForwardWorkspaceModel | null {
  try {
    const raw = window.localStorage.getItem(WALK_FORWARD_WORKSPACE_STORAGE_KEY);
    return raw ? migrateWalkForwardModel(JSON.parse(raw) as unknown) : null;
  } catch {
    return null;
  }
}

function isLegacyImpossibleDefault(model: WalkForwardWorkspaceModel): boolean {
  return model.periods.length === 1 && model.universe === "sp500" && model.holdingCount === 10;
}

function persistRecommended(admission: WalkForwardAdmissionResponse): boolean {
  const recommended = createWalkForwardModelFromAdmission(admission);
  if (!recommended) return false;
  try {
    window.localStorage.setItem(WALK_FORWARD_WORKSPACE_STORAGE_KEY, JSON.stringify(recommended));
  } catch {
    return false;
  }
  return true;
}

function blockedReason(reason: string | undefined): string {
  if (reason === "proxy_membership_only") return "目前只有 proxy 成分證據";
  if (reason === "candidate_limit") return "PIT candidates 超過同步研究上限";
  if (reason === "no_causal_snapshot_window") return "目前沒有符合時序的 PIT 快照";
  if (reason === "combination_budget") return "Exhaustive 組合數超過同步上限";
  return "目前不可執行";
}

export function WalkForwardAdmissionWorkspace() {
  const [state, setState] = useState<AdmissionState>("loading");
  const [admission, setAdmission] = useState<WalkForwardAdmissionResponse | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getWalkForwardAdmission(controller.signal)
      .then((nextAdmission) => {
        setAdmission(nextAdmission);
        const saved = readSavedModel();
        if ((!saved || isLegacyImpossibleDefault(saved)) && persistRecommended(nextAdmission)) {
          setRevision((current) => current + 1);
        }
        setState("ready");
      })
      .catch(() => setState("unavailable"));
    return () => controller.abort();
  }, []);

  function applyRecommended() {
    if (!admission || !persistRecommended(admission)) return;
    setRevision((current) => current + 1);
  }

  if (state === "loading") {
    return (
      <div className="walk-forward-workspace">
        <div className="notice info" role="status">
          <strong>正在讀取 PIT admission</strong>
          <p>確認哪些 Universe、Decision 日期與持股檔數目前具有可執行的因果證據。</p>
        </div>
      </div>
    );
  }

  return (
    <>
      {state === "ready" && admission && (
        <section className="workspace-card" aria-label="Walk-Forward admission">
          <div className="section-heading">
            <div>
              <span className="section-index">A</span>
              <div>
                <h2>目前可執行範圍</h2>
                <p>D1 PIT archive 只負責提前說明 admission；正式研究仍由後端重新驗證全部因果與容量條件。</p>
              </div>
            </div>
            <div className="section-actions">
              <button type="button" className="secondary" disabled={!admission.recommended} onClick={applyRecommended}>套用可執行預設</button>
            </div>
          </div>
          {admission.recommended ? (
            <div className="notice info" aria-live="polite">
              <strong>建議：{admission.recommended.universe.toUpperCase()} · Decision {admission.recommended.decisionDate} · {admission.recommended.holdingCount} 檔</strong>
              <p>{admission.recommended.memberCount} 個 PIT candidates，Exhaustive {admission.recommended.combinationCount.toLocaleString()} 組；最後完整 UTC 日 {admission.asOfDate}。</p>
            </div>
          ) : (
            <div className="notice warning"><strong>目前沒有同步 Walk-Forward 可執行 Universe</strong><p>請等待 PIT archive 更新或縮小研究方法後再執行。</p></div>
          )}
          <div className="wf-run-guidance">
            {admission.universes.map((universe) => (
              <span key={universe.id}>
                <strong>{universe.id.toUpperCase()}：</strong>
                {universe.status === "eligible"
                  ? `${universe.earliestDecisionDate}–${universe.latestDecisionDate} 可用，建議 ${universe.recommendedHoldingCount} 檔`
                  : blockedReason(universe.reason)}
              </span>
            ))}
          </div>
        </section>
      )}
      {state === "unavailable" && (
        <div className="notice warning">
          <strong>PIT admission 暫時無法讀取</strong>
          <p>工作區仍可使用；正式研究送出時後端會維持 fail-closed 驗證。</p>
        </div>
      )}
      <WalkForwardWorkspace key={revision} />
    </>
  );
}
