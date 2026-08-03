function stylePortfolioLabHeatmap() {
  document.querySelectorAll(".pl-heatmap td[data-heat]").forEach((cell) => {
    const value = Number(cell.dataset.heat);
    if (!Number.isFinite(value)) {
      cell.style.removeProperty("background");
      return;
    }
    const alpha = Math.min(0.62, 0.12 + Math.abs(value) * 3.2);
    cell.style.background = value >= 0
      ? `rgba(15, 118, 110, ${alpha})`
      : `rgba(190, 24, 93, ${alpha})`;
  });
}

function installPortfolioLabResultIntegration() {
  const root = document.querySelector("#portfolio-lab");
  if (!root) return;
  const observer = new MutationObserver(stylePortfolioLabHeatmap);
  observer.observe(root, { childList: true, subtree: true });
  stylePortfolioLabHeatmap();
}

installPortfolioLabResultIntegration();
