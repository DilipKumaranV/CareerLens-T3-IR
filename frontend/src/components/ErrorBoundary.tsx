import { Component, type ErrorInfo, type ReactNode } from "react";

/* Without a boundary, one uncaught render error unmounts the whole React tree and the page goes blank.
   This shows the real error (message, stack, component stack) and offers ways out. It uses plain <a> and
   inline styles so it still works if the router or the store is what crashed. */
interface Props { children: ReactNode; resetKey?: string; }
interface State { error: Error | null; componentStack: string; }

export function clearSavedData() {
  try { Object.keys(localStorage).filter((k) => k.startsWith("careerlens:")).forEach((k) => localStorage.removeItem(k)); } catch { /* storage blocked */ }
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, componentStack: "" };

  static getDerivedStateFromError(error: Error): Partial<State> { return { error }; }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.setState({ componentStack: info.componentStack ?? "" });
    console.error("[CareerLens] React render error:", error, info.componentStack);
  }

  componentDidUpdate(prev: Props) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null, componentStack: "" });  // navigating away recovers
  }

  render() {
    const { error, componentStack } = this.state;
    if (!error) return this.props.children;
    const details = `${error.name}: ${error.message}\n\n${error.stack ?? ""}\n\nComponent stack:${componentStack}\n\nURL: ${location.href}\nBrowser: ${navigator.userAgent}`;
    const box: React.CSSProperties = { maxWidth: 900, margin: "40px auto", padding: "0 24px", fontFamily: "system-ui, sans-serif", color: "var(--ink, #18202e)" };
    const pre: React.CSSProperties = { background: "rgba(127,127,127,.12)", padding: 12, borderRadius: 8, overflow: "auto", fontSize: 12.5, whiteSpace: "pre-wrap", wordBreak: "break-word" };
    const btn: React.CSSProperties = { padding: "8px 14px", borderRadius: 8, border: "1px solid #888", background: "transparent", color: "inherit", cursor: "pointer", font: "inherit", marginRight: 8, textDecoration: "none", display: "inline-block" };
    return (
      <div role="alert" style={box}>
        <h2 style={{ margin: "0 0 8px" }}>This page hit an error while drawing</h2>
        <p style={{ margin: "0 0 14px" }}>The rest of CareerLens is fine. The message below is the real error; the first line usually says what data was missing.</p>
        <pre style={{ ...pre, fontWeight: 600 }}>{error.name}: {error.message}</pre>
        <p style={{ margin: "14px 0" }}>
          <button style={btn} onClick={() => this.setState({ error: null, componentStack: "" })}>Try again</button>
          <button style={btn} onClick={() => { clearSavedData(); location.reload(); }}>Clear saved browser data and reload</button>
          <button style={btn} onClick={() => navigator.clipboard?.writeText(details).catch(() => {})}>Copy details</button>
        </p>
        <details><summary style={{ cursor: "pointer" }}>Stack trace</summary><pre style={pre}>{details}</pre></details>
      </div>
    );
  }
}
