import { BarChart3, FileText, Layers, Route as RouteIcon, Search as SearchIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { Meta } from "../lib/types";

const CARDS = [
  { icon: SearchIcon, title: "Job Discovery", text: "Search titles, skills, companies and places. Every result shows why it matched.", to: "/search" },
  { icon: FileText, title: "Resume Analysis", text: "Upload a PDF resume, review the detected profile, edit it and confirm it.", to: "/resume" },
  { icon: Layers, title: "Skill Gap Analysis", text: "Compare your skills with what the best-matching postings actually ask for.", to: "/transition" },
  { icon: RouteIcon, title: "Career Transition", text: "Plan a move from your current role to a target role, optionally at one company.", to: "/transition" },
  { icon: BarChart3, title: "Explainable IR", text: "Switch on Research Mode to see postings, TF-IDF weights, cosine and Jaccard.", to: "/research" },
];

export default function Home() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.meta().then(setMeta).catch((e) => setError(e.message)); }, []);
  const d = meta?.dataset;
  return (
    <main className="page">
      <section className="hero">
        <h1>Find your next role. Understand your skill gaps. Prepare with confidence.</h1>
        <p className="lede">An explainable Information Retrieval platform for job discovery and career transition planning.</p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Link className="btn primary" style={{ padding: "11px 20px" }} to="/search">Find Jobs</Link>
          <Link className="btn primary" style={{ padding: "11px 20px" }} to="/transition">Plan My Career Transition</Link>
          <Link className="btn" style={{ padding: "11px 20px" }} to="/resume">Upload Resume</Link>
        </div>
        {error && <div className="notice error" role="alert" style={{ marginTop: 24, maxWidth: 760 }}>{error}</div>}
        {meta && d && (
          <div className="facts">
            <span><strong className="num">{meta.listings.toLocaleString()}</strong>job listings</span>
            <span><strong className="num">{d.companies?.toLocaleString()}</strong>companies</span>
            <span><strong className="num">{d.distinct_skills}</strong>distinct skills</span>
            <span><strong className="num">{d.countries}</strong>countries</span>
          </div>
        )}
      </section>
      <section style={{ marginTop: 28 }}>
        <div className="cards">
          {CARDS.map(({ icon: Icon, title, text, to }) => (
            <Link key={title} to={to} className="card-link"><Icon size={22} color="var(--accent)" /><h3 style={{ marginTop: 10 }}>{title}</h3><p className="small muted">{text}</p></Link>
          ))}
        </div>
      </section>
      <section className="howto">
        <div>
          <h2>How a result gets its score</h2>
          <ol className="steps">
            <li><span><b>Read the query.</b> Tokenize, fold case and accents, drop stop words, stem, and recognise any skills you name.</span></li>
            <li><span><b>Look it up in the indexes.</b> Title, Skills, Location and Company each have an inverted index; a word is only looked up in the fields it is really about.</span></li>
            <li><span><b>Score.</b> TF-IDF cosine per field, weighted, plus Jaccard overlap, gives the <b>IR Relevance</b> of a job to your query.</span></li>
            <li><span><b>Personalise only if you ask.</b> <b>Career Fit</b> compares a job with the skills you confirmed. Without a profile it is never shown.</span></li>
          </ol>
        </div>
        <div className="panel">
          <div className="panel-title"><h3>Two different questions</h3></div>
          <div className="stack" style={{ gap: 12 }}>
            <div><b>IR Relevance</b><p className="small muted">How relevant is this job to what you searched for? Depends only on your query and the job.</p></div>
            <div><b>Career Fit</b><p className="small muted">How well does this job match you? Depends on the profile you uploaded or typed, never on your search words.</p></div>
          </div>
          {d && <p className="tiny muted" style={{ marginTop: 14 }}>Data: {d.source} ({d.license}). A working sample of {meta?.listings.toLocaleString()} listings from {d.unique_listings?.toLocaleString()} unique listings in 2023.</p>}
        </div>
      </section>
    </main>
  );
}
