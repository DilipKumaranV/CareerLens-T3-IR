"""
CareerLens API (FastAPI). The index is built ONCE at start-up. All IR logic lives in app/ir and app/career;
this file validates input, calls them and maps errors to HTTP responses.

Run:  python -m uvicorn app.main:app --port 8000      (from the backend/ folder)     Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import career as career_mod
from . import evaluation as evaluation_mod
from .analytics import dataset_analytics
from .config import DATASET_INFO_PATH, DEFAULT_CONFIG, EVAL_RESULTS_PATH, FRONTEND_DIST, ZONES
from .ir.jobs import FILTER_FIELDS, JobSearchEngine, QueryError
from .profile import service as resume_service
from .profile.resume import ResumeError
from .profile.skills import pretty
from .schemas import CompareRequest, ExplainRequest, ProfileIn, SearchRequest, TraceRequest, TransitionRequest

STATE: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    STATE["engine"] = JobSearchEngine()
    STATE["analytics"] = dataset_analytics(STATE["engine"])
    yield
    STATE.clear()


app = FastAPI(title="CareerLens API", version="4.0",
              description="Explainable Information Retrieval platform for job discovery and career transition planning (CSD358).", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])


def engine() -> JobSearchEngine:
    if "engine" not in STATE:
        raise HTTPException(503, "The search index is still loading. Try again in a moment.")
    return STATE["engine"]


def _cfg(o):
    try:
        return o.build() if o else DEFAULT_CONFIG
    except ValueError as e:
        raise HTTPException(422, f"Invalid ranking configuration: {e}") from e


def _profile(p: ProfileIn | None) -> dict | None:
    """Normalise a client profile. Returns None when there is nothing usable (then no personalization happens)."""
    if p is None:
        return None
    prof = career_mod.normalize_profile(p.model_dump(), engine().vocab)
    return prof if career_mod.has_profile(prof) else None


@app.exception_handler(QueryError)
async def _query_error(_: Request, exc: QueryError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ResumeError)
async def _resume_error(_: Request, exc: ResumeError):
    return JSONResponse(status_code=422, content={"detail": exc.message, "code": exc.code})


@app.exception_handler(KeyError)
async def _not_found(_: Request, exc: KeyError):
    return JSONResponse(status_code=404, content={"detail": str(exc.args[0]) if exc.args else "Not found"})


@app.exception_handler(RequestValidationError)
async def _validation(_: Request, exc: RequestValidationError):
    msgs = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
        msgs.append(f"{loc}: {err.get('msg')}" if loc else err.get("msg", "invalid input"))
    return JSONResponse(status_code=422, content={"detail": "; ".join(msgs)})


# ---------------------------------------------------------------- meta
@app.get("/api/health")
def health():
    e = STATE.get("engine")
    return {"status": "ok" if e else "loading", "listings": e.N if e else None, "index_build_ms": round(e.build_ms) if e else None}


@app.get("/api/meta")
def meta():
    e = engine()
    try:
        info = json.loads(DATASET_INFO_PATH.read_text())
    except (OSError, ValueError):
        info = {}
    return {"dataset": info, "listings": e.N, "zones": ZONES, "zone_weights": DEFAULT_CONFIG.zone_weights, "default_config": DEFAULT_CONFIG.to_dict(),
            "filter_fields": FILTER_FIELDS, "filter_options": e.filter_options(),
            "vocabulary": {z: e.zone_index[z].vocabulary_size for z in ZONES}, "skill_vocabulary": len(e.vocab),
            "fit_weights": career_mod.FIT_WEIGHTS, "career_thresholds": {"top_jobs": career_mod.TOP_JOBS, "relevance_ratio": career_mod.RELEVANCE_RATIO,
            "min_jobs": career_mod.MIN_JOBS, "min_prevalence": career_mod.MIN_PREVALENCE, "high": career_mod.HIGH, "medium": career_mod.MEDIUM},
            "no_profile_message": career_mod.NO_PROFILE_MESSAGE, "index_build_ms": round(e.build_ms)}


@app.get("/api/companies")
def companies(q: str = Query("", max_length=80), limit: int = Query(8, ge=1, le=20)):
    return {"companies": engine().suggest_companies(q, limit)}


@app.get("/api/skills/suggest")
def skills_suggest(q: str = Query("", max_length=60), limit: int = Query(8, ge=1, le=20)):
    e, ql = engine(), q.strip().lower()
    if not ql:
        return {"skills": []}
    names = sorted((k for k in e.vocab.types if ql in k), key=lambda k: (not k.startswith(ql), len(k), k))[:limit]
    return {"skills": [{"name": pretty(k), "key": k, "type": e.vocab.types.get(k)} for k in names]}


# ---------------------------------------------------------------- search and jobs
@app.post("/api/search")
def search(req: SearchRequest):
    e = engine()
    out = e.search(req.query, req.k, req.filters, _cfg(req.config), req.sort, req.debug)
    out["personalization"] = career_mod.attach_fit(e, _profile(req.profile), out["results"])
    return out


@app.get("/api/jobs/{job_id}")
def job_get(job_id: int, q: str = Query("", max_length=500)):
    e = engine()
    return {"job": e.get_job(job_id).to_dict(), "ir_evidence": e.evidence_for(job_id, q), "similar": e.similar(job_id, 6)["results"]}


@app.post("/api/jobs/{job_id}/explain")
def job_explain(job_id: int, req: ExplainRequest):
    e = engine()
    job = e.get_job(job_id)
    prof = _profile(req.profile)
    out = {"job": job.to_dict(), "ir_evidence": e.evidence_for(job_id, req.query), "similar": e.similar(job_id, 6)["results"],
           "personalization": {"available": prof is not None, "message": None if prof else career_mod.NO_PROFILE_MESSAGE}, "career_fit": None, "preparation": []}
    if prof:
        fit = career_mod.job_fit(e, prof, job)
        out["career_fit"] = fit
        if fit and fit["missing"]:
            req_role = career_mod.target_requirements(e, e.vocab, job.title, None, DEFAULT_CONFIG)
            prev = {s["key"]: s for s in req_role["skills"]}
            prep = []
            for m in fit["missing"]:
                r = prev.get(m["key"])
                prep.append({"skill": m["skill"], "key": m["key"], "priority": r["priority"] if r else "LOW",
                             "evidence": (f"Listed in {round(r['prevalence'] * 100)}% of the {req_role['jobs_used']} most relevant '{job.title}' postings." if r
                                          else "Listed in this posting; rare among similar postings."), "_p": r["prevalence"] if r else 0.0})
            prep.sort(key=lambda x: -x["_p"])
            out["preparation"] = [{**{k: v for k, v in p.items() if k != "_p"}, "order": i} for i, p in enumerate(prep, 1)]
    return out


@app.get("/api/jobs/{job_id}/similar")
def similar(job_id: int, k: int = Query(6, ge=1, le=30)):
    return engine().similar(job_id, k)


@app.post("/api/compare")
def compare(req: CompareRequest):
    e = engine()
    prof = _profile(req.profile)
    jobs = [e.get_job(i) for i in req.ids]
    rows = []
    for j in jobs:
        rows.append({"job": j.to_dict(), "career_fit": career_mod.job_fit(e, prof, j) if prof else None})
    shared = set.intersection(*[set(j.skill_keys) for j in jobs]) if jobs else set()
    return {"jobs": rows, "shared_skills": [pretty(s) for s in sorted(shared)], "personalization": {"available": prof is not None, "message": None if prof else career_mod.NO_PROFILE_MESSAGE}}


# ---------------------------------------------------------------- resume, profile, career transition
@app.get("/api/resume/demos")
def resume_demos():
    return {"demos": resume_service.demo_list(), "label": "Demo Profiles: fictional candidates for testing, not real people."}


@app.post("/api/resume/analyze")
async def resume_analyze(file: UploadFile = File(...)):
    if file.filename and not file.filename.lower().endswith(".pdf"):
        raise ResumeError("not_pdf", "Please upload a PDF file (.pdf), or enter your profile manually.")
    return resume_service.analyze_resume(await file.read(), file.filename or "resume.pdf", engine().vocab)


@app.post("/api/resume/demo/{key}")
def resume_demo(key: str):
    """Runs a bundled demo PDF through exactly the same pipeline as an uploaded one."""
    return resume_service.analyze_demo(key, engine().vocab)


@app.post("/api/profile")
def profile_normalize(profile: ProfileIn):
    """Normalise a profile (skills are normalised and deduplicated, never dropped). Nothing is stored server-side."""
    prof = career_mod.normalize_profile(profile.model_dump(), engine().vocab)
    for s in prof["skills"]:
        s["display"] = pretty(s["name"]) if s["status"] == "dataset" else s["name"]
    return {"profile": prof, "usable": career_mod.has_profile(prof), "message": None if career_mod.has_profile(prof) else career_mod.NO_PROFILE_MESSAGE}


@app.post("/api/career-transition")
def career_transition(req: TransitionRequest):
    e = engine()
    prof = career_mod.normalize_profile(req.profile.model_dump(), e.vocab)
    return career_mod.analyze_transition(e, e.vocab, prof, req.target_role, req.target_company, req.k)


# ---------------------------------------------------------------- research, evaluation, analytics
@app.post("/api/research/trace")
def trace(req: TraceRequest):
    return engine().trace(req.query, req.k, req.filters, _cfg(req.config))


@app.get("/api/analytics")
def analytics():
    engine()
    return STATE["analytics"]


@app.get("/api/evaluation")
def get_evaluation():
    if EVAL_RESULTS_PATH.exists():
        return json.loads(EVAL_RESULTS_PATH.read_text())
    return evaluation_mod.run_and_save(engine())


@app.post("/api/evaluation/run")
def run_evaluation():
    return evaluation_mod.run_and_save(engine())


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, f"No API route /{path}")
    if not FRONTEND_DIST.exists():
        return JSONResponse({"detail": "Frontend not built. Run the Vite dev server (see README) or `npm run build`."}, status_code=404)
    target = (FRONTEND_DIST / path).resolve()
    if path and target.is_file() and FRONTEND_DIST.resolve() in target.parents:
        return FileResponse(target)
    return FileResponse(FRONTEND_DIST / "index.html")
