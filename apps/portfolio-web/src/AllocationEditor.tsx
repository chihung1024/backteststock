import { useEffect, useMemo, useState } from "react";
import { searchAssets } from "./api";
import {
  addAsset,
  addPortfolio,
  clearPortfolio,
  copyPortfolio,
  equalWeightPortfolio,
  normalizePortfolio,
  normalizeSymbol,
  portfolioWeightTotal,
  removeAsset,
  removePortfolio,
} from "./model";
import type { SearchResult, WorkspaceModel } from "./types";

function numberValue(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function AllocationEditor({
  model,
  setModel,
}: {
  model: WorkspaceModel;
  setModel: (updater: (current: WorkspaceModel) => WorkspaceModel) => void;
}) {
  const [mobilePortfolioId, setMobilePortfolioId] = useState(model.portfolios[0]?.id ?? "");
  const [activeSearchId, setActiveSearchId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<SearchResult[]>([]);
  const [searchBusy, setSearchBusy] = useState(false);
  const activeAsset = model.assets.find((asset) => asset.id === activeSearchId);

  useEffect(() => {
    if (model.portfolios.some((portfolio) => portfolio.id === mobilePortfolioId)) return;
    setMobilePortfolioId(model.portfolios[0]?.id ?? "");
  }, [mobilePortfolioId, model.portfolios]);

  useEffect(() => {
    const query = activeAsset?.symbol.trim() ?? "";
    if (!activeSearchId || query.length < 1) {
      setSuggestions([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setSearchBusy(true);
      searchAssets(query, controller.signal)
        .then((items) => setSuggestions(items))
        .catch((error: unknown) => {
          if (!(error instanceof DOMException && error.name === "AbortError")) setSuggestions([]);
        })
        .finally(() => setSearchBusy(false));
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [activeAsset?.symbol, activeSearchId]);

  const mobilePortfolio = useMemo(
    () => model.portfolios.find((portfolio) => portfolio.id === mobilePortfolioId) ?? model.portfolios[0],
    [mobilePortfolioId, model.portfolios],
  );

  function updateAssetSymbol(assetId: string, symbol: string) {
    setModel((current) => ({
      ...current,
      assets: current.assets.map((asset) => (asset.id === assetId ? { ...asset, symbol } : asset)),
    }));
  }

  function chooseSuggestion(assetId: string, symbol: string) {
    updateAssetSymbol(assetId, normalizeSymbol(symbol));
    setSuggestions([]);
    setActiveSearchId(null);
  }

  function updateWeight(portfolioId: string, assetId: string, value: number) {
    setModel((current) => ({
      ...current,
      portfolios: current.portfolios.map((portfolio) =>
        portfolio.id === portfolioId
          ? { ...portfolio, weights: { ...portfolio.weights, [assetId]: Math.max(0, Math.min(value, 100)) } }
          : portfolio,
      ),
    }));
  }

  function updatePortfolioName(portfolioId: string, name: string) {
    setModel((current) => ({
      ...current,
      portfolios: current.portfolios.map((portfolio) =>
        portfolio.id === portfolioId ? { ...portfolio, name } : portfolio,
      ),
    }));
  }

  const searchMenu = (assetId: string) =>
    activeSearchId === assetId && (searchBusy || suggestions.length > 0) ? (
      <div className="search-suggestions" role="listbox" aria-label="股票代碼搜尋結果">
        {searchBusy && <div className="search-state">搜尋中…</div>}
        {suggestions.map((item) => (
          <button
            type="button"
            role="option"
            key={item.symbol}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => chooseSuggestion(assetId, item.symbol)}
          >
            <strong>{item.symbol}</strong>
            <span>{item.name}</span>
            <small>{[item.exchange, item.currency].filter(Boolean).join(" · ")}</small>
          </button>
        ))}
      </div>
    ) : null;

  return (
    <section className="workspace-card allocation-card" aria-labelledby="allocation-title">
      <div className="section-heading">
        <div>
          <span className="section-index">01</span>
          <div>
            <h2 id="allocation-title">資產配置</h2>
            <p>桌機使用資產 × 投組矩陣；手機聚焦編輯單一投組。每組最多 20 項資產。</p>
          </div>
        </div>
        <div className="section-actions">
          <button type="button" className="secondary" onClick={() => setModel(addAsset)} disabled={model.assets.length >= 20}>
            新增資產
          </button>
          <button type="button" className="secondary" onClick={() => setModel(addPortfolio)} disabled={model.portfolios.length >= 5}>
            新增投組
          </button>
        </div>
      </div>

      <div className="matrix-wrap desktop-matrix" role="region" aria-label="投資組合配置矩陣" tabIndex={0}>
        <table className="allocation-matrix">
          <thead>
            <tr>
              <th scope="col" className="asset-column">資產代碼</th>
              {model.portfolios.map((portfolio) => {
                const total = portfolioWeightTotal(portfolio, model);
                const valid = total === 0 || Math.abs(total - 100) <= 0.05;
                return (
                  <th scope="col" key={portfolio.id}>
                    <input
                      className="portfolio-name-input"
                      value={portfolio.name}
                      onChange={(event) => updatePortfolioName(portfolio.id, event.target.value)}
                      aria-label="投資組合名稱"
                    />
                    <div className={`weight-total ${valid ? "valid" : "invalid"}`}>{total.toFixed(1)}%</div>
                    <div className="mini-actions" aria-label={`${portfolio.name} 操作`}>
                      <button type="button" onClick={() => setModel((current) => equalWeightPortfolio(current, portfolio.id))}>等權</button>
                      <button type="button" onClick={() => setModel((current) => normalizePortfolio(current, portfolio.id))}>正規化</button>
                      <button type="button" onClick={() => setModel((current) => copyPortfolio(current, portfolio.id))} disabled={model.portfolios.length >= 5}>複製</button>
                      <button type="button" onClick={() => setModel((current) => clearPortfolio(current, portfolio.id))}>清空</button>
                      <button type="button" onClick={() => setModel((current) => removePortfolio(current, portfolio.id))} disabled={model.portfolios.length <= 1}>刪除</button>
                    </div>
                  </th>
                );
              })}
              <th scope="col" className="row-action-column">列操作</th>
            </tr>
          </thead>
          <tbody>
            {model.assets.map((asset, rowIndex) => (
              <tr key={asset.id}>
                <th scope="row">
                  <div className="ticker-cell">
                    <label className="sr-only" htmlFor={`ticker-${asset.id}`}>第 {rowIndex + 1} 列股票代碼</label>
                    <input
                      id={`ticker-${asset.id}`}
                      value={asset.symbol}
                      placeholder="例如 SPY / 2330"
                      autoComplete="off"
                      onFocus={() => setActiveSearchId(asset.id)}
                      onBlur={() => window.setTimeout(() => setActiveSearchId(null), 120)}
                      onChange={(event) => {
                        updateAssetSymbol(asset.id, event.target.value.toUpperCase());
                        setActiveSearchId(asset.id);
                      }}
                    />
                    {searchMenu(asset.id)}
                  </div>
                </th>
                {model.portfolios.map((portfolio) => (
                  <td key={portfolio.id}>
                    <label className="weight-input">
                      <span className="sr-only">{portfolio.name} 的 {asset.symbol || `第 ${rowIndex + 1} 列`} 權重</span>
                      <input
                        inputMode="decimal"
                        type="number"
                        min="0"
                        max="100"
                        step="0.01"
                        value={portfolio.weights[asset.id] ?? 0}
                        onChange={(event) => updateWeight(portfolio.id, asset.id, numberValue(event.target.value))}
                      />
                      <span>%</span>
                    </label>
                  </td>
                ))}
                <td>
                  <button
                    type="button"
                    className="icon-button danger"
                    onClick={() => setModel((current) => removeAsset(current, asset.id))}
                    disabled={model.assets.length <= 1}
                    aria-label={`刪除第 ${rowIndex + 1} 列資產`}
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mobile-allocation">
        <label className="field">
          <span>目前編輯投組</span>
          <select value={mobilePortfolio?.id ?? ""} onChange={(event) => setMobilePortfolioId(event.target.value)}>
            {model.portfolios.map((portfolio) => (
              <option value={portfolio.id} key={portfolio.id}>{portfolio.name}</option>
            ))}
          </select>
        </label>
        {mobilePortfolio && (
          <div className="mobile-portfolio-card">
            <div className="mobile-portfolio-header">
              <input
                className="portfolio-name-input"
                value={mobilePortfolio.name}
                onChange={(event) => updatePortfolioName(mobilePortfolio.id, event.target.value)}
                aria-label="目前投資組合名稱"
              />
              <span className={`weight-total ${Math.abs(portfolioWeightTotal(mobilePortfolio, model) - 100) <= 0.05 ? "valid" : "invalid"}`}>
                {portfolioWeightTotal(mobilePortfolio, model).toFixed(1)}%
              </span>
            </div>
            <div className="mobile-asset-list">
              {model.assets.map((asset, index) => (
                <div className="mobile-asset-row" key={asset.id}>
                  <div className="ticker-cell">
                    <label htmlFor={`mobile-ticker-${asset.id}`}>資產 {index + 1}</label>
                    <input
                      id={`mobile-ticker-${asset.id}`}
                      value={asset.symbol}
                      placeholder="SPY"
                      autoComplete="off"
                      onFocus={() => setActiveSearchId(asset.id)}
                      onBlur={() => window.setTimeout(() => setActiveSearchId(null), 120)}
                      onChange={(event) => {
                        updateAssetSymbol(asset.id, event.target.value.toUpperCase());
                        setActiveSearchId(asset.id);
                      }}
                    />
                    {searchMenu(asset.id)}
                  </div>
                  <label className="weight-input">
                    <span>權重</span>
                    <input
                      type="number"
                      inputMode="decimal"
                      min="0"
                      max="100"
                      step="0.01"
                      value={mobilePortfolio.weights[asset.id] ?? 0}
                      onChange={(event) => updateWeight(mobilePortfolio.id, asset.id, numberValue(event.target.value))}
                    />
                    <span>%</span>
                  </label>
                  <button
                    type="button"
                    className="icon-button danger"
                    aria-label={`刪除資產 ${index + 1}`}
                    disabled={model.assets.length <= 1}
                    onClick={() => setModel((current) => removeAsset(current, asset.id))}
                  >×</button>
                </div>
              ))}
            </div>
            <div className="mobile-tools">
              <button type="button" onClick={() => setModel((current) => equalWeightPortfolio(current, mobilePortfolio.id))}>等權</button>
              <button type="button" onClick={() => setModel((current) => normalizePortfolio(current, mobilePortfolio.id))}>正規化</button>
              <button type="button" onClick={() => setModel((current) => clearPortfolio(current, mobilePortfolio.id))}>清空</button>
              <button type="button" onClick={() => setModel(addAsset)} disabled={model.assets.length >= 20}>新增資產</button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
