# Implementation and research status

This document separates the implemented prototype from the planned empirical study. It describes the initial artifact; use the repository's `VALIDATION.md` for actual software checks and their current outcomes.

## Implemented prototype

- FastAPI application and Vietnamese web interface for supplied JSON findings/evidence, generation settings, report review, and Markdown/JSON export.
- Input schema and cross-reference validation; supplied PostgreSQL/MySQL/Other engine labels, category and severity metadata. Severity is preserved rather than independently assessed.
- Best-effort redaction before context construction and report persistence. This is not a complete sensitive-data detector; evidence must already be sanitized.
- Offline lexical BM25 retrieval over four official OWASP Cheat Sheet snapshots with revisions, source URLs, attribution, and checksums. This is not embedding retrieval or a demonstration of retrieval relevance.
- Deterministic template generation for a credential-free functional demo, plus native Gemini REST generation with structured JSON/schema and citation-ID guards. Legacy OpenAI-compatible configuration remains supported. Provider failure does not silently become a template result.
- Four grounding/retrieval combinations. Grounding off omits evidence contents/IDs from generator context; retrieval off omits OWASP passages. Grounding therefore changes evidence access and instructions. Retrieval queries are based on finding metadata across grounding levels.
- SQLite report persistence, report provenance, and structural diagnostics. Citation validity and finding coverage are engineering measures, not expert factual judgments.
- CLI and web experiment runners with randomized order, repeated conditions, retained failure records, machine-readable reports, and a blank expert coding CSV aligned with the protocol's 0–3 rubric. Web runs can export a ZIP with case/cluster/split/DBMS metadata, code and prompt hashes, source revisions, and provider-reported tokens/modelVersion for successful generations.

The API's `supported` finding status and `summary.confirmed` count mean that generated claims carry structurally valid evidence references. They do **not** establish semantic support, a confirmed vulnerability, or a correct remediation. The report provenance states `semantic_validation=not_performed`.

## Not yet established

- No live language-model provider has been configured and validated as part of this implementation. A mock/provider-response test exercises code behavior, not real model quality.
- The supplied cases are synthetic software fixtures. They are not an independently annotated research dataset, a gold standard, or evidence for the RQs.
- The target of 120 cases in 40 scenario/environment clusters is a proposed sampling plan, not an existing dataset or a completed experiment.
- No expert factual, entailment, completeness, remediation, or OWASP applicability scores have been collected. The runner deliberately leaves them blank.
- No completed systematic literature search or verified novelty claim is asserted. The literature workbook contains seed references and a protocol awaiting execution.
- Cluster-level statistical analysis, agreement calculation, retrieval relevance assessment, billed-cost calculation, final reviewer blinding packages, and power/precision planning remain research work. Tokens and model version are retained when the provider returns them; missing metadata is not invented. The runner does not implement every planned manifest field or analysis.
- The case schema does not include gold annotation or severity uncertainty. The web study form separately records scenario cluster ID, split and engine version in the experiment manifest; CLI datasets still need a separate versioned split/annotation mapping. Do not infer independent sample size from filenames, repeated outputs, claims, or individual recommendations.
- Raw rejected provider outputs are not retained; safe failure codes are retained. Declare this deviation from the proposed protocol's raw-output preservation plan and do not claim a complete semantic audit of rejected outputs.
- No application performs live database scanning or remediation execution. The prototype does not supply production authentication, multi-tenant access control, encrypted artifact storage, or a complete data-retention policy.

## What is required to answer the RQs

Complete the literature review and qualified human annotation, freeze the exact experimental intervention and split manifests, run the same real model under all four conditions, and have reviewers assess the held-out outputs against the protocol. Retain generation failures and distinguish structural from semantic measures. Only then populate Chapters 4–6 with measured outcomes and uncertainty. Software readiness and a working demo alone do not establish an answer to RQ1, RQ2, or RQ3.
