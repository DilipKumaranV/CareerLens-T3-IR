"""
Resume PDF -> editable profile suggestion.

Pipeline: bytes -> text (pypdf) -> clean -> sections -> role / department / experience / skills.
Everything returned is a SUGGESTION the user can edit and must confirm before it is used for matching.
Nothing here reads a search query, and nothing is guessed when it cannot be found (the field stays empty and a
warning says so). Name and contact details are deliberately not extracted.
"""
from __future__ import annotations

import io
import re
import unicodedata
from datetime import date

from .skills import SkillVocabulary, split_top_level

MAX_BYTES = 8 * 1024 * 1024


class ResumeError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def extract_pdf_text(data: bytes) -> tuple[str, int]:
    if not data:
        raise ResumeError("empty_file", "The file is empty.")
    if len(data) > MAX_BYTES:
        raise ResumeError("too_large", f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    if not data.lstrip()[:5].startswith(b"%PDF"):
        raise ResumeError("not_pdf", "This does not look like a PDF file. Upload a PDF resume, or enter your profile manually.")
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ResumeError("encrypted", "This PDF is password-protected. Remove the password or enter your profile manually.")
        pages = [(p.extract_text() or "") for p in reader.pages]
    except ResumeError:
        raise
    except Exception as e:   # corrupt or unsupported PDF structure
        raise ResumeError("unreadable", f"The PDF could not be read ({type(e).__name__}). Try another file or enter your profile manually.") from e
    text = clean_text("\n".join(pages))
    if len(re.findall(r"[A-Za-z]{3,}", text)) < 15:
        raise ResumeError("no_text", "No readable text was found. The PDF may be a scanned image. Use a text-based PDF or enter your profile manually.")
    return text, len(pages)


def clean_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = re.sub(r"[\u2022\u25cf\u25aa\u25e6\u2023\u2043\u00b7]", "- ", t)
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", t)
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)             # words split across lines
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


SECTION_ALIASES = {
    "summary": ["summary", "professional summary", "profile", "objective", "about me", "career objective"],
    "skills": ["skills", "technical skills", "core skills", "key skills", "core competencies", "competencies", "technologies", "skills and tools"],
    "experience": ["experience", "work experience", "professional experience", "employment", "employment history", "work history", "career history"],
    "education": ["education", "academic background", "qualifications"],
    "certifications": ["certifications", "certificates", "licenses", "training"],
    "projects": ["projects", "key projects"],
}
_HEADINGS = {a: k for k, v in SECTION_ALIASES.items() for a in v}


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"header": []}
    cur = "header"
    for line in text.splitlines():
        key = re.sub(r"[^a-z ]", "", line.lower()).strip()
        if key in _HEADINGS and len(line) < 40:
            cur = _HEADINGS[key]
            sections.setdefault(cur, [])
            continue
        sections[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


ROLE_RE = re.compile(r"\b(engineer|administrator|admin|executive|analyst|manager|developer|architect|specialist|consultant|officer|"
                     r"scientist|designer|lead|technician|coordinator|associate|assistant|director|intern|programmer|accountant|recruiter)\b", re.I)
_SEP = re.compile(r"\s+[\u2014\u2013|@]\s+|\s+-\s+|\s+at\s+|\s{2,}")
_DATE_TAIL = re.compile(r"\s*[\(\[]?\b(?:[A-Za-z]{3,9}\.?\s+)?(?:19|20)\d{2}\b.*$")

DEPT_RULES = [   # ordered: first rule that matches the role/headline wins; documented as a heuristic in the UI
    ("Human Resources", r"\b(hr|human resources|recruit\w*|payroll|talent|employee relations|people operations)\b"),
    ("Cloud & DevOps", r"\b(cloud|devops|sre|site reliability|platform engineer)\b"),
    ("IT Infrastructure", r"\b(system administrator|systems administrator|sysadmin|infrastructure|network (engineer|administrator)|it support|helpdesk|data cent(er|re))\b"),
    ("Data & Analytics", r"\b(data (scientist|analyst|engineer)|analytics|business intelligence|bi developer|machine learning)\b"),
    ("Software Engineering", r"\b(software|developer|programmer|full[- ]?stack|back[- ]?end|front[- ]?end)\b"),
    ("Marketing", r"\b(marketing|seo|content|brand|social media)\b"),
    ("Finance", r"\b(finance|financial|accountant|accounting|audit)\b"),
    ("Sales", r"\b(sales|business development|account executive)\b"),
]
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
RANGE = re.compile(r"(?:(?P<m1>[A-Za-z]{3,9})\.?\s+)?(?P<y1>(?:19|20)\d{2})\s*(?:[-\u2013\u2014]|to)\s*"
                   r"(?:(?:(?P<m2>[A-Za-z]{3,9})\.?\s+)?(?P<y2>(?:19|20)\d{2})|(?P<now>present|current|now|till date|ongoing))", re.I)
EXPLICIT = re.compile(r"(\d{1,2})(?:\.\d)?\s*\+?\s*(?:years|yrs)\b(?:\s+of)?(?:\s+[\w&/-]+){0,4}?\s+experience|experience\s*(?:of|:)?\s*(\d{1,2})\s*\+?\s*(?:years|yrs)", re.I)


def _find_role(sections: dict[str, str]) -> str | None:
    for src in (sections.get("experience", ""), "\n".join(sections.get("header", "").splitlines()[1:6])):
        for line in src.splitlines():
            line = line.strip()
            if not line or line.startswith("-") or len(line) > 130 or not ROLE_RE.search(line):
                continue
            parts = [p.strip(" ,;") for p in _SEP.split(_DATE_TAIL.sub("", line)) if p.strip()]
            for p in parts[:2]:
                if ROLE_RE.search(p) and len(p.split()) <= 9:
                    return p
    return None


def _find_department(text: str, role: str | None, sections: dict[str, str]) -> tuple[str | None, str | None]:
    m = re.search(r"department\s*[:\-]\s*([A-Za-z&/ ]{3,40})", text, re.I)
    if m:
        return m.group(1).strip(), "stated in the resume"
    probe = " ".join(filter(None, [role, "\n".join(sections.get("header", "").splitlines()[:6])]))
    for name, rx in DEPT_RULES:
        if re.search(rx, probe, re.I):
            return name, "inferred from the role (heuristic)"
    return None, None


def _find_experience(text: str, sections: dict[str, str], today: date | None = None) -> tuple[float | None, str | None]:
    head = "\n".join([sections.get("summary", ""), sections.get("header", "")])
    m = EXPLICIT.search(head) or EXPLICIT.search(text)
    if m:
        return float(m.group(1) or m.group(2)), "stated in the resume"
    today = today or date.today()
    spans = []
    for r in RANGE.finditer(sections.get("experience", "") or text):
        s = int(r["y1"]) + (MONTHS.get((r["m1"] or "")[:3].lower(), 1) - 1) / 12
        e = today.year + (today.month - 1) / 12 if r["now"] else int(r["y2"]) + MONTHS.get((r["m2"] or "")[:3].lower(), 12) / 12   # an end month counts to its end
        if e >= s:
            spans.append((s, e))
    if not spans:
        return None, None
    spans.sort(); merged = [list(spans[0])]
    for s, e in spans[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return round(sum(e - s for s, e in merged), 1), "estimated from the dates of the jobs listed"


def _skills_from_section(vocab: SkillVocabulary, block: str):
    # Re-join lines that the PDF wrapped: a short unlabelled line right after a labelled one continues it.
    logical: list[str] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        labelled = ":" in line and len(line.split(":")[0].split()) <= 4
        continues = (logical and not labelled and not line.startswith("-") and ":" in logical[-1]
                     and (logical[-1].rstrip().endswith(",") or len(line.split()) <= 6))
        if continues:
            logical[-1] += " " + line
        else:
            logical.append(line)
    items = []
    for line in logical:
        line = line.lstrip("-").strip()
        if ":" in line and len(line.split(":")[0].split()) <= 4:     # "Cloud: AWS, Azure" -> items after the label
            line = line.split(":", 1)[1]
        items.extend(split_top_level(line))
    short = [i for i in items if len(i.split()) <= 6]
    sk = vocab.from_list(short, source="skills section")
    for long_item in (i for i in items if len(i.split()) > 6):     # a sentence, not a skill: only recognise skills inside it
        sk += vocab.extract(long_item, "skills section")
    return sk


def parse_resume(text: str, vocab: SkillVocabulary, today: date | None = None) -> dict:
    sections = split_sections(text)
    role = _find_role(sections)
    dept, dept_src = _find_department(text, role, sections)
    years, years_src = _find_experience(text, sections, today)
    found = _skills_from_section(vocab, sections["skills"]) if "skills" in sections else []
    seen = {s.key for s in found}
    for s in vocab.extract("\n".join(v for k, v in sections.items() if k not in ("skills", "education")), "experience text"):
        if s.key not in seen:
            found.append(s); seen.add(s.key)
    warnings = []
    if "skills" not in sections:
        warnings.append("No 'Skills' section was found. Skills were taken from the rest of the text; please review them.")
    if not role:
        warnings.append("Current role could not be detected. Please enter it.")
    if years is None:
        warnings.append("Experience could not be detected. Please enter it.")
    if not found:
        warnings.append("No skills were detected. Please add your skills manually.")
    return {"current_role": role, "department": dept, "department_source": dept_src,
            "experience_years": years, "experience_source": years_src,
            "skills": [s.to_dict() for s in found], "sections_found": [k for k in sections if k != "header"], "warnings": warnings}
