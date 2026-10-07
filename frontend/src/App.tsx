import { Moon, Sun } from "lucide-react";
import { useEffect } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import { Tip } from "./components/ui";
import { useStore } from "./lib/store";
import Evaluation from "./pages/Evaluation";
import Home from "./pages/Home";
import JobDetail from "./pages/JobDetail";
import Research from "./pages/Research";
import Resume from "./pages/Resume";
import Search from "./pages/Search";
import Transition from "./pages/Transition";

export function LensMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="14" cy="14" r="9" fill="none" stroke="currentColor" strokeWidth="3" />
      <path d="M21 21l7 7" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <path d="M9.5 14h9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity=".45" />
    </svg>
  );
}

export default function App() {
  const { theme, toggleTheme, research, setResearch, profile, apiProfile } = useStore();
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand"><LensMark /><span>CareerLens</span></Link>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end>Home</NavLink>
            <NavLink to="/search">Find Jobs</NavLink>
            <NavLink to="/transition">Career Transition</NavLink>
            <NavLink to="/resume">Resume Analysis{apiProfile && <span className="badge-count" title={`Confirmed profile: ${profile.current_role || "no role"}`}>✓</span>}</NavLink>
            <NavLink to="/evaluation">Evaluation</NavLink>
            <NavLink to="/research">Research Mode</NavLink>
          </nav>
          <div className="topbar-actions">
            <label className="toggle">
              <input type="checkbox" checked={research} onChange={(e) => setResearch(e.target.checked)} aria-label="Research Mode" />
              Research Mode<Tip text="Research Mode shows the Information Retrieval calculations behind the recommendations." />
            </label>
            <button className="icon-btn" onClick={toggleTheme} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}>{theme === "light" ? <Moon size={17} /> : <Sun size={17} />}</button>
          </div>
        </div>
      </header>
      <ErrorBoundary resetKey={pathname}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<Search />} />
          <Route path="/job/:id" element={<JobDetail />} />
          <Route path="/transition" element={<Transition />} />
          <Route path="/resume" element={<Resume />} />
          <Route path="/evaluation" element={<Evaluation />} />
          <Route path="/research" element={<Research />} />
          <Route path="*" element={<main className="page"><div className="empty"><h3>Page not found</h3><p><Link to="/">Go to the home page</Link></p></div></main>} />
        </Routes>
      </ErrorBoundary>
    </>
  );
}
