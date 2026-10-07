"""
Build the CareerLens working corpus (data/jobs/jobs.csv) from the data_jobs collection.

Source : Luke Barousse, "data_jobs" (2023 job postings collected from Google Jobs through SerpAPI)
         https://huggingface.co/datasets/lukebarousse/data_jobs        License: Apache-2.0 (per the dataset card)
Input  : the single file data_jobs.csv from that page (785,741 rows, 17 columns, about 231 MB).

Usage  : python tools/build_dataset.py --input path/to/data_jobs.csv

Steps (all counted and written to data/jobs/DATASET.json):
  1. Drop rows with no title, no company or no skills list (skills are what makes skill-gap analysis possible).
  2. Merge re-postings: rows with the same (title, company, location) become ONE listing that remembers how many
     postings it stands for (`listings`) and its latest posting date. Nothing else is removed.
  3. Canonicalise company spelling: "Saracus Consulting Gmbh" and "saracus consulting GmbH" share one display name
     (the most frequent form), so company filtering and search work.
  4. Working-corpus rule: keep EVERY listing whose title matches the cloud / infrastructure / architect family
     (the roles the career-transition demo needs) and add a seeded random sample (SEED) of at most PER_FAMILY listings
     from each dataset role label (`job_title_short`). This is a convenience sample to keep the pure-Python index
     small enough for a laptop. It over-represents cloud and infrastructure roles relative to the full dataset,
     and the README says so.
No fields are invented: description, experience level and job URL do not exist in this dataset and are not created.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "jobs"
SEED, PER_FAMILY = 13, 4000
FAMILY_RE = re.compile(r"cloud|devops|architect|infrastructure|\bsre\b|site reliability|platform engineer|sysadmin|"
                       r"system administrator|systems administrator|network", re.I)
OUT_COLUMNS = ["job_id", "title", "company", "location", "country", "workplace", "schedule", "role_family", "skills", "posted",
               "salary_year_avg", "salary_hour_avg", "salary_rate", "via", "listings", "no_degree", "health_insurance"]


def clean(s) -> str:
    return " ".join((s or "").split())


def parse_skills(raw: str) -> list[str]:
    try:
        vals = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return []
    out, seen = [], set()
    for v in vals if isinstance(vals, list) else []:
        v = clean(str(v)).lower()
        if v and v not in seen:
            seen.add(v); out.append(v)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    args = ap.parse_args()
    csv.field_size_limit(10 ** 9)
    stats = {"source": "lukebarousse/data_jobs (Hugging Face)", "source_url": "https://huggingface.co/datasets/lukebarousse/data_jobs",
             "license": "Apache-2.0 (as stated on the dataset card)"}
    groups: dict[tuple, list] = {}
    raw_rows = dropped = 0
    drop_reasons = Counter()
    with open(args.input, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            raw_rows += 1
            title, company, skills = clean(row["job_title"]), clean(row["company_name"]), parse_skills(row["job_skills"] or "[]")
            if not title or not company or not skills:
                dropped += 1
                drop_reasons["no title" if not title else "no company" if not company else "no skills"] += 1
                continue
            loc = clean(row["job_location"])
            key = (title.lower(), company.lower(), loc.lower())
            posted = (row["job_posted_date"] or "")[:10]
            g = groups.get(key)
            if g is None:
                groups[key] = [1, posted, title, company, loc, clean(row["job_country"]), row["job_work_from_home"] == "True",
                               clean(row["job_schedule_type"]), clean(row["job_title_short"]), skills, row["salary_year_avg"], row["salary_hour_avg"],
                               clean(row["salary_rate"]), clean(row["job_via"]).removeprefix("via "), row["job_no_degree_mention"] == "True",
                               row["job_health_insurance"] == "True"]
            else:
                g[0] += 1
                if posted > g[1]:
                    g[1] = posted
    stats.update(raw_rows=raw_rows, dropped_rows=dropped, drop_reasons=dict(drop_reasons), usable_rows=raw_rows - dropped,
                 unique_listings=len(groups), reposts_merged=raw_rows - dropped - len(groups))

    # canonical company spelling = most frequent display form
    forms: dict[str, Counter] = defaultdict(Counter)
    for g in groups.values():
        forms[g[3].lower()][g[3]] += g[0]
    canon_company = {k: c.most_common(1)[0][0] for k, c in forms.items()}

    family = [g for g in groups.values() if FAMILY_RE.search(g[2])]
    rest_by_label: dict[str, list] = defaultdict(list)
    for g in groups.values():
        if not FAMILY_RE.search(g[2]):
            rest_by_label[g[8]].append(g)
    rng = random.Random(SEED)
    chosen = list(family)
    for label in sorted(rest_by_label):
        pool = rest_by_label[label]
        chosen += rng.sample(pool, min(PER_FAMILY, len(pool)))
    chosen.sort(key=lambda g: (g[2].lower(), g[3].lower(), g[4].lower()))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "jobs.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(OUT_COLUMNS)
        for i, g in enumerate(chosen):
            w.writerow([i, g[2], canon_company[g[3].lower()], g[4], g[5] or "Unknown", "Remote" if g[6] else "Not remote", g[7] or "Not stated",
                        g[8], "|".join(g[9]), g[1], g[10], g[11], g[12], g[13], g[0], g[14], g[15]])

    skills_c = Counter(s for g in chosen for s in g[9])
    stats.update(
        working_rule={"keep_all": "listings whose title matches " + FAMILY_RE.pattern, "plus_sample_per_role_label": PER_FAMILY, "seed": SEED,
                      "note": "convenience sample; over-represents cloud/infrastructure roles"},
        family_listings=len(family), working_listings=len(chosen), postings_represented=sum(g[0] for g in chosen),
        companies=len({canon_company[g[3].lower()] for g in chosen}), countries=len({g[5] for g in chosen if g[5]}),
        role_labels=dict(Counter(g[8] for g in chosen).most_common()), distinct_skills=len(skills_c),
        top_skills=skills_c.most_common(15), skills_per_listing_mean=round(sum(len(g[9]) for g in chosen) / len(chosen), 2),
        remote_share=round(sum(g[6] for g in chosen) / len(chosen), 3), with_salary_year=sum(1 for g in chosen if g[10]),
        posted_range=[min(g[1] for g in chosen), max(g[1] for g in chosen)],
        missing_in_working={"location": sum(1 for g in chosen if not g[4]), "schedule": sum(1 for g in chosen if not g[7]),
                            "country": sum(1 for g in chosen if not g[5])},
        fields_absent_from_source=["job description", "required experience / seniority field", "job URL", "department"])
    (OUT_DIR / "DATASET.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps({k: v for k, v in stats.items() if k not in ("role_labels", "top_skills", "working_rule")}, indent=1))
    print("role labels:", stats["role_labels"]); print("top skills:", stats["top_skills"][:8])
    print("wrote", OUT_DIR / "jobs.csv", f"({(OUT_DIR / 'jobs.csv').stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
