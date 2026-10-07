"""
Near-duplicate detection (lecture topic: Jaccard coefficient; the
"content seen?" idea from web crawling).

Exact duplicates are already merged in corpus.py. Here we find listings that
are NEARLY the same: two documents are near-duplicates when the Jaccard
coefficient of their term sets is >= a threshold (default 0.8). Groups are
formed with union-find (transitive closure). Groups are reported and used to
explain the diversity re-ranking; no document is removed.

Candidate pairs come from the inverted index (two documents can only have
Jaccard > 0 if they share a term), so we never compare documents that share
nothing. With ~700 documents the remaining comparisons are cheap.
"""
from __future__ import annotations


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def near_duplicate_groups(term_sets: list[set[str]], threshold: float) -> tuple[list[list[int]], dict[int, int], int]:
    """Return (groups of size >= 2, doc -> group index, pairs compared)."""
    n = len(term_sets)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    # Candidate generation through a term -> docs map
    postings: dict[str, list[int]] = {}
    for d, terms in enumerate(term_sets):
        for t in terms:
            postings.setdefault(t, []).append(d)

    compared = 0
    for i in range(n):
        if not term_sets[i]:
            continue
        cands = set()
        for t in term_sets[i]:
            cands.update(j for j in postings[t] if j > i)
        for j in cands:
            # Jaccard >= threshold is impossible when set sizes differ too much
            small, big = sorted((len(term_sets[i]), len(term_sets[j])))
            if small / big < threshold:
                continue
            compared += 1
            if jaccard(term_sets[i], term_sets[j]) >= threshold:
                parent[find(i)] = find(j)

    groups: dict[int, list[int]] = {}
    for d in range(n):
        groups.setdefault(find(d), []).append(d)
    multi = [sorted(g) for g in groups.values() if len(g) > 1]
    multi.sort(key=lambda g: (-len(g), g[0]))
    member_of = {d: gi for gi, g in enumerate(multi) for d in g}
    return multi, member_of, compared
