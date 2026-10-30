from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Evidence(StrictModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    source: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=12000)
    collected_at: str | None = Field(default=None, max_length=80)


Category = Literal[
    "sql_injection", "excessive_privileges", "tls_disabled", "exposed_database",
    "weak_auth", "audit_logging", "secrets_management", "other",
]


class Finding(StrictModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=240)
    category: Category
    severity: Literal["critical", "high", "medium", "low", "info"]
    description: str = Field(min_length=1, max_length=4000)
    asset: str = Field(min_length=1, max_length=240)
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)


class Case(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    database: Literal["PostgreSQL", "MySQL", "Other"]
    findings: list[Finding] = Field(min_length=1, max_length=30)
    evidence: list[Evidence] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_references(self):
        for name, values in [("finding", self.findings), ("evidence", self.evidence)]:
            ids = [value.id for value in values]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {name} IDs")
        available = {e.id for e in self.evidence}
        for finding in self.findings:
            if len(finding.evidence_ids) != len(set(finding.evidence_ids)):
                raise ValueError(f"Duplicate evidence references in {finding.id}")
            missing = set(finding.evidence_ids) - available
            if missing:
                raise ValueError(f"Unknown evidence IDs in {finding.id}: {sorted(missing)}")
        if sum(len(e.content) for e in self.evidence) > 100000:
            raise ValueError("Total evidence content exceeds 100000 characters")
        return self


class ReportRequest(StrictModel):
    case: Case
    grounding: bool = True
    rag: bool = True
    provider: Literal["template", "llm"] = "template"


class Claim(StrictModel):
    text: str = Field(min_length=1, max_length=3000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)


class Remediation(StrictModel):
    action: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=3000)
    verification: str = Field(min_length=1, max_length=3000)
    owasp_refs: list[str] = Field(default_factory=list, max_length=10)


class GeneratedFinding(StrictModel):
    id: str
    analysis: str = Field(min_length=1, max_length=6000)
    claims: list[Claim] = Field(default_factory=list, max_length=20)
    remediation: list[Remediation] = Field(default_factory=list, max_length=10)


class GeneratedOutput(StrictModel):
    findings: list[GeneratedFinding] = Field(min_length=1, max_length=30)
    _generation_metadata: dict = PrivateAttr(default_factory=dict)
