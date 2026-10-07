"""Classical IR components on the real working corpus: preprocessing, index, TF-IDF, cosine, Jaccard, ranking, filtering."""
import math

import pytest

from app.config import DEFAULT_CONFIG
from app.ir.dedup import jaccard
from app.ir.index import InvertedIndex
from app.ir.jobs import QueryError
from app.ir.preprocess import normalize_tokens, raw_tokens


def test_preprocessing_folds_accents_keeps_acronyms_and_drops_stop_words():
    assert raw_tokens("Wrocław") == ["Wroclaw"]
    assert normalize_tokens(raw_tokens("IT Support"), stemming=False) == ["it", "support"]
    assert normalize_tokens(raw_tokens("the data analyst in Berlin"), query=True, stemming=False) == ["data", "analyst", "berlin"]


def test_inverted_index_postings_df_idf_and_unit_vectors():
    idx = InvertedIndex([["a", "b"], ["a"], ["c", "c"]])
    assert idx.postings["a"] == [(0, 1), (1, 1)] and idx.postings["c"] == [(2, 2)]
    assert idx.df == {"a": 2, "b": 1, "c": 1} and math.isclose(idx.idf["b"], math.log10(3))
    for v in idx.doc_vectors:
        assert math.isclose(sum(w * w for w in v.values()), 1.0)
    assert math.isclose(idx.doc_vectors[2]["c"], 1.0)           # ltc: (1 + log10 2) * idf, then normalised


def test_term_at_a_time_cosine_equals_brute_force(engine):
    idx = engine.zone_index["Title"]
    q = idx.query_vector({"data": (1, 1.0), "analyst": (1, 1.0)})
    taat, _ = idx.cosine_scores(q)
    for d in list(taat)[:300]:
        assert math.isclose(taat[d], sum(w * idx.doc_vectors[d].get(t, 0.0) for t, w in q.items()), abs_tol=1e-12)


def test_jaccard_definition():
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3 and jaccard(set(), set()) == 0.0


def test_ranking_returns_relevant_titles_with_exact_explanations(engine):
    r = engine.search("cloud architect", k=10, debug=True)
    assert len(r["results"]) == 10
    top = r["results"][0]
    assert "cloud" in top["job"]["title"].lower() and "architect" in top["job"]["title"].lower()
    assert top["ir_relevance"] > 0.7          # an exact title match must not be diluted by unrelated zones (zone routing)
    for x in r["results"]:
        assert math.isclose(sum(c["contribution"] for c in x["debug"]["term_contributions"]), x["cosine"], abs_tol=1e-5)
        assert 0 <= x["ir_relevance"] <= 1
    scores = [x["ir_relevance"] for x in r["results"]]
    assert scores == sorted(scores, reverse=True)


def test_skills_named_in_the_query_are_detected_but_are_not_user_skills(engine):
    a = engine.analyze("cloud architect aws terraform dax", DEFAULT_CONFIG)
    assert {"aws", "terraform", "dax"} <= set(a["query_skills"])        # "dax" is a skill in the job data
    assert not hasattr(engine, "profile")                                # the engine has no notion of a user


def test_company_filter_is_case_insensitive_and_exact(engine):
    r = engine.search("data engineer", k=20, filters={"company": ["microsoft"]})
    assert r["results"] and all(x["job"]["company"] == "Microsoft" for x in r["results"])
    with pytest.raises(QueryError) as e:
        engine.search("data engineer", filters={"company": ["Microsft"]})
    assert "Microsoft" in str(e.value)                                   # offers the close spelling, does not guess


def test_filters_combine_with_ranking(engine):
    r = engine.search("data analyst", k=20, filters={"country": ["Germany"], "workplace": ["Remote"]})
    assert all(x["job"]["country"] == "Germany" and x["job"]["workplace"] == "Remote" for x in r["results"])


def test_invalid_input_and_no_results(engine):
    with pytest.raises(QueryError):
        engine.search("", k=5)
    with pytest.raises(QueryError):
        engine.search("data", filters={"planet": ["Mars"]})
    r = engine.search("zzxqv qqwwp", k=5)
    assert r["results"] == [] and any(n["kind"] in ("no_results", "no_known_terms", "unknown_terms") for n in r["notices"])


def test_unknown_word_is_reported_not_silently_dropped(engine):
    r = engine.search("pythn developer", k=3)
    assert "pythn" in r["analysis"]["unknown"] and "python" in r["analysis"]["suggestions"]["pythn"]


def test_similar_jobs_exclude_self_and_are_sorted(engine):
    jid = engine.search("cloud architect", k=1)["results"][0]["job"]["id"]
    sims = engine.similar(jid, 6)["results"]
    assert sims and all(s["job"]["id"] != jid for s in sims)
    assert [s["similarity"] for s in sims] == sorted((s["similarity"] for s in sims), reverse=True)


def test_reposts_are_merged_into_listings(engine):
    assert any(j.listings > 1 for j in engine.jobs)
    keys = [(j.title.lower(), j.company.lower(), (j.location or "").lower()) for j in engine.jobs]
    assert len(keys) == len(set(keys))


def test_no_description_experience_or_url_is_invented(engine):
    d = engine.jobs[0].to_dict()
    assert not {"description", "experience", "url"} & set(d)


def _score(engine, query, doc):
    a = engine.analyze(query)
    scored, _, _ = engine.score_all(a, DEFAULT_CONFIG, {doc})
    return scored.get(doc, 0.0)


def test_work_type_field_lifts_remote_and_contract_listings_with_the_same_title(engine):
    # Same title, different work type: the one that matches the work type in the query must score higher.
    def pick(title, pred):
        return next(j.id for j in engine.jobs if j.title.lower().strip() == title and pred(j))
    rem, onsite = pick("data analyst", lambda j: j.workplace == "Remote"), pick("data analyst", lambda j: j.workplace != "Remote")
    assert "WorkType" in engine.analyze("remote data analyst")["active_zones"]
    assert _score(engine, "remote data analyst", rem) > _score(engine, "remote data analyst", onsite)
    con, ft = pick("data engineer", lambda j: j.schedule == "Contractor"), pick("data engineer", lambda j: j.schedule == "Full-time")
    assert _score(engine, "contractor data engineer", con) > _score(engine, "contractor data engineer", ft)


def test_evidence_exposes_tf_df_idf_tfidf_cosine_and_jaccard(engine):
    r = engine.search("cloud architect aws", k=3, debug=True)
    x = r["results"][0]
    c = x["debug"]["term_contributions"][0]
    assert {"doc_tf", "df", "idf", "doc_tfidf", "doc_weight", "query_weight", "contribution"} <= set(c)
    assert c["doc_tf"] >= 1 and c["df"] >= 1 and math.isclose(c["idf"], math.log10(engine.N / c["df"]) if c["zone"] != "Skills" else c["idf"]) and x["jaccard"] is not None


def test_persisted_index_gives_identical_results(engine):
    from app.ir.jobs import JobSearchEngine
    other = JobSearchEngine(use_cache=True)             # loads the cache written at start-up
    assert other.cache_status.startswith("loaded") or other.cache_status.startswith("built")
    a = [(x["job"]["id"], x["ir_relevance"]) for x in engine.search("cloud architect aws", k=10)["results"]]
    b = [(x["job"]["id"], x["ir_relevance"]) for x in other.search("cloud architect aws", k=10)["results"]]
    assert a == b
