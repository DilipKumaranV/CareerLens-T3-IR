import { RefreshCw } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorNotice, InfoBox, Loading } from "../components/ui";
import { api } from "../lib/api";
import { usePalette } from "../lib/colors";
import { num, pct } from "../lib/format";

const SYS = ["keyword", "tfidf", "tfidf_jaccard", "careerlens", "bm25"] as const;
const SHORT: Record<string, string> = { keyword: "Keyword baseline", tfidf: "TF-IDF", tfidf_jaccard: "TF-IDF + Jaccard", careerlens: "Hybrid CareerLens", bm25: "BM25 (extra)" };

export default function Evaluation() {
  const [ev, setEv] = useState<any>(null);
  const [split, setSplit] = useState<"test" | "all">("test");
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [meta, setMeta] = useState<any>(null);
  const p = usePalette();
  const col: Record<string, string> = { keyword: p["--c-quality"], tfidf: p["--c-pref"], tfidf_jaccard: p["--c-penalty"], careerlens: p["--c-ir"], bm25: p["--c-jaccard"] };
  const tip = { contentStyle: { background: p["--surface"], border: `1px solid ${p["--line"]}`, borderRadius: 8, color: p["--ink"] } };

  useEffect(() => { api.evaluation().then(setEv).catch((e) => setError(e.message)); api.meta().then(setMeta).catch(() => {}); }, []);
  const rerun = async () => { setRunning(true); setError(null); try { setEv(await api.runEvaluation()); } catch (e: any) { setError(e.message); } finally { setRunning(false); } };
  if (error && !ev) return <main className="page"><ErrorNotice error={error} /></main>;
  if (!ev) return <main className="page"><p className="muted" style={{ marginBottom: 12 }}>Loading evaluation results…</p><Loading /></main>;

  const m = (s: string) => ev.systems[s].by_split[split];
  const metrics = ["P@5", "R@5", "AP@5", "P@10", "nDCG@10"];
  const best = Object.fromEntries(metrics.map((k) => [k, Math.max(...SYS.map((s) => m(s)[k]))]));
  const bars = ["P@5", "AP@5", "nDCG@10"].map((k) => ({ metric: k, ...Object.fromEntries(SYS.map((s) => [s, m(s)[k]])) }));
  const recall = [{ metric: "Recall@5", ...Object.fromEntries(SYS.map((s) => [s, m(s)["R@5"]])) }];
  const types = Object.entries(ev.by_type).map(([t, v]: any) => ({ type: `${t} (${v.queries})`, ...Object.fromEntries(SYS.map((s) => [s, v[s]["P@5"]])) }));
  const sig = (vs: string, metric: string) => ev.significance.find((x: any) => x.vs === vs && x.metric === metric && x.split === split);
  const cl = m("careerlens"), kw = m("keyword"), tf = m("tfidf"), bm = m("bm25");
  const n = ev.splits[split];
  const verdict = (a: number, b: number) => (Math.abs(a - b) < 0.005 ? "about the same as" : a > b ? "higher than" : "lower than");

  return (
    <main className="page">
      <div className="page-head">
        <div><h2>IR Evaluation</h2><p>How well does the Information Retrieval system retrieve relevant jobs? This evaluates <b>retrieval quality</b>, not anyone's career. {ev.setup.queries} judged queries over {ev.setup.listings.toLocaleString()} listings. Generated {new Date(ev.generated_at).toLocaleString()}.</p></div>
        <button className="btn" onClick={rerun} disabled={running}><RefreshCw size={15} className={running ? "spin" : ""} />{running ? "Running (about 2 min)…" : "Re-run evaluation"}</button>
      </div>
      {error && <ErrorNotice error={error} />}

      <div className="grid-3">
        <InfoBox><b>Precision@K.</b> Of the top K retrieved listings, how many were relevant? (relevant in the top K ÷ K)</InfoBox>
        <InfoBox><b>Recall@K.</b> Of all relevant listings, how many did the system retrieve in the top K? (relevant in the top K ÷ all relevant). With thousands of relevant listings it is small by construction.</InfoBox>
        <InfoBox><b>Average Precision@K.</b> Rewards putting relevant listings early: the mean of Precision at each rank where a relevant listing appears.</InfoBox>
      </div>

      <section className="panel">
        <div className="row-between"><h3>Results</h3>
          <div className="segmented" role="group" aria-label="Query set"><button className={split === "test" ? "on" : ""} onClick={() => setSplit("test")}>Held-out test ({ev.splits.test} queries)</button><button className={split === "all" ? "on" : ""} onClick={() => setSplit("all")}>All queries ({ev.splits.all})</button></div></div>
        {split === "all" && <div className="notice warn" style={{ margin: "12px 0" }}>The tuned weights (Company, Location, Jaccard) were chosen on the dev half of these queries, so "all queries" numbers are optimistic for CareerLens. The held-out test half is the fair comparison.</div>}
        <div className="table-wrap" style={{ marginTop: 12 }}><table className="data">
          <thead><tr><th>System</th>{metrics.map((k) => <th key={k} className="n">{k}</th>)}</tr></thead>
          <tbody>{SYS.map((s) => <tr key={s}><td>{SHORT[s]}</td>{metrics.map((k) => <td key={k} className={`n ${Math.abs(m(s)[k] - best[k]) < 1e-9 ? "best" : ""}`}>{num(m(s)[k], 3)}</td>)}</tr>)}</tbody></table></div>
        <p className="small" style={{ marginTop: 12 }}><b>Reading the result ({split === "test" ? "held-out test" : "all"} queries, n = {n}).</b> CareerLens's Precision@5 ({num(cl["P@5"])}) is {verdict(cl["P@5"], kw["P@5"])} the keyword baseline ({num(kw["P@5"])}) and {verdict(cl["P@5"], bm["P@5"])} BM25 ({num(bm["P@5"])}); it is {verdict(cl["P@5"], tf["P@5"])} flat TF-IDF ({num(tf["P@5"])}). Average Precision@5: {num(cl["AP@5"])} vs {num(kw["AP@5"])} (keyword), {num(tf["AP@5"])} (TF-IDF).
          {sig("keyword", "P@5") && <> Paired randomization test against the keyword baseline on P@5: p = {num(sig("keyword", "P@5").p_value, 2)}; against TF-IDF on nDCG@10: p = {num(sig("tfidf", "nDCG@10").p_value, 2)}. A small number of queries means small differences are not statistically significant.</>}</p>
      </section>

      <div className="grid-2">
        <section className="panel"><div className="panel-title"><h3>Precision and ranking quality</h3></div>
          <div className="chart-box"><ResponsiveContainer><BarChart data={bars}><CartesianGrid vertical={false} /><XAxis dataKey="metric" tickLine={false} /><YAxis domain={[0, 1]} tickLine={false} axisLine={false} /><Tooltip {...tip} formatter={(v: any) => num(v, 3)} /><Legend />
            {SYS.map((s) => <Bar key={s} dataKey={s} name={SHORT[s]} fill={col[s]} radius={[3, 3, 0, 0]} />)}</BarChart></ResponsiveContainer></div></section>
        <section className="panel"><div className="panel-title"><h3>Recall@5</h3><span className="muted small">all relevant listings in the denominator</span></div>
          <div className="chart-box"><ResponsiveContainer><BarChart data={recall}><CartesianGrid vertical={false} /><XAxis dataKey="metric" tickLine={false} /><YAxis tickLine={false} axisLine={false} tickFormatter={(v) => v.toFixed(3)} /><Tooltip {...tip} formatter={(v: any) => num(v, 4)} /><Legend />
            {SYS.map((s) => <Bar key={s} dataKey={s} name={SHORT[s]} fill={col[s]} radius={[3, 3, 0, 0]} />)}</BarChart></ResponsiveContainer></div>
          <p className="tiny muted">Recall@5 cannot exceed 5 ÷ (number of relevant listings), which is below 0.001 for the largest role queries. Compare systems with each other, not with 1.0. The per-query table shows each query's ceiling.</p></section>
        <section className="panel"><div className="panel-title"><h3>Precision@5 by query type</h3><span className="muted small">all {ev.splits.all} queries</span></div>
          <div className="chart-box"><ResponsiveContainer><BarChart data={types}><CartesianGrid vertical={false} /><XAxis dataKey="type" tickLine={false} interval={0} tick={{ fontSize: 11 }} /><YAxis domain={[0, 1]} tickLine={false} axisLine={false} /><Tooltip {...tip} formatter={(v: any) => num(v, 2)} /><Legend />
            {SYS.map((s) => <Bar key={s} dataKey={s} name={SHORT[s]} fill={col[s]} radius={[3, 3, 0, 0]} />)}</BarChart></ResponsiveContainer></div></section>
        <section className="panel"><div className="panel-title"><h3>What each CareerLens component adds</h3><span className="muted small">change in AP@5 on the test split when removed</span></div>
          <div className="chart-box"><ResponsiveContainer><BarChart data={ev.ablations.map((a: any) => ({ name: a.label, d: a.delta_test["AP@5"] }))} layout="vertical" margin={{ left: 30 }}><CartesianGrid horizontal={false} /><XAxis type="number" tickLine={false} /><YAxis type="category" dataKey="name" width={170} tickLine={false} axisLine={false} interval={0} /><Tooltip {...tip} formatter={(v: any) => num(v, 3)} /><ReferenceLine x={0} stroke={p["--muted"]} />
            <Bar dataKey="d" name="Δ AP@5">{ev.ablations.map((a: any) => <Cell key={a.key} fill={a.delta_test["AP@5"] < 0 ? p["--c-ir"] : p["--c-penalty"]} />)}</Bar></BarChart></ResponsiveContainer></div>
          <p className="small muted">Negative = removing it hurts, so the component helps. The diversity step only reorders ties and changes no score.</p></section>
      </div>

      <section className="panel">
        <div className="panel-title"><h3>Query by query</h3><span className="muted small">click a row to see the top-5 each system retrieved</span></div>
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Query</th><th>Set</th><th className="n">Relevant docs</th><th className="n">Recall@5 ceiling</th><th className="n">P@5 keyword</th><th className="n">P@5 TF-IDF</th><th className="n">P@5 hybrid</th><th className="n">R@5 keyword</th><th className="n">R@5 TF-IDF</th><th className="n">R@5 hybrid</th></tr></thead>
          <tbody>{ev.queries.filter((q: any) => split === "all" || q.split === "test").map((q: any) => (
            <Fragment key={q.id}>
              <tr onClick={() => setOpen(open === q.id ? null : q.id)} style={{ cursor: "pointer" }} aria-expanded={open === q.id}>
                <td>{q.query}<div className="tiny muted">{q.type}</div></td><td>{q.split}</td><td className="n">{q.relevant.toLocaleString()}</td><td className="n">{num(q.recall_ceiling_5, 4)}</td>
                <td className="n">{num(q.keyword["P@5"], 2)}</td><td className="n">{num(q.tfidf["P@5"], 2)}</td><td className={`n ${q.careerlens["P@5"] >= Math.max(q.keyword["P@5"], q.tfidf["P@5"]) ? "best" : ""}`}>{num(q.careerlens["P@5"], 2)}</td>
                <td className="n">{num(q.keyword["R@5"], 4)}</td><td className="n">{num(q.tfidf["R@5"], 4)}</td><td className="n">{num(q.careerlens["R@5"], 4)}</td></tr>
              {open === q.id && <tr><td colSpan={10} style={{ background: "var(--surface-2)" }}>
                <div className="grid-3">{(["keyword", "tfidf", "careerlens"] as const).map((s) => (
                  <div key={s}><div className="label">{SHORT[s]}: retrieved top 5</div>
                    <ol className="small" style={{ margin: "6px 0 0", paddingLeft: 18 }}>{q[s].top5.map((d: any) => <li key={d.id} style={{ color: d.relevant ? "var(--ok)" : "var(--bad)" }}>{d.relevant ? "✓" : "✗"} {d.title.slice(0, 44)} <span className="muted">· {d.company.slice(0, 20)} · {d.role_family}</span></li>)}</ol></div>))}</div></td></tr>}
            </Fragment>))}</tbody></table></div>
      </section>

      <section className="panel">
        <div className="panel-title"><h3>Methodology</h3></div>
        <div className="small stack" style={{ gap: 8 }}>
          <p><b>Relevance judgments.</b> {ev.setup.relevance}</p>
          <p><b>Fair comparison.</b> Listings often have identical scores, so every system breaks ties randomly and results are averaged over {ev.setup.seeds} fixed seeds; no system benefits from file order. Systems: keyword overlap (shared stems), flat TF-IDF cosine over all fields, flat TF-IDF + Jaccard, BM25 (outside the syllabus, shown for reference) and Hybrid CareerLens (zone-weighted TF-IDF cosine with zone routing, plus Jaccard).</p>
          <p><b>What this page is not.</b> Evaluation measures <b>retrieval quality</b>: did the system put relevant listings near the top for a query? It says nothing about whether you are eligible for, or a good fit for, any job. That is Career Fit, which needs your profile.</p>
          <p><b>Tuning and honesty.</b> Title and Skills weights are priors. The Company and Location weights and the Jaccard weight were tuned on the dev half of the queries and are reported on the held-out test half. The best Company weight was the largest value tried. Relevance comes from metadata, not from people reading each posting.</p>
        </div>
        {meta?.dataset && <p className="tiny muted" style={{ marginTop: 10 }}>Dataset: {meta.dataset.source} ({meta.dataset.license}), {meta.dataset.source_url}. {meta.dataset.raw_rows?.toLocaleString()} raw rows → {meta.dataset.unique_listings?.toLocaleString()} unique listings → {meta.listings.toLocaleString()} in the working sample.</p>}
      </section>
    </main>
  );
}
