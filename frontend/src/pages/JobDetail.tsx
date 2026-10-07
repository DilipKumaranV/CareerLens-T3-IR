import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ErrorNotice, Evidence, InfoBox, IRScore, JobMeta, Loading, Prio, SkillChip, TermsList, Tip } from "../components/ui";
import { api } from "../lib/api";
import { FIT_TIP, pct, pretty } from "../lib/format";
import { useStore } from "../lib/store";

export default function JobDetail() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const q = params.get("q") ?? "";
  const nav = useNavigate();
  const { apiProfile, research } = useStore();
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const profileKey = JSON.stringify(apiProfile);

  useEffect(() => {
    setD(null); setError(null);
    api.job(Number(id), q, apiProfile).then(setD).catch((e) => setError(e.message));
  }, [id, q, profileKey]);

  if (error) return <main className="page"><button className="btn ghost sm" onClick={() => nav(-1)}><ArrowLeft size={15} />Back</button><div style={{ marginTop: 12 }}><ErrorNotice error={error} /></div></main>;
  if (!d) return <main className="page"><Loading rows={2} /></main>;
  const job = d.job, fit = d.career_fit, ev = d.ir_evidence;

  return (
    <main className="page">
      <button className="btn ghost sm" onClick={() => nav(-1)} style={{ marginBottom: 14 }}><ArrowLeft size={15} />Back</button>
      <div className="detail-head">
        <div>
          <h1 style={{ fontSize: "clamp(1.8rem,3.6vw,2.5rem)" }}>{job.title}</h1>
          <p style={{ fontSize: "1.15rem", marginTop: 6 }}><b>{job.company}</b></p>
          <JobMeta job={job} full />
          <p className="small muted">Role family (dataset label): {job.role_family}{job.via ? ` · found via ${job.via}` : ""}{job.salary_rate ? ` · salary period: ${job.salary_rate}` : ""}</p>
        </div>
        {ev && <div className="big-fit"><IRScore value={ev.ir_relevance} large /></div>}
      </div>

      <div className="grid-2" style={{ gridTemplateColumns: "minmax(0,1.35fr) minmax(0,1fr)" }}>
        <div className="stack">
          <section className="panel">
            <div className="panel-title"><h3>Required skills</h3>{apiProfile && <span className="small muted">green = you have it, amber = not in your profile</span>}</div>
            <div className="chips">{fit && (fit.covered.length || fit.missing.length)
              ? [...fit.covered.map((c: any) => ({ ...c, kind: "have" })), ...fit.missing.map((c: any) => ({ ...c, kind: "need" }))].sort((x: any, y: any) => x.i - y.i)
                  .map((c: any) => <SkillChip key={c.key} name={c.skill} kind={c.kind} title={c.matched_by ? `matched by your skill: ${c.matched_by}` : "not in your profile"} />)
              : job.skills.map((s: string) => <SkillChip key={s} name={pretty(s)} kind="plain" />)}</div>
            <p className="tiny muted" style={{ marginTop: 10 }}>This dataset lists the skills each posting mentions. It has no job description, no preferred-skills list, no experience requirement and no job URL, so none of those are shown.</p>
          </section>

          <section className="panel">
            <div className="panel-title"><h3>IR evidence</h3><span className="muted small">{q ? `for the query "${q}"` : "open this job from a search to see it"}</span></div>
            {ev ? (<>
              <p className="small">This job's IR Relevance for your search is <b>{pct(ev.ir_relevance)}</b>. Matching terms:</p>
              <TermsList matched={ev.matched_terms} />
              {ev.reasons.length > 0 && <ul className="small" style={{ margin: "10px 0 0", paddingLeft: 18 }}>{ev.reasons.map((r: string) => <li key={r}>{r}</li>)}</ul>}
              {research && <div style={{ marginTop: 12 }}><Evidence r={ev} /></div>}
            </>) : <p className="small muted">{q ? "This job shares no indexed term with your query." : "No search query, so no IR relevance to show."}</p>}
          </section>

          <section className="panel">
            <div className="panel-title"><h3>Career Fit<Tip text={FIT_TIP} /></h3></div>
            {!d.personalization.available ? (
              <div className="fit-unavailable"><b>{d.personalization.message}</b> <Link to="/resume">Upload resume</Link> · <Link to="/transition">Enter skills</Link></div>
            ) : fit && fit.career_fit !== null ? (<>
              <div className="row-between"><span className="num" style={{ fontFamily: "var(--font-display)", fontSize: "2.4rem", fontWeight: 700 }}>{pct(fit.career_fit)}</span>
                <span className="small muted">Skill match {fit.skills_covered} of {fit.skills_required}{fit.role_similarity !== null && fit.role_similarity !== undefined ? ` · role similarity ${pct(fit.role_similarity)}` : ""}</span></div>
              <div className="small muted" style={{ margin: "6px 0 12px" }}>Career Fit = {Object.entries(fit.components).map(([c, v]: any) => `${pct(v.share)} ${c === "skills" ? "skill match" : "role similarity"} (${pct(v.score)})`).join(" + ")}. {fit.not_available?.[0] ? `Not used: ${fit.not_available[0]}.` : ""}</div>
              <div className="grid-2">
                <div><div className="label">Covered skills</div><div className="chips" style={{ marginTop: 6 }}>{fit.covered.length ? fit.covered.map((c: any) => <SkillChip key={c.key} name={c.skill} kind="have" title={`matched by your skill: ${c.matched_by}`} />) : <span className="small muted">none</span>}</div></div>
                <div><div className="label">Missing skills</div><div className="chips" style={{ marginTop: 6 }}>{fit.missing.length ? fit.missing.map((c: any) => <SkillChip key={c.key} name={c.skill} kind="need" />) : <span className="small muted">none</span>}</div></div>
              </div>
            </>) : <p className="small muted">{fit?.reason}</p>}
          </section>

          {d.preparation.length > 0 && (
            <section className="panel">
              <div className="panel-title"><h3>Preparation recommendations</h3><span className="muted small">ordered by how often similar postings ask for the skill</span></div>
              <ol style={{ margin: 0, paddingLeft: 20, display: "grid", gap: 8 }}>{d.preparation.map((p: any) => <li key={p.key}><b>{p.skill}</b> <Prio p={p.priority} /><div className="small muted">{p.evidence}</div></li>)}</ol>
            </section>
          )}
        </div>

        <div className="stack">
          <section className="panel">
            <div className="panel-title"><h3>Posting details</h3></div>
            <dl className="kv">
              <dt>Job title</dt><dd>{job.title}</dd><dt>Company</dt><dd>{job.company}</dd><dt>Location</dt><dd>{job.location ?? <span className="muted">not listed</span>}</dd>
              <dt>Country</dt><dd>{job.country}</dd><dt>Workplace</dt><dd>{job.workplace}</dd><dt>Employment type</dt><dd>{job.schedule}</dd>
              <dt>Posted</dt><dd>{job.posted || "n/a"}</dd><dt>Postings merged</dt><dd>{job.listings}</dd>
              <dt>Degree</dt><dd>{job.no_degree ? "Posting says no degree needed" : "Not stated"}</dd><dt>Health insurance</dt><dd>{job.health_insurance ? "Mentioned" : "Not mentioned"}</dd>
            </dl>
          </section>
          <section className="panel">
            <div className="panel-title"><h3>Similar jobs</h3><span className="muted small">job-to-job cosine on Title + Skills</span></div>
            {d.similar.length === 0 && <p className="small muted">No similar listings found.</p>}
            {d.similar.map((s: any) => (
              <div key={s.job.id} style={{ padding: "10px 0", borderBottom: "1px solid var(--line)" }}>
                <div className="row-between"><Link to={`/job/${s.job.id}${q ? `?q=${encodeURIComponent(q)}` : ""}`} style={{ fontWeight: 600 }}>{s.job.title}</Link><span className="num small">{pct(s.similarity)}</span></div>
                <div className="small muted">{s.job.company} · {s.job.location ?? s.job.country}</div>
                {s.shared_skills.length > 0 && <div className="chips" style={{ marginTop: 6 }}>{s.shared_skills.slice(0, 5).map((k: string) => <SkillChip key={k} name={pretty(k)} kind="plain" />)}</div>}
              </div>))}
          </section>
        </div>
      </div>
    </main>
  );
}
