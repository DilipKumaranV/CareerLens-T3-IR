"""
Job retrieval engine (classical IR). Built once at start-up and reused by every request.

Pipeline for a search:
  analyze()   query text -> tokens -> stop words -> stems -> biwords; skills named in the query are detected
              with the skill vocabulary. The query is the INFORMATION NEED and nothing else: no user profile
              enters this module, so a search term can never become a user skill.
  candidates  union of the postings of the query terms, intersected with the parametric filters
  score_all   per-zone TF-IDF cosine (term-at-a-time), Jaccard, hybrid IR score
  order       heap top-K, then a near-tie diversity step
"""
from __future__ import annotations

import csv
import difflib
import gc
import hashlib
import heapq
import math
import pickle
import random
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ..config import BIWORD_ZONES, DATA_PATH, DEFAULT_CONFIG, ZONES, RankingConfig
from ..profile.skills import SkillVocabulary, canon
from .dedup import jaccard
from .diversity import bounded_rerank
from .index import InvertedIndex
from .preprocess import make_biwords, normalize_tokens, raw_tokens

FILTER_FIELDS = {"company": "Company", "country": "Country", "workplace": "Workplace", "schedule": "Employment type", "role_family": "Role family"}


class QueryError(ValueError):
    """Input the engine cannot answer (empty request, unknown filter value)."""


def _f(x):
    try:
        return float(x) if x not in ("", None) else None
    except ValueError:
        return None


@dataclass
class Job:
    id: int
    title: str
    company: str
    location: str
    country: str
    workplace: str
    schedule: str
    role_family: str
    skills: list[str]
    skill_keys: list[str]
    posted: str
    salary_year: float | None
    salary_hour: float | None
    salary_rate: str
    via: str
    listings: int
    no_degree: bool
    health_insurance: bool

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "company": self.company, "location": self.location or None, "country": self.country,
                "workplace": self.workplace, "schedule": self.schedule, "role_family": self.role_family, "skills": self.skills,
                "posted": self.posted, "salary_year": self.salary_year, "salary_hour": self.salary_hour, "salary_rate": self.salary_rate or None,
                "via": self.via or None, "listings": self.listings, "no_degree": self.no_degree, "health_insurance": self.health_insurance}


def load_jobs(path: Path) -> list[Job]:
    if not Path(path).exists():
        raise FileNotFoundError(f"Dataset not found at {path}. Build it with: python tools/build_dataset.py --input data_jobs.csv")
    jobs = []
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            skills = [s for s in (r.get("skills") or "").split("|") if s]
            keys = list(dict.fromkeys(canon(s) for s in skills))
            jobs.append(Job(id=len(jobs), title=r["title"], company=r["company"], location=r.get("location") or "", country=r.get("country") or "Unknown",
                            workplace=r.get("workplace") or "Not remote", schedule=r.get("schedule") or "Not stated", role_family=r.get("role_family") or "",
                            skills=skills, skill_keys=keys, posted=r.get("posted") or "", salary_year=_f(r.get("salary_year_avg")),
                            salary_hour=_f(r.get("salary_hour_avg")), salary_rate=r.get("salary_rate") or "", via=r.get("via") or "",
                            listings=int(r.get("listings") or 1), no_degree=r.get("no_degree") == "True", health_insurance=r.get("health_insurance") == "True"))
    if not jobs:
        raise ValueError("The dataset file is empty.")
    return jobs


INDEX_VERSION = 5     # bump when the document representation changes, so old caches are ignored


def _skill_term(key: str) -> str:
    return key.replace(" ", "_")


def _fingerprint(path: Path) -> str:
    h = hashlib.sha1(Path(path).read_bytes())
    h.update(f"v{INDEX_VERSION}|{','.join(ZONES)}".encode())
    return h.hexdigest()


def _worktype_text(j) -> str:
    """Words for the WorkType zone, from the schedule type and the remote flag only (no invented data).
    Spelling variants of the dataset's own values are added so "contract" finds "Contractor"."""
    low = j.schedule.lower()
    words = [] if j.schedule == "Not stated" else [j.schedule]
    for key, extra in (("contract", "contract contractor"), ("intern", "intern internship"), ("part", "parttime"), ("full", "fulltime"), ("temp", "temporary temp")):
        if key in low:
            words.append(extra)
    if j.workplace == "Remote":
        words.append("remote wfh")
    return " ".join(words)


class JobSearchEngine:
    _CACHED = ("zone_index", "flat_index", "term_sets", "_surface", "param", "company_lower", "vocab_words")

    def __init__(self, data_path: Path = DATA_PATH, vocab: SkillVocabulary | None = None, use_cache: bool = True):
        t0 = time.perf_counter()
        self.jobs = load_jobs(data_path)
        self.N = len(self.jobs)
        self.vocab = vocab or SkillVocabulary.load()
        self._tb: dict[int, list[float]] = {}
        self._sim: dict[tuple[int, int], float] = {}
        self.cache_status = "disabled"
        if use_cache:
            cache, key = Path(data_path).with_name(".index_cache.pkl"), _fingerprint(data_path)
            if self._load_cache(cache, key):
                self.cache_status = "loaded from cache"
            else:
                self._build()
                self.cache_status = "built and cached" if self._save_cache(cache, key) else "built (cache not writable)"
        else:
            self._build()
        self.build_ms = (time.perf_counter() - t0) * 1000

    def _build(self) -> None:
        """Preprocess every listing and build the inverted indexes (the slow part: tens of seconds)."""
        self._surface: dict[str, Counter] = defaultdict(Counter)
        zdocs = {z: [] for z in ZONES}
        flat = []
        for j in self.jobs:
            t_uni, t_bi = self._terms(j.title, True)
            c_uni, c_bi = self._terms(j.company, True)
            loc_text = j.location if (j.country or "").lower() in (j.location or "").lower() else f"{j.location}, {j.country}".strip(", ")
            l_uni, _ = self._terms(loc_text, False)
            w_uni, _ = self._terms(_worktype_text(j), False)
            zdocs["Title"].append(t_uni + t_bi)
            zdocs["Skills"].append([_skill_term(k) for k in j.skill_keys])
            zdocs["Location"].append(l_uni)
            zdocs["Company"].append(c_uni + c_bi)
            zdocs["WorkType"].append(w_uni)
            sk_words = [w for k in j.skill_keys for w in normalize_tokens(raw_tokens(k), stemming=True)]
            flat.append(t_uni + sk_words + c_uni + l_uni + w_uni)
        self.zone_index = {z: InvertedIndex(zdocs[z], name=z) for z in ZONES}
        self.flat_index = InvertedIndex(flat, name="flat")
        self.term_sets = [frozenset(d) for d in flat]
        self.param: dict[str, dict[str, set[int]]] = {f: defaultdict(set) for f in FILTER_FIELDS}
        self.company_lower: dict[str, str] = {}
        for j in self.jobs:
            vals = {"company": j.company, "country": j.country, "workplace": j.workplace, "schedule": j.schedule, "role_family": j.role_family}
            for f, v in vals.items():
                if v:
                    self.param[f][v.lower() if f == "company" else v].add(j.id)
            self.company_lower[j.company.lower()] = j.company
        self.vocab_words = sorted(self._display_vocab())

    def _save_cache(self, path: Path, key: str) -> bool:
        try:
            tmp = path.with_suffix(".tmp")
            with open(tmp, "wb") as fh:
                pickle.dump({"key": key, **{n: getattr(self, n) for n in self._CACHED}}, fh, protocol=pickle.HIGHEST_PROTOCOL)
            tmp.replace(path)
            return True
        except Exception:      # read-only folder, disk full...: the app still works, it just rebuilds next time
            return False

    def _load_cache(self, path: Path, key: str) -> bool:
        try:
            gc.disable()                     # loading millions of small objects is ~2x faster without garbage-collection passes
            try:
                with open(path, "rb") as fh:
                    blob = pickle.load(fh)
            finally:
                gc.enable()
            if blob.get("key") != key:
                return False
            for n in self._CACHED:
                setattr(self, n, blob[n])
            return True
        except Exception:      # missing, stale or corrupt cache: rebuild
            return False

    # ------------------------------------------------------------------ helpers
    def _terms(self, text: str, biwords: bool):
        uni, bis = [], []
        for seg in (text or "").split(","):
            toks = raw_tokens(seg)
            stems = normalize_tokens(toks, stemming=True)
            lows = normalize_tokens(toks, stemming=False)
            for s, l in zip(stems, lows):
                self._surface[s][l.lower()] += 1
            uni += stems
            if biwords:
                for (a, b), (la, lb) in zip(zip(stems, stems[1:]), zip(lows, lows[1:])):
                    self._surface[f"{a}_{b}"][f"{la.lower()} {lb.lower()}"] += 1
                bis += make_biwords(stems)
        return uni, bis

    def display(self, term: str) -> str:
        c = self._surface.get(term)
        return c.most_common(1)[0][0] if c else term.replace("_", " ")

    def _display_vocab(self):
        return {self.display(t) for t in self.zone_index["Title"].postings if "_" not in t}

    def sim(self, a: int, b: int) -> float:
        key = (a, b) if a < b else (b, a)
        if key not in self._sim:
            self._sim[key] = jaccard(self.term_sets[a], self.term_sets[b])
        return self._sim[key]

    def tiebreak(self, seed: int | None, d: int) -> float:
        if seed is None:
            return d
        if seed not in self._tb:
            rng = random.Random(seed)
            self._tb[seed] = [rng.random() for _ in range(self.N)]
        return self._tb[seed][d]

    def filter_options(self) -> dict:
        out = {}
        for f in ("country", "workplace", "schedule", "role_family"):
            out[f] = sorted(((v, len(ids)) for v, ids in self.param[f].items()), key=lambda x: (-x[1], x[0]))[: 60 if f == "country" else 20]
        return out

    def suggest_companies(self, q: str, limit: int = 8) -> list[dict]:
        q = (q or "").strip().lower()
        if len(q) < 2:
            return []
        counts = {name: len(self.param["company"][name.lower()]) for name in self.company_lower.values()
                  if q in name.lower()} if len(q) >= 2 else {}
        starts = sorted(counts, key=lambda n: (not n.lower().startswith(q), -counts[n], n))[:limit]
        return [{"company": n, "listings": counts[n]} for n in starts]

    def resolve_company(self, name: str) -> tuple[str | None, list[str]]:
        """Exact (case-insensitive) company match, else close spellings. Never guesses."""
        key = (name or "").strip().lower()
        if key in self.company_lower:
            return self.company_lower[key], []
        close = difflib.get_close_matches(key, list(self.company_lower), n=5, cutoff=0.8)
        contains = [self.company_lower[k] for k in self.company_lower if key and key in k][:5]
        return None, list(dict.fromkeys([self.company_lower[c] for c in close] + contains))[:6]

    def allowed_docs(self, filters: dict | None) -> set[int] | None:
        if not filters:
            return None
        allowed: set[int] | None = None
        for f, values in filters.items():
            if not values:
                continue
            if f not in self.param:
                raise QueryError(f"Unknown filter '{f}'. Use one of: {', '.join(FILTER_FIELDS)}.")
            ids: set[int] = set()
            for v in values:
                key = v.lower() if f == "company" else v
                if key not in self.param[f]:
                    hint = ""
                    if f == "company":
                        _, close = self.resolve_company(v)
                        hint = f" Did you mean: {', '.join(close)}?" if close else ""
                    raise QueryError(f"No {FILTER_FIELDS[f].lower()} '{v}' in the dataset.{hint}")
                ids |= self.param[f][key]
            allowed = ids if allowed is None else allowed & ids
        return allowed

    # ------------------------------------------------------------------ query analysis
    def _route(self, stems: list[str], bis: list[str], skill_keys: list[str], cfg: RankingConfig):
        """Zone routing. Each query term is looked up in a zone only if its document frequency there is at least
        routing_tau times its document frequency in the zone where it is most common (skills included in the comparison).
        Without routing, an incidental word ("cloud" inside a company name) activates a zone that can only score 0 and
        drags every score down. With routing, zone weights apply only to the fields the query is really about."""
        tf = Counter(stems + bis)
        zone_terms = {z: {} for z in ZONES}
        skill_df, skill_words = {}, {}
        for key in skill_keys:
            dfk = self.zone_index["Skills"].df.get(_skill_term(key), 0)
            for w in normalize_tokens(raw_tokens(key), stemming=True):
                skill_df[w] = max(skill_df.get(w, 0), dfk)
                skill_words.setdefault(key, []).append(w)
        routing = []
        for t, c in tf.items():
            dfs = {"Title": self.zone_index["Title"].df.get(t, 0), "Company": self.zone_index["Company"].df.get(t, 0)}
            if "_" not in t:
                dfs["Location"] = self.zone_index["Location"].df.get(t, 0)
                dfs["WorkType"] = self.zone_index["WorkType"].df.get(t, 0)
                if t in skill_df:
                    dfs["Skills"] = skill_df[t]
            mx = max(dfs.values())
            if mx == 0:
                continue
            routed = [z for z, v in dfs.items() if v > 0 and (not cfg.use_routing or v >= cfg.routing_tau * mx)]
            for z in routed:
                if z != "Skills":
                    zone_terms[z][t] = (c, 1.0)
            routing.append({"surface": self.display(t), "df": {z: v for z, v in dfs.items() if v}, "routed_to": routed})
        for key in skill_keys:
            term = _skill_term(key)
            dfk = self.zone_index["Skills"].df.get(term, 0)
            if dfk == 0:
                continue
            others = max([max(self.zone_index[z].df.get(w, 0) for z in ("Title", "Company", "Location")) for w in skill_words.get(key, [""])] or [0])
            if not cfg.use_routing or dfk >= cfg.routing_tau * max(others, 1) or others == 0:
                zone_terms["Skills"][term] = (1, 1.0)
        return zone_terms, routing

    def analyze(self, query: str, cfg: RankingConfig = DEFAULT_CONFIG) -> dict:
        query = query or ""
        toks = raw_tokens(query)
        removed: list = []
        lows = normalize_tokens(toks, query=True, stemming=False, removed=removed)
        stems = normalize_tokens(toks, query=True, stemming=True)
        bis = make_biwords(stems) if cfg.use_biwords else []
        skills = self.vocab.extract(query, source="query")           # skills NAMED IN THE QUERY (an information need, not a user skill)
        skill_keys = list(dict.fromkeys(s.key for s in skills))
        # Also accept any query word or word pair that is a skill in the Skills index, even if it is an "ambiguous" word in resume text
        # ("dax"): routing compares its frequency across fields, so a coincidental word does not become a skill.
        words = [l for l in lows]
        for cand in words + [f"{a} {b}" for a, b in zip(words, words[1:])]:
            key = canon(cand)
            if key not in skill_keys and _skill_term(key) in self.zone_index["Skills"].idf:
                skill_keys.append(key)
        zone_terms, routing = self._route(stems, bis, skill_keys, cfg)
        zone_vectors = {z: self.zone_index[z].query_vector(zone_terms[z]) for z in ZONES}
        active = [z for z in ZONES if zone_vectors[z]]
        flat_vec = self.flat_index.query_vector({t: (c, 1.0) for t, c in Counter(stems).items()})
        skill_words = {w for k in skill_keys for w in normalize_tokens(raw_tokens(k), stemming=True)}
        unknown = [l for s, l in zip(stems, lows) if s not in self.flat_index.idf and s not in skill_words]
        suggestions = {u: difflib.get_close_matches(u, self.vocab_words, n=3, cutoff=0.75) for u in unknown}
        terms = []
        for z in ZONES:
            for t, (tf, _) in zone_terms[z].items():
                if t in self.zone_index[z].idf:
                    terms.append({"zone": z, "term": t, "surface": self.display(t) if z != "Skills" else t.replace("_", " "), "tf": tf,
                                  "df": self.zone_index[z].df[t], "idf": round(self.zone_index[z].idf[t], 4)})
        return {"raw": query, "tokens": [t.lower() for t in toks], "removed": [{"token": t, "reason": r} for t, r in removed], "kept": lows,
                "stems": [{"token": l, "stem": s} for l, s in zip(lows, stems)], "biwords": [self.display(b) for b in bis if b in self.flat_index.idf or b in self.zone_index["Title"].idf],
                "query_skills": skill_keys, "routing": routing, "zone_terms": zone_terms, "zone_vectors": zone_vectors, "active_zones": active,
                "flat_vector": flat_vec, "query_set": frozenset(stems), "unknown": unknown, "suggestions": suggestions, "terms": terms}

    # ------------------------------------------------------------------ scoring
    def score_all(self, analysis: dict, cfg: RankingConfig = DEFAULT_CONFIG, allowed: set[int] | None = None):
        """Returns (scored, ctx, stats). scored maps doc -> hybrid IR score; ctx keeps the parts (cosine, Jaccard,
        per-zone cosines) so full records are built only for the few results that are shown."""
        active = analysis["active_zones"]
        alpha = {z: max(0.0, cfg.zone_weights.get(z, 0.0)) for z in ZONES}
        total = sum(alpha[z] for z in active)
        stats = {"postings_traversed": 0, "zone_candidates": {}}
        zone_scores: dict[str, dict[int, float]] = {}
        if cfg.use_zones and active and total > 0:
            cos_map: dict[int, float] = defaultdict(float)
            for z in active:
                sc, trav = self.zone_index[z].cosine_scores(analysis["zone_vectors"][z], allowed)
                zone_scores[z] = sc
                stats["postings_traversed"] += trav
                stats["zone_candidates"][z] = len(sc)
                f = alpha[z] / total
                for d, v in sc.items():
                    cos_map[d] += f * v
        elif analysis["flat_vector"]:
            cos_map, trav = self.flat_index.cosine_scores(analysis["flat_vector"], allowed)
            stats["postings_traversed"] += trav
        else:
            cos_map = {}
        qset = analysis["query_set"]
        nq = len(qset)
        wsum = cfg.w_cosine + cfg.w_jaccard
        wc, wj = cfg.w_cosine / wsum, cfg.w_jaccard / wsum
        scored: dict[int, float] = {}
        jac_map: dict[int, float] = {}
        ts = self.term_sets
        for d, c in cos_map.items():
            j = 0.0
            if nq:
                s = ts[d]
                inter = len(qset & s)
                if inter:
                    j = inter / (nq + len(s) - inter)
            jac_map[d] = j
            scored[d] = wc * c + wj * j
        stats["candidates"] = len(cos_map)
        stats["documents_never_scored"] = self.N - len(cos_map)
        return scored, {"cos": cos_map, "jac": jac_map, "zone": zone_scores, "active": active}, stats

    def order(self, scored: dict[int, float], k: int, cfg: RankingConfig = DEFAULT_CONFIG, seed: int | None = None) -> list[dict]:
        n = k * max(1, cfg.pool_factor) if cfg.diversity else k
        top = heapq.nsmallest(n, scored, key=lambda d: (-scored[d], self.tiebreak(seed, d)))
        if cfg.diversity:
            return bounded_rerank([(d, scored[d]) for d in top], k, cfg.diversity_epsilon, self.sim)
        return [{"doc": d, "relevance": scored[d], "penalty": 0.0, "max_sim": 0.0, "most_similar": None} for d in top[:k]]

    def contributions(self, analysis: dict, d: int, cfg: RankingConfig) -> list[dict]:
        active = analysis["active_zones"]
        tot = sum(cfg.zone_weights.get(z, 0) for z in active) or 1.0
        out = []
        for z in active:
            share = cfg.zone_weights.get(z, 0) / tot
            dv = self.zone_index[z].doc_vectors[d]
            for t, qw in analysis["zone_vectors"][z].items():
                dw = dv.get(t)
                if dw:
                    tf = self.zone_index[z].doc_tf[d].get(t, 0)
                    idf = self.zone_index[z].idf[t]
                    out.append({"zone": z, "term": t, "surface": t.replace("_", " ") if z == "Skills" else self.display(t), "query_weight": qw,
                                "doc_tf": tf, "df": self.zone_index[z].df[t], "idf": idf, "doc_tfidf": (1 + math.log10(tf)) * idf if tf else 0.0,
                                "doc_weight": dw, "zone_share": share, "contribution": share * qw * dw})
        return sorted(out, key=lambda r: -r["contribution"])

    def _payload(self, analysis, ctx, hybrid, d, rank_info, rank, cfg, debug) -> dict:
        job = self.jobs[d]
        contrib = self.contributions(analysis, d, cfg)
        matched: dict[str, list[str]] = defaultdict(list)
        for c in contrib:
            if c["surface"] not in matched[c["zone"]]:
                matched[c["zone"]].append(c["surface"])
        label = {"Title": "Title matches", "Skills": "Skills include", "Location": "Location matches", "Company": "Company matches", "WorkType": "Work type matches"}
        reasons = [f"{label[z]} {', '.join(repr(m) for m in matched[z][:5])}" for z in analysis["active_zones"] if matched.get(z)]
        dv = self.flat_index.doc_vectors[d]
        flat_cos = sum(w * dv.get(t, 0.0) for t, w in analysis["flat_vector"].items())
        out = {"rank": rank, "job": job.to_dict(), "ir_relevance": round(hybrid, 6), "cosine": round(ctx["cos"].get(d, 0.0), 6),
               "jaccard": round(ctx["jac"].get(d, 0.0), 6), "flat_cosine": round(flat_cos, 6),
               "zone_scores": {z: round(ctx["zone"].get(z, {}).get(d, 0.0), 6) for z in analysis["active_zones"]},
               "matched_terms": dict(matched), "reasons": reasons,
               "diversity": {"penalty": round(rank_info.get("penalty", 0.0), 6), "max_similarity": round(rank_info.get("max_sim", 0.0), 6)}}
        if debug:
            out["debug"] = {"term_contributions": contrib}
        return out

    # ------------------------------------------------------------------ public API
    def search(self, query: str, k: int = 10, filters: dict | None = None, cfg: RankingConfig = DEFAULT_CONFIG, sort: str = "best", debug: bool = False) -> dict:
        t0 = time.perf_counter()
        query = (query or "").strip()
        if len(query) > 500:
            raise QueryError("The query is too long (500 characters at most).")
        allowed = self.allowed_docs(filters)
        if not query and allowed is None:
            raise QueryError("Type a job title, skills or a company, or choose a filter.")
        analysis = self.analyze(query, cfg)
        notices = []
        if analysis["unknown"]:
            notices.append({"kind": "unknown_terms", "terms": analysis["unknown"], "suggestions": analysis["suggestions"],
                            "text": "Not found in any listing, so they did not affect ranking: " + ", ".join(analysis["unknown"])})
        if query:
            scored, ctx, stats = self.score_all(analysis, cfg, allowed)
            ranked = self.order(scored, k, cfg)
            results = [self._payload(analysis, ctx, scored[r["doc"]], r["doc"], r, i, cfg, debug) for i, r in enumerate(ranked, 1)]
            if not analysis["active_zones"] and not analysis["flat_vector"]:
                notices.append({"kind": "no_known_terms", "text": "None of your words occur in any listing."})
        else:   # filter-only browsing: newest first, no relevance claim
            ids = sorted(allowed, key=lambda d: (self.jobs[d].posted, -d), reverse=True)[:k]
            results = [{"rank": i, "job": self.jobs[d].to_dict(), "ir_relevance": None, "cosine": None, "jaccard": None, "flat_cosine": None,
                        "zone_scores": {}, "matched_terms": {}, "reasons": ["Shown because it matches your filters (newest first). There is no search query, so no IR relevance."],
                        "diversity": {"penalty": 0.0, "max_similarity": 0.0}} for i, d in enumerate(ids, 1)]
            stats = {"candidates": len(allowed), "documents_never_scored": self.N - len(allowed), "postings_traversed": 0, "zone_candidates": {}}
        if not results:
            notices.append({"kind": "no_results", "text": "No listings matched. Try fewer filters or different words."})
        results = self._sorted(results, sort)
        return {"query": query, "analysis": self.analysis_summary(analysis), "results": results, "notices": notices,
                "stats": {**stats, "N": self.N, "filtered_to": None if allowed is None else len(allowed), "time_ms": round((time.perf_counter() - t0) * 1000, 2)},
                "config": cfg.to_dict()}

    def _sorted(self, results: list[dict], sort: str) -> list[dict]:
        keys = {"best": None, "newest": lambda r: r["job"]["posted"], "company": lambda r: r["job"]["company"].lower(),
                "location": lambda r: (r["job"]["location"] or "~").lower()}
        if sort not in keys:
            raise QueryError(f"Unknown sort '{sort}'. Use one of: {', '.join(keys)}.")
        if keys[sort] is None:
            return results
        return sorted(results, key=keys[sort], reverse=(sort == "newest"))

    def analysis_summary(self, a: dict) -> dict:
        return {"raw": a["raw"], "tokens": a["tokens"], "removed": a["removed"], "stems": a["stems"], "biwords": a["biwords"],
                "query_skills": a["query_skills"], "routing": a["routing"], "active_zones": a["active_zones"], "unknown": a["unknown"],
                "suggestions": a["suggestions"], "terms": a["terms"]}

    def get_job(self, job_id: int) -> Job:
        if not 0 <= job_id < self.N:
            raise KeyError(f"No job with id {job_id} (valid ids: 0 to {self.N - 1}).")
        return self.jobs[job_id]

    def evidence_for(self, job_id: int, query: str, cfg: RankingConfig = DEFAULT_CONFIG) -> dict | None:
        """IR evidence for ONE job against a query (None if they share no term)."""
        self.get_job(job_id)
        if not (query or "").strip():
            return None
        analysis = self.analyze(query, cfg)
        scored, ctx, _ = self.score_all(analysis, cfg, {job_id})
        if job_id not in scored:
            return None
        return self._payload(analysis, ctx, scored[job_id], job_id, {}, None, cfg, True)

    def similar(self, job_id: int, k: int = 6) -> dict:
        """Job-to-job retrieval: the job's own Title and Skills vectors are the query."""
        src = self.get_job(job_id)
        acc: dict[int, float] = defaultdict(float)
        for z, w in (("Title", 0.5), ("Skills", 0.5)):
            vec = self.zone_index[z].doc_vectors[job_id]
            if vec:
                for d, sc in self.zone_index[z].cosine_scores(vec)[0].items():
                    acc[d] += w * sc
        acc.pop(job_id, None)
        out, seen = [], {(src.title.lower(), src.company.lower())}
        src_keys = set(src.skill_keys)
        for d in heapq.nsmallest(k * 6, acc, key=lambda d: (-acc[d], d)):
            j = self.jobs[d]
            sig = (j.title.lower(), j.company.lower())
            if sig in seen:
                continue
            seen.add(sig)
            out.append({"job": j.to_dict(), "similarity": round(acc[d], 6), "shared_skills": [s for s in src.skills if canon(s) in set(j.skill_keys)],
                        "skill_jaccard": round(jaccard(src_keys, set(j.skill_keys)), 4)})
            if len(out) == k:
                break
        return {"source": src.to_dict(), "results": out}

    def retrieve(self, query: str, n: int = 50, filters: dict | None = None, cfg: RankingConfig = DEFAULT_CONFIG):
        """Top-n documents by hybrid IR score WITHOUT the diversity step (used to build target-role requirements)."""
        allowed = self.allowed_docs(filters)
        a = self.analyze(query, cfg)
        scored, ctx, stats = self.score_all(a, cfg, allowed)
        top = heapq.nsmallest(n, scored, key=lambda d: (-scored[d], d))
        return a, [(d, scored[d]) for d in top], ctx, stats

    def title_vector(self, text: str) -> dict[str, float]:
        """TF-IDF (ltc) vector of free text in the Title zone vocabulary; used for role similarity."""
        uni, bi = self._terms(text, True)
        return self.zone_index["Title"].query_vector({t: (c, 1.0) for t, c in Counter(uni + bi).items()})

    # ------------------------------------------------------------------ baselines for evaluation
    def baseline_scores(self, query: str, system: str) -> dict[int, float]:
        stems = normalize_tokens(raw_tokens(query), query=True, stemming=True)
        if system == "keyword":
            q = set(stems)
            return {d: float(len(q & self.term_sets[d])) for d in self.flat_index.candidates(q)}
        if system == "tfidf":
            return self.flat_index.cosine_scores(self.flat_index.query_vector({t: (c, 1.0) for t, c in Counter(stems).items()}))[0]
        if system == "bm25":
            return self.flat_index.bm25_scores(Counter(stems))
        raise ValueError(system)

    def rank_ids(self, query: str, system: str, k: int = 10, seed: int | None = None, cfg: RankingConfig = DEFAULT_CONFIG) -> list[int]:
        if system == "careerlens":
            a = self.analyze(query, cfg)
            scored, _, _ = self.score_all(a, cfg)
            return [r["doc"] for r in self.order(scored, k, cfg, seed)]
        sc = self.baseline_scores(query, system)
        return [d for d in heapq.nsmallest(k, sc, key=lambda d: (-sc[d], self.tiebreak(seed, d))) if sc[d] > 0]

    # ------------------------------------------------------------------ research mode
    def trace(self, query: str, k: int = 8, filters: dict | None = None, cfg: RankingConfig = DEFAULT_CONFIG) -> dict:
        query = (query or "").strip()
        if not query:
            raise QueryError("Research Mode needs a query.")
        allowed = self.allowed_docs(filters)
        a = self.analyze(query, cfg)
        vectors, postings = {}, {}
        for z in ZONES:
            idx = self.zone_index[z]
            vec, rows, norm = idx.query_vector(a["zone_terms"][z], detail=True)
            if rows:
                for r in rows:
                    r["surface"] = r["term"].replace("_", " ") if z == "Skills" else self.display(r["term"])
                vectors[z] = {"rows": rows, "norm": norm, "alpha": cfg.zone_weights.get(z, 0.0)}
                postings[z] = [{"surface": r["surface"], "df": idx.df[r["term"]], "idf": round(idx.idf[r["term"]], 4),
                                "postings": [{"doc": d, "tf": tf} for d, tf in idx.postings[r["term"]][:10]]} for r in rows]
        scored, ctx, stats = self.score_all(a, cfg, allowed)
        ranked = self.order(scored, k, cfg)
        pre = {d: i + 1 for i, d in enumerate(heapq.nsmallest(k * cfg.pool_factor, scored, key=lambda d: (-scored[d], d)))}
        table = []
        for i, r in enumerate(ranked, 1):
            d = r["doc"]
            table.append({"rank": i, "pre_diversity_rank": pre.get(d), "job": self.jobs[d].to_dict(),
                          "zone_scores": {z: ctx["zone"].get(z, {}).get(d, 0.0) for z in a["active_zones"]}, "cosine": ctx["cos"].get(d, 0.0),
                          "jaccard": ctx["jac"].get(d, 0.0), "hybrid": scored[d], "penalty": r.get("penalty", 0.0),
                          "term_contributions": self.contributions(a, d, cfg)[:10]})
        brief = lambda ids: [{"id": d, "title": self.jobs[d].title, "company": self.jobs[d].company, "role_family": self.jobs[d].role_family} for d in ids]
        comparison = {sysname: brief(self.rank_ids(query, sysname, 5, None, cfg)) for sysname in ("keyword", "tfidf", "bm25", "careerlens")}
        flat_rows = self.flat_index.query_vector({t: (c, 1.0) for t, c in Counter(x["stem"] for x in a["stems"]).items()}, detail=True)[1]
        for r in flat_rows:
            r["surface"] = self.display(r["term"])
        return {"query": query, "analysis": self.analysis_summary(a),
                "index": {"N": self.N, "vocabulary": {z: self.zone_index[z].vocabulary_size for z in ZONES}, "flat_vocabulary": self.flat_index.vocabulary_size,
                          "postings": {z: sum(len(p) for p in self.zone_index[z].postings.values()) for z in ZONES}},
                "query_vectors": vectors, "flat_query_vector": {"rows": flat_rows}, "postings": postings,
                "candidates": {"union_of_postings": stats["candidates"], "never_scored": stats["documents_never_scored"],
                               "postings_traversed": stats["postings_traversed"], "per_zone": stats["zone_candidates"],
                               "filtered_to": None if allowed is None else len(allowed)},
                "ranking": table, "comparison": comparison, "config": cfg.to_dict(),
                "formula": "hybrid = (w_cosine * sum_z(alpha_z * cos_z) / sum(alpha of active zones) + w_jaccard * Jaccard) / (w_cosine + w_jaccard)"}
