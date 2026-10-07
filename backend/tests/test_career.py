"""Career Fit, skill gap and transition: the rules that must never break."""
import pytest

from app import career
from app.ir.jobs import QueryError
from app.profile import service
from app.profile.skills import covers

MSG = "Personalized Career Fit unavailable. Upload your resume or enter your skills."


def resume_profile(engine, key):
    ext = service.analyze_demo(key, engine.vocab)          # the same pipeline as a real upload
    return career.normalize_profile({**ext["profile"], "skills": [s["name"] for s in ext["profile"]["skills"]]}, engine.vocab)


# ---------------------------------------------------------------- CRITICAL: no profile
def test_no_profile_means_no_career_fit_and_no_personal_claims(engine):
    r = engine.search("Cloud Architect", k=10)
    status = career.attach_fit(engine, None, r["results"])
    assert status == {"available": False, "message": MSG}
    assert all(x["career_fit"] is None for x in r["results"])
    assert "you already" not in str(r).lower() and "covered" not in str(r).lower()


def test_empty_profile_counts_as_no_profile(engine):
    empty = career.normalize_profile({"skills": [], "current_role": ""}, engine.vocab)
    assert not career.has_profile(empty)
    assert career.attach_fit(engine, empty, engine.search("data analyst", k=3)["results"])["available"] is False


def test_search_terms_never_become_user_skills(engine):
    # The user searched "cloud architect aws terraform" but has not said they know anything.
    r = engine.search("cloud architect aws terraform", k=5)
    career.attach_fit(engine, None, r["results"])
    assert all(x["career_fit"] is None for x in r["results"])
    # And a profile that does not list aws/terraform gets no credit for them just because they were searched.
    p = career.normalize_profile({"skills": ["excel"], "current_role": "HR Executive"}, engine.vocab)
    fit = career.job_fit(engine, p, engine.get_job(r["results"][0]["job"]["id"]))
    assert not {c["key"] for c in fit["covered"]} & {"aws", "terraform"}


# ---------------------------------------------------------------- CRITICAL: manual profile and resume profile personalise
def test_manual_profile_produces_personalized_results(engine):
    p = career.normalize_profile({"current_role": "System Administrator", "department": "IT Infrastructure", "experience_years": 4,
                                  "skills": ["AWS", "Linux", "Networking", "Python"]}, engine.vocab)
    r = engine.search("Cloud Architect", k=5)
    assert career.attach_fit(engine, p, r["results"])["available"]
    fits = [x["career_fit"] for x in r["results"]]
    assert all(f and f["career_fit"] is not None for f in fits)
    assert any(f["covered"] for f in fits) and any(f["missing"] for f in fits)
    assert "experience" in " ".join(fits[0]["not_available"])


def test_resume_profile_produces_personalized_results_and_ordered_matches(engine):
    scores = {}
    for key in ("strong", "partial", "weak"):
        prof = resume_profile(engine, key)
        t = career.analyze_transition(engine, engine.vocab, prof, "Cloud Architect")
        scores[key] = t["career_fit"]
        assert t["recommended_jobs"] and t["to_develop"] is not None
    assert scores["strong"] > scores["partial"] > scores["weak"]          # computed, never hard-coded
    assert scores["weak"] <= 0.15


def test_same_target_different_profiles_give_different_gaps(engine):
    a = career.analyze_transition(engine, engine.vocab, resume_profile(engine, "strong"), "Cloud Architect")
    b = career.analyze_transition(engine, engine.vocab, resume_profile(engine, "weak"), "Cloud Architect")
    assert len(a["to_develop"]) < len(b["to_develop"]) and {s["key"] for s in a["have"]} > {s["key"] for s in b["have"]}


# ---------------------------------------------------------------- unknown skills, requirements, targets
def test_unknown_skills_are_kept_and_custom_phrases_can_cover_dataset_skills(engine):
    p = career.normalize_profile({"skills": ["SQL", "PowerBI", "Cloud Architecture", "Quantum Basket Weaving", "AWS cloud infrastructure"]}, engine.vocab)
    by = {s["name"]: s for s in p["skills"]}
    assert by["Quantum Basket Weaving"]["status"] == "custom" and by["Cloud Architecture"]["status"] == "custom"
    assert by["SQL"]["status"] == "dataset" and by["PowerBI"]["key"] == "power bi"
    assert covers("aws cloud infrastructure", "aws")


def test_requirements_come_from_retrieved_postings(engine):
    req = career.target_requirements(engine, engine.vocab, "Cloud Architect")
    assert req["jobs_used"] >= career.MIN_JOBS and req["skills"]
    used = {k for d in req["jobs"] for k in engine.jobs[d].skill_keys}
    assert all(s["key"] in used and 0 < s["prevalence"] <= 1 for s in req["skills"])
    assert req["skills"] == sorted(req["skills"], key=lambda s: (-s["prevalence"], s["key"]))


def test_unavailable_target_role_is_a_clear_error(engine):
    p = career.normalize_profile({"skills": ["python"]}, engine.vocab)
    with pytest.raises(QueryError) as e:
        career.analyze_transition(engine, engine.vocab, p, "Zzxqv Qqwwp")
    assert "No postings" in str(e.value)
    with pytest.raises(QueryError):
        career.analyze_transition(engine, engine.vocab, p, "")


def test_transition_requires_a_profile(engine):
    with pytest.raises(QueryError) as e:
        career.analyze_transition(engine, engine.vocab, career.normalize_profile({}, engine.vocab), "Cloud Architect")
    assert str(e.value) == MSG


# ---------------------------------------------------------------- company targeting
def test_company_not_in_dataset_is_reported_not_invented(engine):
    p = resume_profile(engine, "partial")
    t = career.analyze_transition(engine, engine.vocab, p, "Cloud Architect", "Microsft")
    assert t["company_status"]["status"] == "not_in_dataset" and "Microsoft" in t["company_status"]["suggestions"]
    assert t["target"]["company"] is None and t["recommended_jobs"]


def test_company_without_the_role_does_not_claim_it_offers_it(engine):
    p = resume_profile(engine, "partial")
    t = career.analyze_transition(engine, engine.vocab, p, "Cloud Architect", "Microsoft")
    assert t["company_status"]["status"] == "found" and t["company_status"].get("role_present") is False
    assert t["target"]["requirement_scope"] == "all companies" and t["closest_at_company"]
    assert all(r["job"]["company"] == "Microsoft" for r in t["closest_at_company"])
    assert any("none has a title matching" in n for n in t["notes"])


def test_company_with_the_role_scopes_requirements_to_that_company(engine):
    p = resume_profile(engine, "strong")
    t = career.analyze_transition(engine, engine.vocab, p, "Cloud Architect", "Nordcloud Finland")
    assert t["target"]["requirement_scope"] == "Nordcloud Finland"
    assert all(r["job"]["company"] == "Nordcloud Finland" for r in t["recommended_jobs"])


def test_unknown_words_in_the_target_role_are_reported(engine):
    p = career.normalize_profile({"skills": ["python"]}, engine.vocab)
    r = career.analyze_transition(engine, engine.vocab, p, "Zzxqv Cloud Architect")
    assert any("zzxqv" in n.lower() and "did not affect" in n for n in r["notes"])
