"""
Diversity-aware re-ranking with Maximal Marginal Relevance (Carbonell &
Goldstein, SIGIR 1998).

Greedy selection from a pool of the most relevant documents. At each step
pick the document d that maximises

    MMR(d) = lambda * rel(d) - (1 - lambda) * max_{s in selected} sim(d, s)

rel(d) is the hybrid relevance score in [0, 1], sim is the Jaccard
coefficient of the two documents' term sets. The subtracted part is the
"redundancy penalty" shown in the UI. lambda = 1 reproduces the pure
relevance ranking exactly.
"""
from __future__ import annotations

from typing import Callable


def mmr_rerank(pool: list[tuple[int, float]], k: int, lam: float,
               sim: Callable[[int, int], float]) -> list[dict]:
    """`pool` is (doc_id, relevance) sorted by relevance (ties already broken).

    Returns dicts: doc, relevance, mmr, penalty, most_similar (doc id or None),
    max_sim. Earlier position in `pool` wins ties, so lam=1 keeps pool order.
    """
    remaining = list(pool)
    selected: list[dict] = []
    while remaining and len(selected) < k:
        best_idx, best = -1, None
        for idx, (doc, rel) in enumerate(remaining):
            max_sim, most_similar = 0.0, None
            for s in selected:
                v = sim(doc, s["doc"])
                if v > max_sim:
                    max_sim, most_similar = v, s["doc"]
            value = lam * rel - (1 - lam) * max_sim
            if best is None or value > best["mmr"] + 1e-12:
                best_idx = idx
                best = {"doc": doc, "relevance": rel, "mmr": value,
                        "penalty": (1 - lam) * max_sim, "max_sim": max_sim,
                        "most_similar": most_similar}
        selected.append(best)
        remaining.pop(best_idx)
    return selected


def bounded_rerank(pool: list[tuple[int, float]], k: int, epsilon: float,
                   sim: Callable[[int, int], float]) -> list[dict]:
    """Relevance-bounded diversification (CareerLens variant).

    At each step, only documents whose relevance is within `epsilon` of the
    best remaining document are eligible; among those, pick the one LEAST
    similar to what is already selected. Guarantee: no selected document is
    more than `epsilon` less relevant than the best one it was preferred to,
    so diversity is only bought inside (near-)ties. With epsilon = 0 it only
    reorders exact ties; this matters here because many listings tie exactly
    (every 'Data Scientist' job scores the same for 'data scientist').
    """
    remaining = list(pool)
    selected: list[dict] = []
    while remaining and len(selected) < k:
        top_rel = max(r for _, r in remaining)
        best_idx, best = -1, None
        for idx, (doc, rel) in enumerate(remaining):
            if rel < top_rel - epsilon - 1e-12:
                continue
            max_sim, most_similar = 0.0, None
            for s in selected:
                v = sim(doc, s["doc"])
                if v > max_sim:
                    max_sim, most_similar = v, s["doc"]
            # least redundant first; then more relevant; then pool order
            key = (max_sim, -rel)
            if best is None or key < best["_key"]:
                best_idx = idx
                best = {"doc": doc, "relevance": rel, "mmr": rel, "max_sim": max_sim,
                        "most_similar": most_similar, "skipped_relevance": top_rel - rel, "_key": key}
        best["penalty"] = best["skipped_relevance"]
        del best["_key"]
        selected.append(best)
        remaining.pop(best_idx)
    return selected
