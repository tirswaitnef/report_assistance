"""Best-effort redaction; users must sanitize evidence before importing it."""
import re

PATTERNS = [
    (re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"), "[REDACTED_GOOGLE_API_KEY]"),
    (re.compile(r"(?i)(\b(?:password|passwd|pwd|api[_-]?key|secret|token)\s*[=:]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s;,]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(\b(?:postgres(?:ql)?|mysql)://[^:\s/]+:)[^@\s]+(@)"), r"\1[REDACTED]\2"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"(?i)(authorization\s*:\s*bearer\s+)\S+"), r"\1[REDACTED]"),
]


def redact(text: str) -> str:
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_value(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    return value
