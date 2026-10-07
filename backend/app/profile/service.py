"""Resume upload pipeline used by both real uploads and the bundled demo resumes (the demos are NOT a shortcut)."""
from __future__ import annotations

from ..config import DEMO_DIR
from .resume import ResumeError, extract_pdf_text, parse_resume
from .skills import SkillVocabulary, pretty

DEMOS = {
    "strong": {"file": "strong-cloud-architect-match.pdf", "title": "Strong Cloud Architect Candidate", "blurb": "Cloud and DevOps engineer, 7 years. Most architect tooling already in place."},
    "partial": {"file": "medium-cloud-architect-match.pdf", "title": "Partial Cloud Architect Candidate", "blurb": "System administrator, 5 years. Linux, networking and basic AWS."},
    "weak": {"file": "weak-cloud-architect-match.pdf", "title": "Career Switcher (Low Match)", "blurb": "HR executive, 4 years. Almost no technical skills."},
}


def analyze_resume(data: bytes, filename: str, vocab: SkillVocabulary, demo: str | None = None) -> dict:
    steps = [{"step": "Upload", "ok": True, "detail": f"{filename}, {len(data) / 1024:.0f} KB"}]
    text, pages = extract_pdf_text(data)        # raises ResumeError with a user-facing message
    steps.append({"step": "Text extraction", "ok": True, "detail": f"{pages} page(s), {len(text):,} characters"})
    parsed = parse_resume(text, vocab)
    for s in parsed["skills"]:
        s["display"] = pretty(s["name"]) if s["status"] == "dataset" else s["name"]
    n_known = sum(1 for s in parsed["skills"] if s["status"] == "dataset")
    steps.append({"step": "Profile detection", "ok": True, "detail": f"role: {parsed['current_role'] or 'not found'}; {len(parsed['skills'])} skills ({n_known} known to the job data, {len(parsed['skills']) - n_known} custom)"})
    return {"file": {"name": filename, "size_kb": round(len(data) / 1024), "pages": pages, "chars": len(text)}, "steps": steps,
            "profile": {"current_role": parsed["current_role"], "department": parsed["department"], "department_source": parsed["department_source"],
                        "experience_years": parsed["experience_years"], "experience_source": parsed["experience_source"], "skills": parsed["skills"]},
            "sections_found": parsed["sections_found"], "warnings": parsed["warnings"], "demo": demo,
            "confirmation_required": True}


def demo_list() -> list[dict]:
    return [{"key": k, **{x: v for x, v in d.items() if x != "file"}, "available": (DEMO_DIR / d["file"]).exists()} for k, d in DEMOS.items()]


def analyze_demo(key: str, vocab: SkillVocabulary) -> dict:
    if key not in DEMOS:
        raise KeyError(f"Unknown demo profile '{key}'. Use one of: {', '.join(DEMOS)}.")
    path = DEMO_DIR / DEMOS[key]["file"]
    if not path.exists():
        raise ResumeError("missing_demo", "The demo resume file is missing from docs/demo-resumes/.")
    return analyze_resume(path.read_bytes(), path.name, vocab, demo=key)
