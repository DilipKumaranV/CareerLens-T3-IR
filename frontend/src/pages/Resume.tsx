import { CheckCircle2, FileUp, UserRoundX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ErrorNotice, InfoBox, SkillChip } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { EMPTY_PROFILE, useStore, type UserSkill } from "../lib/store";

interface Form { current_role: string; department: string; experience_years: string; skills: UserSkill[]; target_role: string }
const EMPTY: Form = { current_role: "", department: "", experience_years: "", skills: [], target_role: "" };
type Step = { step: string; ok: boolean; detail: string };

export default function Resume() {
  const { profile, setProfile, clearProfile, apiProfile } = useStore();
  const nav = useNavigate();
  const [demos, setDemos] = useState<{ key: string; title: string; blurb: string; available: boolean }[]>([]);
  const [demoLabel, setDemoLabel] = useState("");
  const [steps, setSteps] = useState<Step[]>([]);
  const [fileName, setFileName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [meta, setMeta] = useState<{ department_source: string | null; experience_source: string | null; warnings: string[]; demo: string | null }>({ department_source: null, experience_source: null, warnings: [], demo: null });
  const [skillDraft, setSkillDraft] = useState("");
  const [over, setOver] = useState(false);
  const [saved, setSaved] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { api.demos().then((r) => { setDemos(r.demos); setDemoLabel(r.label); }).catch(() => {}); }, []);

  const load = (res: any, target = "") => {
    setSteps(res.steps); setFileName(res.file.name); setSaved(false);
    const p = res.profile;
    setForm({ current_role: p.current_role ?? "", department: p.department ?? "", experience_years: p.experience_years ?? "", skills: p.skills, target_role: target });
    setMeta({ department_source: p.department_source, experience_source: p.experience_source, warnings: res.warnings, demo: res.demo });
  };
  const run = async (fn: () => Promise<any>, name: string, target = "") => {
    setBusy(true); setError(null); setForm(null); setFileName(name);
    setSteps([{ step: "Upload", ok: true, detail: name }, { step: "Text extraction", ok: false, detail: "working…" }]);
    try { load(await fn(), target); }
    catch (e: any) { const ae = e as ApiError; setError({ message: ae.message, code: ae.code }); setSteps([{ step: "Upload", ok: true, detail: name }, { step: "Text extraction", ok: false, detail: ae.message }]); }
    finally { setBusy(false); }
  };
  const onFile = (f?: File | null) => { if (f) run(() => api.analyzeResume(f), f.name); };
  const manual = () => { setError(null); setSteps([]); setFileName(null); setSaved(false); setMeta({ department_source: null, experience_source: null, warnings: [], demo: null }); setForm({ ...EMPTY }); };

  const addSkills = (text: string) => {
    if (!form) return;
    const items = text.split(/[,;\n]+/).map((s) => s.trim()).filter(Boolean);
    const have = new Set(form.skills.map((s) => s.name.toLowerCase()));
    const added: UserSkill[] = items.filter((n) => !have.has(n.toLowerCase())).map((n) => ({ name: n, key: n.toLowerCase(), status: "custom", source: "typed" }));
    setForm({ ...form, skills: [...form.skills, ...added] }); setSkillDraft("");
  };
  const confirm = async () => {
    if (!form) return;
    setBusy(true); setError(null);
    try {
      const years = form.experience_years === "" ? null : Number(form.experience_years);
      const res = await api.normalizeProfile({ current_role: form.current_role, department: form.department, experience_years: years, skills: form.skills.map((s) => s.name) });
      if (!res.usable) { setError({ message: res.message }); return; }
      const p = res.profile;
      setProfile({ confirmed: true, source: meta.demo ? "demo" : fileName ? "resume" : "manual", current_role: p.current_role ?? "", department: p.department ?? "", experience_years: p.experience_years,
        skills: p.skills, target_role: form.target_role, target_company: "", file: fileName ?? undefined });
      setSaved(true);
    } catch (e: any) { setError({ message: e.message }); } finally { setBusy(false); }
  };
  const known = form?.skills.filter((s) => s.status === "dataset").length ?? 0;

  return (
    <main className="page">
      <div className="page-head"><div><h2>Resume Analysis</h2><p>Upload a PDF resume. CareerLens extracts a draft profile, you review and edit it, and only a profile you confirm is used for personalized matching.</p></div>
        {apiProfile && <button className="btn" onClick={() => { clearProfile(); setSaved(false); }}><UserRoundX size={15} />Clear confirmed profile</button>}</div>

      {apiProfile && !saved && <div className="notice info" style={{ marginBottom: 14 }}>Confirmed profile in use: <b>{profile.current_role || "no role"}</b>, {profile.skills.length} skills ({profile.source}). <Link to="/transition">Analyze a career transition</Link> · <Link to="/search">Find jobs</Link></div>}

      <section className="panel">
        <div className={`dropzone${over ? " over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files?.[0]); }} data-testid="dropzone">
          <FileUp size={30} color="var(--accent)" />
          <h3>Drag & drop your resume (PDF)</h3>
          <p className="small muted" style={{ marginBottom: 12 }}>or</p>
          <input ref={input} type="file" accept="application/pdf,.pdf" hidden onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} aria-label="Choose resume PDF" />
          <button className="btn primary" disabled={busy} onClick={() => input.current?.click()}>Choose Resume</button>
          <p className="tiny muted" style={{ marginTop: 12 }}>Your file is read on the server only to extract text and is not stored. Name and contact details are not extracted.</p>
        </div>
        {(fileName || steps.length > 0) && (
          <div className="status-steps" aria-live="polite">
            {fileName && <div className="small"><b>File:</b> {fileName}</div>}
            {steps.map((s, i) => <div key={i} className={`status-step ${s.ok ? "" : s.detail === "working…" ? "wait" : "bad"}`}><span className="dot" /><span><b>{s.step}:</b> {s.detail}</span></div>)}
          </div>
        )}
        {error && <div style={{ marginTop: 12 }}><ErrorNotice error={error.message} />{!form && <button className="btn" style={{ marginTop: 10 }} onClick={manual}>Enter my profile manually</button>}</div>}
      </section>

      <section className="panel">
        <div className="panel-title"><h3>Demo Profiles</h3><span className="muted small">{demoLabel || "Fictional candidates for testing, not real people."}</span></div>
        <div className="cards">
          {demos.map((d) => (
            <div key={d.key} className="card-link" style={{ cursor: "default" }}>
              <h3>{d.title}</h3><p className="small muted" style={{ marginBottom: 12 }}>{d.blurb}</p>
              <button className="btn sm" disabled={busy || !d.available} onClick={() => run(() => api.analyzeDemo(d.key), `${d.key}-demo-resume.pdf`, "Cloud Architect")}>Load this demo profile</button>
            </div>))}
        </div>
        <p className="tiny muted" style={{ marginTop: 10 }}>A demo resume goes through exactly the same extraction pipeline as an uploaded file. Nothing is pre-filled.</p>
      </section>

      {!form && !error && <p className="small muted">No resume? <button className="btn ghost sm" onClick={manual}>Enter my profile manually</button> or use the <Link to="/transition">Career Transition</Link> form.</p>}

      {form && (
        <section className="panel" aria-label="Extracted profile">
          <div className="panel-title"><h3>{fileName ? "Extracted profile" : "Your profile"}</h3><span className="muted small">Review and edit. Nothing is used until you confirm.</span></div>
          {meta.warnings.map((w) => <div key={w} className="notice warn" style={{ marginBottom: 8 }}>{w}</div>)}
          <div className="form-grid">
            <div className="field"><label htmlFor="role">Current role</label><input id="role" className="input" value={form.current_role} onChange={(e) => setForm({ ...form, current_role: e.target.value })} placeholder="e.g. System Administrator" /></div>
            <div className="field"><label htmlFor="dept">Department</label><input id="dept" className="input" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} placeholder="e.g. IT Infrastructure" />
              {meta.department_source && <span className="tiny muted">{meta.department_source}</span>}</div>
            <div className="field"><label htmlFor="exp">Experience (years)</label><input id="exp" className="input" type="number" min={0} max={60} step={0.5} value={form.experience_years} onChange={(e) => setForm({ ...form, experience_years: e.target.value })} />
              {meta.experience_source && <span className="tiny muted">{meta.experience_source}</span>}</div>
            <div className="field"><label htmlFor="tgt">Target role (optional)</label><input id="tgt" className="input" value={form.target_role} onChange={(e) => setForm({ ...form, target_role: e.target.value })} placeholder="e.g. Cloud Architect" /></div>
          </div>
          <div className="field" style={{ marginTop: 14 }}>
            <label htmlFor="skill-in">Detected skills ({form.skills.length}; {known} known to the job data, {form.skills.length - known} custom)</label>
            <div className="skill-input">
              {form.skills.map((s) => <SkillChip key={s.key} name={s.display || s.name} kind={s.status === "custom" ? "custom" : "plain"} title={s.status === "custom" ? "Not in the job data's skill list. Kept and used in matching." : "Known skill in the job data"} onRemove={() => setForm({ ...form, skills: form.skills.filter((x) => x.key !== s.key) })} />)}
              <input id="skill-in" value={skillDraft} onChange={(e) => setSkillDraft(e.target.value)} placeholder="Add a skill, press Enter"
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addSkills(skillDraft); } }} onBlur={() => skillDraft && addSkills(skillDraft)} />
            </div>
            <span className="tiny muted">Dashed chips are skills the job data does not list; they are never discarded.</span>
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
            <button className="btn primary" onClick={confirm} disabled={busy}><CheckCircle2 size={16} />Confirm Profile</button>
          </div>
          {saved && (
            <div className="notice info" style={{ marginTop: 14, flexDirection: "column", gap: 10 }} role="status">
              <span><b>Profile confirmed.</b> It will now be used for Career Fit, skill-match and transition analysis.</span>
              <span style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <button className="btn primary" onClick={() => nav(`/search?q=${encodeURIComponent(form.target_role || form.current_role || "")}`)}>Find Matching Jobs</button>
                <button className="btn primary" onClick={() => nav(`/transition${form.target_role ? `?target=${encodeURIComponent(form.target_role)}` : ""}`)}>Analyze Career Transition</button>
              </span>
            </div>
          )}
        </section>
      )}
      <div style={{ marginTop: 14 }}><InfoBox>Skills come only from your resume or what you type here. A job search never adds skills to your profile.</InfoBox></div>
    </main>
  );
}
