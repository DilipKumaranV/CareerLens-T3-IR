"""HTTP API behaviour, including upload errors."""
import io
from pathlib import Path

DEMO = Path(__file__).resolve().parents[2] / "docs" / "demo-resumes"
MSG = "Personalized Career Fit unavailable. Upload your resume or enter your skills."


def test_health_and_meta(client):
    assert client.get("/api/health").json()["status"] == "ok"
    m = client.get("/api/meta").json()
    assert m["listings"] > 50000 and m["dataset"]["license"].startswith("Apache-2.0") and m["dataset"]["source_url"].startswith("https://huggingface.co/")
    assert set(m["zones"]) == {"Title", "Skills", "Location", "Company", "WorkType"}


def test_search_without_profile_has_no_personalization(client):
    r = client.post("/api/search", json={"query": "Cloud Architect", "k": 5}).json()
    assert r["personalization"] == {"available": False, "message": MSG}
    assert all(x["career_fit"] is None and x["ir_relevance"] is not None for x in r["results"])


def test_search_with_profile_adds_career_fit(client):
    prof = {"current_role": "System Administrator", "skills": ["AWS", "Linux", "Python"]}
    r = client.post("/api/search", json={"query": "Cloud Architect", "k": 5, "profile": prof}).json()
    assert r["personalization"]["available"] and all(x["career_fit"]["career_fit"] is not None for x in r["results"])
    same = client.post("/api/search", json={"query": "Cloud Architect", "k": 5}).json()
    assert [x["job"]["id"] for x in r["results"]] == [x["job"]["id"] for x in same["results"]]      # the profile never changes retrieval


def test_search_errors(client):
    assert client.post("/api/search", json={"query": ""}).status_code == 422
    assert client.post("/api/search", json={"query": "x", "k": 999}).status_code == 422
    assert client.post("/api/search", json={"query": "data", "filters": {"company": ["Nonexistent Corp"]}}).status_code == 422
    assert client.post("/api/search", json={"query": "zzxqv"}).json()["results"] == []


def test_job_detail_and_explain(client):
    jid = client.post("/api/search", json={"query": "cloud architect", "k": 1}).json()["results"][0]["job"]["id"]
    d = client.get(f"/api/jobs/{jid}", params={"q": "cloud architect"}).json()
    assert d["ir_evidence"]["zone_scores"] and d["similar"]
    e = client.post(f"/api/jobs/{jid}/explain", json={"query": "cloud architect", "profile": {"skills": ["python"]}}).json()
    assert e["career_fit"]["career_fit"] is not None and e["preparation"]
    n = client.post(f"/api/jobs/{jid}/explain", json={"query": "cloud architect"}).json()
    assert n["career_fit"] is None and n["preparation"] == [] and n["personalization"]["message"] == MSG
    assert client.get("/api/jobs/99999999").status_code == 404


def test_resume_upload_pipeline_and_demo_match(client):
    data = (DEMO / "strong-cloud-architect-match.pdf").read_bytes()
    up = client.post("/api/resume/analyze", files={"file": ("strong.pdf", data, "application/pdf")}).json()
    demo = client.post("/api/resume/demo/strong").json()
    assert up["profile"] == demo["profile"] and up["confirmation_required"] and demo["demo"] == "strong"
    assert up["profile"]["current_role"] == "Senior Cloud Engineer" and any(s["status"] == "custom" for s in up["profile"]["skills"])
    assert client.get("/api/resume/demos").json()["demos"] and client.post("/api/resume/demo/nobody").status_code == 404


def test_invalid_pdfs_give_clear_errors(client):
    for name, data, code in [("a.pdf", b"", "empty_file"), ("b.pdf", b"not a pdf", "not_pdf"), ("c.pdf", b"%PDF-1.4 junk junk", "unreadable")]:
        r = client.post("/api/resume/analyze", files={"file": (name, data, "application/pdf")})
        assert r.status_code == 422 and r.json()["code"] == code and r.json()["detail"]
    r = client.post("/api/resume/analyze", files={"file": ("cv.docx", b"x", "application/msword")})
    assert r.status_code == 422 and r.json()["code"] == "not_pdf"


def test_profile_normalisation_keeps_unknown_skills(client):
    r = client.post("/api/profile", json={"skills": ["SQL", "PowerBI", "Snowpark Wizardry"]}).json()
    assert [s["status"] for s in r["profile"]["skills"]] == ["dataset", "dataset", "custom"] and r["usable"]
    assert client.post("/api/profile", json={"skills": []}).json()["usable"] is False


def test_career_transition_endpoint(client):
    body = {"profile": {"current_role": "System Administrator", "department": "IT Infrastructure", "experience_years": 4,
                        "skills": ["AWS", "Linux", "Networking", "Python"]}, "target_role": "Cloud Architect"}
    t = client.post("/api/career-transition", json=body).json()
    assert 0 < t["career_fit"] < 1 and t["career_fit"] == t["profile_match"] and t["have"] and t["to_develop"] and t["preparation_plan"] and t["recommended_jobs"]
    assert {s["key"] for s in t["have"]} >= {"aws", "linux"} and "networking" in {s["key"] for s in t["other_skills"]}
    assert client.post("/api/career-transition", json={**body, "profile": {"skills": []}}).status_code == 422
    assert client.post("/api/career-transition", json={**body, "target_role": "Zzxqv Qqwwp"}).status_code == 422


def test_companies_and_skill_suggestions(client):
    assert any(c["company"] == "Microsoft" for c in client.get("/api/companies", params={"q": "micros"}).json()["companies"])
    assert client.get("/api/skills/suggest", params={"q": "terra"}).json()["skills"][0]["name"] == "Terraform"


def test_research_trace_and_analytics(client):
    t = client.post("/api/research/trace", json={"query": "cloud architect aws"}).json()
    assert t["query_vectors"] and t["postings"] and t["ranking"] and set(t["comparison"]) == {"keyword", "tfidf", "bm25", "careerlens"}
    assert client.get("/api/analytics").json()["totals"]["listings"] > 50000


def test_evaluation_endpoint_and_definitions(client):
    ev = client.get("/api/evaluation").json()
    assert {"P@K", "R@K"} <= set(ev["explanations"]) and set(ev["systems"]) == {"keyword", "tfidf", "tfidf_jaccard", "bm25", "careerlens"}
    assert ev["splits"]["test"] > 0 and len(ev["queries"]) == ev["setup"]["queries"]
    assert all(0 <= v <= 1 for s in ev["systems"].values() for v in s["mean"].values())
