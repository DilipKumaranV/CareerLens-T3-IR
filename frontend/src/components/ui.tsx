import { AlertTriangle, Building2, Calendar, Clock, MapPin, Wallet, Info, X } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { FIT_TIP, IR_TIP, money, num, pct, pretty, ZONE_LABEL } from "../lib/format";
import type { Fit, Job, Result } from "../lib/types";

export function Tip({ text }: { text: string }) {
  return <span className="tip" tabIndex={0} role="img" aria-label={text} data-tip={text}>i</span>;
}

export function SkillChip({ name, kind, onRemove, title }: { name: string; kind?: "have" | "need" | "custom" | "plain"; onRemove?: () => void; title?: string }) {
  return (
    <span className={`skill ${kind === "plain" ? "" : kind ?? ""}`} title={title}>
      {kind === "have" && "✓ "}{kind === "need" && "○ "}{name}
      {onRemove && <button type="button" onClick={onRemove} aria-label={`Remove ${name}`}><X size={13} /></button>}
    </span>
  );
}

export const Prio = ({ p }: { p: string }) => <span className={`prio ${p}`}>{p}</span>;

export function ErrorNotice({ error }: { error: string }) {
  return <div className="notice error" role="alert"><AlertTriangle size={17} /><span>{error}</span></div>;
}
export function Loading({ rows = 3, height = 110 }: { rows?: number; height?: number }) {
  return <div className="stack" aria-busy="true" aria-label="Loading">{Array.from({ length: rows }).map((_, i) => <div key={i} className="skeleton" style={{ height }} />)}</div>;
}

export function JobMeta({ job, full = false }: { job: Job; full?: boolean }) {
  const sal = money(job);
  return (
    <div className="tags">
      {job.location ? <span className="tag"><MapPin size={13} />{job.location}</span> : <span className="tag missing">Location not listed</span>}
      <span className="tag"><Building2 size={13} />{job.workplace}</span>
      <span className="tag"><Clock size={13} />{job.schedule}</span>
      {job.posted && <span className="tag"><Calendar size={13} />{job.posted}</span>}
      {sal && <span className="tag"><Wallet size={13} />{sal}</span>}
      {full && job.listings > 1 && <span className="tag" title="Re-postings of the same title, company and location are merged into one listing.">{job.listings} postings merged</span>}
    </div>
  );
}

export function Ring({ value, label }: { value: number | null; label: string }) {
  const r = 62, c = 2 * Math.PI * r, v = Math.max(0, Math.min(1, value ?? 0));
  return (
    <div className="ring" role="img" aria-label={`${label}: ${value === null ? "unavailable" : pct(value)}`}>
      <svg width="150" height="150" viewBox="0 0 150 150"><circle cx="75" cy="75" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="13" />
        <circle cx="75" cy="75" r={r} fill="none" stroke="var(--accent)" strokeWidth="13" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - v)} /></svg>
      <div className="val"><span>{value === null ? "n/a" : pct(value)}</span><small>{label}</small></div>
    </div>
  );
}

export function IRScore({ value, large = false }: { value: number | null; large?: boolean }) {
  return (
    <div>
      <div className="pct num" style={large ? { fontSize: "2.6rem" } : undefined}>{value === null ? "n/a" : pct(value)}</div>
      <div className="lbl">IR Relevance<Tip text={IR_TIP} /></div>
    </div>
  );
}

export function FitSummary({ fit, limit = 4 }: { fit: Fit | null | undefined; limit?: number }) {
  if (!fit || fit.career_fit === null || fit.career_fit === undefined) return null;
  return (
    <div className="fit-col">
      <div className="score-line"><span className="num" style={{ fontFamily: "var(--font-display)", fontSize: "1.5rem", fontWeight: 700 }}>{pct(fit.career_fit)}</span><span className="lbl small muted">Career Fit<Tip text={FIT_TIP} /></span></div>
      {fit.skills_required ? <div className="small muted">Skill match: {fit.skills_covered} of {fit.skills_required} skills</div> : null}
      {fit.missing.length > 0 && (
        <div className="chips" style={{ justifyContent: "inherit" }}>
          {fit.missing.slice(0, limit).map((m) => <SkillChip key={m.key} name={m.skill} kind="need" />)}
          {fit.missing.length > limit && <span className="small muted">+{fit.missing.length - limit} missing</span>}
        </div>
      )}
    </div>
  );
}

export function TermsList({ matched }: { matched: Record<string, string[]> }) {
  const items = Object.entries(matched).flatMap(([z, ts]) => ts.slice(0, 5).map((t) => ({ z, t })));
  if (!items.length) return null;
  return <div className="chips" style={{ marginTop: 8 }} aria-label="Matching terms">{items.map(({ z, t }) => <span key={`${z}-${t}`} className="term" title={`matched in ${ZONE_LABEL[z] ?? z}`}>{t}</span>)}</div>;
}

export function Evidence({ r }: { r: Result }) {
  return (
    <div className="debug">
      <div className="label" style={{ marginBottom: 6 }}>IR evidence: hybrid = (w<sub>cos</sub>·cosine + w<sub>J</sub>·Jaccard) / (w<sub>cos</sub> + w<sub>J</sub>)</div>
      <div className="scorecols" style={{ marginTop: 0 }}>
        <span>Hybrid IR score <b>{num(r.ir_relevance, 4)}</b></span><span>Zone-weighted cosine <b>{num(r.cosine, 4)}</b></span><span>Jaccard <b>{num(r.jaccard, 4)}</b></span>
        <span>Flat cosine <b>{num(r.flat_cosine, 4)}</b></span>
        {Object.entries(r.zone_scores).map(([z, v]) => <span key={z}>{ZONE_LABEL[z]} cosine <b>{num(v, 3)}</b></span>)}
      </div>
      {r.debug && r.debug.term_contributions.length > 0 && (
        <div className="table-wrap" style={{ marginTop: 10 }}>
          <table className="data"><thead><tr><th>Term</th><th>Zone</th><th className="n" title="term frequency in this job">TF</th><th className="n" title="document frequency in the zone">DF</th><th className="n" title="log10(N / DF)">IDF</th><th className="n" title="(1 + log10 TF) × IDF">TF-IDF</th><th className="n" title="TF-IDF after length normalisation">w(doc)</th><th className="n">w(query)</th><th className="n">Zone share α</th><th className="n">Contribution</th></tr></thead>
            <tbody>{r.debug.term_contributions.map((c, i) => (
              <tr key={i}><td><span className="term">{c.surface}</span></td><td>{ZONE_LABEL[c.zone]}</td><td className="n">{c.doc_tf}</td><td className="n">{c.df.toLocaleString()}</td><td className="n">{num(c.idf, 3)}</td><td className="n">{num(c.doc_tfidf, 3)}</td><td className="n">{num(c.doc_weight, 4)}</td><td className="n">{num(c.query_weight, 4)}</td><td className="n">{num(c.zone_share, 3)}</td><td className="n">{num(c.contribution, 4)}</td></tr>))}</tbody></table>
          <p className="tiny muted" style={{ marginTop: 6 }}>Contribution = α × w(query) × w(doc); the contributions add up to the zone-weighted cosine {num(r.cosine, 4)}. Diversity step: max Jaccard to an earlier result {num(r.diversity.max_similarity, 3)}.</p>
        </div>
      )}
    </div>
  );
}

export function ResultCard({ r, query, research, personalized }: { r: Result; query: string; research: boolean; personalized: boolean }) {
  const j = r.job;
  const href = `/job/${j.id}${query ? `?q=${encodeURIComponent(query)}` : ""}`;
  return (
    <article className="result">
      <div className="rank num">{r.rank}</div>
      <div>
        <h3><Link to={href}>{j.title}</Link></h3>
        <div className="small" style={{ margin: "3px 0 0" }}><b>{j.company}</b></div>
        <JobMeta job={j} />
        {j.skills.length > 0 && <div className="chips" aria-label="Skills listed">{j.skills.slice(0, 8).map((s) => <SkillChip key={s} name={pretty(s)} kind="plain" />)}{j.skills.length > 8 && <span className="small muted">+{j.skills.length - 8}</span>}</div>}
        <TermsList matched={r.matched_terms} />
        {personalized && r.career_fit?.missing?.length ? null : null}
        {research && <Evidence r={r} />}
      </div>
      <div className="fit">
        <IRScore value={r.ir_relevance} />
        {personalized && <div style={{ marginTop: 14 }}><FitSummary fit={r.career_fit} /></div>}
      </div>
      <div className="result-actions"><Link className="btn sm" to={href}>View details</Link></div>
    </article>
  );
}

export function InfoBox({ children }: { children: ReactNode }) {
  return <div className="explain-box"><Info size={15} style={{ verticalAlign: "-2px", marginRight: 6 }} />{children}</div>;
}
