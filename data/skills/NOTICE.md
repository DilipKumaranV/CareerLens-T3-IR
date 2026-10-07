# Skill vocabulary notice

`skills_dim.csv` (259 skill names with a type) is the skills dimension table of Luke Barousse's "data_jobs" collection of
2023 job postings (https://huggingface.co/datasets/lukebarousse/data_jobs , license: Apache-2.0 per the dataset card).
The copy used here was read from a public GitHub repository that republishes the tables
(abuhamza11995-cmd/SQL_Project_Data_Job_Analysis); that repository carries no license of its own.
The vocabulary is used to recognise skills in resumes. It is a recognition aid only: skills that are not in it are kept as
"custom" skills and still take part in matching; they are never discarded.
