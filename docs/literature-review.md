# Literature review workbook

**Status:** a structured starting point. This is not a completed systematic review and contains no invented study findings or screening counts.

## 1. Review objective

Establish what existing work says about automated security reporting, database remediation advice, evidence attribution, and retrieval-assisted generation. Determine whether the candidate gap in the proposal is defensible. The three user-specified RQs remain the study's questions; the supplied guide determines document structure rather than content claims.

## 2. Search protocol

Search IEEE Xplore, ACM Digital Library, Scopus or Web of Science if available, the ACL Anthology, and arXiv as a separately labeled preprint source. Search official OWASP guidance and database vendor documentation for control definitions and engine-specific applicability. Record the databases actually accessible; lack of access is a limitation, not a reason to invent coverage.

Use and refine these search strings, recording every actual query and date:

- `(database OR SQL OR PostgreSQL OR MySQL) AND (security report OR vulnerability report) AND (language model OR generative AI)`
- `(vulnerability OR security finding) AND remediation AND (retrieval OR RAG OR language model)`
- `(evidence grounding OR factual consistency OR citation support) AND (language model OR report generation)`
- `(OWASP OR database security) AND (retrieval augmented generation OR automated reporting)`

Begin with work from 2020 onward for retrieval/language-model applications, retaining earlier foundational security-reporting work identified by backward citation search. Record the final search cutoff before submission. Conduct backward and forward citation searches for included studies; log duplicates and exclusions. A second reviewer should check a subset of screening decisions.

## 3. Eligibility

Include peer-reviewed empirical studies relevant to security report generation, remediation, retrieval, factual support, or citation evaluation. Include influential foundational methods with a stated role. Include official guidance as normative/control sources, separately from empirical studies. Preprints may be included but must be labeled and checked for later published versions.

Exclude promotional claims without reproducible methods, duplicate versions when a later definitive version exists, and papers whose full text cannot support the required extraction; document the last category as unavailable rather than implying it was critically reviewed. Retain negative findings and studies that challenge the proposed system.

## 4. Seed references and limited current use

| Source | Established role in this proposal | What it does not establish |
|---|---|---|
| OWASP, Database Security Cheat Sheet. https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html | General database control guidance and corpus candidate | Model effectiveness, engine-specific executable correctness, or complete compliance |
| OWASP, SQL Injection Prevention Cheat Sheet. https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html | SQL injection prevention control guidance and corpus candidate | That a supplied finding actually proves SQL injection |
| P. Lewis et al., Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks, NeurIPS 2020. https://arxiv.org/abs/2005.11401 | Foundational retrieval-conditioned generation method | Effectiveness for database security reporting in this project |
| T. Gao, H. Yen, J. Yu, D. Chen, Enabling Large Language Models to Generate Text with Citations, EMNLP 2023. https://aclanthology.org/2023.emnlp-main.398/ | Citation-oriented generation/evaluation reference | That citation presence guarantees support or useful remediation |
| Z. Ji et al., Survey of Hallucination in Natural Language Generation, ACM Computing Surveys 55(12), 2023. https://doi.org/10.1145/3571730 | Factual reliability and hallucination background | A measured hallucination rate for the proposed system |

These bibliographic seed records are supplied from established publications. This task has not completed full-text critical appraisal of them. Do not invent access dates, quotations, effect sizes, datasets, or performance comparisons. Verify publisher metadata and archive lawful source details when completing the review. The app's OWASP corpus manifest, when available, is the authority for exact source revisions used by retrieval.

## 5. Extraction and quality-assessment matrix

Copy a row for every included study after reading its full text. Empty entries mean work remains; they are not negative findings.

| Field | Extraction rule |
|---|---|
| Citation and publication status | Publisher metadata, year, DOI/URL, peer-reviewed or preprint |
| Research problem | Exact task and claimed contribution in neutral language |
| Context | Security domain, database engines, artifacts and user population |
| Data | Origin, number of independent scenarios, licensing and split strategy |
| Model and retrieval | Model/version, corpus/version, retriever, chunking, top-k, prompts |
| Baselines and ablations | Whether comparisons isolate evidence, retrieval, or another change |
| Reference answers | Who annotated, expertise, independent judgments and adjudication |
| Measures | Definitions, denominators, failure treatment, uncertainty and cost |
| Main findings | Exact supported result with page/table reference; no inference beyond paper |
| Limitations | Author-stated limits and reviewer critique |
| Reproducibility | Available code/data and what was actually inspected or rerun |
| Relation to RQ1/RQ2/RQ3 | Specific relevance and differences from this project |

| Study | Task/data | Model/retrieval | Baseline/ablations | Human ground truth | Findings and source location | Limits | RQ relevance |
|---|---|---|---|---|---|---|---|
| To be filled after screening and full-text review | Pending | Pending | Pending | Pending | Pending | Pending | Pending |

## 6. Thematic synthesis plan

**Database controls and reporting:** distinguish discovery of vulnerabilities from faithful reporting of existing findings. Summarize control principles and identify where vendor documentation is necessary.

**AI reporting and remediation:** compare task scope, input evidence, database specificity, and evaluation by qualified humans. Identify whether outputs were checked for correctness or merely readability.

**Evidence grounding and attribution:** distinguish access to evidence, instructions to cite it, structural citation validity, and semantic support. Compare annotation granularity and handling of missing or contradictory evidence.

**Retrieval and source use:** compare corpus authority, revision control, chunking, retrieval relevance, and generation use of passages. A retrieval improvement may not yield a report improvement.

Within each theme, organize empirical studies chronologically and connect the evolution of methods to current limits. Do not turn a list of papers into a novelty claim without showing the specific unresolved comparison.

## 7. Candidate gap and falsification

Candidate gap: limited controlled evidence about the separate and joint effects of evidence grounding and OWASP retrieval for database-specific report correctness and remediation applicability under incomplete evidence. This statement is provisional. If comparable studies already answer it, narrow the contribution to an independently reproduced benchmark, a new engine/evidence setting, or an identified methodological limitation. A finding of no defensible gap should change the proposal rather than be hidden.

## 8. Search log template

| Date | Database/source | Exact query | Returned | Screened | Included | Exclusion reasons / notes |
|---|---|---|---|---|---|---|
| Not yet executed | — | — | — | — | — | — |

## 9. Citation practice

Number final thesis references in first-appearance order, using IEEE formatting as recommended in the guide. Use a reference manager or Word citation tools to avoid duplicates. Save normative OWASP and vendor references separately from empirical study extraction. Record real access dates for living pages and exact source revisions/checksums for the experiment corpus.
