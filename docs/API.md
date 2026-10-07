# CareerLens API

Base URL `http://localhost:8000` (interactive docs at `/docs`). JSON in and out; errors are `{"detail": "<readable message>"}` with status 422 (invalid input, unknown company, bad PDF; resume errors also carry `"code"`), 404 (unknown job or demo) or 503 (index still loading).

| Method and path | Purpose |
|---|---|
| `GET /api/health` | status, number of listings, index build time |
| `GET /api/meta` | dataset facts and license, zones and weights, filter options, Career Fit weights and thresholds, the no-profile message |
| `POST /api/search` | ranked results for a query; optional `filters`, `sort`, `debug`, `config`, and a confirmed `profile` |
| `GET /api/jobs/{id}?q=` | one job, IR evidence for the query, similar jobs |
| `POST /api/jobs/{id}/explain` | same, plus Career Fit, covered/missing skills and preparation recommendations when a profile is sent |
| `GET /api/jobs/{id}/similar` | job-to-job retrieval (Title + Skills vectors) |
| `POST /api/compare` | 2 to 4 jobs side by side (shared skills, optional Career Fit) |
| `GET /api/companies?q=` | company suggestions with listing counts |
| `GET /api/skills/suggest?q=` | skill suggestions from the job data's skill list |
| `GET /api/resume/demos` | the three fictional demo profiles |
| `POST /api/resume/analyze` | multipart PDF upload -> extraction steps, suggested profile, warnings (user must confirm) |
| `POST /api/resume/demo/{strong\|partial\|weak}` | the same pipeline run on a bundled demo PDF |
| `POST /api/profile` | normalise a profile (skills normalised and de-duplicated, never dropped); nothing is stored |
| `POST /api/career-transition` | profile + target role (+ optional company) -> Career Fit, skills to have/develop, preparation plan, recommended jobs, companies |
| `POST /api/research/trace` | every intermediate artefact of one search (postings, vectors, scores, system comparison) |
| `GET /api/analytics` | dataset statistics |
| `GET /api/evaluation`, `POST /api/evaluation/run` | cached / recomputed retrieval evaluation |

## Search

```json
{"query": "cloud architect aws terraform", "k": 10, "filters": {"company": ["Nordcloud Finland"], "country": ["Finland"]},
 "sort": "best", "debug": false, "profile": {"current_role": "System Administrator", "skills": ["AWS", "Linux"]}}
```

`filters` fields: `company`, `country`, `workplace`, `schedule`, `role_family`. Each result has `ir_relevance`, `cosine`, `jaccard`, `zone_scores`, `matched_terms`, `reasons`, and `career_fit`.
**The profile never changes retrieval** (tested): `career_fit` is `null` for every result and `personalization` is `{"available": false, "message": "Personalized Career Fit unavailable. Upload your resume or enter your skills."}` when no usable profile is sent.

## Career transition

```json
{"profile": {"current_role": "System Administrator", "department": "IT Infrastructure", "experience_years": 4, "skills": ["AWS", "Linux", "Networking", "Python"]},
 "target_role": "Cloud Architect", "target_company": "Microsoft"}
```

Returns `career_fit` (target role), `have`, `to_develop` (with `prevalence` and `priority`), `other_skills` (kept, not required), `preparation_plan`, `recommended_jobs` (with `ir_relevance`, `career_fit`, covered and missing skills), `companies`, `company_status`, `closest_at_company`, `requirements` (postings read, thresholds) and `notes`.
Empty profile -> 422 with the no-profile message; unknown target role -> 422 with suggestions.
