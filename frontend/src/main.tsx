import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { StoreProvider } from "./lib/store";
import "./styles.css";

// Errors outside React (module load, event loop) never reach an error boundary. If one of them leaves the page
// empty, print it on the page so a blank screen always has a visible reason.
function showFatal(reason: unknown) {
  setTimeout(() => {
    const root = document.getElementById("root");
    if (root && root.childElementCount > 0) return;
    const msg = reason instanceof Error ? `${reason.name}: ${reason.message}\n${reason.stack ?? ""}` : String(reason);
    document.body.insertAdjacentHTML("beforeend", `<pre style="margin:24px;padding:16px;white-space:pre-wrap;font:13px monospace;background:#fee;color:#600;border-radius:8px">CareerLens failed to start.\n\n${msg.replace(/</g, "&lt;")}</pre>`);
  }, 50);
}
window.addEventListener("error", (e) => showFatal(e.error ?? e.message));
window.addEventListener("unhandledrejection", (e) => showFatal(e.reason));

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <StoreProvider>
          <App />
        </StoreProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
);
