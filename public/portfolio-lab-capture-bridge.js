(() => {
  const CAPTURE_PATH = "/api/backtest";
  const CAPTURE_PARAMETER = "portfolio_lab_capture";
  const pendingPayloads = new Map();
  const baseFetch = window.fetch.bind(window);

  function requestUrl(input) {
    try {
      const value = typeof input === "string" || input instanceof URL ? input : input?.url;
      return new URL(value, window.location.href);
    } catch {
      return null;
    }
  }

  function legacyCapturePayload(payload) {
    const results = Array.isArray(payload?.results) ? payload.results : [];
    return {
      data: results.map((result, index) => {
        const metrics = result?.metrics || {};
        const series = Array.isArray(result?.series) ? result.series : [];
        return {
          name: String(result?.display_name || result?.name || `投資組合 ${index + 1}`),
          total_return: metrics.total_return,
          cagr: metrics.cagr,
          volatility: metrics.volatility,
          mdd: metrics.max_drawdown,
          sharpe_ratio: metrics.sharpe_ratio,
          sortino_ratio: metrics.sortino_ratio,
          beta: metrics.beta,
          alpha: metrics.alpha,
          portfolioHistory: series.map((point) => ({
            date: point.date,
            value: point.value,
          })),
        };
      }),
    };
  }

  window.fetch = async function portfolioLabCaptureAwareFetch(input, init) {
    const url = requestUrl(input);
    const token = url?.pathname === CAPTURE_PATH
      ? url.searchParams.get(CAPTURE_PARAMETER)
      : null;
    if (token && pendingPayloads.has(token)) {
      const payload = pendingPayloads.get(token);
      pendingPayloads.delete(token);
      return Response.json(payload, {
        status: 200,
        headers: {
          "cache-control": "no-store",
          "x-portfolio-lab-capture": "synthetic",
        },
      });
    }
    return baseFetch(input, init);
  };

  window.addEventListener("portfolio-lab:result", (event) => {
    if (!event.detail?.results?.length) return;
    const token = crypto.randomUUID();
    pendingPayloads.set(token, legacyCapturePayload(event.detail));
    window.fetch(`${CAPTURE_PATH}?${CAPTURE_PARAMETER}=${encodeURIComponent(token)}`, {
      method: "GET",
      cache: "no-store",
    }).catch(() => {
      pendingPayloads.delete(token);
    });
  });
})();
