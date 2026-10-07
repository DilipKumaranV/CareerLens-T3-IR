"""Dataset-level statistics for the Insights page, computed from the loaded working corpus."""
from __future__ import annotations

from collections import Counter

from .config import DATASET_INFO_PATH


def dataset_analytics(engine) -> dict:
    jobs = engine.jobs
    top = lambda c, n: [{"name": k, "count": v} for k, v in c.most_common(n)]
    import json
    try:
        info = json.loads(DATASET_INFO_PATH.read_text())
    except (OSError, ValueError):
        info = {}
    skills = Counter(s for j in jobs for s in set(j.skill_keys))
    return {"totals": {"listings": len(jobs), "postings": sum(j.listings for j in jobs), "companies": len({j.company for j in jobs}),
                       "countries": len({j.country for j in jobs}), "skills": len(skills)},
            "role_family": top(Counter(j.role_family for j in jobs), 12), "workplace": top(Counter(j.workplace for j in jobs), 5),
            "schedule": top(Counter(j.schedule for j in jobs), 8), "country": top(Counter(j.country for j in jobs), 12),
            "company": top(Counter(j.company for j in jobs), 12), "skill": top(skills, 20),
            "salary_listings": sum(1 for j in jobs if j.salary_year), "dataset": info}
