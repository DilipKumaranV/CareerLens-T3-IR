// Local state in localStorage (no accounts needed). Every value is validated on load so bad saved data can never crash the app.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { ApiProfile } from "./api";

export interface UserSkill { name: string; key: string; status: "dataset" | "custom"; display?: string; source?: string }
export interface ProfileState {
  confirmed: boolean; source: "resume" | "manual" | "demo" | null; current_role: string; department: string; experience_years: number | null;
  skills: UserSkill[]; target_role: string; target_company: string; file?: string;
}
export const EMPTY_PROFILE: ProfileState = { confirmed: false, source: null, current_role: "", department: "", experience_years: null, skills: [], target_role: "", target_company: "" };

/** The profile as the API wants it, or null when there is no CONFIRMED, non-empty profile. Search terms are never added here. */
export function toApiProfile(p: ProfileState): ApiProfile | null {
  if (!p.confirmed || (!p.skills.length && !p.current_role.trim())) return null;
  return { current_role: p.current_role, department: p.department, experience_years: p.experience_years, skills: p.skills.map((s) => s.name), target_role: p.target_role, target_company: p.target_company };
}

interface Store {
  profile: ProfileState; setProfile: (p: ProfileState) => void; clearProfile: () => void; apiProfile: ApiProfile | null;
  history: { query: string; at: number }[]; pushHistory: (q: string) => void;
  theme: "light" | "dark"; toggleTheme: () => void; research: boolean; setResearch: (v: boolean) => void;
}
const Ctx = createContext<Store | null>(null);

const V = {
  profile: (v: any) => !!v && typeof v === "object" && typeof v.confirmed === "boolean" && Array.isArray(v.skills) && v.skills.every((s: any) => s && typeof s.name === "string" && typeof s.key === "string"),
  history: (v: any) => Array.isArray(v) && v.every((h) => h && typeof h.query === "string"),
  theme: (v: any) => v === "light" || v === "dark",
  research: (v: any) => typeof v === "boolean",
};

function usePersisted<T>(key: keyof typeof V, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(`careerlens:${key}`);
      if (raw === null) return initial;
      const parsed = JSON.parse(raw);
      if (V[key](parsed)) return parsed as T;
      localStorage.removeItem(`careerlens:${key}`);
    } catch { try { localStorage.removeItem(`careerlens:${key}`); } catch { /* storage blocked */ } }
    return initial;
  });
  useEffect(() => { try { localStorage.setItem(`careerlens:${key}`, JSON.stringify(value)); } catch { /* storage full or blocked */ } }, [key, value]);
  return [value, setValue] as const;
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const prefersDark = typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  const [profile, setProfile] = usePersisted<ProfileState>("profile", EMPTY_PROFILE);
  const [history, setHistory] = usePersisted<{ query: string; at: number }[]>("history", []);
  const [theme, setTheme] = usePersisted<"light" | "dark">("theme", prefersDark ? "dark" : "light");
  const [research, setResearch] = usePersisted<boolean>("research", false);
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  const store = useMemo<Store>(() => ({
    profile, setProfile, clearProfile: () => setProfile(EMPTY_PROFILE), apiProfile: toApiProfile(profile),
    history, pushHistory: (q) => setHistory((h) => [{ query: q, at: Date.now() }, ...h.filter((x) => x.query !== q)].slice(0, 12)),
    theme, toggleTheme: () => setTheme((t) => (t === "light" ? "dark" : "light")), research, setResearch,
  }), [profile, history, theme, research]);
  return <Ctx.Provider value={store}>{children}</Ctx.Provider>;
}
export function useStore() { const s = useContext(Ctx); if (!s) throw new Error("useStore outside StoreProvider"); return s; }
