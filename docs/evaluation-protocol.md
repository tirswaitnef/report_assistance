# Evaluation protocol

**Status:** proposed protocol, not an executed benchmark.  
**Protocol version:** 1.0 draft. Freeze after a development-only pilot and before opening held-out cases.  
**Owner / preregistration date / dataset version:** [to be completed].

## 1. Research questions and estimands

- **RQ1:** accuracy, completeness, and evidence traceability of generated database security test reports.
- **RQ2:** appropriateness of remediation to the finding, collected evidence, and OWASP guidance.
- **RQ3:** effects of evidence grounding and OWASP retrieval on RQ1/RQ2 measures.

Primary estimands are differences in mean cluster-level supported claim precision, required fact coverage, and remediation correctness between paired conditions. Evidence citation support and OWASP recommendation support are reported with explicit eligibility denominators. The interaction estimates whether the combined intervention exceeds the sum of its component effects on the chosen outcome scale; it does not itself explain the mechanism.

## 2. Experimental conditions

| ID | Evidence grounding | OWASP retrieval | Inputs |
|---|---|---|---|
| B00 | Off | Off | Normalized finding metadata |
| B10 | On | Off | Metadata, evidence contents, grounding/citation/abstention instructions |
| B01 | Off | On | Metadata and retrieved OWASP passages |
| B11 | On | On | Metadata, evidence, grounding instructions, retrieved OWASP passages |

All conditions use **the same language model**, exact version where exposed, provider, schema, generation budget, temperature, and nonfactor instructions. Template/offline mode is a separate engineering baseline; its results must never populate this table as if produced by a language model. The evidence intervention combines information access and grounding policy. An instruction-only follow-up must supply identical evidence to all conditions to isolate policy effects. The final thesis must describe the implemented modes exactly; any change to these definitions requires a protocol revision before the test run.

Use the same retrieval query construction and top-k under B01/B11, without reading gold annotations. Do not let evidence-aware queries silently change between those conditions unless explicitly declared as part of the intervention. Cache the retrieved results per case for controlled replay. Record prompt lengths and acknowledge that context length differs; optionally add a preregistered length-matched sensitivity analysis with noninstructional neutral context, clearly separate from the primary study.

## 3. Case construction and data split

Planned target: **120 cases in 40 scenario/environment clusters**, with 10 development clusters and 30 held-out evaluation clusters. These are targets, not a claim that a dataset already exists. A pilot can revise the target based on annotation effort and expected CI precision before test access; record the revision and do not stop early based on favorable results.

A cluster groups every variant from the same underlying application, database configuration, scenario seed, source artifact family, or near-duplicate finding. No such cluster crosses development and test splits. Use a seeded, stratified cluster assignment with a stored split manifest. The retrieval corpus contains public guidance only, never held-out case answers or annotations.

| Dimension | Planned coverage |
|---|---|
| Engine | PostgreSQL and MySQL; record version or unknown |
| Category | SQL injection, privilege excess, transport/configuration exposure, audit controls within corpus scope |
| Evidence quality | Sufficient, incomplete, contradictory, irrelevant, absent |
| Report complexity | Single finding and multiple related findings |
| Severity | Include low to critical and unknown/disputed severity; do not force equal strata if unrealistic |
| Adversarial data | Benign instruction-like text in logs or guidance fixtures to test boundary handling |
| Controls | Unsupported finding labels, negative cases, engine-incompatible remediation traps |

Only authorized laboratory observations or properly licensed, de-identified public artifacts are eligible. No production credentials, personal data, or client assets. Findings and evidence need distinct identifiers. Evidence records include acquisition context, sanitized content, timestamp when genuinely known, provenance, and a checksum. Do not invent timestamps or label scanner output as a verified exploit. Redactions must preserve enough structure for expert judgment and be recorded.

Reject or separately label cases whose rights, provenance, scope, or reviewer interpretability cannot be established. Save all exclusions with reasons. Include difficult valid cases rather than removing them after a model fails.

## 4. Gold reference construction

Two domain reviewers independently produce the following without viewing evaluated model outputs:

1. Atomic supported, contradicted, and indeterminate factual propositions per finding.
2. A minimum set of essential report facts and the evidence span supporting each one.
3. An evidence-sufficiency label and the appropriate uncertainty or abstention behavior.
4. Acceptable remediation control families with prerequisites, engine applicability, and unsafe/inapplicable alternatives.
5. Applicable OWASP sections and relevance judgments for retrieval evaluation.
6. Severity reference where justified, including an explicit unknown/disputed option.

Use development cases to calibrate the codebook. Resolve disagreements through a third reviewer or documented consensus. Preserve the independent labels and the adjudicated reference. Record reviewer expertise and conflicts of interest. Model-generated reviews may assist navigation but are not ground truth and cannot be the sole evaluator of their own outputs.

## 5. Human scoring codebook

Outputs are assigned randomized IDs and presented in randomized order. Hide model/provider/condition labels; acknowledge that citation presence can reveal the intervention. Use equivalent display formatting so cosmetic polish does not determine scores. Double-rate at least 20% of reports after calibration and all alleged severe errors. Report pre-adjudication agreement, not only post-consensus agreement.

### 5.1 Claim support

Split output into atomic checkable claims before coding. Mark each as supported, contradicted, unsupported, or not externally checkable. A claim about an observed vulnerability must be supported by finding evidence; OWASP advice alone cannot prove a vulnerability exists. Generic procedural recommendations are evaluated by the remediation rubric and are not counted as observed facts. Document ambiguous segmentation rules and double-code a sample.

### 5.2 Remediation rubric

Each dimension receives 0–3 with a short reason and cited source/evidence. Report dimensions separately.

| Dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Technical correctness | Incorrect or unsafe | Major correction needed | Mostly correct with minor caveat | Correct for stated engine/context |
| Applicability | Contradicts case | Generic or important prerequisite missing | Applicable with explicit caveat | Directly addresses supported finding |
| OWASP support | False attribution or incompatible source | Topic match without supporting passage | Supports control but limited specificity | Passage directly supports proposed control |
| Actionability | No meaningful action | Vague action | Clear action with some missing context | Clear scoped action and prerequisites |
| Verification | None or misleading | Generic check | Relevant check | Observable success criteria and relevant check |
| Risk awareness | Destructive/unbounded advice | Important tradeoff omitted | Tradeoff or uncertainty acknowledged | Appropriate review, rollback and dependency considerations |

Engine-specific configuration commands require vendor verification in addition to generic OWASP guidance. Do not award a high correctness score merely because prose sounds precise. Mark unsafe advice separately even if the mean rubric score is acceptable.

## 6. Metrics and denominators

Let S, C, and U be supported, contradicted, and unsupported checkable claims. Let M be the number of essential reference facts accurately included and N the number required by the reference.

- **Supported claim precision:** S / (S+C+U). If no checkable claims are produced, report undefined and record the abstention; do not assign perfect accuracy. A separate all-output success measure treats generation failures as zero.
- **Unsupported/contradicted claim rate:** (C+U) / (S+C+U), with C and U also shown separately.
- **Required fact coverage:** M/N, counted against expert essential propositions, not string overlap. If N=0, mark not applicable rather than impute a score.
- **Evidence citation validity:** number of cited evidence IDs that resolve / number of cited evidence IDs. This is structural integrity only.
- **Evidence citation support:** claims whose evidence citations support the claim / claims carrying evidence citations. Also report **evidence citation coverage:** evidence-dependent claims with a supporting citation / all evidence-dependent claims. No citations means support precision is undefined and coverage is zero when eligible claims exist.
- **OWASP citation support:** recommendations for which the cited passage supports the proposed control / recommendations with OWASP citations. Report citation coverage against all OWASP-eligible recommendations separately.
- **Remediation correctness/applicability:** mean reviewer dimension score and fraction of recommendations scoring at least 2, using the preregistered threshold; show per-case and per-cluster aggregates and harmful-advice counts.
- **Abstention quality:** report rates and accuracy separately for sufficient and insufficient evidence. Correct abstention must identify the missing support; unconditional refusal is not rewarded as complete reporting.
- **Retrieval recall@k:** number of expert-relevant corpus sections in top-k / all expert-relevant sections in the frozen corpus. Use cases with at least one relevant section and report ineligible cases. If relevance is graded, compute nDCG@k using the stored expert judgments and a fixed gain function. Report MRR for the first relevant section if useful.
- **Operational measures:** success/failure counts, schema validation failures, provider errors, median/p95 latency, input/output tokens and estimated billed cost. Record cost assumptions and rates; measured wall time is not model-only latency unless instrumented accordingly.

Automated reference resolution, section-presence, and schema checks support engineering validation. They do not estimate factual entailment, semantic completeness, or clinical-style/operational safety on their own. Do not label them as RQ answers.

### 6.1 Annotation CSV produced by the runner

`scripts/run_experiment.py` exports `expert-review.csv` with identifiers only; every human annotation cell is blank. A `row_type=finding` row is provided for each generated finding. A `row_type=remediation` row is provided for each recommendation, using a 1-based `remediation_index` within that finding. Duplicate the appropriate rows to retain independent reviewers and adjudication as separate records; assign real reviewer IDs. Failed generations remain in `runs.jsonl`, even though there is no generated text to score in the CSV.

On **finding rows**, qualified human coders segment and judge the entire finding output, including its analysis, rather than counting only the model's explicit `claims` array. Enter nonnegative integer counts in `supported`, `contradicted`, `unsupported`, `essential_covered`, and `essential_total`. The factual denominator is `supported + contradicted + unsupported`; the coverage numerator must not exceed `essential_total`. Enter the evidence citation counts and OWASP recommendation counts as defined below. These counts require the independent reference annotations and source review, not only software checks.

| CSV numerator | CSV denominator | Protocol measure |
|---|---|---|
| `evidence_citation_supported_claims` | `evidence_citation_claims_total` | Evidence citation support |
| `evidence_dependent_claims_with_supporting_citation` | `evidence_dependent_claims_total` | Evidence citation coverage |
| `owasp_supported_cited_recommendations` | `owasp_cited_recommendations_total` | OWASP citation support |
| `owasp_eligible_recommendations_with_supporting_citation` | `owasp_eligible_recommendations_total` | OWASP citation coverage |

On **remediation rows**, enter integer values from 0 to 3 for the six exact rubric dimensions: `technical_correctness_0_3`, `applicability_0_3`, `owasp_support_0_3`, `actionability_0_3`, `verification_0_3`, and `risk_awareness_0_3`. Leave finding-count fields blank on these rows and rubric fields blank on finding rows. If a dimension is not applicable, leave it blank and explain why in `reviewer_notes`; do not replace not-applicable values with perfect scores. Record unsafe advice explicitly in the notes and a separate adjudication log until a dedicated safety-label schema is frozen. Preserve reasons and supporting evidence/source references in the notes or an accompanying annotation file. The CSV is a coding worksheet, not a completed scoring or statistical-analysis pipeline; human annotation, validation of entered values, agreement analysis, cluster mapping, and inferential analysis are still required.

## 7. Run procedure and reproducibility

1. Freeze dataset, split, gold, corpus files and checksums, retrieval settings, prompt versions, output schema, implementation commit, and model configuration.
2. Run all four conditions on the same held-out cases, with three repetitions per case planned. Interleave/randomize condition order to reduce time-dependent provider effects. Log seed where supported; equal seeds do not guarantee deterministic provider output.
3. Preserve raw output and validation outcome before any repair. If a predefined schema-repair retry is allowed, apply the same maximum attempts to every condition and report first-pass versus final success separately. Never manually improve outputs before scoring.
4. Retain all failures. A provider outage may justify an explicitly documented batch rerun; do not rerun only low-quality outputs.
5. Blind and randomize outputs, collect judgments, resolve disagreements, and freeze the scoring file.
6. Run the preregistered analysis and generate tables from machine-readable data. Archive commands, package versions, runtime information, and source provenance.

Minimum manifest fields: run_id, UTC timestamp, protocol version, case and cluster IDs, split, repetition, condition, backend type, model and provider identifier, temperature and limits, prompts/hash, case/hash, corpus revision/hash, retrieved section IDs and scores, implementation commit, latency, tokens, request outcome, validation errors, and reviewer-file version. Do not log API keys or unredacted evidence in provider diagnostics.

## 8. Statistical analysis

Average repetitions within case and cases within scenario/environment cluster using prespecified weights; report those weights. Treat clusters as the independent resampling units. For bounded metrics, show raw cluster distributions and paired changes, not only a p-value.

Compute a 95% paired cluster bootstrap interval using 10,000 resamples with a recorded seed. Each resample draws cluster IDs with replacement and retains all four conditions for that cluster. Compute differences and the interaction as (B11−B01)−(B10−B00). This measures the grounding-effect difference between retrieval levels. Very small numbers of clusters limit interval reliability and must be stated.

The confirmatory family consists of preregistered contrasts on the selected primary outcomes: B11−B00, grounding averaged across retrieval levels, retrieval averaged across grounding levels, and interaction. Use Holm adjustment across the declared family, including multiple outcomes, if reporting significance tests. A paired sign/permutation test requires its exchangeability or symmetry assumptions to be considered; do not use it mechanically for every metric. Mixed-effects models with cluster random effects may be an explicitly planned secondary analysis if sample size supports them. Report effect sizes and uncertainty even if tests are nonsignificant.

Generation failures are included in the intention-to-evaluate report: successful complete-and-correct report rate uses all attempted cases. Semantic metrics conditional on a generated output are shown with their smaller denominator and cannot hide failure rates. Do not impute unknown expert scores as favorable. Record missing judgments and conduct a prespecified sensitivity analysis rather than quietly dropping them.

No post hoc selection of the best repetition, best prompt, or most favorable metric. Subgroup findings and unplanned analyses are exploratory. Distinguish “no evidence of improvement” from “evidence of no practically important difference”; an equivalence claim needs a prespecified margin and appropriate test.

## 9. Threats to validity

- **Construct:** evidence IDs do not prove claim support; generic OWASP relevance does not prove engine-specific correctness; polished text can influence ratings.
- **Internal:** grounding changes both access and instructions; retrieved context changes token length; provider drift and repeated-case familiarity may confound outcomes. Freeze versions, randomize order, and document limits.
- **External:** two engines, lab artifacts, chosen categories, and one provider do not represent all operational systems.
- **Statistical conclusion:** cases within clusters and repeated generations are correlated; small reviewer or cluster counts limit precision. Do not inflate n with repeats or individual claims.
- **Annotation:** reviewers may disagree on severity and acceptable fixes. Preserve uncertainty and agreement statistics; consensus does not erase disagreement.
- **Data leakage:** shared scenario variants, prompt-tuning on test failures, or reference answers in the corpus invalidate a clean held-out comparison.

## 10. Results table templates

No results are populated until experiments are executed.

| Condition | Attempted cases | Valid outputs | Supported claim precision | Fact coverage | Remediation correctness | Unsafe advice |
|---|---|---|---|---|---|---|
| B00 | Not run | — | — | — | — | — |
| B10 | Not run | — | — | — | — | — |
| B01 | Not run | — | — | — | — | — |
| B11 | Not run | — | — | — | — | — |

| Contrast | Outcome | Cluster count | Paired effect | 95% CI | Adjusted p if used |
|---|---|---|---|---|---|
| Full − base | To be specified before run | Not run | — | — | — |
| Grounding main effect | To be specified before run | Not run | — | — | — |
| Retrieval main effect | To be specified before run | Not run | — | — | — |
| Interaction | To be specified before run | Not run | — | — | — |

## 11. Go/no-go for research claims

Do not answer the RQs empirically until the real model has been run in every declared condition, held-out annotations exist, reviewers have completed scoring, and denominators and failure counts are accounted for. A working web demo, passing software tests, high citation-resolution rate, or a small set of synthetic examples demonstrates implementation only. Claims of OWASP certification, complete compliance, vulnerability discovery accuracy, or successful production remediation are outside this study's evidence.
