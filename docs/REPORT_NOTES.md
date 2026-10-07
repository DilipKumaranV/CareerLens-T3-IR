# Report notes (CSD358)

**Title.** CareerLens: an explainable Information Retrieval platform for job discovery and career transition planning (track T3).

**Problem.** Job search returns lists without reasons and says nothing about the gap between a person and a role. Existing tools mix "relevant to your search" with "right for you".

**Novelty (claim only what the evidence supports).** None of the components is new alone; the contribution is their combination and its transparency.
1. *Two separate scores.* IR Relevance (query vs job) and Career Fit (confirmed profile vs job or target role) are computed by different modules; a test proves a search never changes with the profile and never creates skills.
2. *Target-role requirements measured from retrieval.* The skills a role needs are the IR-weighted prevalence of skills in the top-ranked postings for that role, with the number of postings shown; missing skills get priorities with evidence. Nothing is hard-coded.
3. *Zone routing.* A query word is looked up only in the fields where it is a main field; exact title matches score 0.89 instead of 0.64.
4. *Transparent resume-to-profile pipeline* that keeps unknown skills and requires user confirmation.

**Method.** See README sections 3 to 5. **Evaluation.** README section 7 (held-out test split; honest conclusion: on par with keyword and BM25, ahead of flat TF-IDF).

**Limitations.** README section 10. **Work division.** [TEAM: fill in; no marks attach to it]. **AI use.** README section 12 [TEAM: edit so it is true].

**Mistakes found and fixed during development (worth one paragraph):** skills were dropped by an ESCO vocabulary filter (removed); an earlier Career Fit computed "skills you cover" from the search text (now impossible by construction and tested); dilution of scores by irrelevant fields (zone routing); a React effect returning `window.scrollTo`'s result caused `destroy is not a function` (all effects now have block bodies, regression-tested).
