import type { ReactNode } from "react";
import type { WorkspaceModel } from "./types";

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step = "any",
  suffix,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number | "any";
  suffix?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <div className="input-with-suffix">
        <input
          type="number"
          inputMode="decimal"
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={(event) => {
            const parsed = Number(event.target.value);
            onChange(Number.isFinite(parsed) ? parsed : 0);
          }}
        />
        {suffix && <span>{suffix}</span>}
      </div>
    </label>
  );
}

function Toggle({ label, checked, onChange, hint }: { label: string; checked: boolean; onChange: (value: boolean) => void; hint?: string }) {
  return (
    <label className="toggle-row">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>
        <strong>{label}</strong>
        {hint && <small>{hint}</small>}
      </span>
    </label>
  );
}

function SettingGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="setting-group">
      <legend>{title}</legend>
      <div className="settings-grid">{children}</div>
    </fieldset>
  );
}

export function SettingsPanels({
  model,
  setModel,
}: {
  model: WorkspaceModel;
  setModel: (updater: (current: WorkspaceModel) => WorkspaceModel) => void;
}) {
  return (
    <section className="workspace-card settings-card" aria-labelledby="settings-title">
      <div className="section-heading">
        <div>
          <span className="section-index">02</span>
          <div>
            <h2 id="settings-title">模擬規則與分析</h2>
            <p>所有指標使用完整每日 TWD 帳本；輸出頻率只縮減圖表資料點。</p>
          </div>
        </div>
      </div>

      <SettingGroup title="基本設定">
        <label className="field">
          <span>開始日期</span>
          <input type="date" value={model.startDate} onChange={(event) => setModel((current) => ({ ...current, startDate: event.target.value }))} />
        </label>
        <label className="field">
          <span>結束日期</span>
          <input type="date" value={model.endDate} onChange={(event) => setModel((current) => ({ ...current, endDate: event.target.value }))} />
        </label>
        <NumberField label="初始金額" value={model.initialAmount} min={1} step={1000} suffix="TWD" onChange={(value) => setModel((current) => ({ ...current, initialAmount: value }))} />
        <label className="field">
          <span>比較基準</span>
          <input value={model.benchmark} placeholder="SPY" onChange={(event) => setModel((current) => ({ ...current, benchmark: event.target.value.toUpperCase() }))} />
        </label>
        <label className="field">
          <span>圖表輸出頻率</span>
          <select value={model.outputFrequency} onChange={(event) => setModel((current) => ({ ...current, outputFrequency: event.target.value as WorkspaceModel["outputFrequency"] }))}>
            <option value="daily">每日</option>
            <option value="weekly">每週</option>
            <option value="monthly">每月</option>
          </select>
        </label>
        <NumberField label="交易成本" value={model.transactionCostBps} min={0} max={1000} step={0.1} suffix="bps" onChange={(value) => setModel((current) => ({ ...current, transactionCostBps: value }))} />
        <Toggle label="納入今年 YTD" checked={model.includeYtd} onChange={(value) => setModel((current) => ({ ...current, includeYtd: value }))} />
        <Toggle label="配息再投入" checked={model.reinvestDistributions} hint="關閉時配息保留為 TWD 現金" onChange={(value) => setModel((current) => ({ ...current, reinvestDistributions: value }))} />
      </SettingGroup>

      <SettingGroup title="外部現金流">
        <label className="field">
          <span>現金流類型</span>
          <select value={model.cashflow.type} onChange={(event) => setModel((current) => ({ ...current, cashflow: { ...current.cashflow, type: event.target.value as WorkspaceModel["cashflow"]["type"], frequency: event.target.value === "none" ? "none" : current.cashflow.frequency === "none" ? "monthly" : current.cashflow.frequency } }))}>
            <option value="none">停用</option>
            <option value="fixed">固定金額</option>
            <option value="percent">投組淨值百分比</option>
          </select>
        </label>
        <NumberField label={model.cashflow.type === "percent" ? "流量比例" : "流量金額"} value={model.cashflow.amount} step={model.cashflow.type === "percent" ? 0.1 : 1000} suffix={model.cashflow.type === "percent" ? "%" : "TWD"} onChange={(value) => setModel((current) => ({ ...current, cashflow: { ...current.cashflow, amount: value } }))} />
        <label className="field">
          <span>頻率</span>
          <select disabled={model.cashflow.type === "none"} value={model.cashflow.frequency} onChange={(event) => setModel((current) => ({ ...current, cashflow: { ...current.cashflow, frequency: event.target.value as WorkspaceModel["cashflow"]["frequency"] } }))}>
            <option value="none">無</option><option value="monthly">每月</option><option value="quarterly">每季</option><option value="annual">每年</option>
          </select>
        </label>
        <label className="field">
          <span>執行時點</span>
          <select disabled={model.cashflow.type === "none"} value={model.cashflow.timing} onChange={(event) => setModel((current) => ({ ...current, cashflow: { ...current.cashflow, timing: event.target.value as WorkspaceModel["cashflow"]["timing"] } }))}>
            <option value="beginning">期初</option><option value="end">期末</option>
          </select>
        </label>
        <NumberField label="年度成長率" value={model.cashflow.annualGrowthRatePercent} min={-99.99} max={1000} step={0.1} suffix="%" onChange={(value) => setModel((current) => ({ ...current, cashflow: { ...current.cashflow, annualGrowthRatePercent: value } }))} />
      </SettingGroup>

      <SettingGroup title="再平衡與槓桿">
        <label className="field">
          <span>定期再平衡</span>
          <select value={model.rebalancing.frequency} onChange={(event) => setModel((current) => ({ ...current, rebalancing: { ...current.rebalancing, frequency: event.target.value as WorkspaceModel["rebalancing"]["frequency"] } }))}>
            <option value="none">不定期</option><option value="monthly">每月</option><option value="quarterly">每季</option><option value="semiannual">每半年</option><option value="annual">每年</option>
          </select>
        </label>
        <NumberField label="權重偏離門檻（0 表示停用）" value={model.rebalancing.thresholdPercent ?? 0} min={0} max={100} step={0.1} suffix="%" onChange={(value) => setModel((current) => ({ ...current, rebalancing: { ...current.rebalancing, thresholdPercent: value > 0 ? value : null } }))} />
        <label className="field">
          <span>槓桿模式</span>
          <select value={model.leverage.type} onChange={(event) => setModel((current) => ({ ...current, leverage: { ...current.leverage, type: event.target.value as WorkspaceModel["leverage"]["type"] } }))}>
            <option value="none">無槓桿</option><option value="fixed_ratio">固定倍數</option><option value="fixed_debt">固定借款</option>
          </select>
        </label>
        {model.leverage.type === "fixed_ratio" && <NumberField label="槓桿倍數" value={model.leverage.ratio} min={1.01} max={5} step={0.05} suffix="×" onChange={(value) => setModel((current) => ({ ...current, leverage: { ...current.leverage, ratio: value } }))} />}
        {model.leverage.type === "fixed_debt" && <NumberField label="固定借款金額" value={model.leverage.debtAmount} min={0} step={1000} suffix="TWD" onChange={(value) => setModel((current) => ({ ...current, leverage: { ...current.leverage, debtAmount: value } }))} />}
        {model.leverage.type !== "none" && <NumberField label="借款年利率" value={model.leverage.annualInterestRatePercent} min={0} max={100} step={0.1} suffix="%" onChange={(value) => setModel((current) => ({ ...current, leverage: { ...current.leverage, annualInterestRatePercent: value } }))} />}
        {model.leverage.type !== "none" && <NumberField label="維持保證金率" value={model.leverage.maintenanceMarginPercent} min={0} max={100} step={0.1} suffix="%" onChange={(value) => setModel((current) => ({ ...current, leverage: { ...current.leverage, maintenanceMarginPercent: value } }))} />}
      </SettingGroup>

      <SettingGroup title="進階分析">
        <NumberField label="無風險利率" value={model.analytics.riskFreeRatePercent} min={-99} max={100} step={0.1} suffix="%" onChange={(value) => setModel((current) => ({ ...current, analytics: { ...current.analytics, riskFreeRatePercent: value } }))} />
        <label className="field">
          <span>市場環境分析</span>
          <select value={model.analytics.regime} onChange={(event) => setModel((current) => ({ ...current, analytics: { ...current.analytics, regime: event.target.value as WorkspaceModel["analytics"]["regime"] } }))}>
            <option value="none">停用</option><option value="market">多空環境</option><option value="volatility">高低波動</option><option value="inflation">通膨環境</option><option value="business_cycle">景氣循環</option>
          </select>
        </label>
        <Toggle label="Fama–French + FX 曝險" checked={model.analytics.factorAnalysis} hint="需較長月資料；因子與匯率 Beta 分開呈現" onChange={(value) => setModel((current) => ({ ...current, analytics: { ...current.analytics, factorAnalysis: value } }))} />
        <Toggle label="受約束風格分析" checked={model.analytics.styleAnalysis} hint="IWD/IWF/IWS/IWP/IWN/IWO，權重非負且合計 100%" onChange={(value) => setModel((current) => ({ ...current, analytics: { ...current.analytics, styleAnalysis: value } }))} />
        <Toggle label="通膨調整" checked={model.analytics.inflationAdjusted} hint="目前使用 U.S. CPI，結果會明示限制" onChange={(value) => setModel((current) => ({ ...current, analytics: { ...current.analytics, inflationAdjusted: value } }))} />
        <Toggle label="保留帳本事件" checked={model.includeEvents} onChange={(value) => setModel((current) => ({ ...current, includeEvents: value }))} />
        <Toggle label="保留每日配置歷史" checked={model.includeAllocationHistory} hint="回應較大，僅在需要配置漂移明細時啟用" onChange={(value) => setModel((current) => ({ ...current, includeAllocationHistory: value }))} />
      </SettingGroup>
    </section>
  );
}
