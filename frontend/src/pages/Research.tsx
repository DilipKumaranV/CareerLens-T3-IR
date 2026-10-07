import { Play } from "lucide-react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { ErrorNotice, InfoBox } from "../components/ui";
import { api } from "../lib/api";
import { num, pct, ZONE_LABEL } from "../lib/format";

const SAMPLES = [
  "data engineers are running scalable pipelines with Python SQL AWS in Germany",
  "data analyst in Germany",
  "power bi dax",
  "data scientist at Amazon",
  "cloud architect aws terraform"
];
const SYS: Record<string, string> = { keyword: "Keyword baseline", tfidf: "TF-IDF (flat)", bm25: "BM25 (extra)", careerlens: "Hybrid CareerLens" };

function Stage({ title, note, open, children }: { title: string; note?: string; open?: boolean; children: ReactNode }) {
  return <details className="stage" open={open}><summary><h3>{title}</h3><span className="muted">{note}</span></summary><div className="stage-body">{children}</div></details>;
}

export default function Research() {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? SAMPLES[1]);
  const [cfg, setCfg] = useState<any>(null);
  const [defaults, setDefaults] = useState<any>(null);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.meta().then((m) => { setDefaults(m.default_config); setCfg(m.default_config); }).catch((e) => setError(e.message)); }, []);
  const run = async (q = query, c = cfg) => {
    if (!q.trim() || !c) return;
    setLoading(true); setError(null);
    try { setData(await api.trace({ query: q, k: 8, config: c })); setParams({ q }); } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  };
  useEffect(() => { if (cfg && !data && !loading && !error) run(); }, [cfg]);
  const update = (patch: any) => { const n = { ...cfg, ...patch }; setCfg(n); run(query, n); };
  const submit = (e: FormEvent) => { e.preventDefault(); run(); };

  return (
    <main className="page">
      <div className="page-head"><div><h2>Research Mode</h2><p>Follow one query through every stage of the pipeline. Every number comes from the Python backend for this exact request. Change a weight and the ranking is recomputed. (The Research Mode switch in the top bar also adds this evidence to every search result and job page.)</p></div></div>
      <form onSubmit={submit} className="searchbox" style={{ maxWidth: "none" }}>
        <input value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Query to trace" placeholder="Enter a query to trace" />
        <button className="btn primary" type="submit" disabled={loading}><Play size={16} />{loading ? "Tracing…" : "Trace query"}</button>
      </form>
      <div className="examples">{SAMPLES.map((s) => <button key={s} className="chip" onClick={() => { setQuery(s); run(s); }}>{s}</button>)}</div>
      {error && <div style={{ marginTop: 16 }}><ErrorNotice error={error} /></div>}

      {cfg && (
        <details className="panel" style={{ marginTop: 18 }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>Field weights and ranking settings <span className="muted small" style={{ fontWeight: 400 }}>(hand-set priors or tuned on dev queries; adjustable)</span></summary>
          <div className="grid-2" style={{ marginTop: 14 }}>
            <div className="stack" style={{ gap: 8 }}>
              <div className="label">Zone weights α (Title &gt; Skills &gt; Location/Company; the dataset has no description or department field)</div>
              {Object.keys(cfg.zone_weights).map((z) => (
                <div className="slider-row" key={z}><span>{ZONE_LABEL[z]}</span><input type="range" min={0} max={1} step={0.05} value={cfg.zone_weights[z]} aria-label={`${z} weight`} onChange={(e) => update({ zone_weights: { ...cfg.zone_weights, [z]: Number(e.target.value) } })} /><span className="num">{num(cfg.zone_weights[z], 2)}</span></div>))}
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="label">Hybrid score weights</div>
              {([["w_cosine", "Cosine"], ["w_jaccard", "Jaccard"]] as const).map(([k, l]) => (
                <div className="slider-row" key={k}><span>{l}</span><input type="range" min={0} max={1} step={0.05} value={cfg[k]} aria-label={`${l} weight`} onChange={(e) => update({ [k]: Number(e.target.value) })} /><span className="num">{num(cfg[k], 2)}</span></div>))}
              <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 4 }}>
                <label className="toggle"><input type="checkbox" checked={cfg.use_zones} onChange={(e) => update({ use_zones: e.target.checked })} />Zones</label>
                <label className="toggle"><input type="checkbox" checked={cfg.use_routing} onChange={(e) => update({ use_routing: e.target.checked })} />Zone routing</label>
                <label className="toggle"><input type="checkbox" checked={cfg.diversity} onChange={(e) => update({ diversity: e.target.checked })} />Diversity</label>
                <button className="btn sm" onClick={() => { setCfg(defaults); run(query, defaults); }}>Reset</button>
              </div>
            </div>
          </div>
        </details>
      )}

      {data && (
        <div className="pipeline" style={{ marginTop: 26, opacity: loading ? 0.6 : 1 }}>
          <Stage title="1. Query" note={`"${data.query}"`} open><div className="chips">{data.analysis.tokens.map((t: string, i: number) => <span key={i} className="term">{t}</span>)}</div></Stage>

          <Stage title="2. Preprocessing and normalisation" note="fold, stop words, stem, word pairs, skills named" open>
            <div className="grid-2">
              <div className="stack" style={{ gap: 10 }}>
                <div><div className="label">Removed</div><div className="chips">{data.analysis.removed.length ? data.analysis.removed.map((r: any, i: number) => <span key={i} className="term removed" title={r.reason}>{r.token}</span>) : <span className="muted small">nothing</span>}</div></div>
                <div><div className="label">Kept → Porter stem</div><div className="chips">{data.analysis.stems.map((s: any, i: number) => <span key={i} className="term">{s.token} → {s.stem}</span>)}</div></div>
              </div>
              <div className="stack" style={{ gap: 10 }}>
                <div><div className="label">Word pairs (biwords)</div><div className="chips">{data.analysis.biwords.length ? data.analysis.biwords.map((b: string) => <span key={b} className="term bi">{b}</span>) : <span className="muted small">none</span>}</div></div>
                <div><div className="label">Skills named in the query (information need)</div><div className="chips">{data.analysis.query_skills.length ? data.analysis.query_skills.map((s: string) => <span key={s} className="term exp">{s}</span>) : <span className="muted small">none</span>}</div></div>
                <div><div className="label">Not found in any listing</div><div className="chips">{data.analysis.unknown.length ? data.analysis.unknown.map((u: string) => <span key={u} className="term unknown">{u}</span>) : <span className="muted small">none</span>}</div></div>
              </div>
            </div>
          </Stage>

          <Stage title="3. Zone routing" note="which fields each word is looked up in" open>
            <div className="table-wrap"><table className="data"><thead><tr><th>Word</th>{["Title", "Skills", "Location", "Company", "WorkType"].map((z) => <th key={z} className="n">df in {ZONE_LABEL[z]}</th>)}<th>Looked up in</th></tr></thead>
              <tbody>{data.analysis.routing.map((r: any) => <tr key={r.surface}><td><span className="term">{r.surface}</span></td>{["Title", "Skills", "Location", "Company", "WorkType"].map((z) => <td key={z} className="n">{r.df[z] ?? "–"}</td>)}<td>{r.routed_to.map((z: string) => ZONE_LABEL[z]).join(", ")}</td></tr>)}</tbody></table></div>
            <p className="small muted" style={{ marginTop: 8 }}>A word counts in a field only if its document frequency there is at least {pct(data.config.routing_tau)} of its frequency in its main field. Without this, an incidental word (for example "cloud" inside a company name) activates a field that can only score 0 and lowers every score.</p>
          </Stage>

          <Stage title="4. Inverted indexes and postings" note={`${data.index.N.toLocaleString()} documents; vocabulary: ${Object.entries(data.index.vocabulary).map(([z, n]: any) => `${z} ${n.toLocaleString()}`).join(", ")}`}>
            {Object.entries(data.postings).map(([z, rows]: any) => (
              <div key={z} style={{ marginBottom: 12 }}><div className="label">{ZONE_LABEL[z]} index</div>
                <table className="data"><thead><tr><th>Term</th><th className="n">df</th><th className="n">idf = log10(N/df)</th><th>Postings (document id: tf), first 10</th></tr></thead>
                  <tbody>{rows.map((r: any) => <tr key={r.surface}><td><span className="term">{r.surface}</span></td><td className="n">{r.df.toLocaleString()}</td><td className="n">{num(r.idf, 3)}</td><td className="mono small">{r.postings.map((p: any) => `${p.doc}:${p.tf}`).join(", ")}{r.df > 10 ? ", …" : ""}</td></tr>)}</tbody></table></div>))}
            <InfoBox>Candidate generation: the union of these postings gives <b>{data.candidates.union_of_postings.toLocaleString()}</b> candidates. <b>{data.candidates.never_scored.toLocaleString()}</b> of {data.index.N.toLocaleString()} listings were never scored; {data.candidates.postings_traversed.toLocaleString()} postings were read.</InfoBox>
          </Stage>

          <Stage title="5. TF-IDF query vectors" note="w = (1 + log10 tf) × idf, then length-normalised">
            {Object.entries(data.query_vectors).map(([z, v]: any) => (
              <div key={z} style={{ marginBottom: 12 }}><div className="label">{ZONE_LABEL[z]} zone, α = {num(v.alpha, 2)}, vector length before normalising {num(v.norm, 4)}</div>
                <table className="data"><thead><tr><th>Term</th><th className="n">tf</th><th className="n">1+log10 tf</th><th className="n">df</th><th className="n">idf</th><th className="n">weight</th><th className="n">normalised</th></tr></thead>
                  <tbody>{v.rows.map((r: any) => <tr key={r.term}><td><span className="term">{r.surface}</span></td><td className="n">{r.tf}</td><td className="n">{num(r.log_tf, 3)}</td><td className="n">{r.df.toLocaleString()}</td><td className="n">{num(r.idf, 3)}</td><td className="n">{num(r.weight, 4)}</td><td className="n">{num(r.normalized, 4)}</td></tr>)}</tbody></table></div>))}
          </Stage>

          <Stage title="6. Cosine, Jaccard and the final IR score" note="top results" open>
            <div className="formula">{data.formula}{"\n"}weights: cosine {num(data.config.w_cosine, 2)}, Jaccard {num(data.config.w_jaccard, 2)}; zones {Object.entries(data.config.zone_weights).map(([z, w]: any) => `${z} ${num(w, 2)}`).join(", ")}</div>
            <div className="table-wrap" style={{ marginTop: 12 }}><table className="data">
              <thead><tr><th className="n">#</th><th>Job</th>{data.analysis.active_zones.map((z: string) => <th key={z} className="n">cos {ZONE_LABEL[z]}</th>)}<th className="n">Zone-weighted cosine</th><th className="n">Jaccard</th><th className="n">Final IR score</th><th className="n">Before diversity</th></tr></thead>
              <tbody>{data.ranking.map((r: any) => (
                <tr key={r.job.id}><td className="n">{r.rank}</td><td>{r.job.title}<div className="tiny muted">{r.job.company} · {r.job.location ?? r.job.country}</div></td>
                  {data.analysis.active_zones.map((z: string) => <td key={z} className="n">{num(r.zone_scores[z], 3)}</td>)}<td className="n">{num(r.cosine, 4)}</td><td className="n">{num(r.jaccard, 4)}</td><td className="n best">{num(r.hybrid, 4)}</td><td className="n">{r.pre_diversity_rank ?? "–"}</td></tr>))}</tbody></table></div>
          </Stage>

          <Stage title="7. Per-term evidence: TF, DF, IDF, TF-IDF and contribution" note="the cosine of each result, term by term" open>
            {data.ranking.slice(0, 3).map((r: any) => (
              <div key={r.job.id} style={{ marginBottom: 14 }}><div className="label">#{r.rank} {r.job.title}, {r.job.company}: zone-weighted cosine {num(r.cosine, 4)}, Jaccard {num(r.jaccard, 4)}, final IR score {num(r.hybrid, 4)}</div>
                <div className="table-wrap"><table className="data"><thead><tr><th>Term</th><th>Zone</th><th className="n">TF</th><th className="n">DF</th><th className="n">IDF</th><th className="n">TF-IDF</th><th className="n">w(doc)</th><th className="n">w(query)</th><th className="n">α share</th><th className="n">Contribution</th></tr></thead>
                  <tbody>{r.term_contributions.map((c: any, i: number) => <tr key={i}><td><span className="term">{c.surface}</span></td><td>{ZONE_LABEL[c.zone]}</td><td className="n">{c.doc_tf}</td><td className="n">{c.df.toLocaleString()}</td><td className="n">{num(c.idf, 3)}</td><td className="n">{num(c.doc_tfidf, 3)}</td><td className="n">{num(c.doc_weight, 4)}</td><td className="n">{num(c.query_weight, 4)}</td><td className="n">{num(c.zone_share, 3)}</td><td className="n">{num(c.contribution, 4)}</td></tr>)}</tbody></table></div></div>))}
            <p className="tiny muted">TF = occurrences of the term in the job's field; DF = number of jobs whose field contains it; IDF = log10(N/DF); TF-IDF = (1 + log10 TF) × IDF; w(doc) is TF-IDF divided by the length of the document vector. Final ranking contribution = α × w(query) × w(doc); the contributions sum to the cosine, and the final IR score blends it with Jaccard.</p>
          </Stage>

          <Stage title="8. Same query, different systems" note="top 5 each" open>
            <div className="grid-2" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
              {Object.entries(data.comparison).map(([s, rows]: any) => (
                <div key={s} className="panel" style={{ padding: 12 }}><div className="label" style={{ marginBottom: 6 }}>{SYS[s]}</div>
                  {rows.length ? rows.map((r: any, i: number) => <div key={r.id} className="small" style={{ padding: "3px 0" }}>{i + 1}. <b>{r.title.slice(0, 38)}</b> <span className="muted">· {r.company.slice(0, 18)}</span></div>) : <span className="muted small">no results</span>}</div>))}
            </div>
          </Stage>
        </div>
      )}
    </main>
  );
}
