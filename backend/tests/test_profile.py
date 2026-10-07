"""Skill vocabulary and resume pipeline tests. The PDFs are the real demo resumes in docs/demo-resumes/."""
import io
from datetime import date
from pathlib import Path

import pytest

from app.profile.resume import ResumeError, extract_pdf_text, parse_resume
from app.profile.skills import SkillVocabulary, canon, covers

DEMO = Path(__file__).resolve().parents[2] / "docs" / "demo-resumes"
V = SkillVocabulary.load()


def profile_of(name):
    text, _ = extract_pdf_text((DEMO / name).read_bytes())
    return parse_resume(text, V)


def keys(profile, status=None):
    return {s["key"] for s in profile["skills"] if status is None or s["status"] == status}


# ---------------------------------------------------------------- skills
def test_normalisation_variants_share_one_key():
    assert canon("PowerBI") == canon("Power-BI") == canon("power bi") == "power bi"
    assert canon("Amazon Web Services") == "aws" and canon("K8s") == "kubernetes"


def test_unknown_skills_are_kept_not_discarded():
    # v3 printed "Not in the ESCO vocabulary, so ignored: sql, powerbi". That must never happen again.
    sk = V.from_list(["SQL", "PowerBI", "Cloud Architecture", "Snowpark Wizardry"])
    by = {s.name: s for s in sk}
    assert by["SQL"].status == "dataset" and by["PowerBI"].status == "dataset"
    assert by["Cloud Architecture"].status == "custom" and by["Snowpark Wizardry"].status == "custom"
    assert len(sk) == 4


def test_ambiguous_words_do_not_create_skills_in_running_text():
    assert not V.extract("Please go to the word processor and take the lead")
    assert {s.key for s in V.extract("Wrote Python and used Amazon Web Services")} == {"python", "aws"}


def test_skill_phrase_covers_job_skill():
    assert covers("aws cloud infrastructure", "aws") and covers("sql server", "sql")
    assert not covers("python", "r") and not covers("cloud architecture", "aws")


# ---------------------------------------------------------------- resumes (real PDFs)
def test_strong_resume_profile():
    p = profile_of("strong-cloud-architect-match.pdf")
    assert p["current_role"] == "Senior Cloud Engineer" and p["department"] == "Cloud & DevOps"
    assert p["experience_years"] == 7.0
    assert {"aws", "terraform", "kubernetes", "docker", "linux", "python"} <= keys(p, "dataset")
    assert "cloud architecture" in keys(p, "custom")          # unknown to the vocabulary, still kept
    assert "kubernetes" in keys(p)                            # "K8s" in the text is normalised


def test_partial_resume_profile_has_fewer_cloud_skills():
    strong, partial = profile_of("strong-cloud-architect-match.pdf"), profile_of("medium-cloud-architect-match.pdf")
    assert partial["current_role"] == "System Administrator" and partial["department"] == "IT Infrastructure"
    assert {"linux", "python", "aws", "vmware"} <= keys(partial)
    assert not {"terraform", "kubernetes", "docker"} & keys(partial)
    assert len(keys(partial, "dataset")) < len(keys(strong, "dataset"))


def test_weak_resume_profile_has_no_technical_cloud_skills():
    p = profile_of("weak-cloud-architect-match.pdf")
    assert p["current_role"] == "HR Executive" and p["department"] == "Human Resources"
    assert keys(p, "dataset") <= {"excel", "powerpoint", "outlook", "word"}
    assert "performance management" in keys(p, "custom")       # a wrapped line must not split into two skills


# ---------------------------------------------------------------- experience, department, sections
def test_experience_estimated_from_dates_when_not_stated():
    text = "Jane Doe\nData Analyst\n\nEXPERIENCE\nData Analyst - Acme | Jan 2020 - Dec 2021\n- built reports\nAnalyst - Beta | Jan 2022 - Present\n\nSKILLS\nSQL, Excel"
    p = parse_resume(text, V, today=date(2024, 1, 1))
    assert p["experience_years"] == 4.0 and "estimated" in p["experience_source"]


def test_stated_department_wins_over_inference():
    p = parse_resume("A B\nEngineer\nDepartment: Platform Security\nEXPERIENCE\nSoftware Engineer - X | 2020 - 2022\nSKILLS\nPython", V)
    assert p["department"] == "Platform Security" and p["department_source"] == "stated in the resume"


def test_missing_sections_produce_warnings_not_guesses():
    p = parse_resume("Some free text about gardening and cooking and travelling for many many many years of fun times", V)
    assert p["current_role"] is None and p["experience_years"] is None and p["skills"] == []
    assert len(p["warnings"]) >= 3


def test_search_query_is_never_a_user_skill():
    # The parser has no access to a query; a resume that does not mention a skill never yields it.
    assert "terraform" not in keys(profile_of("weak-cloud-architect-match.pdf"))


# ---------------------------------------------------------------- PDF failure modes
def test_invalid_empty_and_text_less_pdfs():
    for data, code in [(b"", "empty_file"), (b"hello, this is not a pdf at all", "not_pdf"), (b"%PDF-1.4 garbage garbage", "unreadable")]:
        with pytest.raises(ResumeError) as e:
            extract_pdf_text(data)
        assert e.value.code == code
    from reportlab.pdfgen import canvas
    buf = io.BytesIO(); c = canvas.Canvas(buf); c.rect(50, 50, 100, 100); c.save()      # a page with no text (like a scan)
    with pytest.raises(ResumeError) as e:
        extract_pdf_text(buf.getvalue())
    assert e.value.code == "no_text"


def test_encrypted_pdf_is_reported():
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter(); w.append_pages_from_reader(PdfReader(str(DEMO / "weak-cloud-architect-match.pdf"))); w.encrypt("secret")
    buf = io.BytesIO(); w.write(buf)
    with pytest.raises(ResumeError) as e:
        extract_pdf_text(buf.getvalue())
    assert e.value.code == "encrypted"


def test_oversized_upload_rejected():
    with pytest.raises(ResumeError) as e:
        extract_pdf_text(b"%PDF" + b"0" * (9 * 1024 * 1024))
    assert e.value.code == "too_large"
