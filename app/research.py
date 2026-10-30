"""Blank expert annotation forms; no automatic semantic scores."""
import csv

REVIEW_FIELDS = [
    "blind_id", "finding_id", "row_type", "remediation_index", "reviewer_id",
    "supported", "contradicted", "unsupported", "essential_covered", "essential_total",
    "evidence_citation_supported_claims", "evidence_citation_claims_total",
    "evidence_dependent_claims_with_supporting_citation", "evidence_dependent_claims_total",
    "owasp_supported_cited_recommendations", "owasp_cited_recommendations_total",
    "owasp_eligible_recommendations_with_supporting_citation", "owasp_eligible_recommendations_total",
    "technical_correctness_0_3", "applicability_0_3", "owasp_support_0_3",
    "actionability_0_3", "verification_0_3", "risk_awareness_0_3", "reviewer_notes",
]


def blank_review_row(blind_id, finding_id, row_type, remediation_index=""):
    return {**dict.fromkeys(REVIEW_FIELDS, ""), "blind_id": blind_id,
            "finding_id": finding_id, "row_type": row_type, "remediation_index": remediation_index}


def write_review_form(path, reports):
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for blind_id, report in reports:
            for finding in report["findings"]:
                writer.writerow(blank_review_row(blind_id, finding["id"], "finding"))
                for index, _ in enumerate(finding["remediation"], 1):
                    writer.writerow(blank_review_row(blind_id, finding["id"], "remediation", index))
