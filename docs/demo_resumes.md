# Demo resumes

Three **fictional** candidates (invented names, `example.com` e-mail addresses, `555-01xx` phone numbers, and a footer saying
"DEMO PROFILE: fictional candidate"). They are real, text-based PDFs created by `tools/make_demo_resumes.py` and are also offered as
"Demo Profiles" on the Resume Analysis page. A demo goes through exactly the same pipeline as an uploaded file
(PDF text -> sections -> role / department / experience / skills -> you review and confirm). Nothing is pre-filled.

All three target **Cloud Architect**. The results below were produced by CareerLens (40 relevant postings read for the target role);
none of these numbers is hard-coded, and `backend/tests/test_career.py` only asserts their *order*.

| | 1. Strong | 2. Partial | 3. Weak |
|---|---|---|---|
| File | `strong-cloud-architect-match.pdf` | `medium-cloud-architect-match.pdf` | `weak-cloud-architect-match.pdf` |
| Current role / department (extracted) | Senior Cloud Engineer / Cloud & DevOps | System Administrator / IT Infrastructure | HR Executive / Human Resources |
| Experience (extracted) | 7 years | 5 years | 4 years |
| Skills detected (known to the job data / total) | 12 / 18 | 8 / 22 | 3 / 15 |
| **Career Fit for Cloud Architect** | **72%** | **38%** | **0%** |
| Skills the role asks for that the profile has | Azure, AWS, Python, Terraform, Kubernetes, Linux | AWS, Python, Linux, Windows | none |
| Skills to develop | 6, all LOW (GCP, Spark, Jira, SQL, Windows, PowerShell) | 8: Azure (HIGH), Terraform (MEDIUM), GCP, Spark, Kubernetes... | 12: Azure (HIGH), AWS (HIGH), Python (MEDIUM), Terraform (MEDIUM)... |
| Top recommended jobs (by Career Fit) | LEGO "Senior Engineer, Cloud Architect" 78% | Noovle "Cloud Architect" 75%, Aivix "Cloud Architect/Data engineer" 75% | every Cloud Architect posting scores 0% |

Natural-language variations in the PDFs: "K8s", "container orchestration", "HashiCorp Terraform", "AWS cloud infrastructure", "Amazon Web Services".
Skills the job data does not list (for example Cloud Architecture, Cloud Security, Active Directory, VPN) are kept as *custom* skills in the profile; they are not discarded and they count in matching when a job lists a matching skill.

Why Career Fit differs from the extracted skill count: Career Fit weighs each required skill by how often the best-matching "Cloud Architect" postings list it
(Azure 70%, AWS 65%, Python 34%, Terraform 32%...), so having Azure and AWS counts far more than having Jira.

## Suggested demo order

Weak -> Partial -> Strong on the same target role: the gap shrinks from 12 skills to 8 to 6, and the recommended jobs change with the profile.
Then add a missing skill (for example Kubernetes) to the partial profile in the edit form and confirm again: Career Fit rises from 38% to 44%.
