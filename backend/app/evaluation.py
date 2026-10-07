"""
Offline IR evaluation of CareerLens against baselines (this is evaluation of RETRIEVAL, not of anyone's career).

Relevance: rules in evaluation/judged_queries.json (see its description). They are fixed before systems are compared.
Systems  : keyword overlap, flat TF-IDF cosine, flat TF-IDF + Jaccard, BM25 (outside the syllabus), CareerLens hybrid (zones + routing + Jaccard).
Metrics  : Precision@K, Recall@K, Average Precision@K, nDCG@10, MRR, K = 5 and 10.
Ties     : listings often have identical scores. Every system breaks ties randomly and metrics are averaged over N_SEEDS fixed seeds,
           so no system benefits from file order.
Recall   : divided by ALL relevant listings, so for a query with 9,589 relevant listings Recall@5 cannot exceed 5/9,589. The
           ceiling min(K, |relevant|)/|relevant| is reported next to it.
"""
from __future__ import annotations

import json
import math
import random
import statistics
import time
from datetime import datetime, timezone

from .config import DEFAULT_CONFIG, EVAL_RESULTS_PATH, EVAL_DIR, ZONES
from .ir.jobs import JobSearchEngine
from .profile.skills import canon

N_SEEDS = 10
QUERIES_PATH = EVAL_DIR / "judged_queries.json"
SYSTEMS = [("keyword", "Keyword baseline"), ("tfidf", "TF-IDF (flat)"), ("tfidf_jaccard", "TF-IDF + Jaccard (flat)"), ("bm25", "BM25 (extra)"), ("careerlens", "Hybrid CareerLens")]


def rule_ok(job, rules: dict) -> bool:
    for k, v in (rules or {}).items():
        if k == "role_family" and job.role_family not in v:
            return False
        if k == "country" and job.country not in v:
            return False
        if k == "company" and job.company.lower() not in [x.lower() for x in v]:
            return False
        if k == "skills_all" and not all(canon(s) in job.skill_keys for s in v):
            return False
        if k == "skills_any" and not any(canon(s) in job.skill_keys for s in v):
            return False
    return True


def grades_for(engine: JobSearchEngine, q: dict) -> dict[int, int]:
    out = {}
    for j in engine.jobs:
        if rule_ok(j, q["must"]):
            out[j.id] = 2 if rule_ok(j, q.get("should")) else 1
    return out


def metrics(ranked: list[int], grades: dict[int, int]) -> dict:
    rel = {d for d, g in grades.items() if g == 2}
    nrel = len(rel)
    m = {}
    for K in (5, 10):
        top = ranked[:K]
        hits = [1 if d in rel else 0 for d in top]
        m[f"P@{K}"] = sum(hits) / K
        m[f"R@{K}"] = sum(hits) / nrel if nrel else 0.0
        ap, seen = 0.0, 0
        for i, h in enumerate(hits, 1):
            if h:
                seen += 1
                ap += seen / i
        m[f"AP@{K}"] = ap / min(nrel, K) if nrel else 0.0
    top = ranked[:10]
    dcg = sum((2 ** grades.get(d, 0) - 1) / math.log2(i + 1) for i, d in enumerate(top, 1))
    ideal = sorted(grades.values(), reverse=True)[:10]
    idcg = sum((2 ** g - 1) / math.log2(i + 1) for i, g in enumerate(ideal, 1))
    m["nDCG@10"] = dcg / idcg if idcg else 0.0
    m["MRR"] = next((1 / i for i, d in enumerate(top, 1) if d in rel), 0.0)
    return m


METRICS = ["P@5", "R@5", "AP@5", "P@10", "R@10", "AP@10", "nDCG@10", "MRR"]


def rankings(engine, query, system, cfg, K=10):
    """One ranking per tie-break seed, scoring each query only once."""
    import heapq
    if system == "tfidf_jaccard":                      # flat bag of words, cosine + Jaccard, no zones
        system, cfg = "careerlens", cfg.with_overrides(use_zones=False, diversity=False)
    if system == "careerlens":
        a = engine.analyze(query, cfg)
        scored, _, _ = engine.score_all(a, cfg)
        return [[r["doc"] for r in engine.order(scored, K, cfg, seed)] for seed in range(N_SEEDS)]
    sc = engine.baseline_scores(query, system)
    return [[d for d in heapq.nsmallest(K, sc, key=lambda d: (-sc[d], engine.tiebreak(seed, d))) if sc[d] > 0] for seed in range(N_SEEDS)]


def evaluate(engine, queries, gradesets, system, cfg=DEFAULT_CONFIG):
    per, shown = [], []
    for q, g in zip(queries, gradesets):
        runs = rankings(engine, q["query"], system, cfg)
        ms = [metrics(r, g) for r in runs]
        per.append({m: statistics.mean(x[m] for x in ms) for m in METRICS})
        shown.append(runs[0][:5])          # the actual top 5 of the first seed, for the per-query table
    return {"mean": {m: statistics.mean(p[m] for p in per) for m in METRICS}, "per_query": per, "top5": shown}


def sign_flip_p(a, b, trials=10000, seed=7):
    diffs = [x - y for x, y in zip(a, b)]
    obs = abs(statistics.mean(diffs))
    if obs == 0:
        return 1.0
    rng = random.Random(seed)
    hits = sum(1 for _ in range(trials) if abs(statistics.mean(d if rng.random() < .5 else -d for d in diffs)) >= obs - 1e-12)
    return (hits + 1) / (trials + 1)


def run(engine: JobSearchEngine) -> dict:
    t0 = time.perf_counter()
    spec = json.loads(QUERIES_PATH.read_text())
    queries = spec["queries"]
    grades = [grades_for(engine, q) for q in queries]
    res = {s: evaluate(engine, queries, grades, s) for s, _ in SYSTEMS}
    split_idx = {"all": list(range(len(queries))), "dev": [i for i, q in enumerate(queries) if q.get("split") == "dev"],
                 "test": [i for i, q in enumerate(queries) if q.get("split") == "test"]}
    agg = lambda per, idx: {m: statistics.mean(per[i][m] for i in idx) for m in METRICS}
    base = DEFAULT_CONFIG
    ablations = [("no_routing", "without zone routing", base.with_overrides(use_routing=False)),
                 ("no_jaccard", "without Jaccard", base.with_overrides(w_jaccard=0.0)),
                 ("no_worktype", "without the Work type field", base.with_overrides(zone_weights={"WorkType": 0.0})),
                 ("no_diversity", "without diversity step", base.with_overrides(diversity=False))]
    abl = []
    for key, label, cfg in ablations:
        r = evaluate(engine, queries, grades, "careerlens", cfg)
        t = agg(r["per_query"], split_idx["test"])
        abl.append({"key": key, "label": label, "mean": r["mean"], "test": t,
                    "delta": {m: r["mean"][m] - res["careerlens"]["mean"][m] for m in METRICS},
                    "delta_test": {m: t[m] - agg(res["careerlens"]["per_query"], split_idx["test"])[m] for m in METRICS}})

    def job_brief(d, g):
        j = engine.jobs[d]
        return {"id": d, "title": j.title, "company": j.company, "role_family": j.role_family, "country": j.country, "relevant": g.get(d, 0) == 2}
    qrows = []
    for i, (q, g) in enumerate(zip(queries, grades)):
        nrel = sum(1 for v in g.values() if v == 2)
        row = {"id": q["id"], "query": q["query"], "type": q["type"], "split": q.get("split"), "relevant": nrel, "partial": sum(1 for v in g.values() if v == 1),
               "recall_ceiling_5": round(min(5, nrel) / nrel, 6) if nrel else 0.0}
        for s, _ in SYSTEMS:
            row[s] = {**{m: res[s]["per_query"][i][m] for m in METRICS}, "top5": [job_brief(d, g) for d in res[s]["top5"][i]]}
        qrows.append(row)
    by_type = {}
    for t in dict.fromkeys(q["type"] for q in queries):
        idx = [i for i, q in enumerate(queries) if q["type"] == t]
        by_type[t] = {"queries": len(idx), **{s: {m: statistics.mean(res[s]["per_query"][i][m] for i in idx) for m in ("P@5", "R@5", "AP@5", "nDCG@10")} for s, _ in SYSTEMS}}
    sig = []
    for other in ("keyword", "tfidf", "bm25"):
        for m in ("P@5", "AP@5", "nDCG@10"):
            for sp in ("test", "all"):
                a = [res["careerlens"]["per_query"][i][m] for i in split_idx[sp]]
                b = [res[other]["per_query"][i][m] for i in split_idx[sp]]
                sig.append({"vs": other, "metric": m, "split": sp, "careerlens": statistics.mean(a), "other": statistics.mean(b), "p_value": sign_flip_p(a, b)})
    # zone-weight sensitivity (Title weight, other weights rescaled)
    sens = []
    others = {z: w for z, w in DEFAULT_CONFIG.zone_weights.items() if z != "Title"}
    rest = sum(others.values())
    for a in (0.2, 0.3, 0.45, 0.6, 0.75):
        zw = {"Title": a, **{z: w / rest * (1 - a) for z, w in others.items()}}
        r = evaluate(engine, queries, grades, "careerlens", base.with_overrides(zone_weights=zw))
        sens.append({"title_weight": a, **{m: r["mean"][m] for m in ("P@5", "AP@5", "nDCG@10")}})
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "runtime_s": round(time.perf_counter() - t0, 1),
            "setup": {"queries": len(queries), "listings": engine.N, "seeds": N_SEEDS, "relevance": spec["description"], "config": DEFAULT_CONFIG.to_dict(),
                      "systems": {s: l for s, l in SYSTEMS}},
            "explanations": {"P@K": "Precision@K: of the top K retrieved listings, how many are relevant? (relevant in top K / K)",
                             "R@K": "Recall@K: of ALL relevant listings, how many were retrieved in the top K? (relevant in top K / all relevant). It is small when there are thousands of relevant listings, so the recall ceiling is shown.",
                             "AP@K": "Average Precision@K: rewards putting relevant listings early; the mean of Precision at each rank where a relevant listing appears, divided by min(K, all relevant)."},
            "splits": {k: len(v) for k, v in split_idx.items()},
            "systems": {s: {"label": l, "mean": res[s]["mean"], "by_split": {k: agg(res[s]["per_query"], v) for k, v in split_idx.items()}} for s, l in SYSTEMS},
            "ablations": abl, "by_type": by_type,
            "significance": sig, "sensitivity": sens, "queries": qrows}


def run_and_save(engine: JobSearchEngine) -> dict:
    out = run(engine)
    EVAL_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVAL_RESULTS_PATH.write_text(json.dumps(out, indent=1))
    return out
