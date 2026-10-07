# Dataset notice

`jobs.csv` is derived from **data_jobs** by Luke Barousse: https://huggingface.co/datasets/lukebarousse/data_jobs
License: **Apache-2.0** (as stated on the dataset card). The postings were collected from Google Jobs through SerpAPI in 2023 and belong to their employers.

Changes made (as Apache-2.0 requires us to state): rows with no skills list or no title were dropped; re-postings with the same title,
company and location were merged into one listing (the number merged is kept in `listings`); company spellings were canonicalised;
columns were renamed; skills were split into a `|`-separated list; a working sample was selected (every cloud/infrastructure/architect
title plus a seeded random sample of the rest, see `tools/build_dataset.py` and `DATASET.json`). No data was added.

A copy of the Apache-2.0 license is at https://www.apache.org/licenses/LICENSE-2.0.
`data/skills/skills_dim.csv` (259 skill names with a type) comes from the same collection's skills table and is used only to recognise skills in resumes.
