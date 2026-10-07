# Five-minute demo

Prepare: start backend and frontend (README section 1). Open http://localhost:5173. Switch **Research Mode** off.

1. **Problem (30 s).** Home page. "Job search shows results but not why, and tells you nothing about the gap between you and a role. CareerLens does both with classical IR." Point at the two-score box: IR Relevance vs Career Fit.
2. **Search, no profile (60 s).** Find Jobs -> "Cloud Architect". Real companies, locations, skills. Note the banner *"Personalized Career Fit unavailable. Upload your resume or enter your skills."* and that cards show IR Relevance only. Filter by company "Nordcloud Finland".
3. **Show the IR (60 s).** Switch **Research Mode** on. One result expands to TF, DF, IDF, TF-IDF, cosine, Jaccard and the contribution of each term; the contributions sum to the cosine. Open the **Research Mode** page for "cloud architect aws terraform": tokens, zone routing, postings, query vectors, final ranking table, and the same query under keyword / TF-IDF / BM25.
4. **Resume (60 s).** Resume Analysis -> upload `docs/demo-resumes/medium-cloud-architect-match.pdf` (or its demo card). Show extracted role, department, experience and skills; edit one; note the dashed *custom* skills that are kept. **Confirm Profile**.
5. **Career transition (60 s).** Analyze Career Transition -> Cloud Architect: Career Fit 38%, skills you have, skills to develop with HIGH/MEDIUM/LOW and their evidence, recommended jobs with company and per-job fit. Type company "Microsoft": the app says it has no Cloud Architect title and lists the closest postings instead of pretending.
6. **Contrast (30 s).** Repeat with the strong (72%) and weak (0%) PDFs. "Same target, different profile, different answer: nothing is hard-coded."
7. **Evaluation (45 s).** Evaluation page: definitions of Precision@K and Recall@K, five systems, held-out test numbers. Say it plainly: on held-out queries CareerLens is about as good as the keyword baseline and BM25, ahead of flat TF-IDF; relevance judgments are rules over metadata; it measures retrieval, not your eligibility.
8. **Limitation (15 s).** No job descriptions or experience in the dataset, so Career Fit uses skills and role title only.
