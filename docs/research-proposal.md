# Evidence-Grounded AI Assistance for Database Security Test Reporting and OWASP-Aligned Remediation

**FPT University — Capstone Research Thesis Proposal**  
Group members and student IDs: [to be completed]  
Supervisor: [to be completed]  
Project code and submission date: [to be completed]  
Status: proposal and implementation plan; research experiments have not yet been conducted.

## How this proposal uses the supplied guide

The uploaded *The Student’s Guide of Research Thesis Document for the FPT University Students (For IA specific purposes)* supplies the six-report thesis structure, document conventions, milestone schedule, and assessment weights. It is not a system requirements specification or a source of research questions. This proposal uses the user's three research questions below. Thesis documents are written in English, following the guide; the demonstration interface may use Vietnamese. Supervisor review should resolve institutional formatting and milestone ambiguities before submission.

## Abstract

Database security testing produces findings, configuration observations, and execution traces that must be translated into understandable reports and practical corrective actions. Language models can assist this translation, but fluent output may omit important details, exaggerate the implications of limited observations, or recommend controls without a verifiable connection to the tested system. This research proposes an assistant that generates database security test reports from supplied findings and evidence and recommends remediation aligned with guidance from the Open Worldwide Application Security Project. The study focuses on reporting accuracy, completeness, evidence traceability, remediation appropriateness, and the effect of evidence grounding and retrieval of security guidance. A prototype will normalize findings, preserve evidence identifiers, retrieve relevant passages from a versioned guidance collection, and produce structured reports for human review. A controlled factorial experiment will compare the same language model under four combinations of evidence grounding and retrieval. Independent security reviewers will create reference annotations and assess anonymized outputs using a predefined rubric. Measurements will include supported claim precision, required fact coverage, citation correctness, remediation applicability, retrieval relevance, abstention quality, latency, and cost. Scenario-level separation between development and evaluation data will reduce leakage, while paired analyses and confidence intervals will describe uncertainty. No experimental findings are claimed in this proposal. The expected contribution is a reproducible reporting artifact and an empirical assessment of when evidence and retrieved guidance improve assistance, where they fail, and which review controls remain necessary before recommendations are used in a real database environment.

**Keywords:** database security; security reporting; evidence grounding; retrieval-augmented generation; remediation; OWASP; empirical evaluation.

## Abbreviations

| Term | Meaning |
|---|---|
| AI | Artificial intelligence |
| DBMS | Database management system |
| RAG | Retrieval-augmented generation |
| OWASP | Open Worldwide Application Security Project |
| RQ | Research question |
| CI | Confidence interval |

# Chapter 1 — Introduction

## 1.1 Background

Security testing of a database-backed system can produce scanner output, access-control observations, sanitized query traces, configuration excerpts, and manual analyst notes. Reporting requires more than combining these artifacts. An analyst must distinguish an observation from an inferred vulnerability, preserve the affected asset and test conditions, explain the possible impact, and propose actions whose prerequisites match the database engine and application context. OWASP's database and SQL injection prevention guidance provides useful control principles, including restricted privileges and parameterized queries [1], [2]. These principles must be interpreted against the observed system rather than treated as a universal executable fix.

Language models offer a way to draft such reports. Their factual reliability and attribution remain empirical questions. Retrieval-augmented generation conditions output on external passages [3], while citation-oriented generation provides a framework for evaluating whether attributed statements are actually supported [4]. Neither a retrieved passage nor a syntactically valid citation proves that a database finding is correct. This project therefore distinguishes software validity, evidence support, and expert judgment.

## 1.2 Problem statement

The practical problem is a reproducible transformation from heterogeneous, supplied database security findings into a report that is accurate, sufficiently complete, and auditable. A second problem is selecting remediation that fits the actual finding and evidence, with an appropriate OWASP reference. A third problem is measuring the separate and combined contributions of evidence grounding and OWASP retrieval rather than attributing every improvement to a complete system.

Potential failures include inventing affected tables or privileges, changing severity without justification, interpreting missing evidence as a negative result, citing a relevant document that does not support the specific recommendation, and proposing engine-incompatible configuration changes. The project will measure these failures explicitly. It does not assume that the proposed approach is novel or superior before completing the literature review and experiments.

## 1.3 Research objectives and questions

**Objective O1:** implement structured, traceable generation of database security test reports and measure factual correctness, completeness, and evidence traceability.

**RQ1 — Security Report Generation:** How accurately and completely can an AI assistant analyze security findings and automatically generate database security testing reports, while preserving evidence traceability?

**Objective O2:** produce reviewable remediation recommendations connected to supplied findings, collected evidence, and relevant OWASP guidance; evaluate applicability and technical correctness.

**RQ2 — OWASP-Based Remediation Recommendation:** To what extent can an AI assistant recommend database security remediation measures that are appropriate to the security findings, collected evidence, and OWASP guidance?

**Objective O3:** estimate the main effects and interaction of evidence grounding and OWASP retrieval on the outcomes of O1 and O2.

**RQ3 — Evidence Grounding & OWASP RAG Effectiveness:** How does integrating evidence grounding and OWASP retrieval-augmented generation affect the accuracy of security finding analysis and the quality of the assistant's remediation recommendations?

These are translations of the user's questions, not replacements. The original Vietnamese questions are retained in Appendix A.

## 1.4 Significance and intended contribution

The intended engineering contribution is an inspectable prototype that links report statements and recommendations to stable evidence and guidance identifiers. The intended empirical contribution is a controlled evaluation package with de-identified cases, expert annotations, prompts, run manifests, and analysis definitions. A possible research contribution is identifying which types of incomplete or conflicting evidence benefit from grounding and which remediation categories benefit from retrieval. These remain intended contributions until demonstrated.

The artifact should help an analyst review a draft more quickly and locate the source of a claim. It is not intended to replace authorization for testing, expert approval of remediation, or an operational change process. “OWASP-aligned” means a reviewer can trace an applicable recommendation to cited guidance; it is not an OWASP certification or a claim of complete compliance.

## 1.5 Scope and limitations

The initial scope is PostgreSQL and MySQL cases represented as structured JSON findings and sanitized evidence. Categories include SQL injection, excessive privileges, insecure transport, exposed configuration, and insufficient audit controls where the selected corpus provides relevant guidance. The assistant consumes existing findings; it does not scan live databases, execute exploit payloads, run supplied SQL, or automatically apply fixes.

A local, deterministic template mode supports demonstration without external credentials. It is a software baseline, not an evaluated language model. Native Gemini API integration supports the planned language-model experiment, with an optional legacy OpenAI-compatible provider. The research run must fix an available model identifier and record the provider-resolved model version; a latest alias can drift. The initial retrieval method is lexical ranking over a frozen, sectioned OWASP corpus. This is a valid retrieval component but does not establish the performance of embedding-based or hybrid retrieval. Production authentication, multi-tenant authorization, encrypted artifact storage, retention controls, and operational remediation validation remain outside this prototype unless separately implemented and assessed.

Evidence can be incomplete, forged, contradictory, or contain instructions. Uploaded observations and retrieved passages must be treated as data, not as instructions that can change generation policy. Identifier checks establish referential integrity, not semantic entailment. OWASP guidance is general; engine-specific syntax and rollback requirements need an appropriate vendor reference and human verification before use.

## 1.6 Thesis structure

Report 1 introduces the problem and research questions. Report 2 provides a thematic literature review. Report 3 describes the artifact and evaluation methodology. Report 4 reports executed experiments and uncertainty. Report 5 interprets the results and limitations. Report 6 synthesizes supported conclusions and future work. This document drafts Chapters 1–3 and provides honest completion templates for Chapters 4–6.

# Chapter 2 — Literature Review

## 2.1 Review of previous studies and guidance

The review will connect four themes: database security controls, automated security reporting, factual reliability and attribution in language models, and retrieval evaluation. OWASP's Database Security and SQL Injection Prevention Cheat Sheets [1], [2] provide control guidance rather than empirical proof of model effectiveness. Lewis and colleagues introduce a retrieval-augmented generation approach [3]. Gao and colleagues study language-model generation with citations [4]. Ji and colleagues survey hallucination in natural language generation [5]. These sources motivate concepts and evaluation dimensions; they do not directly establish effectiveness for the proposed database-reporting task.

Within each theme, studies will be organized chronologically and appraised for data provenance, task similarity, experimental controls, human evaluation, reproducibility, and external validity. A reproducible search and extraction protocol is supplied in `literature-review.md`. The final review must include security-reporting and remediation studies found through that search; listing foundational work alone is insufficient.

## 2.2 Summary of the literature review

The current conceptual synthesis separates three sources of correctness: finding evidence determines what was observed; security guidance supports control principles; and expert review determines whether an interpretation or proposed action is appropriate to a particular engine and context. Retrieval and citation can make sources visible, but successful source lookup is not equivalent to source support. Factual correctness, coverage, and traceability must consequently be measured separately.

A provisional gap is the need to evaluate the independent and combined effect of evidence grounding and OWASP retrieval on database-specific report and remediation quality under incomplete evidence. This is a candidate gap, not a completed claim of novelty. It must be revised if the systematic search identifies equivalent work.

## 2.3 Intended contribution of this research

The project will contribute: (a) a structured artifact and input contract; (b) an expert-reviewed, scenario-separated evaluation design; and (c) an ablation study that can reveal positive, null, or adverse effects. The offline template mode provides a reproducible engineering reference. It must not be substituted for the same language model in any factorial comparison.

# Chapter 3 — Methodology

## 3.1 Research design

The study combines artifact development with a controlled, paired 2 × 2 experiment. The two factors are evidence grounding and OWASP retrieval. All four experimental conditions use the same language-model version, output schema, provider, decoding parameters, and resource limits. Prompt differences are restricted to the declared factors. The deterministic template generator is assessed separately as an engineering baseline.

The primary unit is a held-out scenario/environment cluster. Cases and repeated generations within a cluster are correlated observations, not additional independent samples. Three generations per case and condition are planned to assess stochastic variation; replication may be revised after a development-only feasibility pilot and documented before the test set is opened.

### 3.1.1 Artifact architecture

1. **Input validation:** validate engine, identifiers, severity, finding category, asset scope, and evidence references; reject malformed or dangling references.
2. **Evidence handling:** retain explicit evidence records, distinguish observations from supplied labels, redact secrets before ingestion, and mark missing or conflicting support for review.
3. **OWASP retrieval:** rank sections from an allowlisted, versioned corpus and expose source title, URL, revision, section identifier, and checksum. A passage is supporting material, not proof that the finding occurred.
4. **Generation:** produce structured finding analysis and remediation from the condition-specific context. The full condition requests uncertainty statements and explicit evidence and source references.
5. **Validation and review:** check structure and reference integrity, retain failures and abstentions, and require human review of factual and remediation correctness.
6. **Reporting and evaluation:** provide a readable report and machine-readable outputs; retain run configuration for reproducibility.

### 3.1.2 Operational definitions

“Evidence grounding” is an intervention whose exact implementation must be frozen before evaluation. In the proposed design, the enabled condition supplies evidence contents and asks for supported claims, citations, and abstention where support is inadequate; the disabled condition supplies normalized finding metadata without evidence payload. This estimates the combined value of evidence access and grounding instructions, not the effect of instructions alone. If the implementation uses another definition, the run manifest and final methods must be updated before the held-out run. A separate instruction-only sensitivity study can keep evidence access constant.

“OWASP RAG” supplies the same top-k retrieved guidance passages to the language model under both grounding settings. Retrieval off supplies no corpus passages. Outputs may mention OWASP from model memory, but those mentions are recorded as uncited unless connected to supplied corpus identifiers. A retrieval citation is correct only when the cited passage supports the recommendation and is applicable to the finding.

### 3.1.3 RQ-to-measure mapping

| RQ | Primary measures | Secondary measures | Reference basis |
|---|---|---|---|
| RQ1 | Supported claim precision; required fact coverage; evidence citation support | Unsupported claim rate; section coverage; severity agreement; review time | Expert factual propositions and minimum report requirements |
| RQ2 | Remediation technical correctness; applicability; OWASP support | Actionability; prioritization; verification quality; harmful advice rate | Expert acceptable-control sets and source relevance judgments |
| RQ3 | Paired differences and interaction in the RQ1/RQ2 primary measures | Retrieval recall@k and nDCG@k; latency; token use and cost | Same held-out cases under all four conditions |

Metrics and denominators are specified in `evaluation-protocol.md`; no single weighted score will hide a safety or correctness failure.

## 3.2 Data collection methods

The planned target is 120 cases grouped into 40 scenario/environment clusters. Ten clusters will be used for development and annotation calibration, and 30 clusters held out for evaluation. These are planning targets, not counts of an existing dataset. A development-only pilot will estimate annotation burden and precision; the final sample and stopping rule will be frozen before evaluation. The scope should be reduced transparently if recruitment or resources make the target infeasible.

Cases will come from authorized local laboratory scenarios and appropriately licensed, de-identified artifacts. No client production evidence or secrets will be included. Each case records engine and version when known, asset boundaries, finding metadata, evidence artifacts, provenance, uncertainty, and allowed control references. Variants with shared origin, configuration, or near-duplicate artifacts remain in the same split. Unsupported and negative-control cases are included to test abstention rather than rewarding confident reporting of every supplied label.

Two reviewers with database/security knowledge will independently annotate supported and contradicted propositions, required facts, acceptable remediation controls, applicable OWASP passages, and evidence sufficiency. A third reviewer or documented consensus resolves disagreement. Reviewers must not use model outputs to manufacture reference answers. The final dataset card records expertise, licensing, exclusions, redaction, and disagreement resolution.

## 3.3 Sampling and data analysis techniques

Sampling is stratified by engine, category, severity, evidence quality, and number of findings, subject to feasible cluster independence. The dataset is not a representative sample of all database vulnerabilities. Its strata and exclusions limit generalization.

Anonymized outputs will be randomized for independent expert scoring, with system identity hidden where possible. At least 20% of scored reports will be double-rated after calibration, and all severe factual or unsafe remediation judgments will receive second review. Agreement is computed before adjudication. A case-level failure to generate or validate remains in the intention-to-evaluate denominator; conditional scores on successful outputs are reported separately.

The planned primary comparisons are full system versus base model, grounding effect within retrieval levels, retrieval effect within grounding levels, and the difference-in-differences interaction. Case metrics are aggregated within scenario clusters before paired inference. Cluster bootstrap 95% confidence intervals and effect sizes are reported. Paired permutation procedures or mixed-effects models may be used if their assumptions and sample size are adequate; the final choice is preregistered after development and before test evaluation. Holm adjustment controls the declared family of confirmatory comparisons; exploratory analyses are labeled. No test-set-driven prompt optimization is allowed.

## 3.4 Limitations of the methodology

Expert annotations are imperfect and reviewers may infer the condition from visible citations. Synthetic lab evidence may be cleaner than operational artifacts. Selected engines and categories do not cover every database platform. Hosted model changes can impair repeatability even when a model identifier is retained. Giving evidence only to grounded conditions changes information availability as well as instructions. Retrieval and output length may change cost and reviewer effort. These limits must be discussed with the results rather than removed from the report because a metric improves.

## 3.5 Ethics, security, and data handling

Use only authorized laboratory or licensed artifacts and remove passwords, tokens, personal records, and internal identifiers before ingestion. External model use requires an approved provider and informed acceptance of its data handling; do not send unredacted evidence to an external endpoint. Evidence and retrieved text are untrusted data. The artifact must not execute recommendations or trust embedded instructions. Preserve access controls and retention rules around experiment outputs. Research judgments do not authorize production changes.

## 3.6 Implementation and validation plan

The minimum artifact is a FastAPI service and a web interface for supplied JSON cases, official-source retrieval, report generation, and export. Required engineering checks cover valid inputs, invalid references, missing evidence, source integrity, content escaping, provider failure, and a functional end-to-end report. An optional provider connection is verified only when available; a successful template run does not verify model output quality. The runtime and setup commands are documented separately in the repository README.

## 3.7 Schedule and six reports

The guide's milestone text contains overlapping durations. The schedule below uses its named submission weeks as anchors and requires supervisor confirmation; it is not a revised institutional rule.

| Week | Work and deliverable | Guide milestone / process weight |
|---|---|---|
| 1 | Agree scope, team roles, authorization, RQs, and proposal | Fix topic and group |
| 2 | Draft problem, objectives, scope, and initial bibliography | Prepare Report 1 |
| 3 | Submit introduction; continue thematic search and screening | Report 1: 10% |
| 4 | Submit literature review with search log and candidate gap | Report 2: 25% |
| 5 | Build input contract, corpus, evidence handling, prototype | Methodology development |
| 6 | Pilot annotations and model modes; freeze evaluation protocol | Prepare Report 3 |
| 7 | Submit methodology; freeze held-out dataset and run manifest | Report 3: 20% |
| 8 | Run planned experiments and expert scoring; retain failures | Experimental work |
| 9 | Submit initial experimental/results report using actual data | Report 4: 25% |
| 10–11 | Complete adjudication, uncertainty and sensitivity analysis | Refine reports and system |
| 12 | Demonstrate artifact and trace results to saved outputs | Show all work; mentor feedback |
| 13 | Submit discussion, conclusions, limitations and future work | Reports 5 and 6: 15% and 5% |
| 14 | Integrate thesis, IEEE references, figures, appendices | Complete thesis |
| 15 | Rehearse and present; archive reproducibility package | Capstone presentation |

The guide assigns 50% of the final project mark to the six-report process and 50% to the committee presentation. Individual marks follow institutional rules; no performance or grade is promised.

# Chapter 4 — Experimental and Results: completion template

**Status: experiments not yet executed. No effectiveness results are available.**

## 4.1 Introduction
Record the protocol version, preregistration date, actual case and cluster counts, engines, model identifier, provider, decoding settings, corpus revision, and deviations from Chapter 3.

## 4.2 Presentation of data
Populate a flow diagram of eligible, excluded, evaluated, failed, and scored cases. Provide all four condition counts, generation failures, latency distribution, token use and cost. Link every aggregate table to a versioned run manifest and anonymized judgments.

## 4.3 Analysis of results
Report per-condition RQ1 and RQ2 metrics, paired cluster differences, 95% confidence intervals, adjusted confirmatory tests, and the interaction. Include missing-evidence and contradictory-evidence strata. Report retrieval relevance separately from final answer support.

## 4.4 Interpretation of results
Explain the practical size and uncertainty of differences, including null or adverse outcomes. Do not convert citation presence into a factual-accuracy claim.

## 4.5 Comparison with literature
Compare only compatible tasks and measures. Explain differences in evidence type, engine scope, models, annotation, and retrieval setup.

## 4.6 Implications of the results
State which development or review decisions the observed data support and which remain untested. Clearly separate functional software tests from research outcome measurements.

# Chapter 5 — Discussion: completion template

**Status: awaiting actual experiment and review data.**

## 5.1 Restate the research problem and objectives
Answer RQ1, RQ2, and RQ3 separately using the corresponding measurements. Compare observed effects against the hypotheses, and discuss cases where the system abstained, failed, or produced unsupported recommendations.

## 5.2 Summarize key findings
Fill only from Chapter 4 results. Discuss alternative explanations, grounding versus evidence access, retrieval relevance versus model use, annotation disagreement, costs, and external validity. Do not describe expected improvements as findings.

# Chapter 6 — Conclusion and Future Work: completion template

**Status: empirical conclusions cannot be drawn yet.**

## 6.1 Conclusion
After experiments, synthesize the supported answer to each research question, the artifact contribution, practical boundaries, and remaining uncertainty. Keep this consistent with the final abstract and avoid claiming general database security improvement from report-quality measures alone.

## 6.2 Future work
Potential extensions include instruction-only grounding ablations, semantic or hybrid retrieval, more engines, controlled expert workflow studies, independently validated engine-specific remediation checks, and production data-governance controls. These are possible extensions, not promises of completed capability.

# References

[1] OWASP Foundation, “Database Security Cheat Sheet,” *OWASP Cheat Sheet Series*. https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html. Living guidance; use the runtime corpus manifest for the exact retrieved snapshot.

[2] OWASP Foundation, “SQL Injection Prevention Cheat Sheet,” *OWASP Cheat Sheet Series*. https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html. Living guidance; use the runtime corpus manifest for the exact retrieved snapshot.

[3] P. Lewis et al., “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,” *Advances in Neural Information Processing Systems*, vol. 33, 2020. https://arxiv.org/abs/2005.11401.

[4] T. Gao, H. Yen, J. Yu, and D. Chen, “Enabling Large Language Models to Generate Text with Citations,” *Proceedings of EMNLP*, 2023. https://aclanthology.org/2023.emnlp-main.398/.

[5] Z. Ji et al., “Survey of Hallucination in Natural Language Generation,” *ACM Computing Surveys*, vol. 55, no. 12, 2023. https://doi.org/10.1145/3571730.

These established references seed the review. This proposal does not claim a completed systematic review or invent access dates, study results, or unavailable quotations. Verify bibliographic details and archive permitted source metadata during the review.

# Appendix A — User-specified research questions in Vietnamese

**RQ1 – Security Report Generation:** Trợ lý AI có thể phân tích các security findings và tự động sinh báo cáo kiểm thử bảo mật cơ sở dữ liệu với mức độ chính xác, đầy đủ và khả năng truy xuất bằng chứng như thế nào?

**RQ2 – OWASP-Based Remediation Recommendation:** Trợ lý AI có thể đề xuất các biện pháp khắc phục lỗ hổng bảo mật cơ sở dữ liệu phù hợp với security findings, bằng chứng thu thập được và hướng dẫn OWASP đến mức nào?

**RQ3 – Evidence Grounding & OWASP RAG Effectiveness:** Việc tích hợp Evidence Grounding và OWASP RAG ảnh hưởng như thế nào đến độ chính xác phân tích security findings và chất lượng khuyến nghị remediation của trợ lý AI?

# Appendix B — Completion checklist

- Replace title-page placeholders with confirmed group and supervisor information.
- Complete and document the literature search; revise the candidate gap if necessary.
- Freeze the implemented factor definitions and the final evaluation protocol before accessing test cases.
- Collect expert reference annotations, permissions, source metadata, and de-identification records.
- Run the same language model in every ablation; retain all failures and repeated outputs.
- Populate Chapters 4–6 and rewrite the abstract only after actual measurements.
- Update the table of contents, list of figures, list of tables, and IEEE citation ordering before submission.
