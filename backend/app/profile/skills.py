"""
Skill vocabulary, normalisation and extraction.

Design rules (they exist because v3 silently dropped valid skills such as "sql" and "powerbi"):
  * The vocabulary is a RECOGNITION AID, never a filter. A skill that is not in it is kept as a "custom" skill
    and takes part in matching exactly like any other.
  * Normalisation maps spelling variants to one canonical key ("PowerBI", "Power-BI" -> "power bi"). The original
    text is always kept for display.
  * User skills come only from what the user supplied (resume or typed). Nothing here ever looks at a search query.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..config import ROOT

SKILLS_CSV = ROOT / "data" / "skills" / "skills_dim.csv"

# Spelling / naming variants -> canonical vocabulary name. This is normalisation, not a whitelist.
ALIASES = {
    "amazon web services": "aws", "amazon aws": "aws", "aws cloud": "aws",
    "microsoft azure": "azure", "azure cloud": "azure",
    "google cloud platform": "gcp", "google cloud": "gcp",
    "k8s": "kubernetes", "hashicorp terraform": "terraform",
    "powerbi": "power bi", "power-bi": "power bi", "microsoft power bi": "power bi", "ms power bi": "power bi",
    "ms excel": "excel", "microsoft excel": "excel", "ms word": "word", "microsoft word": "word",
    "ms powerpoint": "powerpoint", "microsoft powerpoint": "powerpoint", "ms outlook": "outlook",
    "postgres": "postgresql", "postgre sql": "postgresql", "ms sql server": "sql server", "mssql": "sql server",
    "microsoft sql server": "sql server", "t sql": "t-sql", "my sql": "mysql",
    "js": "javascript", "nodejs": "node.js", "node js": "node.js", "reactjs": "react", "react js": "react",
    "react.js": "react", "vuejs": "vue", "vue js": "vue", "vue.js": "vue", "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn", "red hat": "redhat", "rhel": "redhat", "red hat enterprise linux": "redhat",
    "vsphere": "vmware", "vmware vsphere": "vmware", "esxi": "vmware", "vmware esxi": "vmware",
    "shell scripting": "shell", "bash scripting": "bash", "golang": "go", "ms teams": "microsoft teams",
    "github actions": "github", "gitlab ci": "gitlab", "jenkins ci": "jenkins",
    "visual basic for applications": "vba", "sql server": "sql server", "sqlserver": "sql server",
}

# Vocabulary words that are also ordinary English words or single letters. In running text they are NOT counted
# (so "word" or "go" never create a skill by accident); they count only when they are an exact skill-list item.
AMBIGUOUS = {"r", "c", "go", "word", "arch", "flow", "phoenix", "unity", "wire", "unify", "terminal", "express",
             "spring", "play framework", "crystal", "sheets", "planner", "notion", "outlook", "mongo",
             "node", "ruby", "assembly", "swift", "dart", "lisp", "wsl", "yarn", "electron", "capacitor", "gtx"}

def _plain(text: str) -> str:
    """Lower case; '&', '/', '_' and '-' become spaces; punctuation other than + # . removed; spaces collapsed."""
    t = (text or "").lower().replace("&", " and ").replace("/", " ").replace("_", " ").replace("-", " ")
    t = re.sub(r"[^a-z0-9+#. ]", " ", t)
    return re.sub(r"\s+", " ", t).strip().rstrip(".").strip()


_ALIAS = {_plain(k): _plain(v) for k, v in ALIASES.items()}


def canon(text: str) -> str:
    """Canonical key of a skill phrase. The same function is applied to user text and to vocabulary names,
    so "Power-BI", "PowerBI" and "power bi" all become "power bi"."""
    p = _plain(text)
    return _ALIAS.get(p, p)


def tokens(key: str) -> list[str]:
    return [x for x in re.split(r"\s+", key) if x]


@dataclass
class Skill:
    name: str                  # as the user wrote it
    key: str                   # canonical key used for matching
    status: str                # "dataset" (known vocabulary skill) or "custom" (kept, not in vocabulary)
    type: str | None = None    # vocabulary type, e.g. "cloud"
    source: str = "typed"      # "skills section", "experience text", "typed"
    evidence: str | None = None

    def to_dict(self) -> dict:
        return {"name": self.name, "key": self.key, "status": self.status, "type": self.type,
                "source": self.source, "evidence": self.evidence}


class SkillVocabulary:
    def __init__(self, names_with_types: dict[str, str] | None = None):
        self.types: dict[str, str] = {}
        for n, t in (names_with_types or {}).items():
            self.types.setdefault(canon(n), t)
        # patterns for free-text extraction: vocabulary names plus every alias whose target is in the vocabulary
        phrases = {k for k in self.types if k not in AMBIGUOUS}
        phrases |= {_plain(a) for a, tgt in ALIASES.items() if canon(tgt) in self.types and canon(tgt) not in AMBIGUOUS}
        self._phrases = sorted(phrases, key=lambda p: (-len(p), p))
        self._regex = {p: re.compile(r"(?<![A-Za-z0-9+#.])" + r"[\s\-/]*".join(re.escape(w) for w in p.split(" ")) + r"(?![A-Za-z0-9+#])", re.I)
                       for p in self._phrases}

    @classmethod
    def load(cls, path: Path = SKILLS_CSV) -> "SkillVocabulary":
        try:
            with open(path, encoding="utf-8-sig", newline="") as fh:
                return cls({r["skills"]: r.get("type", "other") for r in csv.DictReader(fh) if r.get("skills")})
        except OSError:
            return cls({})        # no vocabulary file: everything is a custom skill, nothing breaks

    def __len__(self) -> int:
        return len(self.types)

    def make(self, text: str, source: str = "typed", evidence: str | None = None) -> Skill:
        k = canon(text)
        known = k in self.types
        return Skill(name=" ".join(text.split()), key=k, status="dataset" if known else "custom",
                     type=self.types.get(k), source=source, evidence=evidence)

    def from_list(self, items: list[str], source: str = "typed") -> list[Skill]:
        """Every non-empty item becomes a skill. Unknown items are kept as custom skills."""
        out: dict[str, Skill] = {}
        for raw in items:
            for item in split_top_level(raw):
                base, inner = _split_parenthetical(item)
                if not canon(base):
                    continue
                sk = self.make(base, source)
                out.setdefault(sk.key, sk)
                for sub in inner:
                    s2 = self.make(sub, source, evidence=f"listed under {base}")
                    out.setdefault(s2.key, s2)
                # a longer phrase may contain known skills: "AWS cloud infrastructure" -> also "aws"
                if sk.status == "custom":
                    for s2 in self.extract(base, source, evidence=f"inside \"{item}\""):
                        out.setdefault(s2.key, s2)
        return list(out.values())

    def extract(self, text: str, source: str = "experience text", evidence: str | None = None) -> list[Skill]:
        """Find vocabulary skills (and aliases) inside running text. Longest phrases first; overlaps skipped."""
        found: dict[str, Skill] = {}
        taken: list[tuple[int, int]] = []
        for p in self._phrases:
            for m in self._regex[p].finditer(text):
                span = m.span()
                if any(s < span[1] and span[0] < e for s, e in taken):
                    continue
                taken.append(span)
                key = canon(p)
                if key not in found:
                    ctx = text[max(0, span[0] - 30): span[1] + 30].replace("\n", " ").strip()
                    found[key] = Skill(name=m.group(0).strip(), key=key, status="dataset", type=self.types.get(key),
                                       source=source, evidence=evidence or f"…{ctx}…")
        return list(found.values())


def split_top_level(text: str) -> list[str]:
    """Split on commas, semicolons, pipes, bullets and newlines, but not inside parentheses."""
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if depth == 0 and ch in ",;|\n\u2022\u00b7":
            parts.append("".join(cur)); cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip(" \t-*") for p in parts if p.strip(" \t-*")]


def _split_parenthetical(item: str) -> tuple[str, list[str]]:
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", item)
    if not m:
        return item, []
    return m.group(1).strip(), [x.strip() for x in m.group(2).split(",") if x.strip()]


def covers(user_key: str, job_key: str) -> bool:
    """Does a user skill satisfy a job skill? Equal keys, or the job skill's words all occur in the user's phrase
    ("aws cloud infrastructure" covers "aws"). Single-letter job skills ("r", "c") must match exactly."""
    if user_key == job_key:
        return True
    jt = tokens(job_key)
    if not jt or (len(jt) == 1 and len(jt[0]) == 1):
        return False
    return set(jt) <= set(tokens(user_key))


_PRETTY = {"aws": "AWS", "gcp": "GCP", "sql": "SQL", "nosql": "NoSQL", "no sql": "NoSQL", "power bi": "Power BI", "t sql": "T-SQL", "javascript": "JavaScript",
           "typescript": "TypeScript", "postgresql": "PostgreSQL", "mysql": "MySQL", "mongodb": "MongoDB", "pytorch": "PyTorch", "tensorflow": "TensorFlow",
           "sql server": "SQL Server", "vmware": "VMware", "github": "GitHub", "gitlab": "GitLab", "bigquery": "BigQuery", "dynamodb": "DynamoDB",
           "pyspark": "PySpark", "numpy": "NumPy", "scikit learn": "scikit-learn", "powershell": "PowerShell", "redhat": "Red Hat", "ibm cloud": "IBM Cloud",
           "ssis": "SSIS", "ssrs": "SSRS", "sas": "SAS", "spss": "SPSS", "vba": "VBA", "html": "HTML", "css": "CSS", "php": "PHP", "sap": "SAP", "dax": "DAX",
           "ci/cd": "CI/CD", "ci cd": "CI/CD", "hr": "HR", "hris": "HRIS", "api": "API", "etl": "ETL", "ml": "ML", "ai": "AI", "vpn": "VPN", "dns": "DNS",
           "dhcp": "DHCP", "tcp ip": "TCP/IP", "iam": "IAM", "ec2": "EC2", "s3": "S3", "ibm": "IBM", "jira": "Jira", "kafka": "Kafka", "redis": "Redis"}


def pretty(name: str) -> str:
    """Display form of a skill key or name: known acronyms and brand spellings, otherwise Title Case."""
    k = canon(name)
    if k in _PRETTY:
        return _PRETTY[k]
    words = k.split()
    return " ".join(w.upper() if len(w) <= 2 and w.isalpha() else w.capitalize() if not any(c in w for c in "+#.") else w for w in words)
