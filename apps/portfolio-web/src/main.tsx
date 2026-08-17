import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { applyPortfolioHandoff, installPortfolioHandoffUi } from "./handoff";
import "./styles.css";
import "./refinery.css";
import "./refineryPhase5.css";
import "./refineryPhase6.css";
import "./walkForward.css";
import "./walkForwardResults.css";
import "./researchLibrary.css";
import "./handoff.css";

const root = document.getElementById("root");
if (!root) throw new Error("Portfolio application root was not found.");

const handoff = applyPortfolioHandoff();
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
installPortfolioHandoffUi(handoff);
