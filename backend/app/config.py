"""
Configuration for CareerLens. Every weight is a HAND-SET PRIOR (not learned) with its rationale next to it;
all of them can be overridden per request and are shown in Research Mode.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = Path(os.environ.get("CAREERLENS_DATA", ROOT / "data" / "jobs" / "jobs.csv"))
DATASET_INFO_PATH = ROOT / "data" / "jobs" / "DATASET.json"
EVAL_DIR = ROOT / "evaluation"
EVAL_RESULTS_PATH = EVAL_DIR / "results" / "eval_results.json"
DEMO_DIR = ROOT / "docs" / "demo-resumes"
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Retrieval zones = the fields that exist in the dataset. (It has no description or department field.)
# job_title_short is deliberately NOT part of the searched text: the evaluation uses it as the relevance label.
ZONES = ["Title", "Skills", "Location", "Company", "WorkType"]
BIWORD_ZONES = {"Title", "Company"}

# alpha_z. Title identifies the role, so it counts most; the skill list is the next most informative field.
# Title and Skills are priors. Company, Location and w_jaccard were chosen by grid search on the DEV half of the judged queries
# (evaluation/results/tuning.json) and are reported on the held-out TEST half. A zone only takes part when the query is about it
# (zone routing), so a high Company weight acts like "the user named a company": postings from other companies lose that share.
# Note: the best Company weight (0.40) was the largest value in the grid, so a larger one might do better still.
# WorkType (schedule type + remote flag) is a low-weight prior: it only matters when the query says "remote", "contract", "internship"...
DEFAULT_ZONE_WEIGHTS = {"Title": 0.45, "Skills": 0.30, "Location": 0.15, "Company": 0.40, "WorkType": 0.10}


@dataclass(frozen=True)
class RankingConfig:
    """Hybrid IR score = (w_cosine * zone-weighted TF-IDF cosine + w_jaccard * Jaccard) / (w_cosine + w_jaccard)."""
    zone_weights: dict = field(default_factory=lambda: dict(DEFAULT_ZONE_WEIGHTS))
    w_cosine: float = 0.85
    w_jaccard: float = 0.35       # set-overlap signal; chosen on the dev half of the judged queries
    use_zones: bool = True        # False = one flat bag of words (used for the TF-IDF baseline)
    use_biwords: bool = True
    use_routing: bool = True      # zone routing: a query word counts only in fields where it is a main field for that word
    routing_tau: float = 0.5      # ...i.e. where its document frequency is >= tau * its document frequency in its main field
    diversity: bool = True        # reorder only near-ties so one posting family does not fill the page
    diversity_epsilon: float = 0.0
    pool_factor: int = 4

    def with_overrides(self, **kw) -> "RankingConfig":
        kw = {k: v for k, v in kw.items() if v is not None}
        if "zone_weights" in kw:
            merged = dict(self.zone_weights)
            merged.update({z: float(w) for z, w in kw["zone_weights"].items() if z in ZONES})
            kw["zone_weights"] = merged
        return replace(self, **kw)

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_CONFIG = RankingConfig()
