"""
Profile, skill-gap analysis, Career Fit and career transition.

Hard rules (each one is covered by a test):
  1. USER SKILLS come only from a resume, typed entries, or a confirmed extracted profile. Never from a search query.
  2. SEARCH QUERY, USER PROFILE, TARGET ROLE and JOB DOCUMENT are four separate things:
       query -> information need (retrieval, in jobs.py)      profile -> the person (this module)
       target role -> what the person wants to become          job -> a retrieved document
  3. Career Fit exists only when a profile exists. Without one the API returns career_fit = None and the reason.
  4. Requirements for a target role are measured from the top-ranked postings for that role in the dataset,
     weighted by their IR relevance. Nothing is hard-coded and nothing is invented.
  5. A skill the user lists is never discarded, whether or not the dataset knows it.
"""
from __future__ import annotations

import difflib
from collections import Counter, defaultdict

from .config import DEFAULT_CONFIG, RankingConfig
from .ir.jobs import JobSearchEngine, QueryError
from .profile.skills import SkillVocabulary, canon, covers, pretty

NO_PROFILE_MESSAGE = "Personalized Career Fit unavailable. Upload your resume or enter your skills."

# Career Fit = weighted mean of the components that can be computed. Hand-set priors, shown in the UI.
FIT_WEIGHTS = {"skills": 0.75, "role": 0.25}
# Target-role requirements
TOP_JOBS = 50            # at most this many top-ranked postings are read
RELEVANCE_RATIO = 0.6    # ...and only those scoring at least this share of the best posting's IR score
MIN_JOBS = 5             # fewer relevant postings than this = "limited evidence"
ROLE_TITLE_COSINE = 0.5  # a posting counts as "this role" when its title is at least this similar to the target role
MIN_PREVALENCE = 0.10    # a skill must appear in this share (IR-weighted) of those postings to count as required
HIGH, MEDIUM = 0.50, 0.25


def normalize_profile(raw: dict | None, vocab: SkillVocabulary) -> dict:
    """Clean a profile coming from the client. Skills are normalised and deduplicated, never dropped."""
    raw = raw or {}
    skills, seen = [], set()
    for item in raw.get("skills") or []:
        name = item.get("name") if isinstance(item, dict) else item
        if not isinstance(name, str) or not name.strip():
            continue
        for sk in vocab.from_list([name.strip()], source=(item.get("source") if isinstance(item, dict) else None) or "typed"):
            if sk.key not in seen:
                seen.add(sk.key)
                skills.append(sk.to_dict())
    years = raw.get("experience_years")
    try:
        years = float(years) if years not in (None, "") else None
    except (TypeError, ValueError):
        years = None
    return {"current_role": (raw.get("current_role") or "").strip() or None, "department": (raw.get("department") or "").strip() or None,
            "experience_years": years if years is None or 0 <= years <= 60 else None, "skills": skills,
            "target_role": (raw.get("target_role") or "").strip() or None, "target_company": (raw.get("target_company") or "").strip() or None}


def has_profile(profile: dict | None) -> bool:
    return bool(profile and (profile.get("skills") or profile.get("current_role")))


def _role_similarity(engine: JobSearchEngine, profile_vec: dict, title: str) -> float:
    jv = engine.title_vector(title)
    return sum(w * jv.get(t, 0.0) for t, w in profile_vec.items())


def job_fit(engine: JobSearchEngine, profile: dict, job, profile_vec: dict | None = None) -> dict | None:
    """Career Fit of ONE job for ONE profile. None when there is no profile."""
    if not has_profile(profile):
        return None
    idf = engine.zone_index["Skills"].idf
    user_keys = [s["key"] for s in profile["skills"]]
    comps, covered, missing = {}, [], []
    if user_keys and job.skill_keys:
        wsum = cov = 0.0
        for i, (name, key) in enumerate(zip(job.skills, [canon(s) for s in job.skills])):
            w = idf.get(key.replace(" ", "_"), 1.0) + 0.1      # rarer skills count more; +0.1 keeps ubiquitous skills non-zero
            wsum += w
            by = next((u for u in user_keys if covers(u, key)), None)
            if by:
                cov += w
                covered.append({"skill": pretty(name), "key": key, "matched_by": by, "i": i})
            else:
                missing.append({"skill": pretty(name), "key": key, "i": i})
        comps["skills"] = cov / wsum if wsum else 0.0
    if profile.get("current_role"):
        if profile_vec is None:
            profile_vec = engine.title_vector(profile["current_role"])
        comps["role"] = _role_similarity(engine, profile_vec, job.title)
    if not comps:
        return {"career_fit": None, "reason": "Add skills or a current role to calculate career fit.", "covered": [], "missing": [], "components": {}}
    wt = sum(FIT_WEIGHTS[c] for c in comps)
    fit = sum(FIT_WEIGHTS[c] * v for c, v in comps.items()) / wt
    n = len(job.skills)
    return {"career_fit": round(fit, 4), "skill_match": round(comps["skills"], 4) if "skills" in comps else None,
            "role_similarity": round(comps["role"], 4) if "role" in comps else None, "covered": covered, "missing": missing,
            "skills_covered": len(covered), "skills_required": n,
            "components": {c: {"score": round(v, 4), "weight": FIT_WEIGHTS[c], "share": round(FIT_WEIGHTS[c] / wt, 4)} for c, v in comps.items()},
            "not_available": ["experience (the dataset has no experience requirement)"]}


def attach_fit(engine: JobSearchEngine, profile: dict | None, results: list[dict]) -> dict:
    """Add a career_fit block to search results. Without a profile nothing personal is added."""
    if not has_profile(profile):
        for r in results:
            r["career_fit"] = None
        return {"available": False, "message": NO_PROFILE_MESSAGE}
    pv = engine.title_vector(profile["current_role"]) if profile.get("current_role") else None
    for r in results:
        r["career_fit"] = job_fit(engine, profile, engine.jobs[r["job"]["id"]], pv)
    return {"available": True, "message": None}


# ------------------------------------------------------------------------------ target-role requirements
def target_requirements(engine: JobSearchEngine, vocab: SkillVocabulary, role: str, company: str | None = None,
                        cfg: RankingConfig = DEFAULT_CONFIG) -> dict:
    """What do the best-matching postings for `role` ask for? (IR-weighted skill prevalence)"""
    filters = {"company": [company]} if company else None
    analysis, top, ctx, stats = engine.retrieve(role, TOP_JOBS, filters, cfg)
    if not top:
        return {"jobs_used": 0, "skills": [], "role_present": False, "limited_evidence": True, "jobs": [], "best_ir": 0.0}
    best = top[0][1]
    kept = [(d, s) for d, s in top if s >= RELEVANCE_RATIO * best and s > 0]
    # does ANY retrieved posting actually share a TITLE term with the role? (otherwise the role may not exist there)
    # The role "exists" only if some posting's TITLE is substantially similar to it (Title-zone cosine >= ROLE_TITLE_COSINE);
    # sharing a single word ("Principal Software Engineer Architect" for "Cloud Architect") is not enough.
    title_best = max((ctx["zone"].get("Title", {}).get(d, 0.0) for d, _ in kept), default=0.0)
    role_present = title_best >= ROLE_TITLE_COSINE if "Title" in analysis["active_zones"] else bool(kept)
    weight_total = sum(s for _, s in kept) or 1.0
    prev: dict[str, float] = defaultdict(float)
    count: Counter = Counter()
    names: dict[str, Counter] = defaultdict(Counter)
    for d, s in kept:
        j = engine.jobs[d]
        for name, key in zip(j.skills, [canon(x) for x in j.skills]):
            prev[key] += s / weight_total
            count[key] += 1
            names[key][name] += 1
    skills = []
    for key, p in sorted(prev.items(), key=lambda kv: (-kv[1], kv[0])):
        if p < MIN_PREVALENCE:
            continue
        skills.append({"key": key, "skill": pretty(names[key].most_common(1)[0][0]), "prevalence": round(p, 4), "jobs": count[key],
                       "type": vocab.types.get(key), "priority": "HIGH" if p >= HIGH else "MEDIUM" if p >= MEDIUM else "LOW"})
    return {"jobs_used": len(kept), "skills": skills, "role_present": role_present, "limited_evidence": len(kept) < MIN_JOBS,
            "best_ir": round(best, 4), "title_best": round(title_best, 4), "jobs": [d for d, _ in kept],
            "example_titles": list(dict.fromkeys(engine.jobs[d].title for d, _ in kept))[:6]}


def skill_gap(profile: dict, requirements: dict) -> dict:
    user = [s["key"] for s in profile["skills"]]
    have, need = [], []
    for sk in requirements["skills"]:
        by = next((u for u in user if covers(u, sk["key"])), None)
        (have if by else need).append({**sk, "matched_by": by})
    total = sum(s["prevalence"] for s in requirements["skills"])
    match = sum(s["prevalence"] for s in have) / total if total else None
    required_keys = [s["key"] for s in requirements["skills"]]
    extra = [s for s in profile["skills"] if not any(covers(s["key"], r) for r in required_keys)]
    return {"profile_match": None if match is None else round(match, 4), "have": have, "to_develop": need, "other_skills": extra,
            "required_total": len(requirements["skills"])}


def preparation_plan(gap: dict, requirements: dict, role: str) -> list[dict]:
    n = requirements["jobs_used"]
    plan = []
    for i, sk in enumerate(gap["to_develop"], 1):
        plan.append({"order": i, "skill": sk["skill"], "key": sk["key"], "priority": sk["priority"], "type": sk["type"],
                     "evidence": f"Listed in {round(sk['prevalence'] * 100)}% (IR-weighted) of the {n} most relevant '{role}' postings ({sk['jobs']} postings)."})
    return plan


# ------------------------------------------------------------------------------ the transition itself
def analyze_transition(engine: JobSearchEngine, vocab: SkillVocabulary, profile: dict, target_role: str, target_company: str | None = None,
                       k: int = 10, cfg: RankingConfig = DEFAULT_CONFIG) -> dict:
    target_role = (target_role or "").strip()
    if not target_role:
        raise QueryError("Enter a target role, for example 'Cloud Architect'.")
    if not has_profile(profile):
        raise QueryError(NO_PROFILE_MESSAGE)
    notes: list[str] = []
    company, company_status = None, None
    if target_company and target_company.strip():
        company, close = engine.resolve_company(target_company)
        if company is None:
            company_status = {"status": "not_in_dataset", "asked": target_company.strip(), "suggestions": close}
            notes.append(f"'{target_company.strip()}' has no postings in this dataset"
                         + (f" (similar names: {', '.join(close)})." if close else ".") + " Showing the role across all companies instead.")
        else:
            company_status = {"status": "found", "company": company, "listings": len(engine.param["company"][company.lower()])}

    unknown = engine.analyze(target_role, cfg)["unknown"]
    if unknown:
        notes.append("Not found in any listing, so they did not affect the target role: " + ", ".join(unknown) + ".")
    all_req = target_requirements(engine, vocab, target_role, None, cfg)
    if all_req["jobs_used"] == 0:
        words = [w for w in engine.vocab_words if abs(len(w) - len(target_role.split()[0])) < 4]
        close = difflib.get_close_matches(target_role.split()[0].lower(), words, n=4, cutoff=0.7)
        raise QueryError(f"No postings in the dataset match '{target_role}'." + (f" Did you mean: {', '.join(close)}?" if close else " Try a more common title such as 'Data Engineer' or 'Cloud Engineer'."))
    req, scope = all_req, "all companies"
    company_req = None
    if company:
        company_req = target_requirements(engine, vocab, target_role, company, cfg)
        if company_req["jobs_used"] and company_req["role_present"]:
            req, scope = company_req, company
        else:
            company_status["role_present"] = False
            notes.append(f"{company} has {company_status['listings']} postings in the dataset, but none has a title matching '{target_role}'. "
                         f"Requirements below come from '{target_role}' postings at all companies; the closest {company} postings are listed separately.")
    if all_req["limited_evidence"]:
        notes.append(f"Only {all_req['jobs_used']} relevant postings were found, so the requirements are based on limited evidence.")

    gap = skill_gap(profile, req)
    plan = preparation_plan(gap, req, target_role)

    # recommended jobs: IR-relevant postings for the target role, re-ranked by Career Fit for THIS profile
    pool_filters = {"company": [company]} if (company and scope == company) else None
    analysis, top, ctx, _ = engine.retrieve(target_role, 60, pool_filters, cfg)
    best = top[0][1] if top else 0.0
    pv = engine.title_vector(profile["current_role"]) if profile.get("current_role") else None
    rows = []
    for d, ir in top:
        if ir < RELEVANCE_RATIO * best:
            continue
        j = engine.jobs[d]
        fit = job_fit(engine, profile, j, pv)
        rows.append({"job": j.to_dict(), "ir_relevance": round(ir, 4), "career_fit": fit["career_fit"] if fit else None, "fit": fit})
    rows.sort(key=lambda r: (-(r["career_fit"] or 0), -r["ir_relevance"], r["job"]["id"]))
    seen, jobs_out = set(), []
    for r in rows:                              # one row per (title, company); the listing count says how many postings it stands for
        sig = (r["job"]["title"].lower(), r["job"]["company"].lower())
        if sig not in seen:
            seen.add(sig); jobs_out.append(r)
    jobs_out = jobs_out[:k]
    comp_stats: dict[str, dict] = {}
    for r in rows:
        c = comp_stats.setdefault(r["job"]["company"], {"company": r["job"]["company"], "jobs": 0, "best_fit": 0.0, "best_ir": 0.0})
        c["jobs"] += 1; c["best_fit"] = max(c["best_fit"], r["career_fit"] or 0); c["best_ir"] = max(c["best_ir"], r["ir_relevance"])
    companies = sorted(comp_stats.values(), key=lambda c: (-c["best_fit"], -c["jobs"]))[:8]

    closest_at_company = []
    if company and scope != company:
        _, ctop, cctx, _ = engine.retrieve(target_role, 5, {"company": [company]}, cfg)
        closest_at_company = [{"job": engine.jobs[d].to_dict(), "ir_relevance": round(s, 4)} for d, s in ctop]

    return {"profile": {"current_role": profile.get("current_role"), "department": profile.get("department"), "experience_years": profile.get("experience_years"),
                        "skills": profile["skills"]},
            "target": {"role": target_role, "company": company, "requirement_scope": scope},
            "career_fit": gap["profile_match"], "profile_match": gap["profile_match"], "have": gap["have"], "to_develop": gap["to_develop"], "other_skills": gap["other_skills"],
            "preparation_plan": plan, "requirements": {"jobs_used": req["jobs_used"], "skills": req["skills"], "limited_evidence": req["limited_evidence"],
                                                      "example_titles": req.get("example_titles", []), "best_ir": req["best_ir"],
                                                      "thresholds": {"top_jobs": TOP_JOBS, "relevance_ratio": RELEVANCE_RATIO, "min_prevalence": MIN_PREVALENCE,
                                                                     "high": HIGH, "medium": MEDIUM}},
            "recommended_jobs": jobs_out, "companies": companies, "company_status": company_status, "closest_at_company": closest_at_company,
            "notes": notes, "fit_weights": FIT_WEIGHTS}
