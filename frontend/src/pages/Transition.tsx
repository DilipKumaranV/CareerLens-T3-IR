import { ArrowRight } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ErrorNotice, FitSummary, InfoBox, Loading, Prio, Ring, SkillChip, Tip } from "../components/ui";
import { api } from "../lib/api";
import { pct } from "../lib/format";
import { EMPTY_PROFILE, useStore, type UserSkill } from "../lib/store";

export default function Transition() {
  const { profile, setProfile, research } = useStore();
  const [params] = useSearchParams();
  const [role, setRole] = useState(profile.current_role);
  const [dept, setDept] = useState(profile.department);
  const [years, setYears] = useState<string>(profile.experience_years === null ? "" : String(profile.experience_years));
  const [skills, setSkills] = useState<UserSkill[]>(profile.skills);
  const [draft, setDraft] = useState("");
  const [target, setTarget] = useState(params.get("target") ?? profile.target_role);
  const [company, setCompany] = useState(profile.target_company);
  const [companies, setCompanies] = useState<string[]>([]);
  const [res, setRes] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { // pick up a profile that was confirmed on the Resume page
    setRole(profile.current_role); setDept(profile.department); setSkills(profile.skills);
    setYears(profile.experience_years === null ? "" : String(profile.experience_years));
    if (!params.get("target")) setTarget(profile.target_role); setCompany(profile.target_company);
  }, [profile.confirmed, profile.file, profile.source]);
  useEffect(() => {
    const t = setTimeout(() => { if (company.length >= 2) api.companies(company).then((r) => setCompanies(r.companies.map((c) => c.company))).catch(() => setCompanies([])); else setCompanies([]); }, 200);
    return () => clearTimeout(t);
  }, [company]);

  const addSkills = (text: string) => {
    const have = new Set(skills.map((s) => s.name.toLowerCase()));
    const add: UserSkill[] = text.split(/[,;\n]+/).map((s) => s.trim()).filter((n) => n && !have.has(n.toLowerCase())).map((n) => ({ name: n, key: n.toLowerCase(), status: "custom", source: "typed" }));
    setSkills([...skills, ...add]); setDraft("");
  };
  const submit = async (e?: FormEvent) => {
    e?.preventDefault();
    const all = draft.trim() ? [...skills, { name: draft.trim(), key: draft.trim().toLowerCase(), status: "custom" as const }] : skills;
    if (draft.trim()) { setSkills(all); setDraft(""); }
    setLoading(true); setError(null);
    try {
      const out = await api.transition({ profile: { current_role: role, department: dept, experience_years: years === "" ? null : Number(years), skills: all.map((s) => s.name) }, target_role: target, target_company: company || null });
      setRes(out);
      setProfile({ confirmed: true, source: profile.source ?? "manual", current_role: role, department: dept, experience_years: years === "" ? null : Number(years), skills: out.profile.skills, target_role: target, target_company: company, file: profile.file });
    } catch (err: any) { setError(err.message); setRes(null); } finally { setLoading(false); }
  };
  useEffect(() => { if (params.get("target") && profile.confirmed && profile.skills.length && !res) submit(); }, []);   // arriving from the Resume page

  const thr = res?.requirements.thresholds;
  return (
    <main className="page">
      <div className="page-head"><div><h2>Career Transition</h2><p>See the gap between your current profile and a target role, measured against the real postings for that role in the dataset.</p></div>
        {profile.confirmed && <button className="btn" onClick={() => { setProfile(EMPTY_PROFILE); setRole(""); setDept(""); setYears(""); setSkills([]); setTarget(""); setCompany(""); setRes(null); }}>Clear profile</button>}</div>

      <form className="panel" onSubmit={submit}>
        <div className="grid-2">
          <div className="stack" style={{ gap: 12 }}>
            <h3>Current profile</h3>
            <div className="field"><label htmlFor="t-dept">Current department</label><input id="t-dept" className="input" value={dept} onChange={(e) => setDept(e.target.value)} placeholder="e.g. IT Infrastructure" /></div>
            <div className="field"><label htmlFor="t-role">Current role</label><input id="t-role" className="input" value={role} onChange={(e) => setRole(e.target.value)} placeholder="e.g. System Administrator" /></div>
            <div className="field"><label htmlFor="t-exp">Years of experience</label><input id="t-exp" className="input" type="number" min={0} max={60} step={0.5} value={years} onChange={(e) => setYears(e.target.value)} /></div>
            <div className="field"><label htmlFor="t-skill">Skills (press Enter after each)</label>
              <div className="skill-input">
                {skills.map((s) => <SkillChip key={s.key} name={s.display || s.name} kind={s.status === "custom" ? "custom" : "plain"} onRemove={() => setSkills(skills.filter((x) => x.key !== s.key))} />)}
                <input id="t-skill" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="AWS, Linux, Networking, Python"
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addSkills(draft); } }} />
              </div></div>
            <Link className="small" to="/resume">…or upload a resume instead</Link>
          </div>
          <div className="stack" style={{ gap: 12 }}>
            <h3>Target</h3>
            <div className="field"><label htmlFor="t-target">Target role</label><input id="t-target" className="input" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="e.g. Cloud Architect" required /></div>
            <div className="field"><label htmlFor="t-company">Target company (optional)</label><input id="t-company" className="input" list="t-companies" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="e.g. Microsoft" />
              <datalist id="t-companies">{companies.map((c) => <option key={c} value={c} />)}</datalist></div>
            <InfoBox>Your skills come only from what you enter here or from a resume you confirmed. The target role is what you want to become; it is never treated as a skill you have.</InfoBox>
            <button className="btn primary" type="submit" disabled={loading} style={{ justifySelf: "start", padding: "10px 20px" }}>{loading ? "Analyzing…" : "Analyze My Transition"}</button>
          </div>
        </div>
      </form>

      {error && <div style={{ marginTop: 14 }}><ErrorNotice error={error} /></div>}
      {loading && !res && <div style={{ marginTop: 14 }}><Loading rows={2} /></div>}

      {res && (
        <div className="stack" style={{ marginTop: 18 }} aria-live="polite">
          <section className="panel">
            <div className="panel-title"><h2>Your career transition</h2></div>
            <div className="row-between" style={{ alignItems: "center", gap: 28 }}>
              <div className="pathway">
                <div className="node"><b>{res.profile.current_role || "Your current profile"}</b><span className="small muted">{res.profile.department || "department not given"}{res.profile.experience_years != null ? ` · ${res.profile.experience_years} years` : ""}</span></div>
                <ArrowRight className="arrow" />
                <div className="node target"><b>{res.target.role}</b><span className="small muted">{res.target.company ? `at ${res.target.company}` : "any company"}</span></div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <Ring value={res.career_fit} label="Career Fit" />
                <div className="small muted" style={{ maxWidth: 270 }}>Career Fit for the target role <Tip text="The share of what the best-matching postings for the target role ask for that you already have. Skills asked for more often, and by more relevant postings, count more. It uses only the profile you supplied." />
                  <br />{res.have.length} of {res.have.length + res.to_develop.length} skills the role asks for. Based on {res.requirements.jobs_used} postings ({res.target.requirement_scope}).</div>
              </div>
            </div>
            {res.requirements.example_titles?.length > 0 && <p className="small muted" style={{ marginTop: 10 }}>Postings read include: {res.requirements.example_titles.join("; ")}.</p>}
            {res.notes.map((n: string) => <div key={n} className="notice warn" style={{ marginTop: 10 }}>{n}</div>)}
            {res.company_status && res.company_status.status === "found" && res.company_status.role_present !== false && <div className="notice info" style={{ marginTop: 10 }}>{res.company_status.company} has {res.company_status.listings} listings in the dataset, and some of them match "{res.target.role}". Requirements below come from that company.</div>}
            {res.company_status?.status === "not_in_dataset" && res.company_status.suggestions.length > 0 && <p className="small" style={{ marginTop: 8 }}>Did you mean: {res.company_status.suggestions.map((c: string) => <button key={c} type="button" className="chip" style={{ marginLeft: 4 }} onClick={() => setCompany(c)}>{c}</button>)}</p>}
          </section>

          <div className="grid-2">
            <section className="panel">
              <div className="panel-title"><h3>Skills you already have</h3><span className="muted small">{res.have.length}</span></div>
              {res.have.length === 0 ? <p className="small muted">None of the skills this role asks for are in your profile yet.</p> :
                <div className="chips">{res.have.map((s: any) => <SkillChip key={s.key} name={s.skill} kind="have" title={`asked for in ${pct(s.prevalence)} of relevant postings; matched by your skill "${s.matched_by}"`} />)}</div>}
              {res.other_skills.length > 0 && <><div className="label" style={{ marginTop: 14 }}>Other skills in your profile (kept, not required by this role)</div>
                <div className="chips" style={{ marginTop: 6 }}>{res.other_skills.map((s: any) => <SkillChip key={s.key} name={s.display || s.name} kind={s.status === "custom" ? "custom" : "plain"} />)}</div></>}
            </section>
            <section className="panel">
              <div className="panel-title"><h3>Skills to develop</h3><span className="muted small">{res.to_develop.length}</span></div>
              {res.to_develop.length === 0 ? <p className="small">You already have every skill this role commonly asks for.</p> :
                <div className="chips">{res.to_develop.map((s: any) => <SkillChip key={s.key} name={`${s.skill} · ${pct(s.prevalence)}`} kind="need" title={`${s.priority} priority`} />)}</div>}
            </section>
          </div>

          <section className="panel">
            <div className="panel-title"><h3>Preparation priority</h3><span className="muted small">most-requested missing skill first</span></div>
            {res.preparation_plan.length === 0 ? <p className="small muted">Nothing to prepare for the skills measured.</p> :
              <ol style={{ margin: 0, paddingLeft: 22, display: "grid", gap: 10 }}>{res.preparation_plan.map((p: any) => <li key={p.key}><b>{p.skill}</b> <Prio p={p.priority} /><div className="small muted">{p.evidence}</div></li>)}</ol>}
            <p className="tiny muted" style={{ marginTop: 10 }}>HIGH = asked for in at least {pct(thr.high)} of the relevant postings, MEDIUM at least {pct(thr.medium)}, otherwise LOW. Skills below {pct(thr.min_prevalence)} are not treated as requirements.</p>
          </section>

          <section className="panel">
            <div className="panel-title"><h3>Recommended jobs</h3><span className="muted small">relevant to "{res.target.role}", ordered by Career Fit for your profile</span></div>
            {res.recommended_jobs.length === 0 ? <p className="small muted">No matching postings.</p> : (
              <div className="table-wrap"><table className="data">
                <thead><tr><th>Company</th><th>Job title</th><th>Location</th><th>Workplace</th><th className="n">IR Relevance<Tip text="How relevant the job is to the target role you searched for." /></th><th className="n">Career Fit<Tip text="How well the job matches your profile." /></th><th className="n">Skill match</th><th>Missing skills</th></tr></thead>
                <tbody>{res.recommended_jobs.map((r: any) => (
                  <tr key={r.job.id}><td>{r.job.company}</td><td><Link to={`/job/${r.job.id}?q=${encodeURIComponent(res.target.role)}`}>{r.job.title}</Link></td><td>{r.job.location ?? r.job.country}</td><td>{r.job.workplace}</td>
                    <td className="n">{pct(r.ir_relevance)}</td><td className="n best">{pct(r.career_fit)}</td><td className="n">{r.fit?.skills_covered}/{r.fit?.skills_required}</td>
                    <td><div className="chips">{r.fit?.missing.slice(0, 4).map((m: any) => <SkillChip key={m.key} name={m.skill} kind="need" />)}{r.fit?.missing.length > 4 && <span className="small muted">+{r.fit.missing.length - 4}</span>}</div></td></tr>))}</tbody></table></div>)}
            {res.closest_at_company.length > 0 && <div style={{ marginTop: 14 }}><div className="label">Closest postings at {res.company_status.company} (none is titled like the target role)</div>
              <ul className="small" style={{ margin: "6px 0 0", paddingLeft: 18 }}>{res.closest_at_company.map((c: any) => <li key={c.job.id}><Link to={`/job/${c.job.id}`}>{c.job.title}</Link> · {c.job.location ?? c.job.country} · IR relevance {pct(c.ir_relevance)}</li>)}</ul></div>}
          </section>

          {res.companies.length > 0 && (
            <section className="panel"><div className="panel-title"><h3>Companies with relevant jobs in the dataset</h3></div>
              <div className="table-wrap"><table className="data"><thead><tr><th>Company</th><th className="n">Relevant listings</th><th className="n">Best Career Fit</th></tr></thead>
                <tbody>{res.companies.map((c: any) => <tr key={c.company}><td>{c.company}</td><td className="n">{c.jobs}</td><td className="n">{pct(c.best_fit)}</td></tr>)}</tbody></table></div></section>
          )}

          <section className="panel">
            <div className="panel-title"><h3>How this was computed</h3></div>
            <p className="small">1) The target role is searched like any query, and the top-ranked postings (at least {pct(thr.relevance_ratio)} of the best IR score, at most {thr.top_jobs}) are read. 2) A skill's weight is the share of those postings that list it, weighted by each posting's IR relevance. 3) Career Fit for the target role is the weight of the skills you have divided by the weight of all required skills. 4) Career Fit per job = {Object.entries(res.fit_weights).map(([k, v]: any) => `${pct(v)} ${k === "skills" ? "idf-weighted skill match" : "role-title similarity"}`).join(" + ")}. Experience is not used because the dataset has no experience requirement.</p>
            {research && res.requirements.skills.length > 0 && (
              <div className="table-wrap" style={{ marginTop: 10 }}><table className="data"><thead><tr><th>Required skill</th><th className="n">IR-weighted prevalence</th><th className="n">Postings</th><th>Priority</th><th>You</th></tr></thead>
                <tbody>{res.requirements.skills.map((s: any) => { const have = res.have.some((h: any) => h.key === s.key); return <tr key={s.key}><td>{s.skill}</td><td className="n">{pct(s.prevalence, 1)}</td><td className="n">{s.jobs}</td><td><Prio p={s.priority} /></td><td>{have ? "✓ have" : "○ missing"}</td></tr>; })}</tbody></table></div>)}
          </section>
        </div>
      )}
    </main>
  );
}
