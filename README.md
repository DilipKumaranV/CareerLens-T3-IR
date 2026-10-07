# CareerLens

**An explainable Information Retrieval platform for job discovery and career transition planning.**
CSD358 Information Retrieval project (track T3, recommendation and personalization).

CareerLens ranks real job postings with classical Information Retrieval (inverted indexes, TF-IDF, cosine similarity,
Jaccard similarity, Top-K retrieval), shows exactly why each result ranked where it did, and, if you supply a profile,
tells you how well you fit a job or a target role, which skills you lack and what to prepare first.

> **Two scores, never mixed.**
> **IR Relevance Score** = how relevant a job is to your *search query*. It depends only on the query and the job.
> **Career Fit** = how well a job (or a target role) matches *your supplied profile*. It exists only after you upload a resume or enter skills.
> Without a profile the app shows: *"Personalized Career Fit unavailable. Upload your resume or enter your skills."*
> Search words are never treated as skills you have.

## 1. Run it (Windows, PowerShell)

Needs Python 3.10+ and Node 18+.

```powershell
# terminal 1: backend
cd backend
py -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
py -m uvicorn app.main:app --port 8000

# terminal 2: frontend
cd frontend
npm install
npm run dev          # open the URL Vite prints (http://localhost:5173)
```

The first backend start preprocesses all listings and builds the inverted indexes (about 30 to 60 s); it then saves them to
`data/jobs/.index_cache.pkl`, so later starts take about 6 s. The cache is rebuilt automatically if `jobs.csv` changes.
`py scripts\build_index.py` (in `backend`) builds it ahead of time. API docs: http://localhost:8000/docs.

Single-process alternative: `cd frontend; npm run build`, then run only the backend and open http://localhost:8000.

Tests: `cd backend; pytest -q` (61 tests). Evaluation: `py -c "from app.ir.jobs import JobSearchEngine; from app import evaluation as ev; ev.run_and_save(JobSearchEngine())"` (about 2 minutes).

## 2. Dataset

| | |
|---|---|
| Name | `data_jobs` (Luke Barousse) |
| Source | https://huggingface.co/datasets/lukebarousse/data_jobs |
| License | Apache-2.0 (as stated on the dataset card). Attribution and change notice: `data/jobs/NOTICE.md` |
| Origin of the data | Job postings collected from Google Jobs through SerpAPI during 2023 (per the author). The postings belong to their employers. |
| Provenance check | The supplied `data_jobs.csv` has the 17 columns and 785,741 rows of that dataset. If your copy came from elsewhere, correct this section. |

**Raw schema (17 columns):** `job_title_short, job_title, job_location, job_via, job_schedule_type, job_work_from_home, search_location, job_posted_date, job_no_degree_mention, job_health_insurance, job_country, salary_rate, salary_year_avg, salary_hour_avg, company_name, job_skills, job_type_skills`.

**What it does not have** (so CareerLens does not show it): a job description, an experience or seniority requirement, a job URL, a department. Salary exists for about 3% of rows.

**Preprocessing and cleaning** (`tools/build_dataset.py`, counts in `data/jobs/DATASET.json`):

| Step | Rows |
|---|---|
| Raw rows | 785,741 |
| Dropped: no skills list (117,036) or no title (1) | 117,037 |
| Usable rows | 668,704 |
| Merged re-postings (same title + company + location) | 152,667 |
| Unique listings | 516,037 |
| **Working corpus used by the app** | **58,952 listings** (representing 72,580 postings), 25,895 companies, 146 countries, 240 distinct skills, 5.74 skills per listing |

The full set is too large for a pure-Python index on a laptop, so the working corpus keeps **every** listing whose title matches a
cloud / infrastructure / architect pattern (18,952) plus a seeded random sample (seed 13, at most 4,000 per role label) of the rest.
It therefore **over-represents cloud and infrastructure roles** compared with the full dataset. Company names are canonicalised to the
most frequent spelling. Nothing is invented: missing values stay missing.

**Fields the app uses:** `job_title` (Title), `job_skills` (Skills), `company_name` (Company), `job_location` + `job_country` (Location),
`job_schedule_type` + `job_work_from_home` (Work type), `job_posted_date`, salary fields, `job_via`. `job_title_short` is kept as a
label ("role family") for filtering and for **evaluation**; it is deliberately **not** part of the searched text, so the evaluation
is not trivially solved by matching its own label.

## 3. IR pipeline

1. **Preprocessing** (`ir/preprocess.py`): Unicode and accent folding, tokenization, case folding (all-caps acronyms such as "IT" survive stop-word removal), stop-word removal (plus query-only words such as "jobs"), Porter stemming, and word pairs (biwords) for Title and Company.
2. **Inverted indexes** (`ir/index.py`): one per field (zone): Title, Skills, Location, Company, Work type, plus one flat index. Each stores postings `(document, tf)`, document frequency $df_t$ and
   $$idf_t=\log_{10}\frac{N}{df_t}.$$
3. **TF-IDF vectors** (lnc.ltc style): $w_{t,d}=(1+\log_{10} tf_{t,d})\cdot idf_t$, length-normalised to unit length.
4. **Cosine similarity**, computed term-at-a-time with accumulators (only documents that appear in a query term's postings are ever touched; depending on the query, between about 12% ("data engineer aws") and 83% ("terraform kubernetes") of listings are never scored).
5. **Zone routing** (`ir/jobs.py`): a query word is looked up only in the fields where its document frequency is at least half of its frequency in its main field (skills are included in that comparison). Without it, a coincidental word ("cloud" inside a company name) switches on a field that can only score 0 and lowers every score; an exact "Cloud Architect" title scored 0.64 without routing and 0.89 with it.
6. **Zone-weighted cosine**: $\cos(q,d)=\dfrac{\sum_{z\in\text{active}}\alpha_z\cos(q_z,d_z)}{\sum_{z\in\text{active}}\alpha_z}$. Weights $\alpha$: Title 0.45, Skills 0.30, Location 0.15, Company 0.40, Work type 0.10 (shown in Research Mode). A field takes part only when the query is about it.
7. **Jaccard similarity** between the query's stems and the listing's term set: $J=\dfrac{|Q\cap D|}{|Q\cup D|}$.
8. **IR Relevance Score** (hybrid): $\text{IR}=\dfrac{w_{c}\cos(q,d)+w_{J}\,J}{w_{c}+w_{J}}$ with $w_c=0.85$, $w_J=0.35$.
9. **Top-K** with a heap (`heapq.nsmallest`), then a diversity step that only reorders exact ties (so one family of identical postings does not fill the page; it changes no score).
10. **Explanations**: the zone-weighted cosine decomposes exactly into per-term contributions $\alpha\cdot w_{t,q}\cdot w_{t,d}$ (checked by a unit test). Normal mode shows the matching terms; Research Mode shows TF, DF, IDF, TF-IDF, normalised weights, cosine, Jaccard and the final score.

**About the weights.** Title and Skills are priors. The Company and Location weights and $w_J$ were chosen by grid search on the *dev half* of the judged queries (`evaluation/results/tuning.json`) and are reported on the held-out *test half*. The best Company weight (0.40) was the largest value in the grid. The Work type zone (0.10) is a prior added afterwards and was not tuned.

## 4. Career Fit

Computed in `backend/app/career.py` only when a confirmed profile exists.

* **Career Fit for one job** = 75% *skill match* + 25% *role similarity* (components that cannot be computed are dropped and the rest renormalised).
  * *Skill match* = idf-weighted share of the job's listed skills that your profile covers: $\dfrac{\sum_{s\in\text{job}\cap\text{you}}(idf_s+0.1)}{\sum_{s\in\text{job}}(idf_s+0.1)}$. A skill phrase covers a job skill when the words match ("AWS cloud infrastructure" covers "aws").
  * *Role similarity* = TF-IDF cosine between your current role and the job title (Title index).
  * Experience is **not** used: the dataset has no experience requirement. The UI says so.
* **Career Fit for a target role** (Career Transition page): the target role is searched like any query. The top-ranked postings (at most 50, at least 60% of the best IR score) are read; each skill's *prevalence* is the share of those postings listing it, weighted by their IR relevance. Career Fit = prevalence of the skills you have ÷ prevalence of all skills the role asks for. Skills below 10% prevalence are not treated as requirements.
* **Skill gaps and priorities:** missing skills ordered by prevalence; HIGH ≥ 50%, MEDIUM ≥ 25%, otherwise LOW; every line shows its evidence ("listed in 70% of the 40 most relevant postings").
* **Companies:** recommended jobs and the "companies with relevant jobs" table come from the retrieved postings. If you name a target company, requirements and jobs come from that company when it has postings titled like the role (title cosine ≥ 0.5); otherwise the app says it has none and lists the closest postings separately. An unknown company name returns spelling suggestions.

## 5. Resume Analysis

`backend/app/profile/resume.py`, `skills.py`, `service.py`; page `Resume Analysis`.

1. **Upload** a PDF (drag and drop or "Choose Resume"). Errors are explicit for: not a PDF, empty file, corrupt PDF, password-protected, scanned image with no text, more than 8 MB. You can always enter a profile manually instead.
2. **Extract text** (`pypdf`), clean it (Unicode normalisation, bullets, line-wrapped words).
3. **Sections** (Summary, Skills, Experience, Education...), then:
   * *Current role*: the first role-like line of the Experience section (e.g. "Senior Cloud Engineer").
   * *Department*: "Department: X" if stated, otherwise inferred from the role by keyword rules and labelled "inferred" in the UI.
   * *Experience*: "7 years of experience" if stated, otherwise the union of the job date ranges.
   * *Skills*: items of the Skills section (category labels removed, bracketed lists split) plus skills recognised elsewhere in the text. Variants are normalised ("K8s", "Amazon Web Services", "PowerBI", "HashiCorp Terraform").
4. **Review and edit.** Every field is editable; skills can be removed or added. Nothing is used until you press **Confirm Profile**.
5. **Unknown skills are never discarded.** The skill list of the job data (240 skills) is a recognition aid, not a filter. A skill not in it (for example "Cloud Architecture") is kept as a *custom* skill and takes part in matching. (The earlier ESCO-based version dropped valid skills such as `sql` and `powerbi`; ESCO has been removed.)
6. Name and contact details are not extracted; the file is not stored.

## 6. Research Mode

The **Research Mode** switch (top right) adds IR evidence to every search result and job page; the **Research Mode** page traces one query through the whole pipeline: tokens, removed words, stems, word pairs, skills named in the query, zone routing, postings, query vectors (TF, log-TF, DF, IDF, weight, normalised), candidates, hybrid formula and ranking table, per-term TF/DF/IDF/TF-IDF/contribution tables, and the same query under the keyword, TF-IDF and BM25 systems. Zone and score weights can be changed with sliders and the ranking is recomputed.

## 7. Evaluation

**Evaluation measures retrieval quality, not anyone's career eligibility.** *Precision@K*: of the top K listings, how many are relevant. *Recall@K*: of all relevant listings, how many are in the top K. *AP@K*: average precision (rewards relevant listings early). All numbers are computed (`backend/app/evaluation.py`); nothing is typed in.

* **Judgments:** 35 queries with relevance *rules* over real fields (`evaluation/judged_queries.json`): role queries (relevant = the dataset's own role label), role + country, role + skills, role + company, skills only. Written before the systems were compared; dev/test split fixed in the file. Relevance comes from metadata, not from people reading each posting, and the skills-only queries are close to circular. Say so when presenting.
* **Fairness:** listings often tie, so every system breaks ties randomly and results are averaged over 10 fixed seeds.
* **Recall@5 is small by construction** (e.g. 5 of 9,589 relevant listings); the per-query table shows each query's ceiling.

Held-out **test** split (17 queries; weights were *not* tuned on these):

| System | P@5 | R@5 | AP@5 | nDCG@10 |
|---|---|---|---|---|
| Keyword baseline | 0.800 | 0.024 | 0.743 | 0.831 |
| TF-IDF (flat) | 0.659 | 0.021 | 0.592 | 0.716 |
| TF-IDF + Jaccard (flat) | 0.729 | 0.021 | 0.690 | 0.783 |
| BM25 (extra, outside the syllabus) | 0.819 | 0.026 | 0.741 | 0.842 |
| **Hybrid CareerLens** | 0.776 | 0.027 | 0.739 | 0.828 |

All 35 queries (tuned weights used the dev half, so these favour CareerLens): P@5 0.840, AP@5 0.796 versus keyword 0.787 / 0.726.

**Honest reading:** on held-out queries CareerLens is **about as good as the keyword baseline and BM25 and not significantly better** (paired randomization p ≥ 0.47 on P@5); it is clearly ahead of flat TF-IDF (AP@5 0.739 vs 0.592) and of flat TF-IDF + Jaccard (0.690). Removing zone routing costs 0.139 AP@5 and removing Jaccard 0.080. The Work type zone changes nothing on these judged queries because none asks for a work type (a unit test verifies it works). With 17 test queries, small differences are not statistically meaningful.

## 8. Demo resumes

Three **fictional** PDFs in `docs/demo-resumes/` (made by `tools/make_demo_resumes.py`), also available as "Demo Profiles" on the Resume Analysis page. They go through the same pipeline as an uploaded file. Same target role (Cloud Architect), computed Career Fit: **strong 72%**, **partial 38%**, **weak 0%**. Details: `docs/demo_resumes.md`. A 5-minute presentation script: `docs/DEMO_SCRIPT.md`.

## 9. Architecture and files

```
backend/app/ir/         preprocess.py index.py jobs.py (zones, routing, scoring, Top-K, trace) dedup.py diversity.py
backend/app/profile/    skills.py (normalisation, never a filter) resume.py (PDF -> profile) service.py (upload + demos)
backend/app/career.py   Career Fit, skill gap, preparation plan, career transition, company targeting
backend/app/evaluation.py  main.py (FastAPI) schemas.py analytics.py config.py
backend/scripts/build_index.py   backend/tests/ (61 tests)
frontend/src/pages/     Home Search JobDetail Transition Resume Evaluation Research
frontend/src/components/ErrorBoundary.tsx   lib/ (api with response checks, validated store)
data/jobs/              jobs.csv (working corpus)  DATASET.json  NOTICE.md
data/skills/            skills_dim.csv (vocabulary for recognising skills in resumes)
evaluation/             judged_queries.json  results/eval_results.json  results/tuning.json
tools/                  build_dataset.py (raw CSV -> jobs.csv)  make_demo_resumes.py
docs/                   API.md demo_resumes.md DEMO_SCRIPT.md REPORT_NOTES.md demo-resumes/
```

The frontend never trusts an API response shape unchecked, an error boundary shows the real error instead of a blank page, saved browser data is validated on load, and every `useEffect` has a block body (the cause of an earlier `destroy is not a function` crash was an effect returning the result of `window.scrollTo`).

## 10. Limitations

* No job descriptions: matching uses titles, skill lists, company, location and work type only. No preferred skills, experience or URL.
* The corpus is a data and cloud oriented 2023 sample (it over-represents cloud roles); thin roles (system administrator, finance) have little evidence, and the app shows how many postings each analysis rests on.
* Retrieval quality is on par with strong lexical baselines, not better. Relevance judgments are rules over metadata.
* The dataset's remote flag is imperfect (postings titled "Remote" with the flag false exist).
* Career Fit is a transparent heuristic with hand-set weights (75/25), not a prediction of hiring success. Resume parsing is rule-based and assumes a conventional layout; always review the extracted profile.
* Startup takes about 30 to 60 s the first time (index build), then about 6 s.

## 11. Future work

Description text if a richer dataset is used; learned weights (learning to rank) on human judgments; experience and seniority matching; linking postings to a skills taxonomy as an *optional* enrichment (never a filter); dense retrieval as a second signal.

## 12. AI-use declaration

Claude (Anthropic) was used in a conversational coding session to design the architecture, write the backend, front end, tests and documentation, and to debug. It also ran the tests, the evaluation and a headless-browser end-to-end test. The team reviewed and directed the work. **Edit this paragraph to match exactly what your team did.** No language model or neural network runs inside CareerLens: all retrieval, scoring, resume parsing and matching are classical, deterministic code. Libraries: FastAPI, Pydantic, NLTK (Porter stemmer only), pypdf, React, Vite, Recharts, lucide-react; reportlab and pytest for development.

An earlier version of this project used the EU's ESCO classification as an optional vocabulary; it was removed because it filtered out valid skills.
