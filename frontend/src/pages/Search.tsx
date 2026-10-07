import { Search as SearchIcon, UserCheck, UserX } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ErrorNotice, InfoBox, Loading, ResultCard, SkillChip, Tip } from "../components/ui";
import { api } from "../lib/api";
import { num, ZONE_LABEL } from "../lib/format";
import { useStore } from "../lib/store";
import type { Meta, SearchResponse } from "../lib/types";

const FILTERS = ["company", "country", "workplace", "schedule", "role_family"] as const;
const SORTS: [string, string][] = [["best", "Best match"], ["newest", "Newest"], ["company", "Company A to Z"], ["location", "Location A to Z"]];

export default function Search() {
  const [params, setParams] = useSearchParams();
  const { apiProfile, profile, research, pushHistory, history } = useStore();
  const q = params.get("q") ?? "";
  const filters: Record<string, string[]> = {};
  FILTERS.forEach((f) => { const v = params.get(f); if (v) filters[f] = [v]; });
  const sort = params.get("sort") ?? "best";
  const k = Number(params.get("k") ?? 10);

  const [draft, setDraft] = useState(q);
  const [companyDraft, setCompanyDraft] = useState(params.get("company") ?? "");
  const [suggest, setSuggest] = useState<string[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const reqId = useRef(0);

  useEffect(() => { api.meta().then(setMeta).catch((e) => setError(e.message)); }, []);
  useEffect(() => { setDraft(q); }, [q]);
  useEffect(() => { setCompanyDraft(params.get("company") ?? ""); }, [params.get("company")]);
  useEffect(() => {
    const t = setTimeout(() => { if (companyDraft.length >= 2) api.companies(companyDraft).then((r) => setSuggest(r.companies.map((c) => c.company))).catch(() => setSuggest([])); else setSuggest([]); }, 200);
    return () => clearTimeout(t);
  }, [companyDraft]);

  const profileKey = JSON.stringify(apiProfile);
  const hasFilters = Object.keys(filters).length > 0;
  const run = useCallback(async () => {
    if (!q.trim() && !hasFilters) { setData(null); setError(null); return; }
    const id = ++reqId.current;
    setLoading(true); setError(null);
    try {
      const res = await api.search({ query: q, k, filters, sort, debug: research, profile: apiProfile });
      if (id === reqId.current) { setData(res); if (q.trim()) pushHistory(q.trim()); }
    } catch (e: any) { if (id === reqId.current) { setError(e.message); setData(null); } }
    finally { if (id === reqId.current) setLoading(false); }
  }, [q, JSON.stringify(filters), sort, k, research, profileKey]);
  useEffect(() => { const t = setTimeout(run, 150); return () => clearTimeout(t); }, [run]);

  const setParam = (key: string, value: string) => { const p = new URLSearchParams(params); if (value) p.set(key, value); else p.delete(key); setParams(p); };
  const submit = (e: FormEvent) => { e.preventDefault(); const p = new URLSearchParams(params); if (draft.trim()) p.set("q", draft.trim()); else p.delete("q"); if (companyDraft.trim()) p.set("company", companyDraft.trim()); else p.delete("company"); setParams(p); };
  const opts = meta?.filter_options;
  const sel = (name: string, label: string, list: [string, number][] | undefined) => (
    <div className="field"><label htmlFor={`f-${name}`}>{label}</label>
      <select id={`f-${name}`} className="input" value={params.get(name) ?? ""} onChange={(e) => setParam(name, e.target.value)}>
        <option value="">Any</option>{(list ?? []).map(([v, n]) => <option key={v} value={v}>{v} ({n.toLocaleString()})</option>)}</select></div>
  );
  const personalized = !!data?.personalization.available;

  return (
    <main className="page">
      <div className="page-head"><div><h2>Find Jobs</h2><p>Search by job title, skills, company or place. Results are ranked with classical Information Retrieval.</p></div></div>
      <form className="panel" onSubmit={submit} role="search">
        <div className="searchbox" style={{ maxWidth: "none", boxShadow: "none" }}>
          <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="e.g. Cloud Architect, data engineer spark airflow, data analyst in Germany" aria-label="Search jobs" />
          <button className="btn primary" type="submit"><SearchIcon size={17} />Search</button>
        </div>
        <div className="form-grid" style={{ marginTop: 14 }}>
          <div className="field"><label htmlFor="f-company">Company</label>
            <input id="f-company" className="input" list="company-list" value={companyDraft} onChange={(e) => setCompanyDraft(e.target.value)} onBlur={() => setParam("company", companyDraft.trim())} placeholder="Any company" />
            <datalist id="company-list">{suggest.map((c) => <option key={c} value={c} />)}</datalist></div>
          {sel("country", "Country", opts?.country)}{sel("workplace", "Workplace", opts?.workplace)}{sel("schedule", "Employment type", opts?.schedule)}{sel("role_family", "Role family (dataset label)", opts?.role_family)}
        </div>
      </form>

      <div className="row-between" style={{ margin: "16px 0 8px" }}>
        {apiProfile ? (
          <span className="tag" style={{ background: "color-mix(in srgb, var(--ok) 12%, var(--surface))" }}><UserCheck size={14} />Personalized with your confirmed profile ({profile.current_role || "no role"}, {profile.skills.length} skills)</span>
        ) : (
          <span className="tag"><UserX size={14} /><span>Personalized Career Fit unavailable. <Link to="/resume">Upload your resume</Link> or <Link to="/transition">enter your skills</Link>.</span></span>
        )}
        <div style={{ display: "flex", gap: 8 }}>
          <select className="input" style={{ width: "auto" }} value={sort} onChange={(e) => setParam("sort", e.target.value)} aria-label="Sort results">{SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          <select className="input" style={{ width: "auto" }} value={k} onChange={(e) => setParam("k", e.target.value)} aria-label="Number of results">{[5, 10, 20, 30].map((n) => <option key={n} value={n}>Top {n}</option>)}</select>
        </div>
      </div>
      <details style={{ marginBottom: 12 }}><summary className="small" style={{ cursor: "pointer" }}>What is the difference between IR Relevance and Career Fit?</summary>
        <div style={{ marginTop: 8 }}><InfoBox><b>IR Relevance</b> answers "how relevant is this job to my search?" using only your query and the job. <b>Career Fit</b> answers "how well does this job match <i>me</i>?" using the profile you uploaded or typed. Your search words are never treated as skills you have.</InfoBox></div></details>

      {error && <ErrorNotice error={error} />}
      {!data && !loading && !error && (
        <div className="empty"><h3>Search for a role, skill or company</h3><p>Try "Cloud Architect", "data engineer spark airflow" or "data analyst in Germany".</p>
          {history.length > 0 && <div className="chips" style={{ justifyContent: "center", marginTop: 16 }}>{history.slice(0, 6).map((h) => <Link key={h.query} className="chip" to={`/search?q=${encodeURIComponent(h.query)}`}>{h.query}</Link>)}</div>}</div>
      )}
      {loading && !data && <Loading />}
      {data && (
        <section aria-live="polite">
          {data.notices.filter((n) => n.kind !== "no_results").map((n, i) => <div key={i} className="notice warn" style={{ marginBottom: 8 }}>{n.text}{n.suggestions && Object.entries(n.suggestions).filter(([, s]) => s.length).map(([u, s]) => <span key={u}> Did you mean {s.map((x) => <button key={x} type="button" className="chip" style={{ marginLeft: 4 }} onClick={() => setParam("q", q.replace(new RegExp(u, "i"), x))}>{x}</button>)}?</span>)}</div>)}
          <QueryPanel data={data} open={research} />
          <p className="small muted" style={{ margin: "10px 0" }}>
            {data.results.length} shown, ranked from {data.stats.candidates.toLocaleString()} candidate listings{data.stats.filtered_to !== null && <> (filters allow {data.stats.filtered_to.toLocaleString()})</>}.
            {" "}{data.stats.documents_never_scored.toLocaleString()} of {data.stats.N.toLocaleString()} were never scored because they share no term with the query. {data.stats.time_ms} ms.
          </p>
          {data.results.length === 0 && <div className="empty"><h3>No listings matched</h3><p>Try fewer filters or different words.</p></div>}
          <div style={{ opacity: loading ? 0.55 : 1, transition: "opacity .15s" }}>
            {data.results.map((r) => <ResultCard key={r.job.id} r={r} query={q} research={research} personalized={personalized} />)}
          </div>
        </section>
      )}
    </main>
  );
}

function QueryPanel({ data, open }: { data: SearchResponse; open: boolean }) {
  const a = data.analysis;
  if (!a.raw) return null;
  return (
    <details className="panel" open={open} style={{ padding: 14 }}>
      <summary style={{ cursor: "pointer", fontWeight: 600 }}>Query analysis <Tip text="How CareerLens read your query before searching the indexes." /></summary>
      <div className="grid-2" style={{ marginTop: 12 }}>
        <div className="stack" style={{ gap: 8 }}>
          <div><span className="label">Original</span><div className="mono small">{a.raw}</div></div>
          <div><span className="label">Tokens → normalised terms</span><div className="chips">{a.removed.map((r, i) => <span key={`r${i}`} className="term removed" title={r.reason}>{r.token}</span>)}{a.stems.map((s, i) => <span key={i} className="term">{s.token} → {s.stem}</span>)}</div></div>
          {a.biwords.length > 0 && <div><span className="label">Word pairs</span><div className="chips">{a.biwords.map((b) => <span key={b} className="term bi">{b}</span>)}</div></div>}
          {a.query_skills.length > 0 && <div><span className="label">Skills named in the query (an information need, not your skills)</span><div className="chips">{a.query_skills.map((s) => <SkillChip key={s} name={s} kind="plain" />)}</div></div>}
          <div><span className="label">Fields searched</span><div>{a.active_zones.map((z) => ZONE_LABEL[z]).join(", ") || "none"}</div></div>
        </div>
        <div className="table-wrap"><table className="data"><thead><tr><th>Word</th><th>Looked up in</th><th className="n">df</th></tr></thead>
          <tbody>{a.routing.map((r) => <tr key={r.surface}><td><span className="term">{r.surface}</span></td><td>{r.routed_to.map((z) => ZONE_LABEL[z]).join(", ")}</td><td className="n">{Object.entries(r.df).map(([z, v]) => `${ZONE_LABEL[z][0]}:${v}`).join("  ")}</td></tr>)}</tbody></table>
          <p className="tiny muted" style={{ marginTop: 6 }}>Zone routing: a word is looked up only in fields where its document frequency is at least half of its frequency in its main field (T = Title, S = Skills, L = Location, C = Company).</p></div>
      </div>
    </details>
  );
}
