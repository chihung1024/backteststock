import { useEffect, useMemo, useRef, useState } from "react";
import { searchAssets } from "./api";
import {
  addAsset,
  addPortfolio,
  clearPortfolio,
  copyPortfolio,
  equalWeightPortfolio,
  normalizePortfolio,
  normalizeSymbol,
  portfolioExposureSummary,
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
  const searchRequestVersion = useRef(0);
  const activeAsset = model.assets.find((asset) => asset.id === activeSearchId);

  useEffect(() => {
    if (model.portfolios.some((portfolio) => portfolio.id === mobilePortfolioId)) return;
    setMobilePortfolioId(model.portfolios[0]?.id ?? "");
  }, [mobilePortfolioId, model.portfolios]);

  useEffect(() => {
    const version = ++searchRequestVersion.current;
    const query = activeAsset?.symbol.trim() ?? "";
    if (!activeSearchId || query.length < 1) {
      setSuggestions([]);
      setSearchBusy(false);
      return;
    }
    setSuggestions([]);
    setSearchBusy(false);
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      if (searchRequestVersion.current !== version) return;
      setSearchBusy(true);
      searchAssets(query, controller.signal)
        .then((items) => {
          if (searchRequestVersion.current === version) setSuggestions(items);
        })
        .catch((error: unknown) => {
          if (searchRequestVersion.current !== version) return;
          if (!(error instanceof DOMException && error.name === "AbortError")) setSuggestions([]);
        })
        .finally(() => {
          if (searchRequestVersion.current === version) setSearchBusy(false);
        });
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
      if (searchRequestVersion.current === version) searchRequestVersion.current += 1;
    };
  }, [activeAsset?.symbol, activeSearchId]);

  const mobilePortfolio = useMemo(
    () => model.portfolios.find((portfolio) => portfolio.id === mobilePortfolioId) ?? model.portfolios[0],
    [mobilePortfolioId, model.portfolios],
  );
  const mobileExposure = mobilePortfolio
    ? portfolioExposureSummary(portfolioWeightTotal(mobilePortfolio, model))
    : portfolioExposureSummary(0);

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

  function deferCloseSearch(assetId: string) {
    window.setTimeout(() => {
      setActiveSearchId((current) => (current === assetId ? null : current));
    }, 120);
  }

  function updateWeight(portfolioId: string, assetId: string, value: number) {
    setModel((current) => ({
      ...current,
      portfolios: current.portfolios.map((portfolio) =>
        portfolio.id === portfolioId
          ? { ...portfolio, weights: { ...portfolio.weights, [assetId]: Math.max(0, value) } }
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
            <h2 id="allocation-title">資產配置與總曝險</h2>
            <p>每組權重總和就是該投組的目標總曝險：低於 100% 的差額保留現金，高於 100% 的部分由融資支應。每組最多 20 項資產。</p>
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
                const exposure = portfolioExposureSummary(total);
                return (
                  <th scope="col" key={portfolio.id}>
                    <input
                      className="portfolio-name-input"
                      value={portfolio.name}
                      onChange={(event) => updatePortfolioName(portfolio.id, event.target.value)}
                      aria-label="投資組合名稱"
                    />
                    <div className={`weight-total ${exposure.kind === "inactive" ? "invalid" : "valid"}`}>{exposure.label}</div>
                    <small>{exposure.detail}</small>
                    <div className="mini-actions" aria-label={`${portfolio.name} 操作`}>
                      <button type="button" onClick={() => setModel((current) => equalWeightPortfolio(current, portfolio.id))}>100% 等權</button>
                      <button type="button" onClick={() => setModel((current) => normalizePortfolio(current, portfolio.id))}>縮放至 100%</button>
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
                      onBlur={() => deferCloseSearch(asset.id)}
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
                      <span className="sr-only">{portfolio.name} 的 {asset.symbol || `第 ${rowIndex + 1} 列`} 曝險</span>
                      <input
                        inputMode="decimal"
                        type="number"
                        min="0"
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
              <span className={`weight-total ${mobileExposure.kind === "inactive" ? "invalid" : "valid"}`}>
                {mobileExposure.label}
              </span>
            </div>
            <small>{mobileExposure.detail}</small>
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
                      onBlur={() => deferCloseSearch(asset.id)}
                      onChange={(event) => {
                        updateAssetSymbol(asset.id, event.target.value.toUpperCase());
                        setActiveSearchId(asset.id);
                      }}
                    />
                    {searchMenu(asset.id)}
                  </div>
                  <label className="weight-input">
                    <span>曝險</span>
                    <input
                      type="number"
                      inputMode="decimal"
                      min="0"
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
              <button type="button" onClick={() => setModel((current) => equalWeightPortfolio(current, mobilePortfolio.id))}>100% 等權</button>
              <button type="button" onClick={() => setModel((current) => normalizePortfolio(current, mobilePortfolio.id))}>縮放至 100%</button>
              <button type="button" onClick={() => setModel((current) => clearPortfolio(current, mobilePortfolio.id))}>清空</button>
              <button type="button" onClick={() => setModel(addAsset)} disabled={model.assets.length >= 20}>新增資產</button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
