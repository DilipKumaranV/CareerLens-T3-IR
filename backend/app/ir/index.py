"""
Inverted index (lecture topics: inverted index, tf-idf, vector space model,
efficient cosine scoring).

One `InvertedIndex` is built per zone (Category, Department, ...) plus one
flat index over all fields. Each holds:

  postings[t]          sorted list of (doc_id, tf)       dictionary + postings
  df[t], idf[t]        idf = log10(N / df)
  doc_vectors[d]       ltc document vector: (1 + log10 tf) * idf, cosine-normalised
  weighted_postings[t] (doc_id, normalised weight), used for term-at-a-time scoring

Cosine scoring is TERM-AT-A-TIME with accumulators: only documents that
appear in the postings of a query term are ever touched, which is the
efficient cosine scoring algorithm from the lectures. Documents that share
no term with the query are never scored at all (index elimination).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict


class InvertedIndex:
    def __init__(self, docs: list[list[str]], name: str = ""):
        self.name = name
        self.N = len(docs)
        postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.doc_tf: list[Counter] = []
        self.doc_len: list[int] = []
        for doc_id, terms in enumerate(docs):
            tf = Counter(terms)
            self.doc_tf.append(tf)
            self.doc_len.append(len(terms))
            for term, count in tf.items():
                postings[term].append((doc_id, count))  # doc ids arrive in order -> sorted
        self.postings = dict(postings)
        self.df = {t: len(p) for t, p in self.postings.items()}
        self.idf = {t: math.log10(self.N / df) for t, df in self.df.items()}
        self.avg_len = (sum(self.doc_len) / self.N) if self.N else 1.0
        self.doc_vectors = [self._ltc(tf) for tf in self.doc_tf]
        self.weighted_postings = {
            t: [(d, self.doc_vectors[d].get(t, 0.0)) for d, _ in p] for t, p in self.postings.items()
        }

    # ------------------------------------------------------------------ vectors
    def _ltc(self, tf: Counter) -> dict[str, float]:
        weights = {t: (1 + math.log10(c)) * self.idf[t] for t, c in tf.items()}
        norm = math.sqrt(sum(w * w for w in weights.values()))
        return {t: w / norm for t, w in weights.items()} if norm > 0 else {}

    def query_vector(self, terms: dict[str, tuple[float, float]], detail: bool = False):
        """Build an ltc query vector.

        `terms` maps term -> (tf, boost); boost < 1 for expanded terms.
        Terms not in this index's vocabulary are skipped. With detail=True
        also returns the per-term arithmetic for the research panel.
        """
        raw = {}
        unboosted_sq = 0.0
        rows = []
        for term, (tf, boost) in terms.items():
            if term not in self.idf or tf <= 0:
                continue
            log_tf = 1 + math.log10(tf)
            plain = log_tf * self.idf[term]
            w = plain * boost
            raw[term] = w
            unboosted_sq += plain * plain
            rows.append({"term": term, "tf": tf, "log_tf": log_tf, "idf": self.idf[term],
                         "boost": boost, "weight": w, "df": self.df[term]})
        # Normalise by the length the vector would have WITHOUT boosts. If we normalised by the
        # boosted length, a field whose query terms are all expansions (boost 0.5) would be
        # rescaled back to full strength and the down-weight would silently disappear.
        # With no boosts this is ordinary cosine normalisation; with boosts the vector has
        # length <= 1, so cosine scores stay in [0, 1].
        norm = math.sqrt(unboosted_sq)
        vec = {t: w / norm for t, w in raw.items()} if norm > 0 else {}
        if not detail:
            return vec
        for r in rows:
            r["normalized"] = vec.get(r["term"], 0.0)
        return vec, rows, norm

    # ------------------------------------------------------------------ scoring
    def build_champions(self, r: int) -> None:
        """Champion lists (lecture: scoring and result assembly): for every term with more than
        r postings keep only the r documents where the term has the highest weight."""
        self.champion_r = r
        self.champions = {t: sorted(p, key=lambda x: -x[1])[:r]
                          for t, p in self.weighted_postings.items() if len(p) > r}

    def cosine_scores(self, qvec: dict[str, float], allowed: set[int] | None = None,
                      min_idf_ratio: float | None = None, use_champions: bool = False
                      ) -> tuple[dict[int, float], int]:
        """Term-at-a-time cosine with accumulators.

        Returns (scores, postings_traversed). Only documents in the postings
        of the query terms receive an accumulator.

        Optional approximations (both off by default, so scores are exact):
          min_idf_ratio  index elimination: skip query terms whose idf is below
                         ratio x the highest idf among the query terms
          use_champions  read only each term's champion list (build_champions first)
        """
        acc: dict[int, float] = defaultdict(float)
        traversed = 0
        items = [(t, w) for t, w in qvec.items() if w != 0]
        if min_idf_ratio and items:
            top = max(self.idf.get(t, 0.0) for t, _ in items)
            kept = [(t, w) for t, w in items if self.idf.get(t, 0.0) >= min_idf_ratio * top]
            items = kept or items
        champions = getattr(self, "champions", None) if use_champions else None
        for term, wq in items:
            plist = champions[term] if champions and term in champions else self.weighted_postings.get(term, ())
            for doc_id, wd in plist:
                traversed += 1
                if allowed is not None and doc_id not in allowed:
                    continue
                acc[doc_id] += wq * wd
        return dict(acc), traversed

    def bm25_scores(self, terms: Counter, k1: float = 1.2, b: float = 0.75) -> dict[int, float]:
        """Okapi BM25 (outside the syllabus; used as an extra comparison system)."""
        scores: dict[int, float] = defaultdict(float)
        for term in terms:
            if term not in self.postings:
                continue
            df = self.df[term]
            idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1)
            for doc_id, tf in self.postings[term]:
                norm = k1 * (1 - b + b * self.doc_len[doc_id] / self.avg_len)
                scores[doc_id] += idf * tf * (k1 + 1) / (tf + norm)
        return dict(scores)

    def candidates(self, terms) -> set[int]:
        """Union of the postings lists of the given terms."""
        out: set[int] = set()
        for t in terms:
            out.update(d for d, _ in self.postings.get(t, ()))
        return out

    @property
    def vocabulary_size(self) -> int:
        return len(self.postings)
