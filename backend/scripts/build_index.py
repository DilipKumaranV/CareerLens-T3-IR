"""Build (or refresh) the persisted search index so the API starts fast.

    python scripts/build_index.py            # from the backend folder

CSV -> preprocessing -> inverted indexes (Title, Skills, Location, Company, WorkType, flat) -> data/jobs/.index_cache.pkl
The cache is keyed by a hash of jobs.csv and the index version; the API rebuilds it automatically when either changes.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import DATA_PATH, ZONES  # noqa: E402
from app.ir.jobs import JobSearchEngine  # noqa: E402

t = time.perf_counter()
e = JobSearchEngine(DATA_PATH, use_cache=True)
cache = DATA_PATH.with_name(".index_cache.pkl")
print(f"{e.N:,} listings | {e.cache_status} | {time.perf_counter() - t:.1f} s")
print("vocabulary per zone:", {z: f"{e.zone_index[z].vocabulary_size:,}" for z in ZONES}, "| flat:", f"{e.flat_index.vocabulary_size:,}")
print("cache file:", cache, f"({cache.stat().st_size / 1e6:.0f} MB)" if cache.exists() else "(not written)")
